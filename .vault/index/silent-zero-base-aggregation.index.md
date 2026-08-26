---
generated: true
tags:
  - '#index'
  - '#silent-zero-base-aggregation'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:8d86b91475ab6de9cbe5156d5f36ea8b32eb8400fd6a9cf77ee9f00ee302738a'
related:
  - '[[2026-06-19-silent-zero-base-aggregation-adr]]'
  - '[[2026-06-19-silent-zero-base-aggregation-audit]]'
  - '[[2026-06-19-silent-zero-base-aggregation-plan]]'
  - '[[2026-06-19-silent-zero-base-aggregation-research]]'
  - '[[2026-06-20-silent-zero-base-aggregation-research]]'
  - '[[2026-07-02-silent-zero-base-aggregation-audit]]'
  - '[[2026-07-05-silent-zero-base-aggregation-audit]]'
---

# `silent-zero-base-aggregation` feature index

Auto-generated index of all documents tagged with `#silent-zero-base-aggregation`.

## Documents

### adr

- `2026-06-19-silent-zero-base-aggregation-adr` - `silent-zero-base-aggregation` adr: `Silent-zero regulated-base aggregation: bounded mirror vs ADR boundary` | (**status:** `accepted`)

### audit

- `2026-06-19-silent-zero-base-aggregation-audit` - `silent-zero-base-aggregation` audit: `Adversarial aggregation audit: cuota-side drops, recargo, annual coverage, reverse-charge symmetry`
- `2026-07-02-silent-zero-base-aggregation-audit` - `silent-zero-base-aggregation` audit: `Wave 1 D9 close-blocker audit`
- `2026-07-05-silent-zero-base-aggregation-audit` - `silent-zero-base-aggregation` audit: `campaign close honesty review`

### exec

- `2026-06-19-silent-zero-base-aggregation-W03-P07-S18` - add LIRPF art. 27/28/30 to M130 casillas 01/02/03, the income and gasto bindings, and the construct, verified by registry load and legal-grounding gates
- `2026-06-19-silent-zero-base-aggregation-W01-P02-S05` - fix the prorrata-porcentaje no-volume-data default from 0 to 100 (full right to deduct, LIVA art-94) so a fully-taxable trader's export unblocks, with a regression test - the correct peer-clean fix for defect C2
- `2026-06-19-silent-zero-base-aggregation-W01-P03-S07` - model recargo de equivalencia on the transaction (recargo rate + recargo cuota alongside the IVA fields, or a dedicated recargo classification) grounded in ley-37-1992:art-161 against the bundled corpus - the prerequisite domain change before any recargo binding
- `2026-06-19-silent-zero-base-aggregation-W01-P03-S08` - add `ledger_iva_aggregation` bindings selecting `recargo_equivalencia` at each recargo tier for the recargo base and cuota casillas, grounded
- `2026-06-19-silent-zero-base-aggregation-W01-P03-S09` - bind the recargo casillas, update the M303 manifest and construct, and add a real-behavior test that a recargo supplier's recargo cuota aggregates instead of reporting zero
- `2026-06-19-silent-zero-base-aggregation-W02-P04-S10` - add an annual M100 actividad-económica income aggregator (annual window, actividad eligibility) mirroring the first-slice expense pipeline shape
- `2026-06-19-silent-zero-base-aggregation-W02-P04-S11` - admit the annual M100 income target in the renta-income source selector and resolver without disturbing the M130 quarterly path, with the build-validation family case
- `2026-06-19-silent-zero-base-aggregation-W02-P05-S12` - bind M100 casilla 0171 to the annual income aggregation (project verb uses the formula-runtime path, so no disentanglement needed) with grounded legal_refs (LIRPF art. 27/28)
- `2026-06-19-silent-zero-base-aggregation-W02-P05-S13` - sweep the M100 tests that supply 0171 to the bound path and rerun the M100 registry, formula-runtime, and verification gates green
- `2026-06-19-silent-zero-base-aggregation-W03-P06-S15` - add an import-deducible casilla to M390 (box, locale, manifest, extraction) and bind it to `ledger_iva_aggregation` import deducible, then add it to the cuota-deducible-total formula so the annual result stops over-stating the importer's amount to pay
- `2026-06-19-silent-zero-base-aggregation-W03-P07-S17` - open a research note for the M130 agrarian estimación-objetiva classification axis distinguishing agrarian-objetiva from actividad-directa income before binding casilla 08
- `2026-06-19-silent-zero-base-aggregation-W01-P01-S01` - complete the abandoned-stale peer base-binding work for casillas 01/04/07/28 (bound to ledger_iva_aggregation base_amount_sum) by adding them to the M303 completeness manifest and construct so the calculation closure and manifest agree
- `2026-06-19-silent-zero-base-aggregation-W01-P01-S02` - rerun the completeness-manifest drift gate and M303 registry build and record green after the base casillas join the manifest/construct
- `2026-06-19-silent-zero-base-aggregation-W01-P02-S06` - add a real-CLI end-to-end test that a fully-taxable M303 trader reaches a granted `.boe` with no prorrata-divergence error and no manual prorrata input
- `2026-06-19-silent-zero-base-aggregation-W02-P05-S14` - add a real-CLI end-to-end test that a sole-trader's M100 casilla 0171 / 0180 / 0224 populate from the ledger unaided
- `2026-06-19-silent-zero-base-aggregation-W03-P06-S16` - add a reconciliation predicate that flags any divergence between the M390 ledger cuota-deducible-total and the reconciliacion-303 total, covering the import and reverse-charge flows
- `2026-06-19-silent-zero-base-aggregation-W01-P02-S03` - SUPERSEDED for the common case by the S05 formula default
- `2026-06-19-silent-zero-base-aggregation-W01-P02-S04` - SUPERSEDED/deferred with S03: volumen-con-derecho per-period binding is not the regulated provisional+regularised prorrata

### plan

- `2026-06-19-silent-zero-base-aggregation-plan` - `silent-zero-base-aggregation` plan

### research

- `2026-06-19-silent-zero-base-aggregation-research` - `silent-zero-base-aggregation` research: `Silent-zero regulated-base aggregation inventory`
- `2026-06-20-silent-zero-base-aggregation-research` - `silent-zero-base-aggregation` research: `M130 agrarian estimacion-objetiva income classification axis`
