---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P10.S45'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-persona-testimonial-re-audit]]'
---

# `cross-campaign-hardening` `P10.S45`

Folded the `P10.S44` testimonial regression into a follow-up repair wave
and re-ran the affected gates.

- Fixed: Modelo 100 profile-sourced binding readiness labels
- Added: CLI regression coverage for real profile-sourced Modelo 100 rows
- Updated: testimonial audit disposition

## Description

`bindings list` mapped the legacy `profile_fact` source kind to
`profile fact` but did not map the current registry source kind
`profile`. The fallback rendered those rows as `ledger source`, which
misdirected operators toward ledger work for profile facts.

`src/aeat/entrypoints/cli/_modelo.py` now maps `profile` to
`profile fact` and retains the legacy `profile_fact` mapping.

`src/aeat/entrypoints/cli/test_modelo_discovery_defects.py` now asserts
that real Modelo 100 rows with `source = "profile"` render readiness as
`profile fact`.

## Tests

`uv run ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo_discovery_defects.py` passed.

`uv run pytest src/aeat/entrypoints/cli/test_modelo_discovery_defects.py -q` passed with 16 tests in 41.72s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S45` closed the row.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/audit/2026-05-21-cross-campaign-hardening-persona-testimonial-re-audit.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P10-S44.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P10-S45.md src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo_discovery_defects.py` passed; Git repeated the pre-existing CRLF notice for the plan.
