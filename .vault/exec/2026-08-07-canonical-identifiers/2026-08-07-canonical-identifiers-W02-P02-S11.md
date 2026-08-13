---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:9c8a41efd4aa3f4c30708b5ee99100f5a09c70be3ec66efef6d35eeda9ee1124'
step_id: 'S11'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-identifiers with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-08-07-canonical-identifiers-plan placeholders are machine-filled by
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
     The retype `ExpedienteDeclarationPayload.expediente_id` from unconstrained bare `str` onto `AeatExpedienteId`, closing the fourth (loosest) divergence sighted on the operator-facing wire contract and ## Scope

- `src/cadrumo/entrypoints/cli/_app_live_payloads.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# retype `ExpedienteDeclarationPayload.expediente_id` from unconstrained bare `str` onto `AeatExpedienteId`, closing the fourth (loosest) divergence sighted on the operator-facing wire contract

## Scope

- `src/cadrumo/entrypoints/cli/_app_live_payloads.py`

## Description

- Replaced the unconstrained declaration-row `expediente_id` with `AeatExpedienteId`.
- Imported the alias from the public `core.identity` facade, its sole canonical cross-package path.

## Outcome

The `app.live.expedientes.view` declaration rows now advertise and enforce the
same observed AEAT expediente constraint as their canonical model source. The
wire value remains a JSON string; only the schema validation and advertised
JSON Schema constraints are tightened.
## Notes

Formal review found no issues. Focused checks passed: canonical identity validation (21 tests), direct valid
and invalid payload construction, Ruff format and lint, Ty, and diff whitespace.

The wider schema-conformance lane is red outside this Step: 332 tests passed
and `test_profile_bound_command_populates_active_profile_label` refuses a
missing `--tax-residence-jurisdiction-scope` precondition. The focused
live-read subgroup lane independently has 33 passes and one stale inventory
failure for the unrelated `deudas` subgroup. Neither failure names this payload
or its identifier constraint.
