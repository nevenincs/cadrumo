---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S30'
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
     The S30 and 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan placeholders are machine-filled by
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
     The Add negative tests proving Modelo 145 has no filing, deadline, live-read, portal, submit, receipt, or AEAT electronic tramite surface and ## Scope

- `tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add negative tests proving Modelo 145 has no filing, deadline, live-read, portal, submit, receipt, or AEAT electronic tramite surface

## Scope

- `tests`

## Description

Extend Modelo 145 registry foundation tests with the full forbidden filing-like surface set named by the step.

Add CLI command-namespace negative tests proving the `m145` subgroup does not expose forbidden filing, deadline, live-read, portal, submit, receipt, or AEAT electronic tramite verbs.

Keep the assertions negative and behavior-free: the tests verify absence of forbidden surfaces without adding new command handlers, aliases, or registry conventions.

## Outcome

`src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py` now rejects the full forbidden surface vocabulary in Modelo 145 application links.

`src/aeat/entrypoints/cli/tests/test_m145_communication_cli.py` now parameterizes forbidden command surfaces and confirms Typer rejects each under `app modelo m145`.

Verification:

- `uv run --no-sync ruff format --check src\aeat\domain\calculations\registry\tests\test_modelo_145_registry_foundation.py src\aeat\entrypoints\cli\tests\test_m145_communication_cli.py`
- `uv run --no-sync ruff check src\aeat\domain\calculations\registry\tests\test_modelo_145_registry_foundation.py src\aeat\entrypoints\cli\tests\test_m145_communication_cli.py`
- `uv run --no-sync pytest src\aeat\domain\calculations\registry\tests\test_modelo_145_registry_foundation.py -q`
- `uv run --no-sync pytest src\aeat\entrypoints\cli\tests\test_m145_communication_cli.py -m integration -q`

## Notes

No blockers. No production behavior or registry data changed.
