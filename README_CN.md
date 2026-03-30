# hydro-efficiency

[English](README.md) | **中文**

工业园区水资源利用效率评价——AHP+CRITIC 组合赋权 + TOPSIS 综合排名。

[![在线演示](https://img.shields.io/badge/在线演示-hydro--efficiency.tianlizeng.cloud-blue?style=for-the-badge)](https://hydro-efficiency.tianlizeng.cloud)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-yellow?style=for-the-badge)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

---

### 无需安装，立即体验

**https://hydro-efficiency.tianlizeng.cloud**

---

![hydro-efficiency demo](docs/screenshots/demo.png)

---

## 功能一览

| 功能 | 说明 |
|------|------|
| **AHP + CRITIC 赋权** | 可调 α 参数融合主客观权重 |
| **三层评价体系** | 园区 → 管网 → 企业级评价 |
| **TOPSIS 排名** | 企业评分与等级排名 |
| **内置样例数据** | 无需上传即可直接使用 |
| **Excel 模板导出** | 下载空白模板填入自有数据 |

## 安装

```bash
git clone https://github.com/zengtianli/hydro-efficiency.git
cd hydro-efficiency
pip install -r requirements.txt
```

## 快速开始

```bash
streamlit run app.py
```

## 自托管

```bash
git clone https://github.com/zengtianli/hydro-efficiency.git
cd hydro-efficiency
pip install -r requirements.txt
streamlit run app.py
```

或直接使用托管版本：**https://hydro-efficiency.tianlizeng.cloud**

## 环境要求

- Python 3.9+
- Streamlit 1.36+

## License

MIT
