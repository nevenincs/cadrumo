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

### p01-s01-baseline-run-5 | medium | Second live baseline: 93 of 100 movements proposed, warm median 13.4 s, 3.87 movements per minute

Run 5 of 2026-11-22, on tui `f949cb2f49` with the bundle 21 package and cadrumo-agent `46f9b44`, model qwen3:4b-instruct served by the bundled llama.cpp router, context 8192 confirmed in the llama-server arguments, automatic placement, 100 synthetic movements attempted. 93 returned a proposal, 5 failed with `ERROR_TRANSACTION_LLM_CLASSIFIER` and 2 were refused with `REFUSED_LEDGER_EVIDENCE_READER`. First result 52.1 s. Warm: median 13.4 s, mean 15.5 s, 95th percentile 29.7 s, minimum 7.2 s, maximum 105.1 s; 3.87 movements per minute warm, 3.40 overall. Classification wall time 1993 s, session setup 73 s, CLI floor median 6.6 s with the machine under a full-gate load. The harness re-sign-in held the session for 33 min. Product log 15609 lines with no WARNING or ERROR. The run exited 1 only at teardown, refused with `runtime_timeout`. Against run 4: 16 of 24 proposed, warm median 29.1 s, 1.78 movements per minute, cut off at 13.5 min. The 1000 movement figure is not yet measured.

### p01-s01-model-time-not-split | medium | Model time cannot be separated from time outside the model

`chat_requests`, prompt tokens and model milliseconds were all 0 in run 5: the router proxies each request to a child llama-server whose timing lines the harness does not capture, so P05 cannot tell model time from the time spent outside it.

### p01-s01-remaining-classifier-failures | high | 7 of 100 valid movements still end without a proposal

5 `ERROR_TRANSACTION_LLM_CLASSIFIER` and 2 `REFUSED_LEDGER_EVIDENCE_READER` in run 5; each code needs its cause named from the run's copied logs.

### p01-s01-teardown-runtime-timeout | medium | Teardown is refused after the measurement completes

The run's closing step was refused with `runtime_timeout`, so a complete measurement exits 1.

### p01-s01-output-placement | low | Harness outputs break the worktree temporary-output naming

Outputs land in `.tmp/ledger-classification-speed/<stamp>` rather than `.tmp/<date>-<owner>-<purpose>/`.

## Recommendations

- For `p01-s01-cli-boundary-after-13-minutes`: trace the refusal to its owner and fix the cause; if the bound is a deliberate session lifetime, the harness re-establishes its session as an operator would rather than lengthening the lifetime.
- For `p01-s01-classifier-errors-on-synthetic-movements`: name the cause of each code and make the classifier return a proposal or a typed reason.
- For `p01-s01-failed-run-loses-evidence`: write the partial summary and copy the logs out before removing the root, on every exit path.
- Re-run `P01.S01` once these land, then take the 100 and 1000 movement figures.
