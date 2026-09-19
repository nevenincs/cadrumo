---
tags:
  - '#audit'
  - '#binding-schema'
date: '2026-09-13'
modified: '2026-09-13'
body_schema: 'body-v2'
body_hash: 'sha256:5d8c7866dfe197c4fcbc2980a2dd345f39bb01cc85a5333259232081dd6ecaa2'
related:
  - "[[2026-09-12-binding-schema-tooling-review-audit]]"
  - "[[2026-09-11-binding-schema-plan]]"
---

# `binding-schema` audit: `Binding-schema overnight repair and hardening`

## Scope

The binding-schema lane's unattended run of 2026-09-13, 02:00-11:00: an incident that
broke registry loading corpus-wide, its repair, the restoration of stated member order
lost to a corpus-wide strip, the tooling and compiler hardening that followed, new
cross-revision coexistence semantics, and two new export-placement gates. Covers the
registry binding sources and compiler validators under
`src/cadrumo/domain/calculations/registry/` and the corpus tooling under `dev/registry/`.

## Incident and repair

A writer enrolled bindings for keyed inheritance in
`src/cadrumo/domain/calculations/registry/keyed_families.py`, republished the authority
artifact, and then ran `dev/registry/strip_restated_bindings.py` corpus-wide after
modifying it. The modification replaced the tool's delete branch with a retain-preamble
write, so fragments that should have been unlinked were instead left on disk as 237 blank
and 31 comment-only files. Every registry load failed against those remnants.

Repair unlinked the 268 remnants and the 7 directories they emptied; the contents of each
removed path were preserved in a manifest before deletion. The tool's delete branch was
restored and three regression teeth were added in `test_strip_restated_bindings.py`.

The same strip also removed stated members from ten reordering editions (modelo 303 five
editions, 390 two, 131 two, and 193 `2025-y-siguientes`). Because those editions restate
inherited members only to change their order, the strip erased their stated order from the
tree, and the republished artifact carried merged predecessor order instead. The order was
restored from an authored pre-strip copy of the 77 affected fragments held under `.tmp/`,
proven four ways: the declared sequence equals the copy, the materialised content equals
the artifact, per-file hashes match, and a separate-process read-back reproduces the
result.

The thirteen `restated_families` declarations for those reordering editions are
deliberately not authored. A declaration on an edition that does not state the family in
full withdraws the unstated members, which would silently drop inherited content. For the
same reason modelo 714 `2022-2025`'s four `m714-m100-*` members remain inherited from the
2021 edition with no declaration.

## Changes

| Path | Change | Tests |
| --- | --- | --- |
| `src/cadrumo/domain/calculations/registry/keyed_families.py` | Bindings enrolled for keyed inheritance | Registry load and resolution suites |
| `dev/registry/strip_restated_bindings.py` | Delete branch restored; carried-grounding guard so a member strips only when its materialised `source_refs` are what the successor default supplies or its constructs cover | `test_strip_restated_bindings.py` (three teeth) |
| `dev/registry/run_exclusions.py` | Edge and exclusion options; `FROZEN_MODELOS` (100, 200) | Owning exclusion tests |
| `dev/registry/corpus_write.py` | Byte-level write with read-back verification | Owning corpus-write tests |
| `src/cadrumo/domain/calculations/registry/binding_provider_registration.py` | Silent skip fixed: `row_set` now agrees on the effective aggregation op | Binding provider registration tests |
| `src/cadrumo/domain/calculations/registry/validate_formulas.py` | Silent skip fixed: unknown `date_binding` operand refused | Formula validation tests |
| `dev/registry/bindings.py` | Two run limitations declared | Corpus run tests |
| `src/cadrumo/domain/calculations/registry/inventory_bindings.py` | Inventory validator teeth restored via `selector_against_model` | Inventory binding tests |
| `src/cadrumo/domain/calculations/registry/corpus_catalogue.py` | Blanket catch narrowed | Compiler validation tests |
| `src/cadrumo/domain/calculations/registry/legal_grounding.py` | Blanket catch narrowed | Compiler validation tests |
| `src/cadrumo/domain/calculations/registry/loader_cache.py` | Blanket catch narrowed | Compiler validation tests |
| `src/cadrumo/domain/calculations/registry/validate_evidence.py` | Two blanket catches narrowed | Compiler validation tests |
| `src/cadrumo/domain/calculations/registry/revision_order.py` | `revisions_coexist` and `revision_windows_intersect` added: coexistence requires windows to intersect and selectors to overlap | Revision order and cross-revision suites |
| `dev/registry/compiler/validate_export_field_placement.py` | New gate: overlap refusal, gap and late-start advisories | Gate teeth plus corpus run |
| `dev/registry/compiler/validate_below_floor_export_refs.py` | New gate: a `below_floor` disposition downgrades a revision's unknown-binding export refusals to one advisory | Gate teeth plus corpus run |

The new coexistence predicates are consumed by `validate_cross_revision`,
`_validate_cross_revision_contiguity`, `_validate_cross_revision_evolution`, and
`validate_revision_windows`. The domain divergence field and
`dev/registry/analysis/delta_minimality.py` were left deliberately unchanged, so the
semantics change is confined to coexistence determination. A `restated_families` casillas
refusal was added, and two retired projection-endpoint evolutions were removed from modelo
303 `2025`.

## Measurements

Order restoration moved modelo 303 findings 92 to 18 to 12 across the two passes, and
corpus findings 3,656 to 3,582 to 3,576, over 77 restored fragments.

Coexistence semantics measured on modelo 036: chains crossing rose from 0 to 498 with 0
new findings, confirming the predicates admit real coexistence without loosening
validation.

Export field placement across the corpus: 415 materialised records, 27,639 spans, 0
overlaps, 115 gaps. Of the gaps, 58 trace to a single envelope-header template omission of
the EEDD fields "Versión del Programa" (position 93, width 4) and "NIF Empresa Desarrollo"
(position 101, width 9), confirmed against 26 designs; 57 are reserved pads; one outlier
remains at page 01 position 12, "Blanco o C".

Below-floor export refs on modelo 232 `2016-2017`: 140 refusals to 0. Corpus compile
refusal lines fell 3,498 to 3,358. The two retired 303 `2025` projection-endpoint
evolutions took that modelo from 6 findings to 0.

## Open items

The thirteen `restated_families` declarations remain unauthored pending the 52-edge
inheritance re-proof; the identity tuple under consideration is
`provider.kind`/`value.data_type`/`value.channel`, and the decision so far is to keep
`data_type` in the tuple. Modelo 100 re-grounding is outstanding, with 667 casillas
re-grounded on `orden-hac-277-2026`. The EEDD envelope fields need to become a
configuration-sourced field kind rather than a template omission. FILLER authoring is owed
for the reserved pads. A family-aware retirement grounding gate is not yet written. Modelo
296 `2023` needs a semantic map for its export bootstrap.

## Rules adopted

Corpus tooling never invokes git; recovery relies on manifests, not on version-control
state. Every script that writes the corpus reads its own output back and compares. Every
destructive operation writes a manifest carrying pre- and post-hashes for each path.
Frozen modelos are declared structurally in the tool, not passed per run. A verification
pass must not inherit the filter of the subject it verifies, or it confirms only what the
subject already assumed. A `restated_families` declaration is authored only on an edition
proven to state the family in full, because a partial declaration withdraws the members it
omits.
