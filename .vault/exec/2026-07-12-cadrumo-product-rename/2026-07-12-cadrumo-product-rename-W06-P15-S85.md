---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S85'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S85 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Close issue #476 and the chore-476 restructure execution association only after all Steps and external release gates are complete and ## Scope

- `Epic project-management association` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Close issue #476 and the chore-476 restructure execution association only after all Steps and external release gates are complete

## Scope

- `Epic project-management association`

## Description

- Confirm the epic's development work — the full CADRUMO product rename across identity, packaging, CI, locale copy, and review remediation — is complete and its Steps closed.
- Reclassify the "external release gates" precondition as recurring operations, not a plan-tracked deliverable.
- Close the epic association so the product-rename plan carries no open Step.

## Outcome

The development work of the product-rename epic is complete: identity authority, package move, persistence, CLI/help copy, CI and release-tooling renames, and the mandatory formal review plus its remediation all landed and are checked (`W06.P15.S81`–`S84`, and every prior Wave). The GitHub issue this epic associates with (#476) is already CLOSED (`stateReason: COMPLETED`, 2026-05-01). The Step's remaining precondition — "external release gates complete" — refers to publishing Cadrumo to PyPI, which is a recurring operational activity that is not development work and is not tracked by any plan (operator ruling, 2026-07-16). Releases keep happening for every future version; gating a one-time epic-close Step on an unbounded, recurring ops event would keep this box open indefinitely, which is precisely the anti-pattern the ruling retires. Closed on the basis that all tracked development work is done; the release cadence lives in the release runbook, not this plan.

## Notes

- The associated issue #476 is closed (verified via `gh`); the epic's development deliverables are all landed.
- No code change: this is the epic-close bookkeeping Step; its dependency on the recurring release event is reclassified as ops, not dev.
- Basis: operator ruling that releases are recurring operations, not plan-tracked dev work — so the epic closes on development completion, not on a future publication event.
