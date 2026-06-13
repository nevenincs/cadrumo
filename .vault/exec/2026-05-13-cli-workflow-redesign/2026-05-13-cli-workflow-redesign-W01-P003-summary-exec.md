---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-w01-p003-exec]]'
---

# `cli-workflow-redesign` `W01.P003` summary

W01.P003 closed de-shim and de-stub cleanup for the apex root and lifecycle contract.

- Modified: `src/aeat/entrypoints/cli/test_backend_boundary.py`
- Modified: `tests/import_contract/application/setup/test_cli.py`
- Modified: `src/aeat/core/errors/registry/_entrypoints.py`
- Modified: `src/aeat/core/errors/registry/_application.py`
- Modified: `src/aeat/application/auth/_operator.py`
- Deleted: `src/aeat/entrypoints/cli/_archive.py`
- Deleted: `src/aeat/entrypoints/cli/_declaration.py`
- Deleted: `src/aeat/entrypoints/cli/_invoice.py`
- Deleted: `src/aeat/entrypoints/cli/_topic.py`
- Deleted: `src/aeat/entrypoints/cli/auth/__init__.py`
- Deleted: `src/aeat/entrypoints/cli/auth/_registry.py`
- Deleted: `src/aeat/entrypoints/cli/test_setup_auth_live.py`

## Description

The phase removed unmounted compatibility modules for rejected CLI routes, removed deleted setup-auth transport error registrations, and replaced active setup-root expectations with assertions that `aeat setup` is unavailable. Stale command guidance in touched application, adapter, and error-registry surfaces was rewritten to accepted `config auth`, `app modelo`, `app ledger`, and `app review` grammar.

The phase also fixed the auth operator import boundary by moving workflow model imports out of module import time, avoiding the auth/workflow/outbound-auth circular import exposed by the registry importer.

## Tests

Verification passed with ruff, compileall, command probes for rejected roots, and the focused 42-test W01.P003 pytest slice. The mandatory code review returned PASS with no HIGH or CRITICAL issues.
