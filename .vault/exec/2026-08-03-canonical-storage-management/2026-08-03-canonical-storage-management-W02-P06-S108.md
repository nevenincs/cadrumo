---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:0dd46aeb1654e032aaf0cc1b4752def3e6e74a652218f34091ce7ea3b374ba60'
step_id: 'S108'
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
     The S108 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Delete the duplicate CONFIG_RESET_JOURNAL_DIRNAME literal in the config-reset repository and re-point its journal-directory join onto the already-declared config_reset_journal grammar, closing the gap the new directory-grammar agreement gate found: the repository joins its own reset-operations constant onto the raw storage root, bypassing storage_path entirely, even though StoragePathDefinition already declares this exact shape and ## Scope

- `src/cadrumo/application/_config_reset_repository.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Delete the duplicate CONFIG_RESET_JOURNAL_DIRNAME literal in the config-reset repository and re-point its journal-directory join onto the already-declared config_reset_journal grammar, closing the gap the new directory-grammar agreement gate found: the repository joins its own reset-operations constant onto the raw storage root, bypassing storage_path entirely, even though StoragePathDefinition already declares this exact shape

## Scope

- `src/cadrumo/application/_config_reset_repository.py`
- `src/cadrumo/adapters/persistence/storage/_storage_path_definitions.py`

## Description

- Verification only. `StorageCategory.CONFIG_RESET_JOURNAL` was created and
  both `CONFIG_RESET_JOURNAL_DIRNAME` declarations re-pointed onto it in the
  earlier `S25` landing (not this Step's own work).
- Confirm no import from `adapters` in `application/_config_reset_
  repository.py`: this Step was twice previously declined because closing
  it would have meant `application` importing `adapters` to make the row
  pass, before `S25` created the core member that removes that pressure.
  Grep confirms clean.
- Confirm no duplicate literal remains: both declarations now read
  `storage_location(StorageCategory.CONFIG_RESET_JOURNAL).subpath`.
- Add the second file citation to the Step's scope
  (`_storage_path_definitions.py`, where `StoragePathDefinition`'s own
  `config_reset_journal` grammar entry lives), which the original row
  omitted.
- Re-run `test_persisted_format_enrollment.py`,
  `test_storage_path_directory_agreement_gate.py`, and
  `test_config_reset_repository.py`: 27 passed.

## Outcome

Already satisfied; no reimplementation performed. The layering concern that
blocked this Step twice is gone because the taxonomy member now exists in
`core`, not because `application` reaches into `adapters`.

## Notes

None. No skipped work, no scaffolds left in code.
