---
name: cadrumo-cierre-trimestre
description: >-
  Life-situation itinerary for the quarter boundary: when a filing quarter
  closes, derive exactly which quarterly obligations are due from the
  overview agenda and calendar, bring the ledger for the closed quarter to
  clean, and drive each surfaced obligation through its owning per-modelo
  skill inside the presentation window. Use when a quarter has just ended
  or its presentation window is open. Never assumes the obligation set;
  derives it per quarter from the overview surface.
applies_when:
  temporal_trigger: quarter_boundary
---

# Cierre de trimestre (quarter close)

Gating situation: a filing quarter has ended and its presentation window is
open or opening. The obligations due at a quarter close differ per taxpayer
(quarterly IVA, IRPF pagos fraccionados, retenciones — whichever the
profile's facts make applicable) and per quarter, so this itinerary never
recites a list from memory: it reads the window's obligations from the CLI
and sequences them. The deadline dates, the period boundaries, and the
obligation set are all deterministic-layer facts; your job is order,
completeness, and plain-language narration.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports an active
  profile) with the profile facts declared.
- The closed quarter's source records (bank statements, invoices issued and
  received) are available.

## Procedure

1. Establish what this quarter close requires: `aeat app overview agenda`
   for what is next due, then
   `aeat app overview calendar --from <PERIOD-START> --to <PERIOD-END>`
   bounded to the presentation window, for the complete set with deadlines.
   Relay each surfaced obligation and its deadline date verbatim. A
   `coverage_advised` line is an open question for the taxpayer, never a
   silent drop.
2. Confirm applicability of any doubtful modelo explicitly:
   `aeat app overview explain <MODELO> --year <YEAR>` — read `verdict` and
   `rationale`.
3. Close the quarter's books BEFORE any calculation: hand off to
   `cadrumo-llevar-libro` to complete the quarter's imports, then `cadrumo-clasificar` for
   classification and apportionment. A quarterly filing computed from an
   incomplete quarter under-declares silently.
4. Drive each surfaced obligation through its owning per-modelo skill
   (`cadrumo-preparar-modelo-303`, `cadrumo-preparar-modelo-130`, `cadrumo-preparar-modelo-111`,
   and siblings), in deadline order — earliest deadline first. Where several
   share a deadline, prepare the IVA and pagos-fraccionados
   self-assessments before informativas, so any resultado the taxpayer must
   pay is known with the most lead time.
5. Surface deadline pressure honestly. If the window is already tight, say
   so with the CLI's own deadline date; if a deadline has already passed,
   this is no longer a quarter close — route to `cadrumo-regularizar-atrasos`,
   which owns the past-due and recargo path.
6. After each filing's local export, the taxpayer files in the AEAT portal
   and `cadrumo-reconciliar` pulls the official evidence. Track the quarter as done
   only when every surfaced obligation is exported and its filing
   reconciled or pending-reconciliation with the taxpayer's knowledge.

## Success assertions

- The quarter's obligation set was read from `aeat app overview agenda` /
  `calendar`, never recited from memory or a previous quarter.
- Deadline dates shown to the taxpayer are verbatim CLI output.
- The ledger for the closed quarter was clean before the first calculate.
- Deadline-ordered sequencing was kept, or the deviation was the
  taxpayer's explicit choice.
- Any already-missed deadline was routed to `cadrumo-regularizar-atrasos`, not
  silently prepared here as if in-window.

## Hand off

Each filing follows its per-modelo skill's hand-off. This itinerary closes
when every obligation the calendar surfaced for the quarter's window is
routed, and the next agenda read shows nothing further due for that
quarter.
