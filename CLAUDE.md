# hydro-efficiency — 工业园区水效评估（AHP+CRITIC+TOPSIS）

## Quick Reference

| 项目 | 路径/值 |
|------|---------|
| 入口 | `app.py` (Streamlit) |
| 核心逻辑 | `src/efficiency/` |
| 公共模块 | `src/common/` |
| Streamlit 配置 | `.streamlit/config.toml` |
| 线上地址 | https://hydro-efficiency.tianlizeng.cloud |
| 本地端口 | 8501（Streamlit 默认） |

## 常用命令

```bash
cd /Users/tianli/Dev/hydro-efficiency

# 本地运行
streamlit run app.py

# 指定端口
streamlit run app.py --server.port 8502

# 安装依赖
pip install -r requirements.txt
```

## 项目结构

```
app.py              # Streamlit 入口，页面路由与布局
src/
  efficiency/       # AHP/CRITIC 权重计算、TOPSIS 排名核心算法
  common/           # 数据加载、Excel 模板导出等公共工具
.streamlit/
  config.toml       # 主题、端口等 Streamlit 配置
```

## 核心功能

| 功能 | 说明 |
|------|------|
| AHP + CRITIC 组合赋权 | α 参数调节主观/客观权重比例 |
| 3 级评估体系 | 园区 → 管网 → 企业逐级评估 |
| TOPSIS 排名 | 企业综合得分与等级分类 |
| 样本数据内置 | 无需上传文件即可体验 |
| Excel 模板导出 | 下载空白模板填入自有数据 |

## 开发注意

- 无外部 API，无需读取 `~/.personal_env`
- 算法参数（α 权重比）在 Streamlit sidebar 交互调节，无硬编码配置文件
- 修改算法逻辑只需改 `src/efficiency/`，不用动 `app.py` 路由层
- 部署到 VPS 参考 `~/Dev/vps-scripts/CLAUDE.md`，服务注册为 systemd unit
