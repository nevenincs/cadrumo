---
tags:
  - '#audit'
  - '#calculation-engine-foundations'
date: '2026-06-12'
modified: '2026-08-26'
body_hash: 'sha256:8cb775bb74481a762f10fd97be68aafc368714b2dda287b65859d47350b3508e'
related:
  - '[[2026-06-10-calculation-engine-foundations-plan]]'
---

# `calculation-engine-foundations` Code Review

## CALC-001 | PASS | S31 unresolved relation propagation

Reviewed the source-mesh unresolved relation channel, relation-prefill diagnostics, engine dependency propagation, caller override filtering, and M200 live regression. No CRITICAL, HIGH, MEDIUM, or LOW findings remain. The path preserves the hard `RegistryValidationError` behavior for relation operands missing outside the explicit unresolved source channel, while formula-consumed source absence now produces an advisory and omits the dependent computed casilla.

## OSS-001 | PASS | S38 M369 live invoice projection

Reviewed the invoice OSS/IOSS axes, line-level OSS rate tier, repository projection into `OssIossLedgerCandidate`, live source-mesh enrollment, source id persistence shape, and M369 live regression. No CRITICAL, HIGH, MEDIUM, or LOW findings remain. The implementation keeps explicit-candidate resolver mode, validates live invoice candidates against destination Member State rates, and rejects `oss_rate_kind` on invoices without invoice-level OSS/IOSS axes.

## TEST-001 | PASS | Real-behavior verification

Focused tests exercise encrypted repository-backed calculation paths without fakes, mocks, monkeypatches, skips, or xfails. Residual risk is limited to broader full-suite interactions outside the touched source mesh and invoice/M369 surfaces; the directly related suites passed.
