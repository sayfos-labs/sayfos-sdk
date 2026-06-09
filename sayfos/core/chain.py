"""
Sayfos Protocol — Source chain: immutable, verifiable action provenance.

Each chain entry links an automated action to provenance references and to the
previous entry hash. Inserting, deleting, reordering, or modifying entries will
break downstream hashes and can be detected by verify().
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sayfos.core.enums import SourceChainBreakTag

_SEP = "|"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(*parts: str) -> str:
    return hashlib.sha256(_SEP.join(parts).encode()).hexdigest()


# ── Chain Entry ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ChainEntry:
    """
    A single link in the source chain — immutable once appended.

    Carries the action identity, its hash link to the previous entry,
    and all provenance references required by source-chain integrity.
    """

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=_now)
    action_ref: str = ""
    action_type: str = ""
    actor_id: str = ""

    # Hash links for chain integrity
    entry_hash: str = ""
    previous_entry_hash: Optional[str] = None
    content_hash: str = ""

    # source-chain integrity provenance references (source-chain fields)
    authorization_ref: Optional[str] = None
    human_anchor_ref: Optional[str] = None
    task_lineage_ref: Optional[str] = None
    input_source_ref: Optional[str] = None
    tool_reason_ref: Optional[str] = None
    adjudication_ref: Optional[str] = None
    budget_state_ref: Optional[str] = None

    # Chain position
    chain_position: int = 0

    # Break tags detected during prior verification
    break_tags: tuple[SourceChainBreakTag, ...] = ()

    # Metadata bag (extensible, typed at serialization boundary)
    metadata: dict[str, Any] = field(default_factory=dict)

    def compute_entry_hash(self) -> str:
        """Compute this entry's hash, incorporating the previous entry's hash."""
        payload = _SEP.join(
            str(v)
            for v in (
                self.action_ref,
                self.action_type,
                self.actor_id,
                self.authorization_ref or "",
                self.task_lineage_ref or "",
                self.input_source_ref or "",
                self.tool_reason_ref or "",
                self.adjudication_ref or "",
                self.previous_entry_hash or "",
                str(self.chain_position),
            )
        )
        return hashlib.sha256(payload.encode()).hexdigest()


# ── Chain Verification Result ────────────────────────────────────────


@dataclass(frozen=True)
class ChainVerification:
    """Output of SourceChain.verify()."""

    chain_id: str = ""
    chain_length: int = 0
    valid: bool = True
    score: float = 1.0

    breaks: tuple[ChainBreak, ...] = ()
    chain_hash: str = ""


@dataclass(frozen=True)
class ChainBreak:
    """A detected break in the chain."""

    position: int
    tag: SourceChainBreakTag
    detail: str = ""
    expected_hash: str = ""
    actual_hash: str = ""


# ── Source Chain ─────────────────────────────────────────────────────


class SourceChain:
    """
    Ordered, append-only, verifiable chain of action provenance.

    Usage::

        chain = SourceChain()
        chain = chain.append(ChainEntry.from_action(decl_1))
        chain = chain.append(ChainEntry.from_action(decl_2))

        result = chain.verify()
        assert result.valid
        print(result.chain_hash)  # single digest for the whole chain
    """

    def __init__(self, entries: Sequence[ChainEntry] = ()):
        self._entries: tuple[ChainEntry, ...] = tuple(entries)
        self._chain_id: str = str(uuid.uuid4())
        self._chain_hash: Optional[str] = None

    @property
    def entries(self) -> tuple[ChainEntry, ...]:
        return self._entries

    @property
    def chain_id(self) -> str:
        return self._chain_id

    @property
    def chain_hash(self) -> str:
        if self._chain_hash is None:
            self._chain_hash = self._compute_chain_hash()
        return self._chain_hash

    @property
    def length(self) -> int:
        return len(self._entries)

    @property
    def last_entry(self) -> Optional[ChainEntry]:
        return self._entries[-1] if self._entries else None

    def append(self, entry: ChainEntry) -> "SourceChain":
        """Create a new SourceChain with entry appended (immutable)."""
        previous_hash = self.last_entry.entry_hash if self._entries else None
        pos = len(self._entries)
        final_entry = ChainEntry(
            **{
                **entry.__dict__,
                "previous_entry_hash": entry.previous_entry_hash or previous_hash,
                "chain_position": pos,
            }
        )
        # Recompute hash with correct previous hash and position
        final_hash = final_entry.compute_entry_hash()
        final_entry = ChainEntry(
            **{**final_entry.__dict__, "entry_hash": final_hash}
        )
        new_entries = self._entries + (final_entry,)
        chain = SourceChain(new_entries)
        chain._chain_id = self._chain_id
        return chain

    def verify(self) -> ChainVerification:
        """
        Verify chain integrity:

        1. Each entry's hash matches its content (no tampering).
        2. Each entry's previous_entry_hash matches the previous
           entry's computed hash (no insertion, deletion, or reordering).
        3. Chain positions are sequential.

        Returns ChainVerification with break details.
        """
        breaks: list[ChainBreak] = []

        for i, entry in enumerate(self._entries):
            # Position check
            if entry.chain_position != i:
                breaks.append(
                    ChainBreak(
                        position=i,
                        tag=SourceChainBreakTag.CHAIN_HASH_MISMATCH,
                        detail=f"expected position {i}, got {entry.chain_position}",
                    )
                )

            # Content integrity
            expected = entry.compute_entry_hash()
            if expected != entry.entry_hash:
                breaks.append(
                    ChainBreak(
                        position=i,
                        tag=SourceChainBreakTag.CHAIN_HASH_MISMATCH,
                        detail="content hash mismatch (tampered?)",
                        expected_hash=expected,
                        actual_hash=entry.entry_hash,
                    )
                )

            # Chain continuity (skip first entry)
            if i > 0:
                prev = self._entries[i - 1]
                if entry.previous_entry_hash != prev.entry_hash:
                    breaks.append(
                        ChainBreak(
                            position=i,
                            tag=SourceChainBreakTag.CHAIN_HASH_MISMATCH,
                            detail=f"previous hash mismatch at position {i}",
                            expected_hash=prev.entry_hash,
                            actual_hash=entry.previous_entry_hash or "",
                        )
                    )

        valid = len(breaks) == 0 and len(self._entries) > 0
        score = max(0.0, 1.0 - len(breaks) * 0.25)

        return ChainVerification(
            chain_id=self._chain_id,
            chain_length=len(self._entries),
            valid=valid,
            score=score,
            breaks=tuple(breaks),
            chain_hash=self.chain_hash,
        )

    def _compute_chain_hash(self) -> str:
        """Merkle-like: hash of all entry hashes concatenated."""
        if not self._entries:
            return hashlib.sha256(b"").hexdigest()
        payload = _SEP.join(e.entry_hash for e in self._entries)
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> dict:
        """Serialize chain for audit storage or cross-system transfer."""
        return {
            "chain_id": self._chain_id,
            "chain_hash": self.chain_hash,
            "length": self.length,
            "entries": [
                {
                    "entry_id": e.entry_id,
                    "timestamp": e.timestamp.isoformat(),
                    "action_ref": e.action_ref,
                    "action_type": e.action_type,
                    "actor_id": e.actor_id,
                    "entry_hash": e.entry_hash,
                    "previous_entry_hash": e.previous_entry_hash,
                    "content_hash": e.content_hash,
                    "authorization_ref": e.authorization_ref,
                    "human_anchor_ref": e.human_anchor_ref,
                    "task_lineage_ref": e.task_lineage_ref,
                    "input_source_ref": e.input_source_ref,
                    "tool_reason_ref": e.tool_reason_ref,
                    "adjudication_ref": e.adjudication_ref,
                    "budget_state_ref": e.budget_state_ref,
                    "chain_position": e.chain_position,
                    "break_tags": [t.value for t in e.break_tags],
                    "metadata": e.metadata,
                }
                for e in self._entries
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SourceChain":
        """Deserialize chain from dictionary."""
        from datetime import datetime as dt

        entries: list[ChainEntry] = []
        for e in data.get("entries", []):
            entries.append(
                ChainEntry(
                    entry_id=e.get("entry_id", ""),
                    timestamp=dt.fromisoformat(e["timestamp"])
                    if e.get("timestamp")
                    else _now(),
                    action_ref=e.get("action_ref", ""),
                    action_type=e.get("action_type", ""),
                    actor_id=e.get("actor_id", ""),
                    entry_hash=e.get("entry_hash", ""),
                    previous_entry_hash=e.get("previous_entry_hash"),
                    content_hash=e.get("content_hash", ""),
                    authorization_ref=e.get("authorization_ref"),
                    human_anchor_ref=e.get("human_anchor_ref"),
                    task_lineage_ref=e.get("task_lineage_ref"),
                    input_source_ref=e.get("input_source_ref"),
                    tool_reason_ref=e.get("tool_reason_ref"),
                    adjudication_ref=e.get("adjudication_ref"),
                    budget_state_ref=e.get("budget_state_ref"),
                    chain_position=e.get("chain_position", 0),
                    break_tags=tuple(
                        SourceChainBreakTag(t)
                        for t in e.get("break_tags", [])
                        if isinstance(t, str)
                    ),
                    metadata=e.get("metadata", {}),
                )
            )
        return cls(entries)
