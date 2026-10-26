---
tags:
  - '#adr'
  - '#registry-completeness-closure'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:c8b06c7184a21921658f4812c0511a77a669a1e667944c93a89b3ca1b86f6f48'
related:
  - "[[2026-08-25-registry-completeness-closure-s33-two-channel-export-proof-research]]"
  - "[[2026-08-24-registry-completeness-closure-adr]]"
---
# `registry-completeness-closure` adr: `S33 two-channel filing export proof` | (**status:** `accepted`)

## Problem Statement

S33 cannot honestly obtain a repository-owned production-emission entry, yet the parent completeness predicate must not be weakened. The related S33 research establishes distinct structural and confidential-value evidence domains.

## Considerations

- The parent completeness ADR requires filing-grade emitted-byte proof and explicit refusal.
- The generator-authority ADR keeps pinned official layout/source bytes and the sole canonical writer authoritative.
- Sensitive custody prohibits repository persistence of taxpayer values, payloads, and instance-derived acceptance digests.

## Considered options

- **Official non-sensitive specimen corpus only. Rejected as sufficient proof.** It can prove a public specimen but not source-owned operator value arrival.
- **Two-channel conformance plus secure replay. Chosen.** It proves layout/writer mechanics without taxpayer fixtures and proves real production value arrival under encrypted custody.
- **Explicit predicate demotion. Rejected.** It weakens the parent filing guarantee without an evidenced capability fact.

## Constraints

- The denominator remains dynamic; current counts are observations, not policy.
- Conformance vectors contain only classified non-sensitive boundary inputs. They are never taxpayer truth, source-owned calculations, filing payloads, or accepted payload-hash authority.
- Official source bytes, selected layout, offsets, semantic map, render profile, and generated provenance remain authoritative layout facts.
- Secure replay reads one approved source-owned calculation revision and matching secure evidence through existing custody. Plaintext values, emitted bytes, payload digests, and instance-derived hashes must not enter the repository, CI artifacts, generated tree, or logs.
- Every successful proof uses the sole production `export_draft` path; no parallel writer is permitted.

## Implementation

Add a typed proof port with two mandatory receipts per eligible filing revision. The conformance receipt runs the canonical writer against a declarative non-sensitive vector and proves law-selected layout, official source identity/bytes, generated provenance, map/profile identity, extent, and distinct official literal offsets. It proves geometry and renderer behavior only.

The secure replay receipt binds an approved calculation revision, source-owned draft, matching producer snapshot, selected layout, and custody provenance. It invokes the same writer and verifies real value arrival, applicability, repeated-record order, extent, and source-pinned probes. Payload and taxpayer-derived digest remain transient or encrypted operator evidence; any external receipt exposes only non-sensitive revision/layout/provenance identity and pass/fail attestation.

CI runs conformance for every dynamically selected filing revision and fails on missing official source, provenance, vector, canonical-writer proof, or unrecorded refusal. Filing-grade release additionally requires a current secure replay receipt; CI cannot waive it because CI lacks taxpayer custody. Implementation waves are: proof-port/custody, dynamic provenance/vector enrollment, and rerun of S33 as a dual-channel gate. The 41 missing manifests, 25 currently probe-ready revisions, eight no-producer-key revisions, and M200 fixture debt remain explicit work.

## Rationale

This split preserves the parent predicate and confidential custody: CI can repeat structural conformance, while actual source-owned acceptance stays in its only legitimate secure context. Specimens may strengthen conformance but cannot substitute for replay; demotion merely relabels the gap.

## Consequences

S33 remains open until both receipts exist for every dynamically selected filing revision. No layout, producer, fixture, or export gains a filing claim merely from this decision.
