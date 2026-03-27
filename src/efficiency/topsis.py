"""TOPSIS 综合评价 + 等级划分"""
import numpy as np
import pandas as pd

# 等级划分标准
GRADES = [
    (80, "水效领跑", "#1890ff"),   # 蓝
    (60, "水效先进", "#52c41a"),   # 绿
    (40, "水效达标", "#faad14"),   # 黄
    (0,  "水效待改进", "#f5222d"), # 红
]


def topsis_evaluate(
    data: np.ndarray,
    weights: np.ndarray,
    directions: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """TOPSIS 评价

    Parameters
    ----------
    data : ndarray, shape (m, n)
        m 个评价对象, n 个指标的原始值
    weights : ndarray, shape (n,)
    directions : ndarray, shape (n,)
        1=正向, -1=负向

    Returns
    -------
    scores : ndarray, shape (m,)  百分制得分
    closeness : ndarray, shape (m,)  相对贴近度
    """
    m, n = data.shape
    data = data.astype(float)

    # 向量归一化（按列）
    col_norms = np.sqrt((data ** 2).sum(axis=0))
    col_norms[col_norms == 0] = 1
    normed = data / col_norms

    # 加权
    weighted = normed * weights

    # 正理想解 / 负理想解
    ideal_best = np.zeros(n)
    ideal_worst = np.zeros(n)
    for j in range(n):
        if directions[j] == 1:
            ideal_best[j] = weighted[:, j].max()
            ideal_worst[j] = weighted[:, j].min()
        else:
            ideal_best[j] = weighted[:, j].min()
            ideal_worst[j] = weighted[:, j].max()

    # 距离
    d_best = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
    d_worst = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))

    # 相对贴近度
    denom = d_best + d_worst
    denom[denom == 0] = 1
    closeness = d_worst / denom

    scores = closeness * 100
    return np.round(scores, 2), np.round(closeness, 4)


def classify(score: float) -> tuple[str, str]:
    """根据得分返回 (等级名称, 颜色hex)"""
    for threshold, name, color in GRADES:
        if score >= threshold:
            return name, color
    return GRADES[-1][1], GRADES[-1][2]


def build_result_table(
    names: list[str],
    scores: np.ndarray,
    closeness: np.ndarray,
) -> pd.DataFrame:
    """构建结果表"""
    grades = [classify(s) for s in scores]
    return pd.DataFrame({
        "企业名称": names,
        "相对贴近度": closeness,
        "水效评分": scores,
        "水效等级": [g[0] for g in grades],
        "预警颜色": [g[1] for g in grades],
    }).sort_values("水效评分", ascending=False).reset_index(drop=True)
