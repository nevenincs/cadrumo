---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:dfff58896d55a77ecc6c7de8a82f65412fbde483a0aab152a5b100fc327664d9'
step_id: 'S99'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# CORRECT the at-risk list produced by the positional-selection sweep, by confirming each named site instead of trusting the sweep's own output. The sweep Step named three sites as at-risk on the strength of a pattern match plus a sampled revision count. Confirming them modelo by modelo shows the list was PART WRONG, and in the direction that matters -- it over-flagged. Measured against the bundled authority: modelo 341 has 2 revisions (2005-2015, 2016-y-siguientes), modelo 038 has 2 (2024-desde-06, 2025-y-siguientes), but modelo 036 has ONE (2025-02-03-y-siguientes) and modelo 130 has ONE (2019-y-siguientes). SO test_audit_oracle_bindings IS NOT AT RISK TODAY, contrary to what the sweep recorded and what the loop prompt was carrying forward as a confirmed target. Its _bind_oracle_id_on_first_cross_reference does carry a double positional assumption, but modelo 130 declares exactly one revision, so next(iter(...)) cannot select wrongly; and the remaining cross_references[0] is deliberate and documented in the very next test, which explains that Modelo 130's first cross-reference is static_official_documentation and is overridden precisely because the audit rejects that surface for every oracle by construction. That is an intentional choice with a stated reason, not an accident of ordering. Editing it would have been a change for its own sake against a test that is correct. Same for the modelo 036 site in test_temporal_coverage. THE ONLY CONFIRMED DEFECTS IN THE SWEEP WERE THE ONES ALREADY FIXED: modelo 184's filing-schedule gate, which died on StopIteration, and modelo 341's temporal-coverage test, which passed while exercising a bounded selector. Both were real, both are green. THE LESSON IS THE SWEEP'S OWN, TURNED INWARD. This campaign's standing rule is that a broad run is an inventory to confirm and never a verdict. A grep sweep is the same kind of artefact and deserves the same treatment: fifty pattern matches are candidates, a sampled revision count is not a confirmation, and the confirming question is always the same one -- how many revisions does THIS modelo actually declare. Two of four named sites did not survive that question. Report the confirmed two, drop the other two, and do not carry an unconfirmed sweep entry forward as though measuring it had already happened; `src/cadrumo/domain/calculations/registry/tests/test_audit_oracle_bindings.py,src/cadrumo/application/registry/tests/test_temporal_coverage.py`.
## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_audit_oracle_bindings.py`
- `src/cadrumo/application/registry/tests/test_temporal_coverage.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S99.md`
- `verify:` focused S96 candidate set -> `3 passed in 43.93s`
- `verify:` S98 exact M341 confirmation -> `1 passed in 56.79s`

## Notes

No historical literal receipt is recoverable. This record attests fresh supporting receipts only: M130 is a one-revision deliberate mutation, M038 is an adjacent-model negative control, and S97/S98 retain M341 as the confirmed positional-selection correction.
