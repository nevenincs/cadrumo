---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:bde3d72e492d8ee01f291c73c7bac8e7a7f0f71f37a737bd1c2c66d04781cfc0'
step_id: 'S288'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Retire the M100 casilla-accessor hand-copy onto the public numeric_casilla_value it duplicates, in a module already importing both that ops module and the error class the copy raises

## Scope

- `src/cadrumo/domain/calculations/registry/_formula_runtime.py`

## Description

- Confirmed the private `_m100_numeric_casilla_value` body in `_formula_runtime.py` was byte-for-byte identical to the public `numeric_casilla_value` in `_formula_runtime_ops.py`, differing only in the error-class binding (`_UnresolvedFormulaDependencyError` alias of the same class) and a missing docstring.
- Renamed the existing single import binding of the public accessor from the misleading `_m210_numeric_casilla_value` to the neutral `_numeric_casilla_value`, since one import of one canonical function now serves every family.
- Deleted the duplicate `_m100_numeric_casilla_value` definition outright, no shim or re-export left behind.
- Routed every caller through the public accessor: the four M100 Art.85 imputed-real-estate reads, the M100 boolean-casilla helper, the M131 módulos text-fallback wrapper, and the two M210 IRNR reads.

## Outcome

Duplicate retired; the public `numeric_casilla_value` (`_formula_runtime_ops.py`) is now the sole casilla-value accessor in the runtime, consumed under the neutral `_numeric_casilla_value` binding by the M100, M131 and M210 families.

Discovery basis: the mandated `vaultspec-rag` code index was measured untrustworthy (mid-rebuild, control probes missed), so a structural AST duplicate scan (function bodies hashed after identifier/string blanking) supplied the cluster, and every claim was re-established by exact `rg` search and by reading both bodies.

Verification (HEAD `1437055950f5b8f4082d323578294fc32ad1d9fe`):

- `uv run --no-sync ruff check` and `ruff format --check` on `_formula_runtime.py` — `All checks passed! 1 file already formatted`.
- `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_modelo_100_imputed_real_estate_art85.py -n0 -q` — 5 collected, `5 passed in 8.90s`.
- Full rerouted-caller sweep `... test_modelo_100_imputed_real_estate_art85.py test_formula_runtime_m210.py test_modelo_131_modulos_engine.py test_formula_runtime.py -n0 -q` — 51 collected, `51 passed`.
- Mutation proof: perturbing the surviving canonical `numeric_casilla_value` return (`+ Decimal("777")`) reddened the Art85 module to `4 failed, 1 passed`, confirming the tests genuinely exercise the canonical path the M100 callers now use; restored to `5 passed`.

## Notes

The rename of the shared alias from `_m210_numeric_casilla_value` to `_numeric_casilla_value` also touches the M131/M210 call sites; this is a pure internal binding rename to the same public function, covered by the 51-test sweep above. No behaviour change.
