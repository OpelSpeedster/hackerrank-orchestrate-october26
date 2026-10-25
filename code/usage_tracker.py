"""Usage tracker for LLM API calls and token counts."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ModelCallRecord:
    case_id: str
    purpose: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float = 0.0


class UsageTracker:
    def __init__(self, pricing: Optional[Dict[str, Dict[str, float]]] = None):
        # Default pricing estimates per million tokens (Groq Llama 70B pricing)
        self.pricing = pricing or {
            "llama-3.3-70b-versatile": {"input": 0.59 / 1_000_000, "output": 0.79 / 1_000_000},
            "llama3-70b-8192": {"input": 0.59 / 1_000_000, "output": 0.79 / 1_000_000},
            "default": {"input": 0.50 / 1_000_000, "output": 0.80 / 1_000_000},
        }
        self.records: List[ModelCallRecord] = []

    def record_call(
        self,
        case_id: str,
        purpose: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        total = prompt_tokens + completion_tokens
        rates = self.pricing.get(model, self.pricing["default"])
        cost = (prompt_tokens * rates["input"]) + (completion_tokens * rates["output"])
        
        self.records.append(
            ModelCallRecord(
                case_id=case_id,
                purpose=purpose,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total,
                cost_usd=cost,
            )
        )

    def get_summary(self) -> Dict:
        total_calls = len(self.records)
        total_prompt_tokens = sum(r.prompt_tokens for r in self.records)
        total_completion_tokens = sum(r.completion_tokens for r in self.records)
        total_tokens = sum(r.total_tokens for r in self.records)
        total_cost = sum(r.cost_usd for r in self.records)
        
        by_model: Dict[str, Dict] = {}
        for r in self.records:
            if r.model not in by_model:
                by_model[r.model] = {
                    "calls": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                }
            by_model[r.model]["calls"] += 1
            by_model[r.model]["prompt_tokens"] += r.prompt_tokens
            by_model[r.model]["completion_tokens"] += r.completion_tokens
            by_model[r.model]["total_tokens"] += r.total_tokens
            by_model[r.model]["cost_usd"] += r.cost_usd

        return {
            "total_calls": total_calls,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "by_model": by_model,
        }

    def write_usage_report(self, report_path: Path, num_requests: int = 518) -> None:
        summary = self.get_summary()
        avg_tokens = summary["total_tokens"] / max(num_requests, 1)
        avg_cost = summary["total_cost_usd"] / max(num_requests, 1)

        lines = [
            "# Usage Report",
            "",
            "## Summary of Full-Dataset Execution",
            "",
            f"- **Total Requests Processed**: {num_requests}",
            f"- **Total API Calls**: {summary['total_calls']}",
            f"- **Total Input Tokens**: {summary['total_prompt_tokens']:,}",
            f"- **Total Output Tokens**: {summary['total_completion_tokens']:,}",
            f"- **Total Tokens**: {summary['total_tokens']:,}",
            f"- **Average Tokens Per Request**: {avg_tokens:.2f}",
            f"- **Estimated Total Cost**: ${summary['total_cost_usd']:.4f}",
            f"- **Estimated Cost Per Request**: ${avg_cost:.6f}",
            "",
            "## Model Breakdown",
            "",
            "| Model Provider / Name | Calls | Prompt Tokens | Output Tokens | Total Tokens | Estimated Cost (USD) |",
            "|---|---|---|---|---|---|",
        ]

        if summary["by_model"]:
            for model_name, stats in summary["by_model"].items():
                lines.append(
                    f"| Groq / `{model_name}` | {stats['calls']} | {stats['prompt_tokens']:,} | "
                    f"{stats['completion_tokens']:,} | {stats['total_tokens']:,} | ${stats['cost_usd']:.4f} |"
                )
        else:
            lines.append("| Groq / `llama-3.3-70b-versatile` (hybrid fallback) | 0 | 0 | 0 | 0 | $0.0000 |")

        lines.extend([
            "",
            "## Architecture & Optimization Notes",
            "",
            "- **Hybrid Architecture**: Deterministic identity resolution and rule evaluation combined with LLM for intent classification and complex ambiguous evidence.",
            "- **Local Embedding Engine**: Sentence-Transformers `all-MiniLM-L6-v2` runs locally on CPU with zero API costs for FAISS similarity indexing.",
            "- **SQLite Evidence Store**: Structured queries against pre-indexed SQLite tables reduce the need for raw LLM document dumping.",
        ])

        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


usage_tracker = UsageTracker()
