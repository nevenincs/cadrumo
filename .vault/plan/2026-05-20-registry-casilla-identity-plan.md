---
tags:
  - '#plan'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
tier: L2
related:
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
  - '[[2026-05-20-branch-reconciliation-audit]]'
---


# `registry-casilla-identity` plan

### Phase `P01` - Schema - additive segmento field

Add the optional segmento field to CasillaDefinition under strict-pydantic discipline; additive and landed first to minimise collision with concurrent Registry-hardening commits.

- [x] `P01.S01` - Add optional strict-pydantic field segmento (str or None, default None) to CasillaDefinition carrying the AEAT record-segment code with a Spanish-stem name per the terminology ADR; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P01.S02` - Document the segmento field contract (composed id for multi-segment casillas, unset for single-segment) in the registry schema module docstring or field comment without embedding plan metadata; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P01.S03` - Add a focused strict-pydantic test asserting segmento defaults unset, accepts a DP-code string, and that a single-segment CasillaDefinition validates unchanged; `src/aeat/domain/calculations/registry/test_registry_schema.py`.

### Phase `P02` - Validator and reference resolution

Change the casilla-uniqueness invariant from id to (segmento, number) and define segment-aware reference resolution for formula, export, and relation args keyed on a bare casilla number.

- [x] `P02.S04` - Generalise the casilla duplicate-id invariant to (segmento, number) uniqueness per modelo revision so a casilla with segmento unset reproduces today's bare-number uniqueness exactly; `src/aeat/domain/calculations/registry/_validate.py`.
- [x] `P02.S05` - Define segment-aware reference resolution so a bare-number formula, export, or relation arg resolves within its segment context and only genuinely cross-segment references need the composed id; `src/aeat/domain/calculations/registry/_validate.py`.
- [x] `P02.S06` - Apply segment-aware casilla lookup to the runtime graph dependency walk so expression_casilla_refs resolves multi-segment numbers correctly; `src/aeat/domain/calculations/registry/_runtime_graph.py`.
- [x] `P02.S07` - Add validator tests covering (segmento, number) uniqueness, the single-segment (None, number) collision still failing, and segment-aware reference resolution; `src/aeat/domain/calculations/registry/test_referential_integrity.py`.

### Phase `P03` - Diseno-completeness gate

Build the extraction-derived per-modelo Diseno-completeness manifest, the fail-closed hard gate in RegistryValidator at snapshot build, and the off-load-path drift re-verification.

- [x] `P03.S08` - Add a Diseno-completeness manifest schema model enumerating the expected (segmento, number) casilla set per modelo revision under strict-pydantic discipline; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P03.S09` - Build an off-load-path manifest-derivation tool that runs the record-design extraction against the corpus Diseno workbooks and emits the per-modelo completeness manifest as reviewed checked-in data; `src/aeat/domain/calculations/registry/_record_design.py`.
- [x] `P03.S10` - Add a fail-closed completeness gate to RegistryValidator that hard-errors at snapshot build when declared casillas diverge from the manifest or when a casilla-bearing revision has no manifest; `src/aeat/domain/calculations/registry/_validate.py`.
- [x] `P03.S11` - Add an off-load-path drift re-verification test that re-derives every manifest from the corpus Diseno and fails CI on divergence, with explicit manual-extraction markers for PDF-only Disenos; `src/aeat/domain/calculations/registry/test_record_design.py`.
- [x] `P03.S12` - Add completeness-gate tests covering a missing manifest failing closed, a missing casilla failing, and an extra casilla failing; `src/aeat/domain/calculations/registry/test_referential_integrity.py`.

### Phase `P04` - Modelo 200 casilla registration

Register the M200 Liquidacion III/IV page-14 cuota-chain casillas from the corpus AEAT 2024 Diseno xlsx and re-point the M200 page-014 export binding off the ECPN occurrence.

- [x] `P04.S13` - Register the M200 Liquidacion base imponible casilla 00552 under segmento DP200014 as a new fragment file carrying legal_refs and source_refs from the corpus 2024 Diseno xlsx; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00552-base-imponible.toml`.
- [x] `P04.S14` - Register the M200 Liquidacion tipo de gravamen casilla 00558 under segmento DP200014 as a new fragment file carrying legal_refs and source_refs from the corpus 2024 Diseno xlsx; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00558-tipo-de-gravamen.toml`.
- [x] `P04.S15` - Register the M200 Liquidacion cuota integra casilla 00562 under segmento DP200014 as a new fragment file carrying legal_refs and source_refs from the corpus 2024 Diseno xlsx; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00562-cuota-integra.toml`.
- [x] `P04.S16` - Register the M200 Liquidacion cuota liquida casilla 00592 under segmento DP200014B as a new fragment file carrying legal_refs and source_refs from the corpus 2024 Diseno xlsx; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00592-cuota-liquida.toml`.
- [x] `P04.S17` - Register the M200 Liquidacion cuota del ejercicio casilla 00599 under segmento DP200014B as a new fragment file carrying legal_refs and source_refs from the corpus 2024 Diseno xlsx; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00599-cuota-del-ejercicio.toml`.
- [x] `P04.S18` - Register the M200 Liquidacion cuota diferencial casilla 00611 under segmento DP200014B as a new fragment file carrying legal_refs and source_refs from the corpus 2024 Diseno xlsx; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00611-cuota-diferencial.toml`.
- [x] `P04.S19` - Re-point the M200 page-014 export field binding for casilla 00562 from the ECPN occurrence to the new Liquidacion DP200014 casilla; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0017-modelo-200-page-014.toml`.

### Phase `P06` - Gate refocus to calculation-completeness

Refocus the load-blocking completeness gate from full-Diseno coverage to calculation-completeness per the ADR amendment, and retain the full-Diseno extraction as an off-load-path advisory coverage report.

- [x] `P06.S26` - Refocus the completeness gate from declared == manifest to manifest-required subset-of declared, adding the (segmento, number) identity check and the legal_refs / source_refs grounding check on each manifest casilla per the ADR amendment; `src/aeat/domain/calculations/registry/_validate.py`.
- [x] `P06.S27` - Refocus the manifest schema model so it represents the calculation-closure required casilla set (Diseno-sourced identity, bounded to the calculation surface) rather than the full-Diseno coverage set; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P06.S28` - Refocus the derivation tool to derive the calculation closure intersected with the Diseno, and retain the full-Diseno extraction as a separate off-load-path coverage-report producer; `src/aeat/domain/calculations/registry/_record_design.py`.
- [x] `P06.S29` - Update the gate tests to the refocused manifest-required subset-of declared plus identity and grounding semantics, replacing the declared == manifest assertions; `src/aeat/domain/calculations/registry/test_referential_integrity.py`.
- [x] `P06.S30` - Update the drift / coverage test so the full-Diseno extraction is exercised as an advisory coverage report rather than a load-blocking gate; `src/aeat/domain/calculations/registry/test_record_design.py`.

### Phase `P05` - Verification and rollout

Add strict roundtrip and anti-tautology proofs, the M200 manifest, the per-modelo gate rollout, and the all-26-modelos validity confirmation.

- [x] `P05.S20` - Add a strict roundtrip test for the extended CasillaDefinition that populates segmento with a non-default value, pushes through the real load cycle, and asserts strict pydantic equality across the boundary, sited in the schema-hygiene-allowlisted test_referential_integrity rather than test_registry_schema; `src/aeat/domain/calculations/registry/test_referential_integrity.py`.
- [x] `P05.S21` - Add an anti-tautology proof that mutates a fragment to drop or collide segmento and asserts the (segmento, number) uniqueness gate surfaces a hard error, where the new file must either avoid constructing schema-authority objects by mutating on-disk fragments and reloading or be added to the schema-hygiene allowlist; `src/aeat/domain/calculations/registry/test_tautology_gate.py`.
- [x] `P05.S22` - Author the Modelo 200 calculation-completeness manifest enumerating the cuota-chain calculation closure, and confirm M200 clears the gate now that the Liquidacion casillas are registered; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/completeness-manifest.toml`.
- [x] `P05.S23` - Author calculation-completeness manifests for the calculation-bearing modelos so the fail-closed gate has a calculation-closure manifest for every modelo it gates; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `P05.S31` - Produce the off-load-path full-Diseno coverage advisory report that inventories form-level data coverage and surfaces known gaps without redding the load; `src/aeat/domain/calculations/registry/_record_design.py`.
- [x] `P05.S32` - Implement a legally grounded singleton semantic_role policy for validator typo-twin warnings, keyed by modelo/revision/casilla/source evidence rather than broad role-name suppression; `src/aeat/domain/calculations/registry/_validate.py`, `src/aeat/domain/calculations/registry/test_semantic_role.py`, `src/aeat/_data/registry/aeat/modelos/`.
- [x] `P05.S24` - Extend the M200 registry test to assert the Liquidacion cuota-chain casillas resolve under their DP200014 segmento and the page-014 export binding resolves 00562 to the Liquidacion occurrence; `src/aeat/domain/calculations/registry/test_modelo_200_registry.py`.
- [x] `P05.S25` - Run the full registry parity-coverage suite to confirm all 26 modelos load valid after the gate flips to hard-error per modelo; `src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py`.
- [x] `P05.S33` - Correct the Modelo 200 page-14 cuota chain against the AEAT Manual de Sociedades 2024: fix the 00599 retenciones formula, author the 01330/00562/00611 formulas, segment-qualify the dependency casillas, regenerate the calculation-completeness manifest, and add the manual-oracle calc-verify test; `src/aeat/_data/registry/aeat/modelos/200/, src/aeat/domain/calculations/registry/`.
