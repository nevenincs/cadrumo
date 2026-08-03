---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:16529692efeb97058c0b638d6bb32c06245de0e2cd3cee9be878541a73a8992f'
step_id: 'S25'
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
     The S25 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Collapse the twin reset-journal directory-name declaration onto the taxonomy member, gated by the existing parity pin rewritten to compare the application constant against the taxonomy rather than against a second constant and ## Scope

- `src/cadrumo/application/_config_reset_repository.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Collapse the twin reset-journal directory-name declaration onto the taxonomy member, gated by the existing parity pin rewritten to compare the application constant against the taxonomy rather than against a second constant

## Scope

- `src/cadrumo/application/_config_reset_repository.py`

## Description

- Add `StorageCategory.CONFIG_RESET_JOURNAL` to the core taxonomy: FIXED
  override policy (no dedicated settings field exists to relocate it
  independently of the storage root -- the same shape as `BUCKETS` and
  `ACTIVE_PROFILE_POINTER`), `UNBOUNDED_BY_DESIGN` lifecycle, `STATE`
  grouping, `consumer_module="application/_config_reset_repository.py"`.
- Re-point both prior standalone `CONFIG_RESET_JOURNAL_DIRNAME` constants
  (`application/_config_reset_repository.py` and `adapters/persistence/
  storage/_storage_path_definitions.py`) to read `storage_location(
  StorageCategory.CONFIG_RESET_JOURNAL).subpath`.
- Rewrite the parity-pin test (`test_persisted_format_enrollment.py::
  test_application_owned_journal_name_agrees_with_the_registry`) to compare
  the application constant against the taxonomy directly, not against the
  second (adapter-layer) constant it previously checked.
- Confirmed byte-identical resolution ("reset-operations") for both
  constants and the taxonomy read.
- Found and fixed fallout from the existing suite (not by inspection): the
  directory-agreement gate's one pre-existing named exemption for
  `config_reset_journal` became stale the moment its run matched a declared
  subpath, and its own anti-rot test caught it. Emptied the exemption dict
  (kept as a live, documented dict rather than deleted) and updated the
  module docstring.

## Outcome

`CONFIG_RESET_JOURNAL_DIRNAME` now has exactly one declaration
(`StorageCategory.CONFIG_RESET_JOURNAL`'s subpath), read from two sites
rather than declared twice. This is the taxonomy member `S108` needs to
exist before it can collapse the application-layer duplicate onto it.
Full storage/core/application suite re-run clean: 1848 passed (one
pre-existing, environment-dependent failure in `test_config_reset.py`
confirmed unrelated by running it against a `git archive` extraction of the
pristine pre-change HEAD, where it fails identically).

## Notes

None. No skipped work, no scaffolds left in code. Landed together with S64
in commit 8c94b7937b.
