---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S17'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement the typed chunk-to-target resolution map: registry casilla fragments resolve to their projected records, legal catalogue entries and corpus HTML to the legal grounding surface anchors, src/aeat modules to generated API stubs, docs sources to built page anchors, CLI modules to the generated CLI reference

## Scope

- `unresolvable hits are dropped and reported`
- `never shipped half-mapped (ADR D6)`
- `dev docs terminology compiler`

## Description

Implements ADR **D6** ("output wrangling is a typed transformation layer")
plus the unified-index reconciliation flagged in the S15/S16 handoffs. Two new
modules under `dev/docs/terminology/`:

`_unified_record.py` -- the unified `SearchRecord` (strict frozen pydantic):
`id`, `kind`, `tier` (`RankingTier`: term | navigation | fulltext), `title`,
four-language `descriptions`, `target` (URL/anchor), `ranking_weight` (`[0,1]`),
and typed `SearchRecordMetadata` (kind-specific provenance: concept_id/domain/
lifecycle, modelo/number/segmento/source_revisions, command_path/registry_key/
option_names, plus legal_refs/source_refs). `to_search_record` is the uniform
funnel: it dispatches any of the four kind records (CasillaSearchRecord,
CliSurfaceRecord, CliOptionRecord, ConceptCardRecord) into ONE homogeneous
shape, deriving the per-kind id/title/target and carrying the grounding refs.

`_resolution.py` -- the chunk-to-target resolution map: `ChunkHit`
(path + line range + score) resolves through `TargetResolver` to a
`ResolvedTarget` (typed `GroundingSurface` + unified `SearchRecord`) or a
`DroppedHit` (typed `DropReason` + detail). `resolve_chunk_hits` batches and
partitions resolved from dropped. The resolver builds its indices once from
the validated authority (casilla records by modelo; the legal `corpus_ref`
reverse index), so a batch resolves without re-projecting per hit.

## Outcome

Landed (one atomic commit, see Notes for hash). 24 new real-behaviour tests
(15 resolution + 9 unified-record); full subtree 50 passed (S15 12 + S16 14 +
S17 24). ruff / ruff format / ty clean; collect-only clean.

**Unified SearchRecord shape:** `id` (stable per-kind, e.g. `concept:prorrata`,
`casilla:303:01`, `cli:ledger.add`, `legal:ley-37-1992:art-104`,
`code:aeat.foo.bar`, `page:how-to/x`), `kind`, `tier`, `title`,
`descriptions: dict[OutputLanguage, str]` (es invariant), `target`,
`ranking_weight`, `metadata: SearchRecordMetadata`. Funnel proven: all four
kinds serialise to the identical field set (`test_all_kinds_serialise_to_the_same_shape`)
and to JSON (the injection payload form).

**Resolution-map path→target rules (all five grounding surfaces):**
- `src/aeat/_data/registry/.../casillas/*.toml` -> CASILLA (modelo from path
  -> the modelo's projected casilla records).
- `.../disenos_registro/modelo_<m>/.../*.extracted.md` -> CASILLA (Diseno is
  the casilla-to-field authority).
- `.../corpus/normatives/.../*.extracted.md` -> LEGAL: strip `.extracted.md`,
  map to the `corpus/...`-rooted path, reverse-look the legal `corpus_ref`
  index -> the legal id carrying the BOE permalink + `#aN` article anchor
  (verified: the resolved target == the catalogue's permalink, with `#a104`).
- `src/aeat/_data/registry/aeat/legal/*.toml` -> LEGAL: scan the file's
  `[legal."<id>"]` headers, cross-check against the validated catalogue, take
  the first known id as the representative legal-grounding target.
- `src/aeat/**/*.py` -> CODEBASE: `aeat.<dotted.module>` -> `api/<dotted>.html`
  (the apidocs stub-naming convention; `__init__.py` -> package stub).
- `docs/cli/<family>.rst` -> CLI: the generated CLI-reference family page
  `cli/<family>.html` (reaches the CLI surface WITHOUT the live CLI walk).
- `docs/**/*.md|*.rst` -> DOCS: the built page `<rel>.html`.
- DROPPED + REPORTED: an unknown path (`UNKNOWN_PATH`), a test/fixture/scratch
  path (`EXCLUDED_SURFACE`), or a matched-rule-but-absent entity
  (`NO_TARGET_ENTITY`, e.g. a casilla path for an unprojected modelo). Never
  shipped half-mapped (anti-tautology test: a junk path MUST be reported).

**Ranking-weight normalisation rule (ADR D5 ordering):** per-kind base weight
concept=1.0 > cli=0.8 > casilla=0.7 > page=0.5 (term cards first, navigation
second, full text third). A sweep score modulates WITHIN `[base*0.5, base]` so
tier ordering is preserved: the worst-scored concept (0.5) still ranks at or
above the best-scored page (0.5). A record with no sweep score keeps its base.
Scores are clamped to `[0,1]`. Proven by
`test_normalisation_preserves_tier_ordering_under_score`.

Test names: resolution (`test_resolution.py`, 15) --
`test_casilla_toml_resolves_to_the_casilla_surface`,
`test_diseno_sidecar_resolves_to_the_casilla_surface`,
`test_normatives_sidecar_resolves_to_the_boe_article_anchor`,
`test_normatives_target_matches_the_catalogue_permalink`,
`test_legal_toml_resolves_to_a_legal_target`,
`test_code_module_resolves_to_its_api_stub`,
`test_package_init_resolves_to_the_package_stub`,
`test_cli_reference_page_resolves_to_the_cli_surface`,
`test_docs_page_resolves_to_its_built_page`,
`test_unknown_path_is_dropped_and_reported`,
`test_test_surface_is_dropped_as_excluded`,
`test_casilla_for_unknown_modelo_is_dropped`,
`test_batch_resolution_partitions_resolved_and_dropped`,
`test_resolver_reuse_avoids_reprojection`,
`test_chunk_hit_and_resolved_target_are_frozen`. Unified
(`test_unified_record.py`, 9) -- `test_concept_card_funnels_to_a_search_record`,
`test_casilla_funnels_to_a_search_record_with_provenance`,
`test_cli_command_and_option_funnel_to_search_records`,
`test_all_kinds_serialise_to_the_same_shape`,
`test_funnelled_records_are_json_serialisable`,
`test_base_weights_follow_the_d5_tier_ordering`,
`test_normalisation_preserves_tier_ordering_under_score`,
`test_normalisation_clamps_and_sorts_within_a_kind`,
`test_search_record_is_frozen`.

## Notes

- **Peer-broken CLI walk:** the brief warned the live CLI tree walk was
  transiently un-importable. By the time S17 verification ran it had settled --
  `test_cli_projection.py` passes 7/7 again. Regardless, S17 does NOT depend on
  the live walk: the resolution map reaches the CLI surface via the generated
  `docs/cli/*.rst` reference page, and the unified-record CLI tests construct
  CLI records directly (their shape is the contract under test). All 43 non-CLI
  subtree tests pass independently.
- **`__init__.py`** now re-exports the unified `SearchRecord` surface and the
  resolution-map surface alongside the S15/S16 record kinds.
- **S18 handoff (wrangling-corrections layer):** S18 operates on the
  `ResolutionResult.resolved` tuple S17 produces. The interface: S18 consumes
  `tuple[ResolvedTarget, ...]` and applies the ADR-D6 documented corrections --
  (a) casilla-revision dedupe (the casilla `SearchRecord.id`
  `casilla:<modelo>:<number>:<segmento>` is the dedup key; the projection
  already dedups across revisions, so S18 dedups cross-HIT collisions on the
  same casilla id); (b) locale-quadruplet collapse (four near-identical locale
  hits for one concept collapse to one record by `id`); (c) score-floor /
  TOC-noise filtering (drop `ResolvedTarget`s whose `source_hit.score` is below
  a floor, or whose record is a low-value page); (d) directory-cluster reading
  (group resolved targets by their record's surface/metadata to read the
  dominant cluster). Every `ResolvedTarget` carries `record` (unified, with
  `ranking_weight` already normalised) + `source_hit` (the originating score),
  so S18 has both the typed target and the raw score to wrangle. The
  `DroppedHit` report is the audit trail S18 extends. S18 then feeds the
  wrangled result set to the sweep (S19).

