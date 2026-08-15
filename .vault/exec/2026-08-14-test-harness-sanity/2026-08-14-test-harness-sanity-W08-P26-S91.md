---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:3904305840cb6f9411a36354a07f29dbf2c3b8b58ce779397fea6df7d096ac9e'
step_id: 'S91'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---
# Run unit and integration recipes and compare measured runtime to baseline

## Scope

- `justfile`

## Description

- Locate the recorded baseline, its exact commands and its scope, rather than measuring against a remembered figure.
- Run each lane sequentially, never concurrently, so lanes do not contend for the same twenty-four cores.
- Report each lane's runtime and state, per lane, whether the comparison to baseline is valid.

## Outcome

Both recipes were run and compared. The comparison is REPORTED AS INVALID for each lane, on separate and specific grounds, and the figures behind that verdict are below. An invalid comparison is this row's result, not a gap in it.

**Baseline**, recovered with its exact commands and scope (`src/cadrumo/entrypoints/`):

| lane | baseline |
|---|---|
| parallel, `-n 8` | 338.17s (3334 passed) / 537.72s (3363) / 578.77s (3363) |
| serial, `-n0` | 301.77s (52 passed, 4248 deselected) |
| unit | none recorded anywhere in the vault |

**Serial integration — invalid because the lane does not complete.** 35 of 52 tests reached, 7 failed, then a hang; pytest-timeout fired and the run was killed at 754s wall. The hang is at `mcp/tests/test_stdio_lifetime.py:845` on a `readline()` of the client's stdout. The read is a deliberate functional floor, whose own comment says the server "must prove it actually serves MCP over this exact pipe, otherwise 'it exited' would pass for a server that simply crashed at startup". So the guard written to catch a crashed server is what hangs when the server crashes, and it hangs rather than seeing EOF because the leaked stdin pipe under test holds the descriptor open. A runtime figure cannot be produced for a lane that never finishes.

**Parallel integration — invalid because the population moved.** Measured twice, either side of an import fix that landed between them:

| run | wall | passed | failed | errors |
|---|---|---|---|---|
| pre-fix | 257.69s | 1941 | 899 | 811 |
| post-fix | 703.47s | 2559 | 1015 | 77 |

Errors fell ninety per cent and passing rose by 618. The lane became SLOWER because it stopped erroring out early and began doing real work. This was predicted before measuring and is the reason the raw ratio must not be quoted: a failed test is cheaper than a passing one, so wall-clock moves opposite to health. Against a baseline that was near-green, the only defensible normalisation is cost per test executed, which is 0.193s now against 0.101 to 0.172s then.

**Unit — no baseline exists, so this establishes one rather than comparing.** 4356.79s at `-n 8`, 20441 passed, 4345 failed, 741 errors. Recorded with the caveat that the recipe's own worker count is `auto`, which is 24 on this machine, so this figure is not recipe-faithful and a recipe-faithful run supersedes it.

## Notes

**The baseline does not work as a regression detector, which is the most reusable thing this row found.** Its three recorded runs span 338s to 579s on identical selection at two commits — a 1.7x spread. Nothing smaller than roughly a seventy per cent change can surface through that noise. Anyone wanting lane-runtime regression detection needs a stable measure — cost per passing test, or a fixed green subset — not a wall-clock total over a population that shifts underneath it.

**What the standing goal still asks for and this row does not deliver**, recorded rather than quietly dropped: a valid runtime comparison for any lane. That requires a tree where the serial lane completes and the failure population is close to the baseline's. Both blockers are outside this campaign — the hang traces to CLI verbs absent from the MCP schema, and the failure population to a registry export-layout gap and a campaign that shipped production refusals without sweeping its callers. This row does not narrow the goal to fit what was measurable.

**Measuring is how the operator's runtime constraint got its evidence.** The figures here established that one integration lane over one directory is 11 to 14 minutes and the unit lane over an hour, and profiling under this row found the causes: fifty-six per cent of every process's registry load is BeautifulSoup re-parsing static regulatory HTML with no cache, and the lane's own hot spots are individual tests of 132s, 105s and 98s. Those are recorded in the harness-performance audit with the two disproved hypotheses beside them.

**Method held throughout, and one violation of it caught.** Lanes were timed sequentially so they could not contend. One set of authority-load readings (68s, 40s, 37s against a true 22s) was taken while an eight-worker run was still going; those were discarded rather than reported, which would have shown a regression that did not exist.
