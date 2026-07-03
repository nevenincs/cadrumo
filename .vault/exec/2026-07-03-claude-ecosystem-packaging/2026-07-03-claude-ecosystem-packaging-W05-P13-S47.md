---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S47'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace claude-ecosystem-packaging with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S47 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Record the verified support matrix (which clients run the local server vs skills-only) that the userdocs will state and ## Scope

- `docs/verification/support-matrix.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Record the verified support matrix (which clients run the local server vs skills-only) that the userdocs will state

## Scope

- `docs/verification/support-matrix.md`

## Description

- Author `docs/verification/support-matrix.md`: the measured — never aspirational — per-client capability matrix (marketplace install, runtime resolution, configure surface, local server spawn, full tool round-trip, permission gate) across Claude Code CLI, Claude Desktop, and Cowork, each row backed by the sibling install-proof documents.
- Record the launch-variant note (local wheel now, PyPI variant re-verify after first publish) and the explicit out-of-scope claims (claude.ai web not measured; the S46 golden itinerary is the remaining scenario measurement).
- Commit `d0694a9e66`.

## Outcome

- The userdocs have a single measured source of truth for what may be claimed per client.

## Notes

Executed inline by the coordinator. S46 (golden regularizar-atrasos itinerary through the installed plugin) remains the one open step and is tracked operator-gated together with the first publish.
