---
tags:
  - '#audit'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:8e4f05644b9526210e1d3d2df327cc0230bc7f6bb5ab7f02d9eae4c06be68ea4'
related:
  - "[[2026-09-07-quality-gate-zero-closure-blind-green-gates-adr]]"
  - "[[2026-09-07-quality-gate-zero-closure-blind-green-measurement-research]]"
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---

# `quality-gate-zero-closure` audit: `Bounded mutmut measurement`

## Scope

Measure the pinned mutation engine against one bounded detector module and
its real assertion gate. The run uses an isolated detached worktree and a
separate POSIX virtual environment so neither the Windows host limitation nor
concurrent edits can contaminate its cache or result set. The record captures
the exact command, revision, wall-clock duration, and counts by terminal mutant
status. It reports no mutation score: each non-killed mutant is retained for
individual triage.

Mutation generation is bounded to the scanner module. The generated test tree
copies both roots that the gate declares it sweeps, because omitting either
would make the anti-vacuity floor fail before mutation rather than measure the
gate against its real subject.

## Findings

### bounded-scanner-run | low | the pinned runner completed a bounded mutation pass in 61.19 seconds

The fresh WSL run used mutmut `3.7.0` in the isolated environment
`/tmp/cadrumo-s105-env-wsl` and invoked
`UV_PROJECT_ENVIRONMENT=/tmp/cadrumo-s105-env-wsl uv run --frozen mutmut run
"dev.quality.tautological_assertion_scan*"` at detached revision
`6166c37a38fd40af64af58286f6dc7922266d4c2`. Its generated tree copied the
declared `src/cadrumo` and `dev` scan roots. It generated 77 mutants of the
single configured scanner module: 70 were killed and 7 survived. No mutant
ended as error, suspicious, timeout, no-test, skipped, or type-check. These
are terminal counts and individual findings, not a mutation score.

### surviving-mutant-triage | high | six survivors expose unprotected behaviour and one is semantically inert

Each survivor was inspected by identifier and diff:

- `x__is_constant_truthy__mutmut_3` changes `bool(node.keys)` to
  `bool(None)`. A non-empty dict assertion is then misclassified as
  never-passing instead of never-failing. This is a real gate finding: the
  detector still emits a row, but the outcome distinction its contract
  explicitly owns is unprotected.
- `x__reason_for__mutmut_8` and `x__reason_for__mutmut_35` corrupt explanatory
  reason strings by surrounding them with `XX`. Both are real gate findings:
  the observable diagnostic is damaged while the fragment-only assertions
  remain green.
- `x_scan_tautological_assertions__mutmut_6` changes the syntax-error separator
  from `chr(10)` to `chr(11)`. This is a real gate finding: an attributable
  line-oriented notice becomes a vertical-tab-delimited diagnostic without
  failing its substring-only assertion.
- `x_scan_paths_for_tautological_assertions__mutmut_3` passes `None` instead of
  the source path. This is a real gate finding: findings lose their openable
  locator while the sweep gate remains green.
- `x_scan_paths_for_tautological_assertions__mutmut_7` replaces explicit
  `utf-8` decoding with the platform default. This is a real gate finding:
  the declared cross-platform source-decoding contract disappears on hosts
  whose default happens to accept the current corpus.
- `x_scan_paths_for_tautological_assertions__mutmut_9` changes `utf-8` to
  `UTF-8`. This mutant is semantically inert because Python codec lookup is
  case-insensitive and both spellings resolve to the same codec.

## Recommendations

Treat the six behaviour-changing survivors as ordinary owner findings: add
controls for the dict outcome, complete diagnostic text and separator, path
propagation, and explicit source decoding. Close the codec-capitalisation
survivor as inert for the recorded reason. Keep the measured scope bounded to
one detector module at a time; use the observed wall clock to declare the
standing verify-only trigger and cadence rather than turning any count into a
target.
