---
name: cadrumo-resumen-anual
description: >-
  Life-situation itinerary for the annual window: when the year closes,
  derive the annual summaries and annual self-assessments the profile owes
  (resúmenes informativos over the year's quarterly filings, then the
  annual declaraciones) from the overview calendar, reconcile each against
  the four quarters the CLI already holds, and drive each through its
  owning per-modelo skill. Use when an annual presentation window is open.
  Never assumes which annual forms apply; derives them from the overview
  surface.
applies_when:
  temporal_trigger: annual_window
---

# Resumen anual (annual window)

Gating situation: a filing year has closed and its annual windows are
opening — first the January resúmenes (the annual summaries that fold the
year's quarterly self-assessments into annual totals with per-perceptor or
per-operación breakdowns), later the annual declaraciones themselves. The
defining property of this season is RECONCILIATION: an annual summary does
not compute a new result, it must agree with the four quarters already
filed, and the CLI computes and reconciles that agreement from the ledger
and the year's filing history. Your job is to sequence the season, relay
the CLI's reconciliation verdicts, and never let a divergence pass
silently.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports an active
  profile) with the profile facts declared.
- The year's four quarters are filed and reconciled — or their gaps are
  known. An unfiled quarter surfaces in the backlog; route it to
  `cadrumo-regularizar-atrasos` BEFORE preparing the annual summary that folds it
  in.

## Procedure

1. Derive the annual obligation set:
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>`
   bounded to the annual window. Relay each surfaced annual modelo and its
   deadline verbatim; treat `coverage_advised` lines as open questions.
2. Confirm any doubtful annual obligation explicitly:
   `aeat app overview explain <MODELO> --year <YEAR>` — read `verdict` and
   `rationale`. Whether an informativa applies (a threshold crossed, a
   category of operation present) is a registry-grounded verdict, never a
   from-memory judgement.
3. Complete the year's ledger first: hand off to `cadrumo-llevar-libro` and
   `cadrumo-clasificar` for any tail of the year still unclassified. Annual totals
   computed over an incomplete year under-declare silently.
4. Prepare the January resúmenes before the annual declaraciones, each via
   its owning per-modelo skill. The annual-summary skills reconcile annual
   totals against the year's quarterly filings — relay any divergence the
   CLI reports verbatim and STOP on it: a summary that disagrees with its
   quarters means either a quarter needs correcting (route to
   `cadrumo-rectificar-declaracion`) or the ledger changed after a quarter was
   filed; the taxpayer decides which path with the facts in front of them.
5. Then the annual declaraciones (the Renta and the IS season), each via
   its owning per-modelo skill, which fold in the year's pagos
   fraccionados and retenciones the CLI already tracks.
6. After each filing's local export, the taxpayer files in the AEAT portal
   and `cadrumo-reconciliar` pulls the official evidence, exactly as in any other
   season.

## Success assertions

- The annual obligation set was read from `aeat app overview calendar` and
  confirmed with `aeat app overview explain` where doubtful — never
  recited from memory.
- Every annual total shown was quoted from CLI output; every
  quarterly-vs-annual reconciliation verdict was relayed verbatim, and no
  divergence was passed over silently.
- Unfiled quarters were routed to `cadrumo-regularizar-atrasos` before any annual
  summary folding them in was prepared.
- Corrections to already-filed quarters were routed to
  `cadrumo-rectificar-declaracion`, never improvised inside an annual preparation.

## Hand off

Each annual filing follows its per-modelo skill's hand-off. The season
closes when the calendar's annual window shows every surfaced obligation
exported, filed by the taxpayer, and reconciled.
