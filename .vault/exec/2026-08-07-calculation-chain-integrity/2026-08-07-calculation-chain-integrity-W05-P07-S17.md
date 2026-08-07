---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:29ef4eb49b06afa905c2e51a8ec8e96f4bee762d7f662d62c0bdaabe0bc38058'
step_id: 'S17'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W05.P07.S17

## Outcome

Ran, and the lane produced a result instead of an absence — for two thirds of it. The remaining third is blocked by something other than workers, which is the finding.

## What ran

`pytest src/cadrumo -m serial -n0` selects **54** tests. **36 produced a verdict: 35 passed, 1 failed.** The other 18 never started.

## Two blockers, neither of them xdist

**A peer collection error stopped the first attempt at one test.** `src/cadrumo/tests/test_ledger_corpus_llm_classification.py` fails to import — `cannot import name 'build_claude_classifier' from 'cadrumo.domain.transactions'` — from the in-flight `llm-package-split` relocation. Pytest aborts the whole session on a collection error, so the lane reported `1 tests ran; 24352 were DESELECTED` and produced nothing at all. Re-running with that one module ignored is what let the lane report.

**A subprocess-spawning test exhausts the global timeout.** After 36 verdicts the run hangs inside `dev/packaging/_smoke_common.py::run_checked`, waiting on `subprocess.communicate`, and the faulthandler timeout fires with the reader threads still blocked. Everything ordered after it never runs.

So the Step's premise — that disabling workers is what the held tests needed — is only half right. Workers were one reason; the lane still cannot complete because one serial test spawns a long-running subprocess with no per-test bound, and one unrelated module cannot be imported at all.

## The verdicts obtained

The single failure is `test_iva_quarterly_aggregation_partitioned_p95_cpu_within_budget`, which is `W05.P07.S31`'s subject and is classified there.

## What this leaves open

Eighteen serial tests still have no verdict, and the honest statement is that this run did not produce one for them rather than that they pass. Bounding the packaging smoke test (a per-test timeout, or moving it out of the lane that other tests queue behind) is what would let the lane complete; that is a change to the packaging surface and is not made here.
