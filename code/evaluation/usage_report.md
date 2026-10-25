# Usage Report

## Summary of Full-Dataset Execution

- **Total Requests Processed**: 518
- **Total API Calls**: 142
- **Total Input Tokens**: 42,133
- **Total Output Tokens**: 13,017
- **Total Tokens**: 55,150
- **Average Tokens Per Request**: 106.47
- **Estimated Total Cost**: $0.0315
- **Estimated Cost Per Request**: $0.000061

## Model Breakdown

| Model Provider / Name | Calls | Prompt Tokens | Output Tokens | Total Tokens | Estimated Cost (USD) |
|---|---|---|---|---|---|
| Groq / `openai/gpt-oss-120b` | 142 | 42,133 | 13,017 | 55,150 | $0.0315 |

## Architecture & Optimization Notes

- **Hybrid Architecture**: Deterministic identity resolution and rule evaluation combined with LLM for intent classification and complex ambiguous evidence.
- **Local Embedding Engine**: Sentence-Transformers `all-MiniLM-L6-v2` runs locally on CPU with zero API costs for FAISS similarity indexing.
- **SQLite Evidence Store**: Structured queries against pre-indexed SQLite tables reduce the need for raw LLM document dumping.
