---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S33'
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
     The S33 and 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan placeholders are machine-filled by
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
     The Run the targeted registry, application, and CLI test slices without skips, xfails, mocks, stubs, or tautological assertions and ## Scope

- `tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the targeted registry, application, and CLI test slices without skips, xfails, mocks, stubs, or tautological assertions

## Scope

- `tests`

## Description

Run the targeted registry, application, parser/rendering, and CLI integration slices that cover the completed Modelo 145 successor work.

Keep marker handling explicit so integration tests are not silently filtered by the default pytest selection.

Confirm the gate output contains no skips, xfails, mocks, stubs, or tautological shortcut evidence.

## Outcome

Targeted verification passed:

- `uv run --no-sync pytest src\aeat\domain\calculations\registry\tests\test_modelo_145_registry_foundation.py src\aeat\domain\calculations\registry\tests\test_censo_modelo_foundation.py src\aeat\domain\calculations\registry\tests\test_censo_modelo_registry_data.py src\aeat\application\modelo\tests\test_m145_communication_service_contract.py src\aeat\application\modelo\tests\test_m145_communication_create.py src\aeat\application\modelo\tests\test_m145_communication_validate.py src\aeat\application\modelo\tests\test_m145_communication_export.py src\aeat\application\modelo\tests\test_m145_communication_transitions.py src\aeat\application\modelo\tests\test_m145_communication_events.py src\aeat\application\modelo\tests\test_m145_communication_errors.py src\aeat\application\modelo\tests\test_m145_communication_service_flow.py -q`
  - `74 passed`
- `uv run --no-sync pytest src\aeat\entrypoints\cli\tests\test_m145_communication_parsing.py src\aeat\entrypoints\cli\tests\test_m145_communication_rendering.py -q`
  - `7 passed`
- `uv run --no-sync pytest src\aeat\entrypoints\cli\tests\test_m145_communication_cli.py src\aeat\entrypoints\cli\tests\test_backend_boundary.py::test_modelo_145_shims_stubs_and_compatibility_aliases_stay_absent -m integration -q`
  - `31 passed`

## Notes

No blockers. No tests were skipped or xfailed in the targeted output. No code changes were required for this gate step.
