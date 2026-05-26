---
tags:
  - '#research'
  - '#linkage-design-audit'
date: '2026-05-26'
related:
  - "[[2026-05-15-linkage-design-audit-research]]"
  - "[[2026-05-15-linkage-design-audit-reference]]"
  - "[[2026-05-17-linkage-design-audit-plan]]"
  - "[[2026-05-18-linkage-design-audit-audit]]"
---

# `linkage-design-audit` research: `casilla-values-collapse-hash-stability`

Pre-flight research for `linkage-design-audit` plan step `P02.S09`
(collapse `CalculationRevision.casilla_values` into a derived
projection over the typed `observations` envelope). The collapse is
constrained by content-addressed identity: `derive_calculation_revision_id`
emits a SHA-256 hash whose payload includes a `casilla_values`
projection. Every already-persisted revision id was derived against
the current payload shape; any change must preserve byte-identical
hashes or every catalogue row mismatches its derived id and the
content-addressing invariant breaks.

## Findings

### Current hash payload shape

The hash payload at `src/aeat/domain/modelos/_calculation_revision.py:135`
is a deterministic JSON object built from seven inputs:

- `work_unit_id`: trimmed string
- `inputs`: sorted dict of trimmed-key trimmed-value strings
- `overrides`: sorted dict of trimmed-key trimmed-value strings
- `outputs`: sorted dict of trimmed-key canonical-Decimal strings —
  this is the projection of `casilla_values`
- `source_transaction_ids`: sorted tuple of trimmed strings
- `borrador_snapshot_id`: trimmed string, conditionally present
- `bindings_sourced_from_borrador`: sorted tuple of trimmed strings,
  conditionally present

The `outputs` projection is built inline in the function:
`dict(sorted((k.strip(), _canonical_decimal(v)) for k, v in casilla_values.items()))`.
The `_canonical_decimal` helper at `_calculation_revision.py:155` is
a pure function over `Decimal`.

### Hash-stability pin (anti-tautology proof)

Landed at `_calculation_revision.py:test_revision_id_pinned_against_fully_populated_fixture`
(P08.S35). Pins SHA-256
`5b78dd04e614a50fe448439b7fdb843f1e31afe76f9d424d0276866679dee7ca`
for a fully-populated derivation. Any future change to the hash
domain — whether intentional migration or accidental drift — fails
this pin.

### Storage shape today

`CalculationRevision` at `_calculation_revision.py:204` carries two
fields after the dual-write campaign:

- `casilla_values: Mapping[str, Decimal]` — flat persisted mapping,
  drives the hash via the `outputs` projection above.
- `observations: tuple[CasillaObservation, ...]` — typed envelope
  with full formula provenance; default-factory empty for
  backward-compat with revisions persisted before the typed envelope
  landed.

`RegistryModeloObservation` at `_bindings.py:117-127` already
demonstrates the canonical collapse pattern: typed `observations`
tuple is canonical storage; `casilla_values` is a derived `@property`
materialising `{obs.casilla_id: obs.value for obs in observations}`.
The same pattern landed on `RegistryCalculationResult` in P02.S08
(commit `6963600c0`).

### Constraint surface (consumers reading from casilla_values)

The cross-module discovery (W09.P20.S139 gate, paired with the
2026-05-26 linkage-P02 inventory in commit `f424db370`) confirmed
~100 read sites of `.casilla_values` plus 27 construction sites
passing `casilla_values=` as a keyword argument. Notable
hash-domain-coupled paths:

- `_actions.py:1005, 2854, 3083` — 3 call sites threading the same
  mapping into `derive_calculation_revision_id` AND into the
  `CalculationRevision` constructor. Both must see the same
  projection for the constructor-validator id check to pass.
- `_calculation_revision.py:228` — the model_validator at construction
  re-derives the id from `self.casilla_values` and compares against
  `self.calculation_revision_id`. If `casilla_values` becomes a
  property, this re-derivation chain still reads via the property
  and the comparison stays consistent.

### Two projection strategies

**Strategy A — derive-at-hash-time, preserve flat shape.** Keep
`casilla_values` as a field today; introduce a derivation helper
`_outputs_for_hash(observations)` that materialises the same
`{casilla_id: Decimal}` projection from the typed envelope; route
both the constructor and `derive_calculation_revision_id` through it.
Hash domain is byte-identical to today because the projection is the
same `{casilla_id: Decimal}` mapping; pinned SHA stable. Field shape
unchanged on the wire (no schema migration). Adds one helper, zero
breaking changes downstream. Closes the P02.S09 intent (the typed
envelope becomes the source of truth even though both fields persist).

**Strategy B — drop the flat field, new canonical projection.**
Remove `casilla_values` from `CalculationRevision` entirely; expose
it as a derived `@property` over `observations` (mirroring
`RegistryModeloObservation`). The hash payload's `outputs` key now
sources from `observations` directly. To preserve the pinned SHA,
the projection must produce the same byte string as today — which it
does, because `{obs.casilla_id: obs.value for obs in observations}`
canonicalised by the same sort+canonical-Decimal logic equals the
current projection. Requires a JSON-schema migration on every
persisted catalogue row (drop the `casilla_values` key, persist
`observations` as the canonical envelope), plus a one-shot data
migration to upcast historical rows that lack `observations`. Touches
27 construction sites + 4 roundtrip suites + the secure-object
storage envelope.

### Hash-stability test result (key observation)

The SHA-256 pin is invariant under projection-source change as long
as the materialised dict is `{casilla_id: Decimal}` keyed by trimmed
casilla_id strings with values canonicalised by `_canonical_decimal`.
Both strategies preserve this — the difference is wire shape, not
hash shape. Confirmed by the existing P02.S08 RegistryCalculationResult
collapse where the same logic landed without hash-domain disturbance.

### Strategy A vs B tradeoffs (architectural)

| axis | Strategy A (keep field, derive at hash time) | Strategy B (drop field, new projection) |
|---|---|---|
| Hash-domain risk | none — projection unchanged | none — projection unchanged but requires migration discipline |
| Wire-shape risk | none | high — every persisted row needs migration |
| Roundtrip suite impact | none (field still present) | 4 suites need fixture/expected-shape updates |
| Construction-site impact | 27 sites unchanged | 27 sites need `casilla_values=` → derivation kwarg shift, libcst codemod (P02.S10) |
| AEAT calculation-grounding-rule alignment | partial — flat field persists alongside typed envelope, which the rule deprecates | full — typed envelope is the only persisted shape |
| Single source of truth | weak — both fields persist; drift possible | strong — observations is canonical, projection is derived view |
| Reversibility | trivial (drop helper, revert) | high cost (data migration to restore the flat field) |

### Cross-campaign collision check

Grounded against in-flight vault docs at `.vault/exec/` and
`.vault/plan/`: no parallel campaign currently touches
`CalculationRevision.casilla_values` or `derive_calculation_revision_id`.
The linkage-design-audit plan is the sole owner of this surface.

The schema-hardening campaign owns `semantic_role` on
`CasillaDefinition` and the registry-fragment architecture; it does
not touch the persisted modelo-revision storage shape.

The live-iva-compensation-wallet campaign owns
`RepairRemediationDecision` and secure-object hardening; it touches
`SecureObjectRepository` but not the calculation-revision payload.

### Recommendation surface

Both strategies preserve the pinned SHA. Strategy A is mechanically
cheap, preserves wire shape, and satisfies the P02.S09 intent (the
typed envelope drives the hash). Strategy B aligns more strictly
with the AEAT calculation-grounding rule's "persist typed envelopes,
not flat scalar mappings" mandate but requires a one-shot data
migration and roundtrip-suite churn.

A staged path is also available: land Strategy A first (single helper
+ constructor wiring; cheap, reversible), then schedule Strategy B
behind a separate migration ADR once Strategy A has run for one
release cycle and proven hash stability in practice.

ADR follows in `2026-05-26-linkage-p02-s09-casilla-values-collapse-adr`.
