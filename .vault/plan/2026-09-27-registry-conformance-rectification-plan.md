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
modified: '2026-09-29'
body_schema: body-v2
body_hash: 'sha256:5540eb900111a151b9719ffff2c62ed6f25d9fa51fbe24be7d565e859a138280'
---

# `registry-conformance-rectification` plan

Bring the AEAT registry back to the delta-keyed, support-year-keyed standard and remove consumer and tool defects that pin single years.

## Description

Approved 2026-09-27. Basis: the operator's registry conformance rectification brief of 2026-09-27. It binds the registry standard (delta keyed against a baseline; keyed by the supported filing years, floor 2022; missing years temporally projected), and authorizes rectifying every deviation on a branch from `main`. It also directs the 2022 baseline for activity-asset amortization parameters and withholding recognition, keying only real yearly differences, and treats Renta 2022/2023 coverage as a conformance defect rather than a scope question. Items the brief marks for operator ruling are collected and returned, not decided here.

Decision coverage. Three accepted decisions bound tax year 2025 as the only filing-grade year and need amendment for the 2022 baseline: the amortization method set, the activity-asset lifecycle contract, and the withholding observation and payment contract. Each amendment extends the supported years and names the yearly divergences it keys; the accepted bodies are preserved and the amendment is appended once its grounded source and tests land. The tool fixes and the Modelo 100 relocation are routine execution within the registry authority flow, authoring and binding rules, and need no new decision. The export-parity withholding re-sourcing of Modelo 100 casillas 0596, 0597 and 0599 is owned by another branch and is out of scope; its bindings and the declarant-as-payer prefills stay unchanged.

The brief's audit is orientation only. Every finding is re-measured against the live tree and the dev tooling before any change, and each registry change cites its official AEAT or BOE evidence per year and is tested through the real compiled registry. Completion is reported separately for candidate validation, installed source, published authority and runtime adoption.

Rulings, 2026-09-29. Basis: the operator delegated the returned rulings to this session on 2026-09-29, on condition that each respects the existing checks. Every registry ruling below is a decision procedure, not a verdict on tax facts: a member moves only where per-year official evidence grounds it, and where the evidence is missing or contradictory the current fail-closed or advisory state stands. None needs a new decision record; the ones touching the amortization method set stay inside its accepted amendment.

- D1, approved: the authority root is resolved without the profile pointer and storage root; the retired-state refusal keeps guarding every storage and profile access (P05.S14).
- D2, keep the fallback, provided each installed oracle reports the generation identity it read (P05.S15).
- D3, a passing run's scratch folder is removed at finish, a failing run's is kept as evidence, and the reaper still reclaims it (P05.S16).
- 1, upheld: Modelo 100 2022 casilla 0670 stays manual while the official dictionary contradicts the manual.
- 2, 3, 4, 7, 8 and 10: grounded per year under the late-authoring standard of P04.S11; dropped legal refs return by override where the provision still governs; the amending-law refs are enrolled from their BOE text; the 2024 electric-vehicle free depreciation refuses a tax period ending before 2024-06-28 if the product can represent one (P05.S17).
- 9, yes: the 2023 accelerated DA 18 regime gets its own refusal token; it stays outside the method set as the accepted amendment says (P05.S18).
- 6: each support-range cell is resolved by evidence as projection, a grounded delta edition, or the modelo's own later start; an unpublished release is reported as such and never authored ahead of AEAT (P05.S19).
- 11, upheld: 2026 refuses renewable free depreciation, as the accepted amendment requires for a year no authored edition covers.
- 12, upheld: the settled-row gate over-refuses rather than admitting a settled row.
- 13: Modelo 200's 2024 rows move to the edition 2024 resolves to; the 2025 root reuses storage and keys only its differences (P05.S20).
- 14: the option is removed, not kept as a refusal, because no compatibility floor is released (P05.S21).
- 15: every defect is reported, through the one projection path (P05.S22).
- 16: already resolved on `main`, which deleted the unwired linkage.
- 17, yes: a headroom refusal is respected by not loading the model, and the label reading stands with a visible notice, as for an unreachable runtime (P05.S23).
- 18: a capability marker excluded from every lane, a configured corpus root with no machine default, and a dedicated recipe that fails rather than skips (P05.S24).
- 5 (F2 and P1) is not ruled: its content is not in any persisted record.
- Found in P04.S11: Modelo 131's 2026 parameter rows open like every other edition's, as P02.S07 set and the support declaration's horizon requires, keying only the annual values such as the general reduction; its 2022 and 2023 modulos engine is authored once the modulos orden provisions are catalogued (P05.S26).
- Found in P04.S11: Modelo 190 and 193 extraction profiles stay undeclared for 2022 and 2023 until a printed specimen is captured, since the record design describes the file, not the PDF; the 2024 Modelo 193 perceptor count follows its design and counts records, and the 2024 Modelo 190 relation to Modelo 111 is grounded in 2024 instructions or loses filing grade (P05.S25).

## Steps

### Phase `P01` - tool defects

Make the collapse verifier, the delta converter and the parity comparison measure the live authority and storage-baseline editions correctly, each with an isolated detector test.

- [x] `P01.S01` - Resolve the collapse verifier's published authority from the working-tree publication and add a scoped modelo filter; `dev/registry/registry_collapse_verification.py`.
- [x] `P01.S02` - Let drop-restatement read storage-baseline editions, not only string predecessors; `dev/registry/edition_delta_migration.py`.
- [x] `P01.S03` - Apply the filing schedule source reference default before comparing schedules; `dev/registry/registry_collapse_verification.py`.
- [x] `P01.S04` - Classify the indexed parity mapping-key order difference and fix the comparison or the ordering; `dev/registry/registry_collapse_verification.py`.
- [x] `P01.S13` - Compose export layouts and scope snapshots to the selected edition before the indexed parity comparison; `dev/registry/registry_collapse_verification.py`.

### Phase `P02` - Modelo 100 baseline relocation

Author the Modelo 100 identity, ledger and settlement chain, the amortization parameters and the root parameter windows at the earliest revision the law requires, keying only genuine divergences.

- [x] `P02.S05` - Author the identity, ledger and settlement chain members at 2022, with 0195 at 2023, and delete the later copies; `src/cadrumo/_data/registry/aeat/modelos/100/`.
- [x] `P02.S06` - Author the 2022 amortization parameter baseline and key the 2023, 2024 and 2025 divergences; `src/cadrumo/_data/registry/aeat/modelos/100/`.
- [x] `P02.S07` - Open the root parameter windows at their statutory dates and drop window-only restatements; `src/cadrumo/_data/registry/aeat/modelos/100/`.

### Phase `P03` - consumer year bounds

Replace hard-coded tax-year equality in consumers with canonical revision selection and grounded per-year rules.

- [x] `P03.S08` - Select the activity-asset revision canonically instead of by tax-year equality; `src/cadrumo/domain/calculations/registry/actividad_asset_bindings.py`.
- [x] `P03.S09` - Ground the Modelo 130 asset projection and withholding recognition for 2022 to 2024; `src/cadrumo/application/aggregation/`.
- [x] `P03.S10` - Remove the Modelo 193 phase materialization year pin; `src/cadrumo/application/aggregation/m193_phase_materialization.py`.

### Phase `P04` - other modelos and rulings

Rectify verified late authoring and closed windows in other modelos, and return the collected ruling items to the operator.

- [ ] `P04.S11` - Rectify verified late authoring and closed windows per modelo, one writer each; `src/cadrumo/_data/registry/aeat/modelos/`.
- [x] `P04.S12` - Amend the three governing decisions for the 2022 baseline and return the ruling list; `.vault/adr/`.

### Phase `P05` - operator rulings

Implement the rulings the operator delegated on 2026-09-29, each within the existing gates: registry rulings grounded per year in official evidence and fail-closed where the evidence is ambiguous, code rulings through the owning boundary with focused tests.

- [x] `P05.S14` - Resolve the authority root without the profile and storage-root settings, so the MCP server and CLI boot beside retired aeat data (D1); `src/cadrumo/domain/calculations/registry/authority.py`.
- [x] `P05.S15` - Keep the installed-oracle authority fallback and prove each oracle names the generation it consumed (D2); `dev/packaging/tests/test_installed_oracles.py`.
- [ ] `P05.S16` - Remove a passing run's scratch folder when the run finishes and keep a failing run's (D3); `dev/test_runs/`.
- [ ] `P05.S17` - Ground the Modelo 100 late-authoring rulings per year: the 193 relation and renta-dep-193, the B4 and B5 items, the 0604 legal refs, the amending-law catalogue entries and the 2024 DA 18 period-end condition (rulings 2, 3, 4, 7, 8, 10); `src/cadrumo/_data/registry/aeat/modelos/100/`.
- [ ] `P05.S18` - Give the accelerated DA 18 regime its own refusal token (ruling 9); `src/cadrumo/domain/renta/actividad_asset/`.
- [ ] `P05.S19` - Resolve each support-range cell by evidence: projection, a grounded delta edition, or the modelo's own later start (ruling 6); `src/cadrumo/_data/registry/aeat/modelos/`.
- [ ] `P05.S20` - Relocate Modelo 200's 2024 rows to the edition 2024 resolves to and store the 2025 edition as a delta (ruling 13); `src/cadrumo/_data/registry/aeat/modelos/200/`.
- [ ] `P05.S21` - Remove the unpersisted --retencion-observation option (ruling 14); `src/cadrumo/entrypoints/cli/_modelo_aggregate_cli.py`.
- [ ] `P05.S22` - Report every invoice withholding defect through the one projection path (ruling 15); `src/cadrumo/application/aggregation/invoice_retencion.py`.
- [ ] `P05.S23` - Let the label reading stand with a visible notice when the optional model fill is refused for headroom (ruling 17); `src/cadrumo/adapters/outbound/llm/`.
- [ ] `P05.S24` - Move the private ingest corpus behind a capability marker, a configured root and its own recipe (ruling 18); `dev/ingest_harness/`.
- [ ] `P05.S25` - Correct the 2024 Modelo 193 perceptor count to count records, and ground or downgrade the 2024 Modelo 190 relation to Modelo 111; `src/cadrumo/_data/registry/aeat/modelos/193/`.
- [ ] `P05.S26` - Author Modelo 131's 2022 and 2023 modulos engine with dated reduction rows and open the 2026 parameter rows, after P05.S17 enrolls the modulos orden provisions; `src/cadrumo/_data/registry/aeat/modelos/131/`.
- [ ] `P05.S27` - Ground Modelo 202's 2025 art. 40.2 base on the Modelo 200 box net of retenciones and ingresos a cuenta, which every era's instructions define it as; `src/cadrumo/_data/registry/aeat/modelos/202/`.
- [ ] `P05.S28` - Make the open-row gate also report an open row a later edition restates unchanged, with a detector case; `dev/registry/tests/test_parameter_rows_stay_open_across_editions.py`.

## Parallelization

Phase P01 (tool defects) and Phase P02 (Modelo 100) may proceed together; P02 Steps are ordered and share one writer. Phase P03 (consumer year bounds) follows the amortization Step of P02. Phase P04 (other modelos) runs after P02, with one writer per modelo. The year-named test scrub runs in an isolated worktree on test files only and merges before plan close; it excludes the test files P02 and P03 own. Phase P05 runs beside P04 within four concurrent lanes and one serialized test lock. The code Steps (S14, S15, S16, S18, S21 to S24) each own disjoint files and may run in parallel. S17 is the single writer of Modelo 100 and of the legal catalogues. S19, S20 and S25 start only after the P04.S11 lane owning the same modelo has finished.

## Verification

- Each rectified registry item carries per-year official citations and focused tests through the compiled registry, with unchanged hydration for the years it does not move.
- For every touched modelo, the edition delta converter is idempotent (a proof run, an apply run in a fresh directory, then a no-op run) and the collapse verifier reports the modelo clean.
- Candidate inspection is publication-valid, and the authoring inspection and compile-path boundary tests pass.
- `just check-registry`, `just check-bindings` and `just check-registry-gate` report no new failure against the `main` baseline, which on this host is clean with 18 unreferenced filing-grade binding warnings.
- The operator receives the collected ruling list, and the four completion boundaries are reported separately.
