---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:39558ee7b10613518ab2de67bdcc726aa384e3b23d7c6c25f9411dc367f21c54'
step_id: 'S14'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---

# Extract exact existing oracle coordinate and payload mappings without adding unsupported claims

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/verification_expectations/0003-reconcile-when-present.toml`

## Description

- Confirmed the exact M100 2024, period `0A`, revision `2024` coordinate.
- Enrolled only `0513` and `0514` in the existing external-grounding declaration.
- Matched the Asturias and Rioja manual-oracle payloads one-to-one to both casillas.
- Retained the Valencian payload's `0513)-only evidence and deferred its `0514) and `6550) limitations.

## Outcome

The declaration now carries 61 grounded casillas. The worker reported 21 integration tests, 15 strict-payload tests, 90 revisions, 24 payloads, zero unattributed payloads, and zero grounding findings before the peer profile edit. No producer, payload, formula, relation, or focus-row semantic changed.

## Notes

A fresh full replay after the peer profile edit is blocked by the shared profile-schema validation error. Live AEAT capture and full repository tests were not run.
