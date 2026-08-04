---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:c015c3cf09e21d965a8dc5801db2f903ce401b454254e2b2b1bde4558d82c495'
step_id: 'S77'
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
     The S77 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Re-express each pins-by-design test so it still defends its original on-disk-name property against the taxonomy's resolved value rather than degenerating into an accessor-equals-itself tautology, starting with the five master-key and keystore entries the provenance gate still carries as pending debt and ## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/tests/`
- `src/cadrumo/adapters/persistence/storage/bucket/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-express each pins-by-design test so it still defends its original on-disk-name property against the taxonomy's resolved value rather than degenerating into an accessor-equals-itself tautology, starting with the five master-key and keystore entries the provenance gate still carries as pending debt

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/tests/`
- `src/cadrumo/adapters/persistence/storage/bucket/tests/`

## Description

- Verification only for the Step's literal target. Confirmed
  `PENDING_ENROLLMENT` in `test_storage_provenance_gate.py` -- the specific
  "provenance gate pending debt" the row names -- is now the empty tuple
  `()`. `git log` on that file traces the closure to a commit re-anchoring
  six keystore-adjacent pins in `test_master_key_file_fallback.py` to
  `bucket_dek_path` (the real write-path function), applying exactly the
  discrimination this Step asks for: a bare accessor swap would have made
  the two `not exists()` assertions in that file trivially satisfied by an
  accessor aimed anywhere production never writes, so a two-independent-
  route cross-check (declared member vs. write-path function) was used
  instead, with the docstring stating the leaf name is deliberately NOT
  independently confirmed -- only the directory is under independent guard.
  Mutation-proven in that landing (pre-fix nested layout diverges the two
  routes; the healthy layout agrees).
- Confirmed the two `bucket/tests/` files the Step also names already carry
  an explicit R14 declaration in their module docstrings:
  `test_keystore_paths.py` ("the literal is the independent oracle. Do not
  migrate it to the accessor") and `test_layout.py` ("A change to a
  declared subpath should red the literal assertions. Do not migrate them
  to the accessor").
- Re-ran `test_storage_provenance_gate.py`,
  `test_master_key_file_fallback.py`, `test_keystore_paths.py`,
  `test_layout.py`: 73 passed.
- Surveyed the rest of `master_key/tests/` for the same literal shape
  (`master.key`/`master.kdf`/etc as bare string constants) beyond the five
  already-closed entries: `test_master_key.py`,
  `test_master_key_kdf_salt.py`, and `test_passphrase_failclosed.py` each
  carry one or more. None of these sat in `PENDING_ENROLLMENT` (that table
  is scoped to joins onto the STORAGE ROOT specifically; these join a local
  `tmp_path`-derived scratch directory, outside that gate's detection
  entirely) and none are among the two already-declared `bucket/tests/`
  files. They are a distinct, larger literal-vocabulary burndown the
  provenance gate's own docstring names explicitly as out of its scope
  ("that is literal vocabulary, not join provenance... Extending it across
  the test corpus is its own burndown") -- the same burndown `S78` scopes
  at "roughly 108 files". Left untouched: closing this Step's literal
  scope does not license silently absorbing that separate, much larger
  Step.

## Outcome

The Step's stated subject -- the five master-key/keystore entries the
provenance gate carried as pending debt -- is fully closed, not by this
Step's own edit but by a prior commit applying the exact discrimination
this Step asks for. No further master_key/tests/ or bucket/tests/ literal
site was migrated or left pinned by this Step; the remainder found in
`master_key/tests/` belongs to the separate test-corpus burndown (`S78`),
not to this Step's narrower, named scope.

## Notes

None. No skipped work in the Step's own scope, no scaffolds left in code.
The broader `master_key/tests/` literal survey is recorded here as a
finding for `S78`, not treated as this Step's own remaining work.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
