---
tags:
  - '#plan'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-15'
body_hash: 'sha256:6cb60645f3fa06a79416eacc988f4c471c2707e62df3f01c980ed6b46bbf9e96'
tier: L2
related:
  - '[[2026-07-14-data-output-standardization-audit]]'
  - '[[2026-07-14-honest-all-green-adr]]'
  - '[[2026-07-13-data-output-standardization-research]]'
---
# `honest-all-green` plan

### Phase `P01` - Renta registry grounding cluster

Root-cause and fix the ~55 registry renta calc-data failures and their ~12 application/modelo cascade, grounded in AEAT/BOE authority, never by editing expectations to match the engine.

- [x] `P01.S01` - Diagnose the renta binding-resolution root cause including the profile-has-economic-activity unsupplied binding and classify each failing assertion as engine defect or expectation defect with authority evidence; `src/cadrumo/domain/calculations/registry`.
- [x] `P01.S02` - Fix the renta registry data or engine per the diagnosis with AEAT/BOE grounding and rerun the registry suite sequentially; `registry renta surfaces`.
- [x] `P01.S03` - Verify the application/modelo cascade failures clear downstream and fix any residual independent defects; `src/cadrumo/application/modelo/tests`.

### Phase `P02` - Core hygiene gates

Fix the exception-base-hygiene unregistered roots and the period-combined-string docs findings at root cause.

- [x] `P02.S04` - Register or rehome the FormerProduct exception classes so the exception-base-hygiene gate passes without allowlist mutes; `src/cadrumo/core/errors`.
- [x] `P02.S05` - Resolve the period-combined-string findings in docs at root cause per the gate grammar; `docs period tokens`.

### Phase `P03` - Storage diagnostics and aggregation

Fix the three master-key-rotation secure-object integrity diagnostics failures and the three aggregation source-resolver enrollment and precedence-ladder failures.

- [x] `P03.S06` - Fix the secure-object integrity diagnostics failures after master-key rotation; `src/cadrumo diagnostics integrity`.
- [x] `P03.S07` - Fix the aggregation source-resolver enrollment and precedence-ladder failures; `src/cadrumo/application/aggregation`.

### Phase `P04` - Structural inventory debt

Close the structural-inventory findings honestly: real coverage, real-behavior tests replacing mock and monkeypatch and skip debt, size-budget compliance, marker metadata, mirror-manifest, parser-boundary and extraction-sidecar findings.

- [x] `P04.S08` - Close the structural-inventory findings with real-behavior fixes per finding; `structural inventory surfaces`.

### Phase `P05` - Packaging and parallel robustness

Fix the companion-wheel build errors and make the loader-cache and import-hygiene tests robust under parallel execution without weakening what they prove.

- [x] `P05.S09` - Fix the companion-wheel uv build failures or prove them environment-only with evidence; `packaging`.
- [x] `P05.S10` - Make the loader-cache cross-session proof and the import-hygiene scan robust under parallel execution without weakening them; `parallel-sensitive tests`.
- [x] `P05.S12` - Root-cause the stale registry disk-cache pickles serving pre-correction snapshots under pytest and prove fingerprint invalidation completeness or fix the gap; `src/cadrumo/domain/calculations/registry/_loader.py`.

### Phase `P06` - All-green verification

Full-suite verification runs to a genuinely green state with zero skips and no new baselines or allowlist mutes.

- [x] `P06.S11` - Run the full suite to genuinely green in parallel and sequential modes and record the closing evidence; `full-tree gates`.
- [x] `P06.S13` - Extend the period-gate allowlist for the landed docs sequences WorkUnit display frames per the established narrow-rule precedent; `src/cadrumo/core/tests/test_period_combined_string_gate.py`.
- [x] `P06.S14` - Complete the landed CLI-identity rename's locale sweep so codebase-to-locale parity and the two locale-audit tests are green; `src/cadrumo/locales`.

## Description

## Steps

## Parallelization

## Verification
