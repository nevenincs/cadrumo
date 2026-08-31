---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:82062b50b1d0cfdb244891922fa1e7e9ec8a4382cd67d64f084dd93d5847c243'
related:
  - "[[2026-08-05-ci-lane-deconflation-P05-S192]]"
---
# `ci-lane-deconflation` audit: `p05 s192 execution self review`

## Scope

Immutable source commit `945987e7cd8530f4484073b82ebc576d0d715478`, its 32-path schema split, the direct-import boundary, byte-accurate module sizes, and the execution record's evidence wording.

## Findings

No CRITICAL, HIGH, or MEDIUM findings.

### reported-focused-receipt | low | The focused pytest command is unavailable

The executor reported `83 passed in 2.76s`, ruff and format clean, and `py_compile` clean, but preserved no literal pytest command. The record labels those as executor-reported rather than reconstructing an invocation or claiming a new run.

### module-specific-global-audit | low | The size result is not a whole-tree result

The 1185, 211, and 161 byte-based physical counts prove only S192's three modules remain below 1250. The executor reported 59 unrelated global findings with schema absent; the record does not present that as a green global audit.

## Recommendations

Keep future focused-test receipts with their exact command and terminal summary. Re-run global debt checks separately and attribute any finding to its owning module.
