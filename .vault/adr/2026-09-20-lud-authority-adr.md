---
tags:
  - '#adr'
  - '#lud-authority'
date: '2026-09-20'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:df5fa822217870e070a05f367f5e09a9e7130ce28984674f009c999c43419e55'
related:
  - "[[2026-09-20-lud-authority-reference]]"
---

# `lud-authority` adr: `startup dependency provisioning policy` | (**status:** `accepted`)

## Problem Statement

Normal CLI commands require a coherent writable state topology and a published registry authority before application dispatch. The current startup path does not establish both preconditions, while the storage materializer cannot distinguish defaults it owns from explicit operator paths it must not silently create. The startup ownership and default-versus-override policy are costly operational commitments and need one decision before implementation. Grounding is in `2026-09-20-lud-authority-reference`.

## Considerations

- The canonical storage taxonomy, materializer, CLI preflight, and authority reader already exist; `2026-09-20-lud-authority-reference`.
- Authority is shipped or explicitly selected and must never be generated, compiled, or repaired by runtime startup; `2026-09-20-lud-authority-reference`.
- Explicit path overrides express operator ownership, while derived defaults express application ownership; `2026-09-20-lud-authority-reference`.
- Help, version, and other metadata invocations must remain isolated and side-effect-free; `2026-09-20-lud-authority-reference`.

## Considered options

- Create every missing resolved directory, including overrides: rejected because a typo in an explicit path becomes accepted state and masks an operator deployment error.
- Fail whenever any resolved directory is missing: rejected because it makes first-run defaults unusable and abandons the existing idempotent materializer.
- Create derived defaults, require explicit overrides to pre-exist, and require published authority: accepted because ownership determines whether startup may mutate the path.
- Generate or repair missing authority at startup: rejected because it crosses the published-authority boundary and makes runtime depend on authoring tooling.

## Constraints

The implementation reuses the typed taxonomy and `model_fields_set`; it adds no path registry or environment-variable inventory. The configured state root remains the application-owned creation anchor even when its location is selected explicitly; the pre-existing dependency rule applies to explicit taxonomy member paths beneath or outside that anchor. Authority verification uses the canonical published reader and performs no source compilation. Failures derive from core exceptions and cross the existing typed CLI error boundary. Metadata invocations remain exempt. The warm path performs existence checks only and must not rewrite, hash, or fully hydrate authority solely for startup.

## Implementation

Extend the existing storage materialization boundary so taxonomy-derived default directories are created idempotently while explicitly configured directory targets are validated and refused when absent or non-directories. Add a small application provisioning composition that runs this storage check and resolves the published authority descriptor through the canonical authority API. Invoke that composition during normal CLI startup before command dispatch and project its core-derived failures through the existing CLI refusal machinery. Add only focused materializer and startup tests, logging enrollment, and strict per-module type coverage. See `2026-09-20-lud-authority-reference`.

## Rationale

The ownership test is decisive: application-selected defaults are safe to provision, while operator-selected paths are dependencies whose absence must be reported rather than invented. Composing the existing materializer, startup boundary, and authority reader preserves their established responsibilities and avoids parallel path or authority logic. See `2026-09-20-lud-authority-reference`.

## Consequences

Fresh installations acquire the complete default state/cache topology automatically and fail before application work when the shipped authority is missing. Deployments with explicit path overrides receive immediate failure for absent directories. Startup gains bounded filesystem probes on normal commands; metadata performance and behavior remain unchanged. Existing callers that intentionally pass absent explicit directory overrides to `ensure_storage_tree()` must opt into default-style creation or provision those fixtures first.
