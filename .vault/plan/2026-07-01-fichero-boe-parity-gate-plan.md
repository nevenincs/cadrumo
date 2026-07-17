---
tags:
  - '#plan'
  - '#fichero-boe-parity-gate'
date: '2026-07-01'
modified: '2026-07-17'
tier: L2
related:
  - '[[2026-07-01-fichero-boe-parity-gate-adr]]'
  - '[[2026-07-01-fichero-boe-parity-gate-research]]'
---

# `fichero-boe-parity-gate` plan

### Phase `P01` - Registry manifest projection

Make the completeness manifest reachable at the fichero-BOE render choke point by projecting it onto the export subview.

- [x] `P01.S01` - Add a completeness_manifest field to RegistryModeloSubview; `src/aeat/application/filing/runtime.py`.
- [x] `P01.S02` - Populate completeness_manifest in _subview_from_snapshot from snapshot.revision.completeness_manifest; `src/aeat/application/filing/runtime.py`.
- [x] `P01.S03` - Roundtrip-test that the export subview carries the revision completeness manifest; `src/aeat/application/filing/tests/test_runtime_subview_manifest.py`.

### Phase `P02` - Rendered-set and applicable-required derivation

Derive the on-disk rendered casilla set across all casilla-bearing field kinds and the manifest required set restricted to casillas representable in an applicable non-suppressed record.

- [x] `P02.S04` - Widen the rendered casilla-set derivation to enumerate every casilla-bearing field kind that reaches disk; `src/aeat/application/filing/_export.py`.
- [x] `P02.S05` - Add a helper for the manifest required set restricted to casillas representable in an applicable non-suppressed record, carrying number, segmento and record-order metadata; `src/aeat/application/filing/_export.py`.
- [x] `P02.S06` - Unit-test the rendered-set enumeration across CASILLA, BINDING-row and COMPUTED field kinds; `src/aeat/application/filing/tests/test_export_rendered_casilla_set.py`.
- [x] `P02.S07` - Unit-test the applicable-required restriction drops disposition-suppressed casillas; `src/aeat/application/filing/tests/test_export_applicable_required_set.py`.

### Phase `P03` - Automatic pre-write parity assertion and coverage honesty

Assert required-applicable subset of rendered before any bytes are written, hard-failing on a shortfall, and surface a non-blocking coverage advisory when the manifest is absent or partial.

- [x] `P03.S08` - Insert a pre-write presence assertion in export_draft that required-applicable casillas are a subset of the on-disk rendered set, raising a hard FilingExportError before write_bytes; `src/aeat/application/filing/_export.py`.
- [x] `P03.S09` - Add a pre-write structural-fidelity assertion that every rendered casilla number and segmento matches the registry-declared metadata with zero drift; `src/aeat/application/filing/_export.py`.
- [x] `P03.S10` - Add a pre-write record and section-order assertion that the rendered record order follows the registry declaration order; `src/aeat/application/filing/_export.py`.
- [x] `P03.S11` - Make the panic loud and explicit by enumerating every drifted casilla with expected-versus-actual number, segmento, order and presence in the error; `src/aeat/application/filing/_export.py`.
- [x] `P03.S12` - Emit a non-blocking loud coverage advisory Notice when the completeness manifest is absent or manual_extraction; `src/aeat/application/filing/_export.py`.
- [x] `P03.S13` - Surface the coverage advisory and propagate the hard parity error on the export_modelo_revision envelope; `src/aeat/application/modelo/_export.py`.
- [x] `P03.S14` - Register locale keys for the parity panic error and the coverage advisory via the locales CLI; `src/aeat/locales/en.yml`.

### Phase `P04` - CI parity regression test

Lock the runtime assertion with an offline fichero-BOE parity test mirroring the workbook gate, including a disposition-suppressed case.

- [x] `P04.S15` - Add an offline fichero-BOE parity test asserting required-applicable casillas reach disk across export-capable covered modelos; `src/aeat/application/filing/tests/test_fichero_boe_completeness_parity.py`.
- [x] `P04.S16` - Assert rendered numbering, segmento and record order fidelity in the fichero-BOE parity test; `src/aeat/application/filing/tests/test_fichero_boe_completeness_parity.py`.
- [x] `P04.S17` - Add a disposition-suppressed case proving the applicable restriction prevents a false panic on a non-refund draft; `src/aeat/application/filing/tests/test_fichero_boe_completeness_parity.py`.
- [x] `P04.S18` - Add an anti-tautology drift case mutating a rendered field number or order and asserting the gate panics; `src/aeat/application/filing/tests/test_fichero_boe_completeness_parity.py`.

### Phase `P05` - Rule codification

Extend the modelo-export-mirrors-official-structure rule to bind the fichero-BOE transport, gated on a green parity gate.

- [x] `P05.S19` - Extend the modelo-export-mirrors-official-structure rule source to bind the fichero-BOE transport and mandate full-structure mirror-or-panic, then run vaultspec-core sync; `.vaultspec/rules/rules/modelo-export-mirrors-official-structure.md`.
- [x] `P05.S20` - Run the filing and modelo export test suites plus src/aeat collect-only and capture a green owner-scoped gate; `src/aeat/application/filing/tests`.

## Description

Extend the `modelo-export-mirrors-official-structure` parity gate to the
fichero-BOE (`.boe`) export so a `.boe` cannot be structurally thin or drifted
yet still pass clean. The gate is wired only for the workbook export today; the
`.boe` renderer has no manifest-grounded completeness or structure check, and its
`sha256` digest validates a byte-shaped-but-thin file. The accepted ADR resolves
the four decisions this plan executes: project the completeness manifest onto the
export subview (P01) so the render choke point can reach it; derive the on-disk
rendered casilla set across all field kinds and the applicable required set (P02);
add automatic pre-write assertions that the rendered `.boe` mirrors the real
targeted modelo-revision structure - casilla presence, numbering, segmento, and
record/section order - hard-failing into loud, explicit panic on any drift, with a
non-blocking coverage advisory only where no manifest exists (P03); lock it with an
offline parity plus anti-tautology drift regression test (P04); and codify the
rule extension once green (P05). The operator is an autonomous LLM tax-advisor
producing a `.boe` for a human to upload, so structural drift must be a hard,
enumerated failure at export time, never a warning. Grounded in the feature ADR
and research linked in this plan's `related:` frontmatter; reuses the workbook
gate and completeness manifest rather than rebuilding them. The
evidence-bytes-by-id export gap is out of scope (owned by the bucket-custody-
completeness brief).

## Steps

## Parallelization

The phases carry hard ordering: P02 depends on P01 (the derivation helpers read
`subview.completeness_manifest`); P03 depends on P02 (the assertions consume the
rendered-set and applicable-required helpers); P04 depends on P03 (the regression
test exercises the live assertions); P05 depends on P04 being green (codify only
after the gate holds). Within a phase, the implementation Steps precede their
paired test Steps. P01.S01 and P01.S02 are one edit surface and land together;
P03.S08 through S11 are one assertion surface and are best implemented as one
coherent change with S12 through S14 following. The disposition-suppressed case
(P04.S17) and the drift anti-tautology case (P04.S18) are independent and may be
authored in parallel once P04.S15 exists.

## Verification

The plan is complete when every Step is closed and each criterion below is a
passing check:

- The export subview carries the revision `completeness_manifest`, proven by the
  P01 roundtrip test.
- Exporting a `.boe` for a manifest-bearing draft that omits a required-applicable
  casilla raises a hard `FilingExportError` before any bytes are written, and the
  error enumerates every drifted casilla with expected-versus-actual number,
  segmento, order, and presence (P03 assertions; P04 tests).
- Rendered casilla numbering, segmento, and record/section order match the
  registry-declared structure for every export-capable covered modelo; any drift
  panics (P04 fidelity and anti-tautology drift tests).
- A disposition-suppressed record (non-refund draft dropping the DID page) does not
  trigger a false panic (P04 suppressed-disposition test).
- A draft whose revision has no completeness manifest exports with a non-blocking,
  operator-visible coverage advisory `Notice` and never a silent pass (P03).
- The M303/M130 golden-SHA and existing fichero-BOE roundtrip tests remain green
  (the assertions are read-only pre-write and do not alter rendered bytes).
- The filing and modelo export suites plus `src/aeat` collect-only are green,
  owner-triaged (P05.S20).
- The `modelo-export-mirrors-official-structure` rule binds the fichero-BOE
  transport after `vaultspec-core sync` (P05.S19).
