# Google Sheets readback, Drive ownership, and Google sign-in

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-013` · **Topic:** [External integrations and local runtime](../topics/external-integrations-and-local-runtime.md)

<!-- preserved:article -->
## Scope and capabilities

This chunk groups the Google Sheets calculation readback adapter with the shared Drive ownership policy, the Drive folder each profile works under, OAuth sign-in and session handling, and one inert outbound LLM package initializer. The primary workflow reads operator-edited calculation workbooks, checks that they belong to the application and were compiled from the current registry/layout, then returns immutable typed edits for local calculation. Related adapters find application-created Drive entries by name and create and verify the one folder a profile works under, all within the granted `drive.file` scope. Google authentication is a per-profile Desktop OAuth sign-in with the single client the installation carries; there is no other credential source.

## Main behavior and data flow

`pull_operator_edits` first validates the spreadsheet ID, confirms the Drive ownership marker, and reads developer metadata. It checks model, revision, filing year/period, engine version, and registry hash against the supplied snapshot before it derives cell addresses or reads worksheet values. Conflicting repeated identity metadata is rejected, while repeated export-time stamps are allowed. It then batch-reads manual/bound casillas, bindings, relations, and allocated detail-row blocks, preserving relation provenance metadata in typed `PullResult` records. `compute_from_pull` rechecks the snapshot binding, maps numeric and text inputs into separate channels, handles enum bindings as strings, and calls the registry Decimal runtime. Readback gates and entry point (`src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`) Metadata reconciliation (`src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`) Snapshot-match check (`src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`) Pull workflow (`src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`) Local calculation mapping (`src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`)

The pull does not persist edits. It reports nonblank cell counts and returns strict, frozen records, including per-cell row-set coordinates and typed source/legal references. Empty numeric inputs and relations are deliberately converted to Decimal zero so the calculation runtime receives its complete input lattice; blank text inputs stay absent. This makes an empty numeric cell semantically equivalent to zero in the computed result, so callers should keep the workbook instructions and review flow clear about that behavior. Typed pull records (`src/cadrumo/adapters/outbound/google/calc_sheets_pull_records.py`) Input collection and zero defaults (`src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`) Text input collection (`src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`) Relation value defaults (`src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`)

Signing in finds or creates one folder for the profile in the user's My Drive, named with the product name and the first eight characters of the profile ID, and stores its ID for the profile. The folder is looked up by name first, so a later sign-in reuses the folder an earlier one created, and a same-named entry without the ownership marker is refused rather than adopted. Nothing supplies a folder ID from outside. A stored ID is not trusted on its own: before it is used as a parent it is read back from Drive and must still be a folder, not trashed, and carrying the marker; otherwise the operation is refused. Folder naming and creation (`src/cadrumo/adapters/outbound/google/root_folder.py`) Stored-folder verification (`src/cadrumo/adapters/outbound/google/root_folder.py`)

The shared Drive-entry helper escapes query literals, returns an entry that carries the application ownership marker, and refuses any other same-named entry, whether it carries foreign properties or none; an unmarked entry is never adopted. The OAuth client is installation data rather than a profile record: one reader loads the Desktop client file the application ships with, bounds its size, and reports a missing or invalid file as one typed refusal that does not carry the parser's reason, because the file holds the value Google labels a client secret. Client validation pins the auth, token, and certificate endpoints to canonical HTTPS hostnames. Desktop OAuth verifies a resolved profile record before network I/O, requires an interactive terminal, uses a loopback flow on `127.0.0.1` with a 300-second wait bound, refuses a consent that returns no refresh token, checks granted scopes, verifies the ID token audience, and derives the account email from its verified claims. Drive query and ownership handling (`src/cadrumo/adapters/outbound/google/drive_entries.py`) OAuth record validation (`src/cadrumo/adapters/outbound/google/records.py`) Profile and terminal guards (`src/cadrumo/adapters/outbound/google/oauth_flow.py`) OAuth login flow (`src/cadrumo/adapters/outbound/google/oauth_flow.py`) ID-token verification (`src/cadrumo/adapters/outbound/google/oauth_flow.py`) Installation client reader (`src/cadrumo/adapters/outbound/google/installation_client.py`)

Per-profile records separate the secret from configuration and audit state: the refresh token uses a SECRET-class namespace; account/scope metadata and the Drive root folder use FINANCIAL-class namespaces. A stored token names the client it was minted for. A token minted for a different client, or stored without one, is never presented to Google, and a refresh that Google answers with `invalid_grant` is reported as a typed sign-in-required refusal rather than a network failure. Logout deletes token and metadata together through one batch operation, preserving the Drive configuration. Record schemas (`src/cadrumo/adapters/outbound/google/records.py`) Session persistence (`src/cadrumo/adapters/outbound/google/session_store.py`) Sign-in state (`src/cadrumo/adapters/outbound/google/sign_in_state.py`) Atomic session deletion (`src/cadrumo/adapters/outbound/google/session_store.py`)

## Security and quality observations

The strongest safety control in spreadsheet readback is the sequence of ownership and registry/layout checks before cell coordinates are derived or values are read. It prevents unrelated Drive content and stale templates from silently feeding current calculations. Decimal coercion rejects ambiguous or non-finite amount strings rather than converting them into plausible figures; text-family casillas remain text, and edits against undeclared or computed casillas are refused. The calculation is local after the pull, and the adapter does not apply or persist operator changes.

The OAuth flow refuses a credential whose `refresh_token` is absent or blank before it constructs `OAuthToken`, so a consent that returns no refresh token cannot be persisted as a session. Whether Google returns a refresh token on a repeated consent is provider behavior that this chunk does not establish. Token extraction (`src/cadrumo/adapters/outbound/google/oauth_flow.py`) Refresh-token validation (`src/cadrumo/adapters/outbound/google/records.py`)

Drive owned-entry lookup requests at most ten matching rows and acts on the first returned row: an owned entry is returned and any other is refused. It does not establish uniqueness across later matches/pages. Duplicate same-name entries can therefore make the outcome dependent on Drive response ordering or hide a later conflicting entry; this is primarily a consistency risk for repeated folder/spreadsheet creation. Owned-entry lookup (`src/cadrumo/adapters/outbound/google/drive_entries.py`)

The authentication boundary has useful typed failure distinctions for missing scopes, noninteractive use, loopback binding, endpoint/network failures, a missing or invalid installation client, a client Google no longer accepts, and a sign-in that has ended. Configuration refusals are reconstructed only from the canonical refusal projection. The local checks are structural rather than proof of the corresponding Google grants, and whether every Sheets and Drive method the export uses is accepted under `drive.file` is provider behavior not exercised here. Typed auth failures (`src/cadrumo/adapters/outbound/google/errors.py`) Canonical refusal reconstruction (`src/cadrumo/adapters/outbound/google/google_configuration_refusal.py`) Ended sign-in classification (`src/cadrumo/adapters/outbound/google/sign_in_state.py`)

## Assessment and limits

The chunk implements a coherent and fairly defensive integration boundary: strict immutable models, explicit scope checks, ownership checks, registry-hash binding, typed provider errors, per-request admission seams, and secure-object persistence are visible in the source. The main product-level ambiguity is blank numeric spreadsheet cells becoming zero. Duplicate Drive-name resolution also merits review. This is static analysis only: no Google API contract, interactive consent, credential persistence, workbook round-trip, calculation output, or remote Drive behavior was exercised here. The directory initializer for outbound LLM is intentionally inert and exposes no capability by itself.

## Coverage appendix

- calc_sheets_pull.py (`src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`) — lines 1–1237
- calc_sheets_pull_records.py (`src/cadrumo/adapters/outbound/google/calc_sheets_pull_records.py`) — lines 1–152
- drive_entries.py (`src/cadrumo/adapters/outbound/google/drive_entries.py`) — lines 1–247
- errors.py (`src/cadrumo/adapters/outbound/google/errors.py`) — lines 1–178
- google_configuration_admission.py (`src/cadrumo/adapters/outbound/google/google_configuration_admission.py`) — lines 1–96
- google_configuration_refusal.py (`src/cadrumo/adapters/outbound/google/google_configuration_refusal.py`) — lines 1–106
- installation_client.py (`src/cadrumo/adapters/outbound/google/installation_client.py`) — lines 1–128
- oauth_flow.py (`src/cadrumo/adapters/outbound/google/oauth_flow.py`) — lines 1–623
- records.py (`src/cadrumo/adapters/outbound/google/records.py`) — lines 1–244
- root_folder.py (`src/cadrumo/adapters/outbound/google/root_folder.py`) — lines 1–137
- session_store.py (`src/cadrumo/adapters/outbound/google/session_store.py`) — lines 1–231
- sign_in_state.py (`src/cadrumo/adapters/outbound/google/sign_in_state.py`) — lines 1–134
- llm/__init__.py (`src/cadrumo/adapters/outbound/llm/__init__.py`) — lines 1–12
<!-- /preserved:article -->
