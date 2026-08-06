---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:a88f5b99ac48ee7eeb9d5a420e743a940815d574f6bb5cc10bbd3aba73f5b5a3'
step_id: 'S95'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Repair the 9cb authority regression while preserving reciprocal ADR supersession

## Scope

- `.vault/adr/2026-07-12-cadrumo-product-rename-adr.md`
- `.vault/adr/2026-07-12-cadrumo-cli-executable-adr.md`
- `src/cadrumo/core/product_identity.py`
- `src/cadrumo/core/tests/test_product_identity.py`
- `.vault/plan/2026-07-12-cadrumo-product-rename-plan.md`
- `S95 execution record`

## Description

- Ground the regression in commit `9cb54a26f6` and the current authority audits before editing.
- Preserve the parent ADR's reciprocal `superseded_by` edge and `superseded` status while refreshing its modified stamp through the Vaultspec metadata command.
- Restore the accepted exact identity matrix in the executable ADR, runtime authority, and direct contract test.
- Remove the ungrounded third operator reconfirmation, wordmark-only mandate, and malformed executable claim introduced by the mixed commit.
- Reopen S07, S87, S90, and S93 through the Vaultspec plan CLI while retaining every other audited Step state.
- Exclude the concurrent S58 execution-record work from this Step and commit.

## Outcome

- The binding tuple is again display `CADRUMO`, Python/distribution/repository/MCP/plugin `cadrumo`, human executable `aeat`, MCP executable `cadrumo-mcp`, environment prefix `CADRUMO_`, the two exact companion distributions, namespace `cadrumo_data`, and authority short name `AEAT`.
- The parent supersession hunk from `9cb54a26f6` is preserved and now has a Vaultspec-maintained `2026-07-13` modified stamp.
- S07, S87, S90, and S93 are open; S08, S38, S89, S91, S92, and S94 remain checked; S05, S86, S62-S67, and the S94-reopened descendants remain open.
- S95 is the only newly completed Step. Independent review follows, then the S91 evidence receives authority-aware re-review.

## Notes

- The dirty S58 record belongs to a concurrent worker and remains outside S95 staging and history.
- Historical quoted commit title `"restore canonical Cadrumo executable"` remains verbatim because it names an earlier commit, not the current display contract.
- Vault checks pass for ADR status, frontmatter, markdown, and placeholders. Modified-stamp and annotation checks retain only pre-existing warnings outside the S95-owned documents.
- Plan validation retains the known non-monotonic `PLAN022` warning. Rule sync dry-run reports the CADRUMO naming rule unchanged in every provider; unrelated generated wrapper documents remain drifted.
- Concurrent merge `f70329749d` absorbed the staged S95 baseline while resolving a foreign marketplace conflict; this closeout removes the conflicting title-case status note introduced by that merge.
