---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S237'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R7-MARC-D1 ledger classify list view blocked by silent profile-completeness gate

## Scope

- `ledger status review update preflight succeed on same profile`
- `config repair confirms ready`
- `no error message identifies which field triggers the gate`
- `surface the specific gate failure to operator or remove the gate`
- `same defect class as R7-A but on different verbs`
- `src/aeat/application/ledger/`

## Description

- Ground S237 through plan and code RAG searches, then inspect the live ledger classify, read, support, and UX-test surfaces.
- Re-read the Taller Norte persona transcript block that exercises ledger status, list, review, classify, and follow-up status on one profile.
- Verify current classify validation routes through ledger-specific bad-parameter formatting instead of the generic `config repair` boundary.
- Verify current status output surfaces concrete readiness issues naming the transaction, classification, missing fields, reason, and detail.
- Run focused real-CLI regression tests for classify, review, list, and view behavior.
- Run an independent no-code closure review; the reviewer reported no findings.

## Outcome

S237 is closed as already fixed/current-state verified. No production code change was needed. The current CLI no longer shows the reported silent profile-completeness gate across ledger classify/list/view/review/status flows: the persona transcript shows same-profile status/list/review/classify success, status names the missing business-classification readiness issue, classify succeeds on the same row, and the follow-up status reports ready.

## Notes

Validation:

- `uvx vaultspec-rag search "R7 MARC D1 ledger classify list view blocked silent profile completeness gate specific field failure" --type vault --doc-type plan --port 8766 --timeout 30` surfaced the open S237 plan row.
- `uvx vaultspec-rag search "ledger classify list profile completeness gate specific field failure ledger status review update preflight" --type code --port 8766 --timeout 30` surfaced ledger classify payloads, status/preflight surfaces, and related tests.
- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_ledger_classify_ux.py::test_classify_with_negative_taxable_base_names_the_real_cause src/aeat/entrypoints/cli/tests/test_ledger_classify_ux.py::test_classify_with_valid_taxable_base_still_succeeds src/aeat/entrypoints/cli/tests/test_ledger_classify_ux.py::test_review_by_short_id_prefix_resolves_the_transaction src/aeat/entrypoints/cli/tests/test_ledger_classify_ux.py::test_review_by_full_id_still_resolves_the_transaction -q` passed with four tests.
- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_ledger_view_ux.py::test_ledger_view_shows_iva_counterparty_and_notes_detail src/aeat/entrypoints/cli/tests/test_ledger_view_ux.py::test_classify_can_correct_and_view_iva_category src/aeat/entrypoints/cli/tests/test_ledger_view_ux.py::test_list_and_view_render_accented_descriptions_identically -q` passed with three tests.

Notes:

- `src/aeat/entrypoints/cli/_ledger_read_cli.py` had unrelated peer WIP during this closure; no ledger source or test file was edited.
- Reviewer Franklin reported no findings. Residual risk is that no single dedicated test is named for S237 and recreates the exact historical profile fixture across all four verbs, but current focused tests and the persona transcript cover the observed failure mode sufficiently for a no-code closure.
