---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S53'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace calculation-source-connectivity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S53 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Test calculation revision roundtrip preserves source refs and ## Scope

- `src/aeat/application/modelo/test_source_mesh_revision_roundtrip.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Test calculation revision roundtrip preserves source refs

## Scope

- `src/aeat/application/modelo/test_source_mesh_revision_roundtrip.py`

## Description

- Add `test_source_mesh_revision_roundtrip.py` under the persistence-adapter tests, mirroring the sibling ledger-filing-evidence roundtrip.
- Build a `CalculationRevision` with a NON-EMPTY `source_provenance` tuple, every `CalculationSourceRef` field populated non-default, and push it through the real `EphemeralMasterKeyProvider` + SQLite + `CalculationRevisionCatalogueRepository` cycle; assert strict model equality on reload.
- Assert `source_provenance` is additive: stripping it yields an unequal model but the SAME content-addressed id (not part of the derivation).
- Add the anti-tautology proof: surgically blank a persisted `source_ref` in the decrypted on-disk payload, re-save, and assert `ValidationError` on load (the `min_length=1` gate bites).

## Outcome

The persisted source-mesh provenance survives the encrypted boundary with strict equality, and a corrupted payload is refused on load, so the roundtrip is non-tautological. Two tests, both green (`2 passed`).

## Notes

Placed under `adapters/persistence/profile/tests/` (the architectural home of the encrypted-boundary roundtrip and its sibling ledger-evidence proof) rather than the plan's suggested `application/modelo/` path, which lacks the encrypted-repository payload-corruption internals the anti-tautology proof requires and would violate the tests-under-tests-folder convention. This roundtrip needs no runtime schema provider, so it is unaffected by the modelo-131 peer-WIP registry state that blocks the S52 integration tests.
