---
tags:
  - '#adr'
  - '#source-casilla-integration'
date: '2026-11-06'
modified: '2026-11-06'
body_schema: 'body-v2'
body_hash: 'sha256:fe7ca24d2854c5240fc041b8a6f6073f9cb9b6011511ac6220d4cce4975e0a40'
related:
  - "[[2026-08-22-source-casilla-integration-adr]]"
  - "[[2026-07-24-evidence-revision-identity-adr]]"
  - "[[2026-07-26-evidence-revision-identity-adr]]"
  - "[[2026-11-06-source-casilla-integration-profile-node-fingerprint-reference]]"
---

# `source-casilla-integration` adr: `Profile provenance node content is the consumed facts` | (**status:** `proposed`)

Proposed amendment to `2026-08-22-source-casilla-integration-adr`. That accepted record stays unchanged until the operator accepts this proposal. This record is then retired.

## Problem Statement

`2026-08-22-source-casilla-integration-adr` makes a provenance node's `fingerprint` its content identity and puts every axis into calculation-revision identity. It does not say what content a profile-sourced node carries.

Today the calculation path hashes the whole loaded profile record, including its save bookkeeping. An edit to any unrelated fact, or a save that changes nothing, therefore changes the revision identity of every Modelo that reads any profile fact. The next recalculation mints a new BORRADOR instead of reusing the verified one (`2026-11-06-source-casilla-integration-profile-node-fingerprint-reference`).

## Considerations

- A node is per binding, and the fingerprint is that node's content identity, per `2026-08-22-source-casilla-integration-adr`. Whole-record content is wider than the node.
- `2026-07-26-evidence-revision-identity-adr` keeps inputs that do not change the calculation out of revision identity, so an unchanged re-run keeps its revision.
- `2026-07-24-evidence-revision-identity-adr` requires operator sign-off for any change to content-address derivation.
- No consumer compares a stored profile fingerprint with the live profile. Header and contact export facts are read live. Whole-record sensitivity therefore protects no current check (reference).
- Persisted revisions re-derive their ID from the stored fingerprint string, never from a profile. A new computation therefore rewrites no history (reference).
- One test pins the whole-record behaviour today. `test_changed_profile_evidence_changes_revision_identity_even_when_contact_values_match` in `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_720_profile_contact.py` asserts that an edit to an unconsumed fact (`identity.email`) changes the Modelo 720 revision identity even when the contact values match. It came from the modelo-profile-bindings plan step S04, which was scoped to preserve existing fingerprint provenance and did not rule on node content (reference).

## Considered options

- **Keep the whole record.** No change, but any profile save churns the identity of every profile-reading revision and loses verified reuse. Rejected.
- **Strip only the bookkeeping fields from the whole record.** This stops churn from bare saves, but an unrelated fact edit still churns, and the hash stays wider than the node it identifies. Rejected.
- **Per-binding consumed facts.** The node's content is exactly what the binding read and resolved, so any change to a consumed fact still changes identity and nothing else does. Chosen.
- **No fingerprint for profile nodes.** This conflicts with the accepted requirement that a connected primary has a non-empty content fingerprint, and it would let a consumed-fact change reuse a stale revision. Rejected.

## Constraints

- A profile-sourced provenance node's fingerprint is a domain-separated digest of:
  - the binding ID;
  - the declared selector paths it read;
  - the channel;
  - the resolved typed value as consumed, including a derived value such as a predicate result;
  - the profile schema identity and version.
- For a row binding, the digest covers the ordered resolved row values and their count.
- The digest is computed whenever the binding resolved from a loaded profile, and is never null in that case.
- The atribucion member source follows the same rule for the facts its projection consumes.
- Record bookkeeping never enters it: update time, record revision, previous or content digest, and setup state.
- Persisted revisions keep their stored IDs and stored fingerprints. Nothing rewrites, re-keys or migrates stored provenance, and re-derivation keeps hashing the stored string.
- The digest uses a distinct domain-separation tag, so a new-scheme value is never mistaken for an old one. No dual reader, compatibility alias or fallback to the whole-record scheme is added for new calculations.
- Scope is profile-sourced provenance nodes only. Other source kinds, draft-approval activity fingerprints and live export reads are unchanged. Unifying the Modelo 720 contact path with live producer keys is a separate decision.

## Implementation

We will replace the whole-record profile fingerprint with a per-binding consumed-facts fingerprint at its two producers:

- the profile binding resolver, `src/cadrumo/application/modelo/profile_binding.py`;
- the atribucion member source.

The provenance shape and the revision-identity payload stay as they are. Hypothesis: a single helper in the profile binding owner builds the canonical payload, and both producers call it.

Required tests:

- A bare save keeps the revision ID and reuses the earlier revision.
- An edit to an unconsumed fact keeps the revision ID and reuses the earlier revision.
- An edit to a consumed scalar, row or derived fact changes the ID.
- The terminal-origin audit still finds a non-null fingerprint on every connected profile primary.
- A revision persisted under the whole-record scheme still loads and re-derives its stored ID.

The pinned test `test_changed_profile_evidence_changes_revision_identity_even_when_contact_values_match` in `test_modelo_720_profile_contact.py` is replaced in the same change by its inverse, because an unconsumed `identity.email` edit must keep the 720 identity. Its encrypted round trip is kept.

Committed revision IDs: the CLI-sequence goldens under `docs/_sequences` hold content-derived `calculation_revision_id` values (46 files, 80 values at this writing). Every golden whose revision consumed a profile node changes ID under the new scheme, so the same change regenerates them through `just docs-generate-sequences` and passes `just test-sequence-goldens-gate`. No other committed fixture stores a derived revision ID: `native/desktop/src-tauri/src/shell/modelo/relay_contracts.json` and `src/cadrumo/_data/operations/contract_manifest.json` name the field without holding a value, and the registry `revision_id` entries in export provenance files are edition identifiers, not calculation identities.

## Rationale

Consumed facts are the only option that matches the node-level meaning of `fingerprint` in `2026-08-22-source-casilla-integration-adr` and also preserves the identity-stability intent of `2026-07-26-evidence-revision-identity-adr`. The reference shows that whole-record sensitivity guards no current consumer. Its only observable effect is lost verified reuse.

## Consequences

- Profile saves that do not touch a consumed fact no longer force re-verification.
- A revision computed before the change and one computed after it, from the same consumed facts, have different IDs, because their fingerprints come from different schemes. The first recalculation after rollout therefore mints a new BORRADOR once per work unit. This is accepted as a one-time cost.
- Reconsider if a future consumer needs to detect that the profile changed at all. That consumer should use its own activity fingerprint, as draft approval already does, rather than widen calculation identity.
