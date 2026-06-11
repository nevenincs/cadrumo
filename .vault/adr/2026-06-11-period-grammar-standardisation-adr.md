---
tags:
  - '#adr'
  - '#period-grammar-standardisation'
date: '2026-06-11'
related:
  - "[[2026-06-11-period-grammar-standardisation-plan]]"
  - "[[2026-06-10-cli-operator-surface-adr]]"
  - "[[2026-06-01-registry-period-code-union-cli-boundary-adr]]"
---

# `period-grammar-standardisation` adr: `core Period value object: one typed period across the backend` | (**status:** `accepted`)

## Problem Statement

The operator-facing period grammar was standardised onto `--year YYYY --period
<AEAT-token>` (the D4 amendment of the `cli-operator-surface` ADR, landed in
`feat(period)` commit `224a6cd6c`): the ledger surfaces now accept only the bare
AEAT tokens and carry the year separately. But that fix stopped at the CLI
boundary. Below it, the backend still represents a filing period as a free-form
`str` whose value is, by convention, a *combined* calendar string — `2026Q1`,
`2026-03`, `2026A`, or the bare year — and that convention is duplicated,
re-parsed, and re-composed across dozens of modules with no single type to
anchor it.

A discovery sweep (vaultspec-rag semantic search plus `rg` programmatic matching
across the project) found the combined-token substrate is pervasive and
load-bearing:

- **`period: str` schema/model fields** sized `max_length=16`/`32` to hold the
  combined string, in `application/state_projection.py`,
  `application/overview/_calendar.py` (four of them, plus the
  `_period_aliases` / `_normalize_period_token` / `_filing_year_from_period`
  helper machinery), `domain/submission/_models.py`,
  `application/aggregation/_service.py` / `_source_mesh.py` / `_retenciones.py`,
  `application/workflow/_resume.py` (the WorkflowEngine contract),
  `domain/iva/_prorrata.py`, and others.
- **Active builders of the combined string**:
  `application/modelo/_work_addressing.py` composes `f"{year}Q1".."Q4"` only to
  re-parse it; `application/filing/_import.py` builds `canonical=f"{ejercicio}Q{quarter}"`;
  `application/overview/_calendar.py` builds `f"{year_prefix}Q{token[0]}"` aliases;
  and the existing aggregation `Period` itself stores a `raw` field holding
  `f"{year}Q{quarter}"`.
- **The registry deadline-window TOML** hardcodes `period = "2026Q1"` across
  every modelo, and `domain/period.py::parse_canonical_period` keeps a battery
  of combined-input regexes alive to read all of the above.
- **Two parser dialects** exist in parallel:
  `domain/period.py::parse_canonical_period` (combined → `(year, token)`) and
  `domain/calculations/registry::parse_modelo_period` (dashed `YYYY-Qn`).

There is no single typed home for "a filing period". Every module re-derives the
same `(year, token)` from a string, and every serialisation re-emits the
combined form. The operator now sees one grammar; the codebase still speaks a
dozen dialects of it.

## Considerations

- A `Period` already exists in `application/aggregation/_models.py` and is the
  de-facto value object: it has `year`, a `Quarter`/`month`/`kind`, computed
  `start`/`end`/`contains()`, `registry_token`, and the
  `from_year_and_token(year, token)` constructor that the CLI grammar now uses.
  It is the obvious seed — but it lives in the application layer, it still
  carries the `raw` combined-string field (the conflation lives *inside* the
  object), and it only models the ledger span shapes (quarters / months /
  annual), not the pago-fraccionado instalment claves (`1P`-`4P`) or the
  extended union members (`EXT-*` / `AD-HOC` / `EVENT-N`).
- `core/_period.py` already owns `StandardPeriodCode` (the canonical token
  `StrEnum`) and the registry-union validation helpers. The core layer is
  therefore the natural and already-established home for period authority; a
  value object composed there has no upward dependency problem.
- The operator directive is explicit: a `Period` is a **core, fundamental
  building block** — a value object with accessors, a canonical string
  representation, and equality/hashing — that every layer consumes, not a
  per-module string convention.
- `no-legacy-compatibility`: this is an unreleased pre-beta project. There is no
  persisted combined-string data to migrate or tolerate; the old shape is
  deleted, not bridged.
- `aeat-architecture-boundaries` (type every constant-like axis; no
  `dict[str, Any]` / bare-`str` for closed domain values) and
  `aeat-registry-authority-flow` (the registry compiles to strict schema
  objects) both point at a typed period as the canonical representation.

## Constraints

- The migration is wide but not deep-risk per file: a `core.Period` that is a
  frozen pydantic value object serialising to a canonical string is a
  mechanical substitution at most call sites. The genuine risk concentrates in
  three coupled surfaces that must move atomically with their consumers:
  1. the **registry deadline-window** schema + every modelo's
     `deadline_windows` TOML (governed by `aeat-registry-authority-flow`; the
     loader/compiler must hydrate `core.Period` at the boundary, leaving the
     TOML authoring shape decision to the rollout plan);
  2. the **WorkflowEngine** period contract (`workflow_period_for_work_unit`,
     `_resume`, `_workflow_gate`) and its ~30 dependent test assertions;
  3. the **persistence boundaries** that store `period` (state projection,
     calculation revisions, filing records) — each needs a strict
     save→load→equality roundtrip per `aeat-roundtrip-discipline`, with the
     anti-tautology proof, because the on-disk representation changes.
- Shared-worktree hazard: this rollout touches files many concurrent campaigns
  hold WIP in. It must land as a sequence of small, coherent, explicit-path
  commits — one substrate cluster per commit — never one mega-commit.
- The canonical `__str__` MUST NOT re-introduce the combined `2026Q1` form as a
  *parseable input*; it is a display/serialisation projection only. Inbound
  construction is always from `(year, StandardPeriodCode)`, never by parsing a
  combined string (the conversion layer the D4 amendment deleted stays deleted).

## Implementation

Promote a single immutable value object, `core.Period`, to `core/_period.py`
beside `StandardPeriodCode`, and roll it out to replace every `period: str`
field and every combined-string construction across the backend.

`core.Period` composes exactly two authoritative fields — a `filing_year: int`
and a `code: StandardPeriodCode` (the bare registry token) — and exposes:

- **Accessors** (read-only properties): `year`, `code` / `registry_token`,
  `start_date`, `end_date`, `contains(date)`, and a `kind`/`period_type`
  cadence discriminator. These subsume the helpers scattered today
  (`_filing_year_from_period`, `_normalize_period_token`, `period_start_date` /
  `period_end_date` in `domain/period.py`, the aggregation `Period.start/end`).
- **String representation**: a canonical `__str__` / `__repr__` and a pydantic
  serialiser that emit one stable, documented form, plus a single classmethod
  constructor `from_year_and_code(year, code)` (the renamed, widened successor
  of `from_year_and_token`) that accepts every union member — span shapes,
  instalment claves, and extended members — not only the ledger-filterable
  subset. The narrower "is this a date span?" question becomes a method
  (`has_date_span()`), so non-span periods are representable without raising.
- **Value semantics**: frozen, hashable, equality by `(year, code)`, so a
  `Period` is a drop-in dict key and comparison target wherever a `(year,
  token)` tuple or a combined string is used today.

The rollout proceeds by substrate cluster, each its own commit: (1) author
`core.Period` + its tests and re-export it; (2) re-seat the aggregation `Period`
on the core type (drop the `raw` field, delegate `from_year_and_token`); (3)
replace `period: str` in the application service / projection / overview / iva
schema models, hydrating `core.Period` at each boundary; (4) the registry
deadline-window schema + TOML; (5) the WorkflowEngine contract; (6) delete the
now-dead `parse_canonical_period` combined regexes and reconcile the
`parse_modelo_period` dialect; (7) the final repo-wide zero-combined-string gate.
The aggregation `Period`'s existing live behaviour (the ledger filter parity the
`one-aggregation-path-pull-equals-calculate` rule protects) is preserved
throughout.

## Rationale

The de-conflation cannot be finished as a string-grammar fix because the
inconsistency is not a grammar — it is the *absence of a type*. As long as a
period is a `str`, every module is free to invent its own spelling, and the
`2026Q1` convention re-grows wherever a developer composes a label. A single
core value object removes the freedom: there is one constructor, one string
projection, one set of accessors, and the combined string can exist only as an
output projection, never as a re-parseable input. This is the typed-axis
discipline `aeat-architecture-boundaries` already mandates for every other
closed domain value (modelo ids became `core.Modelo`, period codes became
`StandardPeriodCode`); `Period` is the missing aggregate that binds a year to a
code. The existing aggregation `Period` proves the shape works in production
(it is the live ledger-filter authority); this ADR generalises it to core and
completes its token coverage.

## Consequences

- **Gain**: one typed period across the whole backend; the combined `2026Q1`
  string survives only as a documented display projection; a new module
  physically cannot store a free-form period string without importing and
  constructing the core type. Discovery, comparison, and date-span logic stop
  being re-derived per module.
- **Gain**: the `domain/period.py` combined-input regexes and the
  `normalize_modelo_work_period` round-trip become deletable (they exist only to
  read the string shape the core type replaces), closing plan phases P03 and P05.
- **Difficulty**: the rollout is wide (the discovery sweep names ~25 production
  modules plus the registry TOML and ~30 workflow tests). It is real work spread
  across many commits, and three clusters (registry deadline-window, workflow
  contract, persistence boundaries) carry genuine coupling and roundtrip-test
  obligations. This is a multi-session campaign, sequenced as a new plan wave.
- **Pitfall**: re-introducing a combined-string *parser* "for convenience" would
  resurrect exactly the conflation the D4 amendment deleted. The core type's
  inbound contract is `(year, code)` only; the combined form is output-only.
- **Pathway**: with a core `Period`, the deadline-window, filing-record, and
  workflow surfaces can later expose period-typed query APIs instead of
  string-keyed lookups, and the registry can hydrate periods directly.

## Codification candidates

- **Rule slug:** `period-is-a-core-value-object-not-a-string`.
  **Rule:** A filing period MUST be represented as the typed `core.Period`
  value object (a `filing_year` plus a `StandardPeriodCode`), never as a
  free-form `str` field or a composed combined-calendar string; the combined
  `YYYYQn` form may exist only as an output/display projection of `Period`,
  never as a parseable inbound contract.
