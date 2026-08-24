---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:8f5c7dc10a6d09f3664b56520e9c7f44489290b7be0766f5121d28ee6d9e0733'
step_id: 'S18'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Replace invalid M210 quarter identities with canonical EVENT-N or 0A identities and author ResultDisposition plus official-code-qualified variants

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/210/revisions/`

## Description

- Locate the canonical M210 deadline coordinate, Period contract, qualifiers, and governing ADR with Vaultspec RAG before editing.
- Remove fabricated quarter deadline identities from both M210 revision owners.
- Author fixed annual windows on canonical `0A` with the existing `ResultDisposition` and official two-digit codes 01, 35, and 02.
- Preserve `EVENT-N` as the registry selector for event-shaped filings and leave tipo 28 without a numeric window.
- Prove each annual row is selected by exactly one canonical revision owner and preserves the 2026 tipo-02 amendment boundary.

## Outcome

- M210 deadline data contains no synthetic 1T-4T identities.
- The 2025 owner carries 2025 annual facts and the 2026 owner carries 2026 annual facts; `select_revision` resolves each owner exactly.
- Rental ingreso, zero, and refund rows use canonical result dispositions and official rental codes 01/35; imputed rent uses official code 02.
- The tipo-02 2025 whole-following-year interval and 2026 April-December interval remain distinct.
- No enum, code projection, period parser, semantic coordinate, selector, or resolver was redeclared.

## Notes

- Whole-tree pytest was temporarily blocked by concurrent incomplete Modelo 322 fragment authoring. Direct M210 loading, isolated M210 validation, focused ownership proof, schema/ownership tests, and Ruff were used without touching that peer-owned file.
- Atomic overlap validation initially and correctly rejected unqualified zero/refund rows overlapping tipo 02. The data was corrected by keeping this Step's annual result variants within the grounded official 01/35 rental scope; the validator was not weakened.
