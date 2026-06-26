---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S07'
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
     The S07 and 2026-06-26-binding-resolver-contract-unification-plan placeholders are machine-filled by
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
     The Enroll the profile and borrador resolvers into merge_source_resolutions with explicit mesh-merge precedence preserving the declared precedence ladder, applying the apply-cached-on-collision drive against the live peer WIP and ## Scope

- `src/aeat/application/modelo/_calculation_actions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Enroll the profile and borrador resolvers into merge_source_resolutions with explicit mesh-merge precedence preserving the declared precedence ladder, applying the apply-cached-on-collision drive against the live peer WIP

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Add `merge_source_resolutions_by_precedence` to the source mesh: a precedence OVERLAY (later tier wins on collision) distinct from the exclusive-claim `merge_source_resolutions`. It is the explicit mesh form of the historical `{**profile, **backend, **borrador, **caller}` dict-merge ladder.
- Enroll profile and borrador as first-class mesh resolution TIERS in `calculate_modelo_revision`: build the borrador tier and the profile tier (profile lowest, excluding every binding the caller / borrador / backend already supplied), wrap the backend mesh values and the caller values into resolution tiers, and overlay the four tiers (profile, backend, borrador, caller) through the precedence merge.
- Carry the borrador provenance from the merged resolution's typed `borrador_provenance`.

Modified files: `src/aeat/application/aggregation/_source_mesh.py`, `src/aeat/application/aggregation/__init__.py`, `src/aeat/application/modelo/_binding_resolution.py` (public tier builders), `src/aeat/application/modelo/_calculation_actions.py`.

## Outcome

Landed in the S07+S09 commit `5620ed7f5`. Profile and borrador are first-class mesh resolutions consumed through the precedence merge. The precedence ladder is byte-identical: tier overlay order reproduces the prior dict-merge exactly (backend contributes no enum tier, only profile carries date). The caller-above-borrador-above-backend precedence test plus the full-calc E2E suite stayed green with no casilla shift.

## Notes

`_calculation_actions.py` carries the live `_pre_mesh_handled` peer WIP; the S07 call-site rewrite was staged through the apply-cached own-only drive, verified zero foreign markers in the index, leaving the peer WIP intact in the working tree.
