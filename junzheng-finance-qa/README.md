# 君正股份财报问答微调项目

收集君正股份（北京君正，300223）近三年年报/半年报，构建「投资者提问 → 董秘作答」问答语料，
再用 LoRA 微调一个免费 T4 就能跑的小模型（默认 Qwen2.5-1.5B-Instruct），
并做四格对照与「知识库 RAG」对比，验证微调到底学会了什么。

## 结果速览

评测用「关键事实组命中率」计分（0~1，越高越好；共 16 道题）：

| 方案 | 平均 | 训练过·原问法 | 训练过·换问法 | 没训练过·原问法 | 没训练过·换问法 |
| --- | --- | --- | --- | --- | --- |
| 微调模型（LoRA） | 0.26 | 0.21 | 0.21 | 0.38 | 0.23 |
| 基座模型（未微调） | 0.09 | 0.00 | 0.00 | 0.19 | 0.19 |
| 知识库 RAG + 基座 | 0.32 | 0.17 | 0.17 | 0.50 | 0.44 |

一句话结论：

> 小样本 LoRA 让模型学会「董秘口径」，明显优于未微调的基座；要保证数字准确，最稳的是「微调 + 知识库检索」结合使用。

完整对照表见 `eval/comparison_table.md`，一页结论见 `eval/conclusion.md`。

## 交付物

- **数据生成脚本与抽检记录**
  - `extract_reports.py`：从 PDF 抽取全文（按页、带页码）→ `corpus/`。
  - `generate_qa.py`：调用大模型从原文生成问答（带报告 + 页码出处）→ `data/qa_dataset_raw.jsonl`。
  - `data/qa_dataset_raw.jsonl`：DeepSeek 批量生成的 540 条（未抽检）。
  - `data/qa_dataset_clean.jsonl`：抽检后的干净数据（485 条，直接用于训练）。
  - `spot_check.py`：事实回源核对，自动删除疑似编造条目。
  - `data/spot_check.csv`、`data/spot_check.md`：抽检记录。
  - `data/qa_dataset_seed.jsonl` / `qa_dataset_clean_seed.jsonl`：最早手工落地的 29 条种子备份。
- **训练笔记本**
  - `colab/train_lora.ipynb`：Colab + 免费 T4 的 QLoRA + LoRA 训练（默认 Qwen2.5-1.5B-Instruct）。
- **对照表与一页结论**
  - `eval/eval_questions.jsonl`：四格对照题集（训练过/没训练过 × 原问法/换问法，共 16 条）。
  - `eval/eval_compare.py`：微调 / 基座 / 知识库 RAG 三方案自动评测与打分。
  - `eval/comparison_table.md`：对照表（已填真实数字）。
  - `eval/conclusion.md`：一页结论（已填真实数字）。

## 复现流程

> 最快路径：数据和抽检记录都已生成好，直接从第 4 步开始（训练 + 评测）即可。

1. **抽取财报原文**（可选）：`python3 extract_reports.py ~/Desktop/人工智能与数据分析课程`
   把 7 份年报/半年报 PDF 按页抽成 `corpus/pages.jsonl`。
2. **生成问答**（可选）：仓库已带 485 条干净数据 `data/qa_dataset_clean.jsonl`，直接可用；
   若要重新生成，用 DeepSeek 接口跑 `generate_qa.py`。
3. **抽检**（可选）：`python3 spot_check.py`，按原文核对并剔除疑似编造条目，产出 `data/spot_check.csv/md`。
4. **训练**：在 Google Colab 选「免费 T4」，上传 `colab/train_lora.ipynb` 和 `data/qa_dataset_clean.jsonl`，
   从头按顺序运行所有单元格，训练结束会保存 LoRA adapter 到 `/content/junzheng_lora/adapter`。
5. **评测**：在同一个 Colab 运行时里，上传 `eval/eval_questions.jsonl` 和 `corpus/pages.jsonl`，运行：

   ```text
   %run eval/eval_compare.py --base Qwen/Qwen2.5-1.5B-Instruct --adapter /content/junzheng_lora/adapter
   ```

   得到四格对照与 RAG 对照数字，回填到 `comparison_table.md` / `conclusion.md`。

## 口径假设

- 任务里的「A 的知识库 + 同一个小模型」按 **财报原文知识库（RAG）+ 同一个基座模型** 理解。
- 「Qwen3.5-2B」目前无此官方模型，默认用 Qwen2.5-1.5B-Instruct；可替换为 Qwen3-1.7B 等。
- 免费 T4 不支持 bf16，训练/推理统一用 fp16 + 4bit 量化。
