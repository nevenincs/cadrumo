---
tags:
  - '#exec'
  - '#m100-per-ano-test-parity'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - "[[2026-04-29-m100-per-ano-test-parity-plan]]"
---

# `m100-per-ano-test-parity` execution summary

Created 14 new test files: B2, C, D, E, F, G, and N for 2024 and 2026. The established 2025 E/F module remains combined, but the new missing-year files follow the production E/F module split.

## Per-anexo counts

- B2: 8 tests across 2024 and 2026.
- C: 14 tests across 2024 and 2026.
- D: 22 tests across 2024 and 2026.
- E: 6 tests across 2024 and 2026.
- F: 16 tests across 2024 and 2026.
- G: 42 tests across 2024 and 2026.
- N: 18 tests across 2024 and 2026.

## Source provenance

- B2: LIRPF arts. 25-26 and retention context from art. 101.4 / RIRPF art. 90.
- C: LIRPF arts. 22-24 and 85, including post-Ley 12/2023 art. 23.2 tiers as caller-supplied reduction amounts.
- D: LIRPF arts. 27-32, LIS arts. 12 and 17, and RIRPF arts. 28, 30, and 32.
- E: LIRPF arts. 33-39.
- F: LIRPF arts. 47-61 and 84.
- G: LIRPF arts. 63, 66, 67, 68.4, and 79; Ley 7/2024 for the 2025+ ahorro top-bracket delta.
- N: LIRPF art. 46 bis plus AEAT manual/autonomic deduction aggregate provenance.

## Verification

- `uv run --no-sync pytest` over the 14 new files: 126 passed.
- No `skip`, `xfail`, mock, fake, stub, patch, freezegun, or pytest-mock usage found in the new files.
- Computed-casilla coverage audit for 2024 and 2026 reported no missing non-B1 computed casillas.
