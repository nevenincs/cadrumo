---
tags:
  - '#adr'
  - '#release-readiness-gate'
date: '2026-07-04'
modified: '2026-07-17'
related:
  - '[[2026-07-06-release-readiness-gate-research]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
---

# `release-readiness-gate` adr: `Immutable-candidate soak and rollback policy` | (**status:** `accepted`)

## Current authority amendment (2026-07-20)

The accepted `[[2026-07-20-release-asset-transport-adr]]` now governs the
storage substrate for the cohort and evidence records this policy consumes:
they ride draft GitHub Release assets with per-run provenance manifests
instead of GitHub Actions artifact storage. The soak and rollback policy is
unchanged — soak reruns, readiness, publication, and rollback continue to
bind the same cohort manifest and SHA-256 values; only where those bytes are
stored between workflows moved. The 12-row evidence contract and the
self-hosted macOS queue/skip doctrine are recorded in the 2026-07-20
amendment of `[[2026-07-15-distribution-installation-readiness-adr]]`.

## Problem Statement

A release needs an observation window and a rollback response in addition to
construction and installation gates. The current distribution architecture now
supplies the missing authority: one immutable, hash-bound cohort is built once,
tested through real acquisition paths, and promoted by one manual GitHub Actions
OIDC workflow. Earlier local-only publication and separate beta-project premises
are obsolete and are not part of this decision.

## Decision

The distribution-installation-readiness ADR is the release evidence and
publication authority. This ADR adds two policies to that authority:

1. A non-hotfix cohort that has completed all pre-publication blocking rows is
   held unchanged for a 48–72 hour release-candidate soak. During the soak,
   scheduled or operator-triggered lanes rerun the cohort-bound installed CLI,
   MCP, split-package, and applicable client/platform proofs against the same
   hashes. Any blocking regression invalidates the cohort; it is never repaired
   in place.
2. Rollback never republishes different bytes under an existing version. It
   stops channel promotion, marks affected acquisition guidance unavailable,
   yanks or disables the bad immutable version where the channel supports that
   operation, and restores pointers to the last fully evidenced cohort. A fixed
   release is a new version and a new cohort.

There is no `aeat-cli-beta` product and no local substitute for cohort staging.
Staging is an evidence state of the immutable Cadrumo cohort, not a parallel
distribution identity.

## Constraints

- Readiness, soak, publication, post-publication verification, and rollback all
  bind the same cohort manifest and SHA-256 values.
- The soak cannot be satisfied by source-tree tests, help/version probes,
  rebuilt artifacts, or an unrelated newest evidence file.
- An unavailable required client or platform row blocks the claim; it does not
  become a passing skip.
- Emergency hotfixes may shorten the elapsed soak only with an incident record,
  explicit release-owner approval, and every applicable functional and
  acquisition gate green before publication.
- Rollback commands that mutate external channels remain explicit manual
  release-owner actions. Diagnostic recipes may print the exact procedure but
  do not silently push, publish, or yank.

## Implementation

The immutable cohort manifest and result records defined by the distribution
ADR carry the release-candidate identity. Release readiness reads the current
cohort's complete blocking record set and its soak timestamps. The sole publish
workflow verifies those records and hashes before promotion and never builds.
Post-publication jobs acquire from every advertised channel and rerun the same
grounded installed-artifact oracle.

Rollback documentation and commands name the affected version, cohort digest,
channels, last known-good cohort, and required operator actions. README and user
documentation promotion remains gated on successful public acquisition; when a
channel is withdrawn, its guidance is withdrawn in the same incident response.

## Rationale

Soak is useful only when it observes the bytes that may ship. Rollback is honest
only when it acknowledges immutable registries and produces a new version for
new bytes. Binding both to the accepted cohort authority removes the earlier
split between local checklists, speculative beta infrastructure, and a release
workflow that could rebuild independently.

## Consequences

- Normal releases take longer, but regressions surface before broad promotion.
- A bad published version remains part of immutable history even when yanked;
  the evidence chain records why it was withdrawn and which cohort replaced it.
- Release ownership stays human and explicit while construction, evidence, and
  publication authority remain singular and machine-verifiable.
