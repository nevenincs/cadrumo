---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S21'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Bring the borrador and n26 fixture corpora under the provenance discipline, since neither carries sidecars nor gate coverage and their generators do not set the producer signature the gate's discriminator depends on

## Scope

- `src/cadrumo/tests/fixtures/borrador`
- `src/cadrumo/domain/calculations/registry/tests`

## Description

- Measure what each corpus declares and what its committed bytes carry.
- Give the borrador and n26 writers a provenance sidecar emitted alongside every PDF.
- Add the gate over both corpora, enumerating by directory glob rather than a file list.
- Prove the gate discriminates, by driving its checker over each way a declaration can lie.

## Outcome

Both corpora are now declared and gated, and the declaration is written by the generator that produces the bytes rather than maintained beside them.

Neither corpus carried a sidecar and neither was covered by any gate. The n26 directory did carry expected-value files, but those are parser expectations and are a JSON list, so nothing there ever declared provenance. Six PDFs across the two corpora were undeclared.

The sidecars are emitted by the generators, so a regenerated fixture cannot drift from its own description. They resolve as a `.json` file beside the PDF, the same rule the justificante gate already uses, so the two gates read sidecars the same way rather than inventing a second convention.

The gate enumerates by directory glob. A fixture added later without a sidecar fails rather than passing unnoticed, which is the failure mode a committed file list would have reintroduced. It also asserts each corpus is non-empty, because a glob over an emptied directory yields zero cases and reports green while checking nothing.

The discriminating logic is factored out of the assertions so it can be driven over deliberately-corrupt inputs. Five cases cover each way a declaration can lie, including the two shapes actually present in the tree before this work, and a sixth asserts a truthful pairing is not flagged. Without that sixth, a checker that always reported a mismatch would satisfy all five.

The sidecar deliberately does not copy the producer into itself. The sidecar carries the claim and the PDF carries the evidence; recording the evidence inside the claim invites a reader to trust the claim in place of the cross-check, which is the structure the governing rule exists to prevent.

## Notes

The gate was confirmed to bite against the committed corpus, not only against synthetic probes: flipping one n26 sidecar to the real-corpus value failed the run naming that file, and the sidecar was restored.

Scope note. The Step names the borrador corpus, but n26 shares the identical defect and the same generator-level cause, so gating one and leaving the other would have left half the finding open. Both are covered.

One thing this does not do. The gate answers whether a fixture is honestly labelled, not whether it is free of real identity. Those are different questions, and this campaign's own record is emphatic that a manifest cannot report what a pipeline failed to notice. Nothing here reads the bytes for identity patterns, and this should not be mistaken for that check.
