---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S21'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P04.S21`

Confirmed both Modelo 130 and Modelo 303 golden-SHA byte-identity
round-trip fixtures pass cleanly.

## Test results

`src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`

```
11 passed in 27.25s
```

- `test_modelo_130_golden_sha_fichero_boe` — M130 946 bytes,
  SHA `feaffb81b89ce8b897066ac0383d31e4bfd45a15c526b650f711a89f25fe0120`
- `test_modelo_303_golden_sha_fichero_boe` — M303 7994 bytes,
  SHA `17d837599f73c2be99ff71f443c064164ca3099e7767de1147add8343f6f7ac9`

Both golden SHAs match their DR-derived expected values.
