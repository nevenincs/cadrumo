---
tags:
  - '#audit'
  - '#ledger-classify-queue'
date: '2026-11-22'
modified: '2026-11-22'
body_schema: 'body-v2'
body_hash: 'sha256:d05e758e89087256afbb9d335ffbd07fe960823df3e0f3f7014f41db912a1171'
related:
  - "[[2026-11-20-ledger-classify-queue-plan]]"
---

# `ledger-classify-queue` audit: `Ledger classification speed baseline`

## Scope

Plan Step `P01.S01`: the speed of one ledger classification through the real `aeat app ledger classify ID --llm` path on the local lane, measured by `dev/measure/ledger_classification_speed.py` against a package built from the head, before any optimisation in phase `P05`. Run by PRIME on the operator's approval of 2026-11-21 23:58; numbers recorded as reported, not re-derived.

## Findings

### p01-s01-baseline-run-4 | medium | First live baseline: warm median 29.1 s per movement, 1.78 movements per minute, run cut short at about 13.5 min

Run 4 of 2026-11-22, on tui `5b6251db85` with the bundle 20 package, model qwen3:4b-instruct served by the bundled llama.cpp, context 8192, automatic placement, 100 synthetic movements attempted. The first 24 reached the model in 809 s. Of those 24, 16 returned a proposal, 6 failed with `ERROR_TRANSACTION_LLM_CLASSIFIER` and 2 were refused with `REFUSED_LEDGER_EVIDENCE_READER`. The first proposal took 115.8 s (cold start). Warm proposals: median 29.1 s, mean 30.7 s, minimum 14.8 s, maximum 46.0 s; throughput 1.78 movements per minute. From about 13.5 minutes into the run, items 24 to 99 and the closing logout were all refused with `REFUSED_CLI_BOUNDARY`. The script exited 1 without writing its JSON summary, and the disposable root was removed with its product and llama-server logs, so this run's per-movement records exist only in the operator's report. The 100 and 1000 movement throughput figures the Step asks for are not yet measured.

### p01-s01-cli-boundary-after-13-minutes | high | Every CLI call is refused after about 13.5 min of continuous classification

A 1000-movement run needs hours, so the cause (harness session lifetime or a product boundary a person would also meet) must be found and fixed before the remaining `P01.S01` figures can be taken.

### p01-s01-classifier-errors-on-synthetic-movements | high | A third of valid movements end without a proposal or a typed reason

6 of 24 `ERROR_TRANSACTION_LLM_CLASSIFIER` and 2 of 24 `REFUSED_LEDGER_EVIDENCE_READER` on synthetic movements that should classify. A valid movement must get a proposal or a reason that says what happened.

### p01-s01-failed-run-loses-evidence | medium | A failed run writes no JSON and deletes its logs

The harness removed the disposable root, with its logs, and wrote no partial summary when the run failed, so a failure cannot be diagnosed afterwards.

## Recommendations

- For `p01-s01-cli-boundary-after-13-minutes`: trace the refusal to its owner and fix the cause; if the bound is a deliberate session lifetime, the harness re-establishes its session as an operator would rather than lengthening the lifetime.
- For `p01-s01-classifier-errors-on-synthetic-movements`: name the cause of each code and make the classifier return a proposal or a typed reason.
- For `p01-s01-failed-run-loses-evidence`: write the partial summary and copy the logs out before removing the root, on every exit path.
- Re-run `P01.S01` once these land, then take the 100 and 1000 movement figures.
