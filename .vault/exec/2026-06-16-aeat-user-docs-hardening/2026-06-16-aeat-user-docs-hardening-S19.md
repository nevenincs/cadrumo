---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S19'
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
     The S19 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden modelo-303.md and ## Scope

- `docs/how-to/modelo-303.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden modelo-303.md

## Scope

- `docs/how-to/modelo-303.md`

## Description

- Verify-close: read `modelo-303.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M14 (reverify degrades to opaque `DRAFT_HAS_ERRORS`): the page documents a complete first-quarter chain that verifies and exports a valid `.boe`; the underlying `build_draft` conditional-formula-trace defect was fixed so 303 reaches a filing-ready draft.
- Confirm finding B2 (casilla 71 silently 0.00 via casilla-65 state-attribution default): the page states casilla 65 resolves to 100 automatically for a común-territory profile (foral refused at profile creation), so casilla 66 and headline casilla 71 carry the full régimen-general result.
- Confirm finding m15 (deductible-expense rows need `--category-id`): the chain documents `--category-id material_oficina` and the `ledger categories` lookup; the `relation_prefill` naming and `iva-wallet pull-history --from-year/--to-year` fixes are present.

## Outcome

- Page verified compliant at HEAD; findings M14, B2, m15, and the 303 naming/flag fixes resolved (2026-06-19 documentation batch; build_draft + B2 engine fixes 2026-06-19). Delta: none required.

## Notes

- Residual m13 (`ledger add` gross-invariant raw pydantic dump) and m14 (`%{detail}` placeholder + malformed inline command) are APP-side ergonomics findings, already fixed per the audit; out of documentation-hardening scope. CLI conformance gate green.
