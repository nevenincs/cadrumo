---
tags:
  - '#research'
  - '#period-revision-resolution'
date: '2026-06-10'
modified: '2026-06-10'
related: []
---



# `period-revision-resolution` research: `Period to revision resolution: existing resolver, the identity-vs-calc divergence defect, and the orden-grounding gap`

Foundational read-only grounding (operator directive 2026-06-10) for an OVERVIEW ADR on the
period→revision resolution engine. The legal principle: every (modelo, year, period) was filed
against exactly ONE revision because AEAT publishes/updates norms and forms per period — "which
revision" is not a choice, it is determined by law; any calc path binding a hardcoded revision
is a defect. Reassuring headline: the codebase ALREADY implements this principle; the work is
to ratify it and close two latent divergence/audit gaps. All claims anchored at HEAD.

## Findings

### 1. The deterministic resolver already exists and is already enforced unambiguous

`select_revision(modelo, filing_year, period, on=None, revision_id=None) -> ModeloRevision`
(`domain/calculations/registry/_temporal.py:15-63`) returns exactly one revision, raising on
zero (`:56-59`) or >1 (`:60-62`) matches. Filters: `period_selector.includes_year(filing_year)`
(`:40`), case-insensitive period membership (`:51`), optional as-of `on` in `[valid_from,
valid_to]` (`:53`), optional `revision_id` narrowing (`:38`). Applicability is DECLARED, not
inferred from the dir name: each `revision.toml` carries `valid_from`/`valid_to` +
`period_selector = {years|year_from/year_to, periods}` (e.g. M130 open-ended
`130/revisions/2019-y-siguientes/revision.toml:3-4`; M100 per-year closed
`100/revisions/2025/revision.toml:4-6`). The non-overlap invariant — the in-code embodiment of
"one period → one revision" — is a registry gate: `validate_revision_windows`
(`_validate_revision_rules.py:19-31`, wired at `_validate.py:145`) fails the registry if two
revisions overlap on both date window and period selector, which makes `select_revision`
provably unambiguous in any valid registry.

### 2. The authority funnels every snapshot through it; production calc resolves from year+period

`ValidatedRegistryAuthority.snapshot(modelo, filing_year, period, on?, revision_id?)`
(`_authority.py:147-171`) → `_build_validated_snapshot` (`_snapshot.py:118-129`) →
`select_revision(...)`. So `authority.snapshot("130", filing_year=2026, period="1T")` DOES
deterministically resolve the revision; `revision_id` is an optional narrowing filter, not a
required input. Production calc/work callers pass the work unit's own `filing_year`/`period` and
do NOT pass `revision_id` (`_calculate_input.py:253,416`; `_multi_year.py:473`;
`_calculation_actions.py:481`). Work-unit creation derives the revision when `--revision` is
omitted (the default) via `resolve_registry_revision_for_work_target`
(`_work_addressing.py:446-467` → `select_revision`). Per-year norm changes within an open-ended
`*-y-siguientes` revision are modelled at the parameter-bracket layer (per-year bracket
`valid_from`/`valid_to`, gated by `validate_bracket_table_temporal_coverage`). **No
hardcoded-revision defects were found in production calc-engine paths.**

### 3. Legal grounding present but not first-class

Per-year ordenes appear inside revision `legal_refs` (M100 2025 cites `orden-hac-277-2026:art-3`,
`100/revisions/2025/revision.toml:25`; M130 cites `orden-eha-672-2007:art-1`). So the publishing
norm is declared — but there is NO explicit per-revision field naming the orden as the
applicability key; it sits unstructured in `legal_refs` alongside framework articles.

### Defect inventory

- **D1 — MEDIUM (latent divergence):** `revision_id` is part of the WorkUnit identity key
  `(bucket_id, modelo, filing_year, period, revision_id)` (`domain/modelos/_work_unit.py:13,
  93-114`) and is persisted at creation, yet every calc path RE-RESOLVES the snapshot purely
  from `filing_year`/`period` and does NOT pass `unit.revision_id` to `authority.snapshot(...)`.
  For single-revision-per-(year,period) modelos they always agree; but a work unit created with
  an explicit `--revision` that survives the weak `_revision_covers_year` check
  (`_work_addressing.py:463`) yet differs from `select_revision`'s pick would file under an
  identity claiming one revision while the numbers were computed under another — a silent legal
  mismatch. This is the closest analogue to the "hardcoded revision" concern: the binding is
  stored but not consulted at calc time.
- **D2 — LOW (test convention, not a defect):** M100/M130 enrollment tests pin
  `revision_id=str(filing_year)` (`test_modelo_100_multiyear_renta_enrollment.py:198`). Legit —
  M100 revisions are named by year — but it hard-pins rather than deriving via the resolver; a
  fixture-coverage characterisation, not a resolution defect.
- **D3 — LOW (structural/audit gap):** applicability is encoded only as `valid_from`/`valid_to`
  + `period_selector`, with the publishing orden buried in free-form `legal_refs`. No
  first-class "this orden fixes this revision for these years" declaration → the period→revision
  binding is not mechanically auditable against BOE.

### Risks

- **R1 (from D1):** an explicit `--revision` override diverging from `select_revision` files an
  identity-vs-computation revision mismatch, invisible to the operator. Latent today only
  because `validate_revision_windows` prevents two revisions covering the same (year, period) —
  the registry gate is the ONLY thing holding R1 latent.
- **R2 (cross-year carry):** prior-year carried values are trusted from stored
  `RegistryModeloObservation`s (`_cross_period_clean_state.py:442`) WITHOUT re-confirming the
  source year resolved to its correct revision when filed. A prior observation persisted under a
  wrong/stale revision would propagate one year's norms into the next undetected — no runtime
  gate re-checks `stored.revision == select_revision(source_modelo, source_year, source_period)`.
- **R3 (open-ended revision norm drift):** for `*-y-siguientes` revisions, a per-year
  rate/threshold change NOT captured by a parameter-bracket window silently applies the wrong
  year's number; the bracket-coverage gate catches gaps but not a wrong-but-present value
  (legal-grounding surface, out of scope here).
- **R4 (from D3):** because the orden is unstructured, an auditor cannot mechanically prove
  "revision X is the legally-correct revision for year Y" from the schema.

### Proposed engine shape (for the OVERVIEW ADR to ratify)

The deterministic resolver already exists and is already enforced unambiguous. The ADR should:
(1) RATIFY `select_revision` as THE single law-determined resolution authority and forbid any
calc path from passing an externally-chosen `revision_id`; (2) DEMOTE `--revision` from a free
override to an assertion verified against `select_revision` (refuse if it disagrees, not merely
if it fails year coverage) — close D1 by reconciling `unit.revision_id ==
select_revision(modelo, unit.filing_year, unit.period).id` at calc time (or drop it from
calc-time resolution and add that equality gate); (3) add a runtime gate for R2 (re-confirm a
stored prior observation's revision against `select_revision` for its source year); (4)
optionally (D3/R4) add a first-class applicability/orden field per revision, validated against
the legal catalogue per `registry-calculation-legal-grounding`, so the period→revision binding
is auditable against BOE. Plug-in point is entirely inside `ValidatedRegistryAuthority` /
`_snapshot.py` / `_temporal.py`; no new top-level surface. HONEST GAP: not every one of the
~247 resolution-grep files was audited for a literal `revision_id`/`filing_year` passed to
`authority.snapshot(` — an ADR-time sweep of `authority.snapshot(` call sites should close the
residual.

Key files: `_temporal.py:15-63` (resolver), `_validate_revision_rules.py:19-31` (non-overlap
gate), `_authority.py:147-171` + `_snapshot.py:118-129` (authority funnel),
`_work_addressing.py:446-467` (work-unit derivation), `_work_unit.py:13,93-114` (identity key),
`_calculation_actions.py:481` / `_calculate_input.py:253` / `_multi_year.py:473` (calc callers),
`_cross_period_clean_state.py:442` (carry trust point).
