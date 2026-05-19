---
tags:
  - '#plan'
  - '#modelo-130-relation-regression'
date: '2026-05-19'
tier: L3
related:
  - '[[2026-05-19-modelo-130-relation-regression-research]]'
  - '[[2026-05-19-modelo-130-relation-regression-adr]]'
  - '[[2026-05-19-iva-compensation-chain-adr]]'
  - '[[2026-05-19-iva-compensation-chain-plan]]'
  - '[[2026-05-19-live-iva-compensation-wallet-research]]'
---

# `modelo-130-relation-regression` `remediation` plan

Repair the Modelo 130 same-year negative-result relation that was exposed while
verifying the IVA compensation-chain runtime. This is a linked wave in the same
cross-period relation family, but it is grounded in Modelo 130 IRPF instructions
rather than IVA compensation law.

## Proposed Changes

The change will first restore broad registry verification, then audit and repair
Modelo 130's prior-negative-result binding and relation. The implementation must
represent AEAT's rule for casilla `15`: unused prior same-year negative casilla
`19` results, applied only when casilla `14` is positive and capped by casilla
`14`. The plan is cross-linked to the IVA compensation-chain plan because both
flows exercise the same relation materialisation and previous-period evidence
path.

The Vaultspec plan CLI was unavailable in this environment, so this document is
authored directly from the repository template with stable identifiers.

## Steps

## Wave `W01` - Modelo 130 relation closure

This Wave closes the non-IVA relation regression discovered during IVA
verification. It depends on the IVA runtime changes for relation materialisation
but has its own legal and casilla semantics.

### Phase `W01.P01` - unblock broad registry verification

This Phase restores the registry loader so Modelo 130 failures can be measured
without unrelated schema errors masking the result.

- [ ] `W01.P01.S01` - restore bracket-overlap helper resolution; `src/aeat/domain/calculations/registry/_schema.py`.
- [ ] `W01.P01.S02` - rerun cross-dependency contract and calculation tests to capture the post-loader Modelo 130 failure set; `src/aeat/domain/calculations/registry/test_cross_dependency_contract.py`.

### Phase `W01.P02` - ground Modelo 130 relation semantics

This Phase aligns the registry declaration with AEAT's casilla `15` and casilla
`19` carry-forward rule.

- [ ] `W01.P02.S01` - audit Modelo 130 source and legal catalogue entries for AEAT instructions and RD 439/2007 article 110; `src/aeat/_data/registry/aeat/legal/irpf.toml`.
- [ ] `W01.P02.S02` - revise Modelo 130 binding, relation, dependency classification, and construct references for same-year unused negative results; `src/aeat/_data/registry/aeat/modelos/130.toml`.
- [ ] `W01.P02.S03` - adjust shared relation selector behavior only if Modelo 130 requires same-year aggregate source periods beyond the IVA previous-quarter selector; `src/aeat/domain/calculations/registry/_bindings.py`.

### Phase `W01.P03` - verify real registry behavior

This Phase adds real-behavior regression coverage without fakes, stubs,
monkeypatches, skips, or mirrored business logic.

- [ ] `W01.P03.S01` - add Modelo 130 carry-forward tests for casillas `15`, `17`, `19`, and `saldo-negativo-fin-periodo`; `src/aeat/domain/calculations/registry/test_modelo_130_registry.py`.
- [ ] `W01.P03.S02` - update cross-dependency contract expectations for the corrected Modelo 130 relation shape; `src/aeat/domain/calculations/registry/test_cross_dependency_contract.py`.
- [ ] `W01.P03.S03` - update cross-dependency calculation coverage for Modelo 130 edge-year and same-year prior-period observations; `src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`.
- [ ] `W01.P03.S04` - run targeted Modelo 130, cross-dependency, and IVA compensation regression suites together; `tests`.

## Parallelization

`W01.P01` must run first because the schema NameError masks the broader failure
set. After that, `W01.P02.S01` can run in parallel with test design for
`W01.P03.S01`, but TOML and runtime changes should land before cross-dependency
expectations are updated. The final verification step must run after all prior
steps in the Wave are complete.

## Verification

The plan is complete when registry loading succeeds, Modelo 130 calculates the
prior-negative carry-forward according to AEAT casilla instructions, the
cross-dependency contract suite accepts the corrected relation declaration, the
cross-dependency calculation suite resolves Modelo 130 observations across edge
years and periods, and the prior IVA compensation focused suite still passes.
