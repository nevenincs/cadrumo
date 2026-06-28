---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-w01-p002-exec]]'
---

# `cli-workflow-redesign` `W01.P002` summary

W01.P002 closed the shadow duplicate removal phase for the apex root and lifecycle contract.

- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `src/aeat/entrypoints/cli/_config.py`
- Modified: `src/aeat/entrypoints/cli/_review.py`
- Modified: `src/aeat/entrypoints/cli/test_cli_surface.py`
- Modified: `src/aeat/entrypoints/cli/test_archive_cli.py`
- Modified: `src/aeat/application/auth/_operator.py`
- Modified: `src/aeat/application/review/_operator.py`
- Modified: `src/aeat/application/review/_models.py`
- Modified: `src/aeat/application/workflow/_models.py`

## Description

The phase removed accepted-root duplicate behavior by keeping the CLI root to `aeat config` and `aeat app`, unmounting rejected `app invoice`, `app declaration`, `app archive`, and `app topic` routes, and moving retained auth behavior behind application services. The review queue now exposes the accepted `app review queue/show` operator path with source-kind filtering and bucket-aware rows. Retained config/profile/auth handlers render through the shared emitter and typed command boundary rather than local JSON or Click validation paths.

Active CLI tests that preserved retired app routes were rewritten as rejection guards, and the review model layer now rehydrates persisted strict pydantic review records correctly when ledger review rows are read back from workflow state.

## Tests

Verification passed with ruff, compileall, runtime command probes for retired routes and retained auth/review routes, and the focused W01.P002 pytest selection with 142 passing tests. The mandatory vaultspec code review returned PASS with no remaining HIGH or CRITICAL issues.
