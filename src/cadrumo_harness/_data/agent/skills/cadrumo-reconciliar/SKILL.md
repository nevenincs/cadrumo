---
name: cadrumo-reconciliar
description: >-
  After the taxpayer has filed in the AEAT portal, fetch the official justificante (or
  compare a PDF you were given), compare it with the prepared declaration, and report
  every difference. Use when the person says they have filed the declaration, and
  never before.
applies_when:
  workflow_phase: reconciliation
---

# Reconcile a filed declaration

Official acceptance comes only from AEAT after the person files. Pull the evidence,
compare, and report - never assert acceptance from a local export or from the
filed marker.

## Preconditions

- The taxpayer has filed the declaration in the AEAT portal and has told you so.
- You know the declaration: its `work_unit_id`, or its modelo, year and period.

## Procedure

1. Choose the evidence source and tell the person what it does before you run it.
   - From AEAT: `aeat app modelo reconcile pull <work_unit_id>` (or `--modelo`,
     `--year` and `--period`). It downloads the justificante from AEAT (`--source
     justificante`, the default) or the filed declaration (`--source declaration`)
     and compares it with the saved calculation. It only reads from AEAT. Through the
     tool server it is the operation `modelo.reconcile.pull`. It needs AEAT read
     access, which the person sets up in Cadrumo; if the call is refused for lack of
     it, report the refusal and its remedy, and stop that step.
   - From a PDF the person holds: put it in the conversation workspace, then
     `aeat app modelo reconcile import <work_unit_id> --file <PDF>` (`--kind
     justificante`, the default, or `declaration`). It reads the file locally and
     contacts no one. Operation `modelo.reconcile.import`.
2. Read the result. `verdict` is `matches` or `mismatches`; `source_kind` says which
   evidence was compared; each entry in `diffs` carries `field_name`,
   `work_unit_value`, `evidence_value`, `diff_kind` and, where the registry grounds
   it, `legal_refs` and `source_refs`. Read `notices` too. Quote all of these as
   returned. Report every difference with its refs; do not reconcile one away.
3. Review earlier comparisons if asked: `aeat app modelo reconcile list`
   (`modelo.reconcile.list`), optionally with `--work-unit-id`.

## Success assertions

- Acceptance is asserted only from official evidence (justificante, filed
  declaration), never from the local export.
- A difference between the evidence and the prepared revision is surfaced as a
  finding with its `legal_refs` and `source_refs`, not silently reconciled.
- The comparison is recorded; `reconcile list` shows it.

## Finish

The filing for the period is evidenced and the audit trail is complete, or the
differences are in front of the person to decide what follows.
