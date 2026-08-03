---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:0d7d297474c8d8696d1156e98053d39f98008e458a61066fb8b10b7e9909e27d'
step_id: 'S64'
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
     The S64 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Delete the fifth unpinned buckets literal in the journal repository's containment check and read the taxonomy member instead, a copy found after the plan was authored and covered by no existing row, gated by the journal repository suite plus the name-unification gate seeing the module and ## Scope

- `src/cadrumo/application/_journal_repository.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Delete the fifth unpinned buckets literal in the journal repository's containment check and read the taxonomy member instead, a copy found after the plan was authored and covered by no existing row, gated by the journal repository suite plus the name-unification gate seeing the module

## Scope

- `src/cadrumo/application/_journal_repository.py`

## Description

- Determined which kind of literal this is before touching it, per the R14
  discrimination: `_validate_existing_root`'s `buckets_root` is production
  safety code checking that the journal root does not nest under bucket
  storage, not a test measuring an accessor's correctness. If the taxonomy
  ever renamed the bucket container, the check must track the real location
  or its own guarantee silently rots -- the opposite of the sanctioned R14
  case (`test_every_derived_output_dir_roots_under_storage_root`), which
  must NOT route through the accessor because doing so would make it assert
  the accessor equals itself.
- Re-point `buckets_root` to `storage_location(StorageCategory.BUCKETS).
  relative_path()` joined onto `self._storage_root`, replacing the fifth
  hand-typed `"buckets"` literal.
- Confirmed byte-identical resolution (`Path("buckets")`).
- Extend the core name-unification gate (`test_storage_taxonomy_name_
  unification.py`) to cover `_journal_repository.py`, renaming its test
  function since the module set is no longer core-only, and documenting why
  an application-layer module belongs beside the core cases (plain drift,
  not the same hexagonal-direction constraint the other four cases share).
  Mutation-proven against a synthetic pre-fix snippet rather than by
  mutating the shared production file in place.

## Outcome

`JournalRepositoryBase._validate_existing_root` (shared by both the
config-reset and profile-export journal repositories) now reads the
bucket-container name once. Full storage/core/application suite re-run
clean: 1848 passed (one pre-existing, environment-dependent failure in
`test_config_reset.py` confirmed unrelated).

## Notes

None. No skipped work, no scaffolds left in code. Landed together with S25
in commit 8c94b7937b.
