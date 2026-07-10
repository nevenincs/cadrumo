---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S14'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-user-docs-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S14 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden import-bank-statements.md and ## Scope

- `docs/how-to/import-bank-statements.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden import-bank-statements.md

## Scope

- `docs/how-to/import-bank-statements.md`

## Description

- Verify-close: read `import-bank-statements.md` in full against the hardening standard and confirm its audit findings are resolved at HEAD.
- Confirm finding M4 (no sample CSV / column format): the page now shows the concrete bank-CSV format (semicolon separator, comma decimals, `Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda` header with worked rows) and documents the sign-carries-direction convention.
- Confirm the dry-run-first workflow, the recognized provider list, and the manual-add path are documented with resolving commands.

## Outcome

- Page verified compliant at HEAD; audit finding M4 resolved (2026-06-19 batch). Delta: none required this pass.
- Imperative steps, precondition block, dry-run-first safety, format example, resolving cross-links.

## Notes

- Residual m1 (missing-file import traceback) is an APP-side finding, already fixed per the audit (clean typed refusal). CLI conformance gate green.
