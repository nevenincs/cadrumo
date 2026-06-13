---
tags:
  - "#adr"
  - "#dev-scaffolding"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-dev-scaffolding-research]]"
  - "[[2026-04-12-dev-scaffolding-plan]]"
---

# dev-scaffolding adr

## status

Accepted (issue wgergely/aeat#4 scope pre-approved by maintainer).

## context

The justfile is the intended developer entry point but only ships one
broken recipe. Env-file handling has no convention. A fresh clone cannot
run `just install && just env-setup && just test`.

## decision

1. **justfile is the single dev entry point.** All core dev-loop commands
   are exposed as just recipes with `[windows]` / `[unix]` parity via
   shebang recipes (`#!/usr/bin/env bash` and `#!pwsh`).

2. **Recipe set (final):**
   - `bootstrap` — runs `uv sync` then `uv run vaultspec-core install`.
   - `install` — `uv sync` (installs runtime + dev deps).
   - `sync` — alias for `uv sync` (explicit name for CI clarity).
   - `env-setup` — copies `env/.env.example` → `env/.env` if missing.
   - `lint` — `uv run ruff check .`
   - `fmt` — `uv run ruff format .`
   - `typecheck` — `uv run ty check src tests`
   - `test` — `uv run pytest`
   - `hooks` — `uv run prek run --all-files`
   - `gcloud-setup` — hardened cross-platform gcloud install/update.

3. **Env file layout.** All `.env` files live under `env/`:
   - `env/.env.example` (tracked, canonical template).
   - `env/.env` (gitignored, user-local).
   - `env/.env.local`, `env/.env.<profile>` (reserved, gitignored).

   `Settings.model_config.env_file` resolves to `PROJECT_ROOT / "env" / ".env"`.

4. **Gitignore.** `env/*` is ignored, with an explicit un-ignore for
   `env/.env.example`. The legacy root `.env.example` is removed.

5. **tests/test_config.py** targets `PROJECT_ROOT / "env" / ".env.example"`
   and asserts its existence at the new location.

6. **Bootstrap docs.** README (out of scope if not already present for this
   section) is not modified; instead, `just bootstrap` is the documented
   first step and `just --list` provides discoverability. No README churn
   — CLAUDE.md already references uv / prek / ty conventions.

7. **gcloud-setup hardening.** Both variants wrap external commands in
   `try`/`trap`-style guards, fall back to printing manual-install
   instructions if no supported package manager is present, and never
   abort the dev loop with a non-zero exit when a reasonable fallback
   message can be shown.

## consequences

- Fresh clones follow `just bootstrap && just env-setup && just test`.
- `.env` at repo root is no longer loaded; any developer with an old
  root-level `.env` must move it to `env/.env`. Acceptable — no
  production usage yet.
- Cross-platform parity is enforced by the acceptance criterion on
  Windows; Unix is covered by construction (same recipe skeletons,
  bash shebang).
