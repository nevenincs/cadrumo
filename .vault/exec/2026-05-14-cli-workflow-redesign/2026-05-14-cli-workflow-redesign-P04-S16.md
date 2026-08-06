---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:86dd10696ba6f7196ef8a8c8a4e2bc660fdc77ddc83e1414032983c335d513c9'
step_id: 'S16'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

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
