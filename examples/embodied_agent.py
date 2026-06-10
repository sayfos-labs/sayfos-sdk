"""
Sayfos SDK example: embodied and vehicle-agent boundaries.

Demonstrates budget and runtime boundaries for automated executors that can
affect physical systems, such as home robots and vehicle agents.

Run: python examples/embodied_agent.py
"""

from sayfos import (
    ActionDeclaration,
    IntentVerificationRequest,
    SayfosRuntime,
)


def main() -> None:
    rt = SayfosRuntime()

    robot_budget = rt.create_budget(
        owner_id="home-robot",
        quotas={
            "spatial_zones": 3,
            "tool_calls": 30,
            "autonomy_level": 2,
            "proximity_cm": 50,
            "noise_db": 60,
            "time_window_hours": 2,
        },
    )
    print(f"[Home robot budget] {robot_budget.quotas}")

    clean = ActionDeclaration(
        actor_type="home_robot",
        action_type="physical_actuation",
        target="living_room/clean",
        parameters={"zone": "living_room", "mode": "vacuum", "noise_db": 45},
        root_authorization_ref="auth://home/owner",
        task_lineage_ref="task://daily-clean",
        tool_reason_ref="reason://scheduled-cleaning",
        decision_token_ref="token://home-approved",
        risk_level=2,
    )
    token = rt.adjudicate(
        IntentVerificationRequest(
            action=clean,
            touch_events=1,
            screen_on=True,
            device_held=True,
        ),
        budget_id=robot_budget.budget_id,
    )
    print(f"  [Living room clean] {token.verdict.value}")

    child_room = ActionDeclaration(
        actor_type="home_robot",
        action_type="physical_actuation",
        target="children_room/enter",
        parameters={"zone": "children_room"},
        root_authorization_ref="auth://home/owner",
        task_lineage_ref="task://unauthorized-explore",
        tool_reason_ref="reason://autonomous-exploration",
        decision_token_ref="token://home-approved",
        risk_level=9,
    )
    token = rt.adjudicate(
        IntentVerificationRequest(
            action=child_room,
            touch_events=0,
            screen_on=True,
            device_held=True,
        ),
        budget_id=robot_budget.budget_id,
    )
    print(f"  [Restricted room entry] {token.verdict.value} - {token.reason_code}")

    night_clean = ActionDeclaration(
        actor_type="home_robot",
        action_type="physical_actuation",
        target="living_room/deep_clean",
        parameters={"zone": "living_room", "mode": "scrub", "noise_db": 75},
        root_authorization_ref="auth://home/owner",
        task_lineage_ref="task://night-clean",
        tool_reason_ref="reason://deep-cleaning",
        decision_token_ref="token://home-approved",
        risk_level=6,
    )
    token = rt.adjudicate(
        IntentVerificationRequest(
            action=night_clean,
            touch_events=0,
            screen_on=True,
            device_held=True,
        ),
        budget_id=robot_budget.budget_id,
    )
    print(f"  [Night deep clean] {token.verdict.value} - noise boundary exceeded")

    vehicle_budget = rt.create_budget(
        owner_id="vehicle-agent",
        quotas={
            "remote_actions": 5,
            "autonomy_level": 1,
            "time_window_hours": 1,
            "speed_kmh": 30,
            "tool_calls": 20,
        },
    )
    print(f"\n[Vehicle agent budget] {vehicle_budget.quotas}")

    check = ActionDeclaration(
        actor_type="vehicle_agent",
        action_type="remote_control",
        target="vehicle/status_check",
        parameters={"vehicle_state": "parked", "action": "battery_check"},
        root_authorization_ref="auth://owner/app",
        task_lineage_ref="task://remote-check",
        tool_reason_ref="reason://owner-status-check",
        decision_token_ref="token://vehicle-approved",
        risk_level=2,
    )
    token = rt.adjudicate(
        IntentVerificationRequest(action=check, touch_events=1, screen_on=True),
        budget_id=vehicle_budget.budget_id,
    )
    print(f"  [Parked status check] {token.verdict.value}")

    drive_action = ActionDeclaration(
        actor_type="vehicle_agent",
        action_type="remote_control",
        target="vehicle/steering",
        parameters={"vehicle_state": "driving", "action": "lane_change", "speed_kmh": 80},
        root_authorization_ref="auth://owner/app",
        task_lineage_ref="task://remote-drive",
        tool_reason_ref="reason://remote-driving-command",
        decision_token_ref="token://vehicle-approved",
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
    print(f"  [Remote steering while driving] {token.verdict.value} - {token.reason_code}")

    late_action = ActionDeclaration(
        actor_type="vehicle_agent",
        action_type="remote_control",
        target="vehicle/unlock",
        parameters={"vehicle_state": "parked", "action": "door_unlock", "hours_elapsed": 3},
        root_authorization_ref="auth://owner/app",
        task_lineage_ref="task://late-unlock",
        tool_reason_ref="reason://late-remote-unlock",
        decision_token_ref="token://vehicle-approved",
        risk_level=6,
    )
    rt.budgets.consume(vehicle_budget.budget_id, {"time_window_hours": 2})
    token = rt.adjudicate(
        IntentVerificationRequest(action=late_action, touch_events=0, screen_on=True),
        budget_id=vehicle_budget.budget_id,
    )
    print(f"  [Out-of-window unlock] {token.verdict.value} - {token.reason_code}")

    print(f"\n[Home robot remaining] {rt.get_budget(robot_budget.budget_id).remaining}")
    print(f"[Vehicle agent remaining] {rt.get_budget(vehicle_budget.budget_id).remaining}")


if __name__ == "__main__":
    main()
