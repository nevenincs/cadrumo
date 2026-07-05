---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S16'
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
     The S16 and 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan placeholders are machine-filled by
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
     The Add backend service ownership for Modelo 145 local payer communication and ## Scope

- `src/aeat/application/modelo` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add backend service ownership for Modelo 145 local payer communication

## Scope

- `src/aeat/application/modelo`

## Description

- Add `M145CommunicationServiceContract` as the immutable backend ownership contract for the local Modelo 145 payer communication surface.
- Build the contract from the shipped Modelo 145 registry snapshot for the `comunicacion` period so service ownership follows the already-approved registry vocabulary.
- Export the contract builder and closed action vocabulary through the `aeat.application.modelo` facade.
- Add application tests proving the service is backend-owned, registry-backed, and free of filing, deadline, live-read, portal, submit, receipt, and amendment vocabulary.

## Outcome

- `build_m145_communication_service_contract()` now publishes the application/modelo service owner, local communication period token, registry revision id, communication surfaces, export layout id, legal references, source references, and the closed create/validate/export/payer-delivery/local-completion action vocabulary.
- The builder refuses registry drift into filing-like surfaces before later behavior steps attach create, validate, export, transition, event, and log behavior.
- Verification passed:
  - `uv run --no-sync ruff check src/aeat/application/modelo/_m145_communication.py src/aeat/application/modelo/tests/test_m145_communication_service_contract.py src/aeat/application/modelo/__init__.py`
  - `uv run --no-sync pytest -q -n 0 src/aeat/application/modelo/tests/test_m145_communication_service_contract.py src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py --tb=short`

## Notes

- This step intentionally stops at backend service ownership. It does not create, persist, validate, export, transition, or expose CLI behavior; those remain assigned to the later open steps in the plan.
- The shared worktree already contained unrelated peer WIP before this step, including CLI workflow exec/reference files and registry/runtime changes. None of that WIP was edited or staged by this step.
