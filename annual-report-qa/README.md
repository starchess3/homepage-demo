# 半导体行业年报问答（向量 + BM25 检索式）

选 13 家 A 股半导体公司，从巨潮资讯下载 2024 年年报全文，抽取正文并把表格还原成“行 | 列”，
按公司/章节/页码切块，建「向量 + BM25」混合索引，做一个提问后答案带出处的网页，并用 10 道题逐题记录召回与对错。

## 目录

```text
annual-report-qa/
├── scripts/
│   ├── download_reports.py   # 巨潮资讯下载年报 PDF
│   ├── extract_reports.py    # 抽取文字+表格，按公司/章节/页码切块
│   ├── indexer.py            # BM25 + 字符bigram特征哈希向量 + RRF 融合
│   ├── run_eval.py           # 跑 10 题评测，输出 md/html
│   └── screenshot.py         # 生成页面截图（本机运行）
├── app/
│   ├── server.py             # stdlib http.server，/query 接口
│   └── index.html            # 问答页
├── data/pdfs/                # 13 份年报 PDF + manifest.json
├── data/chunks.jsonl         # 9,272 个带元数据块
├── eval/questions.jsonl      # 10 道评测题（8 单公司 + 2 跨公司）
└── output/                   # 评测记录、结论、结果一览图、截图
```

## 复现

```bash
cd annual-report-qa
python3 scripts/download_reports.py --year 2024        # 下载 13 份年报
python3 scripts/extract_reports.py --year 2024         # 抽取 + 切块
python3 scripts/run_eval.py                            # 10 题评测
python3 app/server.py 8765                             # 启动问答页
# 浏览器打开 http://localhost:8765
```

依赖：`PyMuPDF`（`fitz`）、`numpy`（其余为标准库）。截图另需 `playwright` + chromium。

## 评测结果

10 题：**8 答对 / 2 翻车**。单公司事实题全对；跨公司全景题全翻车（详见 `output/eval_results.md`、
`output/eval_results.html`、`output/conclusion.md`）。

关键结论：检索式系统擅长“定位原文”，不擅长“跨公司聚合/比较”。

## 页面截图

本仓库的沙箱环境无法启动 Chromium（Mach port 权限被拒），所以截图请在本机执行：

```bash
pip install playwright && python3 -m playwright install chromium
python3 app/server.py 8765 &          # 先启动服务
python3 scripts/screenshot.py         # 生成 output/screenshots/{qa_page,eval_results}.png
```

也可直接浏览器打开 `output/eval_results.html` 和 `http://localhost:8765` 手动截图。
