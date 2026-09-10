---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:5bfac5e40ee9836659328a154369dc1f3e47a76394b53758c63fb136f0f96df7'
step_id: 'S51'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [M | opus-medium] Decide where an inherited row's generated export references are written, because publication refuses without an answer. The real declared-versus-generated comparison is not in any loader caller — it sits one call deeper, where the generated layout's addressed casillas are differenced against the identifiers read from the raw declaration files on disk. Under delta authoring a layout addressing an INHERITED casilla finds no file to write into, and publication fails loudly. That is the right failure mode, but it needs a decision rather than a discovery. Coordinate with the generator lane, which owns that module and has offered to retire it. Proof: a migrated modelo publishes, or refuses for a stated reason that is not this one.

## Scope

- `dev/registry/pipeline`

## Changes

- `M` `dev/registry/pipeline/candidate_staging.py`
- `M` `dev/registry/pipeline/cli.py`
- `A` `dev/registry/tests/test_delta_target_publication.py`
- `verify:` `uv run --no-sync pytest test_delta_target_publication.py` -> `pass` (5)
- `verify:` `uv run --no-sync pytest test_delta_target_publication.py` against the HEAD `cli.py` and `candidate_staging.py` -> `fail` (4 of 5)
- `verify:` `uv run --no-sync pytest test_delta_target_publication.py test_continuity_witness_staging.py test_isolated_edition_staging.py test_generated_tree_cli.py test_generated_export_trees.py test_m303_generated_envelope_proof.py test_export_tree.py test_generated_export_tree_validation.py` -> `fail` (3 pre-existing, 191 passed)
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `verify:` `uv run --no-sync ruff check`, `ruff format --check`, `ty check` on the three files -> `pass`

## Notes

- Map. The raw-file comparison is the `missing` set in `write_generated_casilla_export_refs` (`dev/registry/pipeline/_casilla_export_refs.py`), which scans the revision's `casillas/*.toml` for `id` lines. Its callers are `cli._render_candidate` (check of an absent tree and republish, on the candidate), `cli._publish` (on the candidate, before cutover) and `_tree_publication._write_export_refs`, called by `publish_validated_generated_export_tree` AFTER the export directory swap and again by `_recover_interrupted_publication`. The writer exists because the loader requires the back-reference two ways: `_validate_exports.py` (field not declared by casilla), `export.py` (the same at runtime), `_validate_record_sections.py` and `validate_references.py` (ref names a field), and `validate_revision_identity.py` (one owner per field). The loader's inheritance (`_inherit_casillas`) copies the predecessor's `export_refs` onto inherited rows verbatim, and those ids embed the edition (`m232-2016...`, `m210-2026...`).
- Decision. There is no write path for `export_refs`. The loader derives them from the edition's layout back-pointer, the writer and every caller are deleted, and the comparison that remains is the loader's existing unknown-casilla check on the materialised edition. This Step does not edit either peer module.
- What S14 must build, atomically: derive `export_refs` per casilla from the edition's fixed-width layout fields whose endpoint casilla is that row, in layout emission order, excluding binding record-template fields (the exemption in `_validate_exports.py`), before reference, identity and export validation run. It must derive rather than inherit on inherited rows, and refuse an authored `export_refs` key. It must strip every authored line from the corpus in the same change and prove the result byte for byte against today's values. It must delete `_casilla_export_refs.py`, `_tree_publication._write_export_refs` and its recovery call, both writer calls in `cli.py`, the new pre-write refusal in `cli.py`, the writer tests in `test_export_tree.py`, and the `_remove_candidate_export_refs` defect injection in `test_generated_tree_cli.py`. The two-way checks then become tautological and go too.
- What breaks in between. If the writer is removed before derivation lands, every check and publication fails on field-not-declared. If derivation lands while the writer stays, every publication writes an authored value the loader refuses. Neither half lands alone.
- Sequencing hazard, measured on the probe. Once inherited rows cite the successor's source references (S13), a delta target's absent-tree check passes, and before this change publication then swapped the export tree in live and only afterwards refused in the writer. The refusal added to `cli.py` compares the rendered layout's addressed casillas against the materialised target edition, and refuses before any write when an addressed casilla is undeclared or inherited. It is transitional and S14 deletes it.
- Proof on modelo 210, migrated in a temporary registry (`2026-y-siguientes` names `2025` and drops its 26 rows restated unchanged; it states 8 and materialises to 34), through the real staging, render, validation and publication functions. Candidate staging produces the complete 34-row edition naming no predecessor, and a delta whose predecessor was removed is refused. With the existing tree, check refuses on the loader's field-not-declared rule for inherited casillas (S14's reason), and no target byte changes. With an absent tree, validation refuses because inherited rows cite `aeat-dr-210-2022` outside the 2026 window (S13's reason). With an absent tree and those citations aligned, check and publish refuse before any write with the inherited-casilla reason, and the target export tree stays absent. No run publishes, and none refuses because it found no file to write into.
- Candidate staging drops `export_refs` from inherited rows only. Stated rows keep theirs, and a target that states every row stages byte for byte as before.
- Label carry-over is not exercised here. Modelo 210's catalogue already holds successor-keyed labels for every row, and the carry-over gap recorded under S56 still applies to a genuinely migrated edition.
- The three failures are modelo 184's seeded-lineage continuation refusals (`test_absent_tree_is_validated_then_published_through_the_canonical_authorities` and two tests in `test_generated_export_tree_validation.py`). They reproduce identically with the HEAD `cli.py` and `candidate_staging.py`.
- The reviewer persona could not be launched from this session, so the review is still outstanding.

- The reviewer persona could not be launched; the orchestrating session reviewed the decision and the diff. The decision is no write path: S14 derives `export_refs` and deletes the writer in one change, since neither half lands alone. Candidate staging materialises a delta target. A temporary pre-write refusal guards publish until S14. Re-run: the delta-target, witness and isolated staging tests pass; ruff and ty clean. Peer agreement from REGISTRY-TYPE is still awaited before S14 edits their modules.
