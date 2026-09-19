---
tags:
  - '#research'
  - '#tui-registry-api-gate'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:5f83e349e775bbd151be5fa3cb988c96e9d96acb361b2af1b21493715f10c6d2'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-10-casilla-schema-read-model-adr]]"
---

# `tui-registry-api-gate` research: `TUI registry API stability gate`

The closed casilla-schema campaign and partly executed TUI operation campaign
support a read-only review surface, but not yet a stable, lossless application
API for complex Modelo frontend work. Backend operation work can continue;
complex Modelo UI needs an architecture decision and acceptance gate for a
composed, versioned application facade first.

## Findings

### The dependency gate has moved from CasillaSchema completion to API closure

Casilla-schema closed at commit `097f9fd5adb1ece71c6fc1b43ecf3b553629f009`,
while TUI architecture is 44/113 and TUI interface remains 0/33. The active
plan still says it is blocked on casilla-schema despite advancing to S37;
interface execution remains correctly blocked on the architecture receipt
(`.vault/plan/2026-08-11-tui-architecture-plan.md:24`,
`.vault/plan/2026-08-11-tui-architecture-plan.md:125`,
`.vault/plan/2026-08-11-tui-interface-plan.md:26`).

### Authority-grade work has already broken the completed review contract

`build_modelo_work_review` implicitly requests filing grade
(`src/cadrumo/application/modelo/_work_review_projection.py:508`). M189 2025 now
declares applicability grade
(`src/cadrumo/_data/registry/aeat/modelos/189/revisions/2025/revision.toml:1`),
while its review test remains (`src/cadrumo/application/modelo/tests/test_modelo_work_review.py:148`).
A focused run at HEAD `0789567284ef242d3d84650fad0591ea9e159863`
produced 46 passes and one failure. The authority-grade ADR remains proposed
while its plan executes
(`.vault/adr/2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr.md:14`).

### Current projections omit frontend-significant schema and materialization

`CasillaDefinition` owns localization, constraints, alternate bindings, export
exposure, continuity, semantic roles, aliases and grounding
(`src/cadrumo/domain/calculations/registry/_schema_surfaces.py:199`). Work review
reduces bindings and formulas and exposes row fingerprints without row
coordinates, values, cohorts or direct materialization provenance
(`src/cadrumo/application/modelo/_work_review.py:59`,
`src/cadrumo/application/modelo/_work_review.py:180`). Source-casilla review and
replay parity remains open
(`.vault/plan/2026-08-22-source-casilla-integration-plan.md:227`).

### Locale, provenance and causal structure are lost before the UI boundary

The review uses strict-Spanish `casilla.label` despite locale-aware schema
accessors (`src/cadrumo/application/modelo/_work_review_projection.py:395`,
`src/cadrumo/domain/calculations/registry/_schema_surfaces.py:305`). It flattens
operand namespaces and omits binding selector/aggregation/grounding plus
relation source, period, aggregation and grounding
(`src/cadrumo/application/modelo/_work_review_projection.py:324`,
`src/cadrumo/application/modelo/_work_review_projection.py:341`).

### Capability and operation state lack cohesive production projections

The application exports separate registry closure composers, while their join
is development-only (`src/cadrumo/application/registry/__init__.py:684`,
`dev/registry/conformance/closure.py:173`). The supervisor exposes a journal
persistence DTO rather than the ADR's composed frontend envelope
(`src/cadrumo/application/operations/_journal.py:37`,
`src/cadrumo/application/operations/_supervisor.py:173`). No production TUI
composition root or Modelo operation family exists.

### Two bounded paths remain viable

A narrow read-only milestone can repair grade selection and localization while
preserving `ModeloWorkReview`'s pure-read scope. Complex review, editing and
workflow UI instead favors a separate versioned facade combining grade-explicit
and locale-explicit schema, scalar and row materialization, typed provenance,
capability/refusal and concurrency tokens, plus Modelo commands enrolled in
operations. Direct registry reports remain an expert-inspection alternative
that accepts frontend coupling to registry grammar.

Not investigated: full-suite health, live observation performance/backpressure,
or final semantics of open registry campaigns.

## Sources

- `.vault/adr/2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr.md:14`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:24`
- `.vault/plan/2026-08-11-tui-interface-plan.md:26`
- `.vault/plan/2026-08-22-source-casilla-integration-plan.md:227`
- `src/cadrumo/application/modelo/_work_review.py:59`
- `src/cadrumo/application/modelo/_work_review_projection.py:324`
- `src/cadrumo/application/modelo/tests/test_modelo_work_review.py:148`
- `src/cadrumo/application/operations/_journal.py:37`
- `src/cadrumo/application/operations/_supervisor.py:173`
- `src/cadrumo/application/registry/__init__.py:684`
- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:199`
- `src/cadrumo/_data/registry/aeat/modelos/189/revisions/2025/revision.toml:1`
- `dev/registry/conformance/closure.py:173`
- commit `097f9fd5adb1ece71c6fc1b43ecf3b553629f009`
- commit `0789567284ef242d3d84650fad0591ea9e159863`
