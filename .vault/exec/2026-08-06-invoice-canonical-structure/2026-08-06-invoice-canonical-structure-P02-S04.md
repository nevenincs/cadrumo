---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:b30b123a05e4d2cd4afd9d4b2cb31416dd2e6ebce36f5a7d8a2086bcd30be0bb'
step_id: 'S04'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Prove the already-landed retention-rate and retention-amount writer options persist through the real encrypted namespace with a strict save-load-equality roundtrip plus an anti-tautology proof, the CLI and builder code having landed in ef0438561d and only the roundtrip gate remaining

## Scope

- `src/cadrumo/application/invoices/tests/test_creation.py`

## Description

- Measured the Step's criterion at `HEAD` before writing anything, per this plan's rule that a criterion already green must be recorded rather than ticked.
- Confirmed both halves exist, including that the anti-tautology half mutates the STORED payload rather than an in-memory model.
- Closed the Step as already-satisfied and named what could honestly be named about the satisfying commit.

## Outcome

**Closed as ALREADY SATISFIED. No code was written, and none should have been.**

The Step expected the writer code to be present and "only the roundtrip gate remaining". Both halves of that gate already exist and pass:

- **The strict roundtrip.** The encrypted-boundary roundtrip fixture populates both retención fields with non-default values and asserts strict model equality after reload.
- **The anti-tautology half.** A dedicated invariant module persists the record, deletes `retention_amount` from the STORED payload, and asserts the reload refuses — with the refusal required to name BOTH retención fields, so a refusal raised incidentally by some other validator would not satisfy it. A sibling test does the same for a retención exceeding its base.

That second point is what makes the existing coverage genuinely sufficient rather than superficially similar. The Step's whole concern was that a test merely calling the builder proves nothing once the writer has landed; the existing proof mutates persisted bytes and requires a named refusal, which is the stronger form.

**Writing a second proof here would have been the defect, not the diligence.** A duplicate roundtrip asserting the same property in a second location is the shape this campaign is retiring elsewhere — two authorities for one contract, free to drift.

**One honest limitation on naming the satisfying commit.** The plan asks the Step be closed "against that commit", and cites `ef0438561d` for the writer. That commit exists but is titled "Aggregate wip commit of all current changes", and the test files' own history runs back through similar aggregate and WIP-snapshot commits rather than a feature commit. So the satisfying change cannot be attributed to a clean, single-purpose commit. What can be stated precisely is the evidence: the tests exist at `HEAD`, they assert the required properties, and they pass.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/invoices/tests/test_retencion_persistence_invariant.py src/cadrumo/domain/invoices/tests/test_secure_storage_roundtrip.py -q --no-header
    9 passed in 7.39s

The two properties the Step required, located at `HEAD`:

    test_secure_storage_roundtrip.py:116-117   retention_rate / retention_amount populated non-default, strict equality after reload
    test_retencion_persistence_invariant.py:155 stored payload mutated to delete retention_amount, reload asserted to refuse naming both fields
    test_retencion_persistence_invariant.py:173 stored retencion above its base, reload asserted to refuse

The criterion was green on arrival. Per this plan's governing rule that is recorded, not silently ticked.

## Notes

This is the second Step in the campaign closed without changing code, and the two are different outcomes worth keeping distinct. The earlier one was **re-scoped** — executing it as written would have added a defect. This one is **already satisfied** — the work was done, correctly, before the campaign reached it.

Conflating those two would misread the plan's health. A re-scoped Step means the plan was wrong; an already-satisfied Step means the plan was written against a tree that then moved, which the plan itself predicted would happen and told executors to re-measure for.
