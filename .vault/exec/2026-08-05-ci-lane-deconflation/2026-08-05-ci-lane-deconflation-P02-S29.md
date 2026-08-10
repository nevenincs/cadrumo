---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:e8e42dabd8b806160085569581e7eb4a55f4881bffd85edd6fd99045d747d069'
step_id: 'S29'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Stamp the host load reading at fire time into the pytest timeout failure output, and do NOT convert that ceiling to process CPU-time, because pytest-timeout offers only signal and thread methods and has no CPU notion at all so the conversion is not expressible in configuration, and more importantly because a wall-clock bound is the CORRECT instrument here rather than a tolerated one, since the thing this ceiling exists to kill is a wedged or deadlocked test and a deadlocked process burns almost no CPU so a CPU-time bound would never fire on the exact failure the ceiling was added for, which is the same share-hang argument that saved the wall threshold on the integration budgets except stronger because here wall is the only instrument that works, leaving the real defect as interpretability rather than instrument choice since nothing in a timeout traceback records host load so a legitimately slow test under saturation is indistinguishable from a genuine hang and reaches a lead ledger as a plausible fictitious defect with a traceback attached

## Scope

- `the pytest timeout failure-reporting hook and pyproject.toml`

## Description

- Refused the row's original remedy: converting the wall ceiling to process CPU-time. `pytest-timeout` exposes only signal and thread methods and has no CPU notion, and a wedged process burns almost no CPU, so a CPU bound could never fire on the failure the ceiling exists to catch.
- Measured the packaging boundary before choosing a home for the new module. `src/cadrumo/tests/**` is excluded from both the wheel and the sdist by explicit hatch excludes, and `psutil` sits in the dev dependency group rather than the runtime dependencies, so a psutil-importing hook may live there without breaching the dev-harness-does-not-ship rule.
- Refused the second remedy, attaching the stamp in `pytest_runtest_makereport`. Windows has no `SIGALRM`, so `pytest-timeout` takes the thread method, which calls `os._exit(1)` immediately after dumping stacks. No report hook, no teardown, and no buffered stream survives that call, so a report-time stamp is a structural no-op on precisely the host whose contention it exists to explain while passing on a signal-method platform.
- Armed the stamp from `pytest_timeout_set_timer` instead. Both that hookspec and its cancel counterpart are `firstresult`, and `pytest-timeout` registers its own implementations `trylast`, so an implementation returning `None` runs first, installs a pre-fire timer, and leaves the real ceiling to install unchanged.
- Wrote the reading through the terminal writer rather than to a raw file descriptor. A test runs under fd-level capture, so a plain descriptor write lands in a buffer the exit discards; the terminal writer holds the original stream and is the channel the stack dump itself uses.
- Confirmed no prior art existed. A search by meaning plus a targeted sweep found no host-load reader anywhere in the source tree, the dev tree or the root conftest, verified against a positive control so the zero was a real absence rather than a broken query.
- Delegated the hooks from the repo-root conftest to a shared module, matching the marker, worker-count and deselection hooks already hosted there.
- Landed a matched pair of real-subprocess cases as the gate.

## Outcome

Delivered as specified, verified green by the single test authority: 2 collected, 2 passed, 8.03 seconds, with both file mtimes predating the run so the reading is not a photograph of a state that has since moved.

The gate is a matched pair and neither case is sound alone. A run that hits a real ceiling must carry the stamp **and still time out** — because both hookspecs are `firstresult`, an implementation returning a value instead of `None` would swallow the call and silently uninstall the ceiling the stamp exists to annotate, so that assertion is the ceiling's survival rather than a formality. A test finishing inside the identical ceiling must emit **nothing**, or the stamp is an unconditional banner carrying no load information at all.

The stamp assertion turned out to carry a second proof its author had not designed for. The reading is written by a timer armed for 3.6 seconds against a 4-second ceiling, so a subprocess that died early — on a torn read of a mid-edit module, say — would satisfy the return-code and timeout-text assertions while producing no stamp. Its presence is therefore the evidence that the process was alive at 3.6 seconds and that the ceiling, not a crash, ended the run. That distinction was raised before the run rather than discovered in it, because the false result available here is a false green, and nobody re-runs a pass.

What the stamp claims is stated in the module rather than only here: the reading is taken at T-minus-lead, **not** at the instant of the fire, and the lead is printed in the stamp so the gap is visible rather than assumed. Fire-time is unobtainable, because the code that fires is `pytest-timeout`'s own and it exits the process rather than returning.

One limitation is stated and not covered. The gate proves the thread method on this host. It says nothing about the signal method, which is what macOS and Linux take, and no Windows green can speak to that branch.

## Notes

The row has now attracted **three** remedies that would have passed review and done nothing, and that history is recorded in the module itself rather than only here, because the module outlives the row: a CPU-time bound that cannot fire on a wedge, a report hook that cannot fire on the platform whose saturation it measures, and a raw descriptor write that the exit discards. A future author changing this mechanism should first ask on which platform and on which failure the replacement actually executes.

The change was parked outside the repository three separate times while waiting for verification, and the reason was not to protect the work. A root conftest change registers hooks for every test in the tree, so an unverified copy sitting in a shared worktree would have run inside every other agent's suite. The two new modules were parked alongside it rather than only the conftest, because the test module carries a marker the default lane selects, so leaving it behind would have booted two real subprocesses in every run while exercising hooks the parked conftest no longer wired.

One process failure, mine. Cleared to land, the change was unparked without first reading that the same clearance placed it third in the queue, behind two other batches that would then have run through an unverified root conftest. That is the exact harm the parking existed to prevent. It was caught, reported against my own interest rather than absorbed, and the decision to re-park was handed to the party who was not motivated by wanting the row to move.

The predicted wall time was 15 to 25 seconds against an actual 8.03. The estimate was written before the probe ceiling was set to 4 seconds and never recomputed against that constant; 4 seconds of ceiling plus two subprocess boots is the designed cost. A re-measurement with per-test durations was offered and declined, on the ground that it could only confirm what the stamp assertion already establishes rather than falsify it.
