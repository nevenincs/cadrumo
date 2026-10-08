---
tags:
  - '#adr'
  - '#registry-completeness-closure'
date: '2026-10-05'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:838e712212f9564118fb214e909f8ca01ec2852213baabefe8a2d6fa7cee35b5'
related:
  - "[[2026-10-05-registry-completeness-closure-native-and-communication-proof-research]]"
  - "[[2026-08-25-registry-completeness-closure-s33-two-channel-export-proof-adr]]"
  - "[[2026-08-24-registry-completeness-closure-adr]]"
---

# `registry-completeness-closure` adr: `Prove existing communication and native XML exports through their production owners` | (**status:** `proposed`)

## Problem Statement

The current mandatory two-channel proof cannot represent M145's existing local communication exporter or M100's native XML provenance. Its strict Period/approved-calculation/export_draft/positioned-probe contract refuses those purposes before an actual production proof can run. The release must remain refused until both channels are real; changing calendar periods or inventing a fixed-width manifest would conceal the defect. See `2026-10-05-registry-completeness-closure-native-and-communication-proof-research`.

## Considerations

The application already separates M145 communication from AEAT filing and already renders M100 XML through export_draft. Their production owners and source validators must remain authoritative. A proof schema change needs explicit versioning, strict purpose/transport binding and migration/refusal rules. Current encrypted source access is independently unavailable; this decision cannot supply an operator approval or a secure replay receipt. Historical M145 foundation coverage referenced by older research has not yet been reconciled.

## Considered options

- Keep the present positional filing-draft-only proof. Preserves its wire contract but leaves existing communication/native declarations unprovable.
- Broaden Period or disguise native XML as positioned fixed-width evidence. Rejected: both alter the meaning of the selected authoritative source/purpose.
- Exclude these declarations or waive a channel. Rejected: this weakens the completeness claim.
- Extend the existing proof with closed production-purpose and native-probe variants. Proposed: retain the guarantees while using each existing canonical owner.

## Constraints

Both public conformance and current encrypted source-owned replay remain mandatory for every eligible declared revision. No grade demotion, eligibility exception, new writer, parallel authority loader or caller-authored success is permitted.

Ordinary filing draft evidence retains the current approved-calculation, matching draft/producer and export_draft requirements. M145 must carry its actual communication period and source-owned communication record identity, pass the existing communication validator and invoke export_m145_communication_record. It must never acquire filing, deadline, portal, submit or justificante semantics.

Native XML evidence must bind the actual official dictionary/XSD, the exact selected layout, its reviewed path overrides, compiler inputs and canonical generated provenance. Its probes check source-defined XML structure/literals and schema validation; they may not claim byte positions belonging to fixed-width records. Unknown purpose, transport, probe kind or schema version is refused. Existing stale-pin, output-digest, source-identity, scope and custody mismatches remain refusals.

Source-owned communication replay requires authenticated operator-authorized access to an existing communication record and its matching encrypted custody. A public fixture cannot supply that record or approval. Plaintext values, payload bytes, taxpayer-derived digests and reversible derivatives stay transient or encrypted under the existing custody owner. Public receipts expose only source/layout/revision/purpose identities and pass/fail attestation.

## Implementation

We propose a versioned extension of the existing canonical proof port, not a second closure implementation. Use a closed discriminated purpose variant for ordinary filing versus M145 communication, and a closed probe variant for fixed-width positions versus native XML schema/path checks. The XML branch keeps export_draft as its production writer. The M145 branch names and invokes its existing communication export owner.

Extend the canonical compiler/publisher's native provenance path and reuse the existing dictionary/XSD validation owners. Do not hand-author a positional export-fragment manifest for XML. The exact publication representation and XML probe syntax are implementation hypotheses to verify against those owners before committing their schema.

Add production success/refusal coverage for each purpose and transport, including altered official sources, malformed XML, stale generation pins, unknown variants, communication/filing scope confusion, missing source-owned records and mismatched encrypted custody. Retain explicit absence/refusal for unavailable private access. Re-run the complete dynamic closure denominator and source/candidate acceptance after implementation.

The affected wording in `2026-08-25-registry-completeness-closure-s33-two-channel-export-proof-adr` must be reconciled only after this proposal is authorized. Replace its universal export_draft-only constraint with: ordinary filing and native XML filing use the existing export_draft owner; M145 communication uses its existing export_m145_communication_record owner, with the same two-channel source/provenance/custody obligations and no AEAT filing claim. Scope its universal approved-calculation/draft replay wording to ordinary filing; require the actual validated source-owned communication record and matching custody for M145. Keep every other constraint intact. The parent completeness conjunction is unchanged.

## Rationale

The proposed extension matches existing production boundaries instead of widening domain types or lowering the release predicate. A closed purpose/probe union makes an incorrect writer, source or scope a typed refusal. It adds the representation needed to test the existing capability while preserving both mandatory channels. Detailed evidence and unverified implementation boundaries remain in the related research.

## Consequences

The proof wire schema and native publication representation need versioned implementation and independent verification. Existing positional proofs remain strict. Communication proof requires real authorized communication custody, and native proof requires actual official native evidence; neither becomes green merely because the extension exists. No dependent contract change is authorized by this proposed record. Reconsider the decision if an existing accepted owner already supplies an equivalent admitted proof contract or the native schema cannot provide source-bound checks.
