---
tags:
  - '#adr'
  - '#modelo-190-percepciones-count'
date: '2026-06-25'
modified: '2026-06-25'
related:
  - "[[2026-06-25-modelo-190-percepciones-count-research]]"
---



# `modelo-190-percepciones-count` adr: `Modelo 190 percepciones count: distinct-(perceptor,clave) over the withholding source` | (**status:** `accepted`)

## Problem Statement

Audit #22 flagged the Modelo 190 annual box `decl.total-percepciones` ("NÚMERO
TOTAL DE PERCEPCIONES") as an over-declaration of the same op=sum shape RET-1
fixes for M180/M193. It IS over-declared: the box is computed by formula
`modelo-190-total-percepciones` = `add()` of nine per-clave relations, each
`op="sum"` over `1T-4T` of Modelo 111 box `01` (`semantic_role="perceptor_count"`).
A perceptor present under one clave across multiple quarters is counted once per
quarter, while the annual declaration carries ONE record per (perceptor,
clave/subclave). But — established by the research against the bundled AEAT Diseño
de Registros (Orden EHA/3127/2009 actualizada por HAC/1431/2025, pos. 136-144:
"… las claves o subclaves de percepción a que correspondan. Número de registros de
tipo 2.") — M190's figure is the count of DISTINCT (perceptor NIF, clave/subclave)
type-2 records, NOT the distinct perceptor-NIF count RET-1 materialises. So M190
is a sibling defect needing its OWN fix, and must NOT be routed through RET-1's
`retenciones_aggregation` source (whose `total_perceptors` collapses claves and
would UNDER-declare). This ADR decides M190's correct fix.

## Considerations

- M180/M193 declare "número de PERCEPTORES" (distinct-NIF) — RET-1's
  `total_perceptors` is correct there. M190 declares "número de PERCEPCIONES"
  (distinct per perceptor-clave) — a strictly different count
  (percepciones ≥ perceptores).
- The clave-bearing producer ALREADY EXISTS. The M190/M193 per-perceptor detail
  source is the WITHHOLDING source; `WithholdingObservation` carries
  `perceptor_tax_id`, `clave` (2-char AEAT clave), `subclave`, the
  dinerario/especie amounts, and `retencion_practicada`, and its bindings already
  group `per_perceptor_clave`. So no new clave axis on `RetencionObservation` and
  no `RetencionesAggregation.total_percepciones` field are required — the #28
  spec's anticipated data-model extension is unnecessary.
- The 8-member `RetencionScheme` enum (the RET-1 source's only category axis) does
  NOT map to M190's clave taxonomy (no dinerario/especie split, no derechos-imagen)
  — a second reason the RET-1 source cannot express the M190 figure.
- The WITHHOLDING source is in `DEFERRED_SOURCE_KINDS` (advisory-only on the calc
  path today), so the box falls back to the wrong op=sum relation.
- `calculation-source-canonical-mechanism`: the monetary base/retenciones annual
  relations stay additive sums; only the COUNT is wrong.

## Constraints

- Regulated filed figure: an over- or under-count is a mis-declaration. The
  distinct-key MUST match the Diseño ("registros de tipo 2" = per perceptor +
  clave/subclave), grounded against the bundled corpus, not a secondary source.
- `no-dormant-source-resolvers`: enrolling a count over the withholding source
  requires either live enrollment in `merge_source_resolutions` +
  `_BUCKET_AGGREGATION_OWNED_SOURCES`, or explicit deferral — never a silent blank.
  The withholding source is currently deferred; this fix enrols a distinct-count
  path or the registry binding stays inert (the inert-resolver trap RET-1 P02 hit).
- `one-aggregation-path-pull-equals-calculate`: pull and calculate must produce
  the same percepciones count from the one withholding store; a parity gate enforces it.
- Producer-supplies-clave is load-bearing: the pull/import path that builds the
  `WithholdingObservation` rows MUST supply the AEAT clave per percepción (it
  already models the field) — a count primitive over a clave-less producer is inert.
- `aeat-architecture-boundaries` / `aeat-spanish-stem-naming`: the clave is a closed
  AEAT value set, so it belongs in `core` as a `RetencionClave` StrEnum (the A-O
  clave codes + subclave), not a free-form string, if the current 2-char string
  field is tightened — a sub-decision flagged below.

## Implementation

Materialise M190's `decl.total-percepciones` as a DISTINCT (perceptor_tax_id,
clave, subclave) count over the existing withholding detail, and enrol it on the
calc mesh:

- Add a distinct-(perceptor,clave) count aggregation over the withholding source
  — a new withholding binding op/fact (e.g. `percepcion_count_distinct`,
  `grouping = per_perceptor_clave`) that counts distinct (perceptor_tax_id, clave,
  subclave) `WithholdingObservation` rows for the annual window. This reuses the
  existing per-perceptor-clave row machinery; it does NOT touch the RET-1 retención
  store or `RetencionesAggregation`.
- Enrol the withholding-count path on the live mesh (`merge_source_resolutions` +
  owned set), or keep it explicitly deferred-with-advisory until enrolled — never a
  silent blank. This mirrors RET-1 P02's enrol-a-typed-count pattern, applied to the
  withholding source instead of the dedicated retención store.
- Re-point M190 `decl.total-percepciones` to the count binding (casilla
  `computed`→`bound` or formula→binding), and RETIRE the nine op=sum per-clave
  percepciones relations + drop their dependency entries (no registry≠runtime drift).
  Keep the monetary `decl.percepciones-total` (importe) sum relations.
- SUB-DECISION (DECIDED 2026-06-25): ship the count fix on the EXISTING validated
  2-char `WithholdingObservation.clave` string field. The `core` `RetencionClave`
  StrEnum (closed over the AEAT clave/subclave table) is the
  architecture-boundaries-correct end state but a wider change touching
  `WithholdingObservation` and all its producers, so it is tracked SEPARATELY as a
  follow-up hardening (task #29) — out of this ADR's scope. The percepciones-count
  fix does not block on it.
- Gates: a pull==calculate percepciones-count parity test; a distinct-count
  regression (a perceptor recurring across quarters under one clave counts once; a
  perceptor under two claves counts twice); expected counts grounded in the Diseño /
  a constructed distinct-(NIF,clave) fixture, not the relation formula.

## Rationale

The research established two facts that fix the design: M190's figure is
percepciones (perceptor-clave records) per the bundled Diseño, and the
clave-bearing producer (`WithholdingObservation` with `clave`/`subclave` +
`per_perceptor_clave` grouping) already exists. So the correct, minimal fix is a
distinct-(perceptor,clave) count over the existing withholding detail — not the
#28 spec's anticipated `RetencionObservation` clave-axis extension, and not RET-1's
distinct-NIF source (which would under-declare and cannot even represent M190's
claves). This keeps M190 on its own grounded source while sharing RET-1's
enrol-a-typed-distinct-count discipline.

## Consequences

Gains: M190's filed percepciones count becomes correct (distinct per
perceptor-clave) on the calc path; the wrong sum-of-quarterly relation is retired;
the fix reuses the existing clave-bearing withholding model with no new data-model
axis. Difficulties: the withholding source is deferred today, so this fix must
enrol a count path (the load-bearing new capability) — a count primitive over a
clave-less producer would be inert (the RET-1 P02 inert-resolver lesson). Pitfalls:
routing M190 through RET-1's distinct-NIF `retenciones_aggregation` would
under-declare (the regression this ADR exists to prevent); the producer/pull path
must actually supply the clave per row; the distinct key must be (NIF, clave,
subclave) per the Diseño, not (NIF) alone.

## Codification candidates

- **Rule slug:** `retenciones-counts-match-their-diseno-distinct-key`.
  **Rule:** Each annual retenciones-summary COUNT box must be a distinct-identity
  count whose key matches its AEAT Diseño definition — distinct perceptor NIF for
  "número de perceptores" (M180/M193), distinct (perceptor, clave/subclave) for
  "número de percepciones / registros de tipo 2" (M190) — never a sum of quarterly
  aggregate counts and never the wrong distinct key (NIF where the Diseño says
  per-clave). Promote after both RET-1 and this fix land and the lesson holds.
