---
tags:
  - '#exec'
  - '#determinism-replay-residual'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S01'
related:
  - "[[2026-07-01-determinism-replay-residual-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace determinism-replay-residual with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-07-01-determinism-replay-residual-plan placeholders are machine-filled by
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
     The Add AST clock-seam conformance gate under core/tests failing on bare datetime.now/utcnow in production (named allowlist for injectable live-AEAT auth/certificate/authenticator/site-health sites) and ## Scope

- `route corpus_manifest generated_at through core.time.now().`
- `src/aeat/core/tests/test_clock_seam_usage.py`
- `src/aeat/core/corpus_manifest/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add AST clock-seam conformance gate under core/tests failing on bare datetime.now/utcnow in production (named allowlist for injectable live-AEAT auth/certificate/authenticator/site-health sites)

## Scope

- `route corpus_manifest generated_at through core.time.now().`
- `src/aeat/core/tests/test_clock_seam_usage.py`
- `src/aeat/core/corpus_manifest/__init__.py`

## Description

- Add `src/aeat/core/tests/test_clock_seam_usage.py`: a stdlib-`ast` conformance gate that walks every production module under `src/aeat` (tests excluded) and fails on a bare `datetime.now(...)` / `datetime.utcnow(...)` call, directing the author to `aeat.core.time.now()` so the frozen-clock seam can pin it.
- Resolve datetime bindings per module from its own imports (`from datetime import datetime [as X]` for the class name, `import datetime [as Y]` for the module name) so an aliased binding such as `_dt.now(...)` is caught and an unrelated `.now()` on a non-datetime object is not.
- Skip the seam implementation itself (`core/time/_clock.py`), the one production site that legitimately returns real wall-clock when unfrozen.
- Carry a named, per-entry-reasoned allowlist for the four injectable live-AEAT sites that accept an explicit `now=` and read wall-clock only on the live path (barred from the seam under `AEAT_LIVE_TESTS_ENABLED`): the auth acquisition lock, the certificate evaluators, the authenticator freshness check, and the browser site-health parser. The gate fails on a stale allowlist entry, so the carve-out cannot rot into a mute button.
- Route `core/corpus_manifest/__init__.py` `generated_at` through `aeat.core.time.now()` (replacing the local `datetime.now(UTC)` bypass) so the manifest timestamp is pinned under `frozen_clock`; update its docstring accordingly.

## Outcome

- The new gate passes: the allowlist exactly covers the offender set (no offenders outside it, no stale entries), confirming the four injectable live-AEAT sites plus the seam skip-file are the complete carve-out.
- `build_corpus_manifest` now returns the frozen instant under `frozen_clock`, verified by a direct probe; the nine existing `corpus_manifest` tests still pass.
- `pytest --collect-only -q src/aeat/core` collects clean (986 tests); `ruff check` and `ruff format --check` pass on both touched files.

## Notes

- Decision-1 (surrogate-id lever) and Decision-3 (output-ordering) are separate Steps; this Step lands only Decision-2 (the seam-coverage gate) and its one shipping bypass, per the ADR's additive-slice structure.
- The gate's visitor is structured so it can later grow output-feeding uuid/random and unsorted-filesystem arms into one ambient-input conformance surface, as the ADR anticipates.
