---
tags:
  - '#research'
  - '#google-app-identity'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:1b3c0d4dbce0df9d1e4489e3c7734d1511feefedf2cba8aab1f7e63122f149fe'
related: []
---

# `google-app-identity` research: `Google OAuth registration and verification for a desktop client`

What does Google require before a distributed desktop application can let
arbitrary users sign in and write to their Drive and Sheets, and which choices
decide how heavy that requirement is? The question matters because Cadrumo
currently relies on each operator importing a personal Cloud Console client.
The evidence picture: the requested scope set decides the verification tier,
the publishing status decides who can sign in and for how long, and a desktop
client's credentials are public by design. All pages were fetched on
2026-10-04; Google revises these policies, so re-fetch before relying on a
number.

## Findings

### The most sensitive requested scope sets the verification tier

Google sorts scopes into non-sensitive, sensitive and restricted. For the
scopes Cadrumo touches or names:

- `drive.file` is non-sensitive and is the scope Google marks as recommended
  for the Sheets API. It covers only files the application created or the user
  opened with it.
  https://developers.google.com/workspace/sheets/api/scopes
- `spreadsheets` and `spreadsheets.readonly` are sensitive.
  https://developers.google.com/workspace/sheets/api/scopes
- `drive` and `drive.readonly` are restricted.
  https://developers.google.com/workspace/sheets/api/scopes
- `openid` and `userinfo.email` are basic identity scopes; an application
  requesting only those is exempt from the test-user allowlist and the 7-day
  expiry below.
  https://support.google.com/cloud/answer/15549945

What each tier costs a published external application:

- Non-sensitive only: brand verification. It needs the application name, logo,
  support email, a home page, a privacy policy, and ownership of every
  authorized domain proven in Search Console. Usually automated within
  minutes; manual review takes 2-3 business days.
  https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification
- Any sensitive scope: additionally an unlisted demonstration video showing the
  consent flow with the client ID visible, and a written justification per
  scope explaining why a narrower scope is insufficient. Typically 3-5
  business days.
  https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification
- Any restricted scope: restricted-scope verification, and for an application
  able to access the data from or through a third-party server, a security
  assessment by an empanelled assessor repeated at least every 12 months. The
  page states no exemption for device-only storage.
  https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification

Because Google itself lists `drive.file` for the Sheets API, a justification
that `spreadsheets` is needed for application-created workbooks would have to
argue against Google's own recommendation.

Not investigated: whether `drive.file` alone is accepted by every Sheets
method Cadrumo calls. The scope page implies it; no live call was made.

### Publishing status decides who can sign in and for how long

- Testing: only allowlisted test users, hard cap of 100, and authorizations
  expire 7 days after consent, refresh token included.
  https://developers.google.com/identity/protocols/oauth2/production-readiness/overview
  https://support.google.com/cloud/answer/15549945
- Published and unverified: hard cap of 100 users in total, no application
  name or logo on the consent screen, and a warning screen when sensitive or
  restricted scopes are requested.
  https://developers.google.com/identity/protocols/oauth2/production-readiness/overview
- Published and verified: no cap, normal consent screen.
- Internal (one Workspace organisation) needs no verification but admits only
  that organisation's users.

### A desktop client is a public client

- Google assumes installed applications cannot keep secrets; `client_secret`
  is optional in the token exchange. Shipping the client metadata inside the
  application is the expected pattern.
  https://developers.google.com/identity/protocols/oauth2/native-app
- The supported redirect for Windows, macOS and Linux desktop applications is
  a loopback listener on `http://127.0.0.1:port` or `http://[::1]:port` with a
  random port. Desktop-type clients need no redirect URI registered. Custom
  URI schemes are no longer supported.
  https://developers.google.com/identity/protocols/oauth2/native-app
  https://developers.google.com/identity/protocols/oauth2/resources/loopback-migration
- PKCE is supported and marked recommended, not mandatory.
  https://developers.google.com/identity/protocols/oauth2/native-app
- Incremental authorization is not supported for installed applications, so
  the full scope set is requested at sign-in.
  https://developers.google.com/identity/protocols/oauth2/native-app

Consequence of a public client: anyone can extract the client ID and present a
consent screen in the application's name. The exposure is bounded by the
scopes the client is allowed to request.

### Options the evidence frames

- Each operator imports a personal Cloud Console client (today). No
  verification, but every user must create a Cloud project, and a personal
  project left in Testing gives 7-day sign-ins.
- One publisher-owned client requesting only non-sensitive scopes. Brand
  verification only; requires a publisher domain, home page and privacy
  policy.
- One publisher-owned client that keeps `spreadsheets`. Adds the video and a
  justification that contradicts Google's recommendation.
- Any client requesting `drive.readonly` or Gmail scopes. Restricted tier.

The evidence favors the second option. The ADR must settle the scope set, who
owns the client, and what happens to code paths that need more than
`drive.file`.

### Refresh tokens for a desktop client

- "Refresh tokens are always returned for installed applications", so a
  desktop sign-in needs no forced consent prompt to obtain one.
  https://developers.google.com/identity/protocols/oauth2/native-app
- A refresh token stops working when the user revokes access, when it has
  been unused for six months, when time-based access expires, when an
  administrator restricts a requested service, or when the account exceeds
  the limit of 100 refresh tokens per Google Account per client ID, in which
  case the oldest is invalidated without notice.
  https://developers.google.com/identity/protocols/oauth2

### A service account cannot own the exported files

- "Service accounts don't have storage quota and can't own any files.
  Instead, they must upload files and folders into shared drives, or use
  OAuth 2.0 to upload items on behalf of a human user."
  https://developers.google.com/workspace/drive/api/guides/handle-errors
- A credential source that acts as a service account can therefore place a
  file where a person sees it only by writing into a shared drive, by writing
  under a folder a person shared with it, or by acting for a Workspace user
  through domain-wide delegation. Without one of those the export either
  fails on quota or is visible to nobody.

Not investigated: whether a folder merely shared with a service account is
reachable under `drive.file`.

### Unverified general knowledge

Stated from memory or by inference, not from a page fetched on 2026-10-04:
`drive.file` access and `appProperties` are scoped to the Cloud project that
owns the client. Google's Drive reference says `appProperties` are "private
to the requesting app" without defining whether "app" means the client or the
project.

## Sources

- https://developers.google.com/workspace/sheets/api/scopes
- https://developers.google.com/workspace/drive/api/guides/api-specific-auth
- https://developers.google.com/identity/protocols/oauth2/native-app
- https://developers.google.com/identity/protocols/oauth2/resources/loopback-migration
- https://developers.google.com/identity/protocols/oauth2/production-readiness/overview
- https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification
- https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification
- https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification
- https://support.google.com/cloud/answer/15549945
- https://developers.google.com/identity/protocols/oauth2
- https://developers.google.com/workspace/drive/api/guides/handle-errors
