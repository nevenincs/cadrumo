---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S18'
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
     The S18 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Implement the executor-level anti-tautology proof that executes one representative sequence twice and asserts the pre-mask differing paths equal the central mask set exactly and ## Scope

- `dev/docs/tests/test_sequence_goldens.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement the executor-level anti-tautology proof that executes one representative sequence twice and asserts the pre-mask differing paths equal the central mask set exactly

## Scope

- `dev/docs/tests/test_sequence_goldens.py`

## Description

- Prove residual determinism exactly: a representative capture-threaded JSON sequence executed twice in fresh hermetic sandboxes yields pre-mask differing paths pinned to the residual non-deterministic set — EMPTY on today's enrollable surface — so any new residual path, masked or not, is a named regression that must be consciously enrolled.
- Pin the masked-field canary: the centrally-masked surrogate keys (`snapshot_id`, `run_id`) appear on NO enrollable envelope today; a failure means an enrollable surface started emitting a masked field and the double-run proof must be extended to a sequence that genuinely exercises the flap before the assertion moves.
- Prove the mask bites exactly the declared set through the REAL compare path: a masked-field value flap injected into a real golden/live pair compares clean, while the identical flap under an undeclared key compares red with the key named.

## Outcome

The docs gate cannot silently rot into tautology from either direction: the mask cannot hide a real regression (claim 3b, plus claim 1's exact pin), and a masked-field flap cannot red the gate (claim 3a). The gate composes with the substrate's own anti-tautology proof, which exercises real live-capture envelopes carrying the masked fields.

## Notes

Honest deviation from the literal step text, agreed with the coordinator: the plan asked the double-run pre-mask diff to "equal the central mask set exactly", but every surface emitting `snapshot_id`/`run_id` is a live-AEAT read — unenrollable by design (ADR D6) — so strict equality against a non-empty mask is unreachable from any hermetic sequence. The gate instead pins the residual EXACTLY (empty), adds the canary that forces a genuinely-flapping proof the day a masked key reaches an enrollable envelope, and proves mask-bite/mask-narrowness through the real compare functions by mutating real envelope documents (the same technique as the store's deleted-field proof).
