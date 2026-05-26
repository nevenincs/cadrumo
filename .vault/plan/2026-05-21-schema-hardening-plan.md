---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-21'
tier: L3
related:
  - '[[2026-05-18-schema-hardening-adr]]'
  - '[[2026-05-19-schema-hardening-role-taxonomy-reference]]'
  - '[[2026-05-20-schema-hardening-verification-ledger]]'
  - '[[2026-05-21-schema-hardening-semantic-role-sidecar-audit]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- RETIRED: S63 -->

# `schema-hardening` `semantic_role sidecar continuation` plan

## Wave `W01` - Completed semantic-role sidecar inventories

This Wave preserves the completed Modelo 100 and Modelo 200 sidecar inventories, guards, and review records already executed for the semantic-role warning clusters.

### Phase `W01.P01` - Modelo 200 correction-axis extraction design

This Phase designs the safe mechanical extraction boundary for Modelo 200 correction-table axes.

- [x] `W01.P01.S01` - Define the Modelo 200 correction-axis metadata contract before any registry rewrite.; `src/aeat/domain/calculations/registry`.
- [x] `W01.P01.S02` - Enumerate the Modelo 200 correction-axis base-role allowlist from official manual tables and current registry labels.; `.vault/audit`.
- [x] `W01.P01.S03` - Enumerate the Modelo 200 label-versus-role mismatch records as an explicit review bucket.; `.vault/audit`.
- [x] `W01.P01.S04` - Define regression checks that prevent legal base slugs from being collapsed during correction-axis extraction.; `src/aeat/domain/calculations/registry`.

### Phase `W01.P03` - Modelo 200 policy-gated legal bases

This Phase records the legal and concept bases that extraction must preserve.

- [x] `W01.P03.S05` - Document the keep-list for article, transitional-provision, provision, regime, event, SICAV, cooperative, port-authority, and entity-specific bases.; `.vault/audit`.
- [x] `W01.P03.S06` - Define the review requirement for any future change to a keep-listed legal base slug.; `.vault/reference`.

### Phase `W01.P02` - Modelo 100 family-local pilot

This Phase pilots carryforward-axis extraction only inside one manually grounded family.

- [x] `W01.P02.S07` - Record the c_valenciana_autoconsumo family boundary from registry labels and the Renta 2025 manual.; `.vault/audit`.
- [x] `W01.P02.S08` - Define the family-local axes for generated year and pending state.; `src/aeat/domain/calculations/registry`.
- [x] `W01.P02.S09` - Define a guard that rejects cross-region normalization by repeated label alone.; `src/aeat/domain/calculations/registry`.

### Phase `W01.P04` - Review gate

This Phase prevents implementation from running ahead of legal-source review.

- [x] `W01.P04.S10` - Produce a reviewer checklist for every future semantic-role normalization slice.; `.vault/audit`.
- [x] `W01.P04.S11` - Verify every implemented slice against the official manuals or registry source references named in its audit.; `.vault/audit`.

### Phase `W01.P05` - Modelo 200 exact mismatch inventory

This Phase converts the Modelo 200 label-versus-role mismatch bucket into exact casilla-level review records.

- [x] `W01.P05.S12` - Record exact Modelo 200 casilla IDs, files, labels, and roles for the temporary-label versus permanent-role mismatch bucket.; `.vault/audit`.

### Phase `W01.P06` - Modelo 200 suffix grammar inventory

This Phase inventories the correction-role suffix grammar and legally marked base stems before implementation.

- [x] `W01.P06.S13` - Inventory Modelo 200 correction-role suffix patterns, unmatched correction roles, and legally marked base stems without editing registry source.; `.vault/audit`.

### Phase `W01.P07` - Modelo 100 repeated-label inventory

This Phase inventories repeated Modelo 100 labels that look mechanically normalizable but carry autonomous-community and family-local legal context.

- [x] `W01.P07.S14` - Record exact Modelo 100 2025 repeated-label clusters for generated, pending, and municipality-code labels without cross-family normalization.; `.vault/audit`.

### Phase `W01.P08` - Modelo 100 generated-pending family grammar

This Phase classifies generated and pending repeated-label roles by family-local suffix patterns and flags unsafe cross-family generalizations.

- [x] `W01.P08.S15` - Inventory Modelo 100 generated and pending role suffixes by autonomous-community family and identify safe family-local extraction candidates versus policy blockers.; `.vault/audit`.

### Phase `W01.P09` - Modelo 100 municipality-code guard

This Phase classifies repeated municipality-code labels and data-type shape before any role normalization.

- [x] `W01.P09.S16` - Inventory Modelo 100 municipality-code repeated labels by CCAA, role, and data-type shape, and define normalization blockers.; `.vault/audit`.

## Wave `W02` - Modelo 200 correction-axis implementation readiness

This Wave scopes the future implementation-readiness work for Modelo 200 correction-axis extraction, constrained to the audited suffix grammar, mismatch exclusions, and preserve-listed legal base stems.

### Phase `W02.P10` - M200 extraction contract hardening

This Phase prepares a reviewed implementation contract for the audited Modelo 200 correction-axis grammar before source edits.

- [x] `W02.P10.S17` - Draft the implementation allowlist for the 8-axis and 7-axis Modelo 200 base stems from the audited suffix grammar.; `.vault/audit`.
- [x] `W02.P10.S18` - Define the exact exclusion guard for the 23 temporary-label versus permanent-role mismatch IDs.; `src/aeat/domain/calculations/registry`.
- [x] `W02.P10.S19` - Define tests that preserve legally marked Modelo 200 base stems during sidecar extraction.; `src/aeat/domain/calculations/registry`.

## Wave `W03` - Modelo 100 approved family-local pilot

This Wave scopes the only currently approved Modelo 100 implementation candidate: c_valenciana_autoconsumo generated and pending axes inside its manually grounded family boundary.

### Phase `W03.P11` - C Valenciana autoconsumo pilot promotion

This Phase prepares the approved c_valenciana_autoconsumo family for a source-grounded implementation slice.

- [x] `W03.P11.S20` - Confirm the five c_valenciana_autoconsumo member IDs against the Renta 2025 autonomous deductions manual before implementation.; `.vault/audit`.
- [x] `W03.P11.S21` - Define generated-year and pending-state metadata only inside the c_valenciana_autoconsumo family boundary.; `src/aeat/domain/calculations/registry`.
- [x] `W03.P11.S22` - Define tests that keep hasta_2022 and desde_2023 as legal year-window concepts, not extracted axes.; `src/aeat/domain/calculations/registry`.

## Wave `W04` - Modelo 100 candidate family manual lookup

This Wave scopes discovered but not yet approved Modelo 100 family-local candidates that require manual source lookup before promotion: murcia_infraestructuras, madrid_nuevos_contribuyentes, la_rioja, and catalunya.

### Phase `W04.P12` - Murcia infraestructuras source lookup

This Phase determines whether murcia_infraestructuras is a safe family-local generated and pending axis candidate.

- [x] `W04.P12.S23` - Locate and record the Renta 2025 manual source text for Murcia infraestructuras generated and pending rows.; `.vault/audit`.
- [x] `W04.P12.S24` - Decide whether murcia_infraestructuras may be promoted to the family-local allowlist or must remain blocked.; `.vault/audit`.

### Phase `W04.P13` - Madrid nuevos contribuyentes source lookup

This Phase determines whether madrid_nuevos_contribuyentes is a safe family-local generated and pending axis candidate.

- [x] `W04.P13.S25` - Locate and record the Renta 2025 manual source text for Madrid nuevos contribuyentes generated and pending rows.; `.vault/audit`.
- [x] `W04.P13.S26` - Decide whether madrid_nuevos_contribuyentes may be promoted to the family-local allowlist or must remain blocked.; `.vault/audit`.

### Phase `W04.P14` - La Rioja generated-pending source lookup

This Phase determines whether the La Rioja generated and pending pair has a real family boundary or only a generic CCAA prefix.

- [x] `W04.P14.S27` - Locate and record the Renta 2025 manual source text for the La Rioja generated and pending pair.; `.vault/audit`.
- [x] `W04.P14.S28` - Decide whether the La Rioja pair may be promoted to the family-local allowlist or must remain blocked as CCAA-generic.; `.vault/audit`.

### Phase `W04.P15` - Catalunya generated-pending source lookup

This Phase determines whether the Catalunya generated and pending pair has a real family boundary or only a generic CCAA prefix.

- [x] `W04.P15.S29` - Locate and record the Renta 2025 manual source text for the Catalunya generated and pending pair.; `.vault/audit`.
- [x] `W04.P15.S30` - Decide whether the Catalunya pair may be promoted to the family-local allowlist or must remain blocked as CCAA-generic.; `.vault/audit`.

## Wave `W05` - Future repeated-surface discovery

This Wave scopes not-yet-discovered repeated semantic-role surfaces and requires each future candidate to enter through audit, source lookup, and policy review before implementation.

### Phase `W05.P16` - Repeated-surface discovery intake

This Phase defines the intake for repeated semantic-role surfaces not yet discovered in the current sidecar.

- [x] `W05.P16.S31` - Scan Modelo 100 and Modelo 200 for additional repeated labels, singleton role clusters, and suffix grammars not covered by W01 through W04.; `.vault/audit`.
- [x] `W05.P16.S32` - Create one audit-backed candidate record per newly discovered repeated surface, including official source requirements and no-go conditions.; `.vault/audit`.
- [x] `W05.P16.S33` - Promote a future candidate to its own wave only after source lookup confirms a family-local or table-axis boundary.; `.vault/plan`.

## Wave `W06` - Modelo 200 compensation grid source lookup

This Wave manually source-checks the newly discovered Modelo 200 compensation and carryforward grids before any sidecar metadata extraction: financial-expense carryforwards, negative tax-base compensation, and cooperative quota compensation.

### Phase `W06.P17` - Financial expense carryforward source lookup

This Phase determines whether the Modelo 200 financial-expense pending-deduction grid can be treated as a source-grounded year/state table-axis candidate.

- [x] `W06.P17.S34` - Locate and record official Modelo 200 source text for the financial-expense pending-deduction grid; `.vault/audit`.
- [x] `W06.P17.S35` - Decide whether financial-expense grid axes may be promoted or must remain blocked; `.vault/audit`.

### Phase `W06.P18` - Negative tax-base compensation source lookup

This Phase determines whether the Modelo 200 bases imponibles negativas compensation grid can be treated as a source-grounded year/state table-axis candidate.

- [x] `W06.P18.S36` - Locate and record official Modelo 200 source text for the negative tax-base compensation grid; `.vault/audit`.
- [x] `W06.P18.S37` - Decide whether negative tax-base compensation axes may be promoted or must remain blocked; `.vault/audit`.

### Phase `W06.P19` - Cooperative quota compensation source lookup

This Phase determines whether the Modelo 200 cooperative quota compensation grid can be treated as a source-grounded year/state table-axis candidate.

- [x] `W06.P19.S38` - Locate and record official Modelo 200 source text for the cooperative quota compensation grid; `.vault/audit`.
- [x] `W06.P19.S39` - Decide whether cooperative quota compensation axes may be promoted or must remain blocked; `.vault/audit`.

## Wave `W07` - Modelo 200 deduction grid source lookup

This Wave manually source-checks newly discovered Modelo 200 deduction grids before sidecar metadata extraction: general donations, Canarias investment deductions, and I+D+i excluded-limit branches.

### Phase `W07.P20` - General donations deduction grid source lookup

This Phase determines whether the Modelo 200 general donations deduction grid can be treated as a source-grounded year/state/statutory-branch table-axis candidate.

- [x] `W07.P20.S40` - Locate and record official Modelo 200 source text for the general donations deduction grid; `.vault/audit`.
- [x] `W07.P20.S41` - Decide whether general donations deduction axes may be promoted or must remain blocked; `.vault/audit`.

### Phase `W07.P21` - Canarias investment deduction grid source lookup

This Phase determines whether the Modelo 200 Canarias investment deduction grid can be treated as a source-grounded year/state/subfamily table-axis candidate.

- [x] `W07.P21.S42` - Locate and record official Modelo 200 source text for the Canarias investment deduction grid; `.vault/audit`.
- [x] `W07.P21.S43` - Decide whether Canarias investment deduction axes may be promoted or must remain blocked; `.vault/audit`.

### Phase `W07.P22` - IDI excluded-limit deduction grid source lookup

This Phase determines whether the Modelo 200 I+D+i excluded-limit investigation and innovation grids can be treated as source-grounded year/state/branch table-axis candidates.

- [x] `W07.P22.S44` - Locate and record official Modelo 200 source text for the I+D+i excluded-limit deduction grids; `.vault/audit`.
- [x] `W07.P22.S45` - Decide whether I+D+i excluded-limit deduction axes may be promoted or must remain blocked; `.vault/audit`.

## Wave `W08` - Modelo 100 repeated grid source lookup

Manually source-check the remaining high-volume Modelo 100 singleton semantic_role warning clusters before any normalization proposal.

### Phase `W08.P23` - Anexo C carryforward source lookup

Locate official Renta grounding for Anexo C carryforward year/state grids and decide whether axis extraction is mechanically safe.

- [x] `W08.P23.S46` - Locate and record official Renta source text for Modelo 100 Anexo C carryforward year/state grids.; `.vault/audit`.
- [x] `W08.P23.S47` - Decide whether Anexo C carryforward axes may be promoted mechanically or must remain blocked by basket-specific legal context.; `.vault/audit`.

### Phase `W08.P24` - Deferred imputation source lookup

Locate official Renta grounding for deferred-imputation slot grids and decide whether repeated axes are mechanically safe.

- [x] `W08.P24.S48` - Locate and record official Renta source text for deferred-imputation year, amount, gain, and loss slot grids.; `.vault/audit`.
- [x] `W08.P24.S49` - Decide whether deferred-imputation slot axes may be promoted mechanically or must remain blocked by transaction-specific legal context.; `.vault/audit`.

### Phase `W08.P25` - Cadastral reference source lookup

Locate official Renta grounding for repeated cadastral reference and no-reference marker labels before any family-local extraction.

- [x] `W08.P25.S50` - Locate and record official Renta source text for repeated cadastral reference and no-reference marker labels.; `.vault/audit`.
- [x] `W08.P25.S51` - Decide whether cadastral reference repetition is globally normalizable, family-local only, or blocked pending narrower policy.; `.vault/audit`.

## Wave `W09` - Semantic-role typo-warning sidecar implementation

Implement source-grounded semantic-role axis sibling recognition for audited Modelo 100 repeated surfaces while preserving legal basket, branch, and field-type boundaries.

### Phase `W09.P26` - Audited M100 axis sibling guards

Add exact source-grounded axis sibling guards for Anexo C carryforward states and deferred-imputation slots.

- [x] `W09.P26.S52` - Implement source-grounded semantic-role axis sibling recognition for Anexo C carryforward state roles and deferred-imputation slot roles.; `src/aeat/domain/calculations/registry`.
- [x] `W09.P26.S53` - Add regression tests proving audited M100 axes suppress typo warnings while basket, branch, gain-loss, and cadastral-reference boundaries remain unmerged.; `src/aeat/domain/calculations/registry`.

### Phase `W09.P27` - Supporting contract documentation

Update vault support documents so the implemented warning-sidecar guards are traceable to official-source audit decisions.

- [x] `W09.P27.S54` - Update the schema-hardening reference and audit trail with the implemented warning-sidecar contract and source boundaries.; `.vault/reference`.

## Wave `W10` - Modelo 200 correction-axis warning-sidecar hardening

This Wave converts the audited Modelo 200 correction-axis contract into a stricter warning-sidecar guard that preserves legal base stems, supports balance-only axes, and records that the known label-versus-role mismatch bucket remains excluded from structured metadata extraction without reintroducing typo-warning noise.

### Phase `W10.P28` - Correction-axis warning guard implementation

Implement a source-grounded Modelo 200 correction-axis sibling recognizer for warning suppression without registry rewrites.

- [x] `W10.P28.S55` - Implement the audited Modelo 200 correction-axis warning-sidecar guard with balance-only axis support and explicit no-metadata-extraction boundaries for the mismatch bucket; `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`.
- [x] `W10.P28.S56` - Add real-behavior regression tests for correction balance axes, legal base preservation, and mismatch-bucket warning-only behavior; `src/aeat/domain/calculations/registry/test_semantic_role.py`.

### Phase `W10.P29` - Correction-axis guard documentation and review

Record the code behavior, tests, and review outcome in the vault so the legal-source grounding remains traceable.

- [x] `W10.P29.S57` - Update vault reference, audit, execution, and review records for the Modelo 200 correction-axis warning guard; `.vault`.

## Wave `W11` - Modelo 100 family-local generated-pending warning-sidecar implementation

This Wave implements warning-only semantic-role sibling recognition for source-approved Modelo 100 family-local generated/pending candidates, limited to exact promoted family stems and preserving blocked CCAA-generic La Rioja and Catalunya pairs.

### Phase `W11.P30` - Family-local generated-pending warning guard implementation

Implement exact-family generated/pending warning-sidecar recognition for approved Modelo 100 families without registry rewrites or cross-region normalization.

- [x] `W11.P30.S58` - Implement exact-family generated-pending warning-sidecar recognition for approved Modelo 100 C Valenciana autoconsumo, Murcia infraestructuras, and Madrid nuevos contribuyentes roles; `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`.
- [x] `W11.P30.S59` - Add real-behavior regression tests for approved generated-pending families and blocked La Rioja and Catalunya generic bases; `src/aeat/domain/calculations/registry/test_semantic_role.py`.

### Phase `W11.P31` - Family-local generated-pending documentation and review

Record the source-to-code boundary, blocked families, verification, and review outcome in the vault.

- [x] `W11.P31.S60` - Update vault reference, audit, execution, and review records for the family-local generated-pending warning guard; `.vault`.

## Wave `W12` - Cross-CCAA warning-sidecar legal-boundary hardening

This Wave removes broad autonomous-community token normalization from typo-warning sibling recognition, because the source audit establishes that repeated cross-CCAA role wording is not legal equivalence. Current corpus roles formerly hidden by the broad guard are handled as explicit source-grounded intentional singletons instead.

### Phase `W12.P32` - Cross-CCAA warning guard removal

Remove the broad CCAA sibling guard from semantic-role typo-warning recognition and pin the legal boundary in regression tests.

- [x] `W12.P32.S61` - Remove broad CCAA token sibling recognition from semantic-role typo-warning axis handling; `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`.
- [x] `W12.P32.S62` - Add regression tests proving cross-CCAA role names are not axis siblings and the current corpus warning count remains clean; `src/aeat/domain/calculations/registry/test_semantic_role.py`.
- [x] `W12.P32.S64` - Mark source-grounded Modelo 100 cross-CCAA singleton roles as intentional singletons instead of relying on broad CCAA warning suppression; `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas`.

### Phase `W12.P33` - Cross-CCAA warning guard documentation and review

Record the corpus inspection, source-backed legal boundary, verification, and review outcome in the vault.

- [x] `W12.P33.S65` - Update vault reference, audit, execution, and review records for the cross-CCAA warning-boundary hardening; `.vault`.

## Wave `W13` - Legal-reference warning-sidecar preserve-list hardening

This Wave removes broad legal-reference token stripping from typo-warning sibling recognition, because article, transitional-provision, RDLeg, and LIS markers are source-visible legal identity. Current legitimate singleton roles exposed by the removal are marked explicitly in registry source instead of being hidden by generic normalization.

### Phase `W13.P34` - Legal-reference warning guard removal

Remove generic legal-reference stripping from semantic-role typo-warning axis handling and replace the hidden suppression with explicit source-grounded singleton policy.

- [x] `W13.P34.S66` - Remove broad legal-reference token sibling recognition from semantic-role typo-warning axis handling; `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`.
- [x] `W13.P34.S67` - Mark source-grounded Modelo 200 legal-reference singleton roles as intentional singletons instead of relying on broad legal-marker suppression; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas`.
- [x] `W13.P34.S68` - Add regression tests proving legal-reference role names are not axis siblings and the current corpus warning count remains clean; `src/aeat/domain/calculations/registry/test_semantic_role.py`.

### Phase `W13.P35` - Legal-reference warning guard documentation and review

Record the corpus inspection, legal-marker preserve boundary, verification, and review outcome in the vault.

- [x] `W13.P35.S69` - Update vault reference, audit, execution, and review records for the legal-reference warning-boundary hardening; `.vault`.

## Wave `W14` - Warning-sidecar control census and next-slice triage

Audit the remaining semantic-role typo-warning suppression helpers, run a fresh residual singleton-warning census for Modelo 100 and Modelo 200, and record the next source-grounded implementation slice without introducing blind legal normalization.

### Phase `W14.P36` - Remaining warning-suppressor audit

Inspect every remaining semantic-role typo-warning sibling helper and classify whether it is exact-family source-grounded, warning-only, or still too broad for legally meaningful roles.

- [x] `W14.P36.S70` - Inventory remaining semantic-role typo-warning sibling helpers and source-policy boundaries; `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`.
- [x] `W14.P36.S71` - Probe remaining warning suppressors for hidden Modelo 100 and Modelo 200 singleton exposure; `src/aeat/domain/calculations/registry`.

### Phase `W14.P37` - Residual warning census and next-slice triage

Run a fresh Modelo 100 and Modelo 200 singleton-warning census after W13 and record source-grounded candidate priorities for the next implementation wave.

- [x] `W14.P37.S72` - Generate fresh residual singleton-warning census and candidate ranking for Modelos 100 and 200; `src/aeat/_data/registry/aeat/modelos`.
- [x] `W14.P37.S73` - Update vault audit reference execution and review records with the next-slice triage; `.vault`.
