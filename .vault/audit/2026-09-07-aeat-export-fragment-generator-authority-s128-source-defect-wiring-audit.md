---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:e89fc7a3ff9a12a77a173b4f8e14b74e6c23481b15ac4df97c189519b17b718b'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-31-aeat-export-fragment-generator-authority-source-defect-adjudication-adr]]"
  - "[[2026-09-07-registry-temporal-coverage-enrolment-versus-declared-projection-research]]"
---

# `aeat-export-fragment-generator-authority` audit: `S128 source-defect wiring review`

## Scope

Audited the live uncommitted S128 source-defect relocation and catalogue, the
`_export_tree` and `_tree_check` import cutover, operator CLI wiring, generated-tree
consumer cutover, focused source-defect and CLI seam tests, and the S79 and S32 plan
reconciliations. The review checked the implementation against the accepted narrow
mechanism, completeness-closure, and temporal-coverage decisions and the current
export-fragment and temporal-coverage plans. Exact-symbol discovery also covered every
call to `render_complete_export_tree` and `check_generated_export_tree` so the public
module relocation and declaration consumption could be assessed as an atomic change.

Focused validation passed 16 source-defect and Modelo 390 CLI seam tests. The bracketed
run observed concurrent HEAD movement only in an unrelated CLI test, so that result
remains valid for the measured paths.

## Findings

### consumer-wiring | medium | the read-only render comparison still bypasses the shared catalogue

The public `source_defects` catalogue is consumed by the operator pipeline CLI and the
generated-tree gate, but `compare_revision_against_committed` still calls
`render_complete_export_tree` with its default empty declaration set. Running the
supported render comparison for Modelo 390 revision 2022 exits 1 with an uncaught
`RegistryValidationError` at `modelo-390-page-07-close`, reproducing the original
byte-for-byte refusal that S128 fixes in the publication CLI. The source-defect
relocation is therefore not atomic across renderer orchestration paths: the same
hash-pinned source and authored inputs render through one supported command and refuse
through another, leaving the read-only staleness comparison unable to assess this
enrolled revision.

Resolution on 2026-09-07: resolved. `compare_revision_against_committed` now selects
the declaration set from the canonical catalogue using the authority-derived transport
source reference and passes it explicitly to the renderer. The focused bundled
M390/2022 regression passes. The previously failing command now renders all fourteen
candidate members and reaches a normal `RenderComparison` summary without an exception;
its `--check` exit remains 1 only because the revision has no committed export tree to
match.

## Recommendations

Resolve `consumer-wiring` before accepting S128. Make the read-only comparison obtain
the declaration set from the same canonical catalogue using the selected parser-backed
source identity, pass it explicitly to the renderer, and add a focused real-comparison
test for Modelo 390 revision 2022 that reaches a `RenderComparison` verdict rather than
the literal mismatch. Preserve the existing digest validation so a reissued source
retires the pin by refusal instead of inheriting it silently.

Final verdict: the recommendation is satisfied and no unresolved findings remain in
the reviewed S128 scope.
