---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'W07.P17.S63'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-27-live-iva-compensation-wallet-reload-review-audit]]'
---

# `live-iva-compensation-wallet` `W07.P17.S63`

Removed exact operator-private identity markers from committed tests, fixtures,
and vault notes discovered during the reload privacy sweep.

- Modified: `src/aeat/adapters/inbound/sanitizer/test_records.py`
- Modified: `src/aeat/adapters/inbound/sanitizer/test_streams.py`
- Modified: `src/aeat/adapters/inbound/sanitizer/test_pipeline.py`
- Modified: `src/aeat/adapters/inbound/sanitizer/test_dynamic.py`
- Modified: `src/aeat/adapters/inbound/sanitizer/__init__.py`
- Modified: `src/aeat/adapters/inbound/pdf/test_scrub.py`
- Modified: `src/aeat/adapters/inbound/justificante/test_extract_modelos.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_notifications.py`
- Modified: `src/aeat/application/filing/reconciliation/test_reconcile.py`
- Modified: `src/aeat/application/live/test_borrador_100_roundtrip.py`
- Modified: `src/aeat/application/user_profile/test_repository_roundtrip.py`
- Modified: `src/aeat/application/user_profile/test_repository_anti_tautology.py`
- Modified: `src/aeat/application/workflow/test_engine.py`
- Modified: `src/aeat/tests/fixtures/aeat-sede/expediente-irpf-2023-detail.html`
- Modified: `src/aeat/tests/test_env_loader.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`
- Modified: `.vault/audit/2026-05-27-live-iva-compensation-wallet-reload-review.md`

## Description

The source/vault privacy sweep found exact operator identity markers in
sanitizer tests, synthetic Sede fixtures, storage roundtrip fixtures,
reconciliation defaults, and older vault notes. The slice replaces those exact
markers with synthetic canaries or redacted wording. Sanitizer tests keep
valid-shape synthetic NIE/NIF inputs where production validators need that shape
to prove redaction and checksum behavior. Re-review also removed a remaining
surname-bearing email fixture and replaced non-required reconciliation defaults
with non-tax-ID labels.

The active audit now records the privacy finding as `RELOAD-009`. It also records
the separate reconciliation blockers exposed by the focused gate as `RELOAD-010`:
Modelo 130 previous-filing projection and Modelo 180 legal-ref drift.

## Tests

- `uv run pytest -q src/aeat/adapters/inbound/sanitizer/test_records.py src/aeat/adapters/inbound/sanitizer/test_streams.py src/aeat/adapters/inbound/sanitizer/test_pipeline.py src/aeat/adapters/inbound/sanitizer/test_dynamic.py src/aeat/adapters/inbound/pdf/test_scrub.py src/aeat/application/user_profile/test_repository_roundtrip.py src/aeat/application/user_profile/test_repository_anti_tautology.py src/aeat/application/live/test_borrador_100_roundtrip.py src/aeat/tests/test_env_loader.py` passed.
- `uv run pytest -q src/aeat/application/filing/reconciliation/test_reconcile.py` remains blocked by the non-IVA registry defects recorded in `RELOAD-010`.
- `uv run ruff check` passed for the touched Python files.
- Static source/vault scan for the leaked operator identity markers returned no matches outside the intentionally ignored local private env file.
