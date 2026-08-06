---
tags:
  - '#audit'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:d00bde7e66ff61807a4ff02c3685badbbaf018ea1310d69f7ecbc6a94b7dca58'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
  - "[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]"
  - "[[2026-08-05-modelo-parity-rollup-denominator-research]]"
---
# `modelo-parity-rollup` audit: `S03 classification census review`

## Scope

Reviewed W01.P03.S03 against the accepted annual-matrix contract, with focus on the closed classification vocabulary, census integrity, duplicate-coordinate protection, and the distinction between the finite D2025 matrix and the 73-modelo/90-revision portfolio.

## Findings

### classification-census | low | The six-class census is enforced and now has real failure coverage

The production `ConformanceCoordinateMatrix` validator requires every supported disposition key, requires the census to equal the enumerated coordinate population, and rejects duplicate exact coordinates. Three new real tests exercise incomplete-key, mismatched-count, and duplicate-coordinate failures. The only current coordinate remains D2025 with `not_yet_measured`; the other five classes are explicit zeroes, not omitted populations.

### finite-matrix-boundary | low | The annual classification ledger remains intentionally provisional

The matrix still contains only `(100, 2025, 0A)` selected through the validating authority. No unsupported, open-ended, manual, upstream, or deferred coordinate was fabricated to fill the taxonomy. Expanding those populations belongs to later finite-coordinate and semantic-decision work.

### shared-test-typing | low | Existing unrelated test-file typing debt remains outside S03

Manager typing is clean. The whole `dev/tests/test_registry_conformance_cli.py` still reports 11 pre-existing `CliRunner`/optional-value diagnostics at unrelated later lines; no S03-added typing errors remain. This is retained as a verification boundary and not repaired opportunistically.

## Recommendations

- Keep the six-class census validator as the invariant for every later annual-coordinate expansion.
- Add coordinates only when the law-selected revision, period, and evidence classification are explicit; preserve zero-count classifications in every serialized census.
- Carry the test-file typing debt separately rather than widening S03 or masking it.

## Verification

- `uv run --no-sync pytest -q -n0 dev/tests/test_registry_conformance_cli.py -k "annual_matrix_rejects"` â€” 3 passed; 87 deselected by the configured unit selector.
- A broader `-k annual_matrix` run reached 4 passed and 1 transient cache-fingerprint failure caused by concurrent registry churn; the new three validator tests all passed.
- `uv run --no-sync ruff check dev/registry/conformance/manager.py dev/tests/test_registry_conformance_cli.py` â€” all checks passed.
- `uv run --no-sync ruff format --check dev/registry/conformance/manager.py dev/tests/test_registry_conformance_cli.py` â€” 2 files already formatted.
- `uv run --no-sync basedpyright dev/registry/conformance/manager.py` â€” 0 errors, 0 warnings, 0 notes.
- Whole test-file basedpyright remains bounded at 11 unrelated existing diagnostics; no new S03 diagnostics remain.
- `git diff --check` on the owned files â€” clean.
