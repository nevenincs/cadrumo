---
tags:
  - '#adr'
  - '#product-packaging'
date: '2026-06-28'
modified: '2026-07-17'
body_hash: 'sha256:9c9312832455914e7171ce43f66026e267286e1c0e55a4dab1ab0e5734155d5a'
related:
  - '[[2026-06-28-product-packaging-research]]'
  - '[[2026-06-28-product-packaging-reference]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
---

# `product-packaging` adr: `Exact-version Cadrumo wheel cohort and clean-install proof` | (**status:** `accepted`)

## Problem Statement

Cadrumo must install and run from built artifacts without checkout-only files,
developer dependency groups, post-install legal-data generation, provider
credentials, or ambient executables. The installable product is not one wheel
in isolation: PyPI file-size limits require the large reviewed corpus binaries
to ship in two data companions while the command-bearing distribution keeps
the runtime code, registry, derived data, terminology, and agent assets.

This ADR was authored as proposed and later ratified as accepted (status
flip recorded 2026-07-17): the exact-version three-distribution cohort it
proposes is the contract the accepted
`[[2026-07-15-distribution-installation-readiness-adr]]` builds on and the
implemented packaging surface enforces.

## Decision

Adopt one exact-version Python cohort:

- `cadrumo` is the command-bearing distribution and contains the
  `src/cadrumo` package, excluding tests and split-owned corpus source binaries.
- `cadrumo-data-manuals` owns the manuals corpus source binaries.
- `cadrumo-data-official` owns the AEAT-official and BOE corpus source binaries.
- The command-bearing metadata requires both companions with exact
  `==<cadrumo-version>` pins. The three distributions are mandatory parts of
  one install; there is no advertised slim mode that cannot calculate.
- Both companions contribute to the `cadrumo_data` PEP 420 namespace and are
  disjoint and exhaustive over split-owned files.
- Every artifact lane consumes one prebuilt cohort manifest and verifies wheel
  names, metadata identities, versions, hashes, and companion ownership before
  installation. No smoke lane rebuilds a substitute cohort.

Reviewed data is never downloaded or regenerated after installation. External
browser binaries, provider CLIs, models, credentials, and caches remain
operator-provisioned capabilities rather than package data.

## Constraints

- All three Python projects use the same version. A mismatched companion or a
  non-exact root dependency is a packaging failure.
- Root and companion wheels together cover every required tracked runtime file
  exactly once. Tests, fixtures, and checkout tooling do not ship.
- Installed resource access goes through `cadrumo.core.resources`; consumers do
  not branch on checkout versus wheel paths.
- The sole human command remains `aeat`, bound directly to
  `cadrumo.entrypoints.cli:main`; the MCP command is `cadrumo-mcp`.
- Optional integrations remain capability extras. Their absence produces the
  declared install guidance rather than `ModuleNotFoundError`.
- Clean-install proof uses no taxpayer data, live AEAT mutation, cloud writes,
  secrets, checkout imports, or ambient product executables.
- Publication and channel promotion follow the immutable-cohort evidence
  authority in the distribution-installation-readiness ADR.

## Implementation Evidence

The current repository implements the proposed shape in `pyproject.toml`, the
two `packaging/cadrumo_data_*` projects, and `dev/packaging/python_cohort.py`.
`dev/packaging/smoke_core.py` validates exact pins and cohort identity;
`smoke_split_install.py` proves the joined namespace and complete installed
product; the `packaging-smoke-*` recipes exercise wheel, sdist, extras, browser,
Docker, split-install, and installed-oracle lanes.

These files were the review evidence on which the ratification rested; the
cohort contract they implement is now the accepted authority later
distribution decisions cite.

## Rationale

One exact-version cohort preserves offline legal grounding while respecting
artifact-size limits. Mandatory companions prevent a root wheel from passing
help/version checks yet failing tax work because its corpus is missing. A
single build plus hash-bound reuse makes clean-install evidence attributable to
the bytes that would be promoted.

## Consequences

- Operators receive one functional product even though storage is split across
  three Python files.
- Release tooling must coordinate three immutable Python distributions and
  refuse partial or version-skewed publication.
- Packaging gates cost more than source-tree tests, but they detect missing
  runtime dependencies, omitted data, broken entry points, and split drift that
  a source checkout conceals.
