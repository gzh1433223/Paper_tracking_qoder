# Ontology 文献追踪自动化

自动追踪 ontology 相关领域的最新论文，每天早上6点自动从 arXiv 和 PubMed 获取昨天发表的新文章。

## 功能特点

- **自动化运行**: 使用 GitHub Actions 每天北京时间 6:00 自动运行，无需本地电脑开机
- **多数据源**: 同时从 arXiv 和 PubMed 获取文献
- **仅昨天论文**: 只抓取昨天发表的论文，避免信息过载
- **可配置关键词**: 通过 `config.yaml` 自定义搜索关键词
- **双格式输出**: 生成 JSON 和 Markdown 两种格式的报告

## 项目结构

```
Paper_tracking_qoder/
├── .github/
│   └── workflows/
│       └── daily_fetch.yml    # GitHub Actions 配置
├── config.yaml                # 搜索配置
├── fetch_papers.py            # 主脚本
├── requirements.txt           # Python 依赖
└── results/                   # 输出目录（自动创建）
    ├── papers_2026-09-13.json
    └── papers_2026-09-13.md
```

## 快速开始

### 1.  Fork 或创建仓库

将此项目上传到 GitHub 仓库。

### 2. 配置搜索关键词

编辑 `config.yaml`，修改搜索关键词：

```yaml
keywords:
  - ontology
  - ontologies
  - "ontology learning"
  - "knowledge graph"
```

### 3. 启用 GitHub Actions

1. 进入仓库的 **Settings** → **Actions** → **General**
2. 确保 **Allow all actions** 已启用
3. 进入 **Actions** 标签页，启用 workflow

### 4. 手动测试

在 **Actions** 页面，选择 **Daily Ontology Paper Tracker**，点击 **Run workflow** 手动触发一次。

### 5. 查看结果

运行完成后，结果会自动提交到 `results/` 目录：
- `papers_YYYY-MM-DD.json` - 结构化数据
- `papers_YYYY-MM-DD.md` - 可读报告

## 自定义运行时间

编辑 `.github/workflows/daily_fetch.yml`，修改 cron 表达式：

```yaml
schedule:
  - cron: '0 22 * * *'  # UTC 22:00 = 北京时间次日 6:00（当前配置）
```

常用时间参考：
- `0 22 * * *` - UTC 22:00（北京时间次日 6:00）
- `0 0 * * *` - UTC 0:00（北京时间 8:00）
- `0 12 * * *` - UTC 12:00（北京时间 20:00）

## 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行脚本
python fetch_papers.py
```

## 注意事项

- arXiv 的论文通常在工作日更新，周末可能没有新论文
- PubMed 的论文更新可能有延迟，当天论文可能次日才出现
- GitHub Actions 免费账户每月有 2000 分钟限制
