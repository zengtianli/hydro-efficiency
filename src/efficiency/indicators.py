"""指标计算模块 - 原始数据 → C1-C10"""
import pandas as pd
import numpy as np


def calc_macro_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """大循环层面指标计算 (C1-C4)

    输入列: 年度, 再生水利用量, 污水处理量, 工业增加值, 再生水供水量, 再生水售水量
    """
    result = pd.DataFrame({"年度": df["年度"]})

    result["C1-再生水利用率(%)"] = (
        df["再生水利用量(万m³)"] / df["污水处理量(万m³)"] * 100
    ).round(2)

    # 万m³ / 亿元 → m³/万元: ×10 (1万m³=10000m³, 1亿元=1000万元, 10000/1000=10)
    result["C2-万元工业增加值再生水利用量(m³/万元)"] = (
        df["再生水利用量(万m³)"] / df["工业增加值(亿元)"] * 10
    ).round(2)

    result["C3-再生水管网漏损率(%)"] = (
        (df["再生水供水量(万m³)"] - df["再生水售水量(万m³)"])
        / df["再生水供水量(万m³)"] * 100
    ).round(2)

    # C4: 增长率，第一行无法计算
    rec = df["再生水利用量(万m³)"].values
    growth = [np.nan] + [
        (rec[i] - rec[i - 1]) / rec[i - 1] * 100 for i in range(1, len(rec))
    ]
    result["C4-再生水利用量增长率(%)"] = np.round(growth, 2)

    return result


def calc_meso_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """小循环层面指标计算 (C5-C6)"""
    result = pd.DataFrame({"年度": df["年度"]})

    result["C5-企业再生水管网覆盖率(%)"] = (
        df["接入再生水管网企业数(家)"] / df["企业总数(家)"] * 100
    ).round(2)

    rec = df["园区再生水利用量(万m³)"].values
    growth = [np.nan] + [
        (rec[i] - rec[i - 1]) / rec[i - 1] * 100 for i in range(1, len(rec))
    ]
    result["C6-再生水利用量增长率(%)"] = np.round(growth, 2)

    return result


def calc_micro_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """点循环层面指标计算 (C7-C10)

    自动检测列名中是否包含"上年同期"来适配不同时期数据。
    """
    result = pd.DataFrame({"企业名称": df["企业名称"]})

    result["C7-工业用水重复利用率(%)"] = (
        df["重复利用水量(万m³)"]
        / (df["取水量(万m³)"] + df["重复利用水量(万m³)"]) * 100
    ).round(2)

    result["C8-间接冷却水循环利用率(%)"] = (
        df["间接冷却水循环量(万m³)"]
        / (df["间接冷却水取水量(万m³)"] + df["间接冷却水循环量(万m³)"]) * 100
    ).round(2)

    result["C9-工艺水回用率(%)"] = (
        df["工艺水回用量(万m³)"] / df["工艺用水总量(万m³)"] * 100
    ).round(2)

    # 自动检测上年列名
    prev_col = [c for c in df.columns if "上年" in c and "再生水" in c]
    if prev_col:
        result["C10-再生水利用量增长率(%)"] = (
            (df["再生水利用量(万m³)"] - df[prev_col[0]])
            / df[prev_col[0]] * 100
        ).round(2)
    return result


def aggregate_micro_by_year(
    micro_dict: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """将各年度企业级点循环指标取均值，聚合为年度级数据。

    Parameters
    ----------
    micro_dict : {年度标签: 企业原始数据 DataFrame}

    Returns
    -------
    DataFrame: 行=年度, 列=C7-C10 均值
    """
    rows = []
    for year, df_raw in micro_dict.items():
        ind = calc_micro_indicators(df_raw)
        ind_cols = [c for c in ind.columns if c.startswith("C")]
        means = ind[ind_cols].mean()
        means["年度"] = year
        rows.append(means)
    return pd.DataFrame(rows)[["年度"] + [c for c in rows[0].index if c.startswith("C")]]
