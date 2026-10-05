---
tags:
  - '#adr'
  - '#google-app-identity'
date: '2026-10-04'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:6c1bc1c8358841af65168b4466031b88fcc037377fcd9a634652254dfcce063c'
related:
  - "[[2026-10-04-google-app-identity-adr]]"
  - "[[2026-10-04-google-app-identity-reference]]"
  - "[[2026-10-04-google-app-identity-research]]"
---

# `google-app-identity` adr: `Single client resolution path without operator registration` | (**status:** `deprecated`)

Retired on 2026-10-05: the product owner approved this amendment and its
wording was applied to `2026-10-04-google-app-identity-adr`, which is now the
only authority for it. This record is kept as the history of the proposal.

## Problem Statement

This record held a pending amendment to commitment 3 of
`2026-10-04-google-app-identity-adr`.

Commitment 3 keeps a client registered by the operator as a supported,
per-profile production override. On 2026-10-05 the product owner refused to
load the development project's client through that command: "we established
the oauth json route is a development only test route yet the config google
register command is a production interface - we're conflating production code
with development and I cannot allow that". The accepted text and the product
owner's position disagree. The override was written into commitment 3 without
an explicit ruling on it, and acceptance of the whole record was read as
covering it.

## Considerations

- `config google register` is the only way any client reaches a profile today;
  no installation-level client reader exists
  (`2026-10-04-google-app-identity-reference`).
- Loading the publisher's own client through a per-profile override would
  exercise the override path instead of the path commitment 3 makes primary.
- A desktop client's metadata, `client_secret` included, is not confidential
  (`2026-10-04-google-app-identity-research`), so it needs no secret channel
  and no profile custody.
- Whether Google refreshes a Desktop client's token without `client_secret`
  was not tested, so the value travels with the metadata.
- The earlier reason for an override, organisations that block third-party
  clients, has another answer: an administrator can allow the publisher
  client.

## Considered options

1. **One client, one path.** Chosen. Cadrumo reads one publisher client's
   public metadata from one installation location; no command accepts a
   client. Development and production differ only in which client file the
   installation holds.
2. **Keep registration as development-only tooling inside the shipped
   command tree.** Rejected: a development route in the production interface
   is the conflation the product owner refused.
3. **Keep commitment 3 as accepted.** Rejected by the product owner's
   statement above.

## Constraints

Replacement text for commitment 3 of `2026-10-04-google-app-identity-adr`:

3. **Client identity.** A publisher-owned Desktop client is the only client.
   Its metadata is public installation data read from one location by one
   resolver; it is not a profile record and not a secret. No command, setting
   or environment override accepts a client from the operator. A development
   installation uses the same location and the same code path, holding the
   development project's client file, which the developer supplies and which
   is never committed. With no client metadata present, sign-in is a typed
   refusal with remediation.

Consequential changes to the same record:

- Commitment 9 gains: "A stored per-profile client record is never honoured,
  and its namespace registration is removed; the team's test profiles are
  cleared by hand."
- Commitment 10 gains `config google register` in the released surface removed
  without a deprecation window.
- The authorization-basis sentence "and commitment 3 as written, including the
  optional operator-registered client" is replaced by a citation of this
  amendment and its acceptance date.
- The Implementation lead sentence drops "keeping the operator-registered
  client as a per-profile override", and the Rationale drops the sentence
  beginning "Keeping the imported client as an override".
- Commitment 8 is unchanged and gains a reason: binding a token to its client
  is what stops a token minted under the development client being used with
  the production one.

## Implementation

We will resolve the Google client from installation data only, and remove
operator registration.

Outline:

- Remove the `config.google.register` operation, its command, input kind,
  contracts and correlation, and the per-profile client record with its
  namespace.
- Status and logout results lose their client-registration fields, which
  changes two public result schemas; six `config.google` operations remain.
- Replace the "client not registered" refusals with one "no client metadata
  in this installation" refusal.

Implementation hypotheses, free to change within the commitment:

- The location is the installation's `data/google/` directory named in
  `2026-10-03-application-packaging-adr`; a development checkout resolves it
  through the same storage taxonomy.
- A helper under `dev/` may place a client file into a development
  installation. It is not part of the shipped command tree.

## Rationale

One path means the sign-in the publisher verifies with Google is the sign-in
developers test, so the live proof exercises production behaviour. It removes
a secret-classified profile record for a value that is not secret, and it
removes the only remaining way a user could be asked to bring a Cloud project.

## Consequences

- An organisation that blocks third-party clients must allow the publisher
  client; it cannot substitute its own.
- A development installation cannot sign in until a developer supplies a
  client file.
- Operators on a tagged release lose `config google register` at upgrade with
  no transition period.
- Until build-time delivery of the client metadata exists, which is packaging
  work, only development installations can sign in.
