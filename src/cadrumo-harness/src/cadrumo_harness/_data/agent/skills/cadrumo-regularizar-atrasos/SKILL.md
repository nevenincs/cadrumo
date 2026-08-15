---
name: cadrumo-regularizar-atrasos
description: >-
  Life-situation itinerary for a taxpayer who is behind on their tax
  obligations: surface every past-due filing from the overview backlog,
  relay the recargo extemporáneo the CLI derives (LGT art. 27), and drive
  each overdue obligation through its owning per-modelo skill oldest-first.
  Use when `aeat app overview backlog` reports one or more past-due
  obligations. Never computes a recargo or interest figure; relays the
  CLI's derivation verbatim.
applies_when:
  temporal_trigger: backlog_overdue
---

# Regularizar atrasos (behind on obligations)

Gating situation: the taxpayer has missed one or more filing deadlines. The
CLI already derives what is overdue, by how many days, and which recargo
band of LGT art. 27 applies; this itinerary sequences that surface and
delegates each catch-up filing to the per-modelo skill that owns it. Two
hard rules frame everything here. First, every recargo and days-overdue
figure is quoted verbatim from CLI output — never computed, extrapolated,
or "estimated" by you; the surcharge regime is law the deterministic layer
owns. Second, regularización through this itinerary is the voluntary,
before-requerimiento path that art. 27 covers: if the taxpayer has already
received an AEAT requerimiento or notification for the missed filing, stop
and route them to a human professional — the applicable regime is then
outside this itinerary's scope, and saying so plainly is the honest answer.

## Preconditions

- The taxpayer is onboarded (`aeat app overview status` reports an active
  profile) and the profile facts are declared; an undeclared profile makes
  the backlog derivation incomplete, which the CLI will refuse or warn
  about rather than silently under-report.
- The taxpayer has NOT received an AEAT requerimiento for the missed
  obligations (see the framing rule above).
- The source records (bank statements, invoices) for the overdue periods
  are available, or the taxpayer knows where to get them.

## Procedure

1. Surface the backlog: `aeat app overview backlog`. This is answerable for a
   behind-but-fresh taxpayer who has never filed and has no work units yet — the
   backlog is derived from the profile's obligation applicability and the
   deadline schedule, not from any persisted work state. Read `late_count` and
   the items, which arrive oldest-first. Bound the range with `--from` and
   `--to` only when the taxpayer asks about a specific stretch. Relay any
   warning or `coverage_advised` line as an open question to the taxpayer —
   an advised obligation is unresolved, not inapplicable. If a
   `work_units_degraded` notice appears, the local Modelo work-unit state could
   not be loaded; the backlog is still valid (schedule-derived) but may
   over-report an in-progress draft as still due — note it and continue.
2. When applicability of any surfaced modelo is in doubt, confirm it
   explicitly: `aeat app overview explain <MODELO> --year <YEAR>`. Read
   `verdict` and `rationale`; never assume from memory whether an
   obligation applies.
3. Keep the oldest-first order. The recargo grows with elapsed months and
   changes character at twelve months (interest is added on top), so the
   oldest item is almost always the most urgent. If the taxpayer wants a
   different order, surface that trade-off in plain language and let them
   decide.
4. Before any calculation, bring the ledger for each overdue period to
   clean: hand off to `cadrumo-llevar-libro` and then `cadrumo-clasificar`, scoped to that
   period. A catch-up filing computed from an incomplete ledger
   under-declares silently — the one outcome this whole system exists to
   prevent.
5. Drive each overdue obligation through its owning per-modelo skill
   (`cadrumo-preparar-modelo-303`, `cadrumo-preparar-modelo-130`, and siblings) over the
   standard spine. The work-unit surfaces stamp the filing extemporánea and
   emit the overdue context verbatim — `days_overdue`, `recargo_band`,
   `recargo_pct`, and the plazo-vencido warning notice. Relay those lines
   and the notice to the taxpayer exactly as emitted, with the legal basis
   the CLI cites (LGT art. 27). Never suppress the warning and never
   restate the percentage from memory.
6. Distinguish missing from wrong. This itinerary covers obligations that
   were never filed. If a surfaced problem is instead a filed declaration
   that needs correcting, route to `cadrumo-rectificar-declaracion` — the
   complementaria/sustitutiva path — not to a fresh preparation here.
7. After each local export the taxpayer files in the AEAT portal
   themselves, then hand off to `cadrumo-reconciliar`. The recargo AEAT actually
   liquidates arrives with the official evidence; the CLI's derivation is
   the preview, the justificante is the authority. Say exactly that when
   the taxpayer asks "how much extra will I pay".
8. After each item closes, re-run `aeat app overview backlog` and continue
   until `late_count` is zero. Then show the taxpayer the clean backlog —
   the situation is regularised locally, pending each filing's official
   reconciliation.

## Success assertions

- Every overdue item acted on was read from `aeat app overview backlog`,
  never assumed or recalled from an earlier turn.
- Every recargo, interest, and days-overdue figure shown to the taxpayer
  is a verbatim quote of a CLI output line or notice, with its legal
  reference intact; none was computed here.
- Oldest-first order was kept, or the deviation was the taxpayer's
  explicit, informed choice.
- No statement claims the matter is closed with AEAT before `cadrumo-reconciliar`
  has pulled official evidence for that filing.
- A requerimiento-received case was routed to a human professional, not
  processed here.

## Hand off

Each catch-up filing follows its per-modelo skill's own hand-off (verify,
export, human files, `cadrumo-reconciliar`). This itinerary's job ends when the
backlog reads zero and every regularised filing has its official evidence
reconciled or a clear pending-reconciliation status the taxpayer
understands.
