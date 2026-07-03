---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S27'
related:
  - '[[2026-06-30-cli-persona-testimonials-plan]]'
---

# W05.P10.S27 Touched-Surface Calculation And CLI Gates

Scope: calculation, registry, CLI, ledger, live-read, and Modelo touched surfaces
from the W04 hardening closeout.

## Description

Run the W04 touched-surface gates and repair one campaign-owned test-harness
mismatch discovered by those gates.

RAG grounding:

- `uvx vaultspec-rag search "calculation registry CLI ledger gates touched surfaces all green persona campaign" --type code`
- Additional targeted code RAG searches covered CLI schema, ledger IVA/preflight,
  registry legal verifier, and live read/justificante surfaces.

## Outcome

Fixed:

- `src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py`
- `src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py`

The live CLI tests now seed service data under the same active UUID test bucket
that the secure-storage fixture opens. The failing pre-fix signature was a
storage bucket mismatch: the fixture created the UUID bucket while selected test
seeds still wrote to `default`.

Passed after the fix:

- W04 touched-file ruff gate from `git show --name-only --format= 86c10a724 -- src/aeat` -> passed.
- `uv run --no-sync pytest -q --tb=short src/aeat/application/aggregation/tests/test_iva_ledger.py src/aeat/application/ledger/tests/test_preflight_anomaly.py src/aeat/domain/iva/tests/test_saturation.py` -> 61 passed.
- `uv run --no-sync pytest -q --tb=short src/aeat/domain/calculations/registry/tests/test_catalogue_verification_verifiers.py src/aeat/domain/calculations/registry/tests/test_registry_legal_grounding.py` -> 38 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py` -> passed.
- Isolated rerun of the three previously failing live CLI tests -> 3 passed.
- `uv run --no-sync pytest -q --tb=short -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py` -> 131 passed.
- `uv run --no-sync pytest -q --tb=short src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/live/tests/test_justificante_capture.py src/aeat/application/live/tests/test_justificante_capture_stamp.py` -> 42 passed.
- Modelo/refund/calendar touched tests -> 56 passed.
- Registry CLI verify command -> 1 passed.
- Ledger preflight module -> 6 passed.
- Ledger preflight CLI verb -> 7 passed.

S27 is complete. No source-catalogue byte-count drift surfaced in these focused
gates.

## Notes

The initial CLI integration group failed with 3 failed and 128 passed; all three
failures were the same live CLI test-harness bucket mismatch and were resolved
by the two test-file edits above. Concurrent WIP was present outside the
campaign-owned files during the run and was not edited or reverted.
