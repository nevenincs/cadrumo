---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:eabe7ce991d502f40664f8cf4a11a3d64c85802e90fc3be00fd4895c2a749eda'
step_id: 'S13'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Implement JSON-frame comparison delegating to the observability primitives with exactly the central GOLDEN_MASK_FIELDS, refusing any per-sequence mask extension

## Scope

- `dev/docs/sequences/_compare.py`

## Description

- Implement `compare_transcript_to_golden` in `dev/docs/sequences/_compare.py`: an accumulating single-pass comparison that checks sequence identity, frame count, and per frame the kind, the argv as executed, the exit code, and the capture bindings before the output comparison.
- Compare JSON frames through the shared observability substrate — `mask_document` with its central-mask default plus `canonicalise` byte equality — and report the post-mask `differing_paths` list on divergence.
- Make the per-sequence mask refusal structural: no function on the comparison surface accepts a mask or fields parameter, so a caller cannot widen the mask even accidentally; the central set is the only mask that can ever apply.
- Lead every problem string with the page, sequence id, frame index, and argv locator the check CLI will surface verbatim.

## Outcome

A JSON-frame divergence reds with the exact post-mask paths that moved, and the one dishonesty lever the substrate decision names — mask widening at the call site — is impossible by construction rather than by convention.

## Notes

`check_transcript` (added in the sibling step) is the single function both future gate surfaces call, so neither re-implements comparison.

Review absorption (P04 review LOW): the original mask-centrality pin was weaker than its "structural" claim — the forbidden-parameter check was name-brittle, and the substrate's `mask_document` itself accepts a `fields=` kwarg, so an internal override inside the compare module would have widened the mask without touching any signature. Hardened to three declared tiers: a broadened mask-shaped-parameter signature gate, an AST gate asserting every `mask_document` call in the compare module is argument-free beyond the document, and the executor-level double-run proof; the module docstring now names the enforcement instead of overclaiming.
