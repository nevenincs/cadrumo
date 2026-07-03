---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S17'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-ports-inversion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-07-02-arch-remediation-ports-inversion-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Relocate the modelos runtime repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters runtime_repository entry and ## Scope

- `src/aeat/domain/modelos/_runtime_repository.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Relocate the modelos runtime repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters runtime_repository entry

## Scope

- `src/aeat/domain/modelos/_runtime_repository.py`

## Description

- Create `src/aeat/adapters/persistence/profile/_modelo_runtime.py` holding both `secure_objects_for_modelo_bucket` and the pure `resolve_modelo_repository_bucket_id`, with a module-level same-layer import of `secure_object_repository_for_bucket` from `..storage`.
- Delete `src/aeat/domain/modelos/_runtime_repository.py` and drop both helpers from the `domain.modelos` `__init__` facade import and `__all__`.
- Retarget the five modelos persistence adapters (`participation_index`, `modelos_work_units`, `modelos_verification_reports`, `modelos_filing`, `modelos_calculation`) to import both helpers from the sibling `._modelo_runtime`.
- Relocate the helper test to `adapters/persistence/profile/tests/test_modelo_runtime.py` (retagged `hex_persistence_adapter`), importing domain and storage symbols through their public facades.
- Remove the dead `domain.modelos._runtime_repository -> adapters.persistence.storage` layered ignore and the two stale relocated-test ignores from `.importlinter`, and drop the retired allowlist edge from `test_lazy_import_policy`.
- Regenerate the apidocs stub tree for the moved module.

## Outcome

- The last production `domain -> adapters` edge in the modelos surface is removed; the storage factory now lives in the adapter beside the five repositories it serves, so its storage coupling is a normal same-layer import with no deferral and no ignore.
- Landed as a single atomic commit `8175c98e9a` (15 files; the helper test tracked as a rename).
- Owner-scoped gates green: full `collect-only` clean, `test_importlinter_ledger` (all three subtests), `test_repository_sensitivity_class`, `test_runtime_repository_enrollment`, `test_docstring_core_struct_links`, the relocated `test_modelo_runtime`, and the modelo repository roundtrip suites on real encrypted SQLite (calculation, filing, participation, verification, secure-storage, runtime-attached) all pass. `ruff check`/`format` clean; apidocs `scaffold --check` conformant.

## Notes

- Both helpers were co-located in the adapter rather than splitting them: no domain production code consumes either, and the pure bucket-id resolver is itself repository plumbing, so a single sibling import source for the five adapters is the cleaner layer story.
- `test_lazy_import_policy`, `test_import_hygiene_gate`, and the `AEAT layered architecture` import-linter contract remain red at HEAD from unrelated concurrent campaigns (LLM run-telemetry, amendment-kind, bienes-inversión advisory); none of the failing edges reference the relocated module, and this change removes edges from all three surfaces rather than adding any. Left red and attributed to their owning campaigns.
- Closes plan step W04.P09.S17 only — one leaf of register item D2. D2 also requires the filing-repositories wave (`domain/filing/_repository.py`, `_complementaria_repository.py`, `_runtime_repository.py`; `.importlinter` pins 686/687/704) and the attachments verify (W02.P06.S08); the graph-wide zero-domain-to-adapters check remains the definitive D2 gate.
