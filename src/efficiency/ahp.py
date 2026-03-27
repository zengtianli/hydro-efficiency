"""AHP 主观赋权"""
import numpy as np

# 随机一致性指标 RI
_RI = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12,
       6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}


def ahp_weights(matrix: np.ndarray):
    """计算 AHP 权重并进行一致性检验

    Parameters
    ----------
    matrix : ndarray, shape (n, n)
        判断矩阵，满足 a_ij = 1/a_ji

    Returns
    -------
    weights : ndarray, shape (n,)
    cr : float  一致性比率
    is_consistent : bool  CR < 0.1 则一致
    """
    n = matrix.shape[0]
    # 列归一化
    col_sums = matrix.sum(axis=0)
    normed = matrix / col_sums
    # 行均值 = 权重
    w = normed.mean(axis=1)

    # 最大特征值
    aw = matrix @ w
    lambda_max = np.mean(aw / w)

    # 一致性检验
    if n <= 2:
        return w, 0.0, True

    ci = (lambda_max - n) / (n - 1)
    ri = _RI.get(n, 1.49)
    cr = ci / ri if ri > 0 else 0.0

    return w, float(cr), cr < 0.1


def combined_weights(
    w_ahp: np.ndarray,
    w_critic: np.ndarray,
    alpha: float = 0.5,
) -> np.ndarray:
    """组合权重 W = α * W_AHP + (1-α) * W_CRITIC"""
    return alpha * w_ahp + (1 - alpha) * w_critic
