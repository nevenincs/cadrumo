---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:a7371695e7867b751da19bdcf891f652acad86352bdd41b4446285d0ff8793aa'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
---

# `tui-architecture` audit: `S173 registry authority remediation`

## Scope

Implementation-time remediation audit for `W03.P20.S173`. The audit covers the
public registry authority owner, its typed capture/current-coordinate contract,
canonical physical-root identity, reset and generation preservation, fork safety,
consumer-census completeness, inert package boundary, and compatibility-surface
deletion. The Step remains open for supervisor review and is not closed by this
artifact.

## Findings

### authority-identity | low | one strict physical-root pair owns keys and domains

`src/cadrumo/domain/calculations/registry/authority.py` resolves both roots
strictly, collapses relative, dot-segment, and symlink aliases, applies native
case normalization, and uses the resulting pair for both the root load-state key
and opaque `ContentDigest` comparison domain. Missing, broken, or non-directory
roots refuse before entering authority state.

### fork-incarnation | low | child state rebuild avoids inherited locks

The after-fork callback and PID guard replace the process nonce, state lock,
reader/reset barrier, root map, generation, and reset epoch without acquiring an
inherited lock. Authorities and typed coordinate values retain a private creator
PID/incarnation binding and refuse inherited access before any inherited instance
lock is touched. The POSIX proof forks during an active authority reader, checks
all inherited refusals, then performs a fresh child load in a different domain.

### typed-currentness | low | raw generation compatibility surface is absent

`read_current_generation` and every caller are deleted. Focused consumers use
`read_current_coordinate` and domain-before-generation comparisons. Reset
succession retains the domain and advances generation, while identity transitions
and A-to-B-to-A observations invalidate the prior authority.

### authority-census | low | generated v1 evidence covers every promised category

`dev/quality/registry_authority_consumer_census.py` derives definition locators
and production, test, fixture, documentation, tooling, annotation, registration,
dynamic-target, package-attribute, and reverse-import transitive consumers. Its
checked JSON and tests refuse derived-field drift without fixed counts.

### modelo-200-fixture | low | EXTERNAL bundled-registry validation blocks setup

The complete focused authority module cannot enter its first test because the
shared worktree has unrelated deleted Modelo-200 export layouts and an invalid
split 2024/2025 Modelo-200 authority. Session-fixture construction raises
`RegistryValidationError` before S173 code executes. The static authority proof,
ruff, basedpyright, generated census check, and census drift tests pass.

## Recommendations

Keep `W03.P20.S173` open for independent review. Re-run the complete focused
authority module, including its POSIX-only real-fork tests, after the external
Modelo-200 worktree is valid. Do not weaken validation or restore the removed
raw generation accessor to bypass that blocker.
