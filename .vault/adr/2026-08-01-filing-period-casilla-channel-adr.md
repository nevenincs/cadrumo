---
tags:
  - '#adr'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:b795f33d9c8b70376da6def3e5aa18033054fa344c1e351d0de8054ad27b028c'
related:
  - "[[2026-08-01-filing-period-casilla-channel-audit]]"
---

# `filing-period-casilla-channel` adr: `period token on the typed text channel` | (**status:** `accepted`)

## Problem Statement

Modelo 303's required, legally grounded `decl.periodo` casilla is filled with the
bare quarter ordinal (`Decimal("1")`) where AEAT requires the quarterly token
(`"1T"`). The value bypassed its declared `period_code` validator because the
filing builder's text-channel membership was keyed on the literal
`data_type == "text"`, routing every other typed string family to the Decimal
channel. An uncommitted typed-scalar routing change now makes the validator see
the value and correctly refuse it, which aborts the strict docs build and blocks
an authorised production publish. Evidence and reproduction are recorded in
`2026-08-01-filing-period-casilla-channel-audit`; this record owns the remedy
decision, its persistence-boundary consequences, and the dispatch-pattern ruling
the audit raised without deciding.

The operator's directive is the operative constraint: clear and strict types are
preferred, and introducing tracked issues that strengthen the codebase beats
latent drift persisting.

## Considerations

- The registry declares `decl.periodo` as `data_type = "period_code"` with the
  label naming the accepted set (`1T / 2T / 3T / 4T`), grounded in
  `rd-1624-1992:art-71`; AEAT's quarterly form was externally confirmed as
  `1T`-`4T` (audit, grounding boundary).
- The period token is total over every declared period form
  (`_validate_period_code` accepts `1T`-`4T`, `1P`-`4P`, `0A`, `01`-`12`,
  `EXT-1T`-`EXT-4T`, `AD-HOC`, `EVENT-N`); the ordinal is partial —
  `declaration_period_ordinal` returns `None` for extended, event, ad-hoc forms
  and `4P`, so Modelo 369's `EXT-1T` is inexpressible (audit, finding 3).
- The persisted revision already carries two typed value channels:
  `CalculationRevision.casilla_values: Mapping[CasillaId, Decimal]` (computed
  decimal output, hash-canonicalised through `_canonical_decimal`) and
  `input_values_by_casilla_id: Mapping[CasillaId, str]` (replayable string
  inputs). Typed text casillas (M210 `tipo_renta`, M369 period codes) already
  persist on the string channel and replay from it; verified at
  `_calculation_actions.py` where `resolved_text_inputs` merges into
  `input_values_by_casilla_id`, and in `_revision_replay_inputs.py`.
- `CasillaObservation.value` is strictly `Decimal`; the engine's
  `RegistryCalculationResult.values` is Decimal-only. Text-family casillas
  produce no observation today — a family-wide grounding asymmetry that
  predates this defect.
- `cadrumo.core.COMPATIBILITY_REGIME` is `PRE_RELEASE`: delete-not-migrate, no
  read-tolerance of pre-current shapes, no version bumps or upgraders for
  unreleased data. Confirmed at `core/compatibility_lifecycle.py`.
- The uncommitted routing change spans three packages and cannot be committed
  per-package: `application/filing` imports `registry_scalar_value_type` and
  `validate_registry_text_scalar`, absent at HEAD (audit, finding 4).
- A second live instance of the literal-keyed filter exists at the calculate
  boundary: `_calculate_input.py` routes `--casilla` overrides to the text
  channel only when `casilla_def.data_type == "text"`, sending every other
  string-family override to the Decimal parser.

## Considered options

- **A. Widen `casilla_values` to `Mapping[CasillaId, Decimal | str]`** and carry
  the token there. Rejected: weakens the strict Decimal contract on the computed
  output channel, forces union handling into the content-address hash
  (`_canonical_decimal`), `CasillaObservation.value`, export projections, and
  every payload model — a large union blast radius that contradicts the
  operator's strict-types directive when a dedicated string channel already
  exists.
- **B. Carry the token on the existing string channel** (`text_inputs` into the
  engine, `input_values_by_casilla_id` at persistence). Chosen: no persisted
  model shape changes, both channels stay strictly typed, and the period casilla
  joins the posture every other typed text casilla already holds.
- **C. Keep the ordinal and exempt `period_code` from the typed validator.**
  Rejected outright: it re-opens the validator bypass deliberately, persists a
  value AEAT does not accept, and remains inexpressible for Modelo 369.
- **D. Map `"1"` to `"1T"` at read/replay time.** Rejected: a read-tolerance
  coercion branch for a shape only this app wrote — forbidden under
  `no-legacy-compatibility` in the `PRE_RELEASE` regime.

## Constraints

- The three-package routing set must land atomically with the fill change; a
  per-package commit leaves HEAD unimportable (audit, finding 4).
- The uncommitted working-tree change has an owner in flight; the implementer
  adopts and completes it — coordinating with the owning campaign — rather than
  re-authoring it, and commits only with explicit pathspecs.
- Two pre-existing tests in `application/filing` fail under the routing change
  and must be updated in the same commit
  (`test_build_draft_conditional_formula_trace.py`), as must the parametrised
  ordinal pin in `test_declaration_period_binding.py`.
- The docs publish builds from the working tree; it stays blocked until the fix
  and the golden refresh land. No smaller step is honest: reverting the routing
  discards in-flight peer work and re-hides the defect, and an
  `@expect exit_code == 2` seed edit would publish a refused Modelo 303 verify
  as documented behaviour (audit, finding 4 and recommendations).

## Implementation

Ruling 1 — representation. The filing-period informational casilla carries the
canonical registry period token (`period.registry_token`, e.g. `"1T"`,
`"EXT-1T"`) as a string on the typed text-scalar channel.
`resolve_declaration_period_inputs` supplies the token for the `filing_period`
semantic role and stops projecting through `declaration_period_ordinal`; the
ordinal error path for extended forms disappears, which is what unblocks Modelo
369. The `filing_year` role is unaffected: `data_type = "year"` is int-family
and stays on the Decimal channel. `declaration_period_ordinal` loses its sole
production consumer; it is retired with its tests unless another consumer is
found at implementation time (no dead code).

Ruling 2 — persistence. No persisted model shape changes. `casilla_values`
remains `Mapping[CasillaId, Decimal]`; `CasillaObservation.value` remains
`Decimal`; the token persists in `input_values_by_casilla_id` and replays from
it, exactly as M210 `tipo_renta` does today. Therefore: no version bump, no
upgrader, no migration — and the `PRE_RELEASE` regime forbids them regardless.
An already-persisted revision carrying the ordinal in `casilla_values` is wrong
data, not an old shape: on replay, `_informational_casilla_replay_inputs`
stringifies it to `"1"`, the typed text channel routes it to
`_validate_period_code`, and the build refuses loudly with the instructive
period-code message. That fail-closed refusal is the intended posture; the
remedy is recalculation, never coercion. Coverage: the `CalculationRevision`
roundtrip fixture gains a non-default `period_code` entry in
`input_values_by_casilla_id` per the populate-every-defaultable-field
discipline, and an anti-tautology proof mutates a persisted ordinal-shaped
period value and asserts the draft build refuses — honestly targeting the build
gate, since the pydantic load cannot refuse a string that is merely wrong.

Ruling 3 — dispatch pattern, barred. A per-type membership filter MUST NOT be
keyed on a literal member of a type family when the complement routes to a
different channel: the excluded members fail silently in exactly the way correct
values succeed. Membership derives from the type taxonomy
(`registry_scalar_value_type(data_type) == "str"`) or is written as exhaustive
dispatch with a loud unsupported-type fallthrough. The uncommitted
`_text_casilla_data_types` change is ratified as the reference shape. Confirmed
instances beyond the filing builder: `_calculate_input.py` override routing
(silent complement — in scope, fixed in this campaign) and the
`_validate_verification_predicates.py` `data_type == "text"` gates (loud but
over-restrictive refusals — follow-up reconciliation). Exhaustive ladders that
raise on the unmatched tail (`_binding_input`) and presentation-only formatting
maps are not the barred shape.

Ruling 4 — grounding asymmetry, tracked not hidden. Moving `decl.periodo` off
the Decimal channel removes its `CasillaObservation` (and with it the
per-observation `legal_refs` envelope), placing it in the same posture as every
existing typed text casilla. The family-wide gap — typed text casillas carry no
observation-level provenance — predates this change and is not solved here by
widening the observation union; it becomes an explicit tracked issue per the
operator's issues-over-latent-drift directive. *(The premise of this ruling was
corrected post-execution: see the first Amendment below. The disposition —
tracked issue, no union widening — stands.)*

Ruling 5 — the publish waits. The docs publish is unblocked only by the fix
commit plus the golden refresh (`decl.periodo` moves `'1'`-`'4'` to
`'1T'`-`'4T'`, 54 occurrences). Publish pressure does not alter the ruling.

## Rationale

The registry declaration is the authority: `period_code` is a string family with
a validator whose accepted set is exactly the AEAT form, and the casilla's own
label states it. The token is the only representation total over every declared
period form, which the Modelo 369 finding proves structurally rather than
stylistically. Option B wins because the codebase already owns a strictly typed
string channel end to end — engine input, persistence, replay, draft build —
so the correction strengthens type separation instead of weakening it with a
union, honouring the operator's directive at zero persisted-shape cost. The
pre-release regime resolves the stale-data question decisively: loud refusal
plus recalculation, no migration surface.

## Consequences

- Filed Modelo 303 output carries the AEAT-required token; Modelo 369 extended
  periods become expressible, unblocking the in-flight M369 landing.
- The persisted boundary is untouched in shape; roundtrip and anti-tautology
  coverage is strengthened rather than restructured.
- Any revision persisted with the ordinal refuses loudly at replay/build and
  must be recalculated — accepted, pre-release, and preferable to silent wrong
  values in a filing artefact.
- The two-instance literal-membership sweep closes the silent class at the
  filing and calculate boundaries; the predicate-validator reconciliation and
  the text-casilla observation-parity gap become named follow-up work.
- The docs publish remains blocked until the fix and golden refresh land; the
  unblocking work is the fix itself, not a workaround.

## Amendment (2026-08-01): Ruling 4's premise corrected — the observation persists, wrongly typed

Execution of the plan's P01 (commit `7908da08c6`) disproved Ruling 4's premise
by writing the predicted assertion and watching it fail. The observation does
NOT disappear: `_initial_value_for_casilla` in
`_formula_initial_values.py` gives every non-computed declared casilla
`inputs.get(id, Decimal("0"))`, so a text-family casilla absent from the
Decimal inputs remains in `engine_result.values`, in `casilla_values`, and in
`observations` — carrying a structural `Decimal("0")`. Verified at source
post-landing.

The real gap is therefore type-expressiveness, not absence: the strictly
Decimal `CasillaObservation.value` cannot express a text value, and the
observation that IS emitted is worse than none — a structural `Decimal("0")`
for a period casilla is a plausible-looking wrong value where an absence would
at least read as a gap. The disposition is unchanged: no union widening in this
campaign, an explicit tracked issue instead — but the issue is re-scoped from
"typed text casillas carry no observation" to "the observation channel emits a
structurally wrong Decimal zero for text-family casillas and cannot express
their real value". The landed tests pin the `Decimal("0")` deliberately, which
doubles as an anti-regression guard: reinstating the ordinal fill puts
`Decimal("1")`-`Decimal("4")` back and fails.

Two plan-record corrections from the same execution: `P01.S04` required no code
change (the replay merge precedence already favours the string channel over the
stringified `casilla_values` projection), and `P01.S07`'s scope named
`domain/modelos/tests` while the encrypted-boundary roundtrip fixture lives at
`adapters/persistence/profile/tests/test_calculation_repository_roundtrip.py`.
Also confirmed at HEAD: `declaration_period_ordinal` now has zero production
consumers, so the P02 retirement needs no consumer sweep. The execution
baseline was 22 failing tests, not the 2 this record's Constraints carried from
the audit — the further 20 were the same defect surfacing through
persisted-revision replay one layer out; all 22 pass at the landed commit.

## Amendment (2026-08-01): the adopted set's rider changes are ratified

The adopted working-tree set landed in commit `7908da08c6` carried behaviour
changes beyond the typed dispatch this record ratified. They were
import-coupled through the registry package `__all__`, so splitting them out
would have left HEAD unimportable; the executor landed the coherent set and
flagged them. Ruled on individually:

- **`OneBasedExportOffset` tightening `ExportFieldDefinition.offset` from
  `ge=0` to `ge=1` — correct, ratified.** The offset is a one-based AEAT diseño
  position by both consumption contracts: the record-spec gate requires the
  first field at offset 1 and enforces `offset + length == next.offset`
  contiguity, and the deserialiser slices `spec.offset - 1` with an explicit
  one-based-to-zero-based comment. Every declared registry offset is >= 1
  (verified across the authoring tree; minimum is 1). Under the old `ge=0`, a
  zero offset validated at schema build and failed late or wrongly: a negative
  Python slice reads the wrong bytes silently on the deserialise path. The
  tightening converts a value nothing declares and both consumers treat as
  impossible into a loud registry-build refusal — squarely the strict-types
  directive. It is a validation tightening, not a data migration; no registry
  data changes.
- **`CasillaConstraints` consolidation — correct, ratified.** The `CasillaSchema`
  protocol's bare `min_value`/`max_value` Decimal properties were a partial
  projection of the registry's constraint declaration; the consolidation hands
  the validator the complete registry-owned `CasillaConstraints` object with
  its own `violates` contract. One constraint authority instead of a two-field
  re-projection; same single-contract shape the binding-validation discipline
  mandates.
- **`atomic_write_bytes` in `_export.py` and
  `serialize_renta_web_open_replay_decimal` — unobjectionable, ratified.**
  Torn-write hardening on the export output path and a typed Decimal
  serialisation helper for the oracle replay boundary; both are
  hardening-shaped with no contract change.

The commit message describes the filing-period fix but not these riders; this
amendment is the record that explains why a registry-wide validation tightening
rides in that commit.
