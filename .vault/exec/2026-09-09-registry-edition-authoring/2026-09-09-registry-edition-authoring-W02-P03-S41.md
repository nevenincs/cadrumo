---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:11574fd3318fd341dc6c8e4554dbba0046031f6bff1ed04720879f817c3bc85c'
step_id: 'S41'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [S | sonnet-high] Check every enumeration this campaign introduces against the proposed registry enum-canonicalisation ruling — one named enum per closed vocabulary, no inline unions, no allowlist — and reconcile or record the divergence. That ruling is proposed rather than accepted, so this is a compatibility check and not an obligation to obey it. Proof: each new enumeration is either conformant or carries a stated reason.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `M` `dev/registry/analysis/casilla_lineage_seed.py`
- `M` `dev/registry/analysis/delta_minimality.py`
- `verify:` `uv run --no-sync ruff check dev/registry/analysis/casilla_lineage_seed.py dev/registry/analysis/delta_minimality.py` -> `pass`
- `verify:` `uv run --no-sync ruff format dev/registry/analysis/casilla_lineage_seed.py dev/registry/analysis/delta_minimality.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/registry/analysis/casilla_lineage_seed.py dev/registry/analysis/delta_minimality.py` -> `pass`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_casilla_lineage_seed.py dev/registry/tests/test_casilla_lineage_totality_gate.py dev/registry/tests/test_delta_minimality.py -q` -> `pass` (41 passed)

## Notes

Verdict against the proposed registry enum-canonicalisation ruling (one named enum per
closed vocabulary, no inline unions, no allowlist), scoped by that ruling's own text to
registry schema model fields:

| Enumeration | Location | Verdict | Reason |
| --- | --- | --- | --- |
| `CasillaLineageOrigin` | `src/cadrumo/domain/calculations/registry/casilla_lineage.py` | conformant | Named `StrEnum`, boundary-coerced via `BeforeValidator`, single definition imported by the schema field. |
| `DeclaredPredecessor` / `NoPredecessor` discriminated union | `src/cadrumo/domain/calculations/registry/schema.py` | conformant (out of scope) | The `predecessor` field is a discriminated union of two structured `RegistryModel` types, not a string literal union; the ruling's own constraints state non-string unions cannot become `StrEnum` members and are outside the gate's mechanically decidable subject by construction. The tag strings (`"revision"`, `"none"`) that route the discriminator are never authored or persisted registry data — the discriminator function returns a computed `str`, not a `Literal` union — so no closed vocabulary is spelled inline in the type system either. |
| Materialiser section constants (`_INHERITED_SECTION`, `_RETIREMENT_SECTION`, `_REVISION_EXPORT_LAYOUTS`, `_REVISION_CONSTRUCTS`, `_REVISION_COMPLETENESS_MANIFEST`) | `src/cadrumo/domain/calculations/registry/_loader_internals.py`, `_loader_revision_fragments.py` | conformant | These name raw TOML table keys for structural section routing, not a registry field's value set; `REVISION_SECTION_FIELDS` is computed from `ModeloRevision.model_fields` itself, so there is exactly one definition (the pydantic model) and no independent vocabulary to duplicate. |
| Ledger `category` strings | `dev/registry/analysis/casilla_lineage_seed.py` | divergent, fixed | Sixteen refusal reasons were spelled as bare string literals repeated across `_pair`, `_classify_absence`, `_apply_ruling` and `residual_plan`. Consolidated into `LineageRefusalCategory(StrEnum)` in the same defining module; `Refusal.category`, `ExcludedModelo.residual_category`, `LineagePlan.refuse`, `admit_bare_chain`'s return type and every call site now reference the enum. The ledger reader (`dev/registry/analysis/casilla_lineage_ledger.py`) still reads `category` as a plain `str` from the persisted TOML log — left untouched as reading an artifact file rather than declaring a vocabulary, and out of the small/local/mechanical bound for this Step. |
| Delta-minimality verdict/basis strings | `dev/registry/analysis/delta_minimality.py` | divergent, fixed | `kind` (row verdict) and `basis` (predecessor establishment) were plain `str` fields backed by module-level `Final` string constants, not enum members, and the sibling test file re-spelled several of the same tokens as bare literals rather than importing the constants. Consolidated into `MinimalityVerdict(StrEnum)` and `PredecessorBasis(StrEnum)`; `RowJudgement.kind`, `EditionPredecessor.basis` and `MinimalityCensus.verdicts` now carry the enum types. `test_delta_minimality.py` needed no changes: `StrEnum` members compare equal to their string value, so its existing raw-string assertions still pass. |

Both fixed modules are dev-only analysis tooling outside `src/cadrumo/domain/calculations/registry` and `src/cadrumo/domain/calculations/registry/_loader_internals.py`/`schema.py` were not touched, per the Step's scope guard.
- The reviewer persona could not be launched. The orchestrating session re-ran the seed, totality-gate and minimality tests (41 passed) and ruff and ty (clean). The ledger TOML is byte-unchanged, so the new StrEnums keep the prior values.
