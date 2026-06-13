---
tags:
  - '#plan'
  - '#iva-compensation-chain'
date: '2026-05-19'
modified: '2026-05-19'
tier: L2
related:
  - '[[2026-05-19-iva-compensation-chain-audit-research]]'
  - '[[2026-05-19-iva-compensation-chain-adr]]'
  - '[[2026-05-19-live-iva-compensation-wallet-research]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-19-modelo-130-relation-regression-research]]'
  - '[[2026-05-19-modelo-130-relation-regression-adr]]'
  - '[[2026-05-19-modelo-130-relation-regression-plan]]'
---


# `iva-compensation-chain` `remediation` plan

Repair the Modelo 303 and Modelo 390 IVA compensation chain so it follows the current AEAT record-design fields, resolves previous-quarter carry-forward values through the registry runtime, and keeps the legal and source grounding declared through the resource system.

## Proposed Changes

The change updates the registry runtime to resolve direct previous-filing bindings declared with a singular `source_output`, adds target-relative period offsets to that selector path, and revises Modelo 303 and Modelo 390 TOML definitions around the audited compensation casillas. Tests will exercise the committed registry definitions and resolver behavior using the official AEAT record-design arithmetic, not duplicated production formulas.

The Vaultspec plan CLI was unavailable in this environment, so this document is authored directly from the repository template with stable identifiers.

## Steps

### Phase `P01` - establish legal and source-grounded registry semantics

This Phase updates the schema and registry definitions while keeping the legal and source references attached to the relevant constructs.

- [x] `P01.S01` - add singular-source previous-filing period-offset support; `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `P01.S02` - revise Modelo 303 compensation casillas, formulas, relation, construct references; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [x] `P01.S03` - revise Modelo 390 annual compensation reconciliation casillas and bindings; `src/aeat/_data/registry/aeat/modelos/390.toml`.

### Phase `P02` - verify compensation behavior against official source arithmetic

This Phase adds regression tests and executes targeted validation for the changed chain.

- [x] `P02.S01` - add previous-filing resolver coverage for singular `source_output` offsets; `src/aeat/domain/calculations/registry/test_selector_shape.py`.
- [x] `P02.S02` - add Modelo 303 compensation-chain registry and calculation tests; `src/aeat/domain/calculations/registry/test_modelo_303_registry.py`.
- [x] `P02.S03` - add Modelo 390 annual compensation-chain registry tests; `src/aeat/domain/calculations/registry/test_modelo_390_registry.py`.
- [x] `P02.S04` - run targeted unit tests and registry validation for 303 and 390; `tests`.

### Phase `P03` - track related relation-runtime follow-up waves

This Phase records the required production authority extensions discovered by the IVA remediation but governed by separate research, ADR, and plan documents.

- [ ] `P03.S01` - execute the linked live AEAT IVA compensation wallet plan before treating local recurrence as final authority; `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`.
- [x] `P03.S02` - execute the linked Modelo 130 relation-regression wave for the IRPF same-year negative-result carry-forward; `.vault/plan/2026-05-19-modelo-130-relation-regression-plan.md`.

## Parallelization

`P01.S01` can be implemented independently of the TOML changes, but `P01.S02` depends on it for direct previous-quarter resolution. `P01.S03` can proceed after the 303 source-output names are stable. The test steps in Phase `P02` follow their corresponding implementation steps and can be run together once Phase `P01` is complete. Phase `P03` is a tracking phase: its first linked plan is the live AEAT wallet authority path, and its second linked plan is the Modelo 130 relation-regression wave.

## Verification

The IVA implementation portion is complete when the committed Modelo 303 and Modelo 390 definitions validate, the targeted registry tests pass, the previous-filing resolver returns a 2T binding value from a 1T observation, Modelo 303 calculates casillas `78`, `87`, `69`, and the internal end-of-period carry-forward from grounded scenarios, and Modelo 390 exposes annual casillas `97` and `662` sourced from Modelo 303 observations. The wider relation-runtime closure remains open until Phase `P03` links are resolved: the AEAT-held IVA wallet authority decision and the Modelo 130 relation-regression plan.
