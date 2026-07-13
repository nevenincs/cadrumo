---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S13'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-lifecycle-tutorials with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S13 and 2026-07-13-docs-lifecycle-tutorials-plan placeholders are machine-filled by
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
     The Author tutorials/iva-lifecycle.md: setup with optional prorrata, quarterly Modelo 303 stages with IVA-wallet seed and credit carry, optional Modelo 349 branch, annual Modelo 390 reconciliation, file and reconcile and ## Scope

- `same persona and continuous dataset as the IRPF tutorial`
- `docs/tutorials/iva-lifecycle.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author tutorials/iva-lifecycle.md: setup with optional prorrata, quarterly Modelo 303 stages with IVA-wallet seed and credit carry, optional Modelo 349 branch, annual Modelo 390 reconciliation, file and reconcile

## Scope

- `same persona and continuous dataset as the IRPF tutorial`
- `docs/tutorials/iva-lifecycle.md`

## Description

- Author `docs/tutorials/iva-lifecycle.md`: the "This page covers the ..."
  opening; the shared persona and continuous ledger explicitly continued
  from the IRPF tutorial (same rows carry the IVA detail); five stages -
  the opening IVA-wallet seed with the correction path and the
  consumed-by-filed-return refusal guard, the first paying quarter, a
  credit quarter and the carry demonstrated via `iva-wallet balance`, the
  clearly-marked optional Modelo 349 intra-community branch, and the annual
  Modelo 390 close with its quarters-must-reconcile blocking rule.
- Verify the wallet surface live this session: `aeat app modelo iva-wallet
  --help` (balance/seed/correct/override semantics, including the
  filed-consumption refusal and `--reason`/`--confirm` requirements) and
  `aeat app modelo describe 390` (annual `0A`, 22 casillas, 17 bindings).
  The 303 chain and wallet seed commands match the existing verified
  modelo-303 how-to.
- Land the deferred final trim from P01.S07: the IVA-wallet prose in
  `explanation/building-on-earlier-filings.md` now points at the tutorial
  as its live demonstration.
- No literal output transcripts were fabricated; behaviour beyond the
  verified surfaces is stated in prose.

## Outcome

The IVA lifecycle tutorial exists, the wallet workflow finally has an
actionable home (closing the phase-1 real-gap finding), and the two
tutorials share one persona and dataset as the ADR ratified.

## Notes

Same live-fire caveat as P04.S12: a full-year sandbox replay is a
follow-up candidate for the honesty review.
