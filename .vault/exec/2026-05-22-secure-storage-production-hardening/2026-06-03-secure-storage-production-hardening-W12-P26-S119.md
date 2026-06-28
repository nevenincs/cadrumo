---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S119'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-017 for AEAT site-health evidence

## Scope

- `src/aeat/adapters/outbound/aeat/browser/_site_health.py`
- `src/aeat/adapters/outbound/aeat/browser/test_site_health.py`
- `.vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Description

- Route `SiteHealthEvidence.html_fragment` through the central `aeat.core.redaction.redact_for_log()` policy at model construction.
- Keep the redacted fragment explicitly bounded after redaction so the 4096-character evidence limit remains true even if a replacement lengthens text.
- Keep the strict, frozen pydantic evidence shape while ensuring remote-provider HTML snippets cannot carry raw NIF, URL path/query, or bearer-token text into diagnostics or workflow alerts.
- Add parser-boundary coverage proving a WAF classification redacts sensitive HTML evidence before the `SiteHealthStatus` is returned.
- Close `AFR-017` and `W12.P26.S119` in the active-profile rollout ledger.

## Outcome

- `uv run --no-sync ruff check src/aeat/adapters/outbound/aeat/browser/_site_health.py src/aeat/adapters/outbound/aeat/browser/test_site_health.py` passed.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/browser/test_site_health.py` passed: 41 passed.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/browser/test_site_health.py src/aeat/adapters/outbound/aeat/browser/test_session.py` passed: 58 passed.
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md W12.P26.S119` closed the step row.

## Notes

- `_site_health.py` remains a typed diagnostic model boundary rather than a persistence adapter. The closure hardens the remote-provider evidence payload by applying the centralized audit/log redaction policy before any downstream workflow or diagnostics consumer can persist or render it.
- The next open affected-file rows remain `W12.P26.S120` through `W12.P26.S122` for export deserialization, record specs, and censo live surfaces.
