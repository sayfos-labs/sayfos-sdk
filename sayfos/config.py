"""
Sayfos Protocol — Pipeline configuration.

Pluggable thresholds, decision matrix, and engine registration
that drive the SayfosPipeline's behavior at runtime.

Configuration can be loaded from a dict (JSON/YAML), environment
variables, or programmatic API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Sequence

from sayfos.core.enums import Verdict


class DecisionPolicy(str, Enum):
    """Pre-built decision matrix strategies."""
    STRICT = "strict"       # Any fail → BLOCK
    BALANCED = "balanced"   # Causal fail → BLOCK, budget fail → BLOCK, source fail → HUMAN_REVIEW
    PERMISSIVE = "permissive"  # Only causal fail → BLOCK, others → ALLOW_WITH_CONSTRAINTS


@dataclass
class VerifierThresholds:
    """Per-verifier thresholds for pass/fail scoring."""
    causal_block_threshold: float = 0.3
    budget_low_threshold: float = 0.8
    source_chain_review_threshold: float = 0.5


@dataclass
class PipelineConfig:
    """
    Complete pipeline configuration.

    Usage::

        config = PipelineConfig.from_dict({
            "policy": "balanced",
            "thresholds": {"causal_block_threshold": 0.2},
            "engines": ["causal_consistency", "budget_governance", "source_chain"],
        })
        pipeline = SayfosPipeline(config=config)
    """

    policy: DecisionPolicy = DecisionPolicy.BALANCED
    thresholds: VerifierThresholds = field(default_factory=VerifierThresholds)
    engines: tuple[str, ...] = ("causal_consistency", "budget_governance", "source_chain")
    auto_consume_budget: bool = True
    record_audit_trail: bool = True

    # Custom decision matrix overrides (verdict tuple → output verdict)
    # Key format: "causal_pass|budget_pass|source_pass"
    custom_matrix: dict[str, Verdict] = field(default_factory=dict)

    # Engine-specific overrides
    engine_configs: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "PipelineConfig":
        return cls(
            policy=DecisionPolicy(data.get("policy", "balanced")),
            thresholds=VerifierThresholds(**data.get("thresholds", {})),
            engines=tuple(data.get("engines", ["causal_consistency", "budget_governance", "source_chain"])),
            auto_consume_budget=data.get("auto_consume_budget", True),
            record_audit_trail=data.get("record_audit_trail", True),
            custom_matrix={
                k: Verdict(v) for k, v in data.get("custom_matrix", {}).items()
            },
            engine_configs=data.get("engine_configs", {}),
        )

    @classmethod
    def strict(cls) -> "PipelineConfig":
        return cls(policy=DecisionPolicy.STRICT)

    @classmethod
    def permissive(cls) -> "PipelineConfig":
        return cls(policy=DecisionPolicy.PERMISSIVE)

    @classmethod
    def production(cls) -> "PipelineConfig":
        """Recommended production defaults."""
        return cls(
            policy=DecisionPolicy.BALANCED,
            thresholds=VerifierThresholds(
                causal_block_threshold=0.2,
                budget_low_threshold=0.6,
                source_chain_review_threshold=0.3,
            ),
            auto_consume_budget=True,
            record_audit_trail=True,
        )


# ── Built-in decision matrices ───────────────────────────────────────


STRICT_MATRIX: dict[tuple[bool, bool, bool], Verdict] = {
    # causal, budget, source → verdict
    (True, True, True): Verdict.ALLOW,
    (True, True, False): Verdict.BLOCK,
    (True, False, True): Verdict.BLOCK,
    (True, False, False): Verdict.BLOCK,
    (False, True, True): Verdict.BLOCK,
    (False, True, False): Verdict.BLOCK,
    (False, False, True): Verdict.BLOCK,
    (False, False, False): Verdict.BLOCK,
}

BALANCED_MATRIX: dict[tuple[bool, bool, bool], Verdict] = {
    (True, True, True): Verdict.ALLOW,
    (True, True, False): Verdict.HUMAN_REVIEW,
    (True, False, True): Verdict.ALLOW_WITH_CONSTRAINTS,
    (True, False, False): Verdict.HUMAN_REVIEW,
    (False, True, True): Verdict.BLOCK,
    (False, True, False): Verdict.BLOCK,
    (False, False, True): Verdict.BLOCK,
    (False, False, False): Verdict.BLOCK,
}

PERMISSIVE_MATRIX: dict[tuple[bool, bool, bool], Verdict] = {
    (True, True, True): Verdict.ALLOW,
    (True, True, False): Verdict.ALLOW_WITH_CONSTRAINTS,
    (True, False, True): Verdict.ALLOW_WITH_CONSTRAINTS,
    (True, False, False): Verdict.ALLOW_WITH_CONSTRAINTS,
    (False, True, True): Verdict.BLOCK,
    (False, True, False): Verdict.BLOCK,
    (False, False, True): Verdict.BLOCK,
    (False, False, False): Verdict.BLOCK,
}

POLICY_MATRIX: dict[DecisionPolicy, dict[tuple[bool, bool, bool], Verdict]] = {
    DecisionPolicy.STRICT: STRICT_MATRIX,
    DecisionPolicy.BALANCED: BALANCED_MATRIX,
    DecisionPolicy.PERMISSIVE: PERMISSIVE_MATRIX,
}
