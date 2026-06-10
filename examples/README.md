# Sayfos SDK Examples

These examples show how to place lightweight runtime checks between automated
agents and execution endpoints.

## Run

```bash
pip install -e .
python examples/<name>.py
```

## Examples

| Example | Scenario |
| --- | --- |
| api_cost_budget.py | Capping AI agent API calls and provider cost before execution |
| remote_control_detection.py | Detecting silent remote-control signals before a high-risk action |
| financial_fraud_detection.py | Context-aware intervention for high-risk financial actions |
| prompt_injection_isolation.py | Isolating actions influenced by untrusted input sources |
| finance_agent.py | Budget-governed batch reimbursement |
| cloud_ops_plan.py | Preflighting a cloud-operations plan before execution |
| code_agent_deploy.py | Guarding code-agent changes and deployments |
| multi_agent.py | Delegating runtime authority across parent and child agents |
| embodied_agent.py | Applying boundaries to robot, vehicle, and IoT-style actions |
| end_to_end.py | Combining source chain, budget, preflight, and embodied checks |
