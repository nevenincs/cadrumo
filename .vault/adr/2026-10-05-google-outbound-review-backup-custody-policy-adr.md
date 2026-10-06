---
tags:
  - '#adr'
  - '#google-outbound-review'
date: '2026-10-05'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:4ea87629afb6956d9cf28863b5ee49ec80e3a8d75deef92e455c4f29e58810ea'
related:
  - "[[2026-10-05-google-outbound-review-reference]]"
  - "[[2026-07-12-google-oauth-adr]]"
  - "[[2026-10-04-google-app-identity-adr]]"
  - "[[2026-08-13-sealed-archive-transport-successor-adr]]"
  - '[[2026-08-13-profile-password-custody-rollup-adr]]'
---

# `google-outbound-review` adr: `Proposed Google credential exclusions and confidential backup inventories` | (**status:** `proposed`)

## Problem Statement

Portable custody excludes Google process-local records, while the encrypted-row mirror currently includes them by default. Structural manifests are intentionally plaintext under the accepted mirror ADR. Sealed archives carry a database, so portable selection does not determine restored credential behavior. These choices need explicit custody authority, not an assumption attached to outbound review.

## Considerations

2026-10-05-google-outbound-review-reference distinguishes the three selectors and the unproven restore path. No live recovery test ran and no private records were inspected.

## Considered options

- Preserve all current mirror defaults: least change, but retains credential ciphertext remotely and structural disclosure.
- Exclude Google token, sign-in metadata and root config; encrypt full inventory metadata: recommended. Requires a versioned manifest transition and explicit inventory of exclusions.
- Upload a second Google-specific recovery format: rejected; sealed profile recovery already has an owner.

## Constraints

This is a proposal, not accepted authority to alter namespaces, old manifests or restores. It does not delay the already-authorized removal of remote calculation routes or compliant folder creation. It must not be implemented as an unreviewed shared-policy change by a lane worker.

## Implementation

Proposed wording for identity ADR's open mirror question: Google OAuth token, sign-in metadata and Drive-root config are intentionally excluded from remote backup selection; inventory records their exclusion and requires fresh Google sign-in after recovery. Public installation client metadata belongs to the installed application, not a profile backup. Other SECRET namespaces remain governed individually; there is no blanket exclusion that would accidentally remove recovery-critical state.

Proposed mirror ADR amendment: full namespace, classification, natural-key-derived identifiers and lineage inventories are authenticated and encrypted under the profile's established backup custody. A minimal outer descriptor carries only format/opaque snapshot identity, ciphertext byte lengths/digests and completion state. Never call unkeyed SHA-256 HMAC. Existing plaintext v1 manifests remain recognizable for verification; no silent overwrite, re-encryption or remote deletion. A transition must prove interpretation of actual prior bytes and publish a fresh versioned backup set.

The backup set inventories selected, intentionally excluded, unavailable and failed objects. Completeness is relative to the declared selection, not the whole profile unless every restorative dependency is covered. Recovery evidence must exercise password-authorized sealed recovery in an isolated destination and verify restored facts/attachments. Reuse the provider-neutral custody owner; do not add a remote-row import engine or ingest workbook edits.

Post-restore policy proposal: restored Google credentials are unusable until fresh sign-in, and stored remote roots are not silently activated. Implement this at the restore/custody owner with a test over the encrypted database, not by claiming PROCESS_LOCAL filters sealed archives. Do not destroy other restored financial state. No production profile restore is authorized by Session 01.

## Rationale

The remote backup need not contain the credential used to transport it. Opaque inventory reduces metadata disclosure while preserving integrity through authenticated decryption. Explicit reauthentication avoids accidental access under recovered stale grant/root bindings.

## Consequences

Acceptance entails a real persisted manifest transition and custody-owner coordination. Lane A can inventory and test the current behavior now; policy-changing implementation waits for this proposal's acceptance. Existing mirror uploads remain described as integrity-checked ciphertext mirrors until a recovery test proves the declared recovery scope. The proposal does not authorize retroactive cleanup.
