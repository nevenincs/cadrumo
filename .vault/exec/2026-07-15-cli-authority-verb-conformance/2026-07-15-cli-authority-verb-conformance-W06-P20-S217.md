---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S217'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S217 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Rebuild the feature index after all plan, execution, audit, ADR, research, and reference artifacts are final and ## Scope

- `.vault/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rebuild the feature index after all plan, execution, audit, ADR, research, and reference artifacts are final

## Scope

- `.vault/`

## Description

- Rebuild the feature index after the plan, execution, audit and decision
  artefacts reached their final shape.
- Stage only this feature's index, since the verb is tree-wide.

## Outcome

SATISFIED, with a scoping hazard handled rather than tripped.

The index verb regenerated every feature's index in the vault, not just this
one. Six index files changed as a result and only ONE belongs to this campaign;
the other five are peer campaigns' - conformance-cli, declaracion real-render
verification, M303 prorrata grounding, open-decisions-and-operator-gates, and a
newly-appearing registry-governance backlog. Only this feature's index was
staged. The rest are their owners' to land, and sweeping them into this
campaign's commit would attribute five campaigns' documentation state to a SHA
that has nothing to do with them.

This is the same shape as the API-stub scaffold verb, which is likewise
tree-wide and likewise emits artefacts for modules a campaign does not own. The
remedy is identical: run the verb, stage by name, and never `git add` the
directory.

Gates at HEAD `9161f3122cc9ff48e84bb6ab5a1dfb0e3084a8ae`:

- `uv run --no-sync vaultspec-core vault feature index` regenerated the vault's
  indexes; 6 changed, 1 staged.

## Notes

Recorded because the failure mode is silent. A tree-wide generator produces a
correct result for every feature, so nothing in its output signals that most of
it is not yours. The only tell is `git status`, read before staging rather than
after committing.
