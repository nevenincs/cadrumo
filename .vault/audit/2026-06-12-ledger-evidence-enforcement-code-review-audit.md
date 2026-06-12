---
tags:
  - '#audit'
  - '#ledger-evidence-enforcement'
date: '2026-06-12'
related:
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
  - '[[2026-06-10-ledger-evidence-enforcement-adr]]'
  - '[[2026-06-10-ledger-evidence-enforcement-research]]'
---

# `ledger-evidence-enforcement` Code Review

## LEE-001 | LOW | Shared attachment text validator over-rejected source references

Review found that the first MIME guard in `Attachment` was attached to both `source_reference` and `mime_type`, so an unusual source reference equal to the forbidden link MIME token would have been rejected even though only manifest MIME type is the enforcement axis. Fixed by leaving the shared validator as trim/blank-only and adding a dedicated MIME-only validator. Verified with the focused attachment regression and ruff.

## LEE-002 | INFO | Evidence enforcement audit passed with no open findings

Reviewed the evidence-scope diff against the plan, ADR, and research: link-only attachment storage is removed from the production path; `doclink` resolves bytes or refuses; secure attachment manifests reject link-only MIME values at model and store boundaries; missing-evidence diagnostics stay advisory and exclude cuota-less, personal, zero-amount, and non-active rows; verify integration imports through the aggregation package boundary. No HIGH or CRITICAL findings remain.
