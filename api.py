"""FastAPI wrapper for hydro-efficiency — unchanged Python core, no Streamlit.

Run:
    uv run uvicorn api:app --host 127.0.0.1 --port 8613 --reload
"""
from __future__ import annotations

import base64
import io
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.efficiency.ahp import ahp_weights, combined_weights  # noqa: E402
from src.efficiency.critic import critic_weights  # noqa: E402
from src.efficiency.indicators import (  # noqa: E402
    aggregate_micro_by_year,
    calc_macro_indicators,
    calc_meso_indicators,
    calc_micro_indicators,
)
from src.efficiency.sample_data import (  # noqa: E402
    MICRO_FUNCS,
    create_sample_xlsx,
    default_ahp_matrix,
    macro_cycle_raw,
    meso_cycle_raw,
)
from src.efficiency.topsis import build_result_table, topsis_evaluate  # noqa: E402

app = FastAPI(title="hydro-efficiency-api", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3113",
        "http://127.0.0.1:3113",
        "https://hydro-efficiency.tianlizeng.cloud",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


LAYER_GROUPS = {
    "大循环": ["C1", "C2", "C3", "C4"],
    "小循环": ["C5", "C6"],
    "点循环": ["C7", "C8", "C9", "C10"],
}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/meta")
def meta_info() -> dict:
    return {
        "name": "efficiency",
        "title": "水效评估",
        "icon": "💧",
        "description": "工业园区水效评估 (AHP + CRITIC + TOPSIS)",
        "version": "1.0.0",
    }


def _load_from_upload(xlsx_bytes: bytes):
    """Parse uploaded xlsx into (df_macro, df_meso, micro_dict, ahp_matrix_df)."""
    xls = pd.ExcelFile(io.BytesIO(xlsx_bytes))
    sheet_names = xls.sheet_names

    df_macro = pd.read_excel(xls, sheet_name="大循环") if "大循环" in sheet_names else None
    df_meso = pd.read_excel(xls, sheet_name="小循环") if "小循环" in sheet_names else None

    micro_dict: dict[str, pd.DataFrame] = {}
    for sn in sheet_names:
        if sn.startswith("点循环-"):
            micro_dict[sn.replace("点循环-", "")] = pd.read_excel(xls, sheet_name=sn)

    if "AHP判断矩阵" in sheet_names:
        ahp_matrix_df = pd.read_excel(xls, sheet_name="AHP判断矩阵", index_col=0)
    else:
        ahp_matrix_df = default_ahp_matrix()

    return df_macro, df_meso, micro_dict, ahp_matrix_df


def _load_from_sample():
    df_macro = macro_cycle_raw()
    df_meso = meso_cycle_raw()
    micro_dict = {year: func() for year, func in MICRO_FUNCS.items()}
    ahp_matrix_df = default_ahp_matrix()
    return df_macro, df_meso, micro_dict, ahp_matrix_df


def _df_to_json_safe(df: pd.DataFrame, limit: int | None = None) -> dict:
    """DataFrame → {columns, rows, totalRows}. Handles NaN / datetime / numpy types."""
    total = len(df)
    sliced = df.head(limit) if limit is not None and total > limit else df
    parsed = json.loads(sliced.to_json(orient="split", date_format="iso", force_ascii=False))
    return {"columns": parsed["columns"], "rows": parsed["data"], "totalRows": total}


def _compute_efficiency_core(
    df_macro: pd.DataFrame | None,
    df_meso: pd.DataFrame | None,
    micro_dict: dict,
    ahp_matrix_df: pd.DataFrame,
    alpha: float,
) -> dict:
    """Core pipeline. Returns a dict of all intermediate + final DataFrames + scalars.

    Keys: ind_macro, ind_meso, ind_micro_by_year (dict[year]=df),
          merged_clean, weight_df, pilot_df, layer_w_df, topsis_df,
          xlsx_bytes, meta.
    """
    if df_macro is None or df_meso is None or not micro_dict:
        raise HTTPException(
            400,
            "需要大循环 + 小循环 + 至少一个点循环年度 sheet",
        )

    ind_macro = calc_macro_indicators(df_macro)
    ind_meso = calc_meso_indicators(df_meso)
    ind_micro_agg = aggregate_micro_by_year(micro_dict)

    merged = ind_macro.merge(ind_meso, on="年度", how="inner")
    merged = merged.merge(ind_micro_agg, on="年度", how="inner")
    indicator_cols = [c for c in merged.columns if c.startswith("C")]
    merged_clean = merged.dropna(subset=indicator_cols).reset_index(drop=True)

    if len(merged_clean) < 2:
        raise HTTPException(400, "有效年度数据不足（至少 2 年完整数据）")

    directions = np.array([-1 if "漏损" in c else 1 for c in indicator_cols])

    matrix = ahp_matrix_df.values.astype(float)
    w_ahp, cr, consistent = ahp_weights(matrix)

    data_matrix = merged_clean[indicator_cols].values.astype(float)
    w_critic = critic_weights(data_matrix, directions)
    w_combined = combined_weights(w_ahp, w_critic, alpha)

    weight_df = pd.DataFrame({
        "指标": indicator_cols,
        "AHP权重": np.round(w_ahp, 4),
        "CRITIC权重": np.round(w_critic, 4),
        "组合权重": np.round(w_combined, 4),
    })

    layer_scores: dict[str, np.ndarray] = {}
    layer_weights: dict[str, float] = {}
    for name, prefixes in LAYER_GROUPS.items():
        idx = [i for i, c in enumerate(indicator_cols) if c.split("-")[0] in prefixes]
        sub_vals = merged_clean[indicator_cols].values[:, idx].astype(float)
        sub_dirs = directions[idx]
        sub_w = w_combined[idx]
        sub_w = sub_w / sub_w.sum()
        normed = np.zeros_like(sub_vals)
        for j in range(len(idx)):
            col_vals = sub_vals[:, j]
            rng = col_vals.max() - col_vals.min()
            if rng == 0:
                normed[:, j] = 1.0
            elif sub_dirs[j] == 1:
                normed[:, j] = (col_vals - col_vals.min()) / rng
            else:
                normed[:, j] = (col_vals.max() - col_vals) / rng
        layer_scores[name] = np.round((normed @ sub_w) * 100, 2)
        layer_weights[name] = float(w_combined[idx].sum())

    pilot_total = np.zeros(len(merged_clean))
    for name in LAYER_GROUPS:
        pilot_total += layer_scores[name] * layer_weights[name]
    pilot_total = np.round(pilot_total, 2)

    pilot_df = pd.DataFrame({
        "年度": merged_clean["年度"].values,
        "大循环评分": layer_scores["大循环"],
        "小循环评分": layer_scores["小循环"],
        "点循环评分": layer_scores["点循环"],
        "汇总评分": pilot_total,
    })

    layer_w_df = pd.DataFrame({
        "层面": list(layer_weights.keys()),
        "权重": [round(v, 4) for v in layer_weights.values()],
    })

    # TOPSIS on the latest year's micro data
    latest_year = sorted(micro_dict.keys())[-1]
    df_micro_latest = micro_dict[latest_year]
    ind_micro_latest = calc_micro_indicators(df_micro_latest)
    micro_cols = [c for c in ind_micro_latest.columns if c.startswith("C")]
    micro_idx = [i for i, c in enumerate(indicator_cols) if c in micro_cols]
    w_micro = w_combined[micro_idx]
    w_micro = w_micro / w_micro.sum()
    dirs_micro = np.ones(len(micro_cols))

    data_mat = ind_micro_latest[micro_cols].values.astype(float)
    names = ind_micro_latest["企业名称"].tolist()
    scores, closeness = topsis_evaluate(data_mat, w_micro, dirs_micro)
    topsis_df = build_result_table(names, scores, closeness)

    topsis_sheet_name = f"TOPSIS企业评价({latest_year})"

    sheets = {
        "年度综合指标矩阵": merged_clean,
        "权重详情": weight_df,
        "分层评分与试点汇总": pilot_df,
        "层面权重": layer_w_df,
        topsis_sheet_name: topsis_df,
    }

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
    xlsx_bytes = out.getvalue()

    # Per-year micro indicators (C7-C10) for Tab 1 preview
    ind_micro_by_year: dict[str, pd.DataFrame] = {}
    for year, df_raw in micro_dict.items():
        ind_micro_by_year[year] = calc_micro_indicators(df_raw)

    meta = {
        "years": int(len(merged_clean)),
        "cr": float(cr),
        "consistent": bool(consistent),
        "enterprises": int(len(names)),
        "latest_year": str(latest_year),
    }

    return {
        "ind_macro": ind_macro,
        "ind_meso": ind_meso,
        "ind_micro_by_year": ind_micro_by_year,
        "df_macro_raw": df_macro,
        "df_meso_raw": df_meso,
        "micro_dict_raw": micro_dict,
        "merged_clean": merged_clean,
        "weight_df": weight_df,
        "pilot_df": pilot_df,
        "layer_w_df": layer_w_df,
        "topsis_df": topsis_df,
        "topsis_sheet_name": topsis_sheet_name,
        "indicator_cols": indicator_cols,
        "w_ahp": w_ahp,
        "w_critic": w_critic,
        "w_combined": w_combined,
        "layer_weights": layer_weights,
        "xlsx_bytes": xlsx_bytes,
        "sheets": sheets,
        "meta": meta,
    }


def _run_efficiency(
    df_macro: pd.DataFrame | None,
    df_meso: pd.DataFrame | None,
    micro_dict: dict,
    ahp_matrix_df: pd.DataFrame,
    alpha: float,
) -> tuple[bytes, dict]:
    """Port of app.py's multi-tab compute into a single pipeline.

    Returns (xlsx_bytes, summary_meta).
    """
    out = _compute_efficiency_core(df_macro, df_meso, micro_dict, ahp_matrix_df, alpha)
    return out["xlsx_bytes"], out["meta"]


def _run_efficiency_full(
    df_macro: pd.DataFrame | None,
    df_meso: pd.DataFrame | None,
    micro_dict: dict,
    ahp_matrix_df: pd.DataFrame,
    alpha: float,
) -> dict:
    """JSON-friendly full payload for Next.js client: preview / meta / results / charts."""
    started = time.perf_counter()
    core = _compute_efficiency_core(df_macro, df_meso, micro_dict, ahp_matrix_df, alpha)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    ind_micro_by_year_json = {
        year: _df_to_json_safe(df) for year, df in core["ind_micro_by_year"].items()
    }
    micro_raw_by_year_json = {
        year: _df_to_json_safe(df) for year, df in core["micro_dict_raw"].items()
    }

    # Charts
    weights_chart = [
        {
            "指标": ind,
            "AHP": round(float(core["w_ahp"][i]), 4),
            "CRITIC": round(float(core["w_critic"][i]), 4),
            "组合": round(float(core["w_combined"][i]), 4),
        }
        for i, ind in enumerate(core["indicator_cols"])
    ]
    layer_weights_chart = [
        {"层面": name, "权重": round(float(v), 4)}
        for name, v in core["layer_weights"].items()
    ]
    grade_counts_series = core["topsis_df"]["水效等级"].value_counts()
    grade_color_map = {
        "水效领跑": "#1890ff",
        "水效先进": "#52c41a",
        "水效达标": "#faad14",
        "水效待改进": "#f5222d",
    }
    grade_distribution_chart = [
        {"grade": str(name), "count": int(cnt), "color": grade_color_map.get(str(name), "#999")}
        for name, cnt in grade_counts_series.items()
    ]

    results_payload: dict[str, dict] = {}
    for name, df in core["sheets"].items():
        results_payload[name] = _df_to_json_safe(df)

    return {
        "preview": {
            "macro_raw": _df_to_json_safe(core["df_macro_raw"]),
            "macro_indicators": _df_to_json_safe(core["ind_macro"]),
            "meso_raw": _df_to_json_safe(core["df_meso_raw"]),
            "meso_indicators": _df_to_json_safe(core["ind_meso"]),
            "micro_raw_by_year": micro_raw_by_year_json,
            "micro_indicators_by_year": ind_micro_by_year_json,
        },
        "meta": {
            "years": core["meta"]["years"],
            "cr": core["meta"]["cr"],
            "consistent": core["meta"]["consistent"],
            "enterprises": core["meta"]["enterprises"],
            "latestYear": core["meta"]["latest_year"],
            "elapsedMs": elapsed_ms,
            "xlsxBytes": len(core["xlsx_bytes"]),
            "topsisSheetName": core["topsis_sheet_name"],
        },
        "results": results_payload,
        "charts": {
            "weights": weights_chart,
            "layerWeights": layer_weights_chart,
            "gradeDistribution": grade_distribution_chart,
        },
        "xlsxBase64": base64.b64encode(core["xlsx_bytes"]).decode("ascii"),
    }


@app.post("/api/compute")
async def compute(
    file: UploadFile | None = File(None, description="xlsx — 大循环/小循环/点循环-YYYY年/AHP判断矩阵"),
    alpha: float = Form(0.5, ge=0.0, le=1.0, description="AHP 权重占比 (0-1)"),
    use_sample: bool = Form(False, description="忽略上传，用内置示例数据"),
    format: str = Form("xlsx", description="xlsx (binary) | json (preview+results+charts+base64)"),
) -> Response:
    if use_sample or file is None:
        df_macro, df_meso, micro_dict, ahp_matrix_df = _load_from_sample()
    else:
        content = await file.read()
        if not content:
            raise HTTPException(400, "上传文件为空")
        df_macro, df_meso, micro_dict, ahp_matrix_df = _load_from_upload(content)

    try:
        if format == "json":
            payload = _run_efficiency_full(
                df_macro, df_meso, micro_dict, ahp_matrix_df, alpha
            )
            return JSONResponse(content=payload)
        xlsx_bytes, meta = _run_efficiency(df_macro, df_meso, micro_dict, ahp_matrix_df, alpha)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(
            500,
            f"计算失败: {type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}",
        )
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="efficiency_result.xlsx"',
            "X-Years": str(meta["years"]),
            "X-Cr": f"{meta['cr']:.4f}",
            "X-Consistent": "1" if meta["consistent"] else "0",
            "X-Enterprises": str(meta["enterprises"]),
            "X-Latest-Year": quote(str(meta["latest_year"])),
            "Access-Control-Expose-Headers": "X-Years, X-Cr, X-Consistent, X-Enterprises, X-Latest-Year, Content-Disposition",
        },
    )


@app.get("/api/sample")
def sample_xlsx() -> Response:
    buf = create_sample_xlsx()
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="efficiency_sample.xlsx"'},
    )
