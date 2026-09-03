---
tags:
  - '#audit'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:f3f0e4ccca133752db4f4eb351331964d806c6b5db5d7fcb76c9842a4570dd4f'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---
# `modelo-200-semantic-crosswalk` audit: `W02 P04 identity review`

## Scope

Reviewed the target-source identity worklist CLI, its review-output boundary, and the closed fail-closed classifications for W02.P04.

## Findings

### review-output-containment | high | A writable review destination was unclosable

The CLI accepted an arbitrary `--output` path. Traversal, link aliases, hardlinks, and concurrent filesystem replacement make a user-space destination proof insufficient for a non-authoritative diagnostic. The remediation removes the destination argument and every filesystem-writing helper; the CLI emits the proposal-only TOML worklist to stdout only.

### target-worklist-export | high | CLI exported the retired candidate stream

The CLI wrote the legacy 156-row candidate report instead of the target identity worklist. The remediation emits the proposal-only target worklist with all 185 map-owner mismatches, two orphaned declarations, and 15 printed-identity diagnostics, including typed counts in the TOML document.

### missing-casilla-owner | high | A casilla map entry could omit its owner without detector coverage

The classifier rejected a missing casilla owner in implementation, but no detector exercised it. The remediation adds a mutation test that proves the omission is refused.

## Recommendations

Keep identity diagnostics stdout-only and proposal-only. Any future persistence capability needs a separately owned authority boundary rather than a destination argument on this CLI.
