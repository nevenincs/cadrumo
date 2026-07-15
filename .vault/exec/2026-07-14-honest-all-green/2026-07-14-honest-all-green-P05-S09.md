---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S09'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

# Fix the companion-wheel uv build failures or prove them environment-only with evidence

## Scope

- `packaging`

## Description

- Re-run the packaging cluster at HEAD from a fresh full-suite inventory
  (95 failed / 12796 passed, log preserved under the campaign scratch dir).
- Diagnose `test_wheel_archive_contains_every_tracked_data_file`: the slim
  wheel legitimately excludes two newly tracked corpus source binaries (a
  Modelo 349 orden `.docx` and the Modelo 289 XSD/WSDL `.zip`) because the
  build config excludes `_data/corpus/**/*.{pdf,docx,xls,xlsx,zip}` while
  the test's suffix tuple still listed only pdf/xls/xlsx.
- Verify the contract is coherent before touching the test: the
  `cadrumo_data_official` companion builder's suffix set includes `.docx`
  and `.zip`, so the two files ship in the companion distribution — the
  test expectation was stale, not the wheel.
- Align `_CORPUS_BINARY_SUFFIXES` and the module docstrings with the real
  five-suffix contract, citing the two authorities it mirrors.

## Outcome

`test_wheel_bundles_corpus_and_registry.py` 5/5 green sequentially (real
`uv build --wheel` driven twice); ruff clean. Commit `1d75f3edb8`
(explicit pathspec; the shared index concurrently held peer-staged work
that was correctly left out).

## Notes

The S29-era companion-seam `uv build` exit-2 ERRORs did not reproduce in
the fresh full-suite inventory at HEAD — the packaging cluster's live
member was this wheel-parity failure only. If the seam errors recur they
are environment-shaped (subprocess build of the companion trees) and
should be re-diagnosed on the machine where they fire. The exclusion-side
change that made the test stale landed in peer commit `27a77bebe8`
(2026-07-12) without a test sweep; the fix here completes that contract.
