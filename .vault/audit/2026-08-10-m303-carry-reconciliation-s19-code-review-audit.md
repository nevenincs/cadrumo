---
tags:
  - '#audit'
  - '#m303-carry-reconciliation'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:c5f1270f5de5b41c012aac9f925ac25a15f67c37adc28a0b6744ac729111fc07'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
  - "[[2026-06-21-m303-carry-reconciliation-adr]]"
  - "[[2026-08-09-m303-carry-reconciliation-prior-domiciliation-s21-audit]]"
---

# `m303-carry-reconciliation` audit: `M303 S19 Nota 3 DID export review`

## Scope

Independent formal review of S19's Modelo 303 Nota-3 DID export path against
the governing carry-reconciliation ADR amendment, the S19 plan contract, and
the S17 and S21 audit boundaries. The review covered the typed shared predicate,
renderer and parity consumers, the public export account composer and pre-write
refusal boundary, result-sign compatibility, and both supported 2025 and 2026
page-three layouts.

Evidence included the focused renderer/parity/public-export lanes (94 tests),
the independent reviewer reruns (46 tests), scoped Ruff, scoped production
basedpyright, and a targeted diff-whitespace check. The audit observed the
source and test surfaces directly; it did not modify production code.

## Findings

No triaged finding. APPROVED.

`_did_page_required` expresses the ADR's sole condition: an account-bearing
current disposition, or an M303 rectificativa with casilla 111 semantically
present and the typed KEEP election. The renderer, representability derivation,
rendered-set derivation, manifest gate, and record-order guard all route through
that condition. Typed CANCEL_OR_MODIFY removes only the Nota-3 addition, while
the current D/V/X/U account requirement remains intact.

The public C/KEEP path composes the complete RefundAccount block before the
temporary output write and before the exported event. Missing refund data
therefore refuses without bytes or event; the incompatible current U path is
refused by the existing result-sign authority. The public distinct-account
regression demonstrates that a Nota-3 C use case selects the refund destination
rather than the separate charge account. The 2025 and 2026 regressions prove
the layout-specific page-three coordinates and renderer/parity agreement.

## Recommendations

No remediation is required for S19. Retain the public distinct-account and
missing-account controls, the c111-plus-U sign-gate control, and the dual-revision
KEEP/X renderer-parity controls when the Modelo 303 export layout or account
models change.
