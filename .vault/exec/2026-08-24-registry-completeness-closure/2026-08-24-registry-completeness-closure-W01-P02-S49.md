---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:d0455e7bab8427c0364a6e4a3826270a7360a458cbacd5d914bec21762682957'
step_id: 'S49'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Replace substring-based connected-proof failure taxonomy with structured cause mapping that distinguishes missing proof from digest conflict, with real deletion and drift composer regressions.

## Scope

- `src/cadrumo/application/registry/`

## Description

- Add the closed `SourceConnectivityProofFailureCause` taxonomy to the core proof contract and expose it through the core facade.
- Emit stable Pydantic error types for source enrollment, operator workflow, encrypted provenance, missing executable evidence, and executable-evidence digest mismatch.
- Project the typed cause through `compose_source_connectivity_coverage` and map only digest mismatch to `conflicting_evidence`; retain every other live-proof failure as `missing_evidence`.
- Exercise real live-authority proof material backed by the encrypted calculation repository, then separately mutate the executable evidence bytes and delete the executable evidence file.
- Verify with `uv run --no-sync ruff check src/cadrumo/core/source_connectivity.py src/cadrumo/core/__init__.py src/cadrumo/core/tests/test_source_connectivity.py src/cadrumo/application/registry/_source_connectivity_coverage.py src/cadrumo/application/registry/tests/test_source_connectivity_authority.py` and `uv run --no-sync pytest -q -n 0 src/cadrumo/core/tests/test_source_connectivity.py src/cadrumo/application/registry/tests/test_source_connectivity_authority.py src/cadrumo/application/registry/tests/test_source_connectivity_coverage.py`.

## Outcome

The closure composer no longer infers evidence conflict from prose. A real digest drift produces `conflicting_evidence`; a real missing executable proof produces `missing_evidence`. The selected verification lane passed: 54 tests passed, 18 integration-marked tests deselected.

## Notes

No production or fixture data was deleted. The deletion regression removes only its temporary executable-evidence file within pytest's isolated temporary repository.
