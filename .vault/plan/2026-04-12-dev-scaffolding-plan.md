---
tags:
  - "#plan"
  - "#dev-scaffolding"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-dev-scaffolding-adr]]"
  - "[[2026-04-12-dev-scaffolding-research]]"
---

# dev-scaffolding plan

## phase-1 — env layout

- **step-1** Create `env/` directory. Move `.env.example` → `env/.env.example`
  (git mv). Content unchanged.
- **step-2** Update `src/aeat/config.py`:
  `env_file = PROJECT_ROOT / "env" / ".env"`.
- **step-3** Update `tests/test_config.py` to parse
  `PROJECT_ROOT / "env" / ".env.example"` and assert its existence there.
- **step-4** Update `.gitignore`: replace the blanket `env/` rule with
  `env/*` + `!env/.env.example`. Remove stale `.env` root ignore only if
  it would conflict (keep `.env` ignore — harmless, root `.env` still
  should never be committed).

## phase-2 — justfile dev loop

- **step-5** Rewrite `justfile` with these recipes:
  - `default` → `@just --list`
  - `bootstrap` → `uv sync` + `uv run vaultspec-core install`
  - `install` → `uv sync`
  - `sync` → `uv sync`
  - `env-setup` ([windows]/[unix]) → copy env/.env.example → env/.env if missing
  - `lint` → `uv run ruff check .`
  - `fmt` → `uv run ruff format .`
  - `typecheck` → `uv run ty check src tests`
  - `test` → `uv run pytest`
  - `hooks` → `uv run prek run --all-files`
  - `gcloud-setup` ([windows]/[unix]) → hardened.

- **step-6** Fix `gcloud-setup` on both platforms:
  - Windows: use a single `#!pwsh` shebang recipe; guard `winget` presence;
    print manual install URL if missing; `$ErrorActionPreference = 'Stop'`
    only around the update path.
  - Unix: unchanged structure but add `command -v brew` / `command -v curl`
    guards and manual-install fallback.

## phase-3 — verification

- **step-7** Run `uv sync`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run ty check src tests`, `uv run pytest`. Fix any issues at the root.
- **step-8** Run the acceptance chain: `just install && just env-setup && just test`.
- **step-9** Commit in focused chunks:
  1. vault artifacts (research/adr/plan),
  2. env/ layout + config/tests,
  3. justfile rewrite,
  4. exec summary.

## out of scope

- README rewrite. Pytest markers. New tests beyond the existing
  config alignment suite.
