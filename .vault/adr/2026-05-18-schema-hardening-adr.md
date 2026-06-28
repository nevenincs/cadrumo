---
tags:
  - '#adr'
  - '#schema-hardening'
date: '2026-05-18'
modified: '2026-05-18'
related:
  - "[[2026-05-18-schema-hardening-research]]"
  - '[[2026-05-28-schema-hardening-continuity-conformance-research]]'
  - '[[2026-06-02-schema-hardening-m100-label-legal-continuity-candidate-research]]'
  - '[[2026-06-02-schema-hardening-m100-legal-ref-continuity-candidate-research]]'
---
# `schema-hardening` adr: Canonical semantic-atom layer for modelo registry | (**status:** `accepted`)

## Problem Statement

The AEAT modelo registry under `src/aeat/_data/registry/aeat/modelos/`
declares 26 hand-authored TOML schemas validated by the strict pydantic
schema in `src/aeat/domain/calculations/registry/_schema.py`. The
schema enforces identifier integrity, referential closure, and a narrow
numeric-bounds contract. It does not enforce semantic uniformity across
modelos.

A six-agent discovery swarm consolidated in the schema-hardening
research artefact established three cross-cutting failures:

- **F1.** `CasillaDefinition.data_type` has no `nif`, `name`,
  `country_code`, `year`, `iban`, `postal_code`, `period_code`, or
  `date` variant. Every identifier, name, country, year, and bank-account
  field falls back to `data_type = "text"`. The schema imposes no
  format, length, or check-digit constraint on any of them.
- **F2.** `CasillaConstraints` carries only numeric bounds. There is no
  `pattern`, `min_length`, `max_length`, or `enum` slot. Even when a
  modeller knows the legal contract on a text field (IBAN length, CCAA
  enumeration, postal-code shape), the schema cannot carry the rule.
- **F3.** Where constraints exist they are sparsely and inconsistently
  applied: 31 of 12,520 casillas (0.25%) carry any constraints. The
  same semantic role (`retenciones e ingresos a cuenta`) is
  `non_negative` in three modelos and unconstrained in six others. No
  registry-level rule explains the divergence.

Per-family the research identified HIGH-severity drift in identity,
naming, address, fiscal-period; MEDIUM-HIGH in monetary; MEDIUM in
banking. Concrete examples: payee NIF surfaces as a casilla in M180/M184
but only as a binding row-field in M190/M193; period tokens vary across
`1T/2T/3T/4T`, `1P/2P/3P`, and `EXT-NT`; the same charge-account IBAN
concept surfaces via three different registry layers without a shared
type; M720 stores a 164-char monolithic address blob while M180
decomposes the same real-world object into 13 sub-fields.

Without intervention the registry cannot verify that two modelos
declaring "taxpayer NIF" agree on what that means, and cannot catch
the next modeller introducing a fourth spelling, a fifth period token,
or a sixth address decomposition.

## Considerations

The research proposed three layered mechanisms. The decision is which
of them to adopt, in what sequence, with what failure mode, and where
the cross-modelo identity registry should live.

**Mechanism A — Extend `data_type`.** Add semantic-aware literals to
the `data_type` Literal in `_schema.py`, each backed by a pydantic
`Annotated` alias with a `BeforeValidator`. Low risk because the change
is additive; existing `data_type = "text"` declarations continue to
validate. Highest immediate value comes from `nif`, `year`,
`period_code`, `country_code`, `iban` — the atoms with the highest
cross-modelo footprint per the research.

**Mechanism B — Extend `CasillaConstraints`.** Add `pattern`,
`min_length`, `max_length`, `enum` slots. Wire snapshot-build
validation. Low risk, additive. Unlocks enforcement on legacy fields
that cannot migrate to a richer `data_type` immediately and on legitimate
free-text fields that nonetheless carry an enumerable contract (CCAA
codes that lack a registry-supplied code list, payment-method
discriminators, etc.).

**Mechanism C — Inline `semantic_role` per casilla.** Add an optional
`semantic_role` slot on `CasillaDefinition`. A snapshot-build validator
enforces that all casillas sharing a `semantic_role` declare the same
`data_type` and structurally compatible `constraints`. An `aliases`
slot carries BOE-derived label variants without breaking semantic
identity. A `semantic_role` value appearing on only one casilla in the
entire corpus emits a typo-twin warning.

Three sequencing options were considered: A-only narrow cut; A+B with
C deferred; all three sequenced. The first two leave the cross-modelo
identity gap open — modellers can still introduce a divergent
"retenciones" casilla in a new modelo and nothing will flag it. The
third closes the loop.

Three failure modes were considered: hard error at snapshot build;
audit warning during retrofit then hard error; always audit-only. The
first matches the existing strict-pydantic discipline; the registry
already refuses to load on referential-integrity violations. The second
introduces a transitional state where the schema is "validating but not
enforcing", which produces the same drift pattern this ADR exists to
eliminate. The third makes the validator a periodic audit-swarm finding
rather than a load gate, which the research's F3 finding showed is
insufficient to prevent recurrence.

Three locations were considered for the `semantic_role` registry:
inline per casilla; central catalogue TOML referenced by ID; pydantic
Literal in the schema module. Inline matches the existing
modelling-discipline pattern where authority is carried through
`legal_refs` and `source_refs` at the point of declaration. The central
catalogue would catch role-spelling typos at authoring time but would
introduce a parallel surface modellers must maintain. The Literal
would be strongest but requires a code change for every new role,
which the project's "factory-direct, no PRs" working pattern would
find disruptive.

## Constraints

- The registry validator must run at snapshot build, not as a separate
  test gate. The strict-pydantic discipline established for
  `ValidatedRegistryAuthority` is the load surface.
- Retrofit must preserve every existing `legal_refs` and `source_refs`
  triple. The hexagonal-architecture and calculation-grounding rules
  apply: provenance flows from registry source to operator-facing
  surface unbroken.
- No live AEAT submission is reachable from any code path this ADR
  touches.
- All 26 modelos must remain valid throughout the rollout — the
  validator goes live only after all modelos satisfy the rule for the
  atom in question.
- Inline `semantic_role` declaration loses the central-catalogue
  typo-detection guarantee. The typo-twin warning is the documented
  mitigation but does not fully eliminate the risk.

## Implementation

All three mechanisms are adopted. Implementation proceeds in three
plans, sequenced A → B → C, each plan landing independently against
a clean `main`.

### Plan A — `data_type` Literal extension

Extend the `data_type` Literal in `src/aeat/domain/calculations/
registry/_schema.py` with the following variants, each backed by a
pydantic `Annotated` alias and `BeforeValidator`:

- `nif` — Spanish NIF/NIE/CIF check-digit validator.
- `nif_iva` — Intracomunitario NIF-IVA pattern.
- `name` — non-empty unicode string with length bound.
- `country_code` — ISO 3166-1 alpha-2 plus AEAT-supported extensions.
- `ccaa_code` — closed enumeration of autonomous-community codes.
- `province_code` — two-digit Spanish province code.
- `postal_code` — five-digit Spanish postal code.
- `municipality_code` — five-digit INE municipality code.
- `iban` — IBAN mod-97 validator.
- `bic` — SWIFT BIC pattern.
- `year` — bounded integer matching `RegistrySnapshotRef.filing_year`.
- `period_code` — Literal of `1T|2T|3T|4T|1P|2P|3P|4P|0A|01..12|EXT-NT`
  plus documented event-name carve-outs.
- `date` — calendar date with declared format.

Retrofit the 26 modelos to use the new types where applicable. Add a
strict roundtrip test for each new alias following the
roundtrip-discipline pattern. Snapshot-build validation flips to
hard-error per atom once all 26 modelos clear the retrofit.

### Plan B — `CasillaConstraints` expansion

Extend the constraints model with `pattern`, `min_length`,
`max_length`, and `enum` slots. Wire them through the snapshot-build
validator. Existing numeric constraints behaviour preserved. Hard error
on violation. Add coverage for each new constraint shape via real
modelo fixtures.

### Plan C — Inline `semantic_role` registry

Add an optional `semantic_role: str | None` slot on
`CasillaDefinition`. Add an optional `aliases: tuple[str, ...]` slot
carrying BOE-derived label variants with their own `legal_refs` and
`source_refs`.

Snapshot-build validator enforces:

1. Intra-role consistency. All casillas sharing a `semantic_role`
   must declare the same `data_type` and structurally compatible
   `constraints`. Divergent declarations raise
   `RegistryValidationError` at snapshot build.
2. Typo-twin warning. A `semantic_role` value appearing on only one
   casilla in the entire corpus emits a warning. Does not block load.
3. Alias acceptance. The validator binds on semantic identity, not on
   label-name uniformity. BOE-derived label variants are preserved
   through `aliases`.

Rollout proceeds one canonical role at a time, ordered by cross-modelo
footprint: `taxpayer_nif` → `representative_nif` → `payee_nif` →
`base_imponible` → `cuota_a_ingresar` → `retenciones_ingresos_a_cuenta`
→ `pago_fraccionado` → identity/address/period atoms. Each role lands
as a focused commit retrofitting every affected casilla and turning
the validator on for that role only.

## Rationale

The research findings show drift across every concept family, with the
strongest single signal being F3: the constraint system already in
the schema is not load-bearing for the consistency properties this
work needs to enforce. A type-erasure fix alone (Plan A) catches
identifier-level bugs but leaves cross-modelo divergence untouched —
two modelos can both declare `data_type = "nif"` and still disagree on
whether the field represents the taxpayer or the payee. A constraints
expansion alone (Plan B) catches shape-level bugs but again leaves the
semantic-identity dimension unaddressed. Only Mechanism C closes the
loop on cross-modelo identity, and only the three layered together
deliver the property the user identified as motivating this work:
"the actual common keys within the model of schemas that we define are
not hard and malleable across the model of definitions."

Hard-error at snapshot build was chosen because F3 demonstrates that
audit-only mechanisms have already failed at this scale: nine modelos
disagree on whether `retenciones e ingresos a cuenta` should be
`non_negative`, and no audit ever caught it. The existing
strict-pydantic discipline at the load surface is the only enforcement
mode the codebase has empirically maintained.

Inline `semantic_role` was chosen because authoring discipline in this
codebase has consistently centralised through `legal_refs` and
`source_refs` at the point of declaration rather than through external
catalogues, and the snapshot-build validator pattern is the established
enforcement surface. The typo-twin warning is accepted as a partial
mitigation for the loss of central-catalogue typo detection; if it
proves inadequate in practice a follow-up ADR can revisit the central
catalogue with concrete evidence.

A-only and A+B narrower cuts were rejected because they leave the
cross-modelo identity gap open — the exact gap the research showed
matters most.

## Consequences

**Positive.**

- The registry gains a structural surface where modellers can express
  "this casilla holds a NIF" in a way the schema verifies.
- Cross-modelo semantic drift becomes a snapshot-load failure, not a
  drift that surfaces months later through audit swarms.
- The validator pattern composes with the existing referential-integrity
  validators and inherits their hard-error discipline.
- Retrofit improves the legal_refs / source_refs density on casillas
  that pick up `aliases` declarations.

**Negative / costs.**

- Retrofit touches all 26 modelo TOMLs. Plan A and Plan B retrofits
  are mechanical; Plan C requires per-role judgment about which
  casillas legitimately share a role and which do not.
- The `data_type` Literal grows from a small set to ~15 variants. Test
  coverage for each new variant requires a dedicated roundtrip per the
  roundtrip-discipline rule.
- The inline `semantic_role` choice carries a documented typo-twin
  risk. The warning surface mitigates but does not fully eliminate it.
- Cold atoms (M720 monolithic domicilio, M232 province-or-country,
  M100 FEAC bare-NIF) must be captured as documented deviations via
  `aliases` rather than forced into canonical shape. This requires a
  per-deviation `legal_refs` / `source_refs` justification.
- Plan C rollout is sequential by role; concurrent role retrofits
  would multiply the risk of merge conflicts on the same modelo files.

**Future considerations.**

- Cross-revision casilla deprecation tracking (the M100 IBAN
  rectificación drop pattern) is orthogonal to the atom layer and
  remains an open issue suitable for a follow-up research pass.
- A central `semantic_role` catalogue may become justifiable if the
  typo-twin warning fires repeatedly in practice. The decision can be
  revisited with concrete data after Plan C lands.
- Mechanism A's typed aliases (NIF check-digit, IBAN mod-97) may
  belong in `aeat.core` rather than in `aeat.domain.calculations.registry`
  if other domains (filing draft assembly, oracle replay, export
  layouts) need to validate the same atoms independently.
