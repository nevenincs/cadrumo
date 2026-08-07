---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e495f72c7678bec96f9aaad2fe3659f01ff6c8a2bb7950b1c1a4021f0e288dc7'
step_id: 'S56'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Add the absent-llm packaging smoke lane: install the core cohort without the extra, drive every inference-adjacent surface, and assert each refusal is the declared install guidance rather than a ModuleNotFoundError

## Scope

- `dev/packaging`

## Description

- Add the absent-extra lane: install the exact cohort with no extras, then drive each model-bearing surface and require the declared install guidance.
- Assert at the artifact level that the extra adds requirements the core closure does not already carry.
- Assert that the extra's probe target is exclusive to the extra, which is the precondition every refusal below it depends on.
- Add the cheap structural gates the lane rests on, so they fail in seconds rather than after a wheel build and an install.
- Correct the lane's declared proofs after its own contract gate caught them unbacked.

## Outcome

The lane is written and the structural gates are landed. Building it surfaced a defect that is the most important result in this Step, and the lane cannot pass until that defect is fixed.

**The inference boundary's guard is dormant.** The extra's registry record probes the imaging package's import name, and that package is an unconditional base dependency of the product. So the availability probe succeeds in every core install, the guard that is supposed to refuse is a permanent no-op, and every surface behind it runs unguarded. Measured rather than reasoned: exporting the core closure with no extras and no development group yields the imaging package pinned at a concrete version, and does not yield the NVML binding.

The defect is **invisible from the source tree**, which is why nothing had reported it. The guard is covered where it is written, but that test can only reach the refusal by installing a meta-path finder that blocks the imaging import inside a fresh interpreter. Its own prose is candid that the absent state "has to be constructed rather than installed" and calls the extra nominal. That was accurate when written. A test that constructs the condition it checks will pass forever against a condition no real install can produce, and no amount of source-level coverage distinguishes the two.

**The preceding Step is what made this fixable.** Until the NVML binding was declared, the extra genuinely had no member the core closure did not already supply, so there was no import name a probe could point at and the defect had no fix short of restructuring the extra. Now the extra is real and only the probe is stale — a one-string correction rather than a design problem.

The fix was proven out of repo, editing nothing under the source tree: the same check was recomputed with only the probe's import name swapped.

    llm probe='PIL'    -> dormant={'llm': ['pillow']}
    llm probe='pynvml' -> dormant={}

Red and green off a one-token difference, which establishes both that the gate bites and that it is satisfiable — a gate that can never pass is worth no more than one that never fails.

The structural gate is written over **every** registered extra rather than only this one, because the defect is a class: the moment a package declared in an extra becomes something core also needs, that extra's guard silently stops guarding. The other four extras pass, so the gate is precise rather than noisy.

The lane's own proof contract then caught a second defect, this one authored here. The contract gate reads declared claims and their recording calls statically, so claims built as interpolated strings declare something no assertion can be seen to record. Four were unbacked, and one was substantively wrong — it named a proof the shared installer does not emit, so at runtime the lane would have refused to write its manifest and could never have completed even with the probe corrected. The lane over-claimed in exactly the way that mechanism exists to prevent. Claims are now plain constants shared between declaration and recording, with the variable detail printed beside each proof instead of folded into the claim.

## Verification

The lane's structural gates, marker expression stated and counts read from the log rather than paraphrased:

    uv run --no-sync pytest dev/packaging/tests/test_absent_llm_boundary.py -p no:randomly -n0 -m "unit or (integration and not serial)" -v
    collected 4 items
    test_every_optional_extra_probes_a_package_core_does_not_supply FAILED
    test_the_llm_extra_declares_a_requirement_core_does_not PASSED
    test_the_surface_inventory_names_real_exported_entry_points PASSED
    test_the_expected_hint_matches_the_registered_extra PASSED
    1 failed, 3 passed

Four collected, four ran, none deselected. The single failure is the dormant guard, reported as the extra and the core package supplying its probe target. The second test passing is what establishes the extra itself is sound, so the failure localises to the probe rather than to the dependency closure.

The proof-contract correction, verified against the gate that caught it:

    uv run --no-sync pytest -q -n0 -p no:randomly dev/packaging/tests/test_proof_contract.py dev/packaging/tests/test_absent_llm_boundary.py --tb=line -rf
    1 failed, 19 passed in 75.42s

The contract gate is fully green; the one remaining failure is the deliberate one above.

The whole packaging preflight lane, to give that deliberate red an owner picture:

    uv run --no-sync pytest -q -n0 -m unit dev/packaging/tests
    8 failed, 408 passed, 109 deselected in 889.61s

Two failures belong here: the deliberate one, and the proof-contract one now fixed. The remaining six share one cause outside this Step's surface — the operator-surface schema build cannot resolve three provisioning command subtrees, which is a neighbouring lane's half-landed verb tree. Recorded, not patched.

## Notes

The failing structural gate is **left red deliberately**, and the commit message says so rather than leaving a later reader to infer it. The blast radius was checked before committing: the configured test paths do not include this directory, so it reds only the packaging preflight recipe and not the default suite.

Two things were deliberately not done, both correct calls.

The lane is **not executed end to end**. Its precondition provably cannot pass until the probe is repointed, so a full run would only re-derive at the cost of a wheel build and an install what the cheap gate already establishes in seconds.

The lane is **not registered** with the campaign driver or the task runner. Wiring a lane that cannot pass would red the whole packaging smoke recipe for every agent working in this tree. Registration is a small change once the probe is corrected.

The correction itself is blocked on the deferred environment sync rather than forgotten. The NVML binding is absent from the current environment, so repointing the probe today would make the extra read as absent and start refusing live surfaces — including the rasterisation the vision route depends on. It lands with the sync, which the operator has queued alongside the live NVML read the preceding Step's declaration unblocks.

The lane touched no accelerator and loaded no model at any point.
