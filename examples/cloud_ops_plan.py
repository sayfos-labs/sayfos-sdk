"""
Sayfos SDK example: cloud operations plan preflight.

Demonstrates Sayfos Preflight. A cloud operations agent prepares a
maintenance plan, but one step would exceed the available resource boundary.
Sayfos detects the overflow before any step is executed.

Run: python examples/cloud_ops_plan.py
"""

from sayfos import ActionDeclaration, SayfosRuntime
from sayfos.verification.preflight import PlanDeclaration, PreflightStrategy


def main() -> None:
    rt = SayfosRuntime()

    budget = rt.create_budget(
        owner_id="cloud-ops-agent",
        quotas={
            "amount_cny": 500.0,
            "tool_calls": 20,
            "data_egress_mb": 50.0,
        },
    )
    print(f"[Budget] {budget.quotas}")

    plan = PlanDeclaration(
        owner_id="cloud-ops-agent",
        plan_name="maintenance-window-saturday",
        steps=(
            ActionDeclaration(
                action_type="read",
                target="service-status",
                parameters={"service": "web-gateway"},
                risk_level=1,
            ),
            ActionDeclaration(
                action_type="read",
                target="service-status",
                parameters={"service": "api-server"},
                risk_level=1,
            ),
            ActionDeclaration(
                action_type="write",
                target="config-update",
                parameters={"service": "web-gateway", "config": "timeout=30s"},
                risk_level=3,
            ),
            ActionDeclaration(
                action_type="deploy",
                target="cloud-instance-extend",
                parameters={"amount": 9999.0, "instance_type": "c5.4xlarge"},
                risk_level=7,
            ),
            ActionDeclaration(
                action_type="read",
                target="health-check",
                parameters={"service": "all"},
                risk_level=1,
            ),
        ),
    )

    print(f"\n[Plan] {plan.plan_name}: {plan.step_count} steps")

    result = rt.preflight_plan(plan, budget.budget_id)

    print(f"\n[Preflight] strategy: {result.strategy.value}")
    print(f"  feasible: {result.feasible}")
    print(f"  score: {result.score}")
    print(f"  reason_code: {result.reason_code}")

    if not result.feasible:
        step = result.first_overflow_step
        print(f"\n[Overflow] step {step}: {plan.steps[step].action_type}")
        print(f"  dimension: {result.overflow_dimension}")
        print(f"  detail: {result.overflow_detail}")
        print(f"  hint: replan step {step} before execution starts")

    print(f"\n[Estimated consumption] {result.estimated_consumption}")
    print(f"[Remaining after preflight] {result.budget_remaining_after}")

    result_rw = rt.preflight_plan(
        plan,
        budget.budget_id,
        PreflightStrategy.RISK_WEIGHTED,
    )
    print(
        f"\n[Risk weighted] feasible={result_rw.feasible}, "
        f"first_overflow_step={result_rw.first_overflow_step}"
    )


if __name__ == "__main__":
    main()
