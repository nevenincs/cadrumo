---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:e9608f7adab2e96cb8a32706a64585488db32ada130a888ecdf8fe67d48406d4'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `S130 Modelo 390 bootstrap target review`

## Scope

Reviewed the three new Modelo 390 bootstrap declarations and their focused gate against the accepted narrow-widening rule, the existing S129 bootstrap mechanism, the official source identities already pinned by S80-S82, and the live unpublished target state.

## Findings

No HIGH or MEDIUM findings remain. Each declaration names one exact modelo, revision, source reference, source SHA-256, generated layout identity, CRLF transport, superseded manual layout identity, and expected construct-reference count. The gate exercises all four Modelo 390 declarations as concrete typed parameters and retains the wrong-digest and missing/stale/widened reference-count refusals. The implementation adds no cast, `Any`, type ignore, or checker suppression.

The downstream CLI replay correctly progressed beyond bootstrap selection and exposed separate S21 prerequisites in construct legal-reference closure and transitive continuity staging. Those failures do not weaken these declarations; they demonstrate that the pins widen only bootstrap selection and do not bypass later validation.

## Recommendations

Commit S130 independently so the evidence-carrying authorization exists before publication. Resolve the newly exposed validation prerequisites in a separate derived step, then let S21 publish and prune every bootstrap declaration whose target has become live.
