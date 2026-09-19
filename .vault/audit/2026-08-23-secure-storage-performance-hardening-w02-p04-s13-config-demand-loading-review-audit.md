---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:19a7c33a670fe48629cc5a7626034ed02ed33c5a8ba882c451219b4b78d22ea3'
related:
  - '[[2026-08-22-secure-storage-performance-hardening-plan]]'
---

# `secure-storage-performance-hardening` audit: `w02 p04 s13 config demand loading review`

## Scope

Audit the complete `config` registration tree after conversion to nested lazy
targets, including exact path ownership, sibling-import isolation, repeated
materialization, localized metadata parity, facade behavior, and the measured
`config profile list` cold path.

## Findings

### target-identity | high | Owner labels did not prove the registered callable

The first implementation derived owner strings from a shared callable and its
test compared against a separate manifest. It could not reject a callable that
forged the same module and qualified name. The final gate inspects the actual
frozen target returned by the live registry and requires factory identity with
the distinct path-bound `ConfigCommandTarget`. A planted same-owner impostor
fails.

### sibling-isolation | high | Google subfamilies shared eager payload imports

The first folder target imported credential-source, sync-calculation, and
general Google payload modules. Folder registration and payload contracts were
split at their real ownership boundary. Fresh `google folder get --help` now
imports only folder ownership and shared refusal support.

### repeatability | high | Registrar-backed builders duplicated global mounts

Repeated full-tree materialization mutated shared Typer registrars. Cached
source builders now mount each legacy registrar exactly once. Identity, command
set, group set, and double-walk tests remain stable without duplicates.

### facade-boundary | high | Compatibility shells misrepresented live groups

Synthetic `profile_app` and `repair_app` shells did not preserve complete group
semantics. They were deleted under the no-legacy rule; consumers now resolve the
live command path or a truthful lazily owned export.

### metadata-oracle | high | Generated callback metadata was stale

The localized materialized-tree projection was regenerated after callback
movement. The authoritative check and exact live/source projection now pass.

### inspection-api | medium | Mutable registration state escaped through the audit API

The initial inspection helper returned a live `LazySubcommand`, allowing a
caller to trigger load and mutate its cache. The final public helper returns
only its immutable `LazyNodeTarget`.

### attributed-contracts | low | Two reported refusals predate S13

The immediate pre-S13 snapshot and current tree both refuse the isolated
preflight test with `REFUSED_PROFILE_AUTHENTICATION`. Both also pass the same
nine manager-routing contracts, which explicitly route a host without a
full-screen frontend to the scripted wizard. These contradictions are not S13
regressions and were not falsely claimed as fixed.

## Recommendations

Approve S13 after the final independent review confirms the immutable target
projection. Carry profile-inventory execution purity into W03 and separately
reconcile the pre-existing authentication/refusal contradictions against the
authoritative security contract.
