"""SmartDecigen Execution Runtime — Ch.X.
MCP as infrastructure, not architecture. Reasoning stays in SALAAR.
Execution is: plan → dispatch → execute → collect → verify → learn.

Modules:
  mcp_client  — Composio connection, tool registry, raw execution
  dispatcher  — Plan parser, atomic action queue, retry/fallback
  permissions — Executive authority gates, approval thresholds
  collector   — Result capture, evidence log, verification feed
"""