---
tags:
  - "#research"
  - "#dev-scaffolding"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-dev-scaffolding-adr]]"
  - "[[2026-04-12-dev-scaffolding-plan]]"
---

# dev-scaffolding research

## context

Issue wgergely/aeat#4: the justfile is provisional. `just gcloud-setup` fails,
the core dev loop (install/sync/lint/fmt/typecheck/test/hooks) has no recipes,
and there is no convention for `.env` files — only a loose `.env.example` at
repo root.

## findings

### current justfile

- Uses `set windows-shell := ["pwsh.exe", "-NoLogo", "-Command"]`.
- Only `gcloud-setup` exists, split by `[unix]` / `[windows]` attributes.
- Unix variant uses a bash shebang. Windows variant starts with `#!pwsh`
  which just is NOT the shebang mechanism — just interprets recipe lines as
  individual shell commands when no shebang triggers execution. On Windows,
  `#!pwsh` is passed through the pwsh command-line and is parsed as a
  comment, but the multi-line `if { ... } else { ... }` block is run as
  separate `-Command` invocations, which breaks because each line is a
  standalone pwsh process. The recipe must use a single pwsh shebang recipe
  or a single `-Command` block.
- `set windows-shell` uses `pwsh.exe` — fine if PowerShell 7 is installed,
  but fresh Windows clones may only have Windows PowerShell (`powershell.exe`).
  We will keep `pwsh.exe` for consistency with the existing convention and
  document prek.toml / pyproject requirements alongside.

### settings / env layout

- `src/aeat/config.py` resolves `PROJECT_ROOT = Path(__file__).parent.parent.parent`
  and uses `env_file=PROJECT_ROOT / ".env"`.
- `tests/test_config.py` reads `PROJECT_ROOT / ".env.example"`.
- `.gitignore` already has `env/` listed (line 141) — this must be adjusted
  to ignore `env/*` except `env/.env.example`.

### tooling

- Dev deps: ruff, ty, prek, pytest. Linting via ruff, formatting via
  `ruff format`, typecheck via `ty`, hooks via `prek`.
- `prek.toml` exists; hooks run via `prek run --all-files`.
- Tests lack `@pytest.mark.unit` / `@pytest.mark.live` markers currently —
  out of scope for this issue; we only need to ensure config tests still
  pass with the new env path.

### just attributes

Just supports `[windows]` and `[unix]` attributes to define platform-specific
variants of the same recipe name. Shebang recipes (`#!/usr/bin/env bash`,
`#!pwsh`) execute the entire recipe body as a single script, which is what
we need for multi-line pwsh logic. The existing gcloud-setup Windows recipe
uses `#!pwsh` but just requires the shebang on the FIRST line to trigger
script-mode — the current recipe body is correct in that respect. The
actual failure is more likely that `winget` is not always installed, and
that `(gcloud version 2>$null)[0]` indexing fails when gcloud is not found.

On re-read: the Windows recipe looks correct structurally. The failure mode
reported by the issue is more likely:
1. `pwsh.exe` not on PATH (user has powershell.exe only).
2. `winget` exit code propagation kills the recipe.
3. The Unix variant's `exec -l $SHELL` advisory line is harmless.

We will make both variants defensive: check for package managers, handle
missing-tool cases, and report manual-install guidance without failing
hard.

## decisions needed

See ADR.
