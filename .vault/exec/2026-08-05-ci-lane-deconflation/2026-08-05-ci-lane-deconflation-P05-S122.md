---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:048c65682f22862fcb2df849473080981af3c978f488104d78968247d8d692e4'
step_id: 'S122'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Refactor the size-budget subjects in calc_sheets_apply.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/adapters/outbound/google/calc_sheets_apply.py`

## Changes

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

- `M` `src/cadrumo/adapters/outbound/google/calc_sheets_apply.py`
- `A` `src/cadrumo/adapters/outbound/google/_calc_sheets_apply_formatting.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_apply_adapter_helpers.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_export_integration.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_offline_online_conformance.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_transport_facet_parity.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_grid_resize.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_package_module_allowlist.py`
- `verify:` `uv run --no-sync pytest -n0 -q <five focused real Modelo-plan builder modules>` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -q <apply/preview/clear-order consumer modules>` -> `pass`
- `verify:` `uv run --no-sync ruff check <S122 paths> && uv run --no-sync ruff format --check <S122 paths>` -> `pass`
- `verify:` `source-specific size measurement for calc_sheets_apply.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.size_budget` -> `fail`

## Notes

Grounded against predecessor `6df9635e34`. The source-specific ratchet measurement is 1,172 lines against the default 1,250-line limit. The canonical global size gate exits 1 with 92 remaining findings owned by still-open P05 rows; `calc_sheets_apply.py` is absent from that output. No baseline was changed.
