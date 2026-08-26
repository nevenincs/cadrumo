---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:f59a8bcfe47d35e48fcd400c0766fc626b6c55892fbeefd21713e84d091703af'
step_id: 'S261'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Retire the 11 detail_record_bindings re-export(s) from the registry bindings dispatch module by direct-importing AtributionMemberObservation, Modelo720RowObservation, RefundOperationObservation, RelatedPartyOperationObservation, _build_foreign_asset_rows, _build_related_party_rows and others from their defining module at every production, test, fixture, annotation, tooling and dynamic consumer, delete the corresponding __all__ entries and import block, and prove zero remaining reach through the dispatch module for those symbols.

## Scope

- `src/cadrumo/domain/calculations/registry/detail_record_bindings.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`
- `and every consumer of the listed symbols under src/`
- `dev/ and docs/`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_detail_record_row_builders.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_detail_record_row_builders.py src/cadrumo/domain/calculations/registry/tests/test_detail_record_modelo_coverage.py src/cadrumo/domain/calculations/registry/tests/test_detail_record_observations.py src/cadrumo/domain/calculations/registry/tests/test_foreign_asset_binding_row_field.py -q -m unit` -> `pass` (69 passed)

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->

## Notes

The four validate_* dispatch-table entries for ATRIBUCION_MEMBER, FOREIGN_ASSET, REFUND_OPERATION and RELATED_PARTY_OPERATION stay -- genuine dispatch role, never in __all__, out of this Step's named scope.
