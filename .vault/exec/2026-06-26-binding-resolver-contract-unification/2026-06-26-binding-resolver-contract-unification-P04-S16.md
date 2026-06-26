---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S16'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-resolver-contract-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S16 and 2026-06-26-binding-resolver-contract-unification-plan placeholders are machine-filled by
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
     The Re-base the merge_source_resolutions enrollment and the DEFERRED_SOURCE_KINDS set onto the one disposition mapping so a member's resolution state is declared once, re-reading HEAD because r2 #28 moves the withholding source from DEFERRED_SOURCE_KINDS to live enrollment on this surface, applying the apply-cached-on-collision drive against the concurrent r2 and codex WIP and ## Scope

- `src/aeat/application/aggregation/_source_mesh.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-base the merge_source_resolutions enrollment and the DEFERRED_SOURCE_KINDS set onto the one disposition mapping so a member's resolution state is declared once, re-reading HEAD because r2 #28 moves the withholding source from DEFERRED_SOURCE_KINDS to live enrollment on this surface, applying the apply-cached-on-collision drive against the concurrent r2 and codex WIP

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Re-base the enrollment in `_calculation_actions` onto the one disposition registry: declare the live enrolled set once as `_ENROLLED_SOURCE_KINDS`, build `_BINDING_SOURCE_DISPOSITIONS` from it, and DERIVE `_BUCKET_AGGREGATION_OWNED_SOURCES` as the ENROLLED partition (a comprehension over the registry) rather than a second hand-listed frozenset.
- The novel-source boundary gate and the caller-override guard now consume the derived owned set, so a member's resolution state is declared exactly once.

Modified files: `src/aeat/application/modelo/_calculation_actions.py`.

## Outcome

Landed in the P04 commit `9e59719a9`. The owned-source set is a derived view of the single disposition mapping; `DEFERRED_SOURCE_KINDS` stays the canonical deferred set the registry reads. No casilla shift - the novel-source gate, the caller-override guard, and the full-calc E2E suite green.

## Notes

`_calculation_actions.py` carries the live `_pre_mesh_handled` peer WIP; the S16 disposition-registry hunks were landed through the apply-cached own-only drive, verified zero foreign markers in the index, leaving the peer WIP intact. r2's #28 withholding source is already enrolled at HEAD, so it carries the `enrolled` disposition automatically with no hard-coding.
