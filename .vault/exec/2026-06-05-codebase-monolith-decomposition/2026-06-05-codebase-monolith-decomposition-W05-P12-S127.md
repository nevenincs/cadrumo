---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S127'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W05.P12.S127 Adapter Test Split

Scope: split oversized inbound and outbound adapter tests by external contract surface.

## Description

- Split declaracion verification-chain and parser-boundary tests into focused sibling modules with shared parser support.
- Split AEAT sede declaration tests into focused sibling modules with shared declaration support.
- Split AEAT authenticator tests into focused sibling modules with shared authenticator support.
- Split secure-object SQL tests and runtime migrated repository tests into focused sibling modules with shared persistence support.
- Restored the original `hex_*` markers on every split test module.

## Outcome

The tracked adapter test monoliths are decomposed below the hard line budget while preserving real parser, PDF, browser-auth, SQL, and runtime repository behavior coverage.

## Notes

Verification passed for Ruff and compileall across the S127 split files, 95 parser-boundary tests, 94 verification-chain tests, 61 outbound declarations tests, 80 focused auth tests, 137 storage repository tests, and the 2-test hard codebase size-budget guard. The combined inbound lane is slow on Windows, so it was verified as parser and verification sub-lanes rather than swallowed behind a timeout.
