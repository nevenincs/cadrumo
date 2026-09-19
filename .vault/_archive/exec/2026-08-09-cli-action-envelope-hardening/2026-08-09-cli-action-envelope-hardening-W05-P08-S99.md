---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:b375154c28a8e7892c4b909864c6353d6a5fc1ad93a11c9d9c7d8d56aa94626b'
step_id: 'S99'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate justificante exception action forwarding through cooperative MRO to the retired-error boundary and canonical typed actions

## Scope

- `src/cadrumo/domain/justificante/_errors.py`

## Description

- Audit the declared justificante error module for prose refusals and action forwarding.
- Establish whether a domain error may carry a typed precondition verdict at all.
- Record the adapter-layer raisers that remain outside this step's declared scope.

## Outcome

- The declared module carries no operator-facing prose refusal and needs no migration.
- Its shared extraction-coverage mixin already forwards message, context and translated message through cooperative MRO to the registered error boundary, which is the forwarding shape this step asks for.
- A typed precondition verdict cannot be added here, and this is the substantive finding rather than a limitation. The verdict type is owned by the application operator-actions package; no error anywhere in the domain layer carries one, and the justificante domain imports no application module. A domain error carrying a verdict would invert the accepted hexagonal direction, so the resolved action must stay resolved at the application and CLI boundary. The module's current shape is the only correct one for a domain error.
- Structural verification rather than behavioural: the scan is over the declared file, and the layering claim is established by the absence of any verdict-carrying domain error and the absence of application imports in this package.

## Notes

- The justificante refusals that still render prose live in the outbound sede fetch and adapter-utility modules and the inbound parser package. All three are adapter-layer and outside this step's single declared file; they are recorded here as carry-forward rather than absorbed, because widening the step would hide which surface was actually migrated.
- No code change was made. The step is closed as already satisfied, with the layering rationale recorded so a later reader does not re-open it expecting a verdict carrier that the architecture forbids.
