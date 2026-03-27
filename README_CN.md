# 💧 水效评估

[![GitHub stars](https://img.shields.io/github/stars/zengtianli/hydro-efficiency)](https://github.com/zengtianli/hydro-efficiency)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.36+-FF4B4B.svg)](https://streamlit.io)

工业集聚区水效评估系统，采用 AHP + CRITIC + TOPSIS 方法，覆盖三循环层面。

![screenshot](docs/screenshot.png)

## 功能特点

- **AHP + CRITIC 组合赋权** — 可调 α 参数控制主客观权重比例
- **三循环层面评估** — 大循环（园区）、小循环（管网）、点循环（企业）
- **TOPSIS 排名** — 企业级评分与分类
- **内置示例数据** — 预载示例数据集，无需上传文件
- **模板下载** — 导出空白模板用于自定义数据输入

## 快速开始

```bash
git clone https://github.com/zengtianli/hydro-efficiency.git
cd hydro-efficiency
pip install -r requirements.txt
streamlit run app.py
```

## 部署（VPS）

```bash
git clone https://github.com/zengtianli/hydro-efficiency.git
cd hydro-efficiency
pip install -r requirements.txt
nohup streamlit run app.py --server.port 8503 --server.headless true &
```

## Hydro Toolkit 插件

本项目是 [Hydro Toolkit](https://github.com/zengtianli/hydro-toolkit) 的插件，也可独立运行。在 Toolkit 的插件管理页面粘贴本仓库 URL 即可安装。

## 许可证

MIT
