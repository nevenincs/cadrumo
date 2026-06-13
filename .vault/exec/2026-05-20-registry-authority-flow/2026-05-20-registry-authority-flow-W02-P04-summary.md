---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-20'
modified: '2026-05-20'
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
