---
tags:
  - '#reference'
  - '#google-app-identity'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:e9c04b78fc9674a0608f682cd15c9a83692dd938cac1d42ee3c21feb99ea3048'
related: []
---

# `google-app-identity` reference: `Implemented Google OAuth, Drive and Sheets surface`

How Cadrumo's Google sign-in, Drive and Sheets code behaves today, read to
decide whether it can run on a publisher-owned client restricted to
application-created files.

Provenance. Static reading only on 2026-10-04, branch `feature/tui` at commit
`c74ce317a9` with a dirty working tree; nothing was run and no live Google
call was made. Most locators come from a separate inspection session; the
ones re-read while writing this record are `oauth_flow.py`, `records.py:40-190`,
`calc_sheets_apply.py:260-363`, `drive_entries.py:52-85` and `:199-269`, and
`storage/factory.py:206-249`. `google_auth_oauthlib/flow.py` was read from the
uv-managed interpreter's site-packages, which reports 1.5.0, not from a
project environment. Statements marked "inferred" rest on Google's documented
semantics, not on code or a test. Re-check line numbers after any change.
Paths are relative to `src/cadrumo/` unless they start with another root.

## Summary

### Sign-in flow

- Desktop flow through `InstalledAppFlow.run_local_server(port=0,
  timeout_seconds=300)` with no host argument
  (`adapters/outbound/google/oauth_flow.py:359-365`). The library default
  binds and redirects to `localhost`; the `["http://localhost"]` fallback at
  `oauth_flow.py:573` only populates client configuration.
- PKCE S256 and `access_type=offline` come from library defaults
  (`google-auth-oauthlib` pinned `>=1.3.1,<2` at `pyproject.toml:164`,
  resolved 1.5.0). Cadrumo sets no `prompt` and no `include_granted_scopes`.
- The login requests exactly `REQUIRED_SCOPES`: `openid`, `userinfo.email`,
  `drive.file`, `spreadsheets` (`adapters/outbound/google/records.py:50`,
  values at `core/external_constants.toml:307-311`). Hydration requests the
  same set (`adapters/outbound/storage/factory.py:206-219`).
- A granted set missing any required scope is refused
  (`oauth_flow.py:207-222`).

### Client identity

- Operator-imported only. `config google register`
  (`entrypoints/cli/config/runtime_google_registration.py:27`) decodes the
  Cloud Console JSON (`adapters/outbound/google/google_configuration_inputs.py:28`).
  No bundled or default client exists; the only bundled Google constants are
  the four scopes.
- The whole `OAuthClient`, `client_secret` included, is one encrypted object
  per profile in namespace `cadrumo.google.oauth.client`, classified SECRET
  and PROFILE_LOCAL
  (`adapters/persistence/storage/secure_object_namespaces.py:857-866`,
  `adapters/outbound/google/session_store.py:75-91`). The record's docstring
  treats `client_secret` as a long-lived credential (`records.py:105-114`).
- Neither `OAuthToken` nor `OAuthMetadata` records which client minted the
  token (`records.py:143-190`). The token namespace schema version is at
  `secure_object_namespaces.py:867-876`.
- Inferred from declarations, not run: the client and token namespaces
  inherit the default remote-mirror policy CIPHERTEXT_WITH_METADATA
  (`secure_object_namespaces.py:91`), and `config profile archive push`
  iterates all rows (`adapters/outbound/storage/mirror_push.py:205`), so their
  ciphertext would be uploaded to Drive.

### Paths that touch files Cadrumo did not create

All are reachable with the desktop credential source.

- Root folder. Always a user-supplied ID, never created by Cadrumo. Set by
  `config google folder set`
  (`entrypoints/google_configuration_operation_composition.py:317-323`) or the
  `CADRUMO_GOOGLE_DRIVE_ROOT_FOLDER_ID` override
  (`adapters/outbound/storage/factory.py:228-249`). It is read with
  `files.get` (`adapters/outbound/storage/_google_drive.py:1167`), listed as a
  parent, and used as the parent of every created folder and workbook. The
  Sheets export, the ciphertext mirror and `config google probe` share it
  (`storage/factory.py:326-340`). Inferred: under `drive.file` a folder made
  in the Drive interface is invisible to the application unless chosen through
  Google Picker, and no Picker exists in the code; how this works live today
  is unknown.
- `app ledger evidence pull --source google_drive`
  (`entrypoints/cli/_app_ledger_operations_command_specs.py:78-103`):
  `files.get_media` on a user-supplied file reference
  (`adapters/outbound/google/document_link_resolver.py:224-237`, `:263`).
- `app ledger evidence pull-all --folder`
  (`entrypoints/cli/_app_ledger_management_command_specs.py:502-512`):
  `files.list` of a user-supplied folder's children
  (`document_link_resolver.py:379-389`, `:506`), then `get_media` per child
  (`adapters/outbound/google/document_acquisition.py:91-101`).
- Spreadsheet pull, calculate and verify take a spreadsheet ID as input: a
  Drive `files.get` metadata read on that ID
  (`adapters/outbound/google/calc_sheets_pull.py:189`), refused unless the
  ownership marker is present (`:210`); Sheets content is read only after
  that (`:500-501`).
- Unmarked adoption. A same-named entry under the expected parent with no
  `appProperties` is stamped and treated as owned
  (`adapters/outbound/google/drive_entries.py:248-262`; the mirror provider
  has its own copy at `adapters/outbound/storage/_google_drive.py:554-602`).
  Ownership is decided by the marker only, never by creator. Inferred: under
  `drive.file` the listing would not return user-created files, so this is
  safe by scope rather than by code.

The document-link resolver never inspects credential scopes. Its
`gmail.readonly` and `drive.readonly` constants
(`document_link_resolver.py:53-54`) are refusal text only. Gmail and URL
sources refuse unconditionally (`:213-223`, `:238-248`); the Drive source
attempts the fetch and maps 403/404 to a refusal (`:274-290`).

### API methods called

- Sheets: `spreadsheets.create` (`calc_sheets_apply.py:333`),
  `spreadsheets.get`, `spreadsheets.batchUpdate`, `values.batchGet`,
  `values.batchUpdate`, `values.batchClear`.
- Drive: `files.create`, `files.get`, `files.update`, `files.list`,
  `files.get_media`, `files.delete`.
- Not called anywhere: `permissions.*`, `drives.*`, `about`, `copy`, `export`.
- Every `files.list` is parent-scoped (`'<id>' in parents and ...`,
  `drive_entries.py:118-120`); there is no Drive-wide search and no query on
  `appProperties`.
- Inferred, untested: every listed Sheets method accepts `drive.file` for an
  application-created workbook.

### Ownership marker

- `appProperties` `cadrumo_vault_app=cadrumo` (`drive_entries.py:52-53`),
  classified OWNED, UNMARKED or FOREIGN at `drive_entries.py:74-85`.
- Folders are created with the marker in the `files.create` body
  (`calc_sheets_apply.py:266-276`). Workbooks are not: Sheets
  `spreadsheets.create`, then a Drive `files.get` for parents, then a
  `files.update` that moves and stamps (`calc_sheets_apply.py:332-362`). A
  failure between the calls leaves an application-created, unmarked workbook
  in the Drive root.
- Inferred: `appProperties` and `drive.file` visibility are private to the
  client that wrote them, so files created under one client are invisible to
  another.

### Service-account impersonation

- `config google credential-source set --scope` accepts arbitrary scope
  strings with no allowlist
  (`entrypoints/cli/config/_google_command_specs.py:223-229`,
  `adapters/outbound/google/impersonation.py:168`). It is the only credential
  source that could carry a restricted scope.
- The default target scopes are `drive.file` and `spreadsheets`
  (`adapters/outbound/google/impersonation.py:98`, `:168`), and the selection
  is persisted as JSON (`adapters/outbound/google/session_store.py:226-246`).
- No non-test source calls `permissions.*` or passes `supportsAllDrives` or
  `driveId`, so Cadrumo can neither share a file nor write to a shared drive.
  The impersonation path works today only when the operator shares a folder
  with the service account and supplies its ID.

### Evidence acquisition vocabulary

- `AttachmentSource.URL` is used by AEAT notification-document custody
  (`application/live/notification_documents.py:396`), unrelated to Google.
- `AttachmentSource.GOOGLE_DRIVE` is read at
  `application/ledger/attachment_review.py:36` and `:102` and written at
  `application/ledger/evidence_ingestion_operation.py:304-310`, so stored
  attachment records can carry it. Whether `GMAIL` has a persisted writer is
  unknown.
- Local alternatives already exist: `app ledger evidence batch` takes a
  directory and repeatable `--file`
  (`entrypoints/cli/_app_ledger_evidence_command_specs.py:120-157`), and
  `app ledger invoice import --file`
  (`entrypoints/cli/_app_ledger_invoice_intake_command_specs.py:93-117`).

### Token lifecycle

- The refresh token is written only at consent
  (`entrypoints/google_configuration_operation_composition.py:397`) to
  namespace `cadrumo.google.oauth.token`
  (`adapters/outbound/google/session_store.py:112-129`).
- `oauth_flow.py:588` stringifies `credentials.refresh_token`; the
  `OAuthToken` validator rejects only blank strings (`records.py:156-165`), so
  the literal `"None"` can be persisted if the library ever returns no
  refresh token. No trigger is known: Google states that installed
  applications always receive one
  (`2026-10-04-google-app-identity-research`).
- No Cadrumo code refreshes the desktop credential; `google-auth` does so in
  the API transport. A refresh failure is wrapped as a network error with
  condition `google.api.transport_unavailable`
  (`adapters/outbound/google/api.py:196-208`), with `effect_uncertain` set on
  single-attempt writes.
- `GoogleAuthRevokedError` (`adapters/outbound/google/errors.py:84`) is never
  raised. `reauth_required` is never set true and `last_refresh_at` is never
  updated after login, despite the docstrings at `records.py:149-151` and
  `:169-178`. `login --refresh-only` makes no network call. The setting
  `cadrumo_google_oauth_access_refresh_buffer_s`
  (`core/config_integration_fields.py:44`) has no reader.

### Surfaces

- No Google references in non-test TUI source or in `cadrumo_harness` source.
  Whether MCP operation discovery exposes the evidence-pull operation is
  unknown.
- `native/` has one test fixture with a "Connect Google account" action
  (`native/application/tests/application.rs:246-253`).
