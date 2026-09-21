---
tags:
  - '#adr'
  - '#iva-workflow'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:b25d6596a45ab8ce662c5e9c39d9fc48f7c97bc6e18cdcb8fcdf77f33535135e'
related:
  - "[[2026-09-21-iva-workflow-m303-filing-evidence-authoring-reference]]"
  - "[[2026-09-21-iva-workflow-adr]]"
---
# `iva-workflow` adr: `M303 filing evidence production authoring boundary` | (**status:** `accepted`)

## Problem Statement

Installed Modelo 303 calculation consumes a fully formed filing-instance
evidence envelope, but production has no owner that creates it. Treating the
current plaintext JSON input as authoritative would allow callers to assert
authority-owned and derived facts and would not ground several operator facts in
secure evidence. The ownership gap is measured in
`2026-09-21-iva-workflow-m303-filing-evidence-authoring-reference`.

## Considerations

- The calculation revision is already the encrypted durable owner of the
  validated envelope; another aggregate or draft store is unnecessary.
- Authority, profile and calculation owners already derive part of the
  envelope, while genuine elections and facts still require operator input.
- Nominal evidence references and insolvency without any reference cannot
  establish filing-grade provenance.
- Sensitive financial or taxpayer input must not become a default plaintext
  artifact or appear in diagnostics.

## Considered options

1. Keep the complete external JSON envelope as production truth. Rejected
   because it permits caller ownership of derived facts and unresolved evidence.
2. Add a separate persisted filing-evidence draft aggregate. Rejected because it
   creates another store and lifecycle beside calculation revisions.
3. Add a shared transient application authoring operation that accepts only
   genuine operator assertions and secure references, derives the remaining
   fields through existing owners, and hands the typed result directly to
   calculation. Chosen.

## Constraints

- Authority snapshot, Orden, record design and DANA availability come only from
  the canonical bundled authority.
- Profile scope comes only from the selected secure profile. Calculated results
  and endpoint observations come only from existing application calculation.
- A supplied evidence reference must resolve to an authorized secure record of
  the expected role, taxpayer/profile scope and relevant period. Missing, stale,
  cross-scope, duplicate-conflicting or contradictory evidence refuses.
- No latest-wins precedence, inferred zero, frontend tax arithmetic, test
  fixture import or operator override of derived facts is permitted.
- Optional regimes refuse when their complete evidence contract is not
  available. Refusal of an optional regime must not disable an otherwise
  grounded ordinary Modelo 303 filing.

## Implementation

Extend the existing Modelo calculation application orchestration with a
transient filing-input authoring request. It carries filing identity and period,
typed operator elections or assertions, role-labelled secure references and
expected identities needed to detect stale composition. The operation resolves
references through existing secure owners, obtains authority and profile facts
from their canonical resolvers, derives calculation-owned values, constructs and
validates `FilingInstanceEvidence`, and passes it directly into the existing
calculation-revision persistence flow.

The installed CLI exposes this shared operation through one sensitive input
channel. Standard input is canonical; an explicit file is only a warned
convenience. The CLI never accepts authority-owned or derivable envelope fields,
does not echo the request and returns only sanitized revision identity and
diagnostics. The request is not persisted separately. The validated envelope is
durable only inside the encrypted calculation revision.

The first slice supports the ordinary 2025 Modelo 303 path. Insolvency gains a
mandatory secure evidence identity before it can be enabled. Exemption and
simplified-regime branches are enabled separately only after every assertion and
reference in that branch has an existing secure owner and a complete refusal
contract.

## Rationale

The transient application operation preserves one durable owner while preventing
the CLI from becoming a tax-fact calculator or evidence authority. It reuses the
existing authority, profile, calculation and encrypted persistence boundaries,
closes silent caller precedence, and permits the ordinary installed journey to
advance independently of optional-regime evidence work.

## Consequences

Production no longer depends on a hand-authored complete evidence envelope for
ordinary Modelo 303 calculation. Recalculation creates the normal immutable
calculation revision and preserves earlier evidence through the existing
lifecycle. Optional regimes may remain truthfully unavailable longer, and secure
reference resolution adds explicit failure states, but incomplete or
contradictory evidence can no longer look filing-ready. Existing full-envelope
JSON remains a compatibility-free internal/testing input until removed; it is
not an accepted production authoring source.
## Amendment 1 — Secure operator applicability attestation

Accepted 2026-09-21 under the same IVA implementation authorization. The
initial decision required secure reference resolution but did not identify an
existing owner capable of grounding the mandatory Modelo 390 applicability fact.
The encrypted attachment store is that owner; purchase-invoice evidence and
evidence bundles keep their narrower existing purposes.

The application may admit the operator's typed applicability attestation as
evidence. Admission constructs canonical structured bytes in memory and writes
them directly through the existing encrypted attachment custody path, without a
plaintext staging file. The payload contains a schema version, the closed role
`m303_exonerado_390_applicability`, the asserted value, filing year and period,
a timezone-aware observation instant, and the existing current profile witness:
profile identity, record revision, canonical content digest, schema identity and
schema version. Attachment bucket, identity, digest, capture time and custody
metadata remain owned by the attachment record. Search metadata may repeat only
values derived from the canonical payload.

For the ordinary path, the only admitted value is `not_applicable`. Absence never
implies that value. `applicable` selects the optional exemption branch and must
refuse as unsupported until its activity, endpoint and Modelo 347 evidence
contract is complete.

Resolution loads the referenced attachment from the expected bucket, verifies
custody and digest, strictly parses the canonical payload, and requires the exact
role, asserted value, year, period and current profile witness. The observation
instant may not be future-dated, after capture, or before the covered filing
period closes. Exact-coordinate attestations do not expire merely with elapsed
wall time, but any current profile revision or digest mismatch makes them stale.
Legacy attachments without the typed payload are ineligible and are never
backfilled from filenames, MIME types, notes or free text.

All typed applicability attestations in the same bucket and filing coordinate
participate in conflict detection. Identical-value artifacts may coexist as
separate custody evidence; conflicting values block composition, with no
latest-wins rule. The attachment proves the operator's recorded assertion, not
AEAT acceptance or independent truth. The public CLI may collect the typed
attestation only through the shared application admission operation and returns
a sanitized secure reference; it never manufactures metadata or writes an
intermediate JSON file.
