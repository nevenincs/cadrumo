---
tags:
  - '#adr'
  - '#gate-60-minutes'
date: '2026-11-25'
modified: '2026-11-25'
body_schema: 'body-v2'
body_hash: 'sha256:49398cef4285d4265738b9530fc372c19d097122fbffd9fea30c7d30dabb6229'
related:
  - "[[2026-11-25-gate-60-minutes-research]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace gate-60-minutes with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, superseded, or deprecated. A new ADR starts as proposed; it
     moves to accepted or rejected when the decision is made; it becomes
     superseded when a later ADR replaces it (set by vault adr supersede,
     which also records superseded_by); and deprecated when it is retired
     without a direct successor.

     Reuse, amendment, and supersession follow the vaultspec system section.
     Preserve accepted content while a revision is pending; apply only an
     authorized amendment. Accept a reversal's successor before superseding
     its predecessor. Unchanged coverage needs no new record.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

# `gate-60-minutes` adr: `Full local gate: concurrent composition, single execution, shared inputs and recorded tiers` | (**status:** `accepted`)

Accepted 2026-11-25 on the operator's order of that date, which assigns this work to the gate lead with authority to decide gate composition, test selection and coverage reductions, each recorded with its evidence (`.tmp/2026-11-25-evidence/BRIEF-GATE-60.md`).

## Problem Statement

The full local gate is the only completion proof for a `feature/tui` head, and it takes 5 h quiet and 9 to 16 h under load. The operator requires the complete gate, static checks included, in 60 minutes or less on this machine with no loss of real coverage. The research record `2026-11-25-gate-60-minutes-research` shows the time is lost to a sequential queue, to work the gate executes two to five times, to compiled inputs rebuilt in every worker, and to a few matrices that repeat one contract.

## Considerations

- Test work is about 86,000 summed seconds under load and is spread over thousands of modules; scheduling alone cannot reach the target.
- The gate repeats the sequence corpus three times, compiles the documentation up to five times and compiles the registry once per worker per invocation.
- Whole files are pinned to one worker, so files above 1,000 s set the tail.
- Five tests failed only under load; a wider gate must not oversubscribe the machine.
- Other sessions edit the root checkout; the import gate and the sequence check refuse a tree that changes under them.
- Accepted decisions bind the design: default worker count six (`2026-08-14-test-harness-sanity-successor-adr`), lanes by path or recipe and no runtime-cost marker (`2026-06-05-test-topology-refactor-adr`), separate parallel and serial verdicts (`2026-08-05-ci-lane-deconflation-adr`), no scheduled tier (`2026-07-21-ci-discipline-adr`), no elapsed-time cutoff on correctness tests (`2026-07-20-ci-speed-redesign-adr`), content-digest keys and no git (`2026-10-07-git-free-tooling-adr`), positive controls on scanning gates (`2026-07-25-test-harness-honesty-adr`), immutable-root-only registry sharing (`2026-07-07-registry-disk-cache-pytest-adr`), production-built personas (`2026-11-04-fixture-canonicalization-canonical-test-personas-adr`).

## Considered options

- **Keep the sequential gate and raise the worker count.** Rejected: the baseline at 12 workers still took 3 h 39 min for the test lanes, and heavy files and repeated work are untouched.
- **Change-scoped gate as the completion proof.** Rejected: the operator asked for the complete gate; the change-scoped merge gate remains a separate, weaker signal.
- **Move slow populations to a scheduled or marker-selected tier.** Rejected: both are forbidden by accepted decisions, and it would be a loss of gate coverage.
- **Concurrent gate with single execution, shared read-only inputs, verdict reuse and narrowly recorded representative coverage.** Chosen.

## Constraints

- The gate keeps every population `gate-local` runs today. Nothing leaves the gate in this decision. A later move of a population out of the gate needs an amendment, is made by recipe membership, and must name the recipe that still runs it.
- The repository default of six workers is unchanged. The gate runner passes explicit worker counts under one global budget. Other sessions limit themselves with `CADRUMO_PYTEST_WORKERS`.
- Parallel and serial pytest passes are separate nodes with separate verdicts.
- No test receives a time limit, skip or expected-failure marker for speed.
- Every reuse or cache key is a content digest of declared inputs taken from the filesystem inclusion policy, plus tool version, configuration and `uv.lock` where a tool is involved, or the authority `logical_generation`. Modification time and git are never a key. Missing or unreadable metadata selects the full run.
- A reused clean verdict is valid only if the gate's positive control and non-empty-input assertion ran under the same key. The dependency audit is never reused.
- A shared compiled registry is the immutable bundled root only and must be proven equal to a fresh compile by a typed equivalence check.
- A cached profile world is built through production operations and its key includes a digest of the producing sources.
- Supported years in any representative set are derived from the registry envelope at run time.
- A gate result is valid only for a tree that did not change during the run. The runner records the tree digest at start and end; a moved tree is reported as an invalid run, not as a red or a green.

## Implementation

We will replace the sequential `gate-local` body with a concurrent gate runner that executes every current population exactly once, and we will remove measured waste underneath it.

1. **Runner.** Extend `dev/test_runs` lanes into a dependency graph of nodes with ordering edges and exclusive resources (authority publication, fixture seeding, CMake configure, documentation output, distributions), one global worker budget, continuation past red nodes with every red reported, and separate parallel and serial nodes. `gate-local` invokes it. Benchmarks that assert CPU budgets run as a final node with the machine to themselves.
2. **Durable record.** Each gate writes one record outside the reaped log tree: per node the verdict, wall seconds, input key and whether the verdict was reused; the tree digest; a supplied head label; and JUnit reports. Per-file seconds are aggregated into a timing file that drives duration-balanced shards, with file size as the fallback.
3. **Single execution.** The sequence corpus runs once per gate; the documentation is compiled strictly once in full scope and the strict-build test reads that node's digest-keyed record; `test-pytest-harness` runs once; one distribution build seeds the shared wheel cohort; prerequisites (authority, seeds, configure) run once.
4. **Shared inputs.** The compiled bundled registry is loaded from a digest-keyed disk copy instead of compiled per worker; the clean-validation record is made to survive process exit; profile-world keys gain the producing-source digest.
5. **Static verdict reuse.** Static checks run concurrently, and a check whose input key matches its last clean run is not rerun.
6. **Heavy files.** Files that set the tail are distributed across workers by test, or their shared per-revision work is hoisted to module scope. The rendering capture was examined and is left unchanged: its two digests hash two different serialisations by contract (`src/cadrumo/domain/modelos/calculation_revision_rendering.py:738`, `:750`), so there is no duplicate to remove without changing stored digests.
7. **Recorded coverage reductions.** Only these, each applied only after the implementer shows in the change that the retained tests assert every claim of the removed cases:
   - The installed-wheel annual IVA journey keeps the newest authored envelope year; the every-year contract stays with the in-process persona settlement tests.
   - The TUI workbench grid stops crossing theme with cases whose assertions read text only; one case per theme remains.
   - Year matrices drop only years that resolve to the same modelo, revision and authority grade as a retained year, derived at run time. This keeps coverage.
   The Modelo 100 per-year behaviour matrices and the real-page rerun in the sequence-golden bounded check are not reduced by this decision.

Worker counts, shard counts and the order of the removals are implementation hypotheses to be tuned by measurement.

## Rationale

The research record shows more than a third of baseline wall time is repetition (the corpus three times, documentation compiled up to five times, a registry compile per worker) and that the remainder is bounded by a six-wide queue and by single-worker files. Removing repetition loses no assertion. Concurrency under a budget uses the machine without creating the oversubscription that produced false reds. The reductions are limited to cases where a second layer already asserts the same contract or where an axis is not read by the assertion.

## Consequences

- Projected quiet wall time is 45 to 55 minutes; the projection rests on loaded measurements and must be confirmed by a measured gate. If the measured gate exceeds 60 minutes after all steps, further reductions need an amendment with their own evidence.
- A gate needs a still tree for its duration, so landings pause while it runs.
- The gate becomes sensitive to cache-key correctness; each cache carries an equivalence or positive-control proof.
- No product code changes under this decision. Changing how the rendering digests are built would alter stored digests and needs its own decision.
- This decision does not make the tree green. Reds found by the baseline are tracked separately.
