---
name: cadrumo-reconciliar
description: >-
  After the taxpayer files, pull the official AEAT justificante (or reconcile against
  a local artefact), compare it to the prepared declaration, and record the outcome.
  Use only after the human has filed in the AEAT portal.
applies_when:
  workflow_phase: reconciliation
---

# Reconcile a filed declaration

Official acceptance comes only from AEAT after the human files. Pull the evidence,
compare, and record - never assert acceptance from a local export.

## Preconditions

- The taxpayer has filed the declaration in the AEAT portal.

## Procedure

1. Pull the official justificante: `aeat app modelo reconcile pull`. If you only
   have a local artefact, reconcile against it:
   `aeat app modelo reconcile import --file JUSTIFICANTE.pdf`.
2. Compare the official evidence to the prepared revision. Report any divergence
   with its `legal_refs`/`source_refs`.
3. Review the audit trail: `aeat app modelo reconcile list`.

## Success assertions

- Acceptance is asserted only from official evidence (justificante / CSV cotejo /
  live capture), never from the local export.
- A divergence between the filed evidence and the prepared revision is surfaced as
  a finding, not silently reconciled.
- The reconciliation is recorded in the history.

## Outcome

The engagement's filing for the period is evidenced and the audit trail is
complete.
