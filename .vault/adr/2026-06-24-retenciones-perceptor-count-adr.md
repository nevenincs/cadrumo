---
tags:
  - '#adr'
  - '#retenciones-perceptor-count'
date: '2026-06-24'
modified: '2026-06-24'
related:
  - '[[2026-06-21-eoy-final-calculation-audit]]'
---

# `retenciones-perceptor-count` adr: `Retenciones perceptor count must derive from one repository-backed distinct-NIF source in the calc mesh` | (**status:** `proposed`)

## Problem Statement

The retenciones annual-summary perceptor count is computed divergently across the pull and
calculate surfaces, and on the calc surface it is wrong. For Modelo 180 (both revisions
`2019-2022` and `2023-y-siguientes`) the registry formula `modelo-180-total-perceptores` copies
the relation `modelo-180-rel-115-perceptores-anual`, which aggregates the four quarterly Modelo
115 "número de perceptores" (output `01`) with `op = "sum"` over `[1T,2T,3T,4T]`. A landlord paid
in more than one quarter is counted once per quarter, so the annual total over-counts. The AEAT
Modelo 180 Diseño de Registro defines the field as "NÚMERO TOTAL DE PERCEPTORES … (Número de
registros de tipo 2)" — the count of distinct perceptor (type-2) records on the annual
declaration, not the sum of quarterly aggregate counts. The sibling M180 base and retenciones
relations use the same `op = "sum"` shape, but those sum monetary amounts (additive, correct);
only the perceptor COUNT is wrong.

The correct value already exists as a validated primitive: `RetencionesAggregation.total_perceptors`
(`aggregate_retenciones_180`) is the distinct count of perceptor NIFs, structurally validated
(`total_perceptors` must equal the number of distinct perceptor NIFs or the model raises). But it
is reachable only through the per-modelo aggregation service (the CLI pull/export path), which
receives its per-perceptor observations as ephemeral CLI-supplied input. The live calculation mesh
(`merge_source_resolutions`) has no resolver that produces a per-perceptor distinct count; its
resolvers read persisted repositories (the ledger), and no repository carries per-perceptor
retención identity. So the calc path cannot compute the distinct count from any persisted source
and falls back to the wrong M115-sum relation. This is a pull-equals-calculate divergence — one
value computed two ways that disagree.

The gap is family-wide. Modelo 190 and Modelo 193 declare `perceptor_count` bindings over the
WITHHOLDING source, resolved by `resolve_withholding_binding_values` from passed-in observations,
and that source is likewise absent from the calc mesh. None of 180/190/193 has a repository-backed
per-perceptor source in the live calc path.

## Considerations

- The distinct-NIF primitive already exists and is validated; the missing piece is a persisted,
  calc-mesh-readable per-perceptor source, not the counting logic.
- The calc-mesh resolver contract (`CalculationSourceContext`) is repository-backed: existing
  resolvers (the renta income/expense ledger resolvers) read the ledger via bucket-scoped
  repositories. A perceptor-count resolver needs an equivalent repository of per-perceptor
  retención records.
- Perceptor identity (NIF) for arrendamiento and other retención flows is not modelled on the
  ledger today; the observations that feed the pull path are CLI-supplied and not persisted to a
  calc-readable store.
- The monetary base/retenciones annual relations (`op = "sum"`) are correct and must stay; only the
  COUNT relation is wrong.

## Constraints

- **Regulated value.** The count is a filed figure; an under- or over-count is a mis-declaration.
  The distinct-count semantics must match the AEAT Diseño ("número de registros de tipo 2"),
  including its clause that a perceptor figuring in multiple type-2 records is counted per record
  (the annual declaration carries one type-2 record per perceptor NIF).
- **One-aggregation-path.** Pull and calculate must produce the same count; a parity gate must
  enforce it. No parallel counting mechanism.
- **No-dormant-source-resolvers.** A new mesh source kind must be enrolled (owned set +
  `merge_source_resolutions`) or explicitly deferred; the retired M115-sum count relation must not
  leave a silent blank.
- **No-tautological tests.** Expected counts must be grounded in the AEAT Diseño or a constructed
  distinct-NIF fixture, not the relation formula under test.
- **Sensitive data.** Perceptor NIFs are financial identity data; any persisted per-perceptor store
  must live in the encrypted secure-object substrate, never a plaintext side store.
- **Gated on a data-model decision** (below): the implementation cannot start until the
  per-perceptor source of truth is chosen.

## Implementation

Introduce ONE repository-backed per-perceptor retención source feeding the calc mesh, and route the
retenciones perceptor counts through it:

- Persist per-perceptor retención records (perceptor NIF + scheme + amounts) in the bucket-scoped
  encrypted secure-object substrate, populated from the same inputs that feed the pull path, so pull
  and calculate read one store. This is the load-bearing new capability — the calc path's missing
  repository.
- Add a calc-mesh source resolver (an owned source kind, e.g. `ledger_retenciones_aggregation`)
  that reads those records for the modelo's annual window, calls the existing distinct-count
  primitive, and materialises the perceptor-count binding with `total_perceptors`. Enrol it in
  `merge_source_resolutions` and the owned-source set; add the source kind to `BindingSourceKind`
  with the registry-vs-enum parity gate.
- Retire the M180 perceptores `op = "sum"` relation in both revisions and re-point
  `modelo-180-total-perceptores` at the binding; keep the base/retenciones monetary relations.
  Re-stamp the perceptor binding's `source` from `relation_prefill` to the new source kind.
- Extend the same source to the M190/M193 `perceptor_count` bindings (family-wide unification), so
  all three modelos count distinctly from one source.
- Gate it: a pull==calculate parity test for the perceptor count; a distinct-count regression (a
  perceptor across two quarters counts once); the distinct-NIF anti-tautology proof on the
  aggregation primitive.

## Rationale

The divergence has a single root cause — the calc path has no persisted per-perceptor source, so it
substitutes a quarterly-aggregate sum that the AEAT Diseño contradicts. The fix the established
architecture points to is the repository-backed mesh-resolver pattern already used for ledger
income/expense, applied to a per-perceptor retención store, with the existing validated
distinct-count primitive as the counting logic. This unifies the pull and calculate surfaces onto
one source (one-aggregation-path) and generalises across the retenciones family rather than patching
M180 alone. Grounded in the AEAT Modelo 180 Diseño de Registro (Orden HAP/1732/2014, actualizado por
Orden HFP/1284/2023) "Número de registros de tipo 2", and in the pilot reconciliation discovery that
traced the calc-vs-pull split end to end.

## Consequences

Gains: the filed perceptor count becomes correct (distinct) on the calc path; pull and calculate
reconcile; the whole retenciones-count family is unified on one grounded source; the wrong M115-sum
count relation is deleted. Difficulties: the load-bearing prerequisite is a new persisted
per-perceptor store — a real data-model addition, not wiring; it must live in the encrypted
substrate and be populated coherently for both surfaces. Pitfalls: re-pointing the count before the
repository exists would leave the binding blank (no-dormant-source); the monetary relations must be
left untouched; the distinct-count semantics must follow the Diseño's per-type-2-record rule; tests
must be grounded, not tautological. Open decision: whether per-perceptor records are modelled on the
ledger or persisted as a dedicated retención-observation store — this gates the plan and should be
ratified before execution.

## Codification candidates

- **Rule slug:** `retenciones-counts-are-distinct-not-summed`.
  **Rule:** An annual-summary perceptor/recipient COUNT (Modelo 180/190/193 "número total de
  perceptores") MUST be a distinct-identity (NIF) count from one repository-backed source shared by
  the pull and calculate surfaces, never the arithmetic sum of quarterly aggregate counts; monetary
  annual relations remain additive sums. Promote after the fix lands and the lesson holds across one
  execution cycle.
