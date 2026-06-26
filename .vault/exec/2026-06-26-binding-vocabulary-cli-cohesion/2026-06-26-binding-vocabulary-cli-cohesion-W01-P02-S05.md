---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S05'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-vocabulary-cli-cohesion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Re-home _m232_row_bindings.py to a row-materialisation module name dropping the _bindings stem (e.g. _m232_row_materialisation.py) toward the domain row-model surface as one atomic relocation:m232-row-materialisation commit and ## Scope

- `update materialize_m232_related_party_rows and the single direct-submodule test import`
- `run dev.docs.apidocs scaffold to regen the API-stub (remove the orphan`
- `add the new stub) plus locale + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/domain/calculations/registry/_m232_row_bindings.py`
- `src/aeat/tests/test_storage_decimal_redaction_error_typing.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-home _m232_row_bindings.py to a row-materialisation module name dropping the _bindings stem (e.g. _m232_row_materialisation.py) toward the domain row-model surface as one atomic relocation:m232-row-materialisation commit

## Scope

- `update materialize_m232_related_party_rows and the single direct-submodule test import`
- `run dev.docs.apidocs scaffold to regen the API-stub (remove the orphan`
- `add the new stub) plus locale + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/domain/calculations/registry/_m232_row_bindings.py`
- `src/aeat/tests/test_storage_decimal_redaction_error_typing.py`

## Description

- Re-home the M232 related-party CLI-row materialiser out of the registry binding package to the domain modelos package, dropping the misleading `_bindings` stem; git records it as a rename of `_m232_row_bindings` to `_m232_row_materialisation`.
- Flip the module's registry imports (`CasillaObservation`, `CasillaId`, `RegistryValidationError`, `casillas_by_id`, `ModeloRevision`) from private submodule imports to the registry package facade, per the top-level-reexport rule, and switch the `Modelo232VinculadaRow` import to a sibling-package import.
- Update the one direct-submodule test import in the decimal-redaction error-typing test.
- Run apidocs scaffold to remove the orphan registry stub, add the modelos stub, and update both package toctrees for the m232 module only.

## Outcome

Landed as one atomic commit `relocation:m232-row-materialisation` (`844790e0b`); the re-home flips the prior registry-to-modelos back-edge to the established modelos-to-registry direction (the modelos package already imports registry symbols in production). collect-only clean (16461 baseline-equal), ruff clean, the m232 too-many-rows test green.

## Notes

The B1 file relocation is a public-surface change to the API-reference stub tree. The scaffold regenerates the whole tree, so it also surfaced an in-flight peer module rename (`_casilla_membership` / `_validate_source_outputs`) uncommitted in the shared worktree. The own-only `registry.rst` toctree delta was rebuilt HEAD-anchored to carry only the single m232 line removal, with zero peer markers staged; the untracked peer stubs the scaffold emitted were left unstaged for the peer. apidocs scaffold --check reports the registry package toctree stale, but that drift is peer-owned (their uncommitted module rename), not this B1 change.
