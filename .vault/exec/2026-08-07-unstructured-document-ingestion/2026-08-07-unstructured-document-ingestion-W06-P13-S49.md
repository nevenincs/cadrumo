---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:304ce0ec4c10cfcfc9cf828f7e553cba2819c800d46bf1146fdf29060220b4ad'
step_id: 'S49'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Implement adaptive selection resolving each role to the best candidate fitting the measured hardware tier and the licence posture, with an operator override surfacing a visible licence advisory on a non-commercial candidate, gated by selection-matrix tests over injected profiles

## Scope

- `src/cadrumo/application/provisioning.py`

## Description

- Extract the binding-arena rule into one shared reader and route the existing contention check through it.
- Add the typed selection result carrying the resolved candidate, the reported tier, the measured free figure, the advisories and the operator-facing detail.
- Add the per-role resolver applying the capability, licence and headroom bars in that order and taking the weakest survivor.
- Honour an operator override unconditionally while attaching every concern it carries.
- Expose the localised non-commercial licence advisory off the selection.
- Type the shared construction context so the per-branch splat stays checked.

## Outcome

Selection is bounded from below. Candidates are ordered by ascending memory requirement and the first survivor wins, so a machine with headroom to spare still resolves to the small model; a larger model is reachable only as an explicit operator choice. Nothing in the resolver ranks on capability above the floor.

Three bars apply, each for a different reason. The context window excludes on capability, because a model that cannot hold the request cannot do the job at any price. The licence excludes under a commercial posture, and this is the bar that moved the shipped defaults. Measured headroom compares the requirement plus the configured safety margin against free memory in the binding arena.

The arena rule now has one home shared by the planner and the admitter. It previously existed as an inline expression inside the contention check; two independent copies of "which figure binds this load" would have been free to disagree, and the disagreement would have surfaced as an admitted load that could not fit.

An unmeasurable machine selects rather than refuses, and this is deliberate rather than a softening of the fail-closed rule. Refusing to *name* a model because headroom is momentarily unreadable would break provisioning on exactly the machines that most need to pull one. The load itself is still failed closed at the contention check, and the selection says so through an explicit fit-unverified advisory.

An override always wins and is never quiet. A licence-barred override surfaces a visible advisory naming the model and its licence; an uncatalogued one is honoured while stating plainly that no licence claim can be made about it, rather than defaulting to permissive.

## Verification

Gate authored at `src/cadrumo/application/tests/test_model_selection.py`. Every hardware figure is constructed in the test and passed through the probe's own injection arguments, so the production model construction and comparison run while this host's actual device state — which changes minute to minute under an agent fleet — cannot reach an assertion.

    uv run --no-sync pytest -p no:randomly -o addopts="-p no:cacheprovider" -m unit src/cadrumo/core/tests/test_model_catalogue.py src/cadrumo/application/tests/test_model_selection.py src/cadrumo/application/tests/test_provisioning_hardware_contention.py src/cadrumo/application/tests/test_provisioning.py src/cadrumo/llm/tests/test_local_text_reader_wiring.py -q
    87 passed in 31.75s

The matrix covers four axes and their interactions: the measured tier across all four bands and all three accelerator arenas; the licence posture in both directions; the capability floor; and the override in its catalogued, uncatalogued, licence-barred and below-context forms. Every refusal case carries a positive control asserting the accept case passes through the same call. The capability floor is proven by moving the floor and observing the selection change, rather than by naming the excluded model, so the exclusion is shown to be the context comparison and not an unrelated filter. The margin is proven load-bearing by an exact-fit refusal beside an exact-plus-margin admission.

The advisory is asserted to render, interpolate and differ across all four shipped locales; its wording is never asserted.

## Notes

One authored test asserted a property this catalogue cannot exhibit — that a non-commercial posture could *select* a research-licensed candidate. It cannot, and that is correct: the weakest candidate in every role is permissively licensed, so the two postures resolve identically and the licence filter is load-bearing only against an override. The test was replaced with the true property, plus a guard that reds if a research-licensed candidate smaller than the default is ever added, which is the change that would silently make the posture decide the shipped model.

The shared construction context was initially an untyped mapping splatted into each return, mirroring a pattern already in this module. A type check rejected it; it is now a TypedDict. The sibling untyped splat in the contention check predates this work and was left for its owner.
