---
tags:
  - '#audit'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:598051ea7733bb37e3b54638bcd2786390aa9f1271fc0b35228d94ad0ac95946'
related: []
---

# `filing-period-casilla-channel` audit: `Modelo 303 decl.periodo carries the quarter ordinal, not the AEAT period token`

## Scope

A production docs publish was blocked by a strict Sphinx build failing with
`6 cli-sequence divergence(s)`. Investigation of the blocking refusal, rather
than the divergence, is what this audit records.

The investigation was dispatched as "land an uncommitted Modelo 369 period
validation with refreshed goldens". Nothing was landed and no goldens were
moved. The refusal turned out to be a true positive over a pre-existing defect
in the Modelo 303 filing path, and the golden refresh could not have absorbed
it. The evidence is recorded here because the remedy is an operator decision
with persistence-boundary consequences, and the finding must outlive the
session that produced it.

Audited surfaces: the uncommitted typed-scalar routing change spanning
`src/cadrumo/domain/calculations/registry/`, `src/cadrumo/domain/filing/`, and
`src/cadrumo/application/filing/`; the informational filing-period casilla fill
in `src/cadrumo/application/modelo/_binding_resolution.py`; the registry
declarations for `decl.periodo` under
`src/cadrumo/_data/registry/aeat/modelos/303/` and `369/`; and the committed
cli-sequence goldens under `docs/_sequences/`.

Read-only throughout. No production code was modified and no commit was made.

## Findings

### m303-decl-periodo-carries-quarter-ordinal | critical | a required, legally-grounded field of the filed Modelo 303 carries the bare ordinal where AEAT requires the quarterly token

The informational filing-period casilla is populated with the bare quarter
ordinal. `resolve_declaration_period_inputs` in
`src/cadrumo/application/modelo/_binding_resolution.py` resolves the casilla
carrying `semantic_role = "filing_period"` and assigns
`Decimal(period.declaration_period_ordinal)` — the values `1`, `2`, `3`, `4`.

Modelo 303 declares that same casilla, in its own revision tree, as a typed
period code. In
`src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`
(identically in `2009-y-siguientes`): `data_type = "period_code"`,
`label = "Periodo trimestral (1T / 2T / 3T / 4T)"`, `required = true`,
`legal_refs = ["rd-1624-1992:art-71", "orden-eha-3786-2008:art-1"]`.

The registry's own label states the accepted set outright, and the AEAT
quarterly period value is `1T`, never the bare `1`. The stored value is
therefore wrong in a required field of a declaration a human files outside the
application, grounded in RD 1624/1992 art. 71.

The ordinal is deliberate and pinned. `test_declaration_period_binding.py`
asserts `revision.casilla_values[decl.periodo] == Decimal("1")` across a 1T–4T
parametrisation, under the docstring "carries the work unit's quarter ordinal,
not `0`". The test defends the ordinal against an earlier zero-fill defect and
did not revisit whether the ordinal itself matches the declared type.

### typed-casilla-bypasses-its-own-validator-via-its-channel | critical | the value never reached the validator its declared type names, because of the channel it travelled on

This is the part most worth preserving, because it is a defect class rather
than a single instance.

The registry declares a validator per scalar `data_type`; for `period_code`
that validator is `_validate_period_code` in
`src/cadrumo/domain/calculations/registry/_schema_scalars.py`. Whether a
casilla's value ever reaches its declared validator depended not on its
declared type but on which input channel the filing builder routed it to.

The builder selected the text channel by an exact-string test,
`casilla.data_type == "text"`. A casilla declared `period_code` — or `nif`,
`iban`, `postal_code`, or any other typed string family — failed that test and
was routed to the decimal channel instead. The persisted string `"1"` parsed
cleanly back to a `Decimal`, the draft built without complaint, and the
declared validator was never invoked. The field was typed, the validator
existed and was correct, and nothing connected them.

The silence was total: no finding, no advisory, no log line. The wrong value
flowed through calculate, persisted into the revision, replayed into the draft,
and rendered into 54 committed golden fixtures without a single surface
reporting anything. It survived because a typed field that skips its validator
fails in exactly the way a correct field succeeds.

The generalisable rule: a per-type validator registry is only as good as the
routing that reaches it, and routing keyed on one literal member of a type
family silently excludes every other member. Any future per-type dispatch
should derive its membership test from the type taxonomy itself rather than
naming one member.

### ordinal-fill-is-structurally-broken-for-modelo-369 | high | the ordinal approach cannot express an OSS extended period at all

The ordinal fill is not merely wrong for Modelo 303; it is inexpressible for
Modelo 369. `declaration_period_ordinal` in `src/cadrumo/core/_period.py`
derives from `standard_code` and returns `None` for extended, event, and ad-hoc
forms. The OSS extra-Union quarters `EXT-1T`–`EXT-4T` have no standard code, so
the property returns `None` and `resolve_declaration_period_inputs` raises
`ModeloError` rather than producing a value.

Modelo 369 declares the same `decl.periodo` casilla as `period_code` across all
three of its schemes (`esquema-union`, `esquema-exterior`,
`esquema-importacion`), grounded in `orden-hac-610-2021:art-2`. The registry
validator accepts `EXT-1T`–`EXT-4T` alongside `1T`–`4T`, `1P`–`4P`, `0A`,
`01`–`12`, `AD-HOC`, and `EVENT-N`.

This is corroborating evidence that the period token, not the ordinal, is the
correct representation: the token expresses every declared period form, and the
ordinal expresses only the quarterly subset.

### goldens-cannot-absorb-an-execution-abort | high | the only golden-shaped fix would document that verifying a Modelo 303 is refused

The blocked docs build cannot be cleared by refreshing goldens, and this is
mechanical rather than a matter of judgement.

The failure is an execution abort, not a golden divergence. Reproduced against
`how-to/modelo-390`: the sequence `modelo-390-annual-2025` failed to execute at
`seed:iva-year-2025 line 26` with `frame exited 2, expected 0`, carrying the
underlying refusal `REFUSED_MODELO_WORKFLOW_GATE` / `DRAFT_HAS_ERRORS`:
`text casilla input 'decl.periodo' is invalid: period_code value '1' does not
match a supported filing-period form`.

The exit-0 expectation lives in the sequence source — an `@setup` frame in
`docs/_sequences/seeds/iva-year-2025.seq` — not in the golden. No golden
rewrite can absorb an exit-2. Making the sequence pass without fixing the code
would require editing the seed to declare `@expect exit_code == 2`, which
documents a refused Modelo 303 verify across every page sharing that seed. That
would publish the defect as intended behaviour.

Affected pages: `how-to/filing-spine` (the chain, file, select, and exact-ids
sequences) and `how-to/modelo-390`.

### change-set-spans-three-packages-and-breaks-two-tests | high | commit shape and unfinished consumer updates, for whoever implements

The uncommitted routing change is coherent in itself but incomplete, and its
commit shape is constrained.

It cannot be committed per-package. `src/cadrumo/application/filing/` imports
`registry_scalar_value_type` and `validate_registry_text_scalar`, both verified
absent at `HEAD`; they are uncommitted additions in
`src/cadrumo/domain/calculations/registry/_schema_scalars.py`. Committing the
application layer alone yields an unimportable `HEAD`. The set also carries the
`min_value`/`max_value` to `CasillaConstraints` widening in
`src/cadrumo/domain/filing/_protocols.py` and `_validator.py`, plus
`_formula_text_inputs.py` and `_formula_runtime.py` in the registry package.

It breaks two pre-existing tests in its own package that were not updated. A
real run reported `2 failed, 276 passed in 151.40s`, both failures in
`test_build_draft_conditional_formula_trace.py`
(`test_conditional_computed_casilla_trace_equals_declared_formula_inputs` and
`test_modelo_303_first_period_draft_reaches_listo_para_presentar`), both raising
`ModeloBuilderError: text casilla input 'decl.periodo' must be a string`.
Attribution is certain by mechanism rather than by timing: both tracebacks run
through the changed call site in `src/cadrumo/application/filing/__init__.py`,
which the previous routing could not have reached.

No live editor owned the area during the investigation. The working-tree diff
was byte-identical across three hashed samples spanning eight minutes, and the
last commit touching the area predated the session by twelve hours.

## Recommendations

### The remedy, and why it is a decision rather than a fix

Make the informational filing-period casilla carry the canonical period token
on the text channel instead of the ordinal on the decimal channel — that is,
supply `period.registry_token` (`"1T"`) rather than
`Decimal(period.declaration_period_ordinal)` (`1`). This satisfies the
casilla's declared `period_code` type, matches the AEAT quarterly form, and
extends to the OSS extended forms the ordinal cannot express.

The cost is what makes this an operator decision rather than a routine fix.
The persisted type of a casilla changes from `Decimal` to `str` inside
`CalculationRevision.casilla_values`. That is a persistence-boundary change: it
touches the encrypted revision envelope, the observation records that carry the
same value with its legal grounding, and the replay path that stringifies
informational casillas. Whoever implements should expect roundtrip and
anti-tautology coverage at that boundary to need attention, not just the
assertion updates listed below.

Dependent work in the same change, so the commit is coherent:

- Update `test_declaration_period_binding.py`, whose parametrised assertions
  pin `Decimal("1")` through `Decimal("4")` and whose docstring asserts the
  ordinal is the intended representation.
- Update the two failing tests in
  `test_build_draft_conditional_formula_trace.py`.
- Land the three-package routing set as one commit, since the application layer
  does not import without the registry additions.
- Only then refresh the affected cli-sequence goldens, where `decl.periodo`
  legitimately moves from `'1'` to `'1T'` (54 occurrences) and `'2'`/`'3'`/`'4'`
  to `'2T'`/`'3T'`/`'4T'`.

The docs publish unblocks as a consequence of the code fix. It cannot be
unblocked ahead of it.

### An architectural question a follow-on ADR should settle

Whether per-type validator dispatch may be keyed on a literal member of a type
family at all, or must derive its membership from the type taxonomy. This
instance was routed by `data_type == "text"` while the taxonomy holds twelve
text-family types; every other member silently bypassed its validator. The
decision belongs in an ADR, not here.

### Grounding boundary

The regulatory reading rests on the registry declaration, its explicit label,
the `_validate_period_code` accepted-form set, and RD 1624/1992 art. 71 as
cited in the casilla's own `legal_refs`. The one element not established from
the tree — external confirmation of the AEAT Modelo 303 período field format —
was confirmed against public AEAT documentation by the coordinator on
2026-08-01: quarterly periods are `1T`–`4T`. The boundary is closed and the
reading requires no second reader.

No rule promotion is proposed. Codification was retired by operator directive;
the defect class recorded under the second finding is deliberately kept as an
audit record.
