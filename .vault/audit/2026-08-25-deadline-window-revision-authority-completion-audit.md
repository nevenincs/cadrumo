---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:90a76d4079ec7a883f8b3b43553e9ca0f54dc452fe0badc2fea18ac3fb46bac2'
related: []
---

# `deadline-window-revision-authority` audit: `completion`

## Scope

Final requirement-by-requirement review of the accepted deadline architecture, its research and reference, the complete fifty-step execution trace, final audits and execution records, and the live registry, resolver, engine, application, workflow, declaration/calculation-notice, and CLI paths. The review used Vaultspec RAG for decision discovery, then exact-symbol and path sweeps for competing selectors, resolvers, period parsers, cadence maps, supported-year horizons, deadline catalogues, qualifier vocabularies, clock seams, and multiplicity-erasing consumers.

The persistent objective was tested as nine independent claims: coverage across the canonical supported-year catalogue; unique law-selected revision ownership; complete registry-declared periodic cadence; one qualified filing-window matcher; thin downstream consumers; absence of duplicate authority or downstream deduplication; official source grounding; catalogue-driven deterministic behavior tests; and green attributable closure gates with no unresolved deadline finding.

## Findings

No critical, high, medium, or low finding remains open.

The plan trace reports fifty of fifty checked Steps, zero open Steps, and one execution record for every checked Step. The accepted decision remains consistent with the temporal-coverage and M210 plazo decisions.

Registry construction enforces redundant filing-year equality, globally unique ids and expanded atomic semantic coordinates, exact ownership through `select_revision`, shared cadence classification through `filing_schedule_period_kind_mismatches`, and periodic completeness from the sole `supported_filing_years` catalogue. The planted ownership, ambiguity, duplicate, cadence-contradiction, missing-cell, cold-construction, and warm-load tests prove that each gate bites.

`ValidatedRegistryAuthority.deadline_windows` validates the modelo, law-selects each containing revision, preserves qualified-row multiplicity, and performs deterministic ordering without deduplication. `resolve_filing_window` is the single qualifier-aware matcher; `resolve_filing_closes_on` is its unqualified convenience. M210 reuses `ResultDisposition`, the official tipo-renta code projection, and canonical `EVENT-N`/`0A` periods, refuses ambiguity, and leaves tipo 28 without an invented numeric offset.

`DeadlineEngine.compute`, overview calendar/agenda/backlog, workflow target selection, declaration and calculation plazo notices, and the CLI consume those canonical APIs. Ordered fleet parity covers every authored unqualified row for every catalogue-supported filing year; qualified M210 rows are covered through the canonical post-calculation path. Workflow refuses duplicate exact targets rather than selecting the first. The only reviewed deduplication reconciles observational filing evidence after legal obligations exist and does not alter obligation multiplicity.

The historical twelve-model periodic census reconciles 261 retained plus 294 officially materialised coordinates to 555 unique coordinates. Structural repairs separately remove the twenty-seven invalid duplicate base coordinates and correct M190/M193 identity. The live invariant is catalogue- and schedule-derived, so later enrolled modelos extend coverage without changing the historical denominator. Exact legal dates and source references remain in source-fidelity tests; fleet behavior derives years and relationships from canonical authorities.

Runtime status defaults through `today_madrid()` and accepts explicit dates. Deterministic tests use explicit reference dates or the existing `frozen_clock` seam; no deadline-path test requires the host civil day as a durable fact.

Attributable evidence is green: the pinned S35 closure lane reports 152 passes with cold and warm validation, M210/M720, resolver, engine, overview, agenda, backlog, and real CLI coverage; the wider checkpoint reports 220 passes with only the separately attributed thirteen-model layout inventory. Subsequent S45 through S50 records add deterministic-clock, authority-reset, design-axis, formatting, and real CLI parity verification, including current focused authority/deadline runs of twenty-one and twenty tests and independently reviewed CLI repairs. Ruff, formatting, feature Vault validation, and relevant smoke paths pass. Repository-wide red families are named and owned outside the deadline paths rather than represented as green.

Verdict: APPROVE. Severity counts: critical 0, high 0, medium 0, low 0.

## Recommendations

Retain the existing architecture without a follow-on ADR. Keep exact regulated dates in registry source-fidelity tests, keep fleet behavior derived from the supported-year catalogue and shared period/cadence authorities, preserve ordered multiplicity-sensitive consumer assertions, and continue recording unrelated repository health separately from attributable deadline acceptance.
