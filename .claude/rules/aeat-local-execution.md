---
name: aeat-local-execution
trigger: always_on
---

# AEAT local execution

- Run repository commands from the owning worktree and use the environment declared by the project. Prefer `uv run ...` for Python tools and `rg`/`rg --files` for search.
- Use PowerShell-native quoting and path handling on Windows. Do not publish Unix-only command recipes as the sole project workflow.
- Validate the narrow changed surface first, then the owning subsystem, then broader gates in proportion to risk. Re-run dependent commands sequentially when concurrent runs could contend for the same cache, database, port, or generated output.
- Preserve the actual command, exit status, and complete failure identity. A truncated excerpt, passing retry without explanation, or background launch is not evidence of success.
- Use isolated temporary locations for destructive or detector-teeth checks. Resolve and verify exact paths before delete, move, overwrite, or cleanup operations.
- Do not substitute a mocked service for a repository gate that claims to exercise the real integration. If an external dependency is unavailable, report that limitation explicitly.
