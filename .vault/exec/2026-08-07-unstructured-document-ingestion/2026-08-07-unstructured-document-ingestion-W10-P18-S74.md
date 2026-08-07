---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1637699faff9e622a971df71c42fd037c376ce25902a02586bfd826d6b26444f'
step_id: 'S74'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Add the model remove action reporting freed bytes and the doctor row detecting partially-installed states in both directions (extra without models, models without extra), gated by doctor row tests

## Scope

- `src/cadrumo/application/provisioning.py`

## Description

- Add `read_installed_models`, a short-timeout read of the runtime's on-disk model inventory, distinct from the resident-set read; an unreachable runtime yields `None`, never an empty tuple.
- Add `remove_runtime_model`, delegating deletion to the runtime that owns the store, guarded by the same Cadrumo-selection boundary the unload action carries.
- Measure the freed figure across the action: read the size before the delete, report it only after a re-read confirms the model is gone.
- Add `probe_local_model_provisioning`, a doctor row detecting a partially-installed local-inference posture in both directions.
- Thread the row into `aeat config check` beside the existing hardware and contention rows.

## Outcome

Removal reclaims disk without Cadrumo touching a path it manages. Nothing on the action unlinks a file, walks a directory, or reaches a secure-storage object; the runtime performs the deletion, so no key material or encrypted bucket is reachable from the code by construction.

The freed figure is a measurement rather than an estimate. A delete the runtime accepts but does not perform, and a delete whose confirming read fails, both report no figure: an unreconcilable number is worse than none. A runtime that omits the size reports an absent figure rather than zero.

The doctor row treats the two half-states as different faults. Extra installed with no selected model prescribes a pull; a selected model occupying disk with the extra absent prescribes the install or a removal. The two conditions each require the extra state the other forbids, so neither can be satisfied by the other's evidence. Coherent postures — both halves present, or neither — report available, so the row is not noise on a plain core install. An unreadable inventory reds only when the extra is present; when it is absent the row says out loud which direction it could not rule out rather than claiming a clean result.

## Verification

    uv run --no-sync pytest src/cadrumo/application/tests/test_provisioning_model_removal.py -n0 -p no:cacheprovider -q
    16 passed in 9.55s

    uv run --no-sync pytest src/cadrumo/application/tests/test_provisioning.py src/cadrumo/application/tests/test_provisioning_hardware_contention.py src/cadrumo/application/tests/test_provisioning_model_removal.py src/cadrumo/entrypoints/cli/_config -n0 -p no:cacheprovider -q
    205 passed, 216 deselected in 38.01s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests -n0 -p no:cacheprovider -q
    716 passed, 2899 deselected in 51.11s

Four mutations were applied from outside the repository — the function's source is read from the imported module, one substitution is applied, and the result is bound back onto the module — so no tracked file changed and a peer sweep could not commit the mutation. Each reddened a distinct assertion set.

Dropping the confirming re-read reddened the measured-figure control and the accepted-but-not-performed case. Reporting zero instead of the measured size reddened the measured-figure control and the omitted-size case. Dropping the extra check from the first direction reddened the disjointness test. Dropping it from the second reddened the coherent-posture positive control.

## Notes

The tests use no mock, patch or stub. Runtime interaction runs against a real threading HTTP server holding a mutable store that the delete handler actually mutates, so the production re-read observes a store that genuinely changed rather than a canned second answer. The extra-absent condition is produced by a real import-system meta-path finder that raises the same absence a core install produces, so the production availability predicate and its exception branch both run unaltered.

The operator-facing verb for removal was not added: the Step scopes the change to the application module, and the provision command family and its payload models are another lane's surface. The action is exported and ready for it.

The row's `detail` and `remediation` are plain strings, matching every other status this module builds; the localised part of the rendering is the availability mark the check command applies to all rows alike.
