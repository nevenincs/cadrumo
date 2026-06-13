---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W01.P005'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-w01-p005-exec]]"
---

# `cli-workflow-redesign` `W01.P005` Summary

W01.P005 is complete. The phase tightened active CLI exposure and help vocabulary for the accepted root and lifecycle contract.

Implemented changes:

- `app ledger edit` now exposes `--allocate` and rejects the retired `--split` spelling.
- `config init` exposes `--taxation-type` while persisting the existing backend profile key `declaration.type`.
- Active help copy no longer leaks rejected operator vocabulary on accepted active help surfaces.
- User-facing help tests assert rendered CLI behavior only, not ADR filenames, wave ids, phase ids, plan row ids, or execution bookkeeping.

Verification passed:

- Ruff passed for changed CLI and wizard files.
- Compileall passed for changed CLI and wizard files.
- Focused CLI/wizard test slice passed: `24 passed`.
- Broader apex/root test slice passed: `96 passed`.

Mandatory review result:

- Reviewer returned `PASS`.
- No findings were appended.
