"""Handler registry — auto-discovers service handlers.
Each handler file registers a `handle(tool_name, args) -> dict` function.
"""

import logging
import importlib
from pathlib import Path

log = logging.getLogger("execution.handlers")

# Service prefix to handler function registry
_registry: dict = {}

# Decorator registering a service handler
def register(service_prefix: str):
    def decorator(fn):
        _registry[service_prefix.upper()] = fn
        return fn
    return decorator

# Look up handler by tool name prefix
def get_handler(tool_name: str):
    prefix = tool_name.split("_")[0].upper() if "_" in tool_name else tool_name.upper()
    return _registry.get(prefix)

# Return full handler registry copy
def registered_handlers() -> dict:
    return dict(_registry)

# Collect tool lists from all handlers
def all_tools() -> list:
    tools = []
    for prefix, fn in _registry.items():
        if hasattr(fn, "tool_list"):
            tools.extend(fn.tool_list)
    return tools

# Auto-import all handler modules in package
def _discover():
    handlers_dir = Path(__file__).parent
    for f in sorted(handlers_dir.glob("*.py")):
        if f.name == "__init__.py":
            continue
        mod_name = f"execution.handlers.{f.stem}"
        try:
            importlib.import_module(mod_name)
        except Exception as e:
            log.warning(f"Failed to load handler {f.name}: {e}")

_discover()
