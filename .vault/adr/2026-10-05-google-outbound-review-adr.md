---
tags:
  - '#adr'
  - '#google-outbound-review'
date: '2026-10-05'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:32cbfa76ef5e62a12e27565b4ec90565457083eee2f816b746077ef7b5d5daaf'
related:
  - "[[2026-10-05-google-outbound-review-reference]]"
  - "[[2026-10-05-google-outbound-review-research]]"
  - "[[2026-10-04-google-app-identity-adr]]"
  - "[[2026-07-14-google-optional-adapter-boundary-adr]]"
  - "[[2026-08-08-sync-control-surface-adr]]"
  - "[[2026-06-03-modelo-export-workbook-parity-adr]]"
  - "[[2026-06-03-modelo-export-evidence-parity-adr]]"
  - "[[2026-06-03-modelo-export-visual-design-adr]]"
  - "[[2026-07-12-google-oauth-adr]]"
  - "[[2026-07-09-compatibility-lifecycle-adr]]"
---
# `google-outbound-review` adr: `Outbound revision review and managed artifact admission` | (**status:** `accepted`)

## Problem Statement

Google review must export a selected saved calculation and its supporting evidence without making remote edits calculation inputs. Current push builds a template; pull/calculate consume edits; creation and admission do not enforce the required folder boundary. This is a refinement of Google identity and adapter authority, not a second calculation architecture.

Authorization basis: on 2026-10-05 the product owner instructed Session 01 to own the outbound architecture, retire bidirectional calculation behavior, require strict managed-folder containment, design native Sheets and complete evidence packages, and perform published-client live characterization. That authorizes the product commitments below and their reconciliation with earlier wording. It does not authorize deployment or broad implementation in Session 01. Separate custody-policy choices remain proposed, not implied by this authorization.

## Considerations

Current-source findings and bounded inspection are in 2026-10-05-google-outbound-review-reference. Provider limits and scoped invoice-retention requirements are in 2026-10-05-google-outbound-review-research. A spreadsheet, an immutable evidence package and ciphertext custody have different confidentiality and integrity purposes.

## Considered options

- Retain non-persistent pull/compute: rejected because the requested product boundary excludes calculation from edited remote business values, even without canonical writes.
- Treat existing template creation as revision export: rejected because it does not carry the selected saved values.
- Share one immutable local snapshot between review renderers and the evidence package: chosen; preserves revision identity without a second engine.
- Claim folder isolation from drive.file or marker alone: rejected; neither proves present containment.

## Constraints

The only Google data-access scope is drive.file. Keep the bundled live OAuth client and existing identity scopes; do not request a Sheets scope or broader Drive scope.

1. Google is an optional outbound review/export and backup provider. No remote cell, note, scenario, document or attachment may enter canonical facts, source assembly or a production calculation. Local evidence imports and offline XLSX export remain supported.
2. Remove public spreadsheet pull, remote calculate and public verify, including executable operation registrations, contracts, discovery and help. No functioning compatibility shim remains. Announce removal in the first release carrying this change with a supported execution window of zero: keeping the old behavior would directly violate the owner's new boundary. Earlier zero-window identity removals are precedent, not blanket authorization to discard durable taxpayer records. Preserve required historic local receipt/revision readability under the accepted compatibility lifecycle; assess any real persisted schema transition with released fixtures.
3. Developer acceptance may compare exported baseline cells and allowlisted local-only scenario formulas with the canonical engine. It is opt-in synthetic test tooling, not an installed business workflow, and cannot route results to fact writers. Do not rename general pull as verification.
4. One profile-bound artifact admission contract governs Sheets, readable package copies and storage. Admission binds active profile, root identity, app ownership marker, recorded creation identity, allowed kind, non-trash state and current ancestry. User-supplied workbook IDs, foreign/copy adoption, shortcuts and external shortcut resolution are refused before content access. Known-identity metadata probes are the sole bounded exception to the content boundary; request only identity, kind, marker, trash and parent facts and stop at an unknown/outside ancestor. Never list outside an admitted managed folder except the narrowly authorized application-parent metadata lookup in constraint 5.
5. The user-visible layout is My Drive/Cadrumo/Cadrumo {profile discriminator}/..., as explicitly requested by the product owner on 2026-10-05 after reviewing the live folder. The Cadrumo application parent groups profile roots; the exact profile root remains the content-admission boundary. Creation puts a new profile root directly under its admitted application parent. Known current-client profile roots already created directly in My Drive may be relocated by an explicit, journaled layout operation preserving their IDs, descendants and existing creation/publication receipts. Retain separate placement evidence rather than rewriting original creation history. Re-admit both known identities, record move intent before provider mutation, verify exact resulting parent, and reconcile lost responses by exact IDs without recreating roots. Ordinary content access cannot silently move folders or repair placement. Sharing an application parent never grants access to sibling profile contents. The user authorized a metadata-only lookup for the current client's marked application parent directly under My Drive. Require folder kind, owner marker, ownedByMe, creation UUID and an original provider-ID marker equal to the actual ID; copied markers or multiple candidates refuse. Allocate the parent ID before creation and stamp that identity in its first request. Persist it before mutation so uncertain outcomes reconcile by exact ID. No name-only adoption, profile-root discovery, sibling listing or outside content access is authorized. Stale/lost/ambiguous identity is not proof of absence. Moving descendants outside their profile root revokes admission; profile/ownership mismatch always refuses.
6. Create native Sheets via Drive files.create with native MIME, admitted parent and marker in the creation request, then populate via Sheets. There is no create-then-move window. Re-admit immediately before each content call and each retry; caches are locators, never authorization. Paginate scoped listings fully and reject duplicates/ambiguity. Ambiguous root creation is not blindly retried. In-folder publication markers may reconcile a partial child creation.
7. Literal temporal guarantee is limited: the provider does not expose an atomic Sheets request conditional on Drive ancestry. A user can move an admitted file between check and use. Record this residual race, minimize the interval, postcheck before claiming publication, and stop further access on detected movement. Never describe this as an absolute provider-enforced folder sandbox. If zero race is mandatory, Sheets content access cannot be enabled under the present provider contract.
8. Both renderers consume one immutable revision export snapshot with model/year/period, work/calculation/source revisions, authority generation and registry digest, canonical values and typed provenance, units/currency/rounding, status and unresolved findings, ledger/invoice attribution and included/excluded/missing evidence inventory. No renderer recalculates from current ledger state. A draft/soft calculation is exportable with explicit provisional status; unavailable historical evidence stays missing. Filing-grade gates do not weaken.
9. Baseline values remain the saved local results. A designed native workbook presents overview/status, results, ledger support, evidence index and editable review notes; optional scenarios are clearly separate and never read into production. Re-export creates a new versioned document; published review copies are never cleared or overwritten. Retry reconciliation is distinct from re-export and cannot overwrite a user-visible completed copy. Treat all ordinary strings as literal text, and permit only deliberately generated formulas without external-data acquisition.
10. Audit/evidence packages are versioned independently from the editable Sheet and carry actual selected source payloads, original attachments when permitted, provenance, completeness findings and member digests. A missing payload can yield an explicitly incomplete review package, never an audit-ready success. Digest mismatch refuses publication. Local and remote copies share the same package digest. Checksums are integrity evidence, not authenticity or legal certification.
11. Readable evidence publication requires a distinct capability and per-export disclosure of payload categories/destination. Ciphertext-backup consent never implies authorization to upload decrypted attachments. No sharing changes or deletion of review artifacts are automatic.
12. Retained technical reads have closed purposes: known-identity admission; current in-flight publication reconciliation; allowlisted baseline verification; backup manifest/ciphertext integrity. They produce only receipts, digests and findings, never business inputs. Published notes/scenario cells are not read for routine exports. Remote packages are not evidence acquisition sources.

## Implementation

We will refine the existing registered export and canonical workbook plan, with a shared snapshot builder and artifact admission ports. The integration owner alone changes shared contracts, operation composition, namespace declarations and generated enrollment. Lane A owns containment/retirement/custody, lane B the designed workbook and ledger review renderer, and lane C payload-complete evidence packaging. Exact proposed interfaces, owned files and acceptance obligations are in the Session 01 handovers; no parallel source writers start before the shared contract is frozen.

Publication is journaled as prepared, remote-created, populated, verified, published or uncertain/partial. A timeout is not absence. Reconcile by local publication identity within the admitted folder; never blindly create again after a lost response. Preserve earlier published artifacts and user notes. No destructive remote cleanup or production restore belongs to this session.

## Rationale

Saved values and evidence must have the same origin, and external review must not silently change that origin. One immutable snapshot and canonical plan preserve existing authority while allowing useful review. Central admission closes the current divergence between marker checks, root validation and storage caching. Honest race and recovery limits are part of the contract.

## Consequences

The old public Google calculation routes are retired architecturally; implementation and release notes are still owed. Historical workbooks remain in the user's Drive. Missing draft evidence may limit audit completeness while still permitting a clearly labeled review export. Live OAuth, scoped provider proof, persistent native documents and actual user review are rollout gates, and this decision records none as passed.

Affected accepted wording is amended in place under this authorization: identity commitment 4 loses its arbitrary-workbook exception; optional-adapter Constraints and Implementation lose typed pull/compute; the Sheets portion of sync-control-surface changes from overwrite/diff to new-version publication preview; workbook-parity confines live recomputation to separate external scenarios while retaining structural/format parity; evidence-parity permits labeled provisional review while preserving filing-grade refusal. Historical considerations remain dated evidence. No whole-record supersession is needed because these records continue to govern their other concerns.

## Unsettled policy

OAuth-token/config mirror selection, any change from plaintext structural manifests, and post-sealed-restore credential handling are a separate proposed custody amendment. The existing mirror is not demonstrated recoverable backup. Sealed archive custody remains with its accepted owner; this decision creates no Google row-restore engine.

## Amendment 2026-10-05 - application parent layout

The product owner requested Cadrumo/<Cadrumo {foo}>/** after observing the live profile folder at My Drive root, and explicitly instructed continued work. This authorizes the layout and identity-preserving relocation of known current-client folders. It does not authorize deleting artifacts, adopting foreign folders, broadening OAuth scopes or reopening retired remote calculation. After the narrow metadata-only parent-discovery question, the owner explicitly directed move it now and continue. This is the authorization for the bounded exception in constraint 5, not an inference from elapsed time. Session01 implements the dedicated migration operation and its admission contract; Session02 owns fresh bootstrap integration. Live testing established that drive.file cannot read My Drive itself: retain the exact profile-root source-parent identity and validate it against the marked application parent created or discovered directly under root; do not request broader scopes. Relocation completion is recorded separately in live results.
