# AEAT calculation grounding

**Carry regulatory grounding through every domain boundary.** Every casilla
observation, calculation revision, filing draft, export record and CLI emit MUST
preserve its `legal_refs`, `source_refs` and `formula_id` provenance from the
registry source to the operator-facing surface.

**Persist typed envelopes, not flat scalar mappings.** `RegistryFilingObservation`,
`CasillaObservation`, `CalculationRevision.observations` and equivalent typed
records are canonical. Do not collapse them to `dict[str, Decimal]` for
downstream consumers; expose a derived mapping as a property if a flat view is
needed.

**Emit every casilla in `engine_result.values`, not only computed entries.**
Input and bound casillas MUST produce `CasillaObservation` rows pulled from the
registry casilla definition; computed casillas pull the same fields from the
matching engine entry. Never drop a casilla on the way to the persisted revision.

**Surface `legal_refs` and `source_refs` on every operator-facing CLI JSON
payload.** Wrap typed observations in a parallel JSON list alongside any flat
`casilla_values` mapping — the flat view is for human readability, the typed list
is the contract.

**Validate referential integrity at snapshot build.** Every typed-ID reference
must point at an existing entity on the snapshot; every per-source binding
selector must satisfy its typed selector model; every cross-domain routing table
must reference real casillas in the modelo revision.

**Treat type-system escapes as boundary leaks.** `cast(...)` calls,
`dict[str, Any]` returns and bare `str(...)` coercion of typed aliases are
documentation debt or design escapes. Document third-party API boundaries inline;
remove them everywhere else.

## Total-cuota aggregations must enumerate every cuota-bearing tier

An IVA "total cuota devengada" aggregation — Modelo 303's total casilla, Modelo
390's annual total, and any IVA modelo's equivalent — MUST sum the **recargo de
equivalencia** cuota tiers (LIVA art. 161) alongside the standard, reducido and
super-reducido repercutido tiers and the autorepercutido cuota.

Omitting them silently under-declares for any recargo filer and desynchronises
the annual return from the summed quarters, breaking the M390-to-M303
reconciliation gate. The omission was found twice, each time only by reconciling
an AEAT manual worked example carrying a recargo line against the engine.

## How

- **Good:** the formula enumerates every tier, the construct's `legal_refs` cite
  art. 161, and a grounded parity test against a manual example charging recargo
  reproduces the printed total exactly.
- **Bad:** "fixing" a failing recargo-inclusive parity test by adopting a
  recargo-excluded expected value. The expected figure is the manual's printed
  recargo-inclusive total; fix the formula, not the test.

Generalise it: when a new tier or category is added to any total, confirm every
downstream total and every return that reconciles against it enumerates it too.

Companions: `no-silent-under-declaration`, `registry-calculation-legal-grounding`.
