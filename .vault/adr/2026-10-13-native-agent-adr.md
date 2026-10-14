---
tags:
  - '#adr'
  - '#native-agent'
date: '2026-10-13'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:6f48ee9b1ab233bb1ff630201684a1334419df4eb558a96d983c3c35cb4d1f96'
related:
  - "[[2026-10-13-native-agent-audit]]"
  - '[[2026-10-13-canonical-environment-application-internals-adr]]'
---
# `native-agent` adr: `CMake owns the private agent dependency` | (**status:** `accepted`)

## Problem Statement

The native package lacks a build owner for the private agent, while the desktop development lane names an external source checkout. The owner explicitly requires acquisition, construction, installation, uninstall, rebuild and checksum operations through CMake, and agent verification against the built custom app environment.

## Considerations

The native-agent audit identifies the missing dependency owner, external-checkout launch and duplicate configure inventories. The interpreter-foundation ruling already establishes CMake output ownership, package isolation and `cadrumo/site-packages`. The live-agent-evaluation ruling requires exercising a verified built package rather than a development environment.

## Considered options

The owner clarified the source choice: CMake accepts a configurable local project folder through the cache-only variable `CADRUMO_PACKAGE_AGENT_SOURCE_DIR`. (Amended 2026-10-13 under `2026-10-13-canonical-environment-application-internals-adr`; before that this read: "CMake accepts a configurable local project folder through `CADRUMO_AGENT_SOURCE_DIR`.") No source SHA pin, repository download or Git operation is involved. A public package release contradicts the existing owner ruling. Developer checkout launches and test-time installation contradict this task's explicit instructions.

## Constraints

Acceptance basis: the owner's direct 2026-10-13 instruction to integrate cadrumo-agent into the native CMake build and dependency lifecycle, with all agent integration tests using the deployed custom environment. No additional authority is inferred for hosted-data, credential, consent or launcher capabilities.

Only CMake build targets produce the private agent wheel. Service/native consumers and test runners consume an already-built package and never install it, download it or import an external checkout. The configured source directory and computed wheel checksum enter build receipts and package provenance. Agent third-party dependencies have exact versions and required hashes, constrained by Cadrumo's existing dependency versions; mismatches are refusals.

This settles the open source-provisioning choice in the proposed desktop-agent-host design. It replaces the external-checkout topology in the proposed desktop-agent-host live-lane record for this authorized build and test scope. Those records remain proposed and their unrelated authority choices remain unresolved. The accepted live-agent-evaluation built-package commitment is reused unchanged.

## Implementation

CMake selects the local source directory through cache-only `CADRUMO_PACKAGE_AGENT_SOURCE_DIR`, builds the private wheel in `agent_project`, composes its hashed dependency closure in `python_dependencies`, installs the wheel in `python_product`, and assembles the canonical custom site-packages. Explicit install, uninstall, rebuild, checksum and lock-update targets retain their existing lifecycle and source/checksum receipts.

The same package declares `cadrumo-agent-service` with fixed Python entrypoint `cadrumo_agent_service.main:main`, separate from the agent image. Desktop supervises that service; the service consumes the bundled agent image and owns its version/catalog/store/start invocations and contained tree. Neither the tax root `src/cadrumo`, `aeat`, nor `src/cadrumo_runtime` imports or starts cadrumo-agent. Runtime owns generic login/custody/authorization; neutral client contracts live in `src/cadrumo_client` and MCP in `src/cadrumo_harness`.

Package integration proofs use the assembled service/agent/relay images and actual outer service ready/admin and inner hosting v1 contracts. Existing CTest import/version/dependency/checksum probes remain package-integrity mechanisms, not proof of a hosted conversation. Sharing a locked wheel cohort is a build choice and grants no tax/runtime agent orchestration authority. The current user constraint permits no test or build invocation for this migration.

## Rationale

One build graph preserves a reviewable dependency identity and prevents test results from depending on another checkout or an ambient virtual environment. A supplemental native lock preserves the Python distribution's current core closure and avoids publishing the private agent. Exact shared-version constraints prevent independently resolving incompatible copies into one interpreter.

## Consequences

Builds need the configured local agent folder, and the package has the agent's additional runtime dependencies. Source changes rebuild through CMake; dependency lock updates remain explicit maintenance actions. Native relocation and installed-package import evidence must pass before claiming delivery; decision acceptance alone proves neither runtime service readiness nor UI behavior.

## Boundary amendment 2026-10-14

Authorized by the user's explicit service/harness/native migration instruction. Original acceptance/proposal status, dated rulings and quotations remain unchanged. This amendment sets ownership obligations; it is not evidence of packaged or live acceptance. The current migration runs no tests and only the coordinated import-linter gate.

### Former implementation and ownership (historical)

> ## Implementation
> 
> We will select the local source directory at CMake configuration and build its wheel in `agent_project`, compose its dependency closure in `python_dependencies`, install its wheel in `python_product`, and assemble it into the canonical custom site-packages. Explicit install, uninstall, rebuild, checksum and dependency-lock update targets own their lifecycle. Uninstall removes generated dependent product and staged payloads so the next authorized build reconstructs a coherent package. CTest runs the installed agent import, version, dependency and checksum probe through the application's own interpreter. It also launches the agent the way the runtime does, `-m cadrumo_agent.cli.main serve` on ephemeral ports, waits for the ready line, and stops it (amended 2026-10-13 under `2026-10-13-package-verification-adr`).
> 
