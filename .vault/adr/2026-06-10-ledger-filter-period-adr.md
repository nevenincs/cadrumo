---
tags:
  - '#adr'
  - '#ledger-filter-period'
date: '2026-06-10'
related:
  - "[[2026-06-10-ledger-filter-period-research]]"
  - "[[2026-06-10-cli-operator-surface-adr]]"
  - "[[2026-06-01-registry-period-code-union-cli-boundary-adr]]"
---



# `ledger-filter-period` adr: `Single shared year.period filter; delete residual notation; continuity gate` | (**status:** `accepted`)

## Problem Statement

The ledger period filter is the keystone of the execution-restructure epic: the modelo
calculation snapshot reuses the exact period boundary the CLI ledger filter applies, so
the boundary must have one authority, one grammar, and a proof that it does not
double-count. Three concerns remain after the strict grammar landed (commit
`7c150c749`):

- The canonical `year.period` AEAT-token grammar is enforced at the operator surface but
  is not yet ratified as the *single shared* filter for both the CLI and the modelo
  calculation snapshot. The architecture must declare the shared `Period.contains()`
  path the one authority and forbid any parallel boundary implementation.
- The alternative calendar-shape ("dot/root") notation is refused at the operator
  surface but survives below it: `aggregation_period_for_modelo` still carries internal
  legacy aliases (`Q1`-`Q4`, `A`, `ANUAL`, `ANNUAL`), and six stale test call sites still
  pass the deleted notation and are currently broken.
- No continuity / anti-double-count invariant test exists. The fully-closed
  calendar-month-aware boundary is correct, but correctness is asserted nowhere; a future
  edit to the boundary computation could silently introduce an overlap or a gap.

## Considerations

The grounding research (`2026-06-10-ledger-filter-period-research`) verified against HEAD
that the CLI filter and the calc engine already converge on one boundary implementation —
`Period.model_validate(internal_calendar_str)` + `Period.contains(date)` in
`src/aeat/application/aggregation/_models.py` — with no parallel path. `Period.start`
and `Period.end` are computed fields; quarter and month ends use
`calendar.monthrange(...)` for the true last calendar day; `contains` is the fully-closed
`start <= value <= end`. The closed set of accepted tokens is `StandardPeriodCode`
(`src/aeat/core/_period.py`): `1T`-`4T`, `0A`, `01`-`12` are ledger-filterable spans;
`1P`-`4P` are payment events with no date span; `EXT-*` / `AD-HOC` / `EVENT-N` are not
ledger spans. The binding ADRs `2026-06-10-cli-operator-surface-adr` (D4 grammar) and
`2026-06-01-registry-period-code-union-cli-boundary-adr` (the registry-union CLI
boundary) already fix the operator-surface grammar; this ADR ratifies that grammar as the
shared filter authority and removes the residual notation beneath it.

This is an unreleased pre-beta project: `no-legacy-compatibility` mandates that the
alternative notation be **deleted outright with zero deprecation**, not bridged. Only the
established `year.period` AEAT-token grammar survives.

## Constraints

The decision binds to four existing surfaces that are all stable at HEAD:
`StandardPeriodCode` and the registry period union (`aeat-registry-authority-flow`); the
`Period` aggregation model and its `contains()` boundary; the CLI `_common.py` boundary
helpers (`_canonical_period`, `_filter_canonical_period`, `_ledger_aeat_token`,
`_aeat_token_to_calendar`); and `aggregation_period_for_modelo`. No frontier risk: every
component exists, is typed, and is exercised today. The only deletion that touches live
behaviour is the legacy-alias removal in `aggregation_period_for_modelo`; the research
confirmed every caller already feeds a canonical `StandardPeriodCode` token, so the
removed branches read a shape nothing writes.

## Implementation

The decision settles six points.

**1. Ratify one shared filter authority.** The canonical `year.period` AEAT-token grammar
is the single filter for both the CLI ledger surface and the modelo calculation snapshot.
The one boundary authority is `Period.contains()` over a `Period` built from the internal
calendar string; both transports (CLI `--filter period=` / `--period`+`--year`, and the
calc engine's `aggregation_period_for_modelo`) MUST converge on it. No parallel period
boundary implementation is permitted. The CLI's year-qualified filter form
(`YYYY-<AEAT-token>`) and the modelo surface's `--period`+`--year` pair are two spellings
of the same `(year, token)` input that both map through `_aeat_token_to_calendar` to the
same internal calendar shape.

**2. Delete the internal legacy aliases.** Remove the `Q1`-`Q4`, `A`, `ANUAL`, `ANNUAL`
branches from `aggregation_period_for_modelo` (`_modelo_bindings.py:448-453`), leaving
only the canonical AEAT tokens (`1T`-`4T` → `YYYYQn`, `0A` → bare `YYYY`, `01`-`12` /
`M01`-`M12` → `YYYY-MM`). The four call sites (`_modelo_bindings.py:158`, `:251`, `:304`,
`:383`) and their upstream `CalculationSourceContext` constructors
(`_taxation_comparison.py:287`, `_iva_wallet_gate.py:165`, `_calculation_actions.py:626`,
`_binding_resolution.py:174`) already pass `snapshot.period` / `work_unit.period`, which
are canonical `StandardPeriodCode` values, so no caller normalisation is required beyond
confirming they remain canonical.

**3. Migrate the six stale test call sites** to the canonical year-qualified form: a bare
year `YYYY` → the annual AEAT token `YYYY-0A`; a `YYYYQn` → `YYYY-nT`. The sites are
`test_ledger_corpus_journeys.py:378` (`2025Q1`→`2025-1T`),
`test_ledger_persona_autonoma_close.py:113` (`2025Q1`→`2025-1T`),
`test_ledger_persona_yearend_m100.py:126/277/279` (`2025`→`2025-0A`, `2026`→`2026-0A`),
and `test_ledger_list_filter.py:93-96, 135` (bare `YYYY` → `f"{year}-0A"`).

**4. Add the period-continuity invariant test** — the missing anti-double-count gate. For
every adjacent quarter pair and every adjacent month pair across at least two years, build
the two `Period`s and assert (a) `prior.end + one day == next.start` (no gap, no overlap),
and (b) no real calendar date is `contains()`-ed by both periods. The test uses real
`datetime.date` values and the real `Period` model; it is non-tautological because the
expected boundary days come from the calendar, not from re-running the formula under test.

**5. Confirm no boundary-inclusion override flags.** The fully-closed `[start, end]`
interval with calendar-month-aware ends is correct and continuous; an override flag for
boundary inclusion is the explicitly rejected alternative (see Rationale). The boundary is
fixed, not configurable.

**6. Secure-storage gate.** The filter is a selection predicate over rows that already
ride the per-profile encrypted bucket-scoped `SecureObjectRepository` (read via
`TransactionCatalogueRepositoryProtocol`, keyed by `bucket_id`); it adds no plaintext
persistence. The downstream snapshot the filter feeds bundles its evidence as the
already-encrypted `LedgerFilingEvidence` per `ledger-derived-revisions-bundle-evidence`,
so the evidence surface remains encrypted by that rule's invariant.

## Rationale

A single boundary authority is the only way to guarantee the CLI filter and the modelo
snapshot select the same transactions for the same period — and the snapshot's legal
weight depends on that. The closed `[start, end]` interval with `calendar.monthrange`
ends is chosen over a half-open `[start, next_start)` convention because it states the
last included day explicitly in the same calendar vocabulary an operator reads on a
filing, and because the continuity gate proves the closed form is gap-free and
overlap-free — a half-open form would need the symmetric proof and gains nothing.

A boundary-inclusion override flag is **rejected**: the boundary is a regulatory calendar
fact (a quarter is exactly its three calendar months), not an operator preference, and a
configurable boundary would fork the one authority into per-call variants — precisely the
parallel-implementation risk point 1 forbids. The legacy aliases are deleted rather than
kept because `no-legacy-compatibility` forbids carrying a shape nothing writes on an
unreleased project, and because every alias branch is dead at HEAD.

## Consequences

The epic gains a single, proven period boundary that the modelo calculation snapshot
reuses with confidence; the continuity gate makes any future overlap/gap regression a
loud test failure rather than a silent double-count. The six test migrations restore a
green ledger-filter suite. The alias deletion narrows `aggregation_period_for_modelo` to
the canonical tokens, removing a drift surface. The cost is small and mechanical: the
deletions touch dead branches and broken tests, and the new gate is pure-`Period`
arithmetic with no I/O.

Pitfall to watch: `project_ledger_list` (`_ledger_list.py:41`) is the single injection
point this filter shares with cluster C5's sort parameters — sort applies *after* the
filter — and with cluster C7's `source_transaction_ids` participation index, which is
selected by the *same* period predicate. The continuity gate and the single-authority
ratification keep all three consistent, but any future change to the boundary must be made
once, at `Period.contains()`, never re-derived at a call site.

## Codification candidates

- **Rule slug:** `period-filter-single-boundary-authority`.
  **Rule:** Every period-scoped selection — CLI ledger filter and modelo calculation
  snapshot alike — MUST resolve its date span through the one `Period.contains()`
  boundary built from the canonical `year.period` AEAT-token grammar; no parallel period
  boundary implementation and no boundary-inclusion override flag is permitted, and a
  continuity invariant test MUST prove adjacent periods are gap-free and overlap-free.
