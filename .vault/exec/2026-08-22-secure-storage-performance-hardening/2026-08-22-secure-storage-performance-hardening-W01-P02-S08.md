---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:6997e416bdb23f41d1c3d6e9686d3d545fdb9d5600a24d13e1df7f811eda2177'
step_id: 'S08'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Prove profiler and census gates bite on injected registry loading, filesystem materialization, and unclassified nodes

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_cli_performance_budgets.py`

## Description

- Plant unrelated live-registry loading outside tracked source and trigger it
  after each fresh profiler child starts observing.
- Plant storage-root materialisation through real `pathlib` and OS boundaries
  in independent resolution and safe-help children.
- Compare each plant with an independently measured clean control and require
  failures to name the added modules, directory, file, and audit operations.
- Enroll externally added roots, helper-generated groups, and leaves in a
  planted unclassified-node proof driven by the live command walker.
- Correct the registry import family to the live application and calculation
  authority prefixes exposed by the planted integration run.
- Obtain an approved independent review and run scoped unit, integration,
  profiler, lint, type, and Vaultspec checks.

## Outcome

The profiler now demonstrably bites on unrelated registry imports and
filesystem materialisation in both independent phases. The registry plant adds
and names `cadrumo.application.registry` and
`cadrumo.domain.calculations.registry`; the filesystem plant adds exactly
`planted-materialization` and
`planted-materialization/unexpected.txt`, with corroborating `open.write` and
`os.mkdir` audit-count increases. The caller-provided storage root remains
empty because every observation runs on a private clone.

The census proof fails closed for an unclassified executable root, a nested
helper-generated group callback, and a leaf, reporting each offending live
path without a fixed node count or a policy-derived expected set. Nine unit
cases, two fresh-process integration cases, and the six existing profiler
integration cases passed. Scoped Ruff and `ty` checks passed. Independent
review approved the Step with no findings.

## Notes

The first parallel pytest invocation suffered an xdist worker crash before any
test executed. The focused module was rerun serially so its fresh children were
isolated; both test lanes then passed. Initial adversarial exploration exposed
retired registry-family prefixes, which were corrected before the permanent
plant was accepted. No production optimization or storage mutation was added.
