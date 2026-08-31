---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:ee8d63f3143cf5041d04a06f78c43be660e8eec5bc9dfa863d9e32623260da60'
step_id: 'S121'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Refactor the size-budget subjects in declarations.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/declarations.py`

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

- `M` `src/cadrumo/adapters/outbound/aeat/sede/declarations.py`
- `A` `src/cadrumo/adapters/outbound/aeat/sede/declarations_capture.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/declarations_observations.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/_declarations_support.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part3.py`
- `M` `src/cadrumo/application/live/filed_data_capture.py`
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part1.py::test_authoritative_declaration_selection_uses_latest_alta_row_for_duplicate_period src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part3.py::test_capture_filed_declaration_empty_nif_carries_translated_message` -> `pass`
- `verify:` `uv run --no-sync python -c <canonical consumer capture-import assertion>` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.size_budget` -> `fail`

## Notes

The S121 implementation landed in verified predecessor `5c43de30cf` with other in-flight work; this record attributes the S121 paths and subsequent scoped validation without duplicating or reverting that commit.

Existing browser-backed Sede register fixtures cannot honestly exercise `capture_previous_filing_observations` or `capture_relation_source_observations`: their router supplies navigation/search HTML only and returns 204 for non-navigation traffic, with no Cotejo popup/PDF or submitted-file download protocol. No fabricated router or production injection seam was added.

The canonical size gate reports 93 remaining over-budget subjects owned by still-open P05 rows; `declarations.py` is absent from that list and measures 937 lines. No baseline was changed.
