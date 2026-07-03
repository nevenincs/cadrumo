---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S20'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-ports-inversion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S20 and 2026-07-02-arch-remediation-ports-inversion-plan placeholders are machine-filled by
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
     The Declare the domain-not-adapters layer contract exhaustively rather than by exception list now that the seam is at zero and ## Scope

- `.importlinter` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Declare the domain-not-adapters layer contract exhaustively rather than by exception list now that the seam is at zero

## Scope

- `.importlinter`

## Description

- Declare the `domain -> adapters` seam exhaustively rather than as a per-production-edge exception list in the broad layered contract.
- Add a first-class `[importlinter:contract:domain-not-adapters]` forbidden contract (sibling of `domain-not-application`): `source_modules = aeat.domain`, `forbidden_modules = aeat.adapters`, `allow_indirect_imports = true`, `unmatched_ignore_imports_alerting = error`.
- Pin the 53 sanctioned domain test-file roundtrip/anti-tautology edges individually as `ignore_imports`; production coupling is zero, so a new non-deferred production `domain -> adapters` import now fails this contract loudly.
- Correct the stale layered-contract comment that claimed the calculation/filing/verification sibling modules still hold lazy adapters imports (all migrated at HEAD).

## Outcome

Complete in commit `be5ca85b22`. `lint-imports --config .importlinter`: the new "Domain must not import adapters" contract is KEPT (all 53 test edges correctly ignored, zero production violation). This graduates the domain -> adapters seam from a buried exception list in the `layered` contract to its own enforced boundary, mirroring the S21 `domain-not-application` treatment. Opens the ADR's endgame: with this seam at zero, the only remaining sanctioned cross-layer holes are application -> adapters wiring and core resource loaders.

## Notes

The `layered` contract remains BROKEN — this is the pre-existing, separately ratchet-tracked application -> adapters wiring set, unchanged by this step and containing zero `domain -> adapters` violations. Committed with explicit pathspec verified before commit.
