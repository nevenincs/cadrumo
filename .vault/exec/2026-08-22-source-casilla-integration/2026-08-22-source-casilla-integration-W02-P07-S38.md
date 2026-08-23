---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:088af70051d172e29b802d515b695593df3e5328448af0c44f493c2098caf050'
step_id: 'S38'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S38 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The enroll inventory selector validation in registry binding construction and ## Scope

- `src/cadrumo/domain/calculations/registry/_bindings.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# enroll inventory selector validation in registry binding construction

## Scope

- `src/cadrumo/domain/calculations/registry/_bindings.py`

## Description

- Import the canonical S37 inventory selector and validator into the registry binding aggregator.
- Enroll `BindingSourceKind.INVENTORY` atomically in the selector-model and validator dispatch registries.
- Export `InventorySelector` through the registry facade for later application consumers without exposing a private family module.
- Extend the exhaustive family build matrix with a valid inventory projection and a rival-casilla mutation.
- Prove binding construction hydrates the typed selector with exact activity identity and rejects operation-to-destination drift.
- Preserve the production inventory deferral for the later resolver-enrollment step.

## Outcome

Inventory is now a legal, strictly typed registry binding source at construction time and at the registry-build validation gate. Both canonical dispatch tables point to the single S37 selector contract; no selector or tax operation vocabulary was duplicated in the aggregator.

The public facade exposes the selector type needed by later cross-package source resolution while retaining the family module as its canonical definition. Production source disposition remains deferred: this step adds no resolver, registry binding, source readiness, or connected claim.

Focused verification passed: 93 registry construction, selector, build-validation, source-taxonomy, and source-disposition tests; scoped Ruff; scoped `ty`; and diff hygiene. Mandatory formal review reported zero critical, high, medium, or low findings after the S37 activity-identity remediation landed.

## Notes

The facade export is eager, consistent with the existing registry binding surface. The package's lazy export mechanism remains reserved for the oracle/browser tail. No unrelated shared-worktree changes were staged or modified.
