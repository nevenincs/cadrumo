---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S20'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P03.S20`

Added a golden-SHA fichero-BOE fixture for Modelo 303 and a serialise-then-
deserialise byte-identity round-trip test for the full eight-segment envelope.

## Test

`test_modelo_303_golden_sha_fichero_boe` in
`src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`

## Inputs

- NIF: `12345678Z`, period: `2025Q1`
- Casilla 07 (base 21%): 10000.00
- Casilla 09 (cuota 21%): 2100.00

## Golden SHA

`17d837599f73c2be99ff71f443c064164ca3099e7767de1147add8343f6f7ac9`

Total: **7994 bytes** (DR-confirmed: 328+1581+1706+1017+998+1523+823+18)

## Per-offset non-tautological assertions

Each assertion names its DR sheet/row:
- DR DP30300 rows 1-7, 13: envelope tag structure (`<T` / `303` / `0` / year / period / `0000>` / `<AUX>` / `</AUX>`)
- DR DP30301 rows 1-4: page-01 tag (`<T303 01000>`)
- DR DP30301 row 7: NIF (`12345678Z`)
- DR DP30301 rows 9-10: ejercicio/periodo (`2025` / `1T`)
- DR DP30301 row 37: casilla 07 base 21% (10000.00 → unsigned 17-byte)
- DR DP30301 row 38: tipo 08 constant (`02100` = 21.00%)
- DR DP30301 row 39: casilla 09 cuota 21% (2100.00 → unsigned 17-byte)
- DR DP30301 row 88: page-01 close tag (`</T30301000>`)
- DR DP303DID rows 1-4: DID tag structure including `DID00` as An-type literal
- DR DP303DID row 13: DID close tag (`</T303DID00>`)
- Envelope footer: `</T303020251T0000>`

## Test results

```
11 passed in 26.19s (10 pre-existing + 1 new M303 golden test)
```

Commit: `f2bdda84b`
