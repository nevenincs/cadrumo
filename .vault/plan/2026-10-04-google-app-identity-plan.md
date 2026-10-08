---
tags:
  - '#plan'
  - '#google-app-identity'
date: '2026-10-04'
tier: L1
related:
  - '[[2026-10-04-google-app-identity-adr]]'
modified: '2026-10-05'
body_schema: body-v2
body_hash: 'sha256:63377dfef1811fd0731de49555426cd561c44c23e682bdf8596f0d3f899ed773'
---

# `google-app-identity` plan

Restrict the Google integration to application-created files on one desktop
sign-in with three non-sensitive scopes, and prepare the client identity seam
for a publisher-owned client.

## Description

Approved 2026-10-04

Authorization basis. On 2026-10-04 the product owner directed the
implementing session to take this refactor, was told that the plan and the
code would start once the decision record was accepted, and then accepted
`2026-10-04-google-app-identity-adr` as a whole. That acceptance bounds the
scope of every Step here. The ten Steps themselves were not reviewed one by
one; they are presented with this record, and any Step the product owner
changes is edited through the plan verbs before it executes.

Decision coverage. One accepted record governs all ten Steps:
`2026-10-04-google-app-identity-adr`. Its evidence is
`2026-10-04-google-app-identity-reference` for the code and
`2026-10-04-google-app-identity-research` for Google's policy. No Step needs
a decision outside it. Commitment to Step mapping:

- Commitment 6, one credential source: `S01`.
- Commitment 5, evidence acquisition withdrawn: `S02`.
- Commitment 2, scope set: `S03`, with the owed live proof in `S10`.
- Commitment 7, ownership enforced by code: `S04`.
- Commitment 4, root folder: `S05`.
- Commitment 3, client identity: `S06`.
- Commitment 8, token integrity: `S07`.
- The lifecycle hypothesis, implement or delete: `S08`.
- Commitment 10, released surface removed without a window: the removals
  land in `S01`, `S02` and `S05`; `S09` writes the release notes and user
  documentation that name them.
- Commitment 9, no migration: no Step writes a reader or an adoption path.
  `S01` removes the stored selection namespace registration and `S07` makes
  a token without a client binding require a new sign-in.
- Commitment 1, the product boundary, is the acceptance test for the whole
  plan rather than a Step.

Scope notes that keep Steps honest:

- Each Step that removes or changes a command regenerates the generated CLI
  reference and command-surface inventories it affects in the same commit, and
  changes locale catalogues only through the `dev.locales` workflow. Generated
  provider rule copies are not hand-edited.
- `S02` keeps the `AttachmentSource` members as stored-history vocabulary.
  `AttachmentSource.URL` is also written by AEAT notification-document
  custody and is untouched.
- `S04` treats workbook creation through Drive `files.create` as a
  hypothesis. If the offline checks cannot establish it, the Step keeps the
  refusal of unmarked entries and records the creation path as owed to `S10`.
- `S05` removes a declared setting. The generated environment example and
  the native contract projection change with it; the native projection is
  owned by the packaging work, so this Step regenerates only what this
  repository's own generators produce and reports the rest.
- `S06` follows commitment 3 as amended on 2026-10-05: the publisher client
  is the only client, so the Step removes client registration rather than
  keeping it as a fallback. With no usable file present the behaviour is one
  typed refusal. As first built, the client file was git-ignored and excluded
  from both build targets; `S11` reverses that.
- `S11` follows commitment 3 as amended a second time on 2026-10-05, after
  the product owner ruled, in another session and relayed to this one, that
  the application is deployed with its Google sign-in built in. The client
  file is committed with the source and carried by every build. The file's
  contents are never printed, logged or quoted in a record.
- `S12` and `S13` were added on 2026-10-05 on an instruction from the product
  owner relayed by the decision record's author as "fix the UNKNOWN refusal
  issues", which is that author's reading of a dictated message. Neither
  involves a costly decision and no ADR governs them. Both keep UNKNOWN
  wherever an effect is genuinely ambiguous; only a response that proves the
  effect did not happen may settle as not applied. `S12` stops and reports
  if it would need a change to the supervisor or tracker contract that other
  operation families share. `S13` is outside the Google integration: it was
  observed while `S02` was being verified.
- `S07` changes the persisted token schema. Per commitment 9 there is no
  reader for the old shape.

Out of scope, as the decision record states: the publisher's Google Cloud
registration, build-time delivery of client metadata, the desktop Connect
interface, the `native/` tree, and the remote-mirror policy for the OAuth
client and token namespaces. Project rule sources under `.vaultspec/rules`
that describe the Google adapters are not edited here; wording changes are
proposed to the product owner at plan close.

## Steps

- [x] `S01` - Remove the service-account impersonation credential source, its taxonomy, dispatch, adapter, error types, stored selection namespace, credential-source commands, locale keys and tests; `src/cadrumo/adapters/outbound/google/impersonation.py`.
- [x] `S02` - Remove Google evidence acquisition, the evidence pull and pull-all commands and the document-link CLI choice, keeping the stored attachment source vocabulary; `src/cadrumo/adapters/outbound/google/document_link_resolver.py`.
- [x] `S03` - Drop the spreadsheets scope from the bundled scope constants and the required scope set so sign-in requests exactly openid, userinfo.email and drive.file; `src/cadrumo/core/external_constants.toml`.
- [x] `S04` - Refuse unmarked Drive entries in the Sheets adapter and the mirror provider, and create workbooks through Drive with the ownership marker in one call; `src/cadrumo/adapters/outbound/google/drive_entries.py`.
- [x] `S05` - Create and store a marker-stamped root folder per profile, trust a stored ID only when marker-owned, type the non-Cadrumo workbook refusal, and remove the folder-set command, the root folder setting and its environment example and reference; `src/cadrumo/adapters/outbound/storage/factory.py`.
- [x] `S06` - Resolve the publisher OAuth client through one owner that reads installation data and refuses with one typed error when none is usable, and remove the register operation with its command, input kind, contracts and correlation, the per-profile client record and namespace, and the client fields of the status and logout results, committing no client ID; `src/cadrumo/adapters/outbound/google/installation_client.py`.
- [x] `S07` - Bind the stored token to its minting client, refuse a sign-in without a refresh token, report a revoked or expired grant as a typed sign-in-required state, and use the loopback IP literal; `src/cadrumo/adapters/outbound/google/oauth_flow.py`.
- [x] `S08` - Implement or delete the stale refresh lifecycle declarations: rotated-token persistence, last refresh and reauth fields, the refresh-only login mode and the unread refresh buffer setting; `src/cadrumo/adapters/outbound/google/records.py`.
- [x] `S09` - Document the removals, the local import replacement and the re-export after a client change in the user documentation and release notes, and regenerate the references they feed; `docs`.
- [x] `S10` - Run the live proof of every listed Sheets and Drive method under drive.file alone against an application-created workbook, or record it as pending verification; `src/cadrumo/adapters/outbound/google/tests/test_oauth_live.py`.
- [x] `S11` - Commit the publisher client file with the source and include it in every build, removing the ignore rule and both build exclusions, and confirm a built wheel and sdist carry it; `src/cadrumo/_data/google/oauth_client.json`.
- [x] `S12` - Settle a definitive provider refusal under the Google configuration operation as a refusal with no effect applied, keeping UNKNOWN wherever the effect is ambiguous; `src/cadrumo/application/user_profile/google_configuration_executor.py`.
- [x] `S13` - Report an uncertain custody write during a ledger evidence batch as the designed refusal instead of a validation error; `src/cadrumo/application/ledger/evidence_ingestion_operation.py`.

## Parallelization

The Steps run in sequence in one session at a time. No Step is assigned to a
parallel worker: `S01` to `S08` all edit the same small set of Google adapter,
composition and command-specification files, so disjoint write ownership
cannot be drawn.

Hard ordering:

- `S01` and `S02` come first. They remove the two surfaces that later Steps
  would otherwise have to keep consistent.
- `S04` precedes `S05`: the created root folder relies on the refusal of
  unmarked entries.
- `S06` precedes `S07`: the token binding names the client that the resolver
  selects.
- `S08` follows `S07`, which settles the typed sign-in-required state that
  the lifecycle fields either feed or no longer need.
- `S09` and `S10` come last. `S10` may run earlier if credentials become
  available, but only after `S03` and `S04`.

Other sessions write in this worktree. Each commit stages only this plan's
own paths; nothing is stashed, reset or cleaned.

## Verification

Per Step: the covering tests for the touched area, then
`just check-import-boundaries`, `just check-style`, `just check-format` and
`just check-types` on the configured scopes, with final exit status read and
the intended tests confirmed to have run. Refusal behaviour is tested through
the real owning parser, resolver or adapter, not through a mock of it.

Plan-level success criteria:

- The desktop sign-in requests exactly `openid`, `userinfo.email` and
  `drive.file`, asserted against the flow's scope argument and the hydrated
  credential.
- No non-test source under `src/` contains the `spreadsheets`,
  `drive.readonly` or `gmail.readonly` scope strings.
- No shipped command, setting or environment override accepts a Drive folder
  or file reference from the user, except the workbook ID of spreadsheet pull,
  calculate and verify, which is refused before any content read unless the
  file carries the ownership marker.
- No non-test source references service-account impersonation, Application
  Default Credentials or the credential-source selection.
- Refusal tests exist and pass for: an unmarked entry and a foreign entry in
  both the Sheets adapter and the mirror provider; a stored root folder that
  is not marker-owned; a workbook that is not Cadrumo-created; a sign-in with
  no refresh token; a revoked or expired grant; a token bound to a different
  client; and client resolution with neither a registered nor a bundled
  client.
- Stored attachment records naming a Google source still decode.
- The command-surface reconciliation and the generated CLI reference check
  pass, and locale key coverage passes in every supported locale.
- The live proof under `drive.file` alone either ran, with the methods it
  exercised listed, or is reported as pending verification. The scope change
  is not claimed complete on documentation alone.

The plan is complete when every Step is closed and one integrated review at
plan close passes. Pre-existing failures found while running the gates are
reported separately from regressions this plan introduced.
