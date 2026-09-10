---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:d1fb06a027523baf6aa11627f5aceabef4fecf54ab6dd55bf78bcd1ab9b57025'
step_id: 'S56'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

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
- `verify:` `uv run --no-sync pytest test_isolated_edition_staging.py` with the catalogue write removed -> `fail` (label parity)
- `verify:` `uv run --no-sync pytest test_generated_tree_cli.py` -> `fail` (1 not caused by this change)

## Notes

- `test_absent_tree_is_validated_then_published_through_the_canonical_authorities` fails on modelo 184 seeded-lineage continuation refusals, identically with the HEAD `cli.py` swapped in; it predates this change. An earlier run of the same file also failed five tests on modelo 100 strict continuity drift while another session held 368 uncommitted modelo 100 casilla files; none of the tracebacks passes through the staging code.
- Casilla labels resolve from the packaged catalogue by modelo, edition and casilla id, not from the registry tree. A staged delta therefore carries a staged catalogue: a copy of the source catalogue with each inherited row's origin text written under the row's own occurrence key through `LocaleManager.set_locale_values`, in each locale where the row has no text of its own. Its labels resolve through `override_locales_root` at the staged catalogue. The copy is written only for a delta; no staged catalogue is read today, because the published-layout witness reads export layouts only.
- `withdrawn_review_status` is not surfaced by staging. The staged tree is a temporary check witness that publishes nothing and is discarded with its temporary root; the withdrawn review claim is already absent from the table it is written from.
- The pre-existing unsorted `record_drift_dispositions` import in `cli.py` was reordered to clear ruff I001.
- The reviewer persona could not be launched from this session, so the review is still outstanding.

- The orchestrating session reviewed the entry point and staging diffs against the ADR and committed them: materialisation runs before the copy, a missing predecessor is refused, and no dev import reaches an underscore module in `src`. Re-run: 9 passed, `registry verify` exit 0, ruff and ty clean. The staged label carry-over first waited on the `dev.locales.manager` import break, which 2215d0a484 fixed.

- The label carry-over landed in fa67c4c2bf. The orchestrating session reviewed it against the ADR: inherited rows get the stating edition's text only where the row has none, so an edition's own label wins, and an edition that states every row is unchanged. Re-run: 15 staging and entry-point tests passed, including the four-locale parity test, which fails when the catalogue write is disabled.
