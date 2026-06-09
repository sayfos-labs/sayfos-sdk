"""
Sayfos CLI — command-line interface for the Sayfos protocol.

Usage:
    sayfos verify --action '{"action_type":"payment",...}' --budget-id <id>
    sayfos budget create --owner agent-1 --quotas '{"amount_cny":5000}'
    sayfos budget show <id>
    sayfos budget revoke <id>
    sayfos chain create
    sayfos chain verify <id>
    sayfos plan preflight --plan '{"steps":[...]}' --budget-id <id>
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from sayfos.core.models import ActionDeclaration, IntentVerificationRequest
from sayfos.core.enums import Verdict
from sayfos.verification.preflight import PlanDeclaration
from sayfos.runtime import SayfosRuntime


class SayfosCLI:
    def __init__(self):
        self._runtime: Optional[SayfosRuntime] = None
        self.parser = self._build_parser()

    @property
    def runtime(self) -> SayfosRuntime:
        if self._runtime is None:
            self._runtime = SayfosRuntime()
        return self._runtime

    def _build_parser(self) -> argparse.ArgumentParser:
        p = argparse.ArgumentParser(
            prog="sayfos",
            description="Sayfos Protocol CLI - Agent Runtime Control Protocol",
        )
        sub = p.add_subparsers(dest="command", required=True)

        # verify
        v = sub.add_parser("verify", help="Verify a single action through the pipeline")
        v.add_argument("--action", required=True, help="Action JSON or @file")
        v.add_argument("--budget-id", help="Budget ID for auto-consumption")
        v.add_argument("--chain-id", help="Source chain ID for auto-linking")
        v.add_argument("--touch", type=int, default=5, help="Touch events")
        v.add_argument("--screen-off", action="store_true", help="Mark screen as off")
        v.add_argument("--remote", action="store_true", help="Mark remote control as detected")

        # budget
        b = sub.add_parser("budget", help="Budget management")
        b_sub = b.add_subparsers(dest="budget_cmd", required=True)

        bc = b_sub.add_parser("create", help="Create a budget")
        bc.add_argument("--owner", required=True)
        bc.add_argument("--quotas", required=True, help='JSON: {"amount_cny":5000}')
        bc.add_argument("--parent-id")

        bs = b_sub.add_parser("show", help="Show budget state")
        bs.add_argument("id")

        bcon = b_sub.add_parser("consume", help="Consume budget")
        bcon.add_argument("id")
        bcon.add_argument("--deductions", required=True, help='JSON: {"amount_cny":500}')

        br = b_sub.add_parser("revoke", help="Revoke budget with propagation")
        br.add_argument("id")
        br.add_argument("--source", default="cli")
        br.add_argument("--no-propagate", action="store_true")

        # chain
        c = sub.add_parser("chain", help="Source chain management")
        c_sub = c.add_subparsers(dest="chain_cmd", required=True)

        cc = c_sub.add_parser("create", help="Create a new source chain")
        cver = c_sub.add_parser("verify", help="Verify chain integrity")
        cver.add_argument("id")
        cshow = c_sub.add_parser("show", help="Show chain details")
        cshow.add_argument("id")

        # plan
        pl = sub.add_parser("plan", help="Plan preflight")
        pl_sub = pl.add_subparsers(dest="plan_cmd", required=True)
        pa = pl_sub.add_parser("preflight", help="Check a plan against budget boundaries")
        pa.add_argument("--plan", required=True, help="Plan JSON or @file")
        pa.add_argument("--budget-id", required=True)
        pa.add_argument("--strategy", default="sequential",
                        choices=["sequential", "full_aggregate", "key_step", "risk_weighted"])

        return p

    def run(self, args: Optional[list[str]] = None) -> int:
        ns = self.parser.parse_args(args)

        if ns.command == "verify":
            return self._cmd_verify(ns)
        elif ns.command == "budget":
            return self._cmd_budget(ns)
        elif ns.command == "chain":
            return self._cmd_chain(ns)
        elif ns.command == "plan":
            return self._cmd_plan(ns)
        return 1

    # ── verify ──────────────────────────────────────────────────

    def _cmd_verify(self, ns) -> int:
        data = _load_json(ns.action)
        decl = ActionDeclaration(**{k: v for k, v in data.items()
                                     if k in ActionDeclaration.__dataclass_fields__})
        req = IntentVerificationRequest(
            action=decl,
            touch_events=ns.touch,
            screen_on=not ns.screen_off,
            remote_control_detected=ns.remote,
        )
        token = self.runtime.adjudicate(req, budget_id=ns.budget_id, chain_id=ns.chain_id)
        _print_json({
            "verdict": token.verdict.value,
            "reason_code": token.reason_code,
            "reason_detail": token.reason_detail,
            "scores": {
                "embodied": token.embodied_consistency_score,
                "budget": token.budget_adequacy_score,
                "source_chain": token.source_chain_integrity_score,
            },
            "constraints": token.constraints,
            "budget_deduction": token.budget_deduction,
        })
        return 0 if token.verdict == Verdict.ALLOW else 1

    # ── budget ──────────────────────────────────────────────────

    def _cmd_budget(self, ns) -> int:
        if ns.budget_cmd == "create":
            quotas = _load_json(ns.quotas)
            budget = self.runtime.create_budget(
                owner_id=ns.owner,
                quotas=quotas,
                parent_id=ns.parent_id,
            )
            _print_json({"budget_id": budget.budget_id, "quotas": budget.quotas})
        elif ns.budget_cmd == "show":
            b = self.runtime.get_budget(ns.id)
            if b:
                _print_json({
                    "budget_id": b.budget_id,
                    "owner": b.owner_id,
                    "status": b.status.value,
                    "quotas": b.quotas,
                    "consumed": b.consumed,
                    "remaining": b.remaining,
                })
            else:
                _print_json({"error": "budget not found"})
                return 1
        elif ns.budget_cmd == "consume":
            d = _load_json(ns.deductions)
            b = self.runtime.budgets.consume(ns.id, d)
            if b:
                _print_json({"remaining": b.remaining, "status": b.status.value})
            else:
                _print_json({"error": "budget not found"})
                return 1
        elif ns.budget_cmd == "revoke":
            affected = self.runtime.revoke_budget(
                ns.id,
                source=ns.source,
                propagate=not ns.no_propagate,
            )
            _print_json({
                "affected_count": len(affected),
                "budgets": [
                    {"id": b.budget_id, "owner": b.owner_id, "status": b.status.value}
                    for b in affected
                ],
            })
        return 0

    # ── chain ───────────────────────────────────────────────────

    def _cmd_chain(self, ns) -> int:
        if ns.chain_cmd == "create":
            cid = self.runtime.create_chain()
            _print_json({"chain_id": cid})
        elif ns.chain_cmd == "verify":
            result = self.runtime.verify_chain(ns.id)
            if result:
                _print_json({
                    "chain_id": result.chain_id,
                    "length": result.chain_length,
                    "valid": result.valid,
                    "score": result.score,
                    "chain_hash": result.chain_hash,
                    "breaks": [
                        {"position": b.position, "tag": b.tag.value, "detail": b.detail}
                        for b in result.breaks
                    ],
                })
            else:
                _print_json({"error": "chain not found"})
                return 1
        elif ns.chain_cmd == "show":
            chain = self.runtime.get_chain(ns.id)
            if chain:
                _print_json({
                    "chain_id": chain.chain_id,
                    "length": chain.length,
                    "entries": [
                        {
                            "position": e.chain_position,
                            "action_ref": e.action_ref,
                            "action_type": e.action_type,
                            "entry_hash": e.entry_hash[:16],
                            "authorization_ref": e.authorization_ref,
                        }
                        for e in chain.entries
                    ],
                })
            else:
                _print_json({"error": "chain not found"})
                return 1
        return 0

    # ── plan ────────────────────────────────────────────────────

    def _cmd_plan(self, ns) -> int:
        if ns.plan_cmd == "preflight":
            data = _load_json(ns.plan)
            steps = tuple(
                ActionDeclaration(**{k: v for k, v in s.items()
                                     if k in ActionDeclaration.__dataclass_fields__})
                for s in data.get("steps", [])
            )
            plan = PlanDeclaration(
                owner_id=data.get("owner_id", ""),
                plan_name=data.get("plan_name", ""),
                steps=steps,
            )
            from sayfos.verification.preflight import PreflightStrategy
            strategy = PreflightStrategy(ns.strategy)
            result = self.runtime.preflight_plan(plan, ns.budget_id, strategy)
            _print_json({
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
            })
        return 0


def _load_json(raw: str) -> dict:
    if raw.startswith("@"):
        with open(raw[1:], encoding="utf-8-sig") as f:
            return json.load(f)
    return json.loads(raw)


def _print_json(obj: dict) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def main():
    cli = SayfosCLI()
    sys.exit(cli.run())


if __name__ == "__main__":
    main()
