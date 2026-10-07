"""SALAAR — The Shadow Agent.
Awareness → Threat Detection → Action → People → Causal Chain → Auto-Advance → Execution.

Key entry points:
  salaar_realtime_scan()    — run every 5 min
  salaar_deep_scan()        — run every 30 min
  auto_advance_all_chains() — advance chain steps, verify predictions, fire fallbacks
  scan_org(org_id)          — manual trigger for a single org
  build_actor_map_cached()  — actor profiles from People Graph + LLM
  simulate_causal_chain()   — forward-simulate domino chain
  execute_chain_step()      — execute one link via MCP tools
"""
from .engine import salaar_realtime_scan, salaar_deep_scan, scan_org, deep_scan_org
from .insight import generate_salaar_brief, generate_people_insight
from .causal import (
    build_actor_map, build_actor_map_cached,
    simulate_causal_chain, execute_chain_step,
    auto_advance_chains, auto_advance_all_chains,
)
