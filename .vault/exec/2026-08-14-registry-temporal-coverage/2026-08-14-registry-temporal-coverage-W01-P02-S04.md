---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:c3fc6e1c2885b666b29f46c94f59036ce2172146a6e7bd0b307ee94b7231394b'
step_id: 'S04'
related:
  - '[[2026-08-14-registry-temporal-coverage-plan]]'
  - '[[2026-08-14-registry-campaign-sequencing-audit]]'
---

# Replace the m303_annual_orden field on RegistrySnapshot and RegistryCatalogues with a generic modelo-keyed supplementary orden catalogue, delete the Modelo.M303 branch in generic authority construction, and sweep every consumer in one atomic relocation commit

## Scope

- `src/cadrumo/domain/calculations/registry/_schema.py`
- `src/cadrumo/domain/calculations/registry/_authority.py`
- `src/cadrumo/domain/calculations/registry/`

## Description

This record documents work found already present, uncommitted, in the working
tree at the time of writing; it is written retrospectively from the code, the
diff against `HEAD`, and the reconciler output, not from having performed the
implementation.

- Replace the `m303_annual_orden: M303AnnualOrdenAuthority` field on
  `RegistrySnapshot` and `RegistryCatalogues` (`_schema.py`) with
  `supplementary_ordenes: Mapping[Modelo, M303AnnualOrdenAuthority]`.
- Add `src/cadrumo/domain/calculations/registry/_supplementary_orden.py`: a
  `Modelo`-keyed dispatch table pairing each registered modelo with a compiler
  (`SupplementaryOrdenCompiler` protocol) and a fingerprint collector, plus the
  generic fold `compile_supplementary_ordenes` and
  `collect_supplementary_orden_fingerprints` that iterate the table without
  naming a modelo. `Modelo.M303` is registered as the sole table entry today,
  pointing at the existing `load_m303_annual_orden_authority` /
  `collect_m303_annual_orden_fingerprints` M303-specific compiler, which is
  untouched.
- Delete the `if any(modelo.id == Modelo.M303 ...)` / `else` branch from
  `_construct_authority` in `_authority.py`; generic authority construction now
  calls `compile_supplementary_ordenes` unconditionally and folds whatever the
  table returns onto the shared catalogues.
- Sweep consumers in the same change: `_snapshot.py`'s
  `_build_validated_snapshot` and
  `_m303_orden_resolution.py`'s `supplementary_orden_authority(registry_snapshot.supplementary_ordenes, Modelo.M303)`
  read the new field; `test_m303_did_account_wire_isolated_authority.py`'s
  hand-built `RegistrySnapshot` fixture passes `supplementary_ordenes=` instead
  of `m303_annual_orden=`.
- Remove the stale `_authority.py` entry from
  `dev/registry/modelo_embed_classification.toml` (it classified `_authority.py`
  as `machinery` on the grounds of the now-deleted `Modelo.M303` branch) and add
  a new entry classifying `_supplementary_orden.py` as `machinery` — a dispatch
  table is a routing coordinate, not a regulatory value.

## Outcome

`_m303_orden_resolution.py` legitimately keeps its own `Modelo.M303` checks —
it IS the M303-specific resolver, not generic construction, so this is outside
the row's scope (which targets only `_authority.py`'s generic
`_construct_authority`).

Verification performed for this record:

- `uv run --no-sync python dev/registry/modelo_embed_classification.py` →
  `36 modelo-specific modules derived; 0 reconciliation failures`, confirming
  the ledger reconciles now that `_authority.py` is no longer derived as
  modelo-specific (it no longer carries the `Modelo.M303` branch that made the
  mechanical deriver pick it up) and that `_supplementary_orden.py`'s new
  `machinery` entry is not stale.
- `pytest src/cadrumo/domain/calculations/registry/tests/test_modelo_specific_embed_classification.py -n 0 -q`
  → `10 passed`.
- `pytest src/cadrumo/domain/calculations/registry/tests/test_m303_orden_anual_authority.py src/cadrumo/application/filing/tests/test_m303_did_account_wire_isolated_authority.py -n 0 -q`
  → `9 failed, 33 passed` in 265.78s. All 9 failures are
  `RegistryValidationError: modelo 303 revision ... is 'pending_review'; filing-grade
  snapshot requires operator_reviewed revision` on revisions `2025`,
  `2026-y-siguientes` and `2009-y-siguientes` — the tree-wide review-status
  collision this same day's registry-campaign-sequencing audit (linked in
  `related:`) already documents as blocking every filing-grade snapshot in
  `dev/registry/tests`, not
  a defect this row introduced. `test_m303_did_account_wire_isolated_authority.py`'s
  own tests are among the 33 passing, confirming the field-name sweep in that
  file works.

## Notes

The relocation was found uncommitted when this record was first authored, then landed in commit `a16b0b8ffd` (`registry: retire SupportRemovalDecision, add authority-grade coverage and export-completeness gate`). Later public-module relocation commits moved `_schema.py`, `_authority.py`, `_snapshot.py`, and `_m303_orden_resolution.py` to `schema.py`, `authority.py`, `snapshot.py`, and `m303_orden_resolution.py` without restoring the deleted field or branch. The S04-owned paths are clean in the current worktree.

This Step's deletion-inventory item is the `m303_annual_orden` field and its generic-construction branch; both remain absent from the shared types and generic construction. The M303-specific parsing modules, `M303AnnualOrdenAuthority`, and the `Modelo.M303` dispatch-table registration survive deliberately, per the plan's own "what survives deliberately" list.

A 2026-08-26 reconciliation found zero `m303_annual_orden` field declarations or generic-authority M303 branches. The focused suite produced 32 passes and 25 failures: 22 are blocked before S04 behaviour by the active Modelo 200 registry split, and three expose separate classifier-ledger drift owned by the classifier lifecycle rather than this relocation. Those reds are not represented as S04 proof; the closure rests on the committed deletion/relocation inventory and current structural inspection. S06 remains open to establish the durable planted-mutation gate.
