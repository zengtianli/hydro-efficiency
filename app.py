"""浙水设计-水效评估分析系统"""
import sys
from pathlib import Path


import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO

from src.common.st_utils import page_config, footer
from src.efficiency.sample_data import (
    macro_cycle_raw, meso_cycle_raw,
    MICRO_FUNCS, default_ahp_matrix, create_sample_xlsx,
)
from src.efficiency.indicators import (
    calc_macro_indicators, calc_meso_indicators, calc_micro_indicators,
    aggregate_micro_by_year,
)
from src.efficiency.ahp import ahp_weights, combined_weights
from src.efficiency.critic import critic_weights
from src.efficiency.topsis import topsis_evaluate, classify, build_result_table

# C1-C10 指标方向: 1=正向, -1=负向
DIRECTIONS_ALL = np.array([1, 1, -1, 1, 1, 1, 1, 1, 1, 1])
ALL_INDICATOR_COLS = [
    "C1-再生水利用率(%)", "C2-万元工业增加值再生水利用量(m³/万元)",
    "C3-再生水管网漏损率(%)", "C4-再生水利用量增长率(%)",
    "C5-企业再生水管网覆盖率(%)", "C6-再生水利用量增长率(%)",
    "C7-工业用水重复利用率(%)", "C8-间接冷却水循环利用率(%)",
    "C9-工艺水回用率(%)", "C10-再生水利用量增长率(%)",
]

page_config("水效评估 - Hydro Toolkit", "💧")
st.title("💧 水效评估")
st.caption("工业集聚区水效评估 | AHP + CRITIC + TOPSIS")

# ── 侧边栏 ──
st.sidebar.header("数据设置")
data_source = st.sidebar.radio("数据来源", ["示例数据", "上传数据"])
alpha = st.sidebar.slider("AHP权重占比 (α)", 0.0, 1.0, 0.5, 0.05)

# 下载示例数据
st.sidebar.markdown("---")
st.sidebar.download_button(
    "下载示例数据 (Excel)",
    data=create_sample_xlsx(),
    file_name="示例数据.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# ── 加载数据 ──
df_macro = None
df_meso = None
micro_dict = {}  # {年度: DataFrame}
ahp_matrix_df = default_ahp_matrix()

if data_source == "示例数据":
    df_macro = macro_cycle_raw()
    df_meso = meso_cycle_raw()
    micro_dict = {year: func() for year, func in MICRO_FUNCS.items()}
else:
    st.sidebar.markdown("---")
    st.sidebar.subheader("上传数据文件")
    uploaded = st.sidebar.file_uploader(
        "上传数据 Excel（含大循环/小循环/点循环/AHP sheet）",
        type=["xlsx"],
    )
    if uploaded:
        xls = pd.ExcelFile(uploaded)
        sheet_names = xls.sheet_names
        # 大循环
        if "大循环" in sheet_names:
            df_macro = pd.read_excel(xls, sheet_name="大循环")
        # 小循环
        if "小循环" in sheet_names:
            df_meso = pd.read_excel(xls, sheet_name="小循环")
        # 点循环：匹配 "点循环-xxxx年" 格式的 sheet
        for sn in sheet_names:
            if sn.startswith("点循环-"):
                year_label = sn.replace("点循环-", "")
                micro_dict[year_label] = pd.read_excel(xls, sheet_name=sn)
        # AHP
        if "AHP判断矩阵" in sheet_names:
            ahp_matrix_df = pd.read_excel(xls, sheet_name="AHP判断矩阵", index_col=0)

# ── 主界面 Tabs ──
tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 数据与指标", "⚖️ 权重计算", "🏆 TOPSIS评价", "📈 可视化分析"]
)

# ================================================================
# Tab 1: 数据与指标计算
# ================================================================
with tab1:
    st.header("原始数据与指标计算")

    st.subheader("大循环层面")
    if df_macro is not None:
        st.dataframe(df_macro, use_container_width=True)
        ind_macro = calc_macro_indicators(df_macro)
        st.markdown("**计算结果 (C1-C4)**")
        st.dataframe(ind_macro, use_container_width=True)
    else:
        st.info("请上传包含「大循环」sheet 的数据文件")

    st.markdown("---")
    st.subheader("小循环层面")
    if df_meso is not None:
        st.dataframe(df_meso, use_container_width=True)
        ind_meso = calc_meso_indicators(df_meso)
        st.markdown("**计算结果 (C5-C6)**")
        st.dataframe(ind_meso, use_container_width=True)
    else:
        st.info("请上传包含「小循环」sheet 的数据文件")

    st.markdown("---")
    st.subheader("点循环层面（企业数据）")

    if micro_dict:
        year_options = list(micro_dict.keys())
        year_choice = st.radio("选择年度", year_options, horizontal=True)
        df_micro = micro_dict[year_choice]
        st.dataframe(df_micro, use_container_width=True)
        ind_micro = calc_micro_indicators(df_micro)
        st.markdown("**计算结果 (C7-C10)**")
        st.dataframe(ind_micro, use_container_width=True)
        st.session_state["eff_ind_micro"] = ind_micro
        st.session_state["eff_df_micro"] = df_micro
    else:
        st.info("请上传包含「点循环-xxxx年」sheet 的数据文件")

# ================================================================
# Tab 2: 权重计算 (C1-C10 全覆盖)
# ================================================================
with tab2:
    st.header("权重计算（C1-C10）")

    # 构建年度 × C1-C10 矩阵
    can_build = (df_macro is not None and df_meso is not None and micro_dict)
    if not can_build:
        st.warning("请先在「数据与指标」页加载完整的大循环、小循环、点循环数据")
        st.stop()

    ind_macro = calc_macro_indicators(df_macro)
    ind_meso = calc_meso_indicators(df_meso)
    ind_micro_agg = aggregate_micro_by_year(micro_dict)

    # 按年度合并: 大循环(C1-C4) + 小循环(C5-C6) + 点循环均值(C7-C10)
    merged = ind_macro.merge(ind_meso, on="年度", how="inner")
    merged = merged.merge(ind_micro_agg, on="年度", how="inner")

    # 只保留有完整数据的行（去掉含 NaN 的年度，如增长率首年）
    indicator_cols = [c for c in merged.columns if c.startswith("C")]
    merged_clean = merged.dropna(subset=indicator_cols).reset_index(drop=True)

    if len(merged_clean) < 2:
        st.warning("有效年度数据不足（至少需要2年完整数据），请检查数据")
        st.stop()

    st.markdown("**年度综合指标矩阵**（点循环为企业均值）")
    st.dataframe(merged_clean, use_container_width=True)

    n_ind = len(indicator_cols)
    # 指标方向：C3 为负向，其余正向
    directions = np.array([
        -1 if "漏损" in c else 1 for c in indicator_cols
    ])

    col_ahp, col_critic = st.columns(2)

    with col_ahp:
        st.subheader("AHP 主观赋权")
        st.markdown("判断矩阵（可编辑）：")
        edited_ahp = st.data_editor(
            ahp_matrix_df, use_container_width=True, num_rows="fixed"
        )
        matrix = edited_ahp.values.astype(float)
        w_ahp, cr, consistent = ahp_weights(matrix)

        st.markdown(f"**一致性比率 CR = {cr:.4f}**")
        if consistent:
            st.success("通过一致性检验 (CR < 0.1)")
        else:
            st.error("未通过一致性检验，请调整判断矩阵")

        ahp_df = pd.DataFrame({
            "指标": indicator_cols,
            "AHP权重": np.round(w_ahp, 4),
        })
        st.dataframe(ahp_df, use_container_width=True, hide_index=True)

    with col_critic:
        st.subheader("CRITIC 客观赋权")
        data_matrix = merged_clean[indicator_cols].values.astype(float)
        w_critic = critic_weights(data_matrix, directions)

        critic_df = pd.DataFrame({
            "指标": indicator_cols,
            "CRITIC权重": np.round(w_critic, 4),
        })
        st.dataframe(critic_df, use_container_width=True, hide_index=True)

    # ── 组合权重 ──
    st.markdown("---")
    st.subheader("组合权重")
    w_combined = combined_weights(w_ahp, w_critic, alpha)

    weight_df = pd.DataFrame({
        "指标": indicator_cols,
        "AHP权重": np.round(w_ahp, 4),
        "CRITIC权重": np.round(w_critic, 4),
        "组合权重": np.round(w_combined, 4),
    })
    st.dataframe(weight_df, use_container_width=True, hide_index=True)

    fig_w = go.Figure()
    fig_w.add_trace(go.Bar(name="AHP", x=indicator_cols, y=w_ahp))
    fig_w.add_trace(go.Bar(name="CRITIC", x=indicator_cols, y=w_critic))
    fig_w.add_trace(go.Bar(name="组合", x=indicator_cols, y=w_combined))
    fig_w.update_layout(barmode="group", height=350, title="权重对比")
    st.plotly_chart(fig_w, use_container_width=True)

    # ── 分层评分 ──
    st.markdown("---")
    st.subheader("分层评分与试点汇总")

    # 层面分组定义
    LAYER_GROUPS = {
        "大循环": ["C1", "C2", "C3", "C4"],
        "小循环": ["C5", "C6"],
        "点循环": ["C7", "C8", "C9", "C10"],
    }

    def _layer_score(layer_prefixes):
        """计算某层面的年度百分制评分"""
        idx = [i for i, c in enumerate(indicator_cols)
               if c.split("-")[0] in layer_prefixes]
        sub_vals = merged_clean[indicator_cols].values[:, idx].astype(float)
        sub_dirs = directions[idx]
        sub_w = w_combined[idx]
        sub_w = sub_w / sub_w.sum()  # 归一化子权重
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
        return np.round((normed @ sub_w) * 100, 2)

    # 计算各层面评分
    layer_scores = {}
    layer_weights = {}
    for name, prefixes in LAYER_GROUPS.items():
        layer_scores[name] = _layer_score(prefixes)
        idx = [i for i, c in enumerate(indicator_cols)
               if c.split("-")[0] in prefixes]
        layer_weights[name] = w_combined[idx].sum()

    # 三列展示各层面评分
    col_l1, col_l2, col_l3 = st.columns(3)
    for col, (name, prefixes) in zip(
        [col_l1, col_l2, col_l3], LAYER_GROUPS.items()
    ):
        with col:
            w_pct = f"{layer_weights[name] * 100:.1f}%"
            st.markdown(f"**{name}评分**（层面权重 {w_pct}）")
            layer_df = pd.DataFrame({
                "年度": merged_clean["年度"].values,
                "评分": layer_scores[name],
            })
            st.dataframe(layer_df, use_container_width=True, hide_index=True)

    # 试点汇总评分
    st.markdown("---")
    st.markdown("**试点汇总评分** = 大循环评分 × w₁ + 小循环评分 × w₂ + 点循环评分 × w₃")
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
    st.dataframe(pilot_df, use_container_width=True, hide_index=True)

    # 层面权重表
    lw_df = pd.DataFrame({
        "层面": list(layer_weights.keys()),
        "权重": [round(v, 4) for v in layer_weights.values()],
    })
    st.dataframe(lw_df, use_container_width=True, hide_index=True)

    # 存入 session_state
    st.session_state["eff_w_combined"] = w_combined
    st.session_state["eff_directions"] = directions
    st.session_state["eff_indicator_cols"] = indicator_cols
    st.session_state["eff_weight_df"] = weight_df
    st.session_state["eff_pilot_df"] = pilot_df
    st.session_state["eff_layer_scores"] = layer_scores
    st.session_state["eff_layer_weights"] = layer_weights
    st.session_state["eff_merged_clean"] = merged_clean

# ================================================================
# Tab 3: TOPSIS 企业评价 (C7-C10)
# ================================================================
with tab3:
    st.header("TOPSIS 企业评价")

    needed = ["ind_micro", "w_combined", "indicator_cols"]
    if not all(k in st.session_state for k in needed):
        st.warning("请先完成「数据与指标」和「权重计算」")
        st.stop()

    ind_micro = st.session_state["eff_ind_micro"]
    w_all = st.session_state["eff_w_combined"]
    all_cols = st.session_state["eff_indicator_cols"]

    # 提取 C7-C10 子集权重并重新归一化
    micro_cols = [c for c in ind_micro.columns if c.startswith("C")]
    micro_idx = [i for i, c in enumerate(all_cols) if c in micro_cols]
    w_micro = w_all[micro_idx]
    w_micro = w_micro / w_micro.sum()  # 归一化
    dirs_micro = np.ones(len(micro_cols))  # C7-C10 全部正向

    st.markdown(f"**使用 C7-C10 组合权重（从全局权重提取并归一化）**")
    micro_weight_df = pd.DataFrame({
        "指标": micro_cols,
        "归一化权重": np.round(w_micro, 4),
    })
    st.dataframe(micro_weight_df, use_container_width=True, hide_index=True)

    data_mat = ind_micro[micro_cols].values.astype(float)
    names = ind_micro["企业名称"].tolist()

    scores, closeness = topsis_evaluate(data_mat, w_micro, dirs_micro)
    result_df = build_result_table(names, scores, closeness)

    def _color_grade(row):
        color = row["预警颜色"]
        return [f"background-color: {color}20" for _ in row]

    st.dataframe(
        result_df.style.apply(_color_grade, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### 等级分布")
    grade_counts = result_df["水效等级"].value_counts()
    fig_pie = px.pie(
        values=grade_counts.values,
        names=grade_counts.index,
        color=grade_counts.index,
        color_discrete_map={
            "水效领跑": "#1890ff",
            "水效先进": "#52c41a",
            "水效达标": "#faad14",
            "水效待改进": "#f5222d",
        },
    )
    fig_pie.update_layout(height=350)
    st.plotly_chart(fig_pie, use_container_width=True)

    # ── 导出结果 ──
    st.markdown("### 导出结果")
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        has_layers = "layer_scores" in st.session_state
        if has_layers:
            mc = st.session_state["eff_merged_clean"]
            ls = st.session_state["eff_layer_scores"]
            lw = st.session_state["eff_layer_weights"]

        # ── Sheet 1: 综合评价结果 ──
        row = 0
        ws_name = "综合评价结果"
        # 试点汇总评分
        if "pilot_df" in st.session_state:
            pilot = st.session_state["eff_pilot_df"]
            pd.DataFrame([["【试点汇总评分】"]]).to_excel(
                writer, sheet_name=ws_name, startrow=row,
                index=False, header=False,
            )
            row += 1
            pilot.to_excel(
                writer, sheet_name=ws_name, startrow=row, index=False,
            )
            row += len(pilot) + 2
        # TOPSIS 企业评价
        pd.DataFrame([["【TOPSIS企业评价】"]]).to_excel(
            writer, sheet_name=ws_name, startrow=row,
            index=False, header=False,
        )
        row += 1
        result_df.to_excel(
            writer, sheet_name=ws_name, startrow=row, index=False,
        )

        # ── Sheet 2: 指标明细 ──
        row = 0
        ws_name = "指标明细"
        # 大循环：原始数据与指标横向合并
        if df_macro is not None:
            ind_mac = calc_macro_indicators(df_macro)
            macro_merged = df_macro.merge(
                ind_mac, on="年度", how="left",
            )
            pd.DataFrame([["【大循环 — 原始数据 + 指标(C1-C4)】"]]).to_excel(
                writer, sheet_name=ws_name, startrow=row,
                index=False, header=False,
            )
            row += 1
            macro_merged.to_excel(
                writer, sheet_name=ws_name, startrow=row, index=False,
            )
            row += len(macro_merged) + 1
            # 大循环评分
            if has_layers:
                pd.DataFrame({
                    "年度": mc["年度"].values,
                    "大循环评分": ls["大循环"],
                    "层面权重": round(lw["大循环"], 4),
                }).to_excel(
                    writer, sheet_name=ws_name, startrow=row, index=False,
                )
                row += len(mc) + 2

        # 小循环
        if df_meso is not None:
            ind_mes = calc_meso_indicators(df_meso)
            meso_merged = df_meso.merge(
                ind_mes, on="年度", how="left",
            )
            pd.DataFrame([["【小循环 — 原始数据 + 指标(C5-C6)】"]]).to_excel(
                writer, sheet_name=ws_name, startrow=row,
                index=False, header=False,
            )
            row += 1
            meso_merged.to_excel(
                writer, sheet_name=ws_name, startrow=row, index=False,
            )
            row += len(meso_merged) + 1
            if has_layers:
                pd.DataFrame({
                    "年度": mc["年度"].values,
                    "小循环评分": ls["小循环"],
                    "层面权重": round(lw["小循环"], 4),
                }).to_excel(
                    writer, sheet_name=ws_name, startrow=row, index=False,
                )
                row += len(mc) + 2

        # 点循环：各年度企业指标
        for year, df_raw in micro_dict.items():
            ind_y = calc_micro_indicators(df_raw)
            pd.DataFrame([[f"【点循环 — {year} 企业指标(C7-C10)】"]]).to_excel(
                writer, sheet_name=ws_name, startrow=row,
                index=False, header=False,
            )
            row += 1
            ind_y.to_excel(
                writer, sheet_name=ws_name, startrow=row, index=False,
            )
            row += len(ind_y) + 2
        if has_layers:
            pd.DataFrame({
                "年度": mc["年度"].values,
                "点循环评分(企业均值)": ls["点循环"],
                "层面权重": round(lw["点循环"], 4),
            }).to_excel(
                writer, sheet_name=ws_name, startrow=row, index=False,
            )

        # ── Sheet 3: 权重明细 ──
        row = 0
        ws_name = "权重明细"
        if "weight_df" in st.session_state:
            pd.DataFrame([["【C1-C10 组合权重】"]]).to_excel(
                writer, sheet_name=ws_name, startrow=row,
                index=False, header=False,
            )
            row += 1
            wdf = st.session_state["eff_weight_df"]
            wdf.to_excel(
                writer, sheet_name=ws_name, startrow=row, index=False,
            )
            row += len(wdf) + 2

        pd.DataFrame([["【点循环归一化权重(C7-C10)】"]]).to_excel(
            writer, sheet_name=ws_name, startrow=row,
            index=False, header=False,
        )
        row += 1
        micro_weight_df.to_excel(
            writer, sheet_name=ws_name, startrow=row, index=False,
        )
        row += len(micro_weight_df) + 2

        if has_layers:
            pd.DataFrame([["【层面权重】"]]).to_excel(
                writer, sheet_name=ws_name, startrow=row,
                index=False, header=False,
            )
            row += 1
            pd.DataFrame({
                "层面": list(lw.keys()),
                "权重": [round(v, 4) for v in lw.values()],
            }).to_excel(
                writer, sheet_name=ws_name, startrow=row, index=False,
            )

    st.download_button(
        "下载评价结果 (Excel)",
        data=buf.getvalue(),
        file_name="水效评价结果.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.session_state["eff_result_df"] = result_df

# ================================================================
# Tab 4: 可视化分析
# ================================================================
with tab4:
    st.header("可视化分析")

    if "result_df" not in st.session_state:
        st.warning("请先完成 TOPSIS 评价")
        st.stop()

    result_df = st.session_state["eff_result_df"]
    ind_micro = st.session_state["eff_ind_micro"]
    micro_cols = [c for c in ind_micro.columns if c.startswith("C")]

    # ── 试点评分趋势（分层 + 汇总）──
    if "pilot_df" in st.session_state:
        st.subheader("试点评分趋势")
        pilot_df = st.session_state["eff_pilot_df"]
        fig_pilot = go.Figure()
        for col_name in ["大循环评分", "小循环评分", "点循环评分"]:
            fig_pilot.add_trace(go.Scatter(
                x=pilot_df["年度"], y=pilot_df[col_name],
                mode="lines+markers", name=col_name,
                line=dict(dash="dot"),
            ))
        fig_pilot.add_trace(go.Scatter(
            x=pilot_df["年度"], y=pilot_df["汇总评分"],
            mode="lines+markers+text",
            text=pilot_df["汇总评分"].astype(str),
            textposition="top center", name="汇总评分",
            line=dict(width=3),
        ))
        fig_pilot.update_layout(height=400, title="试点水效评分趋势",
                                yaxis_range=[0, 100])
        st.plotly_chart(fig_pilot, use_container_width=True)

    # ── 各层面指标趋势 ──
    if "merged_clean" in st.session_state:
        merged_clean = st.session_state["eff_merged_clean"]
        all_cols = st.session_state["eff_indicator_cols"]

        st.subheader("各层面指标趋势")
        col_t1, col_t2, col_t3 = st.columns(3)

        with col_t1:
            macro_cols_t = [c for c in all_cols if c.split("-")[0] in ("C1", "C2", "C3", "C4")]
            fig_m = go.Figure()
            for c in macro_cols_t:
                fig_m.add_trace(go.Scatter(
                    x=merged_clean["年度"], y=merged_clean[c],
                    mode="lines+markers",
                    name=c.split("-")[1] if "-" in c else c,
                ))
            fig_m.update_layout(height=350, title="大循环 (C1-C4)")
            st.plotly_chart(fig_m, use_container_width=True)

        with col_t2:
            meso_cols_t = [c for c in all_cols if c.split("-")[0] in ("C5", "C6")]
            fig_s = go.Figure()
            for c in meso_cols_t:
                fig_s.add_trace(go.Scatter(
                    x=merged_clean["年度"], y=merged_clean[c],
                    mode="lines+markers",
                    name=c.split("-")[1] if "-" in c else c,
                ))
            fig_s.update_layout(height=350, title="小循环 (C5-C6)")
            st.plotly_chart(fig_s, use_container_width=True)

        with col_t3:
            micro_cols_t = [c for c in all_cols if c.split("-")[0] in ("C7", "C8", "C9", "C10")]
            fig_p = go.Figure()
            for c in micro_cols_t:
                fig_p.add_trace(go.Scatter(
                    x=merged_clean["年度"], y=merged_clean[c],
                    mode="lines+markers",
                    name=c.split("-")[1] if "-" in c else c,
                ))
            fig_p.update_layout(height=350, title="点循环均值 (C7-C10)")
            st.plotly_chart(fig_p, use_container_width=True)

    # ── 企业雷达图 ──
    st.subheader("企业水效雷达图")
    selected = st.multiselect(
        "选择企业", ind_micro["企业名称"].tolist(),
        default=ind_micro["企业名称"].tolist()[:3],
    )
    if selected:
        fig_radar = go.Figure()
        for name in selected:
            row = ind_micro[ind_micro["企业名称"] == name][micro_cols].values[0]
            fig_radar.add_trace(go.Scatterpolar(
                r=list(row) + [row[0]],
                theta=[c.split("-")[0] for c in micro_cols] + [micro_cols[0].split("-")[0]],
                name=name,
                fill="toself",
                opacity=0.6,
            ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True)),
            height=450,
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    # ── 得分柱状图 ──
    st.subheader("水效评分排名")
    fig_bar = px.bar(
        result_df.sort_values("水效评分"),
        x="水效评分", y="企业名称",
        orientation="h",
        color="水效等级",
        color_discrete_map={
            "水效领跑": "#1890ff",
            "水效先进": "#52c41a",
            "水效达标": "#faad14",
            "水效待改进": "#f5222d",
        },
    )
    for threshold in [40, 60, 80]:
        fig_bar.add_vline(x=threshold, line_dash="dash", line_color="gray")
    fig_bar.update_layout(height=350)
    st.plotly_chart(fig_bar, use_container_width=True)

footer("水效评估", repo_url="https://github.com/zengtianli/hydro-efficiency")
