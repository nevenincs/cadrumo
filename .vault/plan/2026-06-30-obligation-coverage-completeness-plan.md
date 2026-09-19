---
tags:
  - '#plan'
  - '#obligation-coverage-completeness'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:8ede649f26edff767b4d58661d90457fd03bb181ec5f3e600c4750d15fb626d3'
tier: L2
related:
  - '[[2026-06-30-obligation-coverage-completeness-adr]]'
  - '[[2026-06-30-obligation-coverage-completeness-research]]'
---

# `obligation-coverage-completeness` plan

### Phase `P01` - structural coverage closure

Reconcile the full registry modelo set against the surfaced obligations and surface a default advisory so no obligation is silently dropped.

- [x] `P01.S01` - Add the OUT_OF_SCOPE_OBLIGATIONS central declaration; `src/aeat/core/_modelo.py`.; `src/aeat/core/_modelo.py`.
- [x] `P01.S02` - Implement the build_obligation_coverage reconciliation; `src/aeat/application/overview/_coverage.py`.; `src/aeat/application/overview/_coverage.py`.
- [x] `P01.S03` - Attach the coverage report to the calendar, agenda, and backlog read models.; `src/aeat/application/overview/_calendar.py`.
- [x] `P01.S04` - Project the coverage advisory as a default-visible Notice on calendar, agenda, and backlog.; `src/aeat/entrypoints/cli/_overview.py`.
- [x] `P01.S05` - Add the coverage-completeness invariant test.; `src/aeat/application/overview/tests/test_obligation_coverage.py`.

### Phase `P02` - grounded promotions and locale

Upgrade advised obligations to surfaced by authoring windows and seed rules with legal grounding, and complete the locale catalogue entry.

- [x] `P02.S06` - Author the Modelo 190 annual deadline window with legal grounding verified against the bundled corpus.; `src/aeat/_data/registry/aeat/modelos/190`.
- [x] `P02.S07` - Disposition the class-C window-but-no-seed modelos as seed rules or advisories.; `src/aeat/domain/calculations/registry/_applicability.py`.
- [x] `P02.S08` - Scaffold the cli.overview.coverage.investigate locale key across the four catalogues once the peer duplicate key clears.; `src/aeat/locales`.

### Phase `P03` - external universe gate and enrollment ratchet

Bind the coverage invariant to the AEAT obligation universe so recognized-but-unmodeled obligations surface as advised, and harden the out-of-scope hatch.

- [x] `P03.S09` - Add UNMODELED_OBLIGATIONS and grow the Modelo enum with recognized-unmodeled obligations (117, 216, 296) carried in NON_REGISTRY_MODELOS.; `src/aeat/core/_modelo.py`.
- [x] `P03.S10` - Bind the reconciliation to the AEAT universe (registry union unmodeled) and advise unmodeled obligations with the REGISTRY_UNMODELED reason.; `src/aeat/application/overview/_coverage.py`.
- [x] `P03.S11` - Harden the out-of-scope hatch with a gate asserting it cannot silence an applicability-decidable modelo.; `src/aeat/application/overview/tests/test_obligation_coverage.py`.
- [x] `P03.S12` - Emit per-profile coverage advisories on the calendar --all-profiles surface.; `src/aeat/entrypoints/cli/_overview.py`.
- [x] `P03.S13` - Ratchet UNMODELED_OBLIGATIONS toward AEATs full form set and promote each to a grounded registry definition.; `src/aeat/_data/registry/aeat/modelos`.
- [x] `P03.S14` - Wire coverage onto overview status, explain, and the undeclared-profile path.; `src/aeat/entrypoints/cli/_overview.py`.
- [x] `P03.S15` - Wire coverage onto the undeclared-profile path so it reconciles the full universe instead of returning empty.; `src/aeat/application/overview/_calendar.py`.

## Description

Implements the accepted ADR. Phase P01 (landed) is the structural closure: a total
coverage reconciliation over the full registry modelo set, attached to the
calendar / agenda / backlog read models and surfaced by default as a typed
advisory Notice, plus the central out-of-scope declaration and the completeness
invariant test. Silent under-scoping becomes structurally impossible: every
obligation is surfaced, confidently excluded, advised, or explicitly out of scope.
Phase P02 (deferred) upgrades advised items to surfaced by authoring the Modelo 190
window and the class-C dispositions with the legal grounding the registry rules
require, and completes the locale catalogue entry once an unrelated peer duplicate
key clears. The advisory already prevents silent under-filing in the interim.

## Steps

## Parallelization

Within P01, S01 and S02 land first (the declaration and the reconciliation); S03
depends on S02, S04 depends on S03, and S05 depends on all of them. P02 steps are
independent of one another and of P01, but each requires legal grounding (S06, S07)
or an external unblock (S08, the peer duplicate-key clearance).

## Verification

- The coverage-completeness invariant test passes: the report partitions every
  `registry_modelo_codes()` code into disjoint buckets, Modelo 190 is advised
  (never silently absent), and the out-of-scope bucket equals the central
  declaration (`test_obligation_coverage.py`, 7 tests green).
- The default calendar / agenda / backlog surfaces emit the coverage advisory
  without `--show-suppressed` (verified via the rendering helper and the agenda /
  backlog CLI verb tests).
- The full application-overview suite stays green (220 tests); ruff and the
  docstring core-struct-links gate pass; full-tree collect-only is clean.
- P02 is complete when the Modelo 190 window and each class-C disposition are
  authored with corpus-verified legal grounding, and the locale key is scaffolded
  across the four catalogues so the advisory renders localized rather than from its
  English fallback.
