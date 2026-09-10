---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:3c97e2bca5aa32e21982af79b07bcad266d65377ea59af24f0cb26571752655d'
step_id: 'S56'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [M | opus-medium] Fix isolated staging, which deletes exactly what a delta edition needs. The publication path stages a single edition by copying the modelo and removing every sibling directory, so staging a migrated successor deletes its predecessor: the staged tree then declares a predecessor that does not exist, and either the forest rule refuses it or it materialises to only its stated rows and presents a partial edition as complete. The function exists to create isolation, and isolation is precisely what an inheriting edition cannot survive. Two options: keep the ancestor chain when staging, or materialise before staging. The owning lane prefers materialise-before-staging and the reason is sound — it makes the staged thing a complete edition by construction, rather than depending on every downstream check knowing it is looking at a fragment. Proof: a migrated multi-edition modelo stages and validates in isolation, and a staged delta whose predecessor was removed is refused rather than silently thinned.

## Scope

- `dev/registry/pipeline/cli.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/edition_materialisation.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_edition_materialisation_entry_point.py`
- `M` `dev/registry/pipeline/cli.py`
- `A` `dev/registry/tests/test_isolated_edition_staging.py`
- `verify:` `uv run --no-sync pytest test_edition_materialisation_entry_point.py test_isolated_edition_staging.py` -> `pass`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `verify:` `uv run --no-sync ruff check`, `ruff format --check`, `ty check` on the four files -> `pass`
- `verify:` `uv run --no-sync pytest test_generated_tree_cli.py test_generated_export_trees.py test_revision_edition_materialisation.py test_revision_label_inheritance.py` -> `fail` (1 pre-existing)

## Notes

- `test_absent_tree_is_validated_then_published_through_the_canonical_authorities` fails on modelo 184 seeded-lineage continuation refusals, identically with the HEAD `cli.py` swapped in; it predates this change.
- Label carry-over is not landed; the staged delta is not yet a complete edition. Casilla labels resolve from the one packaged catalogue by modelo, edition and casilla id, not from the registry tree, so a staged full copy loses the origin-edition fallback key the live load adds for inherited rows. Typed equality against the live edition holds with only that key removed.
- The designed carry-over copies the source catalogue and writes each inherited row's origin text under its own occurrence key, per locale where the row has none, through `LocaleManager.set_locale_values`; readers resolve it through `override_locales_root`. It is blocked because `dev.locales.manager` is unimportable at HEAD: `dev/locales/_registry_scanner.py` imports `profile_schema_locale_keys`, which commit `b460bd8c41` removed from `src/cadrumo/domain/user_profile/labels.py`. It was parked unapplied rather than leave `cli.py` failing at import.
- `materialise_edition` carries `label_origins` for that carry-over.
- The pre-existing unsorted `record_drift_dispositions` import in `cli.py` was reordered to clear ruff I001.
- The reviewer persona could not be launched from this session, so the review is still outstanding.

- The orchestrating session reviewed the entry point and staging diffs against the ADR and committed them: materialisation runs before the copy, a missing predecessor is refused, and no dev import reaches an underscore module in `src`. Re-run: 9 passed, `registry verify` exit 0, ruff and ty clean. The Step stays OPEN for the staged label carry-over, which is blocked on the `dev.locales.manager` import break.
