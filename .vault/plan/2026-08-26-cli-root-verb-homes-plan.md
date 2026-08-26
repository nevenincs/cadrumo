---
tags:
  - '#plan'
  - '#cli-root-verb-homes'
date: '2026-08-26'
tier: L3
related:
  - '[[2026-08-26-cli-root-verb-homes-adr]]'
  - '[[2026-08-25-cli-root-verb-homes-audit]]'
modified: '2026-08-26'
body_schema: body-v2
body_hash: 'sha256:1f2b6494327899799c3aff4b863403637b47c4be544651e195277c3a5201037c'
---

# `cli-root-verb-homes` plan

## Description

## Steps

## Wave `W01` - Declared transport locus

Add the ParameterSpec annotation the D3 spelling gate requires. Until a parameter declares whether it carries a local path or a remote handle, any spelling gate is a name list rather than a property. Nothing renames in this wave.

### Phase `W01.P01` - Locus annotation

Define the closed locus and shape enums in core and carry them on the parameter spec, validated at spec construction.

- [x] `W01.P01.S01` - Define TransportLocus and TransportShape closed enums; `src/cadrumo/core/`.
- [x] `W01.P01.S02` - Carry locus and shape on OptionSpec and ArgumentSpec, validated at construction; `src/cadrumo/entrypoints/cli/_command_spec.py`.

### Phase `W01.P02` - Locus declaration sweep

Declare a locus on all 55 Path-typed parameters and every remote-handle parameter, then gate that a path or handle parameter without a declared locus cannot be constructed.

- [x] `W01.P02.S03` - Declare locus and shape on all 55 Path-typed parameters; `src/cadrumo/entrypoints/cli/`.
- [x] `W01.P02.S04` - Declare remote-handle locus on folder, reference and spreadsheet-id parameters; `src/cadrumo/entrypoints/cli/`.
- [x] `W01.P02.S05` - Gate that a path-bearing or handle-bearing parameter without a declared locus cannot be constructed, and prove it bites; `src/cadrumo/entrypoints/cli/tests/`.

## Wave `W02` - Placement re-homes

Execute D1's two refusals: the workbook subject moves to app, the one-verb maintenance family moves to config. Land the placement gate that encodes D1 at narrowest-subject granularity.

### Phase `W02.P03` - Workbook subject move

Move config google sync calc to app modelo spreadsheet, renaming export to push and compute to calculate, adopting canonical defining-module imports on the way.

- [ ] `W02.P03.S06` - Move the four sync calc leaves to app modelo spreadsheet with push and calculate renames; `src/cadrumo/entrypoints/cli/`.
- [ ] `W02.P03.S07` - Replace facade imports with canonical defining-module imports in the moved handlers; `src/cadrumo/entrypoints/cli/`.
- [ ] `W02.P03.S08` - Re-key the four envelope command identifiers and their result schemas; `src/cadrumo/entrypoints/cli/`.
- [ ] `W02.P03.S09` - Move the sync calc locale keys to the new namespace in all four catalogues; `src/cadrumo/locales/`.

### Phase `W02.P04` - Maintenance family move

Fold app maintenance reconcile into config repair and retire the one-verb family.

- [x] `W02.P04.S10` - Fold app maintenance reconcile into config repair and retire the family; `src/cadrumo/entrypoints/cli/`.
- [x] `W02.P04.S11` - Update the operator-actions catalogue target command key; `src/cadrumo/application/operator_actions/`.

### Phase `W02.P05` - Placement gate

Land D6 gate one at narrowest-subject granularity, scoped to refusal only, and prove it bites.

- [ ] `W02.P05.S12` - Land the placement gate encoding D1 at narrowest-subject granularity; `src/cadrumo/entrypoints/cli/tests/`.
- [ ] `W02.P05.S13` - Prove the placement gate bites by mounting a filing leaf under config from outside the repository; `src/cadrumo/entrypoints/cli/tests/`.

## Wave `W03` - Transport verb and subject renames

Apply the D2 counterparty grammar and the D4 collision rulings across every affected family. Each rename is a hard cutover with its envelope identifier, locale keys and gate-covered goldens in one commit.

### Phase `W03.P06` - Custody backup subjects

Split the custody backup surface by blast radius: archive keeps the recoverable local pair, the whole-corpus Drive mirror becomes its own mirror subject.

- [ ] `W03.P06.S14` - Rename config profile restore to config profile archive import; `src/cadrumo/entrypoints/cli/_config/`.
- [ ] `W03.P06.S15` - Move config google sync push to config profile mirror push; `src/cadrumo/entrypoints/cli/_config/`.
- [ ] `W03.P06.S16` - Update the bootstrap-exempt and login-gated verb paths and resolve the stale config profile export entry; `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`.

### Phase `W03.P07` - Ledger evidence intake

Move remote evidence intake into the evidence subgroup as pull and pull-all, retaining the source enum untouched.

- [ ] `W03.P07.S17` - Rename app ledger doclink to app ledger evidence pull, retaining the source enum; `src/cadrumo/entrypoints/cli/`.
- [ ] `W03.P07.S18` - Rename app ledger pull-folder to app ledger evidence pull-all; `src/cadrumo/entrypoints/cli/`.

### Phase `W03.P08` - File token renames

Rename the two transport uses of the file token to import so file retains only its filing meaning.

- [ ] `W03.P08.S19` - Rename app modelo reconcile file to reconcile import; `src/cadrumo/entrypoints/cli/`.
- [ ] `W03.P08.S20` - Rename config profile censo file to censo import; `src/cadrumo/entrypoints/cli/_config/`.

### Phase `W03.P09` - Primary and auxiliary local inputs

Apply the D3 role axis to the two non-conformant leaves.

- [ ] `W03.P09.S21` - Convert review-package import-feedback package option to a positional subject; `src/cadrumo/entrypoints/cli/`.
- [ ] `W03.P09.S22` - Declare which of archive import file and artifact is the primary local input; `src/cadrumo/entrypoints/cli/_config/`.

## Wave `W04` - Retirements

Remove the three duplicated surfaces D5 rules out, each conditional on its named precondition being verified first.

### Phase `W04.P10` - Registry integrity retirement

Retire config repair integrity registry in favour of app registry verify, having first proven the reports coincide.

- [ ] `W04.P10.S23` - Prove config repair integrity registry and app registry verify report the same authority state; `src/cadrumo/entrypoints/cli/tests/`.
- [ ] `W04.P10.S24` - Retire config repair integrity registry; `src/cadrumo/entrypoints/cli/_config/`.

### Phase `W04.P11` - Preflight retirement

Make readiness revision-id optional with law-determined resolution and adopt the exit-2 contract, then retire config profile preflight and re-point every calling sequence contract.

- [ ] `W04.P11.S25` - Make app modelo readiness revision-id optional with law-determined resolution; `src/cadrumo/entrypoints/cli/_modelo_readiness_command_specs.py`.
- [ ] `W04.P11.S26` - Adopt the exit-2 missing-field contract on app modelo readiness; `src/cadrumo/entrypoints/cli/`.
- [ ] `W04.P11.S27` - Retire config profile preflight and re-point the ten calling sequence contracts; `src/cadrumo/entrypoints/cli/_config/`.

## Wave `W05` - Gates, rule amendment and charter

Land the D6 spelling gate on top of the W01 annotation, amend the aeat-cli-contract rule sentences D7 enumerates, correct the root help strings, and verify every unscanned sweep surface.

### Phase `W05.P12` - Spelling gate

Land D6 gate two over the declared locus and prove it bites.

- [ ] `W05.P12.S28` - Land the spelling gate over declared locus with path-and-function keyed exemptions and a staleness ratchet; `src/cadrumo/entrypoints/cli/tests/`.
- [ ] `W05.P12.S29` - Prove the spelling gate bites by mis-spelling a declared local-in file parameter; `src/cadrumo/entrypoints/cli/tests/`.

### Phase `W05.P13` - Rule and charter amendment

Amend the enumerated aeat-cli-contract sentences on the rule source, propagate by sync, and correct the two root help strings.

- [ ] `W05.P13.S30` - Amend the four enumerated aeat-cli-contract sentences on the rule source and propagate by sync; `.vaultspec/rules/aeat-cli-contract.md`.
- [ ] `W05.P13.S31` - Correct the config and app root help strings in all four catalogues; `src/cadrumo/locales/`.

### Phase `W05.P14` - Sweep verification

Verify every surface the conformance gates do not scan, and run the full suite sequentially.

- [ ] `W05.P14.S32` - Verify the gate-covered sequence contracts and their JSON goldens; `docs/_sequences/`.
- [ ] `W05.P14.S33` - Sweep the three non-gate-covered docs locale catalogues; `docs/locales/`.
- [ ] `W05.P14.S34` - Sweep the dev quality dispositions and CLI benchmark goldens; `dev/`.
- [ ] `W05.P14.S35` - Run the full suite sequentially and reconcile the vault; `src/cadrumo/`.

## Parallelization

## Verification
