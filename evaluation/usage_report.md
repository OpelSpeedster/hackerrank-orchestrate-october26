# Usage Report

## Summary of Full-Dataset Execution

- **Total Requests Processed**: 518
- **Total API Calls**: 142
- **Total Input Tokens**: 40,597
- **Total Output Tokens**: 13,085
- **Total Tokens**: 53,682
- **Average Tokens Per Request**: 103.63
- **Estimated Total Cost**: $0.0308
- **Estimated Cost Per Request**: $0.000059

## Model Breakdown

| Model Provider / Name | Calls | Prompt Tokens | Output Tokens | Total Tokens | Estimated Cost (USD) |
|---|---|---|---|---|---|
| Groq / `openai/gpt-oss-120b` | 142 | 40,597 | 13,085 | 53,682 | $0.0308 |

## Architecture & Optimization Notes

- **Hybrid Architecture**: Deterministic identity resolution and rule evaluation combined with LLM for intent classification and complex ambiguous evidence.
- **Local Embedding Engine**: Sentence-Transformers `all-MiniLM-L6-v2` runs locally on CPU with zero API costs for FAISS similarity indexing.
- **SQLite Evidence Store**: Structured queries against pre-indexed SQLite tables reduce the need for raw LLM document dumping.
