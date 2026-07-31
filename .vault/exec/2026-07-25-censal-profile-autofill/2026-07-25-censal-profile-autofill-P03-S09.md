---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:0dc1d70bf309b5359364500b3c312e7dc5c1ce0438a1eef4d97b08db50dc3a05'
step_id: 'S09'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Delete the register-based censal pull, its manager action and its tests, and re-point the causa-casilla mapping it fed

## Scope

- `src/cadrumo/application/live/_censo_036_pull.py`
- `src/cadrumo/application/live/tests/test_censo_036_pull.py`
- `src/cadrumo/core/external_constants.py`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py`
- `src/cadrumo/_data/registry/aeat/modelos/036/revisions/2025-02-03-y-siguientes/casillas/0002-causas-presentacion.toml`
- `docs/api/cadrumo.application.live._censo_036_pull.rst`

## Description

- Map the blast radius: the module had exactly four consumers, and was absent from the `application/live` package facade, so no re-export sweep was needed.
- Delete `_censo_036_pull.py` and its test module.
- Remove the `PROVENANCE_SOURCE_CENSO_FILED_036` token, dead once its only two consumers went.
- Regenerate the api stubs, removing the orphaned stub and its toctree entry.
- Remove the `censal-pull` manager action, its runner, its year-span constant and its `_split_against_the_record` helper, whose sole consumer was that runner.
- Keep the 29 causa-de-presentación casillas and correct the header sentence that claimed their lifecycle mapping lived with the code that consumed it.

## Outcome

The register-based censal pull is gone. Modelo 036 is a declaración censal rather than a periodic return, so it never appears in a register of returns; a live authenticated walk confirmed it, returning zero 036 rows for every year from 2022 to 2026 while modelos 100, 303, 130, 111 and 390 all returned real filings in the same pass. The surface could only ever report that nothing was found.

The deletion also removed a write path that was wrong independently of the empty read. It emitted a fact at `censo.filed_on`, a path the user-profile schema does not declare, and stamped it with a provenance token absent from the schema's declared source enum. Both passed every gate, because `UserProfileFact.source` is a length-constrained string rather than that enum and nothing cross-checks a fact's path against the declared field set. Only the total absence of output kept either from reaching a profile. That escape is recorded as a finding in its own right, since it applies to every writer of a profile fact.

The operator-declared `censo.status` path is untouched and remains what the registry's profile-censo-status binding reads; the deleted module was only ever a second, broken writer to it.

Gates: ruff clean, api stub tree conformant with no drift, and the touched packages at 1031 passed. The type checker and the test suite both read the working tree, where a concurrent uncommitted edit to the manager-actions module still carries the removed block, so the single unresolved-import diagnostic there is a working-tree artefact and not a property of the committed tree, which carries zero references.

## Notes

The manager action shares its file with a large concurrent uncommitted change belonging to another work stream. It was landed through a staged-patch drive against a copy of the committed file, so the removal reached the index without the working tree being written; the concurrent edit stayed intact on disk throughout.

That drive was attempted once before and abandoned mid-flight. The shared index acquired eleven files belonging to another work stream between the pre-flight check and the apply, so committing the index would have swept them; the staged hunks were reversed out with the exact inverse of the apply, and nothing was committed. The retry closed the window by making the apply, the verification and the commit a single uninterruptible step rather than three.

Two items were deliberately left to the owner of the manager-actions file rather than taken here, and both have since landed. The concurrent on-disk copy of that module was anchored to the content preceding this removal, so committing it wholesale would have silently restored the deleted action and re-broken the import; its owner rebuilt against the committed content instead. The four orphaned locale keys were held for the same reason, since all four catalogues carried uncommitted concurrent work and the catalogue files have a known write race, and unreferenced keys are inert where the dead verb was not. The owner retired the keys and the stale docstring paragraph in one pass.

The Step's scope is therefore fully landed. Measured against a single pinned commit rather than across several: the removed action, its imports, the four locale keys and the docstring sentence describing the retired pull all read zero. That pinning matters here, because an earlier reading of this same question was taken against the working tree rather than the committed content and reported the keys retired while they were still committed, and a later pair of readings straddled the owner's commit. The state was moving faster than the checks; only a measurement pinned to one commit settles it.
