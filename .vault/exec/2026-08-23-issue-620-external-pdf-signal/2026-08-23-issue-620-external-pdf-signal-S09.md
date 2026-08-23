---
tags:
  - '#exec'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:ef13ec5ead193ede8845872e98715c2ca28dcc5e0e08270244cacc8ea96eaaf2'
step_id: 'S09'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---

# Correct Modelo 130 extraction-profile evidence claims and lock the operator advisory

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/extraction_profiles/`

## Description

Mark the Modelo 130 declaration extraction profile provisional until a populated external specimen proves value placement.

Remove the synthetic-fixture verification claim, lower confidence to review-required, and retain the measured geometry for blank-box safety.

Lock the provisional flag at the parser boundary and bind the reconciliation advisory to the committed registry profile.

Correct registry-gate test language so the committed generated fixtures are described as synthetic rather than real corpus evidence.

## Outcome

The Modelo 130 profile now declares `provisional_pending_specimen = true`, `corpus_round_trip_verified = false`, no verification source, and `review_required` confidence.

Focused parser, reconciliation, corpus-round-trip, provisional-specimen, and verification-source tests passed: 55 tests in 63.42 seconds. Focused Ruff checks passed for every changed Python test module.

The operator advisory is asserted against the committed profile identity and states that no real AEAT specimen confirms the printed layout, so extracted values require manual verification.

## Notes

The implementation was captured intact by concurrent shared-branch commit `c98f334880` together with unrelated peer work before this execution record was scaffolded. Shared history was preserved; this record identifies that commit transparently instead of rewriting it.

The external blank layouts prove physical box discovery and absence safety. They do not prove populated-value placement; that evidence limitation remains deliberate and visible.
