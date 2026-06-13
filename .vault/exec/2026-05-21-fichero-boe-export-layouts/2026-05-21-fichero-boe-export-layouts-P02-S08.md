---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S08'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P02.S08`

Ran the Modelo 130 registry snapshot load and the golden round-trip test
suite, confirming the corrected 946-byte record serialises byte-accurately
and all 26 modelos remain valid.

## Test results

### Golden round-trip test suite (10 tests)

```
src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py
10 passed in 25.45s
```

Includes the new `test_modelo_130_golden_sha_fichero_boe`:
- Total byte count: 946 (DR-grounded: 328+600+18)
- Golden SHA confirmed: `feaffb81b89ce8b897066ac0383d31e4bfd45a15c526b650f711a89f25fe0120`
- All per-offset structural assertions pass

### Application-layer export tests (40 tests)

```
src/aeat/application/filing/test_export.py
40 passed in ~45s
```

The existing `test_export_writes_modelo_130_registry_layout` and
`test_verify_matches_exported_modelo_130_layout` tests continue to pass
with the corrected layout.

### Registry committed snapshot (41 tests, all 26 modelos)

```
src/aeat/domain/calculations/registry/test_committed_registry.py
41 passed in 19.83s
```

All 26 modelos load valid with the corrected 130.toml.

### Modelo parity coverage (1 test)

```
src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py
1 passed in 15.23s
```

### Combined verification run (92 tests)

```
92 passed in 60.77s
```

## M130 byte-accuracy confirmation

The 946-byte fichero-BOE for a standard non-complementaria Modelo 130 with:
- NIF `12345678Z`, period `2026Q1`
- Casilla 01: 10000.00, casilla 02: 4000.00
- Casilla 03 (computed): 6000.00
- Casilla 04 (computed): 1200.00
- Casilla 19 (computed): 1200.00

Produces byte-accurate output at every DR 13001 offset. The offset-432
declaracion_complementaria field serialises to a blank (space) for an
ordinary declaration, confirming the field is present and correctly encoded.

Commit: `ae3b45ccc`
