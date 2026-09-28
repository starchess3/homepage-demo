# 君正股份财报问答微调项目

目标：收集君正股份（北京君正，300223）财报 → 生成“投资者提问→董秘作答”问答 →
用 LoRA 微调小模型 → 做四格对照与 RAG 对比。

## 交付物

- **数据生成脚本与抽检记录**
  - `extract_reports.py`：从 PDF 抽取全文（按页、带页码）→ `corpus/`。
  - `generate_qa.py`：调用大模型从原文生成问答（带报告+页码出处）→ `data/qa_dataset_raw.jsonl`。
  - `data/qa_dataset_raw.jsonl`：DeepSeek 批量生成的 540 条（未抽检）。
  - `data/qa_dataset_clean.jsonl`：抽检后干净数据（485 条，可直接用于训练）。
  - `spot_check.py`：事实回源核对，自动删除疑似编造条目。
  - `data/spot_check.csv`、`data/spot_check.md`：抽检记录。
  - `data/qa_dataset_seed.jsonl` / `qa_dataset_clean_seed.jsonl`：最早手工落地的 29 条种子备份。
- **训练笔记本**
  - `colab/train_lora.ipynb`：Colab + 免费 T4 的 QLoRA + LoRA SFT 训练（默认 Qwen2.5-1.5B-Instruct）。
- **对照表与一页结论**
  - `eval/eval_questions.jsonl`：四格对照题集（训练过/没训练过 × 原问法/换问法，共 16 条）。
  - `eval/eval_compare.py`：微调/基座/知识库RAG 三方案自动评测与打分。
  - `eval/comparison_table.md`：对照表（方法 + 模板）。
  - `eval/conclusion.md`：一页结论。

## 复现流程

1. `python3 extract_reports.py ~/Desktop/人工智能与数据分析课程`
2. （生成问答）`OPENAI_API_KEY=sk-xxx python3 generate_qa.py`，或直接使用已生成并抽检的 `data/qa_dataset_clean.jsonl`。
   本项目已用 DeepSeek 跑通：`OPENAI_API_KEY=$DEEPSEEK_API_KEY OPENAI_BASE_URL=https://api.deepseek.com MODEL=deepseek-chat python3 generate_qa.py`。
3. `python3 spot_check.py` 抽检并产出干净数据。
4. 在 Colab 上传 `colab/train_lora.ipynb` 与 `data/qa_dataset_clean.jsonl`，选 T4 GPU，依次运行训练。
5. 训练后跑 `%run eval/eval_compare.py --base Qwen/Qwen2.5-1.5B-Instruct --adapter /content/junzheng_lora/adapter`，
   得到四格对照与 RAG 对照的真实数字，回填到 `comparison_table.md` / `conclusion.md`。

## 口径假设

- 任务里的“A 的知识库 + 同一个小模型”按 **财报原文知识库（RAG）+ 同一个基座模型** 理解。
- “Qwen3.5-2B”目前无此官方模型，默认用 Qwen2.5-1.5B-Instruct；可替换为 Qwen3-1.7B 等。
- 免费 T4 不支持 bf16，训练/推理统一用 fp16 + 4bit 量化。
