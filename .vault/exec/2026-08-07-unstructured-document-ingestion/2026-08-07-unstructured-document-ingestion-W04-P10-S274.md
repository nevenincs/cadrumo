---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b233a6958db07b4924d0a9cf196f50ac12028d245cd965b479b59d62ddc3d0b2'
step_id: 'S274'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Build the scoring arm the harness lacks, since _runner.py does not read documents and Scored takes matched wrong and fabricated as caller-supplied integers with nothing anywhere comparing a model emitted fields against scorable_fields and fabrication_trap_fields to produce them - so fabrication on null-truth has a place to be recorded and no code that computes it - and the arm must prove it can return non-zero before any zero it reports counts as a measurement

## Scope

- `dev/ingest_harness`

## Description

- Add `dev/ingest_harness/_scoring.py`: `score_emission` decides one verdict per declared slot and is the only place a verdict is decided.
- Derive every slot from the corpus, never from an example: scorable slots come from `scorable_fields` and traps from `fabrication_trap_fields`, and no field name is enumerated in the module.
- Keep fabrication apart from a wrong answer end to end, through `FieldVerdict` and into `Scored` via `as_scored`.
- Treat an abstention spelling as silence rather than invention, through the named `ABSTENTION_SENTINELS` set.
- Report an emitted field the key declares nothing about beside the counts, never inside them.
- Carry field NAMES on verdicts and never emitted values, so the arm stays safe to point at evidence that is not the public corpus.
- Add `dev/ingest_harness/tests/test_scoring.py`: 23 cases driven from a recorded emission, so the arm has a gate that does not wait on a transport.

## Outcome

The harness could record `matched`, `wrong` and `fabricated` long before anything could compute them: `Scored` took all three as caller-supplied integers, so the failure mode the campaign exists to measure had a place to be written down and no code producing it. The arm closes that.

Three judgement calls decided the shape, each in the non-obvious direction:

Treating an emitted `""`, `"N/A"` or `"null"` as a value would have scored an abstention as a fabrication on every trap slot, making the abstaining model the worst offender and inverting the exact property the campaign measures. Abstention spellings are silence.

Calling an undeclared emitted field a fabrication would assert an absence the corpus never stated, so those are reported separately and never pooled into the counts.

Comparison is strict and derived from the truth value's own shape: a numeric truth compares in exact decimal at the document's own `tolerance_cents`, anything else compares whitespace-normalised and case-sensitive, a boolean never matches the integer one, and composites compare structurally. A comma-decimal against a dot-decimal truth scores wrong. That understates a reader that reads correctly and formats in the Spanish convention, and it is deliberate: the field-form contract pins form separately, so post-contract runs stay comparable. The strictness is asserted by its own case so it cannot soften unreviewed.

## Verification

    uv run --no-sync python -m pytest dev/ingest_harness/tests -p no:randomly -n 0 -m "unit or integration" -q
    68 passed in 6.42s

Each counter carries a proof it can be non-zero, and each proof was shown to fail under a mutation applied from outside the repository, so no tracked file carried a mutation window:

- scorer stuck at zero: the matched, wrong, fabricated and all-three proofs all red.
- fabrication relabelled as wrong: the fabrication and all-three proofs red, while matched and wrong stay green, which is correct since that mutation touches only trap slots.
- abstention sentinels removed: the abstention proof reds.

No proof survived every mutation, and the unmutated baseline is green throughout.

An anti-vacuity guard pins that the anchor document still carries 19 scorable fields and 10 traps, and a second case pins that both entries of the paired document carry truth and a trap. Without those, a corpus edit removing the traps would leave the fabrication proof passing while measuring nothing.

## Notes

The harness test suite crashes an xdist worker on this machine's backing share, reporting `INTERNALERROR` and `no tests ran` — which reads nothing like a failure. Sequential selection is required, and the marker lane must be named explicitly or the run selects nothing and exits green.
