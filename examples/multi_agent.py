"""
Sayfos SDK — Example: 父 Agent 拆分子 Agent（多 Agent 预算继承）

Demonstrates budget governance 子预算继承 (spawn_child) and source-chain integrity 来源链跨 Agent 追踪.

Scenario:
  父 Agent 被授权处理市场分析任务，总预算 10000 CNY。
  父 Agent 将任务拆分为 3 个子 Agent，各自继承受限子预算。
  当父 Agent 撤销授权时，所有子 Agent 的预算连锁冻结。

Run: python examples/multi_agent.py
"""

from sayfos import (
    ActionDeclaration,
    SayfosRuntime,
    IntentVerificationRequest,
    Verdict,
)


def main():
    runtime = SayfosRuntime()

    # ── 1. Create parent budget ─────────────────────────────────
    parent = runtime.create_budget(
        owner_id="orchestrator-agent",
        quotas={
            "amount_cny": 10000.0,
            "tool_calls": 50,
            "data_egress_mb": 100.0,
        },
    )
    print(f"[父预算] {parent.budget_id}: {parent.quotas}")

    # ── 2. Spawn child agents with constrained sub-budgets ──────
    children = {}
    for name, amount in [
        ("数据采集Agent", 3000),
        ("分析建模Agent", 4000),
        ("报告生成Agent", 2000),
    ]:
        child = runtime.create_budget(
            owner_id=name,
            quotas={"amount_cny": float(amount), "tool_calls": 10},
            parent_id=parent.budget_id,
        )
        children[name] = child
        print(f"  [子预算] {name} → {child.budget_id}: {child.quotas}")

    # ── 3. Each child agent does work ───────────────────────────
    chain = runtime.create_chain()

    for name, child in children.items():
        decl = ActionDeclaration(
            actor_type=name,
            action_type="data_egress" if "数据" in name else "read",
            target=f"API/{name}",
            parameters={"amount": 500},
            root_authorization_ref=f"auth://parent/{parent.budget_id}",
            task_lineage_ref=f"task://市场分析/{name}",
            budget_state_ref=child.budget_id,
        )
        request = IntentVerificationRequest(
            action=decl,
            touch_events=5,
            screen_on=True,
            device_held=True,
        )
        token = runtime.adjudicate(
            request,
            budget_id=child.budget_id,
            chain_id=chain,
        )
        print(f"  [{name}] → {token.verdict.value}")

    # ── 4. Revoke parent — children should be frozen ────────────
    print("\n[撤销] orchestrator-agent 授权被撤回...")
    affected = runtime.revoke_budget(parent.budget_id, source="user_revoked")

    for b in affected:
        print(f"  {b.owner_id}: status={b.status.value}")

    # Verify children are revoked
    for name, child in children.items():
        c = runtime.get_budget(child.budget_id)
        print(f"  [{name}] 状态: {c.status.value}")

    # Verify chain integrity
    result = runtime.verify_chain(chain)
    print(f"\n[来源链] 有效={result.valid}, 长度={result.chain_length}")


if __name__ == "__main__":
    main()