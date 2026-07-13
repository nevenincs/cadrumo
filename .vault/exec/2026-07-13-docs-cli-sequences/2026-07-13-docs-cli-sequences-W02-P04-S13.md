---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S13'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-cli-sequences with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S13 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Implement JSON-frame comparison delegating to the observability primitives with exactly the central GOLDEN_MASK_FIELDS, refusing any per-sequence mask extension and ## Scope

- `dev/docs/sequences/_compare.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
