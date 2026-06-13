---
step_id: S369
date: 2026-05-30
modified: '2026-05-30'
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W04.P19 S369-S396 execution record

## Steps closed (28)

S369-S396 — W04.P19 locale W2-scope completions, f-string-as-key fixes, tab-pair label localisation, aggregate coverage test.

## Files touched

- `src/aeat/adapters/outbound/aeat/auth/_authenticator.py` — 9 translated_message threadings (session_stale, closing, no_active_context, capture_requires_active_session, already_active_before_resume, no_context_capture_storage, capture_requires_certificate, persisted_session_verification_failed, context_marker_missing)
- `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py` — 5 threadings already in HEAD (already_active, verify_requires_active_context, metadata_invalid, approval_timeout, dni_nie_not_set)
- `src/aeat/adapters/outbound/aeat/sede/_declarations.py` — 4 threadings already in HEAD (playwright_buscar_click_failed, playwright_combobox_open_failed, playwright_combobox_select_failed, playwright_alert_modal_failed)
- `src/aeat/application/modelo/_actions.py` — 5 threadings (work_unit_mutation_refused, work_unit_already_discarded, amendment_verification_refused x2, workflow_input_mismatch)
- `src/aeat/application/ledger/_actions.py` — 2 threadings already in HEAD (evidence_attachment_requires_ids, purchase_evidence_already_set)
- `src/aeat/entrypoints/cli/_config/__init__.py` — 1 threading (unsupported_bundle_schema_version)
- `src/aeat/application/aggregation/_prorrata.py` — 3 f-string-as-key fixes (year_out_of_range, current_year_not_after_prior, invalid_provisional_period)
- `src/aeat/application/aggregation/_grouping.py` — 1 f-string-as-key fix (unsupported_modelo)
- `src/aeat/application/wizard/_commands.py` — next-hint tab label wrapped in tr()
- `src/aeat/diagnostics/secure_objects.py` — namespace + count tab labels wrapped in tr()
- `src/aeat/locales/en.yml`, `es.yml`, `ca.yml`, `hu.yml` — 32 new keys each
- `src/aeat/application/aggregation/test_counterpart.py` — updated to assert translated_message key + context
- `src/aeat/application/aggregation/test_prorrata.py` — updated 3 tests to assert new dotted keys
- `src/aeat/diagnostics/test_secure_objects.py` — updated to locale-agnostic value matching
- `src/aeat/test_locale_coverage_inventory.py` — new S396 test (132 items, all pass)

## Outcomes

- translated_message threadings per file: authenticator=9, clave_movil=5(HEAD), declarations=4(HEAD), modelo=5, ledger=2(HEAD), config=1
- f-string-as-key fixes: 4
- locale keys created: 32 per catalogue (en/es/ca/hu)
- pytest outcome: 132/132 locale inventory tests pass; aggregation, auth, wizard, diagnostics suites pass
- locale audit: ca/en/es/hu all ok
- collision signal: _clave_movil.py had peer WIP (SecretStr changes) at start; swept forward; peer committed before my commit
- commit SHA: 91a2ad67a
