# Shared CLI transport and profile configuration surfaces

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-166` · **Topic:** [Operator interfaces, part 1: command graph and principal workflows](../topics/operator-interfaces-part-1.md)

<!-- preserved:article -->
## Scope

This 28-file slice covers command loading and suggestions, shared output/action transport, profile history and mutations, censal import/pull, authentication and representative setup, profile backup schemas, collaboration recipients, and Google configuration. I read all 5,584 assigned lines (46,296 measured tokens) across the nine planned pages. This is static analysis; I did not run commands, access an account, or contact AEAT, Google, or a remote storage provider.

## Command routing, output, and taxpayer identity

The Typer group keeps command families lazy. It lists names and renders help/completion from registration metadata, importing a subtree only when that command is selected. Import targets name an explicit module and public attribute; a missing dependency is treated as optional only when it matches the target’s declared optional set, otherwise the normal failure path applies. It also preserves the operator’s unparsed remainder in Click context metadata so root guards can recognize help and unknown-command cases without relying on process `argv`. Synonym hints supplement ordinary typo suggestions for selected profile and app commands (command loading and suggestions (`src/cadrumo/entrypoints/cli/command_suggestions.py`)).

The shared transport resolves registered action references against the live action catalogue and command input schema, verifies that argument bindings match declared inputs and provenance, then derives current CLI paths and copyable next-action commands. PowerShell tokens are quoted as literal single-quoted strings when needed, including embedded typographic quotes, so shell expansion does not reinterpret supplied values. `emit_envelope` centralizes strict JSON envelopes, typed notices, active-profile identity and sandbox indicators. Metadata calls skip profile, sandbox, and notice discovery; ordinary text output adds notices and actions through the same renderer used for streamed progress. The progress funnel masks tax identifiers and opaque record IDs, but its own contract explicitly does not mask filesystem paths. Consumers that place paths on streamed lines therefore expose those paths (shared transport (`src/cadrumo/entrypoints/cli/common.py`)).

The common profile projection preserves an important filing invariant. Read-only calendar-style callers may use a synthetic placeholder tax ID when the profile has no declared identity, but `filing_taxpayer_or_refuse` checks the actual `identity.tax_id` fact and refuses before producing a declaration under that placeholder. Its refusal resolves the missing selector against the authenticated operation’s pinned profile schema and registry grounding. The same module provides a consistent no-active-profile refusal that distinguishes “create a profile” from “log in to an existing one,” and repository helpers keep profile-backed reads behind the selected bucket (identity and filing guards (`src/cadrumo/entrypoints/cli/common.py`)).

## Profile facts, readiness, and censal evidence

Profile history binds to the authenticated or explicitly resolved profile, parses event-type and time filters, normalizes naive timestamps to UTC, and projects each event with its typed payload. Capability view reads one authenticated profile revision and evaluates declared service capabilities against profile facts and settings. Capability writes use the profile’s expected revision and content digest, then verify the committed value in a fresh read; if that post-write view is unavailable, the refusal still reports the operation ID and that the commit succeeded. `complete-setup` similarly checks the exact active profile, reads the overview baseline, names missing required facts, and submits a revision-bound promotion request. The result reports a readiness claim and the revision, including idempotent completion; it does not expose the profile’s facts or claim that every downstream service is ready (history (`src/cadrumo/entrypoints/cli/config/_bucket_history.py`), capability commands (`src/cadrumo/entrypoints/cli/config/_capabilities_cli.py`), setup promotion (`src/cadrumo/entrypoints/cli/config/_complete_setup_cli.py`), setup result (`src/cadrumo/entrypoints/cli/config/_complete_setup_payloads.py`)).

Censal data has two intentionally different sources. File import is labeled non-official; the module documents that its inbound certificate adapter is currently structure-only and refuses documents, so this CLI code does not establish that G313 files can presently be enrolled. The live pull is scoped to the authenticated profile’s own session and currently fills identity and address, not censal regime fields. Preview is the default. Applying uses the registered prepare/review runtime and an explicit confirmation defaulting to “no.” The transport reports adopted, unchanged, and diverging values separately; declared answers and deliberate clears remain for the operator to adjudicate. If the reviewed operation is rejected, proposed adoptions are removed from the result. Divergence notices distinguish conflicting values, redacted values, and profile-cleared paths, and do not attach an automatic action. The application/runtime layer remains authoritative for the live read, data reconciliation, and write (censal transport (`src/cadrumo/entrypoints/cli/config/_censo_transport.py`), review prompt (`src/cadrumo/entrypoints/cli/config/_censo_review_cli.py`), censal payloads (`src/cadrumo/entrypoints/cli/config/_censo_payloads.py`)).

## Authentication, representatives, and profile backup

Authentication commands expose provider catalogue, configure, status, test, login, logout, and reset. Status/test project local readiness and precondition actions; login is the live session operation. Logout removes sessions but preserves provider configuration, while destructive reset requires `--yes`. Cl@ve Móvil output separates whether a profile tax ID exists, whether the provider identity exists, and whether they align. Diagnostic listing omits captured HTML/screenshots; detail output reports structured configuration, fingerprints, reported phone state, and an HTML excerpt. The exact redaction and persistence guarantees depend on the runtime auth readers and diagnostic services outside this slice (auth handlers (`src/cadrumo/entrypoints/cli/config/_auth.py`), auth command authority (`src/cadrumo/entrypoints/cli/config/_auth_command_specs.py`), diagnostic projection (`src/cadrumo/entrypoints/cli/config/_auth_diagnostics.py`)).

Apoderado configuration writes only to the encrypted representative namespace, not as a taxpayer profile fact. The represented NIF is sent to the registered configure operation; invalid-NIF refusals intentionally omit it from refusal context. Configuration can use command options or a paged interaction. `status` is an offline configuration read. `check` does not claim live verification: the handler documents that live AEAT reads are not wired and delegates to a refusal. Scopes come from the service catalogue. Password-change/reset, login/logout, and certificate-secret command declarations separately describe machine-secret fields and input channels, with reset marked destructive; their secure readers are not in this chunk (representative commands (`src/cadrumo/entrypoints/cli/config/_apoderado.py`), custody declarations (`src/cadrumo/entrypoints/cli/config/_custody_command_specs.py`)).

Profile archive export writes a sealed encrypted capsule and refuses a bad suffix or existing destination before reading the capsule. The archive omits the profile label; key-free inspection reports the plaintext header (product, bucket ID, schema version, creation time, manifest digest) and no recovery-enrollment status. A separate push payload describes remote mirroring of ciphertext objects and namespace manifests, not a portable archive: failed objects are identified by namespace/HMAC rather than plaintext. It also makes cleanup failure visible because an object left remotely after rollback failure may have no manifest to enumerate it. Reconciliation payloads distinguish journals whose staged cleartext was removed from failures left journalled for later retry. These are security-relevant states; the actual archive cryptography, remote storage, and reconciliation implementation were not inspected here. Collaboration declarations likewise make public-key recipient add/list/remove available, but key validation and trust are delegated (archive export/inspect (`src/cadrumo/entrypoints/cli/config/_archive_cli.py`), mirror result schema (`src/cadrumo/entrypoints/cli/config/_archive_push_payloads.py`), reconciliation result schema (`src/cadrumo/entrypoints/cli/config/_archive_reconcile_payloads.py`), collaboration command authority (`src/cadrumo/entrypoints/cli/config/_collab_command_specs.py`)).

Google commands distinguish client registration, OAuth login/status/logout, credential-source selection, folder configuration, and provider probing. Result schemas omit client secrets, refresh tokens, and service-account private keys; login/status expose account email, scopes, presence and timestamps. Impersonation selection requires a target principal when scopes, delegates, subject, or lifetime are supplied, then reconstructs the canonical selection for validation. The token is described as re-derived from Application Default Credentials rather than stored in the CLI payload. Drive folder IDs and probe facts are projected as configuration/health, not proof of a successful sync. Credential acquisition, OAuth, remote permissions, and storage-provider behavior remain delegated (Google command authority (`src/cadrumo/entrypoints/cli/config/_google_command_specs.py`), credential-source handler (`src/cadrumo/entrypoints/cli/config/_google_credential_source_cli.py`), credential-source validation (`src/cadrumo/entrypoints/cli/config/_google_credential_source_payloads.py`), folder commands (`src/cadrumo/entrypoints/cli/config/_google_folder.py`), Google result schemas (`src/cadrumo/entrypoints/cli/config/_google_payloads.py`)).

The profile create/edit dispatcher constructs wizard flows only after the selected lazy leaf is resolved. It keeps the pinned registry operation lease around flow construction and dispatch, routes creation through scripted registration, and routes editing through the wizard’s runtime patch persister. A shared command error boundary wraps both modes, avoiding wizard imports on unrelated config commands. Config schema helper and check declaration keep deferred payload references and the workstation check surface import-light. This code establishes routing and schema intent; it does not establish the wizard’s profile-update correctness or the workstation check’s diagnostic coverage (profile wizard dispatch (`src/cadrumo/entrypoints/cli/config/_manager_dispatch.py`), shared schema declaration (`src/cadrumo/entrypoints/cli/config/_command_spec_schema.py`), check command authority (`src/cadrumo/entrypoints/cli/config/_check_command_specs.py`)).

## Evidence and limits

The strongest evidence here is the separation of data provenance and authority: local certificate artifacts are explicitly non-official, reviewed live censal values retain divergences, live representative verification is not falsely reported, and filing output refuses a synthetic identity. Revision/digest checks and read-after-write verification constrain profile mutation. Material limits are the delegated parsers, authenticated runtime operations, archive cryptography, diagnostics redaction, OAuth/Drive provider, and collaboration-key trust; this pass did not exercise them. The command declarations are a useful capability map but cannot prove that implementation effects match policy without inspecting the owning services.

## Coverage appendix

All 28 assigned files are linked below.

- `src/cadrumo/entrypoints/cli/command_suggestions.py`
- `src/cadrumo/entrypoints/cli/common.py`
- `src/cadrumo/entrypoints/cli/config/__init__.py`
- `src/cadrumo/entrypoints/cli/config/_apoderado.py`
- `src/cadrumo/entrypoints/cli/config/_archive_cli.py`
- `src/cadrumo/entrypoints/cli/config/_archive_push_payloads.py`
- `src/cadrumo/entrypoints/cli/config/_archive_reconcile_payloads.py`
- `src/cadrumo/entrypoints/cli/config/_auth.py`
- `src/cadrumo/entrypoints/cli/config/_auth_command_specs.py`
- `src/cadrumo/entrypoints/cli/config/_auth_diagnostics.py`
- `src/cadrumo/entrypoints/cli/config/_bucket_history.py`
- `src/cadrumo/entrypoints/cli/config/_capabilities_cli.py`
- `src/cadrumo/entrypoints/cli/config/_censo_payloads.py`
- `src/cadrumo/entrypoints/cli/config/_censo_review_cli.py`
- `src/cadrumo/entrypoints/cli/config/_censo_transport.py`
- `src/cadrumo/entrypoints/cli/config/_check_command_specs.py`
- `src/cadrumo/entrypoints/cli/config/_collab_command_specs.py`
- `src/cadrumo/entrypoints/cli/config/_command_spec_schema.py`
- `src/cadrumo/entrypoints/cli/config/_complete_setup_cli.py`
- `src/cadrumo/entrypoints/cli/config/_complete_setup_payloads.py`
- `src/cadrumo/entrypoints/cli/config/_custody_command_specs.py`
- `src/cadrumo/entrypoints/cli/config/_google_command_specs.py`
- `src/cadrumo/entrypoints/cli/config/_google_credential_source_cli.py`
- `src/cadrumo/entrypoints/cli/config/_google_credential_source_payloads.py`
- `src/cadrumo/entrypoints/cli/config/_google_folder.py`
- `src/cadrumo/entrypoints/cli/config/_google_folder_payloads.py`
- `src/cadrumo/entrypoints/cli/config/_google_payloads.py`
- `src/cadrumo/entrypoints/cli/config/_manager_dispatch.py`
<!-- /preserved:article -->
