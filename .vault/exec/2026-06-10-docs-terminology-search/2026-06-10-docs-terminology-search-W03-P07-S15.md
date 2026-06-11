---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S15'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement the casilla projection compiler: per-modelo casilla search records from registry snapshots via the validated authority (modelo, casilla number, localised label/description including per-revision locale fragments where authored - conforming to the official casilla descriptions - plus legal_refs), deduplicated across revisions, never hand-curated (ADR D4)

## Scope

- `dev docs terminology compiler`

## Description

Implements ADR **D4** record kind (b): the casilla projection compiler that
machine-generates one search record per AEAT casilla from registry snapshots
(never hand-curated), deduplicated across revisions.

This Step was a RESCUE: the originating agent left three untracked,
uncommitted, untested files (`dev/docs/terminology/_search_record.py`,
`_casilla_projection.py`, `__init__.py`) and stalled. The sibling CLI/concept
emitters (S16) already imported the shared `SearchRecordBase` from those
uncommitted files, so committing them repairs S16's broken-in-history import.

`dev/docs/terminology/_casilla_projection.py`:
`project_casilla_search_records(authority=None)` walks every casilla of every
modelo revision -- read through `ValidatedRegistryAuthority` / `bundled_authority()`
(never raw TOML, per `aeat-registry-authority-flow`) -- into a strict frozen
`CasillaSearchRecord`, deduplicated in a single pass.
`project_modelo_casillas(modelo, authority=None)` is the per-modelo focused
projection used by tests and per-modelo index builds.

`dev/docs/terminology/_search_record.py` owns the shared `SearchRecordBase`
(the `kind` discriminator + four-language `descriptions` map) and
`SearchRecordKind` (concept | casilla | cli | page), plus `CasillaSearchRecord`
(modelo, number, segmento, section, semantic_role, legal_refs, source_refs,
source_revisions). This is the SAME base S16's CLI-surface and concept-card
emitters extend.

`__init__.py` now re-exports BOTH S15's records/projection AND S16's
CliSurfaceRecord / CliOptionRecord / ConceptCardRecord / projections, so the
`dev.docs.terminology` package imports cleanly and both module families are
importable together.

## Outcome

Landed (one atomic commit, see Notes for hash). Both S15 (12 new) and S16 (14)
tests pass together: full subtree 26 passed. ruff / ruff format / ty all clean;
collect-only clean.

**Hang diagnosis: NO HANG.** The peer did not stall on performance. The full
projection over the real registry completes in ~1.0s (plus ~1.1s import); the
code is already efficient -- it walks each revision's casilla list ONCE through
the authority and dedups in a single O(n) pass (no per-casilla snapshot
reload, no O(n^2)). The stall was non-technical (no tests written, never
committed). A performance-sanity test
(`test_full_projection_completes_within_a_bounded_time`, < 30s ceiling) guards
against a future per-casilla-reload regression.

**Projection runtime + counts (real bundled registry):**
- projection time: ~1.0s (import ~1.1s)
- `raw_casilla_rows`: **15,301** (every casilla row across every revision)
- `deduplicated_records`: **5,962**
- `collapsed`: **9,339** cross-revision duplicates
- `records_with_localized` (en/ca/hu beyond es): **11**

**Every-casilla parity (the "never drop a casilla" gate):** an independent
walk of the authority's casilla lists counts 15,301 -- EXACTLY the projection's
`raw_casilla_rows`. Per-modelo: every one of M303's 120 distinct
`(number, segmento)` identities is emitted. No casilla is dropped.

**Multilingual coverage:** M303 authors per-revision locale fragments, so its
casillas carry es+en+ca+hu (e.g. casilla `iva.repercutido.general`:
es="Cuota IVA repercutido...", en="Output IVA quota at general rate...",
ca="Quota IVA repercutit...", hu="Felszamitott AFA..."). Of the 5,962 deduped
records, 11 carry non-Spanish localised labels; the rest are es-only (registry
locale coverage is sparse today -- bounded by registry locale authoring, a
separate workstream the ADR explicitly does not own). Every record carries the
es invariant (the registry `label`).

**Calculation grounding:** all 15,301 casillas carry non-empty `legal_refs`
AND `source_refs` (verified independently: 0 casillas without either), so the
schema's `min_length=1` constraint holds registry-wide; every projected
`legal_ref` resolves in the bundled legal catalogue (0 unresolved across all
5,962 records).

**Dedup rule:** identity is `(modelo, number, segmento)`. A casilla identity
appearing across multiple revisions collapses to ONE record built from the
LATEST revision (greatest `valid_from`; revision id as a stable tiebreak) --
the latest revision carries the current official label and the richest locale
coverage. Every contributing revision id is recorded on `source_revisions`
(latest first) so the collapse is auditable.

Test names (`test_casilla_projection.py`, 12):
`test_projection_walks_every_casilla_row`,
`test_m303_emits_every_distinct_casilla_identity`,
`test_dedup_collapses_cross_revision_duplicates`,
`test_dedup_key_is_unique_across_records`,
`test_record_carries_contributing_revisions_latest_first`,
`test_every_record_carries_legal_and_source_refs`,
`test_all_legal_refs_resolve_in_the_catalogue`,
`test_m303_record_has_correct_identity_and_spanish_label`,
`test_m303_has_multilingual_casilla_labels`,
`test_es_description_is_always_present`,
`test_full_projection_completes_within_a_bounded_time`,
`test_records_are_frozen`.

## Notes

- **What the partial work contained:** sound, complete projection logic +
  schema (the three untracked files). The projection itself needed NO
  correctness fix -- it already satisfied every ADR-D4 / calculation-grounding
  gate. What was MISSING: tests (none written), the commit (never made), the
  S16 re-exports in `__init__.py`, and source-hygiene cleanup.
- **What I completed/fixed:** (1) added the 12 missing real-behaviour tests;
  (2) extended `__init__.py` to export both S15 and S16 record kinds;
  (3) removed the peer's source-hygiene violations -- PM tokens
  (`W03.P07.S15`, `W03.P07.S16`, `W04`, `S16`) in production docstrings,
  rephrased to describe by function (ADR ids retained); (4) ran ruff format on
  `_casilla_projection.py` (peer left it unformatted).
- **S17 handoff (unified-index-schema reconciliation that remains):** S15 and
  S16 records now SHARE `SearchRecordBase` / `SearchRecordKind` and are all
  re-exported from `dev.docs.terminology`, but they are NOT yet unified into
  one homogeneous index payload schema with a single discriminated-union type
  and per-kind metadata/weight normalisation. S17 owns: (a) a single
  `SearchRecord` discriminated union (or a uniform serialisation funnel) over
  CasillaSearchRecord / CliSurfaceRecord / CliOptionRecord / ConceptCardRecord;
  (b) the chunk-to-target resolution map (ADR D6) that the sweep consumes;
  (c) any ranking-weight normalisation across the kinds. The record kinds and
  their `descriptions` / `target` / `legal_links` fields are the stable inputs
  S17 reconciles.

