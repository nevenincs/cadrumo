---
step_id: S02
tags:
  - '#exec'
  - '#quality-hardening-campaign'
date: '2026-06-10'
related:
  - '[[2026-06-09-quality-hardening-campaign-audit]]'
---

# `quality-hardening-campaign` S02: QHC-005 `@override` decorator burn-down (batch 3a)

## Outcome

`missing-override-decorator` reduced from 47 to **0**. `reportMissingParameterType`
remains at 7, all in peer-WIP files (`_amendment_actions.py`,
`_verification_actions.py`, `test_borrador_binding.py`) that cannot be touched
per the WIP fence.

Commit: `c2608a46d` — `types(qhc-005): add @override decorators in
adapters/application/core/domain (batch 3a)` — 15 files, 63 insertions.

## Files modified

- `src/aeat/adapters/outbound/aeat/browser/tests/test_session.py` — 5 methods: `apply`
  (x2, `_RecordingEvasion` + `FailingEvasion`), `launch` (x2,
  `FailingLaunchChromium` + `FailingNewContextChromium`), `new_context`
  (`FailingNewContextBrowser`)
- `src/aeat/adapters/outbound/llm/_providers/tests/test_gemini.py` — `log_message`
  on `_ObservedGeminiRequest`
- `src/aeat/adapters/persistence/storage/envelope/tests/test_secure_bound_repository.py`
  — `extract_identifier` on `_DummyRepository`
- `src/aeat/adapters/persistence/storage/envelope/tests/test_secure_bound_repository_contract.py`
  — `extract_identifier` on `_DummyRepository`
- `src/aeat/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`
  — 3 methods on `_FileWriteVisitor`: `visit_FunctionDef`, `visit_AsyncFunctionDef`,
  `visit_Call`
- `src/aeat/application/ledger/tests/test_bulk_classify_scale.py` —
  `save_with_secure_object_writes` on `_CountingTxRepo`
- `src/aeat/application/live/tests/test_snapshot_base.py` — 7 methods on
  `_ProbeSnapshotService`: `_derive_snapshot_id`, `_build_active_payload`,
  `_payload_axis_key`, `_payload_captured_at`, `_payload_snapshot_id`,
  `_payload_state`, `_demote_to_superseded`
- `src/aeat/application/wizard/tests/test_prompter.py` — `write`, `write_raw` on
  local `_RaisingOutput` class inside test function
- `src/aeat/core/i18n/tests/test_translatable_contract.py` — 13 visitor methods on
  `_TranslatableContractVisitor`
- `src/aeat/core/observability/tests/test_logging_filter.py` — `emit` on
  `_CaptureHandler`
- `src/aeat/core/resources/tests/test_registry.py` — `_load` on `_DummyRepository`
- `src/aeat/domain/currency/tests/test_service.py` — `get_eur_rate` on
  `_TableRateProvider`
- `src/aeat/entrypoints/cli/conftest.py` — `invoke` on `_TyperAwareCliRunner`
  (existing `# type: ignore[override]` retained; `@override` added above the def)
- `src/aeat/entrypoints/cli/tests/test_stdio.py` — `emit` on `_CapturingHandler`
- `src/aeat/tests/test_small_axis_cleanup_canonical_homes.py` — 6 methods across 3
  local `FinancialProvider` subclasses: `ingest` and `validate_source` each

## Before / after delta

| Diagnostic class           | Before (session start) | After  |
|----------------------------|------------------------|--------|
| `missing-override-decorator` | 47                   | **0**  |
| `reportMissingParameterType` | 7 (peer-WIP)         | 7      |

## Decisions

- `conftest.py` `invoke` already carried `# type: ignore[override]` with a rationale
  comment (click version variance); added `@override` above the def without disturbing
  the ignore. The two annotations are orthogonal: `@override` declares intent to the
  type system; `type: ignore[override]` suppresses pyright's signature-compatibility
  complaint.
- Local classes inside test functions (wizard prompter `_RaisingOutput`, small-axis
  cleanup providers) receive `@override` normally — the decorator is valid on methods
  in any scope.
- `test_bulk_classify_scale.py` `save_with_secure_object_writes` retained its existing
  `# type: ignore[no-untyped-def]` comment alongside the new `@override`.

## Verification gate

`just check-types` summary: `missing-override-decorator: 0`,
`reportMissingParameterType: 7` (all peer-WIP).
106 focused tests pass (`pytest` on the 15 modified test files).
`ruff check` clean after auto-fix of 1 import-order issue in
`test_bulk_classify_scale.py`.
