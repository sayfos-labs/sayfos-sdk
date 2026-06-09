"""
Sayfos Protocol — Agent Runtime Control Protocol.

Five standard semantic objects defined as frozen, type-safe dataclasses.
Implementations MUST preserve immutability and hashability to ensure
audit chain integrity.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class Verdict(str, Enum):
    """Adjudication verdict for a single action event."""

    ALLOW = "allow"
    ALLOW_WITH_CONSTRAINTS = "allow_with_constraints"
    PARAM_CROP = "param_crop"
    DELAY = "delay"
    REVERIFY = "reverify"
    HUMAN_REVIEW = "human_review"
    SESSION_ISOLATE = "session_isolate"
    TASK_CHAIN_FREEZE = "task_chain_freeze"
    TOKEN_REVOKE = "token_revoke"
    BLOCK = "block"
    ROLLBACK = "rollback"


class SourceChainBreakTag(str, Enum):
    """Tags indicating a specific source-chain integrity failure."""

    MISSING_AUTHORIZATION = "missing_authorization"
    MISSING_TASK_LINEAGE = "missing_task_lineage"
    INPUT_POLLUTION = "input_pollution"
    TOOL_REASON_MISSING = "tool_reason_missing"
    ADJUDICATION_SOURCE_MISSING = "adjudication_source_missing"
    CHAIN_HASH_MISMATCH = "chain_hash_mismatch"
    SIGNATURE_INVALID = "signature_invalid"
    REVOCATION_ACTIVE = "revocation_active"
    NODE_UNTRUSTED = "node_untrusted"


class BudgetStatus(str, Enum):
    """Proxy-authority budget lifecycle states."""

    ACTIVE = "active"
    PARTIALLY_CONSUMED = "partially_consumed"
    CONSTRAINED = "constrained"
    FROZEN = "frozen"
    REVOKED = "revoked"
    EXPIRED = "expired"
    AWAITING_REVERIFY = "awaiting_reverify"
    RECOVERED = "recovered"
