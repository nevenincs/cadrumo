---
tags:
  - '#adr'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-08'
related:
  - '[[2026-06-16-aeat-user-docs-hardening-plan]]'
  - '[[2026-06-18-aeat-user-docs-hardening-audit]]'
---

# `aeat-user-docs-hardening` adr: `user docs hardening authority alignment` | (**status:** `accepted`)

## Problem Statement

The `aeat-user-docs-hardening` feature carries a plan (32 per-page how-to hardening steps) and a large persona-driven audit, but no local decision-authority node. The feature-lifecycle checker requires research to ADR to plan to exec, so no execution record can be scaffolded for the feature and no plan step can be honestly closed until an ADR anchors it. This is a curation-alignment concern, not a new implementation mandate.

## Considerations

The hardening work is driven by the naive-user persona audit that exercised the full user-facing documentation surface against the live CLI and confirmed every finding at HEAD. The substantive remediation of that audit's findings (the doc rewrites and the paired application fixes) was largely landed by an earlier documentation batch; the remaining work is a per-page verify-close confirming each page meets the hardening standard at HEAD, spot-fixing any residual gap, and closing the stale plan ledger. A sibling feature (`aeat-cli-userdocs-hardening`) carries its own executed campaign and its own curation ADR; the two are distinct efforts kept on distinct feature tags rather than merged.

## Considered options

- Create a same-feature authority ADR (chosen): gives `aeat-user-docs-hardening` its required decision node, unblocks exec records, and keeps the feature distinct from the executed `aeat-cli-userdocs-hardening` campaign.
- Rename/merge the feature into `aeat-cli-userdocs-hardening` (rejected): the two are genuinely different efforts (a big executed W01-W07 campaign vs this later audit-remediation plan); merging would conflate their ledgers and lose the distinction.

## Constraints

Vault-only. No application code, tests, registry data, or runtime behaviour is changed by this ADR. The hardening standard is defined by the `aeat-user-docs-hardening` and `aeat-documentation-workflow` rules and validated by the documented-command conformance gate and the nitpicky Sphinx build; this ADR does not restate those.

## Implementation

Treat this ADR as the authority node for the hardening feature. Per-page verify-close reads each how-to page against the hardening standard, confirms the audit findings for that page are resolved at HEAD, records the honest per-page delta in an execution record, and marks the plan step closed. Spot-fixes are applied only where a real residual gap remains; compliant pages are not rewritten, preserving the story-driven narrative the pages already deliver well.

## Rationale

A same-feature ADR resolves the lifecycle-gap that blocks honest ledger closure while keeping the feature graph clean and the two related campaigns distinct. It records the decision to verify-close rather than rewrite, so a future reader understands why the closed steps carry small or empty deltas: the pages were authored to standard and remediated earlier, and this pass verifies and records that state.

## Consequences

Execution records can now be scaffolded and the stale 0/32 ledger closed against real per-page verification evidence. The feature retains a distinct authority node for future semantic discovery. The risk is that a future reader mistakes the verify-close deltas for no-op churn; the per-page execution records name the specific verification performed and any spot-fix to keep the evidence honest.
