"""
Sayfos SDK — Example: 云运维 Agent 批量变更（plan preflight 计划预适配）

Demonstrates Sayfos Preflight: the agent plans a maintenance
window with 5 steps, but step 4 (extend instance) would exceed
the cloud quota.  Sayfos detects this BEFORE execution begins.

对比: Without plan preflight → agent executes first 3 steps, fails at step 4
      With plan preflight    → agent learns about overflow at planning time,
                    can re-plan before any execution happens

Run: python examples/cloud_ops_plan.py
"""

from sayfos import (
    ActionDeclaration,
    SayfosRuntime,
)
from sayfos.verification.preflight import PlanDeclaration, PreflightStrategy


def main():
    rt = SayfosRuntime()

    # ── 1. Create a maintenance window budget ───────────────────
    budget = rt.create_budget(
        owner_id="cloud-ops-agent",
        quotas={
            "amount_cny": 500.0,      # cloud cost budget
            "tool_calls": 20,
            "data_egress_mb": 50.0,
        },
    )
    print(f"[预算] {budget.quotas}")

    # ── 2. Agent plans a 5-step maintenance window ──────────────
    plan = PlanDeclaration(
        owner_id="cloud-ops-agent",
        plan_name="维护窗口-周六凌晨",
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
            # Step 4: EXTEND INSTANCE — would exceed quota!
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

    print(f"\n[计划] {plan.plan_name}: {plan.step_count} 步")

    # ── 3. preflight the plan ───────────────────────────────────
    result = rt.preflight_plan(plan, budget.budget_id)

    print(f"\n[预适配] 策略: {result.strategy.value}")
    print(f"  可行: {result.feasible}")
    print(f"  评分: {result.score}")
    print(f"  原因码: {result.reason_code}")

    if not result.feasible:
        print(f"\n[超界] 步骤 {result.first_overflow_step}: "
              f"{plan.steps[result.first_overflow_step].action_type}")
        print(f"  维度: {result.overflow_dimension}")
        print(f"  详情: {result.overflow_detail}")
        print(f"\n  → Agent 应重新规划，将第 {result.first_overflow_step} 步移至下一维护窗口")

    print(f"\n[预估消耗] {result.estimated_consumption}")
    print(f"[剩余预算] {result.budget_remaining_after}")

    # ── 4. Try with risk-weighted strategy ──────────────────────
    result_rw = rt.preflight_plan(
        plan, budget.budget_id, PreflightStrategy.RISK_WEIGHTED
    )
    print(f"\n[风险加权] 可行={result_rw.feasible}, "
          f"首次超界={result_rw.first_overflow_step}")


if __name__ == "__main__":
    main()