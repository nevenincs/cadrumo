---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:204908c8632e38b172c4554f8e210b2437f10999e738392ad9b0277bd595e240'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# `secure-storage-performance-hardening` audit: `s17 exact command spec gate review`

## Scope

The review attacked S17's sole-authority scanner for broad exemptions, false positives,
alias and reflection bypasses, assignment shapes, nontermination, and missing bite tests.

## Findings

### s17-exact-command-spec-gate-review | high | resolved broad runtime projection exemption

The first revision exempted the whole error-decoration module. The final gate allows only
the exact same-object callback wrapper and continues to reject structural construction,
decorators, registration, and metadata assignment everywhere outside the compiler.

### s17-exact-command-spec-gate-review | medium | resolved false positives and reflection bypasses

Registrar matching is now call-shape aware, so unrelated `register(record)` calls remain
valid while structural app registration bites. Constant folding, alias propagation,
reflective lookup/mutation, nested targets, and dictionary metadata assignment all have
independent negatives. Conflicting constants use a monotone lattice and cannot oscillate.
The final focused suite and Ruff pass with no blocking finding.

## Recommendations

Retain both static adversarial scanning and dynamic live-graph parity; neither should be
weakened or replaced with a hardcoded command count.
