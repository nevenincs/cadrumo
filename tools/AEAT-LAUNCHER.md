# aeat windows launcher

Operator-facing helper scripts that complement `uv run aeat`.

## `aeat.cmd` / `aeat.ps1` — Windows interactive launcher

Plain `uv run aeat` on Windows re-syncs the virtualenv on every invocation.
The sync races the OS handle on `Scripts/aeat.exe` and intermittently raises
`os error 32` (file in use). The canonical workaround is `uv run --no-sync
aeat ...`; these launcher scripts make it the default.

### cmd / batch

```
tools\aeat.cmd config status
tools\aeat.cmd app overview status
```

### PowerShell

```
tools\aeat.ps1 config status
tools\aeat.ps1 app overview status
```

### When to run `uv sync` manually

Any time `pyproject.toml` or the lockfile change. `aeat config repair`
surfaces a stale-sync diagnostic row with `next: uv sync` when drift is
detected (see the `dev-environment-uv-windows` ADR).
