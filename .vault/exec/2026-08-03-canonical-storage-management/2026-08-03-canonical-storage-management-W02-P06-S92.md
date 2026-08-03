---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:2aefd7ba3777b042fed55733c90bced0994b49d32c970e726acc0aa15f3e5eaf'
step_id: 'S92'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S92 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Decide whether the manuals fetcher's write to aeat_manuals_root is a scope-narrowing correction to the BUNDLED_RESOURCE escape reason, which currently states the application never writes there, or a new escape role naming the fetcher's write explicitly, since the module genuinely streams source.pdf and manifest.json to disk under that root and ## Scope

- `src/cadrumo/domain/manuals/_fetch.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Decide whether the manuals fetcher's write to aeat_manuals_root is a scope-narrowing correction to the BUNDLED_RESOURCE escape reason, which currently states the application never writes there, or a new escape role naming the fetcher's write explicitly, since the module genuinely streams source.pdf and manifest.json to disk under that root

## Scope

- `src/cadrumo/domain/manuals/_fetch.py`

## Description

- Confirm the fetcher's write target before deciding: `resolve_part_root` reads `aeat_manuals_root` directly, whose default is `bundled_path("corpus", "manuals")` -- the package's own `_data/corpus/manuals` tree under an editable install, unchanged before and after the decision.
- Confirm the decision already landed on a prior commit: add `ExternalPathRole.MAINTAINER_TOOLING_OUTPUT` and re-classify `aeat_manuals_root`'s `EXTERNAL_PATH_SETTINGS_FIELDS` entry from `BUNDLED_RESOURCE` to it, correcting the false "the application never writes there" reason to name the true tooling-write behaviour.
- Confirm this is a scope-narrowing correction, not a relocation: the write destination is byte-identical before and after; only the declared escape role and its reason text changed. `aeat_normatives_root` and `cadrumo_iva_catalogue_root` keep `BUNDLED_RESOURCE`, which stays honest for those two (read-only from every angle checked).
- Run the taxonomy, binding-gate, and fetch test suites to confirm the six-role escape set and the fetcher's real write path both stay green.

## Outcome

Decision was already implemented and committed ahead of this dispatch (`1463ae56b7`). Verified independently rather than trusted on the commit message alone: read `_fetch.py`/`_loader.py` to confirm the write target, confirmed `ExternalPathRole` carries the sixth `maintainer_tooling_output` member and the binding gate locks it, and confirmed no on-disk location changed. 50 tests passed across `test_storage_taxonomy.py`, `test_storage_binding_gate.py`, `test_fetch.py`. No relocation occurred; nothing further to change.

## Notes

No code changes required by this Step; verification and exec-record closure only.
