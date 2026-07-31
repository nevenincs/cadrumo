---
tags:
  - '#adr'
  - '#arch-remediation-data-budget'
date: '2026-07-02'
modified: '2026-07-22'
body_hash: 'sha256:9cbdf2eb9741448d6a486b40703d30208ee6d1fda364e946a6dfcd2ae205f5b6'
related:
  - '[[2026-07-02-aeat-architecture-review-audit]]'
  - '[[2026-07-02-arch-remediation-program-adr]]'
  - '[[2026-05-15-corpus-registry-packaging-adr]]'
  - '[[2026-07-06-arch-remediation-data-budget-research]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
---

# `arch-remediation-data-budget` adr: `Whole-tree and split-distribution data budgets` | (**status:** `accepted`)

## Problem statement

This architectural decision record (ADR) governs Cadrumo's whole-tree and split-distribution data budgets. Cadrumo retains its reviewed legal corpus, registry, terminology, and agent data as one logical installed cohort. Cadrumo requires two exact-version companion wheels and offers no optional slim mode. Offline verification covers bundled reviewed grounding without claiming infallibility.

During authoring and review, check bundled authoritative text first. Cross-check every numeric amount or rate against current consolidated Boletín Oficial del Estado (BOE) or Agencia Estatal de Administración Tributaria (AEAT) text. Typed observations carry registry-provided source and legal references. Each legal entry resolves to authoritative corpus evidence.

The ADR governs maintainers and release reviewers. Continuous integration (CI) enforces it through source-budget and real-artifact packaging gates. The gates require no end-user feature setup, credentials, or live AEAT access.

## Considerations

The whole-tree byte-accounting universe is the shipped-data source tree treated as one logical product, excluding every `tests/` subtree. Byte accounting measures this live, test-excluded tree. Packaging tests prove tracked artifact ownership separately. That ownership doesn't define the whole-tree byte-accounting universe.

The corpus-binary slice contains shipped files under `corpus/` with `.docx`, `.pdf`, `.xls`, `.xlsm`, `.xlsx`, or `.zip` extensions. The runtime slice is its exact complement. These slices are disjoint, exhaustive, and sum exactly to the whole-tree byte-accounting universe.

Separate source limits control different risks. The whole-tree ceiling controls aggregate product growth. The runtime ceiling exposes growth in derived, registry, terminology, and agent data. The aggregate corpus-binary ceiling controls uncompressed source growth.

The Python Package Index (PyPI) per-file cap controls each companion wheel's compressed upload size. Passing one limit doesn't prove that the other limits pass.

## Considered options

- Adopt the chosen ceilings: raise the whole-tree limit to 625 mebibytes (MiB) and the runtime limit to 270 MiB. Explicitly ratify the unchanged aggregate 380 MiB corpus-binary limit. Preserve current ownership and the strict PyPI per-file cap. The `2026-07-06-arch-remediation-data-budget-research` record quantifies the remaining margin for all three governed source-tree budgets and both companion wheels.
- Rebalance binary ownership now: rejected. Rebalancing changes the physical partition without reducing logical product size.
- Move derived runtime data into companion wheels: rejected. This would violate ownership boundaries merely to pass a budget gate.
- Remove reviewed data or offer a slim mode: rejected. Either choice would weaken the mandatory cohort and its bundled legal grounding.

## Decision

Keep four complementary limits:

- the complete test-excluded `src/cadrumo/_data` tree stays at or below 625 MiB;
- the runtime slice stays at or below 270 MiB;
- the aggregate corpus-binary slice stays at or below 380 MiB; and
- each `cadrumo-data-*` companion wheel stays below the accepted PyPI per-file cap of 100 megabytes (MB), or 100,000,000 bytes.

The three source-tree limits use uncompressed byte sums, where one MiB equals 1,048,576 bytes. The runtime and corpus-binary slices partition the whole-tree byte-accounting universe exactly.

Packaging tests independently prove tracked artifact ownership. The two companion-wheel ownership sets are disjoint and exhaustive over tracked split-owned binaries. The root wheel retains all tracked runtime data after removing tests and companion-owned binaries.

Companion packaging tests compare live build-hook scans with expected sets of tracked files. The parity check fails if a scan finds an untracked shipped file.

## Constraints

Reviewed corpus, registry, terminology, and agent data remain available to the installed cohort. Budgeting can't weaken legal grounding. The root wheel requires both companion wheels at its exact version. No slim mode exists.

Companion ownership remains disjoint and exhaustive. Derived corpus surfaces remain in the root wheel. Raising a ceiling or changing ownership requires reviewed ADR authority. This ADR forbids silent constant changes.

## Implementation

This ADR defines the architecture. `2026-07-06-arch-remediation-data-budget-research` records supporting evidence.

`src/cadrumo/tests/test_data_size_budget.py` is the source-tree byte-budget authority. It excludes every `tests/` subtree and defines the live byte taxonomy, 625/270/380 MiB ceilings, and exact partition. It doesn't prove tracked ownership or compressed artifact sizes.

`dev/packaging/tests/test_cadrumo_data_distribution.py` proves tracked companion disjointness, exhaustive parity, real builds, exact versions, and the strict PyPI per-file cap. Root packaging helpers and tests inventory all tracked files under `src/cadrumo/_data`. They remove test files and companion-owned binaries from the expected root set. The built root wheel's complete `_data` member set must equal the expected runtime set.

`pyproject.toml` configures the packaging boundary; real tests prove the configured root and companion boundaries. Three ceiling assertions report the actual MiB value and ceiling. Partition failures report the exact byte operands.

Any ceiling raise, distribution split, or packaging boundary change requires reviewed ADR authority. For runtime breaches, remove dead derived data or justify the growth. Don't move incompatible runtime data merely to pass.

Repartitioning addresses per-wheel distributability, not logical total or aggregate corpus-binary growth. The packaging gate fails any companion wheel measuring 100,000,000 bytes or greater. CI encodes no lower warning threshold.

Audits preserve provenance. Escalation follows the reviewed ADR workflow.

## Rationale

The isolated feature measurement and real builds recorded in `2026-07-06-arch-remediation-data-budget-research` quantify the remaining margin for all three governed source-tree budgets and both companion wheels. Every governed limit passes. Immediate repartitioning is therefore unwarranted.

The chosen option accommodates complete supported-period hydration while preserving valid ownership and mandatory exact-version companion wheels. The exact byte partition prevents growth from hiding between source slices. Independent tracked artifact parity prevents the physical split from evading those source budgets.

## Consequences

Bundled reviewed grounding remains available offline. External tools, credentials, and caches remain operator-provisioned. The root wheel and its two exact-version companion wheels form one product.

The product supports no slim mode. Budget growth and ownership changes require visible, reviewed decisions.

The product's download and storage requirements remain. Promotion must coordinate three immutable, version-matched artifacts. Preflight validation rejects incomplete pre-promotion cohorts and refuses overwrites.

PyPI multi-file uploads are not atomic. These checks reduce but don't eliminate the risk of partial publication.

Every release and each CI run enrolled in the real-artifact packaging gates pays the build-and-measure cost. Failed gates can block campaigns or releases. Resolution may require a new packaging boundary, another companion wheel, or a reviewed ceiling increase. This friction is an intended control.
