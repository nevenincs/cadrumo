---
tags:
  - '#exec'
  - '#ccaa-in-profile'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - '[[2026-04-28-ccaa-in-profile-research]]'
  - '[[2026-04-28-ccaa-in-profile-adr]]'
  - '[[2026-04-28-ccaa-in-profile-plan]]'
---

# `ccaa-in-profile` execution summary

Implemented the tax-residence profile required by `#452` so Modelo 100 imports can resolve Kent's ordinary CCAA from durable local state instead of hand-feeding it at every verification call site.

## M100 call sites

- `aeat filing import --from-borrador`: now calls `require_tax_residence()` before parsing and verification. When `0545` and `0551` are present, it computes `compute_cuota_autonomica_general(0545, residence.ccaa, año)` and reports whether printed `0551` matches the profile CCAA tariff.
- `aeat filing import --from-declaracion` for Modelo 100: now calls `require_tax_residence()` before verification and prints the configured CCAA.
- `compute_cuota_autonomica_general(blg, ccaa, año)` remains the single source of autonomic-tariff computation and still consumes the closed `CCAA` enum from `modelo_100._ccaa`.

## Persistence

The profile is local-state Path A JSON. The file payload is schema-versioned:

```json
{
  "schema_version": "1",
  "ccaa": "madrid",
  "tax_residence_since": "2025-01-01",
  "tax_residence_change_history": []
}
```

Default path resolution uses `AEAT_TAX_RESIDENCE_PROFILE_PATH` when set; otherwise `%APPDATA%\aeat\tax-residence.json` on Windows, `$XDG_CONFIG_HOME/aeat/tax-residence.json` when present, and `~/.config/aeat/tax-residence.json` as the POSIX fallback. Writes are atomic via same-directory temporary file plus `os.replace`.

No dependency on `aeat.adapters.persistence.storage`, SQLAlchemy, Alembic, or the in-flight `#216` database branch was introduced.

## CLI surface

- `aeat profile show`
- `aeat profile show --json`
- `aeat profile set tax-region <ccaa> [--since YYYY-MM-DD]`
- `aeat profile clear`

The registered JSON schema is `profile show`, with payload fields `configured`, `schema_version`, `ccaa`, `ccaa_label`, `tax_residence_since`, `profile_path`, and `downstream_references`.

## Foral path

`pais-vasco`, `país-vasco`, `pais_vasco`, `país_vasco`, `euskadi`, and `navarra` raise `ForalRegimeError`. The error is registered as `REFUSED_PROFILE_FORAL_REGIME` and the trilingual message points to `#424`.

## Trilingual output

The new CLI and errors use `Translatable` strings. Tests cover default Spanish and explicit English CLI paths. Hungarian strings are supplied as defaults.

Post-review remediation also moved the new profile help text, profile downstream references, M100 tax-residence/tariff messages, and setup tax-residence prompt behind the same `Translatable` pattern.

## Setup integration

`SetupAnswers` now captures `tax_residence_ccaa`. The interactive wizard prompts for the RENTA tax-residence CCAA, defaults to Madrid, and persists the tax-residence JSON beside the existing setup output.

## Bootstrap lockfile note

`uv.lock` changed because the issue bootstrap explicitly required `uv sync --all-groups --upgrade`, `uv lock --upgrade`, and `uv run vaultspec-core install --upgrade`. The lockfile refresh is retained as part of that requested bootstrap, with no new `pyproject.toml` dependency added for #452.

## Verification

- `uv run pytest src\aeat\profile src\aeat\cli\profile -q`
- `uv run pytest src\aeat\setup -q`
- `uv run pytest tests\integration\test_kent_workflows.py -q`
- `uv run pytest tests\test_config.py src\aeat\profile src\aeat\cli\profile src\aeat\setup tests\integration\test_kent_workflows.py -q`
- `just lint`
- `just typecheck`
- `just test`
- `just test-cov` completed with total coverage 81.48%, above the 60% floor
- `just hooks`
- `uv run aeat audit rulesets citations` reported aggregate 232/232 computed casillas with citations, 100.00% coverage

## Scope notes

Foral regimes remain out of scope for `#452` and belong to `#424`. Multi-residency within a tax year and per-CCAA per-deduction profile detail remain out of scope. Live AEAT submission remains permanently forbidden; this work only affects local profile state and local verification.
