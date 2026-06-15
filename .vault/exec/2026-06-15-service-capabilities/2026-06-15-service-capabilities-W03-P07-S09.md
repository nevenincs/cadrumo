---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S09'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace service-capabilities with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-06-15-service-capabilities-plan placeholders are machine-filled by
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
     The Capability extras + relocate torch and ## Scope

- `just doctor/provision recipes`
- `fix env-playwright`
- `reconcile README/justfile`
- `pyproject.toml`
- `justfile`
- `README.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Capability extras + relocate torch

## Scope

- `just doctor/provision recipes`
- `fix env-playwright`
- `reconcile README/justfile`
- `pyproject.toml`
- `justfile`
- `README.md`

## Description

Landed (committed):

- Add `just doctor` (runs `aeat config check`) and `just provision` (runs `env-playwright`) recipes; chain `just bootstrap` to end with `-just doctor` (commit `f926b41c8`).
- Fix the broken `env-playwright` recipe to `playwright install chromium` (was a dead `python -m aeat.entrypoints.cli.browser.health` reference) (commit `f926b41c8`).
- Reconcile `README.md` fresh-clone entry point to `just bootstrap` + `just doctor` (commit `5dc9e2a15`).
- Relocate torch out of `[project.dependencies]` to the dev group — split into its own step S13 (commit `93d903f30`).

Deferred (not attempted):

- The capability-extras lean-core migration (relocate google / playwright / anthropic out of `[project.dependencies]` into capability-mapped optional extras).

## Outcome

The provisioning/doctor/README/torch deliverables of this step are committed and green. The lean-core extras migration is deferred; the dependency-provisioning ADR §4 records the rationale. This step is left UNCHECKED because its named "capability extras" deliverable is an intentional carry-forward, per `plan-closure-requires-exec-records`.

## Notes

The lean-core extras migration requires converting several adapter import sites from eager to lazy import so the package installs and imports without the optional dependencies present — a breakage-risky refactor out of scope for this capability/provisioning campaign. It is a standalone follow-up; the close audit (S15) records the deferral.
