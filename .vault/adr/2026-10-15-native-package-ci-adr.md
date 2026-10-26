---
tags:
  - '#adr'
  - '#native-package-ci'
date: '2026-10-15'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:7fddfb004311c90f4d772b8268df55521ed6ca3cb5cfe377ebf689b2c526256a'
related:
  - '[[2026-10-15-unit-suite-repair-audit]]'
  - '[[2026-10-13-package-verification-adr]]'
  - '[[2026-06-05-test-topology-refactor-adr]]'
  - '[[2026-10-13-native-agent-adr]]'
---
# `native-package-ci` adr: Explicit native CI input and artifact-owned test lanes | (**status:** `accepted`)

## Problem Statement

The unit suite exposes a native CTest population with no release-prove invocation and a broad package pytest selector duplicating source-owned contracts. Native package builds also require an explicitly selected local cadrumo-agent checkout. Repairing CI requires a durable runner-input and artifact-ownership commitment; the evidence is recorded in 2026-10-15-unit-suite-repair-audit.

## Considerations

The accepted 2026-10-13-package-verification-adr requires actual application-process proofs to use the unmodified CMake stage while source and wheel proofs retain their respective artifacts. The accepted 2026-06-05-test-topology-refactor-adr requires truthful, uniquely owned test populations. Native keychain access and external-tool integration remain measured capabilities rather than assumed properties of every Windows runner.

## Considered options

- Keep CTest local-only and broaden holdouts: avoids runner configuration, but leaves the strict CI coverage defect unresolved and misstates ownership.
- Run all runtime-lifecycle tests against a package or alternate verification launcher: duplicates source/wheel claims and conflicts with the accepted artifact contract.
- Invoke ordinary native verification in Windows prove CI with an explicit local agent input, and give genuine external-tool package proofs a separate opt-in owner: closes native coverage while preserving artifact and capability boundaries. Chosen.

## Constraints

The Windows prove workflow reads repository variable CADRUMO_PACKAGE_AGENT_SOURCE_DIR and passes its value explicitly to the existing CMake cache input of the same name. Missing input fails clearly. Do not add an environment-driven CMake fallback, substitute agent implementation, or implicit checkout/download.

Only tests asserting the CMake stage/manager contract belong to the native package pytest population. Installed wheel entrypoint and source/library contracts retain source/wheel execution. A positive native_package marker may identify the stage cohort; it is not a CI holdout. Preserve every execution and capability marker and strict unique-owner/reachability assertions.

External-tool package integration has a distinct opt-in CTest label and recipe. Ordinary native verification excludes that label and does not claim those proofs passed. A CI lane requiring a usable credential store fails its capability preflight on refusal; it must not silently count skipped proofs as coverage.

## Implementation

We will add an explicit Windows native prove invocation using the selected repository variable and existing CMake build/CTest boundary. Source recipes select runtime-lifecycle cases according to asserted artifact and existing platform/capability conditions. CTest and lane discovery distinguish ordinary verification from the labeled opt-in external-tool recipe using the actual declarations.

These are scoped refinements of native CI invocation and lane ownership. The accepted package-verification and test-topology commitments remain unchanged and require no contradictory wording amendment. Acceptance records the user's all-unit/all-issues authorization and their 2026-10-15 instruction, Use the repository variable; it does not assert implementation is complete.

## Rationale

An explicit repository variable matches the user's selected runner configuration and the existing deliberate CMake source-selection boundary. Separating genuine stage assertions avoids treating fixture dependencies or directory names as artifact ownership. Actual CTest labels and recipe invocations provide auditable coverage without introducing exclusions to make the unit gate green.

## Consequences

Windows native CI needs a maintained cadrumo-agent checkout at the configured path and the capabilities required by the ordinary selected proofs. Prove execution costs increase by native build and test time. External-tool package proofs remain separately executable and visible. A change to the agent delivery model, stage authority, or required CI host capabilities requires reconsidering this decision.
