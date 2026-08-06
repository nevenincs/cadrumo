---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-20'
modified: '2026-07-17'
body_hash: 'sha256:113cb1f1aae7445cdeac6366c5b1b8906c886ee0939038c48996fe684bc9fd25'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W02.P04` summary

Repaired nested export identity for appended fragments.

- Modified: `_loader.py`, `test_loader_directory_mode.py`
- Created: step execution records

## Description

Directory-mode merges now reject duplicate ids when same-record fragments append table arrays, covering export field duplication without broadening validation beyond the current committed registry contract.

## Tests

`test_loader_directory_mode.py` passed.
