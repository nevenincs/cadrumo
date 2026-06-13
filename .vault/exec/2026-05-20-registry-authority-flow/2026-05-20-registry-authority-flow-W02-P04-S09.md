---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S09'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W02.P04.S09`

Rejected duplicate nested export field ids during same-record fragment appends.

- Modified: `_loader.py`
- Created: this execution record

## Description

Added merge-time duplicate id detection for appendable same-record table fragments, keeping existing single-fragment semantics while blocking cross-fragment duplicate field ids.

## Tests

Covered by `test_directory_mode_rejects_duplicate_export_field_ids_after_record_merge`.
