"""
Sayfos Protocol — REST API server.

Provides development endpoints for the community SDK reference pipeline.
Production gateways should provide durable storage, policy management,
authentication, authorization, and operational controls.

Run:
    pip install sayfos-sdk[api]
    sayfos-server

Or:
    uvicorn sayfos.api:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from typing import Any, Optional

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError(
        "Sayfos API server requires: pip install sayfos-sdk[api]"
    )

from sayfos.core.models import ActionDeclaration, IntentVerificationRequest
from sayfos.core.enums import Verdict
from sayfos.verification.preflight import PlanDeclaration, PreflightStrategy
from sayfos.runtime import SayfosRuntime

# ── App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Sayfos Protocol API",
    description="Agent Runtime Control Protocol",
    version="0.1.0",
)

runtime = SayfosRuntime()


# ── Request / Response Models ────────────────────────────────────────


class ActionRequest(BaseModel):
    action_type: str = ""
    target: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    actor_id: str = ""
    actor_type: str = ""
    root_authorization_ref: Optional[str] = None
    task_lineage_ref: Optional[str] = None
    input_source_ref: Optional[str] = None
    tool_reason_ref: Optional[str] = None
    risk_level: int = 0


class VerifyRequest(BaseModel):
    action: ActionRequest
    budget_id: Optional[str] = None
    chain_id: Optional[str] = None
    touch_events: int = 5
    screen_on: bool = True
    device_held: bool = True
    remote_control_detected: bool = False


class VerifyResponse(BaseModel):
    verdict: str
    reason_code: str
    reason_detail: str
    scores: dict[str, float]
    constraints: dict[str, Any]
    budget_deduction: Optional[dict[str, float]]


class BudgetCreateRequest(BaseModel):
    owner_id: str
    quotas: dict[str, float]
    parent_id: Optional[str] = None


class PlanPreflightRequest(BaseModel):
    steps: list[ActionRequest]
    budget_id: str
    owner_id: str = ""
    plan_name: str = ""
    strategy: str = "sequential"


# ── Endpoints ────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok", "protocol": "Sayfos"}


@app.post("/verify", response_model=VerifyResponse)
def verify_action(req: VerifyRequest):
    """Run a single action through the Sayfos pipeline."""
    decl = ActionDeclaration(**req.action.model_dump(exclude_none=True))
    request = IntentVerificationRequest(
        action=decl,
        touch_events=req.touch_events,
        screen_on=req.screen_on,
        device_held=req.device_held,
        remote_control_detected=req.remote_control_detected,
    )
    token = runtime.adjudicate(request, budget_id=req.budget_id, chain_id=req.chain_id)
    return VerifyResponse(
        verdict=token.verdict.value,
        reason_code=token.reason_code,
        reason_detail=token.reason_detail,
        scores={
            "embodied": token.embodied_consistency_score,
            "budget": token.budget_adequacy_score,
            "source_chain": token.source_chain_integrity_score,
        },
        constraints=token.constraints,
        budget_deduction=token.budget_deduction,
    )


@app.post("/budget")
def create_budget(req: BudgetCreateRequest):
    """Create a new proxy-authority budget."""
    b = runtime.create_budget(
        owner_id=req.owner_id,
        quotas=req.quotas,
        parent_id=req.parent_id,
    )
    return {"budget_id": b.budget_id, "owner": b.owner_id, "quotas": b.quotas}


@app.get("/budget/{budget_id}")
def get_budget(budget_id: str):
    """Get budget state."""
    b = runtime.get_budget(budget_id)
    if not b:
        raise HTTPException(404, "budget not found")
    return {
        "budget_id": b.budget_id,
        "owner": b.owner_id,
        "status": b.status.value,
        "quotas": b.quotas,
        "consumed": b.consumed,
        "remaining": b.remaining,
    }


@app.post("/budget/{budget_id}/consume")
def consume_budget(budget_id: str, deductions: dict[str, float]):
    """Consume budget."""
    b = runtime.budgets.consume(budget_id, deductions)
    if not b:
        raise HTTPException(404, "budget not found")
    return {"remaining": b.remaining, "status": b.status.value}


@app.post("/budget/{budget_id}/revoke")
def revoke_budget(budget_id: str, source: str = "api", propagate: bool = True):
    """Revoke budget with optional propagation."""
    affected = runtime.revoke_budget(budget_id, source, propagate)
    return {
        "affected_count": len(affected),
        "budgets": [
            {"id": b.budget_id, "owner": b.owner_id, "status": b.status.value}
            for b in affected
        ],
    }


@app.post("/plan/preflight")
def plan_preflight(req: PlanPreflightRequest):
    """Check a multi-step plan against budget boundaries."""
    steps = tuple(
        ActionDeclaration(**s.model_dump(exclude_none=True))
        for s in req.steps
    )
    plan = PlanDeclaration(
        owner_id=req.owner_id,
        plan_name=req.plan_name,
        steps=steps,
    )
    strategy = PreflightStrategy(req.strategy)
    result = runtime.preflight_plan(plan, req.budget_id, strategy)
    return {
        "plan_id": result.plan_id,
        "feasible": result.feasible,
        "score": result.score,
        "reason_code": result.reason_code,
        "verdict": result.verdict.value,
        "first_overflow_step": result.first_overflow_step,
        "overflow_dimension": result.overflow_dimension,
        "overflow_detail": result.overflow_detail,
        "estimated_consumption": result.estimated_consumption,
        "budget_remaining_after": result.budget_remaining_after,
    }


@app.get("/chain/{chain_id}")
def get_chain(chain_id: str):
    """Get source chain details."""
    chain = runtime.get_chain(chain_id)
    if not chain:
        raise HTTPException(404, "chain not found")
    return {"chain_id": chain.chain_id, "length": chain.length}


@app.post("/chain/{chain_id}/verify")
def verify_chain(chain_id: str):
    """Verify source chain integrity."""
    result = runtime.verify_chain(chain_id)
    if not result:
        raise HTTPException(404, "chain not found")
    return {
        "chain_id": result.chain_id,
        "length": result.chain_length,
        "valid": result.valid,
        "score": result.score,
        "chain_hash": result.chain_hash,
        "breaks": [
            {"position": b.position, "tag": b.tag.value, "detail": b.detail}
            for b in result.breaks
        ],
    }


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise ImportError(
            "sayfos-server requires: pip install sayfos-sdk[api]"
        ) from exc
    uvicorn.run("sayfos.api:app", host="127.0.0.1", port=8080)
