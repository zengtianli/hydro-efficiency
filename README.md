# 💧 Hydro Efficiency — Water Efficiency Assessment

[![GitHub stars](https://img.shields.io/github/stars/zengtianli/hydro-efficiency)](https://github.com/zengtianli/hydro-efficiency)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.36+-FF4B4B.svg)](https://streamlit.io)

Water efficiency assessment for industrial parks using AHP + CRITIC + TOPSIS methodology across three circulation levels.

![screenshot](docs/screenshot.png)

## Features

- **AHP + CRITIC combined weighting** — adjustable α parameter for subjective/objective weight blending
- **Three-level evaluation** — macro (park), meso (pipeline), and micro (enterprise) circulation
- **TOPSIS ranking** — enterprise-level scoring and classification
- **Built-in sample data** — pre-loaded example dataset, no file upload required
- **Excel template download** — export blank template for custom data input

## Quick Start

```bash
git clone https://github.com/zengtianli/hydro-efficiency.git
cd hydro-efficiency
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (VPS)

```bash
git clone https://github.com/zengtianli/hydro-efficiency.git
cd hydro-efficiency
pip install -r requirements.txt
nohup streamlit run app.py --server.port 8503 --server.headless true &
```

## Hydro Toolkit Plugin

This project is a plugin for [Hydro Toolkit](https://github.com/zengtianli/hydro-toolkit) and can also run standalone. Install it in the Toolkit by pasting this repo URL in the Plugin Manager.

## License

MIT
