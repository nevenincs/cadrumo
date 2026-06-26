---
tags:
  - '#research'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-adr]]"
  - "[[2026-06-26-bindings-architecture-unification-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #research) and one feature tag.
     Replace binding-resolver-contract-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `binding-resolver-contract-unification` research: `binding shape-c aggregation unification`

Grounds follow-up #36 from the bindings-architecture-unification sweep: the shape-C
per-modelo aggregation service (`aggregate_per_modelo`, `src/aeat/application/aggregation/_service.py`)
is the SOLE backend of the CLI `aggregate` verb (`src/aeat/entrypoints/cli/_modelo_aggregate_cli.py`)
and has NO calculate-path caller (enforced CLI-only by `test_backend_boundary.py`). The
verb persists its observations (shared with calculate via set-replace), then computes a
FULL ROLLUP preview through the service — a SECOND aggregation mechanism over the same
observations, distinct from the canonical calculate-path mesh resolvers. That is a
`one-aggregation-path-pull-equals-calculate` + `calculation-source-canonical-mechanism`
violation: an operator's `aggregate` preview can diverge from what is filed. This research
classifies every shape-C source per-modelo and recommends the unification.

## Findings

### Headline: NO class-(b) silent-blank correctness gaps

The decisive result. Every shape-C source either resolves live on the calculate path
through a DIFFERENT and canonical mechanism (class a), is already tracked as deferred
with a standing advisory (M720), or is unmodelled on calculate (M347, class c). The
original campaign's silent-blank class does NOT recur. Deferring #36 left no
dormant-mesh-resolver invariant breach and no silent under-declaration — the ADR's
deferral rationale is confirmed.

### Per-modelo classification

Classes: (a) already-live on calculate via a canonical resolver — shape-C is redundant;
(b) genuinely unrouted on calculate = silent-blank gap; (c) served only by shape-C, no
calculate need.

- **Retenciones 111 / 115 / 123 — class a.** Quarterly; no count-box / per-perceptor
  binding in the registry. The annual roll-ups (180/190/193) carry the declarable
  figures. `_retenciones.py`.
- **Retenciones 180 — class a.** Binds `source="retenciones_aggregation"` (count box
  `decl.total-perceptores`), live via the enrolled `RetencionesAggregationSourceResolver`.
- **Retenciones 190 — class a.** Binds `source="withholding"`: nine per-perceptor row
  bindings (`percibido_dinerario`, `percibido_especie`, `retencion_practicada`,
  `ingreso_a_cuenta`, …) plus `percepcion_count`. The full base+retención IS modelled as
  withholding rows — live via the enrolled `WithholdingSourceResolver`. So the rich
  rollup the CLI shows is already canonical on calculate for M190.
- **Retenciones 193 — class a.** Binds `withholding` per-perceptor rows plus the
  `retenciones_aggregation` count box; live via both enrolled resolvers.
- **Counterpart 349 — class a.** Binds `source="collectible_invoice"` (operator_count,
  base_sum, per-operator rows), live via the enrolled `InvoiceCatalogueSourceResolver`
  consuming `InvoiceObservation`. The standalone `CounterpartObservation` the shape-C
  aggregator consumes has NO calculate-path origin.
- **Counterpart 347 — class c.** M347 has no `bindings/` directory and no calculate
  modelling; no registry binding declares `source="counterpart"` anywhere
  (`rg 'source = "counterpart"'` over the registry returns nothing). The shape-C 347
  rollup feeds no filing value.
- **Foreign-assets 720 — class b\* (already-tracked deferred, NOT silent).** Binds
  `source="foreign_asset"` (per-asset rows), but `FOREIGN_ASSET` is in
  `DEFERRED_SOURCE_KINDS`; calculate emits a standing advisory via
  `collect_unhandled_source_diagnostics`, not a silent blank.

Decisive registry fact: no binding uses `source="counterpart"` — the shape-C counterpart
aggregator consumes a CLI-only `CounterpartObservation` type with no registry binding and
no calculate-path origin.

### Two adjacent observations (NOT new gaps; flagged so they are not conflated)

- **M349 partial-clave coverage (pre-existing, independent of shape-C):** the M349
  bindings declare ten claves (E,M,H,A,T,S,I,R,D,C); the invoice resolver's
  intra-community clave derivation emits only E/A/T. This is an M349 calculate-completeness
  limit on its own surface; shape-C does not close it (different observation type). Belongs
  to the M349 surface, not this unification.
- **M347 has no calculate modelling (class c):** retiring shape-C removes the only M347
  aggregation surface; making M347 operator-fileable needs a registry binding + a canonical
  resolver — a separate feature, not part of this unification.

### Unification recommendation

Retire the shape-C rollup as a SECOND aggregation mechanism; keep the shared persistence;
derive the CLI preview from the ONE canonical surface:

- **Keep** the verb's set-replace persistence (`persist_retencion_observations` /
  `persist_withholding_observations`) — that IS the one-aggregation-path store calculate
  reads.
- **Re-point** the preview: instead of calling `aggregate_per_modelo`, the verb resolves
  the just-persisted observations through the SAME enrolled mesh resolver(s) the calculate
  path runs and projects its preview fields (`observation_count`, `result_row_count`,
  `source_kinds`, the casilla/binding summary) from the one `CalculationSourceResolution`
  envelope. Delegate, never re-implement (`composition-service-no-parallel-write-path`).
  This brings `aggregate` under the `test_pull_path_calculate_path_casilla_parity.py`
  guarantee, so the operator preview cannot diverge from the filing.
- **Retire** `aggregate_per_modelo`, the shape-C service wrapper, and the shape-C
  aggregators (`no-legacy-compatibility`: delete, don't bridge), retaining the
  `aggregate_retenciones_{180,193}` cores the enrolled `RetencionesAggregationSourceResolver`
  already consumes.
- **Disposition** M347 = reserved/unmodelled and M720 = deferred in the one disposition
  registry the resolver-contract ADR §4 introduces, so their non-mesh state is enforceable,
  not silently service-only.

### ADR direction

Amend the `binding-resolver-contract-unification` ADR §3 Execution refinement — no new ADR
needed. The ADR already scoped #36 and named the (a)/(b)/(c) framework; this research
fills the answer: classification result (above), CLI verb re-pointed to the canonical mesh
resolver(s) with `aggregate_per_modelo` + the shape-C aggregators retired, and M347/M720
enrolled in the §4 disposition registry. It lands under the existing
`one-source-resolver-contract` codification candidate plus `one-aggregation-path-pull-equals-calculate`
and `calculation-source-canonical-mechanism` — no new rule required.
