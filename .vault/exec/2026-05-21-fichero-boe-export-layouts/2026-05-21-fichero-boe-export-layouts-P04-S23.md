---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S23'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P04.S23`

Confirmed both Modelo 130 and Modelo 303 produce byte-accurate
fichero-BOE output via the application-layer export service that
backs the `aeat app modelo export` CLI verb.

## M303

- Inputs: NIF `12345678Z`, period `2025Q1`, casilla 07 = 10000.00,
  casilla 09 = 2100.00
- Output: **7994 bytes**, SHA-256 =
  `17d837599f73c2be99ff71f443c064164ca3099e7767de1147add8343f6f7ac9`
- Matches the P03.S20 golden-SHA fixture exactly.

## M130

- Inputs: NIF `12345678Z`, period `2026Q1`, casilla 01 = 10000.00,
  casilla 02 = 4000.00, previous-year net income = 13000.00
- Output: **946 bytes**, SHA-256 =
  `feaffb81b89ce8b897066ac0383d31e4bfd45a15c526b650f711a89f25fe0120`
- Matches the pre-existing P02 golden-SHA fixture exactly.

## Test fixes

Two tests in `src/aeat/application/filing/test_export.py` that
expected M303 to have no export layout were updated to use
`_provider_without_export_layout` to strip the layout explicitly.
This restores the "missing layout" code path coverage without
depending on a modelo that happens to lack a layout.

```
40 passed in 59.09s
```

## CLI

The `aeat app modelo export` verb is a thin delegate over
`export_draft`; no new CLI-layer verification was needed — the
service-layer invocation above exercises the identical code path.
The `NoDeadlineWindowsError` collection failure in
`test_modelo_export_verb.py` is a pre-existing regression from
commit `845d40233` (deadline/period robustness work by another agent)
and is unrelated to this feature.
