---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:69ba619b13598bafff0ea07529de52c260e468d1ce9e4dcb92e252adee14cb7e'
step_id: 'S17'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Refuse cloud provider selection on real-evidence paths absent the explicit per-invocation consent acknowledgement, default-off and gestor-barred, gated by refusal tests on both the extract and confirm surfaces

## Scope

- `src/cadrumo/llm`

## Description

- Reinstate the two deployment consent settings on `Settings`, both defaulting to the refusing value, and restate the neighbouring telemetry block's claim that it was the last off-host posture.
- Add the consent module: the three-condition permission function, a per-invocation token that refuses every serialization path, and the sole minting entry point that runs the gate before constructing one.
- Add a typed consent error that is deliberately not a configuration-error subclass, so a caller retrying at another provider cannot swallow a confidentiality refusal.
- Carry an evidence marker and an excluded consent token on the request model.
- Enforce the gate at the client's single dispatch point, ordered before the cache read and before adapter construction.
- Mark every request the two evidence readers build as evidence-derived unless the caller names the public measurement corpus; mark the two local classifiers' requests for the same reason even though their provider pin makes the gate unreachable from there.
- Re-scope the cloud-deletion gate: three symbols move from the deleted sweep to a presence-and-wiring assertion, the non-vacuity floor re-bases, and the module docstring records the move as the visible decision its own contract demands.
- Add the refusal strings to all four locale catalogues.

## Outcome

An off-host read of a taxpayer document refuses with no configuration at all, refuses when the deployment flag alone is set, refuses in a gestor deployment even with a correctly minted token, and refuses through the unpinned text reader when a caller names a cloud provider and model. A fully consented read reaches the provider. The dispatch is the only place any of this is decided, so no per-caller provider pin is load-bearing.

The ordering is the part that carries the most weight and the least visibility. Gating before the cache read stops a once-consented entry from serving a later unconsented invocation. Gating before adapter construction stops a missing API key from raising first — an absent credential is an accident that looks like a control, and a boundary whose refusal is indistinguishable from a misconfiguration cannot be relied on to have fired. Every case in the suite therefore supplies a usable credential against a loopback endpoint, refusals included.

Scope landed narrower than the governing decision in one respect, stated rather than glossed: the per-profile capability and the operator-facing acknowledgement flag stay asserted deleted, because nothing mints a token at a CLI boundary yet. The consequence is that today the gate refuses every off-host evidence read in production. That is the correct default-off posture, but it is not yet the full lifecycle.

## Verification

    uv run --no-sync pytest -n0 -p no:cacheprovider src/cadrumo/llm/tests/test_evidence_consent_gate.py src/cadrumo/tests/test_cloud_transport_fully_deleted.py -q
    22 passed in 24.08s

Mutation proof, six mutations applied from a pytest plugin outside the repository so no tracked file changed. Each removed one property and reddened exactly the assertions that own it:

    remove_gate                    4 failed, 18 passed
    drop_gestor_bar                1 failed, 21 passed
    drop_opt_in_condition          1 failed, 21 passed
    unmark_the_reader              1 failed, 21 passed
    reorder_the_dispatch           1 failed, 21 passed
    delete_the_call_from_source    2 failed, 20 passed

Two of these are worth reading together. Removing the gate at runtime left the deletion gate's wiring assertion green, which is correct rather than a miss: that assertion reads source, so only the source-level deletion reds it — and it did. The reorder mutation failed on `assert 9 < 4`, the ordering comparison itself, not on the guard that all three calls are present.

Sequential full-tree delta over `src/cadrumo/llm`, `src/cadrumo/application/ledger`, `src/cadrumo/core` and `src/cadrumo/tests`, cold cache both sides:

    before   78 failed, 3790 passed, 18 deselected in 1617.30s
    after    60 failed, 3838 passed, 23 deselected in 1715.12s

Three failures appear in the after set and none is attributable to this change: two do not reproduce when re-run in isolation, and the third names two modules under `dev/release/` that this Step does not touch.

    uv run --no-sync python -m dev.quality.quiet lint-imports
    Contracts: 5 kept, 1 broken.

The broken contract is the layered one, on two application-ledger modules outside this surface. The persistence contract returned to kept once the new test module's adapter-facade edge joined the existing test-file carve-out beside its five siblings.

## Notes

The before-run is honestly contaminated and should not be read as a clean baseline: editing began while it was still executing, so file-reading gates in it saw partially-changed content. The clearest symptom is the deletion gate's own sweep, which is red in the before set and green in the after set purely because the settings landed mid-run. The delta above is still usable because every after-set failure was triaged individually rather than inferred from the counts.

Deliberately not built, and each belongs to a later row: the per-profile eligibility bar, the CLI minting surface and its acknowledgement flag, and the consent-ledger append at the same choke point. The minting-side provenance assertion was left untouched for the same reason — narrowing it to "every transport mintable without a consent token is local" has nothing to bite on while no consented cloud stamp can be produced.

The locale scaffold reflowed a handful of neighbouring entries that peers had set as single lines. No value changed; only YAML wrapping did.

One overlap needs routing rather than a decision taken here. This row and `W05.P11.S41` describe the same choke-point gate, and landing it at all required the `W05.P11.S40` deletion-gate re-scope in the same change, because the reinstated symbols cannot exist while that gate still lists them as deleted. Which rows this closes is a plan question.
