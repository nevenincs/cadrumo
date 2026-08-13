---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:f79fb0ee12dcf9541887b999e3f554cc2293a70ea9f19824ff4a9b76d3da676a'
step_id: 'S34'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Render overview text and JSON from one typed action projection

## Scope

- `src/cadrumo/entrypoints/cli/_overview.py`
- Co-scoped transport: `src/cadrumo/entrypoints/cli/_overview_payloads.py`

## Description

- Replace the two separate status calls - one building text lines, one building notices - with a single projection returning both from one pass over the application next-step producer.
- Replace the prepare and pipeline payload rows' next-command strings with the schema-resolved action the renderer already resolved for the notice.
- Remove the remedy from the calendar warning payload row entirely.
- Update the owned CLI verb tests onto the typed contract.

## Outcome

The status verb previously called a line renderer and a notice builder separately, and each derived the guidance independently. It now makes one call whose two return values are built from the same resolved objects, so neither can be changed without the other.

The prepare and pipeline payload rows carry the resolved action rather than a command string. This follows the config-check precedent from the paired provisioning cutover, where the resolved precondition action rides in the result payload beside the notice channel; the object in the row is the same object the notice carries, resolved once.

The calendar warning payload lost its remedy field rather than gaining a typed one. The envelope contract already names `fix_command` a reserved action side channel that cannot appear inside a result, and the warning now reaches the operator as a notice carrying the resolved remedy. Restating it in the payload would have been a second copy of operator guidance in the shape the contract reserves for the notice channel. The producer-side declaration is therefore excluded from serialization.

CLI JSON schema conformance: 332 passed.

## Notes

- `_overview_payloads.py` is not named in the Step row. The payload rows are the transport half of the rendering change and could not stay on retired fields; they are recorded here rather than left implied.
- One conformance test and nine prepare/pipeline verb tests fail in fixture setup, before any overview code runs, because a peer added a newly required profile flag that the shared profile-creation test helper does not pass. The same helper fails identically in unrelated modelo test modules, so the breakage is tree-wide and peer-owned rather than a regression from this Step.
