"""Transparent planning heuristics, optionally calibrated by comparable claims."""

from decimal import Decimal
from statistics import median

from .config import DESCRIPTORS, CreditError, credits, display


def estimate(
    config,
    ledger,
    *,
    task_type="feature",
    complexity="medium",
    size="medium",
    strategy="balanced",
    testing="targeted",
    phases=1,
    retries=0,
    uncertainty="0.25",
):
    descriptors = {
        "task_type": task_type,
        "complexity": complexity,
        "size": size,
        "strategy": strategy,
        "testing": testing,
    }
    for key, options in DESCRIPTORS.items():
        if descriptors[key] not in options:
            raise CreditError(f"Invalid {key}.")
    if (
        type(phases) is not int
        or not 1 <= phases <= 5
        or type(retries) is not int
        or not 0 <= retries <= 5
    ):
        raise CreditError("Phases must be 1..5 and retries 0..5.")
    spread = Decimal(credits(uncertainty)) / 1_000_000
    if spread > 1:
        raise CreditError("Uncertainty must be 0..1.")
    samples = [
        credits(c["usage"])
        for c in ledger.claims()
        if c["verified"] and c["descriptors"] == descriptors
    ]
    basis = "uncalibrated-heuristic"
    if len(samples) >= 3:
        base = Decimal(str(median(samples)))
        basis = "comparable-verified-history"
        base_label = "median of comparable complete-task claims; no model credit conversion"
    else:
        base = Decimal(
            {"feature": 20, "bugfix": 15, "refactor": 25, "docs": 5}[task_type] * 1_000_000
        )
        base *= Decimal({"small": "0.5", "medium": "1", "large": "2"}[complexity])
        base *= Decimal({"small": "0.8", "medium": "1", "large": "1.5"}[size])
        base *= Decimal({"economy": "0.8", "balanced": "1", "thorough": "1.4"}[strategy])
        base *= Decimal("1.4" if testing == "full" else "1")
        base_label = "hand-set planning weights, not validated Kiro billing rates"
    expected = round(base * (1 + Decimal("0.15") * (phases - 1)) * (1 + Decimal("0.20") * retries))
    return {
        "kind": "estimate",
        "basis": basis,
        "confidence": "low" if len(samples) < 5 else "moderate",
        "sample_count": len(samples),
        "expected": display(expected),
        "low": display(round(expected * (1 - spread))),
        "high": display(round(expected * (1 + spread))),
        "descriptors": descriptors,
        "assumptions": {
            "base": base_label,
            "phase_count": phases,
            "phase_increment": "15% per extra phase",
            "expected_retries": retries,
            "retry_increment": "20% per retry",
            "uncertainty": str(spread),
        },
        "recommendations": [
            "Use local search and existing repository notes before requesting broad exploration.",
            "Choose an available model capable of the task; confirm current Kiro credit rules.",
            "Keep necessary security and correctness checks; escalate testing with risk.",
        ],
    }
