---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S26'
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
     The S26 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden reconcile.md and ## Scope

- `docs/how-to/reconcile.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden reconcile.md

## Scope

- `docs/how-to/reconcile.md`

## Description

- Verify-close: read `reconcile.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding m11 (mismatches showed SHA-256 hashes, not legible values; evidence_invalid framing): the page now documents the three verdicts (matches / mismatches / evidence_invalid), and a `mismatches` verdict names the differing header field and shows the LOCAL value next to the value in the justificante (legible, not a hash).
- Confirm the page states honestly that reconciliation compares header fields (modelo, filing year, period, tax id), not box/casilla totals, and points to the amendment path for a wrong box value.
- Confirm the two transports (`reconcile file --file` and `reconcile pull`) and their auth/refusal behaviour are documented.

## Outcome

- Page verified compliant at HEAD; finding m11 resolved (legible mismatch values; evidence_invalid as a documented verdict). Delta: none required.

## Notes

- Residual m16 (invalid-PDF parser-internals leak) is APP-side, fixed per the audit (clean typed `evidence_invalid` refusal). CLI conformance gate green.
