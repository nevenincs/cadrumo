---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:94e38f9dbc607b6261fa3280836d9f577120b1f87efd6d8bdae8a93a6ba3b22a'
step_id: 'S20'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---

# `aeat-design-relayout-boundary` execution record: `W02.P04.S20`

Confine the transitional rate rungs pinned to 2024 to the two 2024-covering revisions only.

## Measured first

All five split revisions' designs were read through the real parser (`extract_record_design`), not the extracted derivatives: the 2023 and 2024-early designs declare only box [154] (`Constante "00500"`); the 2024-late design declares [154] (Nota 8) and [166] (`Constante "00200"`); the 2025 and 2026 designs declare both as `Constante "00000"`. The 2023 revision's 166 chain (rate box, formula, parameter rung, super-reducido transitorio carrier and binding pair, 167 projection) therefore had no design field or law behind it for any 2023 filing period, and the 2025/2026 revisions carried dated 2024 windows their own designs supersede with mandated zeros.

## Executed

- 2023: the parameter file now carries the 2023 design's own single 5 % rung on [154], grounded on `n:art-72` (RD-ley 20/2022 art. 72); the 166 rate box, its formula and parameter rung, the super-reducido transitorio carrier, its base/cuota binding pair, the 167 projection formula, the construct formula entries, the completeness-manifest rows and the verification-expectations list entry are all removed; boxes 165/167 return to their pre-transitional manual shape.
- 2025 and 2026-y-siguientes: the parameter files now carry their own designs' mandated `Constante "00000"` on [154]/[166] as per-design single-rung parameters; the dated 2024 windows are gone.
- The two 2024-covering revisions are untouched, and no 303 export map referenced the removed casillas, so no export tree regeneration was needed.

## Verification

- `load_modelo_directory` on the swept modelo 303 loads clean with all six revisions (referential integrity across casilla/formula/parameter/binding/construct/manifest holds).
- An isolated-registry authority load validates all five revised revisions clean; the only remaining refusal is the known 2009-2022 export-layout gap owned by S22/S23.
- Core generated-tree, coverage and parse gates: 68/68 green after the peer's test-relocation landed.
- The sweep script (idempotent, exact-string with counts) lives at `tmp/s20_m303_rungs.py`.
