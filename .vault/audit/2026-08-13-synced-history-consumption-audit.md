---
tags:
  - '#audit'
  - '#synced-history-consumption'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:837e215f1b66fccbcef08daf51aaf31482340e57a59046da97cf0bd4b1824552'
related: []
---
# `synced-history-consumption` audit: final canonicalization closure review

## Scope

Fresh-context review covered initial canonicalization commits `f12e12c409`, `0648cbfadb`, `1d4248368e`, `83b679c770`, `3b23d564f3`, and `65b6f5f244`; the Sede-wrapper remedy `12bf5f3fbcc3f531c25c5c361008f34a7559e16c`; and final residual-removal commits `0768c1894c` and `658c2989f2`, all ancestors of current `HEAD`. RAG grounded the current calculation and Sede ownership topology; exact diffs, full changed-file context, and residual symbol searches covered previous-filing, relations, IVA partition, tolerance, Sheets, and Sede submitted-file observation paths.

## Findings

### sede-test-support-wrappers | resolved | Direct defining imports and explicit Period values replaced wrappers

The prior Medium finding is resolved by `12bf5f3fbcc3f531c25c5c361008f34a7559e16c`. It deletes both Sede resolver wrappers and their support exports. `test_declarations_part2.py` imports `resolve_previous_filing_bindings_from_filed_declarations` directly from `_declarations_observations.py`, and `test_declarations_part3.py` imports `resolve_relation_values_from_filed_declarations` from that same defining module. All affected calls pass `Period.from_year_and_code(...)`; no wrapper conversion or test business logic remains.

### relation-period-alias | resolved | Defining private helper is now imported directly inside its owning package

`0768c1894c` removes `derive_offset_source_period = _derive_offset_source_period` from `_relations.py` and repoints the sole intra-package validator consumer at `_derive_offset_source_period`. Current search finds no residual relation-period alias or re-export.

### submitted-file-observation-aliases | resolved | One defining Sede projection owns every consumer

`658c2989f2` removes the private submitted-file casilla alias, two header convenience aliases, and the test-support export. `_declarations_observations.py` now defines `observed_casillas_from_submitted_file` once; `_declarations.py` and the direct test consume that defining name. Current residual search finds no prior aliases, re-exports, or test wrappers.

No open Critical, High, Medium, or Low findings remain in the reviewed synced-history canonicalization scope. Required package `__init__` facades remain canonical public surfaces under `aeat-architecture-boundaries`; they are not forbidden bridge modules.

## Recommendations

No remediation is required for the reviewed scope. Preserve the defining-owner topology: private helpers stay intra-package only, package facades serve cross-package consumers, and Sede tests import defining observation functions directly with typed `Period` values.

## Verification

RAG located current canonical owners before each review. Every reviewed commit is an ancestor of current `HEAD`; all eight reviewed commit diffs passed `git diff-tree --check`. Exact residual searches found one defining resolver each for previous-filing and relation filed-observation resolution and no aliases for the removed relation-period or submitted-file projections. The final closure changed paths pass focused Ruff; the two final commit whitespace checks pass.

The direct previous-filing resolver test and cross-modelo direct-selector taxonomy test passed in the final focused run. The submitted-file observation test failed before exercising a duplicate implementation because concurrent, unreviewed registry WIP leaves the current Modelo 130 revision with no export-layout fragment; `resolve_export_layout` therefore correctly refuses `modelo 130 revision 2019-y-siguientes has no exports`. The affected Modelo 130 construct and dependency-classification paths are outside `658c2989f2`, which touches no registry authoring paths. This is an external current-tree gate limitation, not a canonicalization regression. Earlier complete Sede collection found 38 tests; broader Sede executions also timed out without a failure trace while shared-tree registry churn was active.
