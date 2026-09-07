---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:d27598ba885c8b1f06a92ae58f6cca39d5b09602ded5924fcb49cd50df92fdf2'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
---

# `aeat-export-fragment-generator-authority` audit: `S129 candidate staging review`

## Scope

Reviewed `W04.P07.S129` against the accepted generator-authority decision and
the live implementation diff. The review covered candidate isolation from both
loader-recognized export authorities, supplementary Orden closure, explicit
bootstrap precedence and count pins, Modelo 390 construct legal closure,
detector teeth, path confinement, and the later no-fallback publication
cutover.

## Findings

### drift-gate-bootstrap-retarget | high | RESOLVED: the enrolled drift gate omitted the complete candidate-staging boundary

`candidate_staging.py` exposes three independent helpers rather than one
candidate-staging operation. The operator path in `cli.py` invokes all three,
including `retarget_bootstrap_construct_export_layout`, but
`test_generated_export_trees.py::_isolated_authority` invokes only the export
directory exclusion and supplementary Orden helpers. Its Modelo 390 test merely
asserts directory absence and Orden presence, so it cannot detect the omitted
retarget. Replaying validation on that gate-shaped candidate after rendering
the generated layout refuses because construct
`modelo-390-iva-resumen-anual` still references unknown export layout
`modelo-390-2022-fichero-boe`. The current parametrized drift test does not
expose this because it stops first at the deliberately unpublished-tree
assertion. Once `W04.P07.S21` publishes the generated tree and deletes the
manual tree, the enrolled gate will reach this refusal and cannot verify the
hard cutover it is meant to protect.

Resolution verified on re-review: `stage_generated_export_candidate` now owns
the complete staging operation and both `cli.py::_prepare` and
`test_generated_export_trees.py::_isolated_authority` consume it. Both resolve
the same `GeneratedExportBootstrapTarget` from
`generated_export_bootstrap_targets.toml`, so export-directory exclusion,
supplementary Orden staging, and the explicit superseded-construct retarget
cannot drift between the operator and gate paths. The Modelo 390 gate test now
asserts both old authority directories are absent, asserts the construct names
the generated layout, renders the real candidate, and passes full candidate
validation. The count-pin detector covers missing, stale-pin, and widened
membership and proves refusal leaves the original bytes unchanged. Focused
re-review ran the gate-level validation and all three detector cases: four tests
passed. The test's HEAD bracket drifted only across unrelated Vaultspec audit,
index, and plan paths, so none of the measured implementation or test paths
changed during the run. No HIGH or MEDIUM findings remain.

## Recommendations

Resolve `drift-gate-bootstrap-retarget` by making the complete staging operation
the single public boundary consumed by both the CLI and enrolled drift gate,
with bootstrap supersession identity and expected reference count read from one
declaration. Add a gate-level Modelo 390 detector that renders and validates the
isolated candidate while both prior export trees are absent, and prove stale,
missing, and widened construct-reference counts refuse before any staged file
is rewritten.

Completed on re-review; no further recommendation remains for S129.
