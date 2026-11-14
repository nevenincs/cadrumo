---
tags:
  - '#plan'
  - '#source-casilla-integration'
date: '2026-11-14'
tier: L2
related:
  - '[[2026-11-14-source-casilla-integration-modelo-840-profile-facts-and-premises-repeat-adr]]'
  - '[[2026-08-25-source-casilla-integration-modelo-840-source-and-repeated-row-owner-deferral-adr]]'
modified: '2026-11-14'
body_schema: body-v2
body_hash: 'sha256:2cced88733a748590d9ff79861fccac1f917d541aea9d121a431c4378ea11963'
---

# `source-casilla-integration` plan

Supply the Modelo 840 export's cited producer keys from stored, custodied profile facts, with no stubs.

## Description

Approved 2026-11-14. Basis: the operator approved the proposed records "if they do not diverge
from delta keyed compacted registry definitions", and PRIME applied that approval at 13:54
(RULINGS 2026-11-14 13:54), accepting
`2026-11-14-source-casilla-integration-modelo-840-profile-facts-and-premises-repeat-adr` with
option (a), owner LIFECYCLE, after M322T and M322P.

The plan supplies the 65 Modelo 840 producer keys the export layout cites from stored profile
facts, in three hands that follow the ADR's Implementation section. Phase P01 adds the profile
facts. Phase P02 adds the premises repeat to the export generator. Phase P03 adds the producers
and the official round trip.

Decision coverage: the accepted 2026-11-14 ADR governs every Phase. It is the explicitly
authorized Modelo 840 slice of the accepted 2026-08-25 deferral ADR. Each family it reopens
meets that ADR's five reopening conditions through this plan's proofs. The authorization covers
this slice only and does not start phase 2 in general.

## Steps

### Phase `P01` - profile-schema facts for Modelo 840

Hand 1 stores the structured fiscal address with INE codes, the AEAT delegacion and administracion, and per-activity premises with their Regla 14 surfaces and tax elements as typed, custodied, dated profile facts the operator enters.

- [ ] `P01.S01` - Ground the Modelo 840 fact list in the official record design, form and IAE tariff instruction (Regla 14), and declare the fiscal-address INE codes, AEAT delegacion and administracion, and per-activity premises with surfaces and tax elements in the profile schema with sensitivity, effective dates, provenance and custody; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`.
- [ ] `P01.S02` - Add the typed profile records with a durable per-local identity and distinct total, rectified and computable surfaces, persisted only through encrypted custody, with zero, absent and correction semantics; `src/cadrumo/domain/contribuyente`.
- [ ] `P01.S03` - Let the operator enter and correct the facts through the registered profile operation and the wizard or CLI, with wording in all four locales through dev.locales; `src/cadrumo/application/user_profile`.

### Phase `P02` - premises repeat in the export generator

Hand 2 gives the export generator repeat semantics for the anexo premises slots keyed by a durable per-local identity and regenerates only the Modelo 840 editions whose layout changes.

- [ ] `P02.S04` - Give the export generator repeat semantics for the anexo Relacion de locales slots keyed by the per-local identity, proven against the official slot positions; `dev/registry/pipeline`.
- [ ] `P02.S05` - Regenerate only the Modelo 840 export editions whose layout changes, declaring any new registry member once at its earliest edition, including an informational casilla for the representante's municipality name (design Apart. III position 492) that the operator enters with the other representante address casillas, mapped to that export field instead of a profile producer; `src/cadrumo/_data/registry/aeat/modelos/840`.

### Phase `P03` - producers and the official round trip

Hand 3 writes producers that read only the stored facts, proves the export round trip against the official design and turns the known red green without stubs.

- [ ] `P03.S06` - Write the Modelo 840 producers over the stored facts only, keeping the typed refusal for any key without a stored fact; `src/cadrumo/application/filing`.
- [ ] `P03.S07` - Prove the Modelo 840 export round trip against the official design per own-edition year and turn test_every_cited_producer_key_is_resolvable green with no refusing stubs; `src/cadrumo/application/filing/tests`.

## Parallelization

The Phases run in order, one hand each. P02's repeat key is P01's per-local identity, and P03's
producers read P01's facts through P02's layouts. P02's generator work can begin once P01's
identity type is fixed, but it is handed after P01 lands. Steps within a Phase are one hand,
landed alone.

## Verification

- P01: profile facts round-trip through encrypted custody with their effective dates and
  provenance. A missing fact stays absent and never takes a default. All four locales pass
  `dev/locales` `test_audit.py` and `test_parity.py`.
- P02: the repeat semantics are proven through the real export builder against the official
  slot positions. Only Modelo 840 export editions whose layout changes are regenerated, and
  `target-current` reports current for each. `delta_minimality` and `edition_delta_assessment`
  are green. The year-independence gate and conformance valid, runtime-load and integrity pass.
- P03: a Modelo 840 export of a synthetic profile matches bytes transcribed from the official
  design for each own-edition year enumerated from the registry envelope. A key without a stored
  fact keeps its typed refusal. `test_every_cited_producer_key_is_resolvable` passes, and no
  producer always refuses.
- Every hand passes `branch_gate_delta` against feature/tui, the import contracts, ruff and ty.
  A review at each Phase close and at plan close finds no open critical or high finding.
