---
tags:
  - '#audit'
  - '#calendar-semantics'
date: '2026-06-12'
modified: '2026-06-12'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-05-calendar-filing-semantics-adr]]'
---

# `calendar-semantics` Code Review

## CALENDAR-001 | INFO | No blocking findings

Reviewed the calendar-semantics slice for the local filing versus AEAT submission distinction. The implementation keeps local Modelo records created by normal operators as `ready_to_file` even when they carry AEAT external evidence, and reserves `external_baseline_imported` for `aeat-import` actors. Targeted unit and CLI integration tests passed.
