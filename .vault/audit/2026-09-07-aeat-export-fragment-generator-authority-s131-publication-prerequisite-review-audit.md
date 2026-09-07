---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:6f54330de56546878ed63abf6c91e796fbdd6fa0c0a9d0a226facb1f5e186cfc'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `S131 Modelo 390 publication prerequisite review`

## Scope

Reviewed the shared continuity-witness refactor, its transitive predecessor closure, the Modelo 390 2023-2025 construct legal-reference expansions, focused mutation coverage, strict typing, and the real operator CLI candidate checks.

## Findings

No HIGH or MEDIUM findings remain.

The prior CLI and enrolled-gate helpers independently copied only immediate predecessor revisions. That happened to cover Modelo 303's broad 2026 transition but failed Modelo 390's linear history: the copied 2024 or 2023 metadata retained evolutions naming an older revision that had not been staged. One pipeline-owned helper now walks only source-declared `from_revision` edges to a closed set, refuses missing or cyclic targets, copies only revision metadata, casillas, and continuity evolutions, and is consumed by both callers.

The generated layouts also require legal references beyond the old manual constructs' closure. Each 2023-2025 construct now carries the union of its existing calculation closure and its own semantic-map export closure. Epoch-specific authorities remain narrow: RDL 11/2022 occurs only in 2023, RDL 4/2024 only in 2024, and neither occurs in 2025.

The implementation introduces no cast, `Any`, type ignore, or checker suppression. The one type-ignore found by the bounded scan predates this step and remains outside the edited region.

## Recommendations

Proceed to S21 publication through the canonical CLI, then remove all four superseded manual trees, retarget the live constructs to the generated layout identities, enroll every published revision in the generated-tree drift gate, and prune the now-dormant bootstrap declarations atomically.
