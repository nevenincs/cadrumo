---
tags:
  - '#audit'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-repo-health-triage-adr]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# `repo-health-triage` W02 Typecheck Baseline

## TYPE-001 | HIGH | Focused W02 type errors cleared

Status: remediated.

The focused W02 file set previously reported 15 `ty` diagnostics and 24 Pyright
errors across counterpart source-kind typing, secure repository payload type
overrides, sanitizer narrowing, source-mesh protocol bodies, registry-provider
date narrowing, and usage-ratio generic arguments.

After W02 repairs, `ty check` reports no diagnostics on the focused file set.
Pyright reports 0 errors and 23 warnings. The remaining warnings are pre-existing
type-improvement opportunities: one private date parser import warning, repeated
unnecessary Decimal runtime-check warnings in registry bindings, and two unused
private helper warnings in registry bindings.

## TYPE-002 | MEDIUM | Focused behavior gates remained green

Status: verified.

Focused aggregation and registry behavior tests passed with 79 tests. Secure
repository behavior tests passed with 60 tests. Sanitizer and usage-ratio behavior
tests passed with 378 tests.
