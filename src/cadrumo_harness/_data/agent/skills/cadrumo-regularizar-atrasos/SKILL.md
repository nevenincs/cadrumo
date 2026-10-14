---
name: cadrumo-regularizar-atrasos
description: >-
  Catch up a taxpayer who is behind on filings: list the past-due obligations oldest
  first from the overview backlog, relay the recargo extemporáneo preview exactly as
  Cadrumo shows it (LGT art. 27), and route each overdue modelo to its per-modelo
  skill. Use when `aeat app overview backlog` reports past-due obligations.
applies_when:
  temporal_trigger: backlog_overdue
---

# Regularizar atrasos (behind on obligations)

Gating situation: the taxpayer has missed one or more filing deadlines. Cadrumo
already derives what is overdue, by how many days, and which recargo band of LGT
art. 27 applies; this skill sequences that and points each catch-up filing to the
per-modelo skill that owns it. Two hard rules frame everything here. First, every
recargo and days-overdue figure is quoted verbatim from tool output - never computed,
extrapolated or "estimated" by you; the surcharge regime is law the deterministic layer
owns. Second, regularización here is the voluntary, before-requerimiento path that
art. 27 covers: if the taxpayer has already received an AEAT requerimiento or
notification for the missed filing, stop and tell them to consult a human
professional - the applicable regime is then outside this skill's scope, and saying so
plainly is the honest answer.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports an active profile) and
  the profile facts are declared. An undeclared taxpayer model makes the backlog empty
  and the result says so (`taxpayer_model_declared` false, with `incomplete_reason`);
  do not read an empty backlog as "nothing is overdue" in that case.
- The taxpayer has NOT received an AEAT requerimiento for the missed obligations (see
  the framing rule above).
- The source records (bank statements, invoices) for the overdue periods are
  available, or the taxpayer knows where to get them.

## Procedure

The overview commands are local reads of the profile and registry; they never contact
AEAT. Through the tool server, `search` for the operation, `describe` it, run it with
`execute` and read the outcome with `result`. Say what you are about to read first.

1. Surface the backlog: `aeat app overview backlog` (operation `overview.backlog`). It
   is answerable for a behind-but-fresh taxpayer who has never filed and has no work
   units yet - the backlog is derived from the profile's obligation applicability and
   the deadline schedule, not from any saved work. Read `late_count` and `items`, which
   arrive oldest first; each item carries `days_overdue` and, in `recovery`,
   `still_filable` and the `recargo_band` (`surcharge_pct`, `interest_applies`,
   `legal_ref`). Bound the range with `--from` and `--to` only when the taxpayer asks
   about a specific stretch. Relay any warning or `coverage_advised` entry as an open
   question to the taxpayer - an advised obligation is unresolved, not inapplicable. If
   a `work_units_degraded` notice appears, the saved work could not be loaded; the
   backlog is still valid (schedule-derived) but may report a draft in progress as
   still due - note it and continue.
2. When the applicability of a surfaced modelo is in doubt, confirm it:
   `aeat app overview explain <MODELO> --year <YEAR>` (`overview.explain`). Read
   `verdict` and `rationale`; never assume from memory whether an obligation applies.
3. Keep the oldest-first order. The recargo grows with elapsed months and changes
   character at twelve months (interest is added on top), so the oldest item is almost
   always the most urgent. If the taxpayer wants a different order, put that trade-off
   in plain language and let them decide.
4. Before any calculation, bring the ledger for each overdue period to clean: load
   `cadrumo-llevar-libro` and then `cadrumo-clasificar`, scoped to that period. A
   catch-up filing computed from an incomplete ledger under-declares silently - the one
   outcome this whole system exists to prevent.
5. Prepare each overdue obligation with its own skill (`cadrumo-preparar-modelo-303`,
   `cadrumo-preparar-modelo-130` and the other `cadrumo-preparar-modelo-*` skills). The
   work unit's deadline output (for example from `aeat app modelo work calculate`)
   carries `days_overdue`, and when a band is known a `conditional_recargo_preview`
   (`band_id`, `surcharge_pct`, `interest_applies`, `legal_ref`, `assessment_status`
   `unassessed`), plus a plazo-vencido warning notice. Relay those and the notice to the
   taxpayer exactly as returned, with the legal basis it cites (LGT art. 27). Never
   suppress the warning and never restate the percentage from memory.
6. Distinguish missing from wrong. This skill covers obligations that were never filed.
   If a surfaced problem is instead a filed declaration that needs correcting, load
   `cadrumo-rectificar-declaracion` (the complementaria, sustitutiva or rectificativa
   path), not a fresh preparation here.
7. After each local export (made only with the person's go-ahead), the taxpayer files in
   the AEAT portal themselves, then load `cadrumo-reconciliar`. The recargo AEAT
   actually liquidates arrives with the official evidence; the preview is
   `unassessed`, the justificante is the authority. Say exactly that when the taxpayer
   asks "how much extra will I pay".
8. After each item closes, read `aeat app overview backlog` again and continue until
   `late_count` is zero. Then show the taxpayer the clean backlog - the situation is
   regularised locally, pending each filing's official reconciliation.

## Success assertions

- Every overdue item acted on was read from the backlog, never assumed or recalled from
  an earlier turn.
- Every recargo, interest and days-overdue figure shown to the taxpayer is a verbatim
  quote of tool output, with its legal reference intact; none was computed here.
- Oldest-first order was kept, or the deviation was the taxpayer's explicit, informed
  choice.
- No statement claims the matter is closed with AEAT before `cadrumo-reconciliar` has
  pulled official evidence for that filing.
- A requerimiento-received case was sent to a human professional, not processed here.

## Finish

Each catch-up filing follows its per-modelo skill through verify, export, the
taxpayer's own filing and `cadrumo-reconciliar`. This skill is done when the backlog
reads zero and every regularised filing has its official evidence reconciled or a
clear pending-reconciliation status the taxpayer understands.
