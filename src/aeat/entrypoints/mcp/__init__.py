"""Project-owned MCP launch helpers.

Hosts repo-local launchers for upstream Model Context Protocol servers.
The launchers bridge tracked, secret-free ``.mcp.json`` entries to
gitignored credential sources managed by :mod:`aeat.core.config`.

See :mod:`aeat.entrypoints.mcp.launch_google_workspace` for the
``workspace-mcp`` launcher.
"""
