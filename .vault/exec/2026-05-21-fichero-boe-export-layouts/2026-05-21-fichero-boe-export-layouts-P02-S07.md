---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S07'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P02.S07`

Authored the Modelo 130 golden-SHA fichero-BOE byte-identity round-trip test
in `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`.

## Test: `test_modelo_130_golden_sha_fichero_boe`

### Location

`src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`

### How the golden SHA is AEAT-grounded

The expected bytes are derived from the AEAT Diseño de Registros DR 13001
(Orden HAP/258/2015, version 1.2, March 2019, ejercicios 2019 y siguientes).
The test is non-tautological because:

1. The total byte count (946) is derived from the DR layout:
   328 bytes (DR 13000 envelope header) + 600 bytes (DR 13001 page-01 record)
   + 18 bytes (envelope closing tag) = 946 total. Any registry change that
   alters a record length or inserts/removes a field fails this assertion
   before reaching the SHA check.

2. Per-offset byte assertions name the DR row they verify:
   - DR 13001 row 1-4: open tag, modelo literal, page number, close
   - DR 13001 row 5: complementaria indicator (offset 12, blank for ordinary)
   - DR 13001 row 6: declaration type (offset 13, must be "I")
   - DR 13001 row 7: NIF (offset 14, 9 bytes)
   - DR 13001 rows 8-9: surnames/name (offsets 23/83)
   - DR 13001 rows 10-11: year/period (offsets 103/107)
   - DR 13001 rows 12-30: all 19 casilla fields (offsets 109-431)
     - casilla 01 (10000.00 -> 1000000 cents -> 17-byte zero-padded)
     - casilla 02 (4000.00 -> 400000 cents)
     - casilla 03 signed (6000.00 = 01-02, " " + 16-digit zfill)
     - casilla 04 unsigned (1200.00 = 20% x 6000.00)
     - casilla 19 signed (1200.00, full calculation chain verified in comment)
   - DR 13001 row 31: declaracion_complementaria (offset 432, blank)
   - DR 13001 row 32: previous_receipt (offset 433, blank)
   - DR 13001 row 36: page close tag (offset 589, `</T13001000>`)
   - Envelope footer: `</T130020261T0000>` (18 bytes)

3. The SHA `feaffb81b89ce8b897066ac0383d31e4bfd45a15c526b650f711a89f25fe0120`
   was recorded after all structural assertions passed. It locks byte identity
   so any change to encoding, field order, padding, or sign convention that
   passes the structural checks but still corrupts bytes is caught.

4. Money amounts are independently derived using the `_money_bytes` helper
   which implements the DR encoding rule directly (N + 16-digit zfill for
   negative, space + 16-digit zfill for positive signed, 17-digit zfill for
   unsigned). A regression in `_format_money` that changes byte output
   fails the per-field assertion independently of the SHA.

The test uses the real `export_draft` application function backed by the
real registry snapshot — no mocks, no fakes, no inline-built specs. It
exercises the full path: registry load -> layout resolution -> field rendering
-> encoding -> byte output.

Commit: `ae3b45ccc`
