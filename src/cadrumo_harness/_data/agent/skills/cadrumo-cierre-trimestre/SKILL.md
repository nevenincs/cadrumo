---
name: cadrumo-cierre-trimestre
description: >-
  Close a filing quarter: read which quarterly obligations are due from the
  overview agenda and calendar, bring the quarter's ledger to clean, and take each
  surfaced obligation through its modelo skill in deadline order. Use when a
  quarter has just ended or its presentation window is open.
applies_when:
  temporal_trigger: quarter_boundary
---

# Cierre de trimestre (quarter close)

Gating situation: a filing quarter has ended and its presentation window is open or
opening. The obligations due differ per taxpayer (quarterly IVA, IRPF pagos
fraccionados, retenciones - whichever the profile's facts make applicable) and per
quarter, so never recite a list from memory: read the window's obligations from the
overview and sequence them. Deadlines, period boundaries and the obligation set are
facts the tools return; your part is order, completeness and plain-language
explanation.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports a profile) with the
  profile facts declared.
- The closed quarter's source records (bank statements, invoices issued and
  received) are files in the conversation workspace. Ask the person for any that are
  missing.

## Procedure

1. Establish what this quarter requires. Both commands read local state and contact
   nobody. `aeat app overview agenda` (operation `overview.agenda`) shows what is due
   next; then `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>`
   (operation `overview.calendar`), bounded to the presentation window, gives the
   complete set with deadlines. Relay each obligation and its deadline date exactly
   as returned. A coverage advisory (the coverage report's `advised` entries; the
   command line prints `coverage_advised`) is an open question for the taxpayer,
   never a silent drop.
2. Confirm any doubtful modelo: `aeat app overview explain <MODELO> --year <YEAR>`
   (operation `overview.explain`); read `verdict` and `rationale`.
3. Close the quarter's books before any calculation: load `cadrumo-llevar-libro` to
   complete the quarter's imports, then `cadrumo-clasificar`. A quarterly filing
   computed from an incomplete quarter under-declares silently.
4. Take each surfaced obligation through its modelo skill (`cadrumo-preparar-modelo-303`,
   `cadrumo-preparar-modelo-130`, `cadrumo-preparar-modelo-111` and the others in the
   `cadrumo-preparar-modelo-<NUMBER>` family), earliest deadline first. Where several
   share a deadline, prepare the IVA and pagos-fraccionados self-assessments before
   the informativas, so any amount the taxpayer must pay is known with the most lead
   time.
5. Say honestly how much time is left. If the window is tight, say so with the date
   the overview returned. If a deadline has already passed, this is no longer a
   quarter close: load `cadrumo-regularizar-atrasos`, which covers past-due filings
   and recargos.
6. After each filing's local export, the person files in the AEAT portal and, once
   they say they have, `cadrumo-reconciliar` pulls the official evidence. Count the
   quarter as done only when every surfaced obligation is exported and its filing is
   reconciled, or is pending reconciliation with the person's knowledge.

## Success assertions

- The quarter's obligation set was read from `overview agenda` and `calendar`, not
  recited from memory or from a previous quarter.
- Deadline dates shown to the taxpayer are exactly the ones returned.
- The quarter's ledger was clean before the first calculation.
- Deadline order was kept, or the deviation was the taxpayer's explicit choice.
- Any already-missed deadline was sent to `cadrumo-regularizar-atrasos`, not
  prepared here as if still in window.

## Next

Each filing follows its modelo skill's steps. This skill is done when every
obligation the calendar surfaced for the quarter's window has been taken up and the
next `overview agenda` shows nothing further due for that quarter.
