---
tags:
  - '#adr'
  - '#product-packaging'
date: '2026-06-28'
modified: '2026-10-11'
body_hash: 'sha256:f7b9ccb8e9e37902403d494a9ec3bc93d6bd456ce91d705819c01522ed492261'
related:
  - '[[2026-06-28-product-packaging-research]]'
  - '[[2026-06-28-product-packaging-reference]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
  - '[[2026-10-03-duplication-remediation-hashing-proof-boundaries-adr]]'
  - '[[2026-10-07-broad-test-failure-repair-corpus-companion-adr]]'
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
- Clean-install proof uses no taxpayer data, live AEAT mutation, cloud writes or
  secrets. Installed-product commands and probes use no checkout product imports
  or ambient product executables. A separately identified controller may use
  explicitly selected, pinned checkout support under the process-role clarification
  below; that support may never enter the installed target's product import path.
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

## Proof process-role clarification (2026-10-03)

Authorized by the user's delegated architect instruction, "make the decisision", and
recorded in `2026-10-03-duplication-remediation-hashing-proof-boundaries-adr`. The
controller/verifier host may use explicitly selected, pinned checkout support and
canonical inward core contracts for orchestration and bookkeeping. Record its actual
interpreter and imported first-party origins; it must not silently obtain support from
the installed artifact under verification or an unrelated checkout. Installed-product
commands and probes remain separate clean, cohort-bound processes with checkout product
imports and ambient executables excluded.

Expected installed-byte integrity calculations remain private and stdlib-based, never
product hashing or target-installed implementations. Expected tax outcomes remain
externally grounded. Existing isolated stdlib payload verification is retained; an
installed entrypoint may be imported by the separate origin-identification probe without
becoming the source of expected integrity calculations. The host is not claimed to be
stdlib-only. One existing core hashing owner serves ordinary tooling, with caller byte
representations unchanged.

The original constraint read: "Clean-install proof uses no taxpayer data, live AEAT
mutation, cloud writes, secrets, checkout imports, or ambient product executables."
The dated clarification identifies the clean installed product/probe and separate pinned
controller to which those import requirements apply. It permits no checkout dependency
in the installed target and no self-supplied expected hashing implementation. Cohort,
companion, resource, public command and publication commitments are unchanged. This
ruling records authority, not completed rollout or a foreign source-write release.

## Scoped amendment (2026-10-07)

Explicitly approved by the user and accepted in `2026-10-07-broad-test-failure-repair-corpus-companion-adr`. This ruling controls current implementation within its stated scope; the preceding text is preserved as decision history.

The mandatory exact-version Python cohort now contains four distributions: cadrumo and three data companions. cadrumo-data-manuals owns manuals binaries; cadrumo-data-official owns aeat_official and eu_official binaries; cadrumo-data-normatives owns only corpus/normatives binaries. The root requires all three companions at its exact version. All four distributions share the version. Companion ownership remains disjoint and exhaustive; all resource paths, source bytes, namespace and immutable-cohort verification constraints remain binding. Prior references to two companions and three distributions describe the earlier partition.

## Scoped amendment (2026-10-11): Windows corpus destination paths

Accepted under the operator's explicit continuation authorization to fix complete application packaging, make real installation and runtime failures fail acceptance, and refine existing checks without duplicate harnesses. This amendment refines physical resource placement for that repair; it grants no release publication or host installation authority.

The real disposable Windows guest's user MSI failed with error 1304 while writing an exact manifest-owned corpus correction sidecar whose destination contains 261 UTF-16 code units; Windows Installer reported final error 1603 before installation ownership committed. Measured payload destinations also exceed the legacy path budget at supported default user and machine roots. This is a package-layout defect independently of the still-unproved precise native error cause. The failed immutable cohort and private failure evidence remain retained in the runtime-process-lifecycle audit.

Permit bounded physical corpus basenames in a new versioned cohort, within the existing resource directory layout and companion ownership. Retain every binary and its byte count and SHA-256, official URL and aliases, original filename, title, retrieval metadata and declared stable source identifier. Update all manifest stored_path and registry corpus_path references coherently. Re-render affected extraction sidecar pairs through their existing canonical owner with preserved extraction units, source digest and attribution; update correction locators and derived identities coherently. No stale aliases, missing evidence, network reacquisition, payload exclusions, semantic edits or mixed-cohort references may conceal relocation.

This is the sole exception to the 2026-10-07 amendment's preservation of all resource paths. Namespace, directory ownership, exact-version pins, exhaustive source coverage, package budgets, canonical resource access and immutable-cohort verification remain binding. Existing accepted history remains intact. Recompute affected legal-input and physical authority identities through complete canonical publication before packaging.

The existing MSI producer must reject excessive installed UTF-16 destination lengths including sidecar suffixes at supported default roots. The actual native maintenance admission must reject an unsupported selected prefix before creating or mutating installation state; producer checks against one builder's defaults do not prove another user's redirected root. Do not shorten the acceptance root, enable OS long-path policy or use unproved MSI extended-prefix/short-name behavior as the repair. Acceptance requires the new complete cohort's actual MSI installation and manager/native authenticated client operation in both scopes; this decision itself claims neither successful installation nor completed rollout.
