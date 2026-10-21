---
name: cadrumo-resumen-anual
description: >-
  Run the annual window: read from the overview calendar which annual summaries
  (resúmenes informativos over the year's quarterly filings) and annual declaraciones
  the profile owes, and route each to its per-modelo skill, stopping on any mismatch
  with the quarters. Use when the year has closed and an annual presentation window is
  open.
applies_when:
  temporal_trigger: annual_window
---

# Resumen anual (annual window)

Gating situation: a filing year has closed and its annual windows are opening - first
the January resúmenes (the annual summaries that fold the year's quarterly
self-assessments into annual totals with per-perceptor or per-operación breakdowns),
later the annual declaraciones themselves. The defining property of this season is
RECONCILIATION: an annual summary does not compute a new result, it must agree with the
four quarters already filed, and Cadrumo checks that agreement from the ledger and the
year's filing history when the annual summary is verified. Your job is to sequence the
season, relay those findings, and never let a divergence pass silently.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports an active profile) with
  the profile facts declared.
- The year's four quarters are filed and reconciled - or their gaps are known. An
  unfiled quarter surfaces in the backlog; load `cadrumo-regularizar-atrasos` BEFORE
  preparing the annual summary that folds it in.

## Procedure

The overview commands are local reads of the profile and registry; they never contact
AEAT. Through the tool server, `search` for the operation, `describe` it, run it with
`execute` and read the outcome with `result`. Say what you are about to read first.

1. Derive the annual obligation set:
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>` (operation
   `overview.calendar`), bounded to the annual window. Relay each surfaced annual modelo
   and its deadline as returned; treat `coverage_advised` entries as open questions.
2. Confirm any doubtful annual obligation: `aeat app overview explain <MODELO> --year
   <YEAR>` (`overview.explain`); read `verdict` and `rationale`. Whether an informativa
   applies (a threshold crossed, a category of operation present) is a registry-grounded
   verdict, never a from-memory judgement.
3. Complete the year's ledger first: load `cadrumo-llevar-libro` and
   `cadrumo-clasificar` for any tail of the year still unclassified. Annual totals
   computed over an incomplete year under-declare silently.
4. Prepare the January resúmenes before the annual declaraciones, each with its own
   skill (for example `cadrumo-preparar-modelo-190`, `cadrumo-preparar-modelo-390`,
   `cadrumo-preparar-modelo-180`). Those skills verify the annual totals against the
   year's quarterly filings. Relay any divergence or blocking finding as returned and
   STOP on it: a summary that disagrees with its quarters means either a quarter needs
   correcting (load `cadrumo-rectificar-declaracion`) or the ledger changed after a
   quarter was filed; the taxpayer decides which path with the facts in front of them.
5. Then the annual declaraciones (the Renta and the IS season), each with its own skill
   (for example `cadrumo-preparar-modelo-100`, `cadrumo-preparar-modelo-200`), which
   fold in the year's pagos fraccionados and retenciones that Cadrumo already tracks.
6. After each filing's local export (made only with the person's go-ahead), the
   taxpayer files in the AEAT portal and `cadrumo-reconciliar` pulls the official
   evidence, exactly as in any other season.

## Success assertions

- The annual obligation set was read from `overview.calendar` and confirmed with
  `overview.explain` where doubtful - never recited from memory.
- Every annual total shown was quoted from tool output; every quarterly-versus-annual
  finding was relayed as returned, and no divergence was passed over silently.
- Unfiled quarters were routed to `cadrumo-regularizar-atrasos` before any annual
  summary folding them in was prepared.
- Corrections to already-filed quarters were routed to `cadrumo-rectificar-declaracion`,
  never improvised inside an annual preparation.

## Finish

Each annual filing follows its per-modelo skill through verify, export, the taxpayer's
own filing and reconciliation. The season closes when the calendar's annual window
shows every surfaced obligation exported, filed by the taxpayer and reconciled.
