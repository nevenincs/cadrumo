---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:aae2053e02cd0ba7bf96176438ce2336fce2beb416176d3244a89198b8039307'
step_id: 'S113'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---
# Land the detector gates in the existing per-push development-test lane

## Scope

- `dev/quality/tests/`
- retirement of the old `dev/tests/test_tautological_assertion_gate.py`

## Changes

- Retired the old off-lane tautological-assertion gate after its strengthened replacement landed under `dev/quality/tests/`.
- Kept every detector gate marked `unit`, matching the existing `test-dev-ci` marker expression.
- Added no lane and changed neither `justfile` nor `.github/workflows/`.

## Current per-push selection proof

- `just --dry-run test-dev-ci` includes `dev/quality/tests` in its non-serial `unit or (integration and not serial)` invocation and in its serial integration invocation.
- `.github/workflows/ci.yml` invokes `just test-dev-ci` on push.
- Explicit collection of the six detector gates selected 227 tests.
- Executing the same six files with `-n 0` passed all 227 tests in 142.19 seconds.
- The twelve detector/gate SHA-256 identities after the run were: tautology `99298B59800FC3C40541485E55FEC32867B0BF79B45C18FF9CF92D29CD7E495D` / `2027C7E472554BB6AB80541CD3C77A7ECD5FFA45D20B9C973DABD6431DD55485`; subsumption `5D74756B3E02C282C0E4E71787F0834202B3E120BE418B7D386194718FB605E8` / `CA675F02EA16B9A9917BFD3FD3A79536102EEF179C77E008C15510CC90A11B31`; self echo `C5A9E2537CAE6B082BC188A3A44BF8B368AEBA53F4A2A15FB18CE400E66F690D` / `00CFFF41AFCD7AABEBEE71DA3B70E58D7EA80BD76CC1EF90A31603EB7FDD9AFC`; locale `DA8B2997123DFFF5A7304845A080C2C0E932DC751FFDD5FBF17BC780C83CCB48` / `AF781657C40F76763CD12AAE5FFBBABED91247ACBC00206D6CB1E0F4072AF548`; taxonomy `2BE9BBA9A9255A3BD12E2CBD9D75CA513C7AAB201DB1D7D7468A96E47155CDEF` / `4CDF7BDC6155811890A54EA46E07CA6120919971B4F6B006C64E2B5D736E93B9`; verdict grammar `3F567EA4740B7D648F3FD0931B0048BF9FACE275BBEECA568EC6CD5553A37031` / `FC96F3451C04876E0504AED722FA4E09FA53845D288BEC87EC294F3891D7FAFF`.
- Ruff lint, Ruff formatting, and `ty` pass over all twelve files. Basedpyright passes the new verdict detector/gate pair with no diagnostics.

The first post-change aggregate attempt encountered a concurrent deletion of an unrelated test file between enumeration and read and is not counted as a pass. A fresh complete invocation produced the terminal 227/227 result above.
