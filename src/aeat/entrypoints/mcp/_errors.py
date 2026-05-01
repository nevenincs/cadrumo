"""MCP launcher error surface.

Re-exports :exc:`aeat.core.errors.McpLaunchError` so MCP entry points raise
a stable, package-local symbol without coupling to the canonical core
error taxonomy at the import site.
"""

from __future__ import annotations

from ...core.errors import McpLaunchError

__all__ = ["McpLaunchError"]
