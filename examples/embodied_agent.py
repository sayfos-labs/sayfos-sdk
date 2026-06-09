"""
Sayfos SDK — Example: 具身执行端/车载代理预算边界

Demonstrates proxy-authority budget governance for embodied agents:
  - Home robot: spatial budget, proximity limit, device access, noise level
  - Vehicle agent: remote control scope, vehicle state, time window, sovereignty

Corresponds exactly to:

Run: python examples/embodied_agent.py
"""

from sayfos import (
    ActionConstraint,
    ActionDeclaration,
    SayfosRuntime,
    IntentVerificationRequest,
    Verdict,
)


def main():
    rt = SayfosRuntime()

    # ═══════════════════════════════════════════════════════════
    # Scenario A: Home robot cleaning task
    # ═══════════════════════════════════════════════════════════

    robot_budget = rt.create_budget(
        owner_id="home-robot",
        quotas={
            "spatial_zones": 3,          # allowed: living_room, kitchen, hallway
            "tool_calls": 30,
            "autonomy_level": 2,          # 0=supervised, 1=assisted, 2=semi-auto, 3=full
            "proximity_cm": 50,           # minimum distance to humans
            "noise_db": 60,               # max noise level
            "time_window_hours": 2,       # allowed operation window
        },
    )
    print(f"[家庭机器人预算] {robot_budget.quotas}")

    # Allowed: clean living room
    clean = ActionDeclaration(
        actor_type="home_robot",
        action_type="physical_actuation",
        target="living_room/clean",
        parameters={"zone": "living_room", "mode": "vacuum", "noise_db": 45},
        root_authorization_ref="auth://home/owner",
        task_lineage_ref="task://daily-clean",
        risk_level=2,
    )
    token = rt.adjudicate(
        IntentVerificationRequest(action=clean, touch_events=1, screen_on=True, device_held=True),
        budget_id=robot_budget.budget_id,
    )
    print(f"  [客厅清洁] {token.verdict.value}")

    child_room = ActionDeclaration(
        actor_type="home_robot",
        action_type="physical_actuation",
        target="children_room/enter",
        parameters={"zone": "children_room"},
        root_authorization_ref="auth://home/owner",
        task_lineage_ref="task://unauthorized-explore",
        risk_level=9,
    )
    token = rt.adjudicate(
        IntentVerificationRequest(action=child_room, touch_events=0, screen_on=True, device_held=True),
        budget_id=robot_budget.budget_id,
    )
    print(f"  [儿童房进入] {token.verdict.value} — {token.reason_code}")

    night_clean = ActionDeclaration(
        actor_type="home_robot",
        action_type="physical_actuation",
        target="living_room/deep_clean",
        parameters={"zone": "living_room", "mode": "scrub", "noise_db": 75},
        root_authorization_ref="auth://home/owner",
        task_lineage_ref="task://night-clean",
        risk_level=6,
    )
    token = rt.adjudicate(
        IntentVerificationRequest(action=night_clean, touch_events=0, screen_on=True, device_held=True),
        budget_id=robot_budget.budget_id,
    )
    print(f"  [夜间深度清洁] {token.verdict.value} — noise exceeded")

    # ═══════════════════════════════════════════════════════════
    # Scenario B: Vehicle agent remote control
    # ═══════════════════════════════════════════════════════════

    vehicle_budget = rt.create_budget(
        owner_id="vehicle-agent",
        quotas={
            "remote_actions": 5,          # max remote control actions
            "autonomy_level": 1,           # 0=supervised only, 1=low-risk auto
            "time_window_hours": 1,        # operation window
            "speed_kmh": 30,              # max speed during remote operation
            "tool_calls": 20,
        },
    )
    print(f"\n[车载代理预算] {vehicle_budget.quotas}")

    # Allowed: low-risk remote check while parked
    check = ActionDeclaration(
        actor_type="vehicle_agent",
        action_type="remote_control",
        target="vehicle/status_check",
        parameters={"vehicle_state": "parked", "action": "battery_check"},
        root_authorization_ref="auth://owner/app",
        task_lineage_ref="task://remote-check",
        risk_level=2,
    )
    token = rt.adjudicate(
        IntentVerificationRequest(action=check, touch_events=1, screen_on=True),
        budget_id=vehicle_budget.budget_id,
    )
    print(f"  [停车状态检查] {token.verdict.value}")

    drive_action = ActionDeclaration(
        actor_type="vehicle_agent",
        action_type="remote_control",
        target="vehicle/steering",
        parameters={"vehicle_state": "driving", "action": "lane_change", "speed_kmh": 80},
        root_authorization_ref="auth://owner/app",
        task_lineage_ref="task://remote-drive",
        risk_level=10,
    )
    token = rt.adjudicate(
        IntentVerificationRequest(
            action=drive_action,
            touch_events=0,
            screen_on=True,
            device_held=False,
        ),
        budget_id=vehicle_budget.budget_id,
    )
    print(f"  [行驶中远程操控] {token.verdict.value} — {token.reason_code}")

    late_action = ActionDeclaration(
        actor_type="vehicle_agent",
        action_type="remote_control",
        target="vehicle/unlock",
        parameters={"vehicle_state": "parked", "action": "door_unlock", "hours_elapsed": 3},
        root_authorization_ref="auth://owner/app",
        task_lineage_ref="task://late-unlock",
        risk_level=6,
    )
    # Simulate expired time window by exhausting time budget
    rt.budgets.consume(vehicle_budget.budget_id, {"time_window_hours": 2})
    token = rt.adjudicate(
        IntentVerificationRequest(action=late_action, touch_events=0, screen_on=True),
        budget_id=vehicle_budget.budget_id,
    )
    print(f"  [时间窗口外操作] {token.verdict.value} — {token.reason_code}")

    # ═══════════════════════════════════════════════════════════
    # Budget state after scenarios
    # ═══════════════════════════════════════════════════════════
    print(f"\n[家庭机器人剩余] {rt.get_budget(robot_budget.budget_id).remaining}")
    print(f"[车载代理剩余] {rt.get_budget(vehicle_budget.budget_id).remaining}")


if __name__ == "__main__":
    main()