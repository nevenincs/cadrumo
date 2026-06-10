---
tags:
  - '#research'
  - '#ledger-filter-period'
date: '2026-06-10'
related:
  - '[[2026-06-10-cli-operator-surface-adr]]'
  - '[[2026-06-01-registry-period-code-union-cli-boundary-adr]]'
---

# `ledger-filter-period` research: `Ledger period filter grammar and boundary continuity`

This research grounds cluster C6 (filtering and period-boundary semantics) of the
execution-restructure epic. It maps the period-filter grammar already shipped at the
operator surface, traces the single boundary implementation the CLI ledger filter and
the modelo calculation snapshot both converge on, inventories the residual legacy
notation that survives below the operator surface, and identifies the missing
anti-double-count continuity gate. The filter is the epic keystone: the modelo
calculation snapshot reuses this same period boundary, so the boundary authority must
be single and proven.

## Findings

### The strict `year.period` grammar already landed

Commit `7c150c749` (2026-06-10) installed the canonical grammar at the CLI ledger
period surface. Three boundary helpers in `src/aeat/entrypoints/cli/_common.py` own it:

- `_canonical_period(period, *, year)` (`_common.py:247`) backs `--period` / `--year`.
  It accepts only the bare AEAT modelo tokens — `0A` (annual), `1T`-`4T` (quarters),
  `01`-`12` (months) — validated through the registry period union, and composes them
  with `--year` exactly as the modelo surface does. A calendar shape (`2026Q1`,
  `2026-03`, `2026`) or any other notation is refused with a message that names the AEAT
  tokens and the `--year` argument.
- `_filter_canonical_period(value)` (`_common.py:281`) backs `--filter period=`. The
  filter mini-grammar is a `KEY=VALUE` clause with no place for a separate `--year`, so
  the year travels inline on the AEAT token: only `YYYY-<AEAT-token>` is accepted
  (`2026-1T`, `2026-0A`, `2026-03`), gated by `_FILTER_YEAR_QUALIFIED_RE`
  (`^(?P<year>\d{4})-(?P<token>[0-9A-Za-z]+)$`). A bare calendar shape (`2026Q1`,
  `2026`) is refused.
- Both helpers funnel through `_ledger_aeat_token` (`_common.py:227`) — which validates
  the trailing token against the registry union and accepts it only when it is a
  span-shaped `StandardPeriodCode` member the ledger can filter by — and
  `_aeat_token_to_calendar` (`_common.py:207`), which maps the validated `(year, token)`
  pair onto the internal calendar shape (`1T`-`4T` → `YYYYQn`, `0A` → bare `YYYY`,
  `01`-`12` → `YYYY-MM`). Instalment claves (`1P`-`4P`, a Modelo 202 payment event, not
  a date span) and the extended-union members (`EXT-*`, `AD-HOC`, `EVENT-N`) correctly
  return `None`, so the filter refuses them with the instructive message.

`StandardPeriodCode` in `src/aeat/core/_period.py:25` is the authoritative closed set:
its values are exactly `1T`-`4T`, `1P`-`4P`, `0A`, `01`-`12`. The ledger-filterable
subset is the span-shaped members (quarters, annual, months); the instalment claves are
in the enum but are payment events with no ledger date span.

### One shared boundary implementation — CLI filter and calc snapshot do not drift

The CLI ledger filter and the modelo calculation snapshot converge on a single boundary
authority: `Period.model_validate(internal_calendar_str)` plus `Period.contains(date)`
in `src/aeat/application/aggregation/_models.py`. There is no parallel boundary
implementation.

- `Period` (`_models.py:80`) is a strict frozen pydantic model. Its `start`
  (`_models.py:178`) and `end` (`_models.py:189`) are computed fields: quarter ends use
  `calendar.monthrange(year, month)[1]` for the true last calendar day; the annual span
  is Jan 1 – Dec 31; monthly spans use the same `monthrange` last-day rule.
- `Period.contains(value)` (`_models.py:208`) is `self.start <= value <= self.end` —
  a fully-closed inclusive interval `[start, end]`.
- CLI path: `--filter period=2024-1T` → `_filter_canonical_period` → `"2024Q1"` →
  `Period.model_validate` → `Period.contains`.
- Calc-engine path: an AEAT token → `aggregation_period_for_modelo`
  (`src/aeat/application/aggregation/_modelo_bindings.py:442`) → `"2024Q1"` → `Period`.

Both transports land on the identical `(start, end, contains)` computation. The boundary
is single-authority by construction.

### Boundary days are correct and adjacent periods are disjoint

The fully-closed `[start, end]` interval with calendar-month-aware ends produces correct,
continuous, non-overlapping boundaries: Q1 ends Mar 31 and Q2 starts Apr 1; the gap
between `prior.end` and `next.start` is exactly one day with no shared date, so no
transaction is double-counted across adjacent periods and none falls into a gap. The
boundary behaviour needs no override flag — the closed interval is already correct. What
is missing is a **proof**: there is no continuity / anti-double-count invariant test that
exercises every adjacent quarter pair and every adjacent month pair.

### Residual legacy notation below the operator surface

The operator surface refuses the calendar-shape ("dot/root") notation, but two residual
surfaces still carry the deleted notation:

(a) **Internal legacy aliases in `aggregation_period_for_modelo`**
(`_modelo_bindings.py:448-453`). Beyond the canonical AEAT tokens (`1T`-`4T`, `0A`,
`01`-`12` / `M01`-`M12`), the function still accepts `Q1`-`Q4`, `A`, `ANUAL`, `ANNUAL`.
These branches are dead: every caller now feeds a canonical token. The four call sites
are `_modelo_bindings.py:158`, `:251`, `:304` (each `period=context.period`, where
`CalculationSourceContext.period` is `snapshot.period` / `work_unit.period`) and `:383`
(the top-level `aggregate_modelo_ledger_bindings`, `period=period`). The upstream
context-construction sites — `_taxation_comparison.py:287`, `_iva_wallet_gate.py:165`,
`_calculation_actions.py:626`, `_binding_resolution.py:174` — all populate `period` from
`snapshot.period` / `work_unit.period`, which are constrained to the canonical
`StandardPeriodCode` values. The `Q1`/`A`/`ANUAL`/`ANNUAL` branches read a shape nothing
writes; per `no-legacy-compatibility` they are deletable dead weight.

(b) **Six stale test call sites** still pass the deleted notation and are therefore
currently broken / refused at the surface:

- `test_ledger_corpus_journeys.py:378` — `period=2025Q1`
- `test_ledger_persona_autonoma_close.py:113` — `period=2025Q1`
- `test_ledger_persona_yearend_m100.py:126` — `period=2025`
- `test_ledger_persona_yearend_m100.py:277` — `period=2025`
- `test_ledger_persona_yearend_m100.py:279` — `period=2026`
- `test_ledger_list_filter.py:93-96, 135` — `period=<bare YYYY>` (`target` / `target_year`
  are computed as a four-digit year string)

The migration shape is mechanical: a bare year `YYYY` becomes the annual AEAT token
`YYYY-0A`; a `YYYYQn` becomes `YYYY-nT`. (`test_cli_surface.py:397` already uses the
canonical `period=2026-06` and is a worked example of the target shape.)

### Secure-storage gate

The period filter is a selection predicate over persisted ledger rows. Those rows ride
the per-profile encrypted bucket-scoped `SecureObjectRepository`: the CLI ledger filter
reads through `TransactionCatalogueRepositoryProtocol` (`project_ledger_list` in
`_ledger_list.py:41`, bound to `transaction_repository.bucket_id`), and the calc-engine
path reads through the same repository protocols
(`aggregate_iva_ledger_observations_from_repositories` keyed by `bucket_id`). The filter
selects encrypted-at-rest rows; it adds no plaintext persistence surface. The downstream
modelo calculation snapshot that consumes the same period boundary bundles its evidence
as the already-encrypted `LedgerFilingEvidence` per
`ledger-derived-revisions-bundle-evidence`, so the evidence the filter ultimately feeds
is encrypted by that rule's invariant.

### Cross-cluster contracts

- **C5 (sort):** sort applies *after* this filter. `project_ledger_list`
  (`_ledger_list.py:41`) is the single injection point shared with C5's sort parameters;
  filter narrows the row set, sort orders the survivors. The two compose cleanly at one
  call site.
- **C7 (participation index):** the same period filter selects the
  `source_transaction_ids` the participation index records
  (`_modelo_bindings.py:435`, the sorted contributor tuple on
  `ModeloLedgerBindingAggregation`). Filter selection and index membership are
  definitionally the same predicate — they must stay consistent.
- **C1 (amount sign):** unaffected by the period filter.

## Open questions

- None blocking. The grammar, the single boundary authority, the residual-notation
  inventory, and the cross-cluster injection points are all verified against HEAD. The
  ADR settles the deletions, the test migration, and the missing continuity gate.
