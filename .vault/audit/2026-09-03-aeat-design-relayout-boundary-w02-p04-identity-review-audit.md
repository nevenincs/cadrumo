---
tags:
  - '#audit'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:9faf79226dbe18ab28b7b621712e4ff089673043c55619a0dd94198c402de6da'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---
# `modelo-200-semantic-crosswalk` audit: `W02 P04 identity review`

## Scope

Reviewed the target-source identity worklist CLI, its review-output boundary, and the closed fail-closed classifications for W02.P04.

## Findings

### review-output-containment | high | Canonical registry overwrite was possible

The CLI accepted an arbitrary `--output` path and used an atomic replacement without proving that the destination stayed outside canonical registry authority through path traversal, link aliases, hardlinks, or a parent-swap race. The remediation now refuses lexical and resolved canonical-root containment, opens only non-linked regular files, requires a single link, and repeats path-and-handle identity checks before truncation.

### target-worklist-export | high | CLI exported the retired candidate stream

The CLI wrote the legacy 156-row candidate report instead of the target identity worklist. The remediation writes the proposal-only target worklist with all 185 map-owner mismatches, two orphaned declarations, and 15 printed-identity diagnostics.

### missing-casilla-owner | high | A casilla map entry could omit its owner without detector coverage

The classifier rejected a missing casilla owner in implementation, but no detector exercised it. The remediation adds a mutation test that proves the omission is refused.

## Recommendations

Keep review diagnostics proposal-only and preserve the handle-verified output boundary for every future write-capable review CLI.
