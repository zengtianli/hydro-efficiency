"""CRITIC 客观赋权"""
import numpy as np
import pandas as pd


def critic_weights(
    data: np.ndarray,
    directions: np.ndarray,
) -> np.ndarray:
    """计算 CRITIC 权重

    Parameters
    ----------
    data : ndarray, shape (m, n)
        m 个评价对象, n 个指标
    directions : ndarray, shape (n,)
        1=正向, -1=负向

    Returns
    -------
    weights : ndarray, shape (n,)
    """
    m, n = data.shape
    # 标准化
    normed = np.zeros_like(data, dtype=float)
    for j in range(n):
        col = data[:, j].astype(float)
        rng = col.max() - col.min()
        if rng == 0:
            normed[:, j] = 1.0
        elif directions[j] == 1:
            normed[:, j] = (col - col.min()) / rng
        else:
            normed[:, j] = (col.max() - col) / rng

    # 标准差
    sigma = normed.std(axis=0, ddof=1)

    # 相关系数矩阵
    corr = np.corrcoef(normed, rowvar=False)
    # 处理 NaN（当某列标准差为 0 时）
    corr = np.nan_to_num(corr, nan=1.0)

    # 信息量
    info = np.zeros(n)
    for j in range(n):
        conflict = sum(1 - abs(corr[j, k]) for k in range(n) if k != j)
        info[j] = sigma[j] * conflict

    total = info.sum()
    if total == 0:
        return np.ones(n) / n
    return info / total
