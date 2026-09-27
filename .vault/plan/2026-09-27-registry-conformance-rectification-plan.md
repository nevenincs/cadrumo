---
tags:
  - '#plan'
  - '#registry-conformance-rectification'
date: '2026-09-27'
tier: L2
related:
  - '[[2026-09-23-assets-core-amortization-method-set-adr]]'
  - '[[2026-09-21-assets-core-lifecycle-contract-adr]]'
  - '[[2026-09-21-retenciones-workflow-observation-payment-contract-adr]]'
modified: '2026-09-27'
body_schema: body-v2
body_hash: 'sha256:e65618b468876f073c74c6f72fb28c8123f6f74eef34d368ad378498630b4720'
---

# `registry-conformance-rectification` plan

Bring the AEAT registry back to the delta-keyed, support-year-keyed standard and remove consumer and tool defects that pin single years.

## Description

Approved 2026-09-27. Basis: the operator's registry conformance rectification brief of 2026-09-27. It binds the registry standard (delta keyed against a baseline; keyed by the supported filing years, floor 2022; missing years temporally projected), and authorizes rectifying every deviation on a branch from `main`. It also directs the 2022 baseline for activity-asset amortization parameters and withholding recognition, keying only real yearly differences, and treats Renta 2022/2023 coverage as a conformance defect rather than a scope question. Items the brief marks for operator ruling are collected and returned, not decided here.

Decision coverage. Three accepted decisions bound tax year 2025 as the only filing-grade year and need amendment for the 2022 baseline: the amortization method set, the activity-asset lifecycle contract, and the withholding observation and payment contract. Each amendment extends the supported years and names the yearly divergences it keys; the accepted bodies are preserved and the amendment is appended once its grounded source and tests land. The tool fixes and the Modelo 100 relocation are routine execution within the registry authority flow, authoring and binding rules, and need no new decision. The export-parity withholding re-sourcing of Modelo 100 casillas 0596, 0597 and 0599 is owned by another branch and is out of scope; its bindings and the declarant-as-payer prefills stay unchanged.

The brief's audit is orientation only. Every finding is re-measured against the live tree and the dev tooling before any change, and each registry change cites its official AEAT or BOE evidence per year and is tested through the real compiled registry. Completion is reported separately for candidate validation, installed source, published authority and runtime adoption.

## Steps

### Phase `P01` - tool defects

Make the collapse verifier, the delta converter and the parity comparison measure the live authority and storage-baseline editions correctly, each with an isolated detector test.

- [x] `P01.S01` - Resolve the collapse verifier's published authority from the working-tree publication and add a scoped modelo filter; `dev/registry/registry_collapse_verification.py`.
- [ ] `P01.S02` - Let drop-restatement read storage-baseline editions, not only string predecessors; `dev/registry/edition_delta_migration.py`.
- [ ] `P01.S03` - Apply the filing schedule source reference default before comparing schedules; `dev/registry/registry_collapse_verification.py`.
- [x] `P01.S04` - Classify the indexed parity mapping-key order difference and fix the comparison or the ordering; `dev/registry/registry_collapse_verification.py`.
- [x] `P01.S13` - Compose export layouts and scope snapshots to the selected edition before the indexed parity comparison; `dev/registry/registry_collapse_verification.py`.

### Phase `P02` - Modelo 100 baseline relocation

Author the Modelo 100 identity, ledger and settlement chain, the amortization parameters and the root parameter windows at the earliest revision the law requires, keying only genuine divergences.

- [x] `P02.S05` - Author the identity, ledger and settlement chain members at 2022, with 0195 at 2023, and delete the later copies; `src/cadrumo/_data/registry/aeat/modelos/100/`.
- [x] `P02.S06` - Author the 2022 amortization parameter baseline and key the 2023, 2024 and 2025 divergences; `src/cadrumo/_data/registry/aeat/modelos/100/`.
- [x] `P02.S07` - Open the root parameter windows at their statutory dates and drop window-only restatements; `src/cadrumo/_data/registry/aeat/modelos/100/`.

### Phase `P03` - consumer year bounds

Replace hard-coded tax-year equality in consumers with canonical revision selection and grounded per-year rules.

- [ ] `P03.S08` - Select the activity-asset revision canonically instead of by tax-year equality; `src/cadrumo/domain/calculations/registry/actividad_asset_bindings.py`.
- [ ] `P03.S09` - Ground the Modelo 130 asset projection and withholding recognition for 2022 to 2024; `src/cadrumo/application/aggregation/`.
- [ ] `P03.S10` - Remove the Modelo 193 phase materialization year pin; `src/cadrumo/application/aggregation/m193_phase_materialization.py`.

### Phase `P04` - other modelos and rulings

Rectify verified late authoring and closed windows in other modelos, and return the collected ruling items to the operator.

- [ ] `P04.S11` - Rectify verified late authoring and closed windows per modelo, one writer each; `src/cadrumo/_data/registry/aeat/modelos/`.
- [ ] `P04.S12` - Amend the three governing decisions for the 2022 baseline and return the ruling list; `.vault/adr/`.

## Parallelization

Phase P01 (tool defects) and Phase P02 (Modelo 100) may proceed together; P02 Steps are ordered and share one writer. Phase P03 (consumer year bounds) follows the amortization Step of P02. Phase P04 (other modelos) runs after P02, with one writer per modelo. The year-named test scrub runs in an isolated worktree on test files only and merges before plan close; it excludes the test files P02 and P03 own.

## Verification

- Each rectified registry item carries per-year official citations and focused tests through the compiled registry, with unchanged hydration for the years it does not move.
- For every touched modelo, the edition delta converter is idempotent (a proof run, an apply run in a fresh directory, then a no-op run) and the collapse verifier reports the modelo clean.
- Candidate inspection is publication-valid, and the authoring inspection and compile-path boundary tests pass.
- `just check-registry`, `just check-bindings` and `just check-registry-gate` report no new failure against the `main` baseline, which on this host is clean with 18 unreferenced filing-grade binding warnings.
- The operator receives the collected ruling list, and the four completion boundaries are reported separately.
