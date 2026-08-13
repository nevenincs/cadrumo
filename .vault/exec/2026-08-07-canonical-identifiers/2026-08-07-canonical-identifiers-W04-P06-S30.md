---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b41881c3ae89f6a3bbef4899cebcee3958c815b1e3e11a9911d3433b6c2c6600'
step_id: 'S30'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# retype classified transaction-id pydantic model fields onto `TransactionId` in `application/aggregation/`

## Scope

- `src/cadrumo/application/aggregation/_impatriado_income_ledger.py`
- `src/cadrumo/application/aggregation/_irnr_income_ledger.py`
- `src/cadrumo/application/aggregation/_iva_ledger.py`
- `src/cadrumo/application/aggregation/_renta_gasto_ledger.py`
- `src/cadrumo/application/aggregation/_renta_income_ledger.py`
- `src/cadrumo/application/aggregation/_renta_ledger.py`
- `src/cadrumo/application/aggregation/tests/test_grouping.py`
- `src/cadrumo/application/aggregation/tests/test_income_withheld_derivation.py`
- `src/cadrumo/application/aggregation/tests/test_renta_ledger_helpers.py`

## Description

- Re-derived the denominator with an AST probe over a fresh `git archive
  HEAD` extraction of `application/aggregation/`, model-field-only,
  `tests/` excluded, matching `W04.P06.S29`'s methodology. Found 11 bare
  `str` sites across 6 files plus one non-model `@dataclass` field
  (`_IvaTransactionContext.transaction_id`, `_iva_ledger.py`) correctly
  out of scope for a "pydantic model field" retype.
- Traced every one of the 11 to its construction site(s) before retyping:
  - 9 sites across `_impatriado_income_ledger.py`,
    `_irnr_income_ledger.py`, `_renta_gasto_ledger.py`,
    `_renta_income_ledger.py`, `_renta_ledger.py` (the row's own named
    "renta-ledger-expenses model") — every construction site traced to
    `transaction.transaction_id` off an already-loaded, real catalogue
    `Transaction`, directly or through one local variable / one intervening
    helper function. Retyped.
  - `ProrrataLedgerReference.transaction_id` (`_iva_ledger.py`) — one
    construction site, `transaction.transaction_id`. Retyped.
  - `IvaLedgerAggregationIssue.transaction_id` (`_iva_ledger.py`) — LEFT
    BARE, a real and load-bearing exclusion. Most construction sites feed
    `transaction.transaction_id`, but `aggregate_iva_ledger_candidates`
    feeds `candidate.ledger_id` where `candidate: IvaLedgerCandidate` and
    `ledger_id: _LedgerId` (a module-private alias, 1-128 chars, no
    hex-64 pattern) — "one pre-classified ledger line... that cannot be
    inferred safely from a bank transaction", by its own docstring, so a
    real `IvaLedgerCandidate` need not name a catalogued `Transaction` at
    all. `IvaLedgerAggregationIssue.transaction_id`'s OWN existing bound
    (`Field(min_length=1, max_length=128)`) matches `_LedgerId`'s 128-char
    cap, not `TransactionId`'s 64-hex pattern — evidence the field's
    author sized it to admit BOTH populations. `IvaLedgerCandidate` has
    zero production construction sites in `src/` today (only tests), so
    retyping would not break a LIVE caller, but would silently narrow a
    wired, exported, tested production path the moment it gets one.
    Documented inline with a code comment, not only in this record, so a
    future retype attempt reads the reason before repeating it.
- Fixed 11 tests broken by the retype, across 3 files, all placeholder
  literals (`"tx-1"`, `"tx-2"`, `"tx-3"`, `"tx-a"`, `"tx-b"`, `"tx-c"`)
  predating the retype:
  - `test_grouping.py`: added a `_tx(suffix)` helper padding a single hex
    character to 64 chars (`suffix.rjust(64, "0")`) so the file's own
    sort-order assertions (`("tx-a", "tx-b", "tx-c")`) stay meaningful
    under the real shape — the trailing character still sorts the same
    way, so the fixture keeps proving what it always proved.
  - `test_income_withheld_derivation.py`: two `model_validate(...)` dict
    fixtures replaced with real `hashlib.sha256(...).hexdigest()` values,
    so the assertion each test actually makes (`pytest.raises(ValueError,
    match="claims a derived figure" / "must not carry the figure it
    refused")`) is reached — a bare-shape `transaction_id` would have
    raised on the FIELD before the model's own `model_validator(mode=
    "after")` ever ran, so the match string would never appear and the
    test would fail for an unrelated reason.
  - `test_renta_ledger_helpers.py`: one shared `_issue()` fixture helper,
    one named constant.

## Outcome

COMPLETE. 10 of 11 classified sites retyped; 1 left bare with a traced,
demonstrated construction-site reason, documented both in this record and
inline in the source. `ruff check`, `ruff format --check`, `basedpyright`
clean on all 6 touched production files. Full
`application/aggregation/tests/` suite: 919 passed, 5 pre-existing
unrelated failures (confirmed by error type — none is a
`pydantic.ValidationError` naming `transaction_id`; each is a distinct
pre-existing business-logic or fingerprint assertion, and none of the 5
implicated files were dirty before this row started).

## Notes

No incidents. The `IvaLedgerAggregationIssue` exclusion is the same shape
as `W04.P06.S29`'s two exclusions and `W06.P09.S45`'s semantic-
misclassification findings: a census name match does not by itself prove
one population, and this campaign's standing discipline of tracing every
construction site before retyping is what catches it before a mechanical
sweep would have silently narrowed a currently-dormant but real production
contract.
