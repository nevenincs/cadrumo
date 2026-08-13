---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:573131a47cff456c61b98cbf16de8a5b14dfb4900f5a191a73cb5fcc9288bc4d'
step_id: 'S29'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# retype classified transaction-id pydantic model fields onto `TransactionId` in `application/ledger/`

## Scope

- `src/cadrumo/application/ledger/_llm_review_workflow.py`
- `src/cadrumo/application/ledger/_models.py`
- `src/cadrumo/application/ledger/tests/test_llm_review_workflow_types.py`
- `src/cadrumo/application/ledger/tests/test_actions_classification_parse.py`

## Description

- Re-derived the denominator with an AST probe over a fresh `git archive
  HEAD` extraction of `application/ledger/` rather than trusting the
  reference document's census figure, distinguishing pydantic MODEL
  fields from non-model classes and excluding `tests/`, matching this
  campaign's established model-field-only methodology. `old_transaction_id`
  and `previous_transaction_id` matched zero sites in this package — a
  real finding, not an omission; they may live in `domain/transactions/`,
  out of this row's scope.
- Found 5 bare `str` occurrences of the target names on genuine pydantic
  models. Traced every ONE to its construction site(s) before retyping,
  per this campaign's standing discipline, rather than mechanically
  retyping the whole set:
  - `LlmReviewRequest.transaction_id` (`_llm_review_workflow.py`) —
    retyped. Zero production callers anywhere in `src/` (only this
    module's own tests construct it), so no live input source to check
    for a malformed-value risk; safe by construction.
  - `BulkClassifyRow.transaction_id` (`_models.py`) — retyped. Its sole
    construction site (`_actions_classification.py`'s
    `_parse_bulk_classify_rows`) already wraps `BulkClassifyRow
    .model_validate(...)` in `except (ValidationError, ValueError,
    KeyError)`, routing a shape failure into a `BulkClassifyFailure`
    rather than crashing — the retype narrows what was already a
    validated construction path.
  - `ApplyRulesAppliedRow.transaction_id` (`_models.py`) — retyped. Its
    one construction site feeds `tx.transaction_id` from an already-loaded,
    real catalogue `Transaction`, never raw input.
  - `BulkClassifyFailure.transaction_id` (`_models.py`) — LEFT BARE, a
    real and load-bearing exclusion, not caution. Traced every
    construction site in `_actions_classification.py`: several
    (surplus-cell rows, non-text-cell rows, and the `except` branch
    around `BulkClassifyRow.model_validate` itself) construct it from
    `_raw_csv_text(raw_row.get("transaction_id", ""))` — the UNVALIDATED
    raw CSV cell text, taken specifically BECAUSE the row failed to
    parse. None of these four `BulkClassifyFailure(...)` calls are
    themselves wrapped in a `try/except`. Retyping this field to
    `TransactionId` would make constructing the FAILURE RECORD raise on
    exactly the malformed input it exists to report, crashing CSV bulk
    classify on any row with a non-hex64-shaped `transaction_id` cell
    instead of reporting it as a failure.
  - `LedgerPreflightIssue.transaction_id` (`_preflight.py`) — LEFT BARE,
    also load-bearing. `_unsupported_period_issue()` constructs one with
    the literal sentinel `"__period__"` for a period-level issue with no
    associated transaction at all — a genuine second population sharing
    this field's name, the same class of finding `W06.P09.S45` recorded
    for `AeatParty.tax_id`. Every OTHER call site in this module passes a
    real transaction's id via `**common`, so the field mixes a real
    identity population with one deliberate non-identity sentinel; no
    single alias is correct for both.
- Fixed 4 tests broken by the retype, all placeholder-literal fixtures
  (`"tx-1"`, `"tx-valid"`, `"tx-invalid"`, `"tx-personal"`, `"tx-extra"`)
  predating the retype, never real or hex64-shaped: replaced with real
  `hashlib.sha256(...).hexdigest()` values, one per fixture label so a
  fixture that is SUPPOSED to fail for one stated reason (bad
  classification value; an extra CSV cell) does not coincidentally also
  carry an invalid `transaction_id` shape and pass for an unintended
  second reason.

## Outcome

COMPLETE. 3 of 5 classified sites retyped; 2 left bare, each with a
concrete, traced construction-site reason (a raw-echo failure record; a
sentinel-value mix), not caution. `ruff check`, `ruff format --check`,
`basedpyright` clean on all touched files. Full `application/ledger/tests/`
suite: 1344 passed, 5 pre-existing unrelated failures (confirmed by content
and by `git status` — none reference `transaction_id`, none of the
implicated files are dirty this session). Targeted CLI sweep
(`entrypoints/cli/tests/ -k "ledger or classify or bulk"`): 116 passed, 2
pre-existing unrelated failures (an `operator_action`-missing fixture gap
and the already-flagged `matched_rule_id` pattern mismatch, neither
referencing `transaction_id`, file confirmed clean).

## Notes

No incidents. The two exclusions found here are the same shape as this
campaign's other semantic-misclassification findings (`W06.P09.S45`): a
field's census name matched the target concept, but tracing its real
construction sites showed it sometimes carries a DIFFERENT value on
purpose (a raw unvalidated echo; a non-transaction sentinel). Neither is
this row's to redesign.
