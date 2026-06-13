---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S96
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P25.S96-S98

## Outcome

Implemented ledger bulk-classify CSV path, rule engine CLI surface, and 13
regression tests across three plan steps (S96/S97/S98) in two commits.

### Domain model and repository (committed with S97 application layer)

`src/aeat/domain/transactions/_classification_rule.py`:
- `LedgerClassificationRule` — strict/frozen pydantic model; `rule_id` is a
  64-char SHA-256 hash of `description_pattern|classification|category_id`
  (content-addressed, so adding the same rule twice is idempotent).
- `LedgerClassificationRule.create()` factory validates the regex pattern via
  `re.compile` and sets `created_at=UTC now`.
- `matches(description)` runs `re.search(pattern, description, re.IGNORECASE)`.

`src/aeat/application/ledger/_rule_repository.py`:
- `LedgerClassificationRuleRepository(SecureBoundRepository[LedgerClassificationRule])` —
  namespace `"aeat.ledger.classification.rules"`, sensitivity `AUDIT`, schema
  version 1. `list_rules()` returns rules sorted by `(priority, created_at)` asc.

### Application layer (previously committed; no working-tree diff at this session's start)

`src/aeat/application/ledger/_models.py`:
- `ManualLedgerTransactionCommand.classified_by_override: str | None = None` —
  lets the rule engine inject `"rule:<rule_id>"` provenance without changing
  `BucketEvent.actor` (which has a 64-char cap; `"rule:"+64-char-id` = 69 chars).
- `BulkClassifyRow`, `BulkClassifyFailure`, `BulkClassifyResult` — typed models
  for the CSV batch path.
- `ApplyRulesAppliedRow`, `ApplyRulesResult` — typed result for rule apply.
- `LedgerTransactionReviewPayload.classified_by: str | None` — exposes
  provenance in `ledger list` JSON output.

`src/aeat/application/ledger/_actions.py`:
- `_transaction_from_command`: sets `classified_by = command.classified_by_override or "manual"` when `business_classification != NOT_YET_PROCESSED`.
- `bulk_classify_from_csv`: parses CSV into `BulkClassifyRow`, rejects unknown
  columns pre-persistence, applies partial-success semantics.
- `add_classification_rule`: content-addressed rule creation via repo save.
- `apply_classification_rules`: loads rules + catalogue, evaluates rules in
  priority order (first match wins), skips already-classified transactions
  unless `reaffirm=True`.

### CLI surface (previously committed)

`src/aeat/entrypoints/cli/_ledger.py`:
- `ledger classify --from-csv <path>` — exclusive with `--id`/`--classification`;
  emits `{total, applied, skipped, failures}`.
- `rule_app` sub-app registered as `ledger rule`:
  - `rule add --description-pattern --classification [--priority] [--category-id]`
  - `rule list` — JSON `{rules: [...]}`
  - `rule apply [--dry-run] [--reaffirm]` — dry-run returns preview without mutations.

### Tests

`src/aeat/entrypoints/cli/test_ledger_bulk_classify.py` (13 tests, all pass):
- `--from-csv`: valid batch, partial-failure, unknown-column rejection,
  exclusivity with `--id`, file-not-found.
- `rule add/list`: add + list round-trip, idempotency same-pattern, invalid
  regex rejection, empty list.
- `rule apply`: classifies NOT_YET_PROCESSED with correct `classified_by` provenance,
  skips already-classified without `--reaffirm`, dry-run does not mutate,
  priority ordering (lower int wins).

## Commits

Prior session:
- `_actions.py`, `_models.py`, `_ledger.py` changes (bulk-classify + rule engine
  implementation + CLI surface) — committed before this session's context window.

This session:
- `6c4ec924c` — W05.P25.S96-S98: bulk-classify CSV + rule engine + 13 regression tests
  (adds `_classification_rule.py`, `_rule_repository.py`, `test_ledger_bulk_classify.py`)
