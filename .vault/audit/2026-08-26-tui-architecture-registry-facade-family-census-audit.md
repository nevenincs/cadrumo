# Registry facade family census — working S175 audit

## Scope and chronology

`c94133f29516b12e3529f3d154c31592562f6198` is the already-delivered mechanical
private-to-public registry relocation. It renamed exactly 78 modules under
`src/cadrumo/domain/calculations/registry`, changed consumers to direct module
imports, and left `registry/__init__.py` inert. This audit does not replay that
move, restore a private module, or introduce a compatibility surface.

S173 work had begun against the recovered authority mapping before the plan was
corrected to make S175 its predecessor. The shared-tree work therefore only
repairs direct defining-owner routes and authority semantics; it does not claim
an S175 disposition. In particular, post-c941 owner discoveries are recorded
separately from this fixed historical family and are not smuggled into its 78
rows.

## Discovery and exact census

Semantic discovery used the canonical Vaultspec-RAG search for registry facade
relocation and authority ownership, followed by the exact historic command:

```powershell
git diff-tree -r -M --name-status --format= c94133f295^ c94133f295 -- src/cadrumo/domain/calculations/registry
```

Its rename-filtered result is exactly 78 one-to-one rows. The scoped generator
`dev/quality/registry_facade_family_census.py` derives only this set, historic
facade exports from the parent `__init__.py`, and current AST/text consumers
under `src/`, `dev/`, and `docs/`. It is intentionally family-specific rather
than a new generic scanner.

## Current adjudication state

`registry_facade_family_census.v1.json` now contains the working semantic
adjudication for all 78 rows and all 594 historic facade symbols. It records 40
`keep_public` and 38 `hard_move_complete` dispositions, 78 non-empty owner and
evidence records, and 78 unique proposed IDs (`W03.P20.S175.R01` through
`W03.P20.S175.R78`). The role and disposition judgments were written from the
family-level RAG findings plus exact defining-symbol and consumer evidence; the
deterministic generator does not synthesize those fields. The IDs are proposed
row coordinates only and still await canonical plan-CLI amendment and
independent architecture review.

This is intentionally not an S175 completion claim: the plan has not yet been
amended with one bounded disposition Step per row, and the final zero-binding,
zero-re-export, and zero-unresolved-row gate remains open. S173 remains gated by
that review and amendment.

## Working semantic discovery and exact evidence

The required RAG-first pass was run once per cohesive family (all searches were
restricted to the registry production tree):

| Family | RAG query | Exact owner anchors confirmed |
| --- | --- | --- |
| host | `AEAT host normalization and remote tax service endpoints registry` | `aeat_hosts.py`: `canonical_remote_hostname`, `is_aeat_host`, `first_aeat_host`; consumed by `remote_state_guard.py`. |
| authority | `registry authority capture identity provenance process incarnation and lifecycle ownership` | `authority.py`: `RegistryAuthorityCapture`, `ValidatedRegistryAuthority.load`; `loader.py` and `identity.py` are the adjacent source/identity owners. |
| binding | `registry binding definitions casilla observations aggregation requirements and selector queries` | `bindings.py`: `CasillaObservation` and binding resolvers; `binding_selector_utils.py`, `relations.py`, and the ledger resolver are delegated owners. |
| schema | `registry schema definitions input kinds scalar verification and record design validation` | `schema.py`: `ModeloRevision`, `ModeloDefinition`; `schema_input_kind.py`, `schema_scalars.py`, `schema_verification.py`, and validation modules own their axes. |
| calculation | `registry formula runtime applicability relation aggregation schedule temporal snapshot calculation` | `formula_runtime.py`: `calculate_registry_snapshot`; `temporal.py`: `select_revision`; `snapshot.py`: `build_snapshot`; `relations.py`: `resolve_relation_values`. |
| export | `registry export layout XML fixed width encoding value policy and Modelo 303 projection` | `export.py`: `ResolvedExportLayout`; `export_parse.py`: `ParsedExportPayload`; `fixed_width_codec.py`: `pad_fixed_width_text`; M303 projection/source/compiler modules own their typed projections. |
| grounding | `registry external grounding legal references corpus catalogue live parity and remote state guard` | `external_grounding.py`: `ExternalGroundingFinding`; `legal.py`: `verify_legal_catalogue`; `live_parity.py`: `LiveParityCatalogue`; `remote_state_guard.py`: `RemoteStateGuardPolicy`. |
| handoff | `registry handoff paths relations queries support matrix and filing capability reports` | `handoffs.py`: relation handoff audits; `queries.py`: `RegistryQueryService`; `support_matrix.py`: `build_support_matrix`. |
| identity | `registry identity stamps revision coordinates continuity localization and cross revision validation` | `identity.py`: `RegistryIdentity`; `snapshot_coordinate.py`: `registry_snapshot_id`; `validate_cross_revision.py`: `validate_cross_revision_casilla_consistency`; localization owns locale-key identity. |

The exact confirmation commands were run after the RAG pass:

```powershell
git diff-tree -r -M --name-status --format= c94133f295^ c94133f295 -- src/cadrumo/domain/calculations/registry
rg -n "class ValidatedRegistryAuthority|class RegistryAuthorityCapture|def load\(" src/cadrumo/domain/calculations/registry/authority.py
rg -n "class CasillaObservation|class DataBindingDefinition|resolve_.*binding" src/cadrumo/domain/calculations/registry/bindings.py
rg -n "class ModeloDefinition|class ModeloRevision|class InputKind|class RegistryVerificationPolicy" src/cadrumo/domain/calculations/registry/schema.py src/cadrumo/domain/calculations/registry/schema_input_kind.py src/cadrumo/domain/calculations/registry/schema_verification.py
rg -n "def calculate_registry_snapshot|def select_revision|def build_snapshot|def resolve_relation_values" src/cadrumo/domain/calculations/registry/formula_runtime.py src/cadrumo/domain/calculations/registry/temporal.py src/cadrumo/domain/calculations/registry/snapshot.py src/cadrumo/domain/calculations/registry/relations.py
rg -n "class ResolvedExportLayout|class ParsedExportPayload|class ExportValuePolicy|def pad_fixed_width_text" src/cadrumo/domain/calculations/registry/export.py src/cadrumo/domain/calculations/registry/export_parse.py src/cadrumo/domain/calculations/registry/export_value_policy.py src/cadrumo/domain/calculations/registry/fixed_width_codec.py
rg -n "class RemoteStateGuardPolicy|class LiveParityCatalogue|class ConvenioAuthority|def verify_legal_catalogue|class ExternalGroundingFinding" src/cadrumo/domain/calculations/registry/remote_state_guard.py src/cadrumo/domain/calculations/registry/live_parity.py src/cadrumo/domain/calculations/registry/convenio.py src/cadrumo/domain/calculations/registry/legal.py src/cadrumo/domain/calculations/registry/external_grounding.py
rg -n "class RegistryRelationHandoff|class RegistryQueryService|def build_support_matrix" src/cadrumo/domain/calculations/registry/handoffs.py src/cadrumo/domain/calculations/registry/queries.py src/cadrumo/domain/calculations/registry/support_matrix.py
rg -n "class RegistryIdentity|def registry_snapshot_id|def validate_cross_revision" src/cadrumo/domain/calculations/registry/identity.py src/cadrumo/domain/calculations/registry/snapshot_coordinate.py src/cadrumo/domain/calculations/registry/validate_cross_revision.py
```

The exact checks reported 78 rows, 78 current public paths, zero old private
paths, and 78 history rename records. The current matrix also has 78 unique
proposed IDs. Any later generator refresh must preserve those invariants and
must be followed by a new `--check`; no ambiguity was silently grouped into a
family, and no post-c941 owner discovery was added to these fixed rows.

## Required review handoff

The reviewer must populate exactly one of `keep_public`, `hard_move_complete`,
`privatize_external_elimination`, or `delete` for each row, explain the semantic
owner from code/architecture evidence, assign a unique canonical follow-on Step,
run `python dev/quality/registry_facade_family_census.py --check`, then amend
the plan through its CLI. The final package gate remains separate: zero project
package binding, zero re-export, and zero unresolved family rows.
