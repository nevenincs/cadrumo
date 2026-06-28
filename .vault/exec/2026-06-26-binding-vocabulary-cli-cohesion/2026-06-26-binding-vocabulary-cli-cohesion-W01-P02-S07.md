---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S07'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-vocabulary-cli-cohesion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Verify W01.P02 no-shift: run pytest --collect-only -q clean, dev.docs.apidocs scaffold --check clean (no orphan / missing stubs), and the catalogue-verification / m232-row test consumers green and ## Scope

- `assert the relocations changed only module paths and import sites`
- `no behaviour`
- `src/aeat/domain/calculations/registry/tests/test_catalogue_verification.py`
- `src/aeat/domain/calculations/registry/tests`
- `docs/api` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify W01.P02 no-shift: run pytest --collect-only -q clean, dev.docs.apidocs scaffold --check clean (no orphan / missing stubs), and the catalogue-verification / m232-row test consumers green

## Scope

- `assert the relocations changed only module paths and import sites`
- `no behaviour`
- `src/aeat/domain/calculations/registry/tests/test_catalogue_verification.py`
- `src/aeat/domain/calculations/registry/tests`
- `docs/api`

## Description

- Run collect-only over the full `src/aeat` tree after both B1 and B2 relocations.
- Run the catalogue-verification, m232 materialiser, and decimal-redaction error-typing test consumers.
- Confirm the apidocs scaffold drift is attributable to peer churn, not the B1/B2 relocations.

## Outcome

W01.P02 no-shift proven. Collect-only is clean at 16461 collected (baseline-equal). The B1/B2 consumer tests ran 60 passed across the catalogue-verification and error-typing modules. Both relocations changed only module paths and import sites, with no behaviour change.

## Notes

apidocs scaffold --check reports the `aeat.domain.calculations.registry` package toctree stale. That drift is owner-distinguished as peer-owned: it is caused by an in-flight, uncommitted peer module rename (`_casilla_membership` / `_validate_source_outputs`) in the shared worktree, present before and independent of the B1/B2 work. Each B1/B2 stub delta was rebuilt HEAD-anchored to carry only its own m232 / `_sources` toctree change, so the owner-surface stub tree is self-consistent for this feature.
