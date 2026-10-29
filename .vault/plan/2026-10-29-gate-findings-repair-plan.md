---
tags:
  - '#plan'
  - '#gate-findings-repair'
date: '2026-10-29'
tier: L1
related:
  - '[[2026-07-18-user-docs-localization-adr]]'
  - '[[2026-07-21-locale-key-resolution-adr]]'
  - '[[2026-10-07-git-free-tooling-adr]]'
  - '[[2026-09-02-gate-integrity-adjudication-commit-time-mechanical-gates-adr]]'
  - '[[2026-07-01-import-centralization-adr]]'
  - '[[2026-07-13-data-output-standardization-adr]]'
  - '[[2026-08-14-test-harness-sanity-successor-adr]]'
modified: '2026-10-29'
body_schema: body-v2
body_hash: 'sha256:f45b553880447f582e2a8943f9586eba837f1920c2532e66431fdd82a666bf76'
---

# `gate-findings-repair` plan

## Description

Approved 2026-10-29

The operator requested all eleven named checks, triage of incoming findings, and delegated repair using Terra 6.1 high for bounded changes and Sol 6.1 for architectural work. This authorization covers ordinary corrections within accepted decisions, without relaxing gates or overwriting concurrent changes.

S01 aligns strict spelling context with the accepted Spanish AEAT terminology and native translation decisions. S02 repairs canonical defining-module and import privacy violations within existing ownership rules; it moves temporary-output behavior to a public semantic owner, updates every consumer atomically, shares the documentation inclusion predicate, and refreshes the census. S04 applies the accepted 2026-10-29 workspace amendment from the data-output-standardization decision: Python packaging general temporary state and disposable source snapshots belong under owning worktree .tmp; final artifacts and native enrolled build admission retain their contracts. S05 applies the accepted test-harness-sanity successor decision to coverage process ordering and real subprocess verification: one confined data destination must exist before controller and worker instrumentation starts. The mechanical repair and Git-free tooling decisions govern verification throughout. No new costly decision is introduced. Uncovered commitments must return with evidence before implementation.

Earlier direct repairs normalized two mixed-ending files without a Git diff, wrapped a packaging error line, and corrected a stale ModelRunLane test fixture. Existing unrelated edits and external dictionary work retain their ownership.

## Steps

- [x] `S01` - Align spelling segmentation with accepted Spanish AEAT terminology and exact product names while preserving typo detection; `dev/locales spelling owners and focused tests, dev/docs/casilla_page_rendering.py and numeric section regression test, canonical generated casilla refresh`.
- [x] `S02` - Repair reproducible import authority violations and regenerate the governed module census after sources stabilize; `dev/temporary_output.py, dev/_paths.py and all moved-function consumers, dev/docs/i18n.py, dev/locales/signal_documentation_inventory.py, .importlinter, import census and focused tests`.
- [x] `S04` - Keep Python release cohort temporary state inside owning worktree scratch while preserving snapshot and native build admission; `dev/packaging/build_storage.py, dev/packaging/python_cohort.py, dev/packaging/release_cohort.py, snapshot reclaim contracts and focused packaging tests`.
- [x] `S05` - Keep pytest controller and worker coverage data in one admitted destination and verify complete combination before reporting; `dev/test_runs coverage destination lifecycle, test-coverage recipe/bootstrap and isolated pytest-cov regression tests`.
- [ ] `S03` - Reconcile all eleven requested gate results and review integrated repairs against their governing decisions; `gate verification and final audit`.

## Parallelization

S01 is assigned to locale_resolution (Sol 6.1 high): locale spelling segmentation/enrollment and focused tests only. S02 is assigned to import_resolution (Sol 6.1 high): temporary-output owner and all moved-function consumers, documentation inclusion predicate and its consumer, import classification and census. These Steps may execute concurrently; S02 must coordinate its mechanical import change in dev/locales with S01. Workers preserve unrelated edits and send exact diffs. The parent serializes governance and commits. test_health_checks (Terra 6.1 high) owns packaging, coverage and health-report execution. Expensive checks have one owner; final import/health checks wait for stable inputs. S04 follows the current import proof boundary and is assigned to import_resolution; it owns build_storage, Python/release cohort snapshot placement, reclamation contracts and focused tests. Terra owns the unrelated packaging fixture repairs and coverage. S05 is assigned to import_resolution after the completed prior checks; test_health_checks owns read-only copied-database recovery evidence. S03 follows all repairs and verifies the integrated result. Any remaining locale inventory debt requiring a new persisted language schema stays an explicit finding rather than being suppressed.

## Verification

Use focused detector tests for exact tax/product spans, surrounding typos, dictionary routing, temporary-output confinement, and shared documentation inclusion. Run lint, format, type and covering tests for changed files. S05 adds real small xdist coverage probes for default and explicit destinations, early plugin importability from a temporary working directory, combined worker contributions, and absence of orphan shards. Copied-database recovery remains a secondary measurement and cannot change the original recipe exit. Record final exit codes for all eleven operator-requested commands; reuse earlier passing checks when their inputs remain unchanged. Re-run failed checks after relevant repairs and disclose concurrent source changes or unavailable gates separately from defects. The authoritative import gate must prove a current census on stable source inputs. Complete final integrated review against the linked decisions before closing S03; do not report a failing or unavailable check as passed.
