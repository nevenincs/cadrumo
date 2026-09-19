---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:624dbce8659268f53580ad8a8baee1683f1a7c7112a378546a4e351852f9d15b'
related:
  - '[[2026-08-14-registry-temporal-coverage-plan]]'
---
# `registry-temporal-coverage` audit: `s44 review`

## Scope

Independent review of commit `13c733cfef` and its Modelo 182 temporal authority evidence, selector boundaries, source and legal catalogue entries, downstream revision consumers, and focused quality gates.

## Findings

### stale-revision-consumers | medium | Two downstream tests retained the deleted revision identifier

The S44 commit correctly renamed the only Modelo 182 revision from `2007-y-siguientes` to `2025`, but `test_deferred_detalle_source_advisories.py` and the two Modelo 182 scenarios in `test_row_set_assembly.py` still selected the deleted identifier. The targeted correction in commit `0745edd51c` moves those three references to the canonical `2025` revision.

### stale-census-coordinate | medium | The source-connectivity census retained the deleted revision and its refused 2007 coordinate

The same rename left the Modelo 182 donor-row census target at the deleted revision, filing year 2007, and an obsolete binding path. Commit `f291e2af1f` repairs the target to revision `2025`, period `2025 0A`, and the canonical binding path.

## Recommendations

The corrections are complete. Future revision-id renames should run an exact repository-wide consumer sweep before the authoring-tree change is declared complete.

## Verification

The final focused authority script confirms that only exercise 2025 selects; 2007, 2023, 2024, and 2026 onward refuse. It also confirms the exact 2025 source hash, the unselected 2024 catalogue source, unique amendment references, unchanged applicability grade and absent export layout, and the repaired census target. Ruff passes for the S44 consumer correction.
