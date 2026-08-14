---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:53ad7883381679f7f16f6d1a56aab0167a523bde019f753d08cadb633833e4e2'
related:
  - "[[2026-08-14-registry-temporal-coverage-adr]]"
---

# `registry-temporal-coverage` audit: `architecture review of filing-grade legal and temporal authority`

## Scope

The review covered the proposed filing-grade legal and temporal authority decision,
its governing registry-authority, revision-resolution, conformance, and grounding
decisions, the current legal-review and snapshot implementation, the Modelo 390
source topology, the exact failing Modelo 303 and Modelo 390 snapshot unions, and
the proposed S86-S91 and S84 dependency design. The review was read-only; the
decision record was then amended to resolve every finding below while remaining
proposed.

## Findings

### revision-eligibility | critical | legal review alone could promote a pending revision

The draft required an operator-reviewed legal slice but did not require the selected
revision's independent operator signoff. That left the conformance decision's
fail-closed revision backlog outside the production boundary. The ADR now requires
both independent human gates before a filing snapshot exists.

### inspection-type-boundary | high | static work lacked a safe non-filing authority

Static semantic mapping and generation must be able to inspect honest review backlog,
but using `RegistrySnapshot` would either block that work or invite a raw-loader or
test-owned snapshot bypass. The ADR now defines a separately typed inspection
projection from the validated authority, using the canonical resolver and unable to
enter filing consumers.

### modelo-390-epochs | high | the temporal repair did not name the supported source epochs

The open Modelo 390 revision mixes four annual designs and exposes a 2024-only
provision in every selected year. The ADR now requires disjoint 2022, 2023, 2024,
and 2025 epochs, caps the 2025 source, confines the time-bounded provision to 2024,
and refuses unsupported earlier and later years.

### dependency-order | high | filing consumers were not separated from static work

The original execution prose placed generator mapping, filing rendering, and the
annual-summary handoff behind one undifferentiated review boundary. The ADR now lets
S67-S71 and static generation use inspection authority, places the three legal-review
partitions after S87, makes S91 the revision-review and filing-grade closure, and
makes S84 depend on S91.

### attribution-integrity | medium | legal reviewer metadata could name nobody

The legal-review schema contract did not explicitly carry the non-whitespace reviewer
and fixed date-horizon integrity already applied to revision governance. The ADR now
requires both for legal and revision attestations.

### exact-review-partition | medium | the operator campaign lacked an executable denominator

The exact failing target union is twenty references partitioned into nine shared,
nine Modelo-303-only, and two Modelo-390-only references. The ADR now requires the
three sets to be exhaustive and pairwise disjoint before and after one-at-a-time
operator review, while retaining the rule that counts never authorize promotion.

## Recommendations

Keep the ADR proposed until the existing user authorization is mapped through the
owning VaultSpec lifecycle. Implement the typed inspection projection before moving
static tests off filing snapshots. Land the Modelo 390 split before generating the
operator worklists. Treat S88-S91 as human gates: an agent may prepare evidence and
run checks but may not write any operator attestation. Require exact affected filing
snapshots, including the expected Modelo 390 2026 unsupported refusal, before S84 or
filing-instance rendering can close.
