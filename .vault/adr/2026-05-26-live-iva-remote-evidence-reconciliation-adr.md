---
tags:
  - '#adr'
  - '#live-iva-compensation-wallet'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-research]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
  - '[[2026-05-19-iva-compensation-chain-adr]]'
  - '[[2026-04-12-modelo-303-390-adr]]'
---



# `live-iva-compensation-wallet` adr: `remote IVA evidence persistence and reconciliation authority` | (**status:** `accepted`)

## Problem Statement

The IVA compensation chain needs durable, reloadable AEAT evidence. A live pull
that cannot be stored, reloaded, compared, and attributed to a profile is not a
production authority. Conversely, local recurrence that ignores AEAT maintained
state can produce plausible but legally unsafe Modelo 303 prefill values.

The application therefore needs a durable remote-evidence model that stores
filed-history observations, wallet observations, acquisition manifests, and
reconciliation decisions through the active profile's secure storage. It must
also define how multiyear local recurrence interacts with AEAT evidence.

## Considerations

The secure-object drift research proves that state persistence is a correctness
surface. Some active-profile namespaces contained unreadable rows caused by
test contamination, while current IVA compensation namespaces were readable.
The correct response is not blind trust in storage, but runtime-owned
repositories, reload tests, fail-closed degraded-source reporting, and privacy
guards.

The live IVA research separates AEAT wallet evidence from local recurrence and
taxpayer override. The Modelo 303/390 ADRs define periodic and annual IVA
calculation relations, but they do not make local calculations superior to
remote AEAT state.

The secure-storage ADR defines `StorageRuntime` as the production boundary for
profile-bound sensitive state. Remote IVA evidence belongs behind that boundary.

## Constraints

Remote IVA evidence must be stored only through active-profile runtime-owned
repositories or explicit test isolation helpers.

No private taxpayer values from live AEAT reads may be committed into source,
tests, fixtures, plans, ADRs, audits, logs, or snapshots.

Local recurrence may diagnose and fallback, but it may not silently override
available AEAT evidence. Unresolved divergence blocks filing-grade output.

Tests must use production calculation and repository services. They must not
mirror IVA arithmetic in test code or use private live values as expected
oracles.

## Implementation

Persist four separate evidence families:

1. Filed-history observations, including model, year, period, filing status,
   source locator, capture timestamp, and parsed filed values when available.
2. Wallet/cartera observations, including source period, generated amount,
   applied amount, pending amount, source locator, and capture timestamp.
3. Acquisition manifests, including requested scope, typed outcomes, redacted
   diagnostics, and evidence ids.
4. Reconciliation decisions, including authority source, local recurrence
   value, remote evidence references, divergence status, operator override
   status, and blocking state.

Reload APIs must support latest evidence and historical evidence without live
authentication. Calculation services consume reloaded source observations and
persisted reconciliation decisions, not live browser adapters.

Multiyear IVA recurrence must model source period, generated amount, applied
amount, pending amount, remaining balance, and expiry-review state. It must
compare against persisted AEAT evidence and classify exact match, AEAT higher,
AEAT lower, stale remote evidence, incomplete local evidence, missing wallet,
filed-history-only, and override-required states.

## Rationale

This architecture keeps the legal and technical authority layers separate.
AEAT evidence is the binding external state when available. Local recurrence is
still valuable because it explains and audits that state, detects divergence,
and supports fallback when the live wallet surface is inaccessible.

Persisting evidence through secure profile storage makes the system usable
without authenticating on every calculation and gives the operator a durable
audit trail. Keeping acquisition manifests separate from calculation decisions
prevents a live browser success from silently becoming a filing value.

## Consequences

The calculation path must become more conservative. Missing, stale, unreadable,
or divergent evidence can block export and filing-grade verification.

The persistence model grows multiple namespaces and reload APIs. Those
namespaces must participate in secure-storage integrity diagnostics and test
isolation guards.

Some tests will be longer because they need repository-backed multiyear
fixtures. That is acceptable; the alternative is tautological arithmetic tests
or private taxpayer-data oracles.
