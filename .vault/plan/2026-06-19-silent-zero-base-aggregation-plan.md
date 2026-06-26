---
tags:
  - '#plan'
  - '#silent-zero-base-aggregation'
date: '2026-06-19'
modified: '2026-06-21'
tier: L3
related:
  - '[[2026-06-19-silent-zero-base-aggregation-adr]]'
  - '[[2026-06-19-silent-zero-base-aggregation-research]]'
  - '[[2026-06-19-silent-zero-base-aggregation-audit]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
---


# `silent-zero-base-aggregation` plan

Close the remaining silent-zero regulated-base and dropped-cuota gaps by
aggregating each casilla from its grounded canonical ledger source, per the
decided mechanisms in the ADR; defer only what genuinely requires a new
classification axis.

## Description

The research inventory and the adversarial audit enumerated every regulated base,
volume, or cuota casilla whose siblings aggregate from the ledger but which itself
resolves silently to zero. The bounded mirrors (M130 directa gastos; M303
régimen-general bases) are done or in flight; this plan executes the decided
mechanisms for the rest. Each Wave carries the ADR's named mechanism. M303 Steps
are sequenced behind the peer's in-flight base-binding work and must only touch
M303 files once they are peer-clean. No Step may ship a regulated value that is
not grounded in its binding provision cross-checked against the bundled corpus, and
no Step may approximate prorrata or recargo with a rate/category axis that cannot
express them.

## Steps

## Wave `W01` - M303 IVA aggregation completeness

Complete the M303 régimen-general bases, the prorrata general-prorrata volumes, and
the recargo de equivalencia tiers so an M303 with ledger-aggregated cuotas also
carries grounded bases and a non-zero prorrata. Sequenced behind the peer's
in-flight base-binding work; every Step is gated on the touched M303 file being
peer-clean. Backed by the ADR's M303 mechanism decisions and the IVA aggregation
taxonomy.

### Phase `W01.P01` - régimen-general bases (peer-coordinated)

Confirm the peer's domestic base bindings land cleanly and the surface stays green.

- [x] `W01.P01.S01` - complete the abandoned-stale peer base-binding work for casillas 01/04/07/28 (bound to ledger_iva_aggregation base_amount_sum) by adding them to the M303 completeness manifest and construct so the calculation closure and manifest agree; `src/aeat/_data/registry/aeat/modelos/303/; `src/aeat/_data/registry/aeat/modelos/303/`.
- [x] `W01.P01.S02` - rerun the completeness-manifest drift gate and M303 registry build and record green after the base casillas join the manifest/construct; `src/aeat/domain/calculations/registry/tests/test_record_design.py; `src/aeat/domain/calculations/registry/tests/test_record_design.py`.

### Phase `W01.P02` - prorrata general-prorrata ledger volumes

Bind the prorrata volume casillas to the IVA ledger base aggregation so the LIVA art. 104 percentage computes from the ledger.

- [ ] `W01.P02.S03` - SUPERSEDED for the common case by the S05 formula default; `a per-period base_amount_sum binding for volumen-total would ship a wrong prorrata for mixed traders (the regulated prorrata is the prior-year definitive percent applied provisionally + Q4 regularisation), so the faithful mechanism is deferred to a cross-period prorrata model; src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/bindings/; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/bindings/`.
- [ ] `W01.P02.S04` - SUPERSEDED/deferred with S03: volumen-con-derecho per-period binding is not the regulated provisional+regularised prorrata; `deferred to the cross-period prorrata model; src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/bindings/; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/bindings/`.
- [x] `W01.P02.S05` - fix the prorrata-porcentaje no-volume-data default from 0 to 100 (full right to deduct, LIVA art-94) so a fully-taxable trader's export unblocks, with a regression test - the correct peer-clean fix for defect C2; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml; `src/aeat/_data/registry/aeat/modelos/303/`.
- [ ] `W01.P02.S06` - add a real-CLI end-to-end test that a fully-taxable M303 trader reaches a granted `.boe` with no prorrata-divergence error and no manual prorrata input; `src/aeat/application/modelo/tests/`.

### Phase `W01.P03` - recargo de equivalencia rate axis

Introduce a grounded recargo rate axis and aggregate the recargo bases and cuotas.

- [x] `W01.P03.S07` - model recargo de equivalencia on the transaction (recargo rate + recargo cuota alongside the IVA fields, or a dedicated recargo classification) grounded in ley-37-1992:art-161 against the bundled corpus - the prerequisite domain change before any recargo binding; `src/aeat/domain/iva/_schema.py; `src/aeat/domain/iva/_schema.py`.
- [x] `W01.P03.S08` - add `ledger_iva_aggregation` bindings selecting `recargo_equivalencia` at each recargo tier for the recargo base and cuota casillas, grounded; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/bindings/`.
- [x] `W01.P03.S09` - bind the recargo casillas, update the M303 manifest and construct, and add a real-behavior test that a recargo supplier's recargo cuota aggregates instead of reporting zero; `src/aeat/_data/registry/aeat/modelos/303/`.

## Wave `W02` - M100 annual actividad-económica income

Restore the M100 income/expense symmetry: casilla 0171 "Ingresos de explotación"
aggregates from the ledger like the first-slice expenses already do. Depends on no
other Wave. Backed by the ADR's M100 mechanism decision.

### Phase `W02.P04` - annual income aggregator

Build the annual actividad-económica income aggregator mirroring the M100 expense pipeline.

- [x] `W02.P04.S10` - add an annual M100 actividad-económica income aggregator (annual window, actividad eligibility) mirroring the first-slice expense pipeline shape; `src/aeat/application/aggregation/`.
- [x] `W02.P04.S11` - admit the annual M100 income target in the renta-income source selector and resolver without disturbing the M130 quarterly path, with the build-validation family case; `src/aeat/domain/calculations/registry/_ledger_bindings.py`.

### Phase `W02.P05` - bind casilla 0171 and verify the M100 chain

Bind the income casilla and prove the rendimiento chain.

- [x] `W02.P05.S12` - bind M100 casilla 0171 to the annual income aggregation (project verb uses the formula-runtime path, so no disentanglement needed) with grounded legal_refs (LIRPF art. 27/28); `src/aeat/_data/registry/aeat/modelos/100/; `src/aeat/_data/registry/aeat/modelos/100/`.
- [x] `W02.P05.S13` - sweep the M100 tests that supply 0171 to the bound path and rerun the M100 registry, formula-runtime, and verification gates green; `src/aeat/application/modelo/tests/`.
- [ ] `W02.P05.S14` - add a real-CLI end-to-end test that a sole-trader's M100 casilla 0171 / 0180 / 0224 populate from the ledger unaided; `src/aeat/application/modelo/tests/`.

## Wave `W03` - annual reconciliation and deferred axes

Verify the M390 annual carrier is canonical, and gate the agrarian axis on research.
Backed by the ADR's M390 decision and the M130 grounding completion already shipped.

### Phase `W03.P06` - M390 annual reverse-charge/import carrier

Confirm the reconciliacion-303 relation is the canonical annual carrier.

- [x] `W03.P06.S15` - add an import-deducible casilla to M390 (box, locale, manifest, extraction) and bind it to `ledger_iva_aggregation` import deducible, then add it to the cuota-deducible-total formula so the annual result stops over-stating the importer's amount to pay; `src/aeat/_data/registry/aeat/modelos/390/`.
- [ ] `W03.P06.S16` - add a reconciliation predicate that flags any divergence between the M390 ledger cuota-deducible-total and the reconciliacion-303 total, covering the import and reverse-charge flows; `src/aeat/_data/registry/aeat/modelos/390/`.

### Phase `W03.P07` - deferred axes and grounding

Gate the agrarian axis on a classification design; record the grounding completion.

- [x] `W03.P07.S17` - open a research note for the M130 agrarian estimación-objetiva classification axis distinguishing agrarian-objetiva from actividad-directa income before binding casilla 08; `.vault/research/`.
- [x] `W03.P07.S18` - add LIRPF art. 27/28/30 to M130 casillas 01/02/03, the income and gasto bindings, and the construct, verified by registry load and legal-grounding gates; `src/aeat/_data/registry/aeat/modelos/130/`.

## Parallelization

Waves are sequenced only where they share a file surface. W01 (M303) is internally
ordered (P01 peer-confirm precedes P02 and P03; P02 and P03 may then run in
parallel once M303 is peer-clean). W02 (M100) is independent of W01 and W03 and may
run in parallel with them. W03.P06 (M390) is independent; W03.P07.S18 is already
done and W03.P07.S17 is a research gate with no code. The hard ordering is: no M303
Step (W01.P02, W01.P03) starts until W01.P01 confirms the M303 files are peer-clean.

## Verification

The plan is complete when every Step is closed. Mission criteria: (1) no regulated
base, volume, or cuota casilla whose siblings aggregate from the ledger resolves
silently to zero on the live calculate path; (2) a fully-taxable M303 trader and a
sole-trader M100 each reach a granted `.boe` unaided, verified against the real CLI;
(3) every new binding is grounded in its binding provision cross-checked against the
bundled corpus; (4) the registry build, completeness-manifest drift, source-resolver
enrollment, binding-source-kind taxonomy, and legal-grounding gates stay green; (5)
no prorrata or recargo value is approximated on a rate/category axis that cannot
express it. W03.P07.S18 (M130 grounding) is already verified green.
