---
tags:
  - '#audit'
  - '#ast-exception-gate-remediation'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:8b20acdd3b83f9436d25a405e9b76f6bf8802c1d46e7794342fae0a520dfb4c0'
related:
  - '[[2026-07-08-gate-drift-reconciliation-plan]]'
---

# `ast-exception-gate-remediation` audit: `closeout review`

## Scope

The review covered the AST-backed exception-hygiene and error-registry gates, the
explicit source-descriptor contract, and the per-class rationale declarations required
by the restored hygiene scan. It checked that discovery remains source-based and
non-importing, that runtime classes and source records are handled explicitly, and that
the gate populations cannot pass vacuously.

## Findings

No high- or medium-severity findings remain in the reviewed core diff. Source records
use ordinary `module`, `qualname`, `name`, and `bases` data instead of reserved Python
class metadata; registry keying and diagnostic formatting consume those fields directly.
The qualname walkers cover the same class population reached by `ast.walk`, and both
anti-vacuity floors remain enforced.

### adjacent-tui-descriptor | low | A separate TUI gate retains the same reserved-metadata pattern

`src/cadrumo/entrypoints/tui/tests/test_textual_private_attribute_shadowing.py` still
defines `__module__` and `__qualname__` properties on its AST descriptor. That module is
outside the core exception lane and was not changed here, but it remains a separate
collection risk.

## Recommendations

Remediate the adjacent TUI descriptor through its owning lane by replacing the reserved
metadata properties and their consumers with explicit source fields.
