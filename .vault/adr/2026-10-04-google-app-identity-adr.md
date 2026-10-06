---
tags:
  - '#adr'
  - '#google-app-identity'
date: '2026-10-04'
modified: '2026-10-06'
body_schema: 'body-v2'
body_hash: 'sha256:3890c24aef6a304502638f37c9249f96bc141984c1331c587d65fa27da7e5ec8'
related:
  - "[[2026-10-04-google-app-identity-research]]"
  - "[[2026-10-04-google-app-identity-reference]]"
  - "[[2026-07-14-google-optional-adapter-boundary-adr]]"
  - "[[2026-07-04-google-sa-impersonation-adr]]"
  - "[[2026-07-12-google-oauth-adr]]"
  - "[[2026-10-03-application-packaging-adr]]"
  - '[[2026-06-10-ledger-evidence-enforcement-adr]]'
  - '[[2026-08-26-cli-root-verb-homes-adr]]'
---

# `google-app-identity` adr: `Publisher-owned Google client limited to application-created files` | (**status:** `accepted`)

## Problem Statement

Cadrumo users must sign in to Google so Cadrumo can export its own
calculations for review and keep a backup. Today that works only for an
operator who creates a personal Cloud Console client and imports its JSON.
A distributed application needs one Google identity that any user can sign in
to, and Google's verification burden for that identity is set by the scopes it
requests and by which files it can reach. The current scope set and several
code paths ask for more than the product needs.

The open question "publisher-owned versus imported Google client
registration" in `2026-10-03-application-packaging-adr` is answered here.

Authorization basis. On 2026-10-04 the product owner stated the product
boundary in commitment 1 and approved commitments 2 to 5 in conversation.
Commitment 6 was first approved as "keep the source with restricted scopes"
and, after the service-account evidence, re-ruled the same day as removal;
that ruling was given in the implementing session and relayed. Commitment 10
was approved in conversation as removal without a deprecation window.
The product owner then accepted this record as a whole on 2026-10-04, in both
the authoring and the implementing session, which covers commitments 7 to 9.
Commitment 3 was amended on 2026-10-05: as first accepted it kept an
operator-registered client as a production override, which the product owner
then refused as conflating development with production. The amendment was
drafted in `2026-10-04-google-app-identity-client-registration-adr`, approved
by the product owner on 2026-10-05 in the cloud-setup session on a summary of
its main points, and relayed. Later on 2026-10-05 the product owner ruled, in
the same session and relayed verbatim, that the application is deployed with
Google sign-in built in and that the `cadrumo` project's client is the client
in development and deployment alike: "We will deploy this application. This
is the only way this can work. Even in development, no more arguing. The
authentication is to be added to the application now." Commitment 3 was
revised again to say the client file is committed and built in, replacing the
earlier wording that kept it out of the repository and out of builds.
Statements under "Implementation hypotheses" remain hypotheses.

## Considerations

- The most sensitive requested scope sets the verification tier; a
  non-sensitive set needs brand verification only
  (`2026-10-04-google-app-identity-research`).
- `drive.file` is Google's recommended scope for the Sheets API and reaches
  only application-created or user-picked files
  (`2026-10-04-google-app-identity-research`).
- A desktop client is a public client; its metadata is not a secret
  (`2026-10-04-google-app-identity-research`).
- The export root folder is a user-supplied ID shared by the Sheets export,
  the ciphertext mirror and the provider probe; two shipped commands read
  user-supplied Drive files; ownership is decided by a marker that unmarked
  entries can acquire (`2026-10-04-google-app-identity-reference`).
- Sign-in would persist a non-token string if no refresh token came back, and
  a revoked grant surfaces as a network error
  (`2026-10-04-google-app-identity-reference`).
- A service account cannot own Drive files
  (`2026-10-04-google-app-identity-research`).
- Whether every Sheets method Cadrumo calls accepts `drive.file` is documented
  by Google but untested here.

## Considered options

1. **Keep operator-imported clients only.** Rejected: every user needs a Cloud
   project, and a project left in Testing gives 7-day sign-ins.
2. **Publisher-owned client with the current four scopes.** Rejected:
   `spreadsheets` is sensitive, so verification needs a demonstration video
   and a justification that contradicts Google's own recommendation, for
   access the product does not use.
3. **Publisher-owned client on non-sensitive scopes, application-created
   files only.** Chosen. A variant that kept the imported client as a
   per-profile override was first accepted and then withdrawn; see the
   authorization basis.
4. **Publisher-owned client plus Google Picker for user-chosen folders and
   files.** Rejected for now: Picker is a browser component with its own
   API key and hosting needs, and the product boundary does not require
   reaching files the user already had.

## Constraints

Binding commitments:

1. **Product boundary.** The Google integration exists to export Cadrumo's
   own calculations for user review and to back up. Cadrumo reads, lists and
   writes only Drive and Sheets files it created under the active client.
2. **Scope set.** The desktop sign-in requests exactly `openid`,
   `userinfo.email` and `drive.file`. No sensitive or restricted scope is
   requested by any Cadrumo credential source.
3. **Client identity.** A publisher-owned Desktop client remains the only shipped client. Under the user's explicit 2026-10-06 instruction, its complete installed-client JSON is supplied through the secret-valued core setting `CADRUMO_GOOGLE_OAUTH_CLIENT_JSON`. Development uses ignored `env/.env` provisioning and CI uses a GitHub repository secret. Builds embed the validated configuration as installation data so the installed application needs neither a dotenv file nor inherited credentials. The client file and credential values are removed from source control and its affected history. No profile registration or user-facing client selector is introduced. The prior 2026-10-05 instruction to commit the client is superseded only in this commitment; publisher identity, scopes, token binding and built-in sign-in remain unchanged. Missing or malformed configuration retains the typed refusal.
4. **Root folder.** Cadrumo creates a marked root and stores its exact creation
   identity per profile. No command, setting or environment override accepts a
   Drive folder or file reference from the user. The former workbook-ID
   exception for pull, calculate and verify is withdrawn by the authorized
   2026-10-05 outbound-review amendment. Sheets, mirror and provider probes
   share profile-bound current-containment admission; a marker alone is
   insufficient. Bootstrap creates a fresh root without a My Drive name search;
   recovery uses only a known local root receipt. The bounded metadata exception
   and provider movement race are defined in 2026-10-05-google-outbound-review-adr.
5. **Evidence acquisition.** Acquiring evidence bytes from Google Drive,
   Gmail or a URL through the Google adapter is withdrawn. Local evidence
   and invoice import are the supported intake. Stored attachment records
   that name a Google source remain readable.
6. **One credential source.** Service-account impersonation is removed. The
   desktop sign-in is the only way Cadrumo obtains Google credentials. Once
   commitment 4 lands the impersonation source cannot deliver the product
   goal: a service account owns no storage, and Cadrumo neither shares files
   nor writes to shared drives (`2026-10-04-google-app-identity-research`,
   `2026-10-04-google-app-identity-reference`). Two alternatives were put to
   the product owner and declined: keeping the source with restricted scopes,
   which cannot produce an export a person can see, and keeping it only with
   a required Workspace `subject`, which is untested and serves only
   organisations that grant domain-wide delegation.
7. **Ownership is enforced by code.** An entry without the ownership marker
   is not adopted. Creation carries the marker so that an application-created
   entry without it cannot exist.
8. **Token integrity.** A stored token is bound to the client that minted it
   and is never used with another, so a token is never refreshed against a
   different client if the application's client ever changes. A sign-in that yields no refresh token is
   refused. A revoked or expired grant is reported as a typed
   sign-in-required state, not as a network failure.
9. **No migration.** No compatibility reader and no adoption of earlier
   remote state. Tokens stored without a client binding require a new
   sign-in. Folders and workbooks created under another client stay in the
   user's Drive untouched and are not searched for; the user exports again.
   A stored credential-source selection and a stored per-profile client
   record are never honoured, and their namespace registrations are removed. By the product owner's account
   on 2026-10-04 (relayed from the implementing session), only the team's
   own test profiles hold stored Google state and only test data has been
   pushed to Drive, so those profiles are cleared by hand. The profile
   archive push refuses rows in an unregistered namespace
   (`src/cadrumo/adapters/outbound/storage/mirror_push.py:313`), which
   affects only such an uncleared test profile.
10. **Released surface is removed without a deprecation window.** The
    evidence pull commands, the folder-set command, the
    `config google credential-source` commands, `config google register` and
    the
    `CADRUMO_GOOGLE_DRIVE_ROOT_FOLDER_ID` setting are present in the tagged
    releases `v0.4.0`, `v0.5.0` and `v0.5.1`. They are removed in the first
    release that carries this decision, with a supported window of zero,
    because each one accepts a Drive reference the product boundary forbids,
    selects a credential source that cannot serve it, or registers a client
    commitment 3 no longer admits, and because
    no one outside the team is known to rely on them. The release notes name
    the removals and the local import replacement. The setting's
    removal also changes the generated environment example and the native
    contract projection.

Out of scope: the publisher's Google verification and publishing status, the
desktop Connect interface, and
the remote-mirror policy for the OAuth token namespace. The last is an open
question recorded in `2026-10-04-google-app-identity-reference`.

Affected prior rulings. These amendments were applied to the named accepted
records when this record was accepted:

- `2026-07-14-google-optional-adapter-boundary-adr`, Constraints, replace the
  bullet beginning "`doclink` and `pull-folder` remain explicit" with: "Google
  evidence acquisition is withdrawn by `2026-10-04-google-app-identity-adr`.
  This ADR does not mandate a watched Drive inbox, automatic filename router,
  plaintext staging pipeline, or rejection-sidecar subsystem." In the bullet
  beginning "A Google command may persist data only", replace "This permits
  the secure OAuth store and explicit evidence acquisition" with "This
  permits the secure OAuth store". Under Implementation, remove "acquire
  operator-selected evidence bytes," from the first paragraph and remove the
  in-scope item "explicit `doclink` and `pull-folder` acquisition through
  canonical attachment custody, with `doclink` also using the ledger evidence
  linker;". For the removed credential source: in Constraints replace "Each
  profile uses its approved credential source: OAuth Desktop or
  service-account impersonation." with "Each profile signs in through OAuth
  Desktop; service-account impersonation is removed by
  `2026-10-04-google-app-identity-adr`."; under Implementation replace "the
  approved per-profile credential source" with "the profile's OAuth Desktop
  sign-in" and replace the in-scope item "persisted per-profile
  credential-source selection, ephemeral service-account impersonation, and
  provider composition;" with "provider composition;".
- `2026-07-04-google-sa-impersonation-adr` is retired: its status becomes
  `deprecated`, with a line citing `2026-10-04-google-app-identity-adr` as
  the reason. Its need, one shared identity for a gestor team, is left
  without a replacement.
- `2026-10-03-application-packaging-adr` is itself proposed. Suggested
  wording for its author: the layout line "public OAuth client metadata, if
  selected" becomes "public OAuth client metadata", and "publisher-owned
  versus imported Google client registration" leaves the open list with a
  citation of this record.
- `2026-06-10-ledger-evidence-enforcement-adr`, Constraints, replace the
  bullet "Google credentials and scope" with: "Remote link acquisition is
  withdrawn by `2026-10-04-google-app-identity-adr`, which also settles the
  scope question this record deferred: no `drive.readonly` or
  `gmail.readonly` upgrade. Evidence bytes enter through local import only."
  Under Decision 1, add: "The repurposed remote verb is withdrawn by
  `2026-10-04-google-app-identity-adr`. The invariant is unchanged: an
  evidence record carries encrypted document bytes, and no link-only record
  exists."
- `2026-08-26-cli-root-verb-homes-adr`, in the transport dispositions, replace
  the `app ledger` line with: "`app ledger`: `import` / `export` complete for
  rows; evidence intake is local (`evidence add`, `evidence batch`); remote
  inbound absent **by policy** (`2026-10-04-google-app-identity-adr`)." In
  the paragraph "Ledger evidence intake moves into its own subgroup", add:
  "`evidence pull` and `evidence pull-all` are withdrawn by
  `2026-10-04-google-app-identity-adr`; `evidence add` and `evidence batch`
  are unchanged."
- `2026-07-12-google-oauth-adr` is unaffected: the mirror boundary does not
  depend on who creates the root folder.

## Implementation

We will run Cadrumo's Google integration on one publisher-owned Desktop
client, read from installation data, restricted to non-sensitive scopes and
to files Cadrumo created.

Outline:

- Drop `spreadsheets` from the required scope set and from the bundled scope
  constants.
- Resolve the client from installation data through one owner, and remove the
  register operation with its command, input kind, contracts and correlation,
  and the per-profile client record. Status and logout results lose their
  client-registration fields, which changes two public result schemas. One
  "no client metadata in this installation" refusal replaces the "client not
  registered" refusals.
- Replace the user-supplied root folder with a created, marker-stamped folder
  and remove the folder-set command and the environment override.
- Remove the Drive evidence pull commands and their acquisition code; keep the
  stored source vocabulary.
- Remove the impersonation source: its credential-source taxonomy and
  dispatch, adapter, error types, commands and stored selection.
- Refuse unmarked entries in both the Sheets adapter and the mirror provider.
- Bind tokens to their client, refuse a missing refresh token, and type the
  revoked-grant state.

Implementation hypotheses, free to change within the commitments:

- Workbooks are created through Drive `files.create` with the spreadsheet
  MIME type, parent and marker in one call, then populated through Sheets
  `batchUpdate`.
- The client metadata is package data at
  `src/cadrumo/_data/google/oauth_client.json`, read through the bundled-data
  reader, so a wheel carries it and no assembler step has to place it. If the
  native layout in `2026-10-03-application-packaging-adr` relocates bundled
  data, the same reader follows it.
- The built artifact preserves Google's Desktop client download, including
  `client_secret`, because refreshing a Desktop client's token without it was
  not tested.
- The loopback listener uses the IP literal. Sign-in does not force a consent
  prompt: Google always returns a refresh token to an installed application
  (`2026-10-04-google-app-identity-research`), so the refusal in commitment 8
  is a defensive check.
- Stale lifecycle declarations found in the reference record (unused refresh
  fields, the non-refreshing refresh-only mode, the unread buffer setting) are
  either implemented or deleted.

Verification owed before the scope change is claimed complete: a live run,
under `drive.file` alone, of every Sheets and Drive method the reference
record lists, against an application-created workbook. Until it runs, the
scope change is reported as pending verification.

## Rationale

Option 3 is the only option that needs no review of sensitive data use,
because it requests none (`2026-10-04-google-app-identity-research`). The
product boundary makes the narrower scope sufficient rather than a
compromise: nothing Cadrumo is meant to do requires a file it did not create.
One client read from one location means the sign-in the publisher verifies
with Google is the sign-in developers test, and no user can be asked to bring
a Cloud project.

Enforcing ownership in code rather than relying on the scope keeps the
boundary true even if the client's registered scopes were ever widened.
Removing impersonation leaves one sign-in path to verify and document, and
drops a path that could not serve the product goal. Binding tokens to their
client guards the case where the application's client changes: without it a
token could be refreshed against the wrong one. Building the client into the
application is what lets sign-in work in any installation without a setup
step.

## Consequences

- The publisher needs a domain, a public home page and a privacy policy
  before any user outside a 100-person test list can sign in.
- Files exported under an operator's own client are not visible to the
  publisher client; affected users export again.
- An organisation that blocks third-party clients must allow the publisher
  client; it cannot substitute its own.
- Development and deployment share one Google Cloud project, so its
  publishing status applies to both. While it is in Testing, only accounts on
  its test-user list can sign in and their grants expire after 7 days;
  widening that is a console action by the publisher.
- The client metadata is readable by anyone with the source or a build.
- Users lose evidence pull from Drive and use local import instead.
- The public client can be presented by a third party on a consent screen;
  the exposure is limited to `drive.file`.
- Tokens stored before the client binding require a new sign-in.
- Teams that shared one service-account identity lose that option; each
  profile signs in with a Google account.
- Operators on a tagged release lose the evidence pull, folder-set,
  credential-source and client-register commands and one setting at upgrade,
  with no transition period.

Reconsider if the live proof shows a required Sheets method refusing
`drive.file`, or if users need Cadrumo to open a spreadsheet or folder they
already own. Either reopens the choice between Google Picker and a sensitive
scope and needs a new decision.

## Amendment 2026-10-05 - outbound review

The product owner's Session 01 instruction authorizes the scoped wording changes above, governed by 2026-10-05-google-outbound-review-adr. Earlier descriptions of then-current behavior remain historical evidence, not permission to retain retired routes. Other commitments remain in force. This amendment records architecture, not completed implementation or live acceptance.

## Amendment 2026-10-05 - application parent layout

The product owner explicitly requires My Drive/Cadrumo/Cadrumo {profile discriminator}/... . Commitment 4 now distinguishes the shared application parent from the profile content boundary, as specified in 2026-10-05-google-outbound-review-adr. Commitment 9 does not prohibit the newly authorized, identity-preserving relocation of a known current-client root with retained creation evidence: that operation changes placement, never adopts historical foreign-client state or rewrites creation history. No global/name discovery exception is inferred from the layout request; the earlier restriction remains until separately resolved. This is an authorized architecture adjustment, not a claim that the live folder has been moved.


## Amendment 2026-10-06 - credential provisioning outside Git

Authorized by the user's explicit request to remove client credentials from the repository and history, provision main/env/.env and tui/env/.env and GitHub repository secrets, and use core Settings for local and CI builds. Commitment 3 now distinguishes ignored build inputs from distributed installation data. Earlier authorization-basis text records history and no longer authorizes committing credential bytes. The native environment contract continues clearing ambient overrides; installed Settings resolves its embedded default. This ruling does not claim rollout completion.
