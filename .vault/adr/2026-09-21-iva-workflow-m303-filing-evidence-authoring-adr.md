---
tags:
  - '#adr'
  - '#iva-workflow'
date: '2026-09-21'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:7fc6486f14fcc4f6a334b9caccda4b91f9fa75583f36e448a8649bd174c4b9e0'
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


## Amendment 2 — Registry-selected ordinary coordinates

Accepted 2026-09-23 under the IVA implementation authorization, refining the first-slice scope rather than reversing it. The ordinary evidence envelope carries three operator-declared header facts: the joint self-assessment election, the non-zero annual volume answer and the Modelo 390 exemption applicability. A filing coordinate admits ordinary authoring and applicability attestation only when it is quarterly and the law-selected Modelo 303 revision for that quarter declares all three facts in its official record design (producer keys `m303.joint_return_elected`, `m303.annual_volume_nonzero` and `m303.exonerado_390_applicable`). Support therefore follows the registry instead of a year constant. Every authored revision from 2022 through `2026-y-siguientes` declares the three facts, so 2026 quarters are no longer refused. The 2026 design's new hydrocarbon-deposit header fact is profile-owned and does not enter the operator evidence. Monthly coordinates and coordinates outside the registry envelope still refuse before custody is touched. Grounding for the per-revision declarations is the registry record design cited by each revision's export layout; no new authority generation or publication is implied.



## Amendment 3 — Period-scoped ordinary evidence and monthly coordinates

Accepted 2026-09-23 under the IVA implementation authorization, refining Amendment 2. Every bundled Modelo 303 record design from 2022 through `2026-y-siguientes` (DP30301, fields 14, 23 and 24 with Notas 3, 4 and 5) scopes the three operator header facts by settlement period, and Orden EHA/3786/2008 art. 7 establishes monthly and quarterly settlement periods alike, each with a last period of the year. The first slice asked for every fact in every period and printed the annual-volume answer where the design forbids it; that wrong output is corrected separately and this amendment aligns the evidence contract with the same rule.

- Coordinates: ordinary evidence is admitted for any quarterly (1T–4T) or monthly (01–12) Modelo 303 period whose law-selected revision declares the three producer keys. Whether a taxpayer may settle monthly is an obligation fact owned outside this evidence; the evidence neither asserts nor infers it.
- Joint self-assessment election (field 14): required in every period.
- Modelo 390 exemption applicability (field 23, Nota 4): asserted and evidenced only in the last period of the year (12 or 4T), where the secure attestation of Amendment 1 is required. In every other period the evidence carries no applicability assertion and no attestation reference, and a supplied attestation refuses rather than being ignored; the record prints `0`.
- Annual-volume answer (field 24, Nota 3): printed only by a filer exempt from Modelo 390 in the last period. The exempt branch remains unsupported on the ordinary path, so ordinary evidence carries no annual-volume answer in any period and the record prints `0`. The exempt branch collects the answer, in the last period only, when it lands.
- Last period is resolved by the canonical `is_last_filing_period_of_year` resolver; its final-period set for Modelo 303 tokens equals the design's "12 y 4T". Declaring per-field period applicability as typed record-design data is a separate registry decision and is not required here.
- Schema: the calculate operation's nested ordinary request becomes a new version carrying the joint-return election and an optional attestation pair supplied as a unit; the request schema version increments, and a pending invocation recorded under the previous version is refused by the pinned-definition check, never migrated or replayed with defaults. The persisted `M303FilingInstanceEvidence` makes the annual-volume answer and the Modelo 390 evidence optional, with the 390 evidence required in the last period. Calculation revisions persisted under Amendment 2 remain valid and keep their content-addressed identity; the values they carry outside the printed scope are retained, never rewritten, and are not printed because export applies the Nota 3 and Nota 4 rules to every revision.
