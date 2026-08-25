---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:9d7bd25fd0d40883188e6ba4b9761eabda8973eed3abe8f676e2a9462cadfe99'
step_id: 'S85'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S85 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
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
     The Replace application flow parity dependencies on TUI modules with backend contract assertions and ## Scope

- `src/cadrumo/application/flows/tests/test_frontend_parity.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace application flow parity dependencies on TUI modules with backend contract assertions

## Scope

- `src/cadrumo/application/flows/tests/test_frontend_parity.py`

## Description

- Delete the application-owned test that imported frontend implementation.
- Relocate three-frontend convergence, invalid-verdict, and section-copy parity proofs beneath the canonical TUI test owner.
- Retain engine, line-frontend, and localized-failure contracts beneath the application flow owner.
- Prove no application flow test imports the TUI package.

## Outcome

Application flow tests assert only frontend-neutral engine and line behavior. Frontend parity is exercised from `entrypoints.tui.tests.test_frontend_parity`, so the dependency points inward from the outer TUI boundary and no backend test reaches an entrypoint.

The focused backend and relocated parity selection passes 36 unit cases. RAG plus exact source/history audit found no remaining application-owned frontend parity file or TUI import. Independent review approved S85.

## Notes

The relocation landed through `0acec93b1a0`; the final cross-layer copy was deleted in `8c845ab92f`. No compatibility test module or import bridge was retained.
