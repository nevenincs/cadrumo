---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'W04.F27'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
  - '[[2026-05-21-live-iva-compensation-wallet-code-review-audit]]'
  - '[[2026-05-21-live-iva-compensation-wallet-persona-testimonials-audit]]'
---

# `live-iva-compensation-wallet` `W04.F27`

Added public CLI privacy contracts for repair and secure-object inventory.

- Created: `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- Modified: `src/aeat/application/test_repair_integrity.py`

## Description

The W04.F25 and W04.F26 mitigations were initially verified through application
tests and local shell smoke checks. This step makes the guarantee architectural:
the public CLI now has a regression contract that creates a real profile through
`config profile create`, writes a real encrypted secure-object row under the
active storage backend, and then exercises `config repair` and `config repair
list` in text and JSON modes.

The test asserts that public command output does not expose UUID-shaped active
profile identifiers while still rendering readiness counts, row context, and
placeholder object-key hints. The repair attribution invariant was also
tightened so it rejects actual payload disclosure while allowing the explicit
metadata field `payload_disclosure`.

No destructive repair command was run. No live AEAT operation was performed in
this step.

## Tests

- `uv run pytest src/aeat/entrypoints/cli/test_repair_privacy_contract.py -q --disable-warnings` completed with 2 passed.
- `uv run pytest src/aeat/application/test_repair_integrity.py::TestReportInvariants::test_unreadable_attribution_report_is_metadata_only src/aeat/entrypoints/cli/test_repair_privacy_contract.py -q --disable-warnings` completed with 3 passed.
- `uv run pytest src/aeat/entrypoints/cli/test_repair_privacy_contract.py src/aeat/application/test_repair_integrity.py src/aeat/application/test_diagnostics.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py -q --disable-warnings` completed with 62 passed.
- `uv run ruff check src/aeat/entrypoints/cli/test_repair_privacy_contract.py src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py src/aeat/application/diagnostics.py src/aeat/application/test_diagnostics.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py` passed.
