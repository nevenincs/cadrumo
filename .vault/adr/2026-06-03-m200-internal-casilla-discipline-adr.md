---
tags:
  - '#adr'
  - '#m200-internal-casilla-discipline'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-m200-internal-casilla-discipline-research]]"
  - "[[2026-06-02-modelo-200-base-determination-adr]]"
---

# `m200-internal-casilla-discipline` adr: `Modelo 200 internal-only casilla schema field exempts app-internal ceilings from AEAT diseno-coverage gates` | (**status:** `accepted`)

## Problem Statement

Three reds fire in the M200 calculation-registry test suite
(`test_registered_record_design_sources_are_discovered_and_parseable`,
`test_calculation_completeness_manifests_match_their_calculation_surface`,
`test_calculation_closure_bounds_the_full_diseno_coverage` under
`src/aeat/domain/calculations/registry/test_record_design.py`) because the
M200 base-determination ADR (accepted 2026-06-02) introduced a synthetic
casilla `DP200014:bin-aplicada-maxima` whose `(segmento, number)`
identity does not appear in the AEAT-published Diseno de Registros for
the 2024-y-siguientes M200 revision. The casilla represents the LIS
art. 26.1 BIN-compensation ceiling (an app-internal computed limit AEAT
publishes as a formula, not as a form box) and is consumed by a
BLOCKING `cap_le_when_positive` verification predicate that bounds the
operator-elective applied amount `DP200014:00547`. The casilla is
substantively correct (real LIS authority, real legal_refs, real role in
the calc graph) but structurally invisible to the calculation-closure
gate, which today refuses any closure casilla carrying a segmento whose
pair is absent from the Diseno.

The registry schema has no way to declare that a casilla is intentionally
app-internal: formula-derived from real casillas, consumed only by
verification predicates or downstream computed casillas, never exported
to a fichero / BOE record, and not present in the AEAT Diseno. The
speculative fix already attempted (set `segmento=None`) bypasses the
diseno check but breaks the multi-segment manifest layering downstream
because the M200 calc graph identifies casillas by the segment-carrying
composite id. The cheap workaround (per-casilla allowlist in
`_record_design.py`) re-introduces exactly the honor-system per-fixture
list the `fixture-provenance-declared-in-sidecar` rule explicitly
forbids for a structurally analogous problem. The right fix lands the
internal-only intent in the schema where the gate can route around it
without losing its discipline against the mis-tag case the gate exists
to catch.

This ADR records that decision. The companion research enumerates the
inventory, the gate surface, and the AEAT Diseno authority scope; this
ADR decides the mechanism.

## Considerations

- **The bin-aplicada-maxima casilla is the first instance, not the
  last.** The M200 base-determination Phase 2 work will derive further
  internal intermediates (a `base imponible previa` subtotal, a
  correcciones aggregate) that have no AEAT Diseno presence either. Any
  fix that scales only to one casilla (an allowlist entry) carries
  immediate technical debt; the schema-field path scales to N internal
  casillas with no per-casilla maintenance.
- **The calc-graph identity must remain segment-aware.**
  `DP200014:bin-aplicada-maxima` declares `segmento = "DP200014"` because
  the calc graph identifies M200 casillas by composite (segmento,
  number) and the BIN compensation lives in the DP200014 Liquidacion III
  segment. The fix must not collapse the identity to bare-number form;
  the gate exemption must preserve the segment-carrying identity.
- **The casilla carries real LIS authority.** LIS art. 26.1 establishes
  the ceiling formula `min(BIN_stock, max(EUR 1M, 0.7 * base_previa))`.
  The casilla's `legal_refs = ["ley-27-2014:art-26", "ley-27-2014:art-25"]`
  and `source_refs` are grounded in the reviewed corpus. The
  `aeat-calculation-grounding`, `registry-calculation-legal-grounding`,
  and `no-silent-under-declaration` rules all defend this grounding;
  none of them is in tension with the internal-only intent. The casilla
  must keep its grounding under any exemption mechanism.
- **The Diseno authority is the form-export contract.** AEAT publishes
  the Diseno as the machine-readable fichero / BOE record format. It is
  authoritative on which numbers exist on the form, in which segment,
  with which data type. It is NOT authoritative on the application's
  internal calculation graph, which may compute intermediates AEAT does
  not publish as form boxes. The
  `derive_calculation_completeness_casillas` gate today over-extends the
  Diseno authority by refusing any closure casilla absent from it; the
  refusal is correct for the wrong-segment mis-tag and wrong only for
  the intentional app-internal case.
- **The schema is the right home for declaration of intent.** A casilla
  declares its own intent today (semantic_role, semantic_role_cardinality,
  semantic_role_cardinality_reason, required, input_kind, export_refs).
  Adding one more boolean follows the established declaration shape and
  rides the existing pydantic validator chain. The
  `fixture-provenance-declared-in-sidecar` rule's reasoning translates
  directly: declare the intent at the casilla, validate the declaration
  against physical evidence (here, the empty `export_refs`), and reject
  the per-casilla allowlist.
- **Anti-tautology check is the schema-level guard.** A casilla
  declaring `internal_only=true` AND non-empty `export_refs` is
  incoherent: AEAT would import it from a fichero record that does not
  exist. The schema validator MUST refuse such a casilla at load. This
  guard converts a footgun (mis-declared internal-only on an exported
  casilla) into a load-time RegistryValidationError. The
  `fixture-provenance-declared-in-sidecar` `/Producer` cross-check is the
  precedent.

## Constraints

- **Schema widening is the load-blocking surface.** The
  `CasillaDefinition` schema is the contract every modelo's TOML loader
  honors; adding a field touches every revision that authors a casilla.
  The default `False` keeps every existing casilla declaration
  syntactically unchanged; the migration burden is only on the M200
  bin-aplicada-maxima TOML (and any future internal-only casilla).
  Acceptable.
- **No new evaluator op needed.** The exemption is a single boolean
  short-circuit before the existing Diseno-presence check; the
  verification-predicate DSL, the formula registry, and the
  known-operators silent-pass guard are all untouched. No new operator
  registration, no new evaluator code paths.
- **Parent-feature stability.** Depends on the accepted
  `2026-06-02-modelo-200-base-determination-adr` (which introduced the
  ceiling casilla and the BLOCKING predicate) and the stable
  CasillaDefinition pydantic schema. Both are stable.
- **No fichero, no engine, no CLI surface change.** The exemption rides
  inside the registry-load gate. Operator-facing surfaces (CLI emit,
  verify findings, fichero export) are unaffected because the casilla
  already carries its provenance and the predicate already consumes its
  value.
- **Three reds must clear without weakening the gate.** The fix must
  unblock the M200 closure for `bin-aplicada-maxima` while preserving
  the gate's refusal of wrong-segment mis-tags on every other casilla.
  The anti-tautology test (a new casilla declaring `internal_only=true`
  AND non-empty `export_refs` is rejected at load) is the structural
  proof that the discipline is preserved.

## Implementation

A schema-first, three-Phase rollout, none of which touches operator
surfaces.

**(1) Schema field on `CasillaDefinition`.** Add
`internal_only: bool = Field(default=False, description=...)` to
`CasillaDefinition` in `src/aeat/domain/calculations/registry/_schema.py`.
The docstring names the contract: "App-internal computed casilla that
participates in the calculation graph but is intentionally absent from
the AEAT-published Diseno de Registros. Typically a regulatory ceiling
or intermediate the app materialises as a casilla so verification
predicates and downstream formulas can reference it. An internal_only
casilla MUST be computed (`input_kind = COMPUTED`), MUST carry no
`export_refs`, and MUST carry legal_refs / source_refs grounding the
internal computation in real regulatory authority." The schema's
`_validate_input_kind` (or a sibling validator
`_validate_internal_only`) raises `RegistryValidationError` if any of
those three conditions is violated.

**(2) Gate exemption in
`derive_calculation_completeness_casillas`.** In
`src/aeat/domain/calculations/registry/_record_design.py`, build a set
of internal-only `(segmento, number)` pairs from the revision at the
start of the function:

```
internal_only_identities = frozenset(
    (casilla.segmento, casilla.number)
    for casilla in revision.casillas
    if casilla.internal_only
)
```

In the multi-segment branch, before the
`if diseno_pairs is not None and segmento is not None ...` check, skip
internal_only pairs:

```
if (segmento, number) in internal_only_identities:
    ordered.append(DerivedDisenoCasilla(segmento=segmento, number=number))
    continue
```

The internal-only casilla is preserved in the manifest with its
segment-carrying identity (so downstream consumers that key on the
manifest still find it), but the Diseno-presence check is skipped. The
gate's discipline against wrong-segment mis-tags is unchanged for every
non-internal_only casilla.

**(3) M200 migration plus anti-tautology test.** Flip
`internal_only = true` on
`src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-bin-aplicada-maxima.toml`.
Author one anti-tautology test in
`src/aeat/domain/calculations/registry/` that constructs a
`CasillaDefinition(internal_only=True, export_refs=(some_export_id,))`
and asserts a `RegistryValidationError` raises. Author a second
real-behavior test that constructs an
`internal_only=True, input_kind=MANUAL` casilla and asserts the same
refusal: an internal ceiling that is not derived from a formula has no
legitimate computation surface. The three M200 reds clear by virtue of
(2); the anti-tautology tests defend the schema's discipline against
future mis-declarations.

The corresponding records-construct
(`records/constructs.part-002b.toml`) and formula authoring
(`records/formulas.toml`) for bin-aplicada-maxima do not change; only
the casilla TOML acquires the `internal_only = true` field.

## Rationale

The schema-field path is chosen because (a) it scales to every future
internal casilla with no per-casilla maintenance, (b) it declares intent
at the casilla rather than in a far-away allowlist in test source — the
locality discipline the `fixture-provenance-declared-in-sidecar` rule
codifies — and (c) it allows a schema-level anti-tautology validator
that catches mis-declarations at registry load rather than at runtime,
matching the pydantic-strict boundary the
`aeat-architecture-boundaries` rule mandates. The empty-`export_refs`
proxy is rejected because several legitimately-Diseno-published computed
casillas may currently carry empty `export_refs` only because their
fichero wiring has not been authored yet; the proxy would silently
exempt them from the diseno gate, which is precisely the discipline the
gate exists to enforce. The per-casilla allowlist is rejected for the
same reason
`fixture-provenance-declared-in-sidecar` rejects the per-fixture
allowlist: it re-introduces an honor-system list in test source that a
new internal casilla added later silently bypasses until someone
notices and patches the allowlist.

The fix preserves every regulatory grounding the casilla carries:
legal_refs and source_refs flow unchanged; the BLOCKING predicate
`modelo-200-compensacion-bin-no-excede-limite-art-26` continues to
consume `DP200014:bin-aplicada-maxima` to bound `DP200014:00547`; the
`no-silent-under-declaration` discipline the parent ADR enacts is
unaffected because the ceiling continues to participate in the calc
graph. The exemption changes only the Diseno-presence gate's
classification of the casilla, not its substantive role.

## Consequences

- **Three reds clear.** The M200 calculation-registry suite passes
  again, and the M200 base-determination ADR's BIN-compensation ceiling
  ships under a durable schema discipline rather than a workaround.
- **Future internal-only casillas land cleanly.** The M200
  base-determination Phase 2 work (and any other modelo's internal
  intermediate) declares `internal_only = true` at the casilla and the
  gate routes around it without per-casilla maintenance. The cost of
  authoring the next internal casilla collapses from "patch
  `_record_design.py` plus add a comment plus pray reviewers notice" to
  "set one boolean in the casilla TOML".
- **Mis-declarations are refused at load.** A casilla flagged
  `internal_only=true` with non-empty `export_refs` (or with
  `input_kind != COMPUTED`) raises `RegistryValidationError` at
  registry load. The honest signal is preserved.
- **The Diseno-presence gate keeps its discipline for non-internal
  casillas.** Every other M200 closure casilla still has its
  `(segmento, number)` cross-checked against the published Diseno; a
  wrong-segment mis-tag is still a load-time error. The gate narrows
  its claim ("every closure casilla MUST appear in the Diseno") to
  match its actual jurisdiction ("every exported closure casilla MUST
  appear in the Diseno"), which is what the AEAT Diseno authority
  covers.
- **One additional schema field on a hot type.** `CasillaDefinition`
  acquires one boolean. Every TOML revision that uses pydantic
  deserialisation continues to load (default `False`); the M200
  bin-aplicada-maxima TOML is the only existing file that flips it.
- **Tautological-test trap is excluded.** The anti-tautology test
  builds an in-process `CasillaDefinition` and asserts the validator
  refuses it; it does not assert against a registry-authored expected
  value. The `no-tautological-calculation-tests` rule is satisfied
  because the test exercises a validation contract, not a hand-computed
  calculation expectation.

## Codification candidates

- **Rule slug:** `casilla-internal-only-declared-at-source`.
  **Rule:** A casilla that participates in the modelo's calculation
  graph but is intentionally absent from the AEAT-published Diseno de
  Registros (an app-internal regulatory ceiling, intermediate, or
  derived limit) MUST declare `internal_only = true` at its TOML
  source. Per-casilla allowlists in test or gate source code are
  forbidden; the schema validator MUST refuse an `internal_only=true`
  casilla that also declares `export_refs` or whose `input_kind` is not
  `computed`.

  This candidate promotes only if the discipline survives the
  bin-aplicada-maxima migration without operator regression and the
  Phase 2 M200 base-determination work uses the flag for at least one
  additional casilla. Otherwise it remains documented rationale here.
  The candidate is a narrowing of `aeat-calculation-grounding`,
  `aeat-registry-authority-flow`, and `fixture-provenance-declared-in-sidecar`,
  not a wholly new constraint.
