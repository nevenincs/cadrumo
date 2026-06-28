---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S14'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement Tier-A seed importers - IATE TBX download (es/hu/en, tax/law/finance domains, reliability at least 3) and UBTERM fiscalitat (ca/es/en, CC BY 3.0), EuroVoc labels only after licence verification - stamping seed_provenance with the required attribution on every seeded value and excluding all ND/NC/unlicensed sources (ADR D9)

## Scope

- `aeat.terminology seed importers + licence notes`

## Description

Implements ADR **D9** (Tier-A external seeding with provenance stamping and
ND/NC/unlicensed exclusions). The durable deliverable is the importer
infrastructure (`src/aeat/terminology/_seed_import.py`); the actual
third-party export files are placed later at an operator-chosen path.

**Parsed intermediate (strict pydantic):** `SeedTerm` (language, label,
`term_status`, optional source `short_description`) grouped into a `SeedEntry`
(`source`, `spanish_key`, `terms`, optional `source_entry_id`). `SeedSource` is
a closed StrEnum with Tier-A members (`IATE`, `UBTERM`, `EUROVOC`) and the
excluded members (`TERMCAT_OBERTA`, `TERMCAT_UOC_IATE`, `RAE_DPEJ`,
`MICROSOFT_TERMINOLOGY`) present so the gate can refuse them by name.

**Parsers:** `parse_iate_tbx(path, min_reliability, domains)` reads the TBX
`termEntry / langSet / tig` three-tier shape, applies the reliability floor
(>= 3) and the subject-field allow-set (tax/law/finance), and maps termType
fullForm->preferred / synonym->admitted. `parse_ubterm_csv(path)` reads the
trilingual ca/es/en CSV (with an optional `definition_es` gloss). Both refuse
a missing/malformed file rather than returning empty.

**Licence gate (hard, structural):** `assert_source_ingestible(source)`
refuses every excluded source with its reason ("CC BY-ND ... reformatting into
Handbook records is a derivative", etc.) and refuses EuroVoc until
`_EUROVOC_LICENCE_CONFIRMED` (held False). `source_attribution` re-asserts
ingestibility before returning the licence-required attribution string. The
`SeedEntry` model_validator refuses any source with no attribution mapping;
`SeedProvenance.attribution` is `min_length=1` (defence in depth). The `seed`
CLI verb surfaces `SeedSource` as a Choice and refuses excluded sources at the
boundary.

**Mapper:** `apply_seed_entries(entries, ...)` matches each entry's
`spanish_key` (case-folded) against an existing concept's `es` `preferred`
label and fills ONLY gaps -- a new language section gets the seed's preferred
term + a source gloss (or the source label, never invented prose) as its
required `short_description`; an existing section gains admitted aliases;
`seed_provenance` is stamped (source + attribution + `source_entry_id`) when
the concept carries none. Curated values are never overwritten (msgmerge
PRESERVE); lifecycle is never touched (a seeded draft stays draft -- a seed
never satisfies approved-completeness). Every write re-validates the whole tree
through `default_handbook_validators()` and refuses an invalid result.

A `seed` verb was added to the `python -m aeat.terminology` CLI mirroring the
S12 curation-verb / locales CLI-is-authoritative discipline.

## Outcome

Landed (one atomic commit, see Notes for hash). 21 new real-behaviour tests
(no mocks; parse the committed fixture exports, apply to a controlled fixture
tree); full terminology suite 93 passed (72 existing + 21 new); ruff / ruff
format / ty / pyright all clean; collect-only clean.

**Sources fetched vs fixture-proved (network reality):**
- **UBTERM** fiscalitat page fetched (209 KB, "CC BY 3.0" confirmed on the
  page) BUT it is a search/browse HTML interface with no bulk
  TBX/CSV/zip download link -- per-term scraping would be fragile and the
  brief forbids fabricating committed fragments, so UBTERM is proven against a
  committed CSV FIXTURE. Full ingest runs when a real CSV export
  (columns `es,ca,en,definition_es`) is placed and passed to `seed ubterm`.
- **IATE** TBX is a large bulk zip not fetchable here; proven against a
  committed TBX FIXTURE. Full ingest runs when the downloaded TBX is passed to
  `seed iate --min-reliability 3 --domain finance ...`.
- **EuroVoc** download-page licence COULD NOT BE VERIFIED in this environment
  (the Publications Office page returned 0 bytes). Per ADR D9 EuroVoc is
  ingested ONLY after licence verification, so it is SKIPPED:
  `_EUROVOC_LICENCE_CONFIRMED = False` and the gate refuses it with
  "download-page licence not yet verified". Flipping that flag is a deliberate
  reviewed change paired with the confirmed attribution.

**No seeded production fragments were committed** (the bundled tree is
byte-unchanged); seeded concept fragments must come from genuinely-fetched data
or be omitted -- never invented. The fixture run proves a controlled concept
gains 2 real languages (en + hu from IATE) with provenance stamped.

**Loader / validators still pass and re-scaffold is a no-op:** the bundled
tree is unchanged so `default_handbook_validators()` passes over it
(`test_bundled_handbook_stays_loader_valid_after_step`) and
`python -m aeat.terminology scaffold --check` reports `0 new drafts, 0 retired,
95 unchanged`. The PRESERVE contract on a seeded tree is proven by
`test_re_scaffold_after_seeding_is_a_no_op` (seeded values survive a
re-scaffold byte-for-byte).

Test names (`test_seed_import.py`): `test_excluded_source_is_refused`
(parametrised over the 4 excluded sources), `test_eurovoc_refused_until_licence_verified`,
`test_tier_a_source_is_ingestible_with_attribution`,
`test_excluded_source_has_no_attribution`,
`test_parse_iate_tbx_filters_and_maps_terms`,
`test_parse_iate_tbx_without_domain_filter_keeps_reliable_entries`,
`test_parse_ubterm_csv_reads_trilingual_rows`,
`test_parse_ubterm_csv_rejects_missing_es_column`,
`test_apply_seeds_fills_missing_languages_and_stamps_provenance`,
`test_apply_seeds_does_not_overwrite_curated_es`,
`test_apply_seeds_never_auto_approves_a_draft`, `test_apply_seeds_is_idempotent`,
`test_apply_seeds_reports_unmatched_keys`,
`test_seeded_tree_stays_loader_valid_and_dry_run_does_not_write`,
`test_re_scaffold_after_seeding_is_a_no_op`,
`test_bundled_handbook_stays_loader_valid_after_step`,
`test_seed_entry_refuses_unattributed_source`.

## Notes

- **EuroVoc licence-verification outcome:** UNVERIFIED in this environment
  (page unreachable) -> SKIPPED per ADR D9. The importer is wired but gated off
  behind `_EUROVOC_LICENCE_CONFIRMED = False`.
- **Sources skipped + why:** EuroVoc (licence unverifiable); TERMCAT
  Terminologia Oberta (CC BY-ND -- derivatives forbidden); TERMCAT/UOC
  Catalan-IATE export (no confirmed licence); RAE DPEJ (no download); Microsoft
  Terminology (no redistribution). All are refused by the licence gate.
- **Fixtures** under `src/aeat/terminology/tests/fixtures/`
  (`iate-sample.tbx`, `ubterm-sample.csv`) are clearly labelled hand-authored
  structural samples, NOT real bulk data.
- **`__init__.py`** gained the seed-import re-exports (top-level surface);
  `cli.py` gained the `seed` verb. The bundled `_data/terminology/concepts/`
  tree is untouched.

