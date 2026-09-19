---
tags:
  - '#adr'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:4c9c4ba9872623291b6fa90ea913eec346f7652ae4117b64cfd5172c542f258c'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-research]]"
  - "[[2026-08-22-secure-storage-performance-hardening-reference]]"
  - "[[2026-08-13-secure-storage-hardening-successor-adr]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `secure-storage-performance-hardening` adr: `command-scoped loading and pure secure-storage reads` | (**status:** `accepted`)

## Problem Statement

Small read-only profile commands inherit startup and storage work belonging to
unrelated capabilities. A governing boundary is required so each command loads
and validates only the authorities needed for its declared result without
weakening custody, integrity, durability, or public-facade contracts.

## Considerations

- Startup cost and populated-listing cost are separate optimization domains;
  `2026-08-22-secure-storage-performance-hardening-research`.
- Existing facade and profile-projection decisions remain authoritative; this
  decision narrows when their implementations load dependencies or enter
  custody workflows.
- Listing is discovery, not authentication, inspection, recovery, or repair.
- Performance work must preserve refusal semantics and authoritative validation.
- Portable structural gates accompany calibrated latency budgets;
  `2026-08-22-secure-storage-performance-hardening-reference`.

## Considered options

- **Retain eager composition and tune individual functions:** rejected because
  unrelated dependency construction and custody traversal remain contractual.
- **Import private lightweight modules from handlers:** rejected because this
  bypasses canonical facades and creates a second consumption boundary.
- **Add a plaintext cache/manifest or background warm-up:** rejected because it
  creates another authority or hides rather than removes work.
- **Trust commit markers or directory names alone:** rejected because it drops
  label provenance, identity, current-format, and no-follow guarantees.
- **Demand-load public dependencies and add a pure authoritative summary
  inventory:** accepted because it removes unrelated work while retaining
  validation at owning boundaries.

## Constraints

The accepted custody, secure-storage, profile-state, and lifecycle ADRs are
stable parents. Their formats, cryptographic authority, transactions, label
ownership, encrypted facts, and destructive-cutover rules do not change.

The public package facade remains the sole cross-package application boundary.
Lazy dispatch changes import timing, not public names, schemas, errors, or layer
direction. Private cross-package imports remain prohibited.

Inventory remains anchored to the canonical capsule root and preserves
retired-layout refusal ordering, canonical UUID recognition, bounded parsing,
strict current commit validation, UUID-bound label provenance, deterministic
ordering, and refusal of links, reparse points, traversal, malformed members,
and unsupported schemas.

Listing must not unwrap a DEK, derive a key, access keyring/session state, read
password or recovery envelopes, authenticate a sentinel, open encrypted facts,
run recovery, publish a label head, materialize topology, or repair a projection.
Those operations remain with explicit owning commands.

Concurrent publication, deletion, or label change must produce either a summary
proven coherent within one anchored observation or a typed degraded/concurrent
result, never a mixed-generation summary or incidental repair.

Performance tests use real subprocesses, filesystem adapters, and persisted
capsules. Mocks, monkeypatches, skips, exact-count allowlists, and single-sample
host-specific thresholds are not authoritative.

## Implementation

The CLI becomes demand-loaded from bootstrap through handler execution. Command
registration retains lightweight metadata and loader references. Resolving
`config profile list` imports its own payload contract and the public inventory
symbol, not calculation registries, filing engines, certificate adapters,
unrelated config payloads, or broad workflow aggregators.

Each executable callback owns one immutable execution policy, including its
storage write route. That callback-attached declaration is the sole live
authority for profile-bound and bootstrap-root routing; the former hand-kept
verb-path catalogue, prefix matcher, mutation heuristics, exports, and fallback
defaults are deleted. This supersedes earlier ADR and reference clauses that
prescribed catalogue enrollment. Missing or invalid callback policy refuses
dispatch rather than being interpreted as state-free or non-profile-bound.

Application facades use explicit PEP 562 lazy maps. Heavy Pydantic contracts
move to cohesive sibling modules and construct only when requested. A command
that genuinely needs registry or engine authority pays that cost on first use.

The profile boundary exposes immutable `ProfileSummary` and a dedicated summary
inventory containing only UUID, authenticated label, caller-joined active state,
and minimum provenance for a recognized current capsule observation. It cannot
authenticate, authorize mutation, expose encrypted facts, or imply custody health.

Persistence implements inventory as a pure read: retired-layout refusal first,
canonical no-follow candidate enumeration, one recognized commit per observation,
and a UUID-bound read-only label witness. Label-head pure verification and repair
are split. Helpers consume the recognized witness instead of reopening records.

The active pointer is read once and joined in memory. Rendering consumes the
summary and must not resolve storage again. Read-only settings/path resolution is
separated from directory, permission, log, journal, and topology materialization.

Verification layers quiet-runner median budgets, import-graph exclusions,
real-adapter scaling/read-count observation, negative capability gates,
filesystem before/after assertions, and adversarial filesystem/concurrency cases.
Full unlock, recovery, inspection, and repair suites retain stronger custody paths.

## Rationale

This option removes work at its two owners: dependency amplification through
demand-loaded public facades, and storage amplification through a purpose-built
read projection. It improves empty and populated behavior without weakening
validation or inventing a cache.

Every alternative fails a knockout constraint: private imports violate the
facade, marker-only scans weaken provenance, manifests create another authority,
and tuning the full aggregate preserves the category error that listing is a
custody workflow. The accepted separation follows the grounding in
`2026-08-22-secure-storage-performance-hardening-research`; implementation seams
are defined by `2026-08-22-secure-storage-performance-hardening-reference`.

## Consequences

Profile listing becomes proportional to requested summaries and does not pay for
unrelated capabilities, cryptographic custody, encrypted facts, or repair. Empty
read commands cease materializing storage or logging topology.

Import cost moves to the first command genuinely needing each capability. Heavy
commands may not immediately become faster, but their cost becomes attributable.

The repository gains a smaller read contract beside full inspection and mutation.
This is surface separation, not duplicated authority. Pure label verification
and explicit repair become distinct; callers no longer receive incidental repair.

Explicit lazy maps and lightweight contract modules add maintenance obligations.
Public-surface parity, forbidden-import, and layer gates prevent missing exports,
cycles, and shortcuts. Concurrent changes may yield typed transient degradation,
which truthfully preserves pure-read semantics. Latency budgets require controlled
runner calibration; structural, side-effect, capability, and scaling gates remain
portable.
