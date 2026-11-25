---
tags:
  - '#research'
  - '#gate-60-minutes'
date: '2026-11-25'
modified: '2026-11-25'
body_schema: 'body-v2'
body_hash: 'sha256:0801b59ff3774733771010fccdfc06eb81f686e7a2b4358e50bfbfe60a26f1a1'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #research) and one feature tag.
     Replace gate-60-minutes with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown [label](path) links in the document body.
     - Cite external sources as bare URLs. Cite code, commits, packages, and
       standards as inline backtick locators: `src/module.py:42`, commit
       `abc1234`, `package@1.2.3`, RFC 9110. -->

<!-- DOCUMENT BOUNDARY:
     Research grounds; the ADR decides. Frame the option space with evidence
     and trade-offs; at most name the option the evidence favors and what
     the ADR must settle. Never record the decision here - a decision
     outside the ADR forks and goes stale when the ADR chooses otherwise. -->

# `gate-60-minutes` research: `Where the full local gate spends its time`

The full local gate (`just gate-local`, `justfile:2136`) takes about 5 h on a quiet machine and 9 to 16 h under load; the operator's target is 60 minutes with no loss of real coverage. This record measures where the time goes and frames the options. The evidence favours a concurrent gate under one worker budget, single execution of work the gate currently repeats, shared read-only compiled inputs, and a small number of recorded coverage reductions; concurrency alone cannot reach the target.

## Findings

### The gate is a sequential queue of eleven steps with no record

`gate-local` runs `check-code`, `check-registry`, `fixtures-check`, `check-repository`, `check-dependency-vulnerabilities`, `docs-build`, `docs-check`, `test-product`, `test-registry`, `test-tooling` and `build-release` one after another (`justfile:2137-2147`), stops at the first red step and writes no per-step duration or verdict. Pytest lanes use six workers unless `CADRUMO_PYTEST_WORKERS` is set (`src/cadrumo/tests/worker_count_hook.py:67`, `justfile:1071`) on a machine with 12 cores and 24 logical processors. Per-shard records of the earlier 5 h, 9 h and 13 to 16 h gates were lost with a removed worktree.

### Baseline: step wall times on 2026-11-25

Measured in the root checkout from head `0809877053` (the tree moved to `6e3b155baa` during the run), as two concurrent streams with pytest at 12 workers, while another session ran focused tests. The machine was loaded, so every figure is an upper bound. Records: `.tmp/2026-11-25-gate60-baseline/steps-static.tsv`, `steps-tests.tsv`, per-step logs and JUnit reports.

- `check-code` 2,470 s (red), `check-registry` 300 s, `fixtures-check` 434 s, `check-repository` 448 s, dependency audit 7 s, `docs-build` 7,195 s, `docs-check` 3,628 s (its docs tests 1,597 s, then the second harness run 2,001 s, green), `build-release` 134 s. The static stream sums to 14,616 s (4 h 4 min).
- `test-pytest-harness` 2,190 s, `test-unit` 2,209 s, `test-integration-parallel` 2,258 s, `test-integration-serial` 179 s, `test-registry` 2,722 s, `test-test-policy` 313 s, `test-repository-contracts` 2,440 s, `test-ci-contracts-gate` 539 s, `test-ci-perf` 264 s. The pytest lanes sum to 13,114 s (3 h 39 min).

### Test work totals about 86,000 summed seconds and is not concentrated

JUnit times sum to 86,286 s over 86,995 tests in 6,822 modules (`.tmp/2026-11-25-gate60-baseline/analysis.txt`). The top 50 modules hold 35% of the time, the top 400 hold 73%. Even with perfect scheduling on this machine that is about an hour of wall time for tests alone, so the target needs work removed, not only rescheduled. Largest groups: `src/cadrumo/entrypoints/tests` 18,111 s, `src/cadrumo_runtime/host/tests` 6,902 s, `src/cadrumo/entrypoints/tui` 6,290 s, `dev/registry/pipeline/tests` 4,589 s, `src/cadrumo/adapters/persistence` 4,108 s, `src/cadrumo/application/modelo` 3,608 s, `dev/acceptance/iva/tests` 2,548 s, documentation tests about 6,000 s.

### Whole heavy files run on one worker

Lanes use `--dist=loadfile` (`pyproject.toml:1221`), so a file such as `src/cadrumo/entrypoints/tests/test_persona_obligations.py` (1,273 s) or `src/cadrumo/application/modelo/tests/test_work_form_answers.py` (1,283 s) occupies one worker for its whole length and sets the lane's tail regardless of worker count.

### The documentation work is repeated

- The CLI sequence corpus runs in full three times per gate: in the `docs-build` hook (`dev/docs/sequence_build_gate.py:172`), in `test-pytest-harness` inside `docs-check` (`justfile:2030`) and in `test-pytest-harness` inside `test-product` (`justfile:1258`). One harness run costs 2,190 s; its golden check alone is 1,714 s with a fixed pool of eight children (`dev/docs/sequences/checks.py:897-909`).
- Clean-result reuse exists per sequence (`dev/docs/sequences/verdict_cache.py`) but did not hit in the baseline, because locale files changed during execution; change detection uses size and modification time (`verdict_cache.py:180-207`). The page-coherence check never reuses (`checks.py:890`), 435 s per run.
- A gate compiles the documentation up to five times: the full `docs-build` whose output no gate step reads (`justfile:1926`), a strict all-language build plus a witness build for the docs tests (`dev/docs/tests/built_site.py:152-217`), a strict full-scope dummy build (`dev/docs/tests/test_docs_build_full_scope.py:63`, 1,101 s), and partial builds. Sphinx parallel reading is inactive on Windows (`dev/docs/build.py:404-408`).

### The compiled registry is rebuilt in every worker, and its clean-validation record does not survive

`_worker_compiled_authority` (`dev/registry/conftest.py:50`), `registry_authority` (`dev/registry/tests/conftest.py:32`) and module copies each call `compiled_bundled_authority` (`dev/registry/compiler/authority.py:527`). One compile measured 41 to 58 s in a fresh process; about 46 s of a profiled compile was validation. The clean-validation record (`validation_verdict_cache.py:198-224`) was written during a process and absent after it ended in six checks, so each process revalidated. What removes it was not identified. The accepted registry disk-cache decision permits sharing for the immutable bundled root only.

### Profile and persona tests spend their time in calculation and rendering, not in profile setup

Persona worlds are already built once per run through production operations, sealed and copied per test (`src/cadrumo/adapters/persistence/profile/tests/sealed_profile_world.py:181`, `:313`); the fixtures use a fixed synthetic custody envelope and a session-scoped authority lease. In `test_calculation_rendering_snapshot_store.py` the per-year round trips took 52 to 87 s each; sampled time was dominated by `CalculationRenderingSnapshot.capture`, and by reload validation (`modelos_calculation.py:643-647`, `:720`). A closer reading found no duplicate serialisation: the registry digest (`src/cadrumo/domain/modelos/calculation_revision_rendering.py:738`) and the rendering digest (`:750`) hash different serialisations by contract, each computed once per snapshot object, and the reload work is the storage trust-boundary validation. Several persona files replay a persona per test without the existing reuse option (`test_persona_prorrata_settlement.py:259`, `test_persona_materialisation.py:106`). The sealed-world key carries no digest of the producing sources, so a world built by older code can be served.

### Candidate coverage reductions, each needing a decision

- `dev/acceptance/iva/tests/test_annual_cli_journey.py:196` runs the export-before-filing journey through an installed wheel for every supported year (874 s for that test); `test_persona_prorrata_settlement.py:241` asserts the same behaviour per horizon in process.
- `src/cadrumo/entrypoints/tui/tests/test_workbench_acceptance.py:134-165` crosses theme with every case while asserting rendered text only.
- `test_m100_rental_pending_attestation.py:94` and `test_m100_trabajo_income_statement.py:285` repeat nine behaviours per supported year.
- `test_calculation_rendering_snapshot_store.py:417` runs every envelope year; years resolving to the same modelo, revision and grade repeat one contract.
- `test_sequence_goldens.py:747` reruns a real page clean, which the golden check already asserts.

### Tests that fail only under load

Five tests failed in the baseline and passed alone (for example `src/cadrumo_runtime/host/tests/test_warm_heap.py`, `dev/tui/harness/tests/test_sequence_scenarios.py`). A wider gate must keep total concurrency within what the machine carries, or these become false reds. One further red came from the machine's untracked `env/.env` reaching `Settings()` defaults and was fixed in commit `0fe60217fc`.

### Constraints from accepted decisions

Default worker count is six and changing the default needs an amendment; an explicit count on a recipe is allowed. Lanes are selected by path or recipe, never by a runtime-cost marker. Parallel and serial verdicts stay separate. No scheduled tier. No repository-imposed elapsed-time cutoff on correctness tests. Staleness keys are content digests, never git. A reused verdict keeps its positive control. These are recorded in the test-harness-sanity, test-topology, CI lane deconflation, CI discipline, CI speed redesign, harness honesty, git-free tooling, registry disk cache and fixture canonicalization decisions.

### Not investigated

Setup versus call split for `dev/registry/pipeline/tests`; the runtime-host subprocess files; quiet-machine times for every step; per-phase split inside `docs-build`.

## Sources

- `justfile:1071`, `justfile:1093`, `justfile:1258`, `justfile:1926`, `justfile:2030`, `justfile:2136-2147`
- `pyproject.toml:1221`, `src/cadrumo/tests/worker_count_hook.py:67`
- `dev/docs/sequence_build_gate.py:172`, `dev/docs/sequences/checks.py:890`, `dev/docs/sequences/checks.py:897-909`, `dev/docs/sequences/verdict_cache.py:180-207`, `dev/docs/tests/built_site.py:152-217`, `dev/docs/tests/test_docs_build_full_scope.py:63`, `dev/docs/build.py:404-408`
- `dev/registry/conftest.py:50`, `dev/registry/tests/conftest.py:32`, `dev/registry/compiler/authority.py:527`
- `src/cadrumo/adapters/persistence/profile/tests/sealed_profile_world.py:181`, `src/cadrumo/adapters/persistence/profile/tests/test_calculation_rendering_snapshot_store.py:417`
- `dev/acceptance/iva/tests/test_annual_cli_journey.py:196`, `src/cadrumo/entrypoints/tui/tests/test_workbench_acceptance.py:134-165`
- Baseline records under `.tmp/2026-11-25-gate60-baseline/` and the evidence folder `.tmp/2026-11-25-evidence/` (scratch; figures are restated above).
