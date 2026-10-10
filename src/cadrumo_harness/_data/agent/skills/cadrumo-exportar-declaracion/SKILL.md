---
name: cadrumo-exportar-declaracion
description: >-
  Verify a prepared modelo revision, export the local fichero-BOE artefact, and hand
  off for the taxpayer to file in the AEAT portal. Use after a modelo is calculated
  and before the human files. Never submits to AEAT.
applies_when:
  workflow_phase: export
---

# Export and hand off a declaration

The application produces and verifies; the human files. Your job ends at a verified
local artefact and a clear handoff. Never describe this as filing to AEAT.

## Preconditions

- A calculated modelo revision exists for the work unit.

## Procedure

1. Verify: `aeat app modelo work verify <work-unit-id> --format json`.
   Treat exit `1` as a verdict; relay every finding. Do not proceed on BLOCKED.
   A clean verify informs the person's decision; it does not approve the export.
2. When verified clean, report the result and ask the person to approve the export.
   Only after the person approves that exact act in Cadrumo, export the local
   artefact: `aeat app modelo export <work-unit-id>`. This produces a fichero-BOE
   file. An MCP elicitation answer, a client confirmation hint, or a CLI
   `--yes`/`--confirm` flag is not the person's approval.
3. Record that the human will file: the local export is NOT official evidence and
   the return is NOT filed. Tell the taxpayer to upload the file in the AEAT portal.
4. After the human files, optionally mark the local filing state with
   `aeat app modelo work file <work-unit-id>` to record that the person has filed
   outside the application, never to assert AEAT acceptance. Run it only after the
   person approves that exact act. Approval of the export does not cover the marker.

## Success assertions

- Verification is clean (or every finding is surfaced and accepted) before export.
- The export and the marker each ran only after the person approved that exact act.
- The narration never calls the local export "filed", "submitted", or "accepted".
- Any amount stated comes verbatim from the verify/revision JSON.

## Hand off

Once the human has filed, the reconciler (`cadrumo-reconciliar`) pulls the official
evidence.
