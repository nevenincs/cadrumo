---
tags:
  - '#exec'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:a2be01d2c621079d559dcb289ad7973cdb3b8aaa60529c13a47b5671daed82a6'
step_id: 'S05'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` `W01.P02.S05`

## Scope

Project-structure and locale tests.

## Description

- Moved locale CLI, parity, and translation-honesty tests into the central package test harness.
- Kept locale data files untouched.

## Outcome

- Locale tests no longer live beside locale YAML data.
- Central harness now owns cross-cutting project structure and locale/tooling tests.

## Notes

- Locale file edits remain governed by the dedicated locale CLI; this step only moved test modules.
