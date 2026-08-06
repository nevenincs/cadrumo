---
tags:
  - '#audit'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:bb3a9df0320c08ad0ccc73b545dc04d3f2ff0a54ec310c44aba36ccdde00fe86'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# `fichero-boe-parity-gate` audit: `fichero-BOE parity gate execution status`

## Scope

Honest execution-status record for the fichero-BOE parity gate after P01-P04
landed, distinguishing completed work from deferred and reframed plan Steps, so
plan-step closure is backed by evidence and the remaining surface is explicit.
Companion to the per-Step exec records; this audit is the deferral register the
`plan-closure-requires-exec-records` rule calls for.

## Findings

### landed-and-tested | low | P01-P04 core gate is committed, green, and regression-locked

The pre-write completeness gate is landed across four commits (`807a55eb9` P01
subview manifest projection, `0eaefcc98` P02 representable/rendered derivation,
`db7eda99d` P03 panic core, `e616666ad` P04 multi-modelo parity lock). Seventeen
feature tests pass in isolation. The gate raises a hard `FilingExportError`
before any bytes are written when a fixed-width `.boe` would omit a required,
representable casilla, enumerating each missing casilla with its number and
segmento. It is scoped to `layout.format == "fixed_width"` (the fichero-BOE DR
format); xml_dictionary exports are excluded because an absent casilla is a
legitimately-absent optional element, not a blank slot.

### reframed-numbering-segmento | low | P03.S09 satisfied by the panic message, not a separate assertion

The plan Step called for a runtime assertion that each rendered casilla's number
and segmento match the registry-declared metadata. This is redundant: the
registry manifest validator already cross-checks manifest metadata against the
casilla at registry-build. The intent is met by enumerating number and segmento
in the panic message (P03.S11), giving the operator the structural identity of
each drift without a tautological runtime re-check. Step left unchecked; intent
delivered.

### reframed-record-order | low | P03.S10 record-order fidelity moved to offline analysis, not a runtime check

A runtime "records emitted in registry-declared order" assertion is tautological:
the renderer sorts records by `record.order` before emitting, so a runtime
monotonicity check can never fail. True order-fidelity (does the layout's declared
order match the official Diseno) is a registry-authoring property, not an
export-time one. Step left unchecked as a deliberate no-tautological-tests
decision; no runtime order gate was added.

### deferred-coverage-advisory | medium | P03.S12-S14 blocked by active peer WIP on _export.py

The coverage advisory (a non-blocking `Notice` when a fixed-width `.boe` revision
declares no completeness manifest, so the operator learns the export was not
completeness-verified) is not implemented. It requires editing
`application/filing/_export.py`, `application/modelo/_export.py`, the CLI export
command, and adding locale keys in four languages. `_export.py` carries active
uncommitted peer WIP (an import-centralization refactor), so per
`uncommitted-wip-is-not-orphaned` the edit is deferred until that WIP commits, to
land via the apply-cached drive or a clean commit. The panic path (the actual
under-declaration defect) is unaffected; the advisory is honesty polish for the
manifest-absent case.

### reframed-parity-fidelity | low | P04.S16 delivered as a non-vacuous guard, not order fidelity

The parity test asserts `required_applicable` is non-empty per covered modelo (the
gate is genuinely active, never vacuously passing) alongside the subset parity.
Full numbering/segmento/order fidelity in the test was not added, consistent with
the reframing above. Step left unchecked; the non-vacuous guard is committed.

### owner-triage-peer-circular-import | low | the src/aeat collect gate is red from unrelated peer WIP

The broad owner-gate run (P05.S20) hit a circular-import collection error in
`aeat.application.workflow` (`WorkflowEvent`), surfaced through the modelo tests.
`workflow/_models.py`, `review/_actions.py`, `modelo/_action_errors.py` and
siblings all carry uncommitted peer changes; the import cycle is theirs, not this
feature's. The filing owner surface is green in isolation (17 feature tests plus
the existing filing export suite). Per `full-tree-gate-must-distinguish-owner`,
this is peer churn, not an owner regression; the collect-only gate stays open
until the peer refactor settles.

### code-review-critical-empty-kind | critical | the shipped gate keyed on id membership, not value presence — fixed in the working tree, commit blocked

The dispatched `vaultspec-code-review` found a CONFIRMED critical defect in the
committed gate (`db7eda99d`): `rendered_casilla_ids` computed
`{value.casilla_id for value in draft.values}` and intersected it with the
representable set. But `build_draft` emits a `ModeloValue` row for EVERY declared
casilla, marking an unsupplied one `EMPTY` (`value=None`). So casilla-id membership
in `draft.values` is the full declared set, not the valued set: an `EMPTY`,
manifest-required, schema-optional casilla (e.g. M130 `06`) counted as "rendered,"
the gate's `missing` set came up empty, and the export succeeded with a valid
digest -- exactly the structurally-thin file the gate exists to refuse. The
reviewer reproduced it end-to-end on M130 casillas `06`/`08`/`10`/`16`/`18`. The
paired test (`test_thin_fixed_width_draft_panics_before_writing`) was tautological
w.r.t. the real bug: it removed the `ModeloValue` tuple entry (an unreachable
state) instead of emptying it. Fix: `rendered_casilla_ids` filters
`value.value is not None` (value is None iff `kind == EMPTY`, per the `ModeloValue`
contract); the test now empties a required-applicable casilla (the real production
state) and asserts the panic. Fourteen filing tests pass with the fix, including
the corrected thin-draft test and the P04 parity (complete drafts still reach disk;
zeros are real values, only `EMPTY` is excluded). STATUS: fix implemented and
tested in the working tree; the commit is blocked because a concurrent peer has 238
files staged in the shared index (a codebase-wide import-centralization sweep,
including `_export.py`). Committing now would sweep peer work, so the fix lands via
the apply-cached drive once that changeset commits and the index clears. The
committed gate is currently ineffective (it never fires on the real thin state) but
causes no active harm: it does not false-panic and writes nothing incorrect.

RESOLUTION: the fix LANDED. The value-presence code fix was co-committed into a
concurrent peer import-centralization commit (`3c1748da7`, which swept the
working-tree change via `git commit -a`) -- verified intact in HEAD. The
strengthened test (emptying a required-applicable casilla in place to reproduce the
real `EMPTY` state) landed cleanly via pathspec (`2488ef810`). All 17 feature tests
pass against HEAD. The gate now fires on the real production thin state. No peer
work was swept by this feature (the peer's 238-file changeset committed on its own;
my reverse-apply left their index intact throughout).

### code-review-medium-row-field | medium | dormant false-panic vector via row_field_casilla_ids

`boe_representable_casilla_ids` unions `record.row_field_casilla_ids.values()` into
the representable set, but those casillas are materialised from `binding_values`,
never `draft.values`, so `rendered_casilla_ids` can never see them. A
manifest-required casilla whose only representable route is a `row_field_casilla_ids`
mapping would show permanently missing and false-panic on every export. Currently
dormant: no shipped registry revision has a manifest-required casilla routed solely
through `row_field_casilla_ids` (confirmed across 130/111/115/123/131). Follow-up:
either extend the rendered computation to count binding-materialised row casillas,
or add a registry-build validator forbidding a manifest-required casilla from being
row_field-only.

### code-review-medium-coverage | low | RESOLVED in substance — the gate is exercised on every fixed-width export test

The gate runs unconditionally inside `export_draft` for every fixed-width,
manifest-bearing modelo, so it is exercised by ALL the existing fixed-width export
tests in `test_export.py` (130/111/115/123/131/200/303/…), every one of which
passes with the gate active — including modelo 200 (sociedades,
`test_export_writes_modelo_200_negative_cuota_diferencial_as_signed_money`) and 303
(IVA, the roundtrip test). So the concern that "the gate is unverified on 8 shipped
modelos" is resolved in substance: a complete draft that trips the gate would fail
those tests. The P04 parity file now covers 130/111/115/123/131/**200** (a complete Modelo 200
sociedades draft fixture was added, with its 2024/0A provider) and the fichero-BOE
roundtrip covers 130/303 — the ADDITIONAL explicit invariant assertions on top of
the whole-suite exercise. The only remaining nicety is a dedicated explicit-parity
assertion for the informativas (`180 202 232 349 720`); the gate is already
validated on every fixed-width export test, so this is genuinely optional.

### code-review-medium-coverage-historic | low | (superseded) P04 draft-based lock covers 5 of 12; dormancy lock covers 7

Twelve fixed-width modelos carry a completeness manifest and are gated in
production (`111 115 123 130 131 180 200 202 232 303 349 720`). Effective gate
coverage on COMPLETE drafts is broader than the P04 parity file alone: the P04
parity lock covers `130 111 115 123 131` (131 added after the truth-grounded gate
landed), and the fichero-BOE roundtrip test independently exercises `export_draft`
under the gate on complete `130` and `303` drafts (byte-roundtrip through the
parser). So `303` (IVA) is genuinely validated under the gate despite not being in
the P04 parity file. The structural row_field dormancy lock covers `130 111 115 123
131 303 200`. The genuine remaining gap is a complete-draft export test for `200`
(sociedades) and the informativas `180 202 232 349 720`; `200` is exercised
structurally by the dormancy lock but has no complete-draft gate test. Follow-up.

### truth-grounded-required-set | high | RESOLVED — the gate requires computed/schema-required casillas, not optional inputs

The value-presence fix (correct for computed casillas) over-corrected: it required
EVERY manifest ∩ representable casilla to carry a value, which broke the existing
`test_export_writes_modelo_131_binding_derived_layout` at HEAD (a real regression).
Grounded in the AEAT casilla semantics rather than guessed: Modelo 131 manifest
casillas 02/08/09/12/14 are `Pago fraccionado previo por datos-base`, `Retenciones
e ingresos a cuenta`, `Minoración por rendimientos netos`, `Pago de préstamos para
vivienda habitual`, and `Resultado a ingresar de autoliquidaciones anteriores` --
all OPTIONAL operator inputs a taxpayer may legitimately not have, so a blank slot
is a valid zero, not a thin file. Probed across the covered modelos: manifest
casillas are a mix of computed results (formula) and optional inputs (131 = 7
computed + 8 optional; 130 = 12 computed + 1 schema-required + 7 optional; etc.),
and every complete fixture populates its computed casillas. The gate now restricts
the required set to casillas that declare a formula (calculation RESULTS) or are
schema-required, using `schema_provider.get_collection(modelo)`; optional inputs
are excluded. This keeps the real thin-file protection (a blank computed result
means the calc did not run) while eliminating the false-panic on optional inputs.
The 131 regression is fixed (its 7 computed casillas are populated), and the full
filing export surface is green (64 tests). The gate test now empties a computed
casilla to reproduce a real thin file, and the parity test mirrors the restricted
required set. This also downgrades the row_field-only vector further: an optional
row_field-only casilla is now excluded by the computed/required filter too.

### manifest-classification-audit | low | the gate's required-set classification is sound across all 12 gated modelos

A systematic classification audit ran over every manifest-bearing gated modelo
(130 111 115 123 131 303 200 190 180 349 232 720), categorising each manifest
casilla by `input_kind` (COMPUTED / BOUND / MANUAL / INFORMATIONAL) against the
gate's `formula-or-schema-required` predicate. Findings, all confirming the design:
(1) the registry validator ties `COMPUTED` one-to-one to declaring a formula, so
the gate's formula check is exactly the COMPUTED set. (2) The `required` flag
correctly OVERRIDES `input_kind`: a mandatory field is gated whatever its
provenance -- Modelo 349's four intracom operation totals are BOUND yet
schema-required (so gated), and Modelo 232/720's `ejercicio`/`CNAE` are
INFORMATIONAL yet schema-required (so gated). This means NO gated modelo has a
vacuous gate; each requires at least its mandatory fields (an initial assumption
that 349/232/720 were vacuous was wrong -- they require their mandatory metadata).
(3) The gate excludes only NON-required, NON-computed casillas: optional BOUND
ledger-materialised values (Modelo 303 IVA cuotas repercutido/soportado/
autorepercutido, Modelo 130 retenciones), optional MANUAL inputs, and non-required
INFORMATIONAL fields -- all legitimately zero/blank when the taxpayer has no such
operations, so requiring them would false-panic on a valid zero-data filing. No
mis-classification (e.g. a formula casilla mis-marked MANUAL) was found. The
classification is now locked by `test_manifest_classification.py` (36 cases) in
both drift directions -- under-strict (a COMPUTED/required casilla dropped) and
over-strict (an optional casilla added).

### workbook-boe-consistency | low | the two export transports are grounded in one calculation surface

The `modelo-export-mirrors-official-structure` rule binds both export transports
(the workbook plan and the fichero-BOE). A cross-transport consistency probe over
the fixed-width modelos confirms the containment invariant `boe_representable ⊆
workbook_emitted` holds with zero orphans for 130/111/115/200: the fichero-BOE
never files a casilla the workbook does not compute, so a value on disk in the
`.boe` is always grounded in the same calculation the workbook renders. The reverse
does not hold and is not asserted -- the workbook is the full calculation surface
and legitimately emits internal carries the DR record omits (e.g. Modelo 130
`saldo-negativo-fin-periodo`, present in the workbook and manifest but not
representable in the `.boe`). Locked by `test_workbook_boe_consistency.py`.

### workbook-303-modulos-gap | medium | RESOLVED — the workbook now renders Modelo 303 2025 módulos

The consistency slice surfaced a real, pre-existing workbook regression: the Modelo
303 2025 revision's módulos-IVA coefficients are a `keyed_bracket_table` parameter
(keyed by epígrafe:módulo) consumed by a keyed-lookup formula, and the calc-sheets
workbook engine supports neither. `build_export_plan("303")` failed two ways: (1)
`_tariff_tables` called `_resolve_scalar` on the keyed_bracket_table tariff anchor
before its non-scalar skip-check, crashing the whole export -- fixed in
`e00f0d800c` by skipping non-scalar types before scalar resolution; and (2) the
keyed-lookup formula cannot be translated to a spreadsheet formula
(`TranslationError` in `_translator`). RESOLUTION (`7e5900da84`): the second failure
was NOT a missing keyed-lookup translation feature but a transitive-exclusion bug.
The engine already omits untranslatable `internal_only` advisory casillas from the
export (`_untranslatable_internal_only_casillas`), but it probed translatability
against a layout with every casilla present, so it caught
`modulos-iva-cuota-devengada` (custom op, untranslatable regardless of layout) but
missed `modulos-iva-cuota-derivada` (a `max` over it) -- which only becomes
untranslatable once the dependency's cell is excluded. `_formula_cells` then crashed
translating that `max`'s reference to a missing cell. Computing the exclusion to a
fixpoint (rebuild the probe layout with the exclusions found so far, re-check until
none newly fails) omits both módulos casillas, both `internal_only` advisory-support
figures the official DR record does not file. The 303 workbook now builds and passes
the parity gate, and 303 is included in the workbook<->fichero-BOE consistency lock.
The broader calc-sheets suite (75 tests) stays green. No keyed-table workbook
rendering was needed -- the design already intends these casillas to be omitted; the
bug was only that the omission was not transitive. Verified across FILING YEARS: the
303 workbook builds and the boe-subset-of-workbook invariant holds for 2022
(2009-y-siguientes revision, no módulos surface) through 2026 (2023-y-siguientes,
módulos omitted for every year 2023/2024/2025/2026); the parity and consistency
gates were widened to span these years and revision boundaries (26 consistency + 27
parity cases). So the fix is not 2025-specific -- it covers every year each 303
revision serves.

## Recommendations

- Correct the codified `modelo-export-mirrors-official-structure` rule text to say
  the fichero-BOE gate requires calculation RESULTS and schema-required casillas
  (not every manifest casilla), matching the truth-grounded implementation.
- Land the coverage advisory (P03.S12-S14) once the peer `_export.py` WIP commits,
  routing the manifest-absent signal through the typed `Notice` channel and adding
  the locale keys via the locales CLI.
- Re-run the `src/aeat` collect-only gate after the peer workflow/review refactor
  commits to confirm the circular import clears; it is not this feature's to fix.
- Codify the `modelo-export-mirrors-official-structure` rule extension (P05.S19) to
  bind the fichero-BOE transport after the code review closes.
- Address any findings the dispatched `vaultspec-code-review` returns before
  declaring the feature structurally complete.
