---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S28'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-workflow-redesign with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S28 and 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan placeholders are machine-filled by
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
     The Add real service tests for create, validate, export, delivered-to-payer, and locally completed behavior and ## Scope

- `tests/application/modelo` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add real service tests for create, validate, export, delivered-to-payer, and locally completed behavior

## Scope

- `tests/application/modelo`

## Description

Add a real application-service flow test for Modelo 145 communication records.

Exercise create, validate, export, delivered-to-payer, and locally completed operations through the persisted bucket-local service runtime.

Verify the composed flow keeps the record in the expected lifecycle states and produces the registry-backed export payload without fake services or test-only shims.

## Outcome

`src/aeat/application/modelo/tests/test_m145_communication_service_flow.py` now covers the end-to-end backend service sequence using `isolated_runtime_profile` and application-facade imports.

Verification:

- `uv run --no-sync ruff format --check src\aeat\application\modelo\tests\test_m145_communication_service_flow.py`
- `uv run --no-sync ruff check src\aeat\application\modelo\tests\test_m145_communication_service_flow.py`
- `uv run --no-sync pytest src\aeat\application\modelo\tests\test_m145_communication_service_flow.py -q`
- `uv run --no-sync pytest src\aeat\application\modelo\tests\test_m145_communication_create.py src\aeat\application\modelo\tests\test_m145_communication_validate.py src\aeat\application\modelo\tests\test_m145_communication_export.py src\aeat\application\modelo\tests\test_m145_communication_transitions.py src\aeat\application\modelo\tests\test_m145_communication_service_flow.py -q`

## Notes

No blockers. No skipped gates. No fake, stub, monkeypatched, or compatibility test support was introduced.
