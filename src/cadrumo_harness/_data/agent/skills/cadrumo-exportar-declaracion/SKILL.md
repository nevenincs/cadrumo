---
name: cadrumo-exportar-declaracion
description: >-
  Verify a prepared modelo revision, export the local fichero-BOE artefact once
  the person agrees, and tell the person how to file it in the AEAT portal. Never
  submits anything to AEAT. Use when a modelo has been calculated and the person
  wants the file to file themselves.
applies_when:
  workflow_phase: export
---

# Export a declaration for the person to file

Cadrumo produces and verifies; the person files. Your part ends at a verified local
artefact and a clear explanation. Never describe any step here as filing,
submitting or presenting to AEAT.

## Preconditions

- A calculated revision exists for the work unit (its own `cadrumo-preparar-modelo-*`
  skill ran `work create` and `work calculate`).

## Procedure

1. Verify: `aeat app modelo work verify --work-unit-id <work-unit-id>` (operation
   `modelo.work.verify`; it only reads the stored revision). On the command line,
   exit `1` is a verdict, not a crash; with the tool server read the result.
   Relay every finding. Do not go on while it is blocked or incomplete. A clean
   verify informs the person's decision; it does not approve the export.
2. Report the clean result and any amount exactly as the tools returned it. Tell
   the person you are about to write the local file
   (`aeat app modelo export <work-unit-id> --output <PATH in the workspace>`,
   operation `modelo.export`). For Modelo 303 the export also takes a refund
   election (`--refund-election compensar|devolver`) and a payment election
   (`--payment-election ingreso|domiciliacion|cuenta_corriente`): these decide what
   happens to money, so ask the person which they want and say which default
   applies if they do not choose. Export only after the person gives the go-ahead
   in the conversation. The file is a fichero-BOE (XML for Modelo 100).
3. Explain that the local export is not official evidence and the return is not
   filed. The person uploads the file in the AEAT portal themselves.
4. Only after the person says they have filed, and asks you to, record that locally
   with `aeat app modelo work file --work-unit-id <work-unit-id>` (operation
   `modelo.work.file`). It records that they filed outside Cadrumo; it sends
   nothing and does not show AEAT accepted it. The go-ahead for the export does not
   cover this marker.

## Success assertions

- Verification was clean, or every finding was surfaced and the person accepted it,
  before export.
- The export and the marker each ran only after the person's go-ahead for that act.
- Nothing said calls the local export "filed", "submitted" or "accepted".
- Every amount stated comes verbatim from the verify or revision result.

## Next

After the person has filed, load `cadrumo-reconciliar` to fetch the official
evidence and compare it.
