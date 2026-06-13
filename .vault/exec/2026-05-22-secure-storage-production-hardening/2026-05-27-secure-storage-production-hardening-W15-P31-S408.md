---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S408'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W15.P31.S408`

Added real-custody CLI privacy roundtrips for the current repair list, quarantine, bootstrap, and log surfaces.

- Modified: `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`

## Description

The privacy suite now creates a real profile through the CLI, writes real encrypted secure-object rows, and creates unreadable rows by sealing payloads under a different active bucket key. No fakes, mocks, stubs, monkeypatching, `skip`, or `xfail` are used.

Coverage now includes:

- `config repair list` digest-only output for readable rows.
- `config repair list --unreadable` filters mixed readable/unreadable namespaces to degraded rows only.
- `config repair integrity objects` metadata-only unreadable-row reporting.
- `config repair quarantine --dry-run` non-mutating preview.
- `config repair quarantine --yes` explicit mutation that archives unreadable rows without disclosing payloads.
- `config repair logs` redacted log tail output.
- bootstrap-exempt repair surfaces before profile enrollment.

## Tests

Passed:

- `uv run pytest -q src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- `uv run pytest -q src/aeat/entrypoints/cli/test_repair_policy_coverage.py src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py`

Result:

- 19 focused repair tests passed.
