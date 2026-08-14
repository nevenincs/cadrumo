---
tags:
  - "#adr"
  - "#profile-bucket-lifecycle"
date: '2026-08-13'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
supersedes:
  - '2026-05-14-profile-bucket-lifecycle-adr'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:90a6f7f902ada425d2f52a6f2963acda4f2af89f1b109c07d6934e7b2671ba82'
---
# `profile-bucket-lifecycle` adr: `current-format profile capsule lifecycle` | (**status:** `accepted`)

## Problem Statement

Profile naming, discovery, selection, local data ownership, and destructive removal remain necessary after custody moves to the profile-password roll-up. This successor preserves only those independent lifecycle facts and binds initial typed profile state to the same atomic capsule publication.

## Considerations

- Custody and atomic capsule publication belong to `2026-08-13-profile-password-custody-rollup-adr`.
- The encrypted fact owner and non-authoritative aggregate provenance belong to `2026-08-13-profile-state-aggregate-successor-adr`.
- A display label is mutable presentation; the immutable UUID is identity.
- Discovery must not infer profiles from arbitrary directories or unlock encrypted profile state.

## Considered options

- Preserve the mixed lifecycle-and-custody repository: rejected because it leaves two authorities.
- Publish an empty capsule and create canonical profile facts in a second post-publication write: rejected because a crash can expose a committed profile without its required semantic root.
- Publish the initial encrypted record as verified staged capsule data and retain only non-custody lifecycle facts here: accepted.

## Constraints

The profile repository remains the canonical owner of collision-safe label-to-UUID resolution and selected-profile projection. It may not unwrap keys, infer retired formats, read encrypted facts during discovery, or create another activation, restore, or deletion protocol. Label uniqueness is serialized and established before capsule publication.

## Implementation

Profiles are addressed internally by immutable UUID. Labels remain mutable, non-secret presentation with collision-safe validation. Listing and selection project only committed current-format capsules. Profile-scoped application services resolve UUID before opening an authenticated data session. Capsule publication, password custody, pointer compare-and-swap, restore, and local deletion delegate exclusively to `2026-08-13-profile-password-custody-rollup-adr`.

Registration supplies validated initial typed facts and setup state to the lifecycle transaction. Under root-then-profile locking and a transient DEK-bound session, the transaction initializes the profile-local secure-object database and its revision-one `UserProfileRecord` inside the sibling staging capsule before stage verification, marker fsync, and the single no-replace directory rename. Pointer publication remains last. Refusal or completion closes the transient session and zeroises its DEK material. There is no second post-publication fact-store creation path. A setup-incomplete profile is a committed capsule with a revision-one setup-state record; later wizard edits and the one-way setup-completion transition use the encrypted record owner's compare-and-swap operations.

Restore takes canonical encrypted profile data from the authenticated restorative archive, not caller-selected replacement facts. Before exposing an unlocked projection it validates that the restored current-schema record binds the immutable capsule UUID. A missing presentation label may yield an explicit UUID-derived unavailable presentation and be repaired, but a corrupt or conflicting label projection is reported as typed degradation rather than treated as authority.

Physical deletion belongs only to the custody transaction and removes the encrypted database as part of the capsule's bounded inventory. It does not tombstone or delete a profile row through the semantic repository, and no reactivate operation exists. Immutable filing-time snapshots remain governed by their filing and evidence owners rather than keeping a deleted capsule locally alive.

The hard cutover removes the retired lifecycle repository, manifest and arbitrary-bucket discovery, generic profile-row mutation, tombstone, reactivation, and mixed rename routes from production composition and facade exports. Registration routes through staged lifecycle creation. Wizard, edit, setup, and owner-specific fact refresh route through the authenticated record command boundary. Calculation, modelo, filing, readiness, authentication, and cotejo consume the current session-bound record or an explicitly owned immutable snapshot. Overview and inspection compose the provenance-bearing profile projection and require unlock only for encrypted facts. Backup and restore inventory encrypted capsule data without enumerating a legacy record store; an access or portability view may serialize decrypted facts only after explicit authentication. Local deletion routes only through custody.

## Rationale

Staging the semantic root with the capsule makes every visible profile attributable after a crash. Keeping label resolution, encrypted facts, and physical custody in separate canonical owners preserves operator-visible discovery without recreating a plaintext manifest or a second lifecycle writer.

## Consequences

Creation must initialize encrypted semantic state before publication and therefore has a broader staged verification contract. Restore must validate the current encrypted record after authentication. Consumers must complete the hard cutover together; compatibility aliases, tombstoned profiles, reactivation, and post-publication record creation are unavailable.
