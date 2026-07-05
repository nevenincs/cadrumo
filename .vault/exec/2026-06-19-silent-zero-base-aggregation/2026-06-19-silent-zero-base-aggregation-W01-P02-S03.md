---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S03'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace silent-zero-base-aggregation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-06-19-silent-zero-base-aggregation-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The SUPERSEDED for the common case by the S05 formula default and ## Scope

- `a per-period base_amount_sum binding for volumen-total would ship a wrong prorrata for mixed traders (the regulated prorrata is the prior-year definitive percent applied provisionally + Q4 regularisation)`
- `so the faithful mechanism is deferred to a cross-period prorrata model`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/bindings/`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/bindings/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# SUPERSEDED for the common case by the S05 formula default

## Scope

- `a per-period base_amount_sum binding for volumen-total would ship a wrong prorrata for mixed traders (the regulated prorrata is the prior-year definitive percent applied provisionally + Q4 regularisation)`
- `so the faithful mechanism is deferred to a cross-period prorrata model`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/bindings/`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/bindings/`

## Description

- Re-read the silent-zero ADR, research inventory, and July 2 audit before acting on the open prorrata volume step.
- Confirmed the planned per-period `base_amount_sum` binding for `iva.prorrata-volumen-total` remains superseded by the S05 full-deduction default for the fully-taxable case.
- Confirmed the mixed-trader case still requires the cross-period prorrata mechanism: prior-year definitive percentage applied provisionally, then fourth-quarter regularisation against current-year annual volumes.

## Outcome

- `W01.P02.S03` is formally deferred, not implemented as a registry binding.
- Blocker: a current-period ledger base binding for total annual prorrata volume would calculate the wrong legal percentage for exempt-without-right traders, so shipping it would violate the no-wrong-regulated-number boundary.
- Follow-up: the cross-period prorrata regularisation mechanism named by the ADR and later IVA-complexity work, backed by the deferred `PRORRATA_REGULARIZACION` source kind and its provisional-carry store.
- Verification evidence: RAG and grep against HEAD found the ADR deferral, the July 2 audit deferral, `BindingSourceKind.PRORRATA_REGULARIZACION`, and the live prorrata regularisation advisory path rather than a live automatic binding.

## Notes

- No code was edited for this step. The correct action is to avoid a misleading `ledger_iva_aggregation` binding and keep the automatic feed gated on the cross-period design.
