---
tags:
  - '#adr'
  - '#modelo-edit-contract'
date: '2026-11-09'
modified: '2026-11-09'
body_schema: 'body-v2'
body_hash: 'sha256:d40c18726fa8f197158b59d107247ce8f316febe24ec62ae79239dd3f9ec7867'
related:
  - "[[2026-08-24-modelo-edit-contract-adr]]"
  - "[[2026-11-08-prior-carry-attestation-adr]]"
  - '[[2026-11-08-prior-carry-attestation-audit]]'
---

# `modelo-edit-contract` adr: `D4 amendment: the attest_no_amount binding intent` | (**status:** `proposed`)

## Problem Statement

D4 of `2026-08-24-modelo-edit-contract-adr`, with its 2026-08-26 amendment, enumerates two binding intent kinds, `SET_OVERRIDE_VALUE` and `REMOVE_OVERRIDE`. The accepted `2026-11-08-prior-carry-attestation-adr` adds a third, `ATTEST_NO_AMOUNT`, and ships it (`src/cadrumo/application/modelo/edit_models.py`). The contract record still names two kinds, so it no longer describes the contract. This record proposes the amendment that reconciles it. It is retained separately until the operator authorizes it, and the accepted D4 text stays unchanged meanwhile.

## Considerations

- The attestation ADR is accepted and governs the intent. This amendment only reconciles the contract record that it amends.
- Rule 07 keeps absent, unknown and proven zero distinct. A stated zero must stay distinguishable from a typed zero in the operator layer.
- The plan-close re-review in `2026-11-08-prior-carry-attestation-audit` found the contract record still names two kinds. The scope of the intent is a registry declaration, not a source-kind inference.

## Considered options

- Amend D4 in place by one binding intent kind with its admission condition: proposed.
- Leave D4 naming two kinds and rely on the attestation ADR: rejected. The contract record would misstate the edit vocabulary that frontends and the manifest carry.
- Supersede the edit-contract ADR: rejected. Its other decisions stand, and one added kind is a refinement, not a reversal.

## Constraints

- Applies only once the operator authorizes it. Until then the accepted D4 text and its amendments stay as written.
- Adds one kind and changes no existing kind, address shape or surface entry. The edit contract version is unchanged.
- The scope and behaviour come from `2026-11-08-prior-carry-attestation-adr`. This record restates neither.

## Implementation

We will amend D4 so that `ModeloEditBindingIntentKind` names three kinds: `SET_OVERRIDE_VALUE`, `REMOVE_OVERRIDE` and `ATTEST_NO_AMOUNT`. The proposed text to add to D4 as an amendment section reads:

`ATTEST_NO_AMOUNT` addresses a binding by `ModeloEditBindingAddressV1` and carries no value. It is admitted only on a writable binding override whose registry binding declares an `absence_attestation` family. The registry schema allows that family only on a decimal binding read from an earlier filing (`src/cadrumo/domain/calculations/registry/schema.py:291`). Applying it records the operator override as zero and adds the binding to the operator layer's `attested_binding_ids`. `SET_OVERRIDE_VALUE` and `REMOVE_OVERRIDE` on the same binding withdraw the attestation. Like the other binding kinds, it takes part in the submission's duplicate-address check.

## Rationale

The contract record is what frontends and reviewers read for the edit vocabulary. Naming the third kind and its admission condition there keeps one home for the contract. The behaviour stays in the attestation ADR.

## Consequences

- Once applied, D4 again lists every binding intent kind that the operation contract manifest carries.
- No code changes: the intent and its admission already ship under the accepted attestation ADR.
- If the operator declines, the accepted attestation ADR still governs the intent. The contract record's omission then stays a recorded documentation gap in `2026-11-08-prior-carry-attestation-audit`.

## Open item

The coordinator ruled on 2026-11-09 that the attestation ADR's resolution-and-verification bullet stands. An attested zero must carry its provenance through the earlier-filing resolver and verification into results, not only onto the work form. Today only the form reads `attested_binding_ids` (`src/cadrumo/application/modelo/calculation_bucket_actions.py:666`), so this is open (finding attested-resolution-provenance in `2026-11-08-prior-carry-attestation-audit`). It is to be implemented only after the operator accepts this amendment.
