---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S26'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-setup-flow with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S26 and 2026-07-23-profile-setup-flow-plan placeholders are machine-filled by
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
     The Build the cotejo compare-select reconciliation of flow answers against the parsed G313 fact set with keep, adopt, and defer decisions and ## Scope

- `src/cadrumo/application/wizard/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Build the cotejo compare-select reconciliation of flow answers against the parsed G313 fact set with keep, adopt, and defer decisions

## Scope

- `src/cadrumo/application/wizard/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Build the cotejo compare-select reconciliation in `src/cadrumo/application/wizard/_cotejo.py`: an axis exists only where a certified censo fact's schema path matches a wizard question's profile key AND the staged answer genuinely disagrees under a canonical comparison fold (case, accent, and whitespace variants never spawn a false divergence page; the fold is a comparison key only — adopted and kept values persist verbatim).
- Emit one substrate compare-select page per axis with keep as the conservative default and the engine-supplied defer arm; adopted values carry the censo-artefact provenance token the registered-values suffix projection renders.
- Splice via `attach_cotejo_pages`, the same post-bridge decoration seam as the descendant group, threaded through the shared definition builder; today exactly one certified field maps to a wizard question, the rest stay display-only evidence per the accepted present-in-both rule.

## Outcome

Landed as `5c8524ea7d` with the revision `c253a117c2`. Two review passes: the first required revision (comparison normalization, a parameter-name collision); the re-review verified both closed with the misroute guarantee proven in both directions and the persisted-verbatim property pinned by test. The whole family is honestly dormant: the inbound parser refuses every document until a G313 specimen pins extraction, so tests drive a directly-constructed certificado through the real engine.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- This step's original commit swept a peer's uncommitted facade hunk in the wizard package init (an import for a module the sweep did not include), leaving one intermediate commit non-collecting until the peer's module landed — the second entangled-facade incident of the campaign, upgrading the trap to systemic; the revision commit held the tightened per-file-diff-plus-marker-grep discipline.
- The comparison fold duplicates the accent-strip shape of a private core helper with a divergent constraint (no whitespace collapse there); the substitutability pre-filter blocks promotion — revisit a shared public fold primitive if a third caller lands.
- End-to-end wiring of flow decisions through the outcome projection into the apply authority deliberately awaits the parser specimen; recorded as a ledger item, never assumed complete.
