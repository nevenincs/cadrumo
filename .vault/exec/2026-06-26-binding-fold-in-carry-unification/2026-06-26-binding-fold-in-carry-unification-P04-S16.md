---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S16'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-fold-in-carry-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S16 and 2026-06-26-binding-fold-in-carry-unification-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The vaultspec-standard-executor: delete the MultiYearResolver class and its request/report models, cleanly separating it from the live EnrollmentRecorder in the shared module, atomic relocation:MultiYearResolver-removal with __all__ baseline and ## Scope

- `src/aeat/application/calculations/_multi_year.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# vaultspec-standard-executor: delete the MultiYearResolver class and its request/report models, cleanly separating it from the live EnrollmentRecorder in the shared module, atomic relocation:MultiYearResolver-removal with __all__ baseline

## Scope

- `src/aeat/application/calculations/_multi_year.py`

## Description

- Delete the confirmed-orphan `MultiYearResolver` class plus its request/report models and the dead functional wrapper, separating them cleanly from the live `EnrollmentRecorder` and `PreviousFilingSourceResolver` that share the module file.
- Remove the contiguous block (the two scan models and the resolver, stopping before the live `PreviousFilingSourceResolver`), the dangling `resolve_prior_year_observations` wrapper, the now-orphaned `_revision_prefill_divergence` and `Iterable` imports, and the four deleted names from `__all__`.
- Remove the package re-exports (imports plus `__all__` entries) in `application/calculations/__init__.py`.
- Remove the two redundant R2 carry-gate tests of `MultiYearResolver.resolve` from `test_revision_stamp_roundtrip.py`; the live-path R2 coverage stays in `test_carry_gate_parity.py`.

## Outcome

- Landed in the P04 commit (`relocation:remove-MultiYearResolver-orphan`). The live `EnrollmentRecorder`, `EnrollmentEvidence`/`EnrollmentYearObservation`/`EnrollmentEvidenceError`, `assert_enrollment_matches_manifest`, and `PreviousFilingSourceResolver` remain intact and importable. collect-only clean.

## Notes — preserved deferral intent (captured verbatim before deletion)

`MultiYearResolver` carried a design-only deferral note for a future multi-year scan capability with ZERO production callers; per `aeat-source-hygiene`, `no-dormant-source-resolvers`, and `no-legacy-compatibility` it is deleted now and is to be re-introduced LIVE, with its caller and tests, when the work below lands. The intent is captured here so it survives the deletion (intent in this record plus code in git history).

- Staged scope (the modelos the resolver was intended for):
  - Modelo 200 IS — BIN (base imponible negativa) unlimited carryforward (LIS arts. 25-26), and Modelo 202 pago-fraccionado roll-up across prior years.
  - Modelo 303 IVA — prorrata four-year average (LIVA art. 105), and regularización de inversiones five-year straight-line (LIVA art. 93).
- The capability being staged: `MultiYearResolutionReport` exposed the derived year-sets `requested_years` / `found_years` / `missing_years`, letting a caller decide whether to refuse, prompt the operator, or zero-fill absent prior years without re-scanning the store. `PreviousFilingSourceResolver` (the live previous_filing source-mesh resolver) does NOT expose these year-sets; that explicit-coverage report is the capability deferred for later.
- Why not wired: the modelos above were in DORMANT aggregation state per the calculation-engine-foundations audit F6 matrix (no enrolled source resolver for their multi-year inputs).
- Re-author pointer: re-introduce `MultiYearResolver` LIVE — with its caller and tests — when the M200 BIN / M202 roll-up and M303 prorrata / regularización-inversiones multi-year inputs are enrolled, per the calculation-engine-foundations plan W02.P06 / W03.P08 (audit F6).
- R2 redundancy: the R2 carry gate (`_revision_prefill_divergence`) lives in the live binding-prefill path and is comprehensively exercised by `test_carry_gate_parity.py` (the carry sites across the matching / divergent / missing / indeterminate outcomes); the two `MultiYearResolver` R2 tests removed here were secondary coverage of that same gate, so R2 coverage is preserved by the live-path tests.
