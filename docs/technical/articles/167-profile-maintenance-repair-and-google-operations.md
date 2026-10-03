# Profile maintenance, repair, and Google operations

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-167` · **Topic:** [Operator interfaces, part 1: command graph and principal workflows](../topics/operator-interfaces-part-1.md)

<!-- preserved:article -->
## Scope

This 42-file slice covers profile inspection and mutation, repair and backup reconciliation, secure custody, certificate sources, descendant facts, workstation checks, and Google account/Drive operations. I read all 5,971 assigned lines (47,642 measured tokens) across the nine planned pages. I inspected code and declared transport contracts only; I did not execute commands, connect to an account, or test filesystem, runtime, browser, or provider effects.

## Profile lifecycle and repair

Single-profile deletion requires a named profile and defaults to a non-mutating preflight. That result includes the label, content fingerprint, and a retention assessment; the command refuses the active profile and has no retention override. With confirmation, deletion rechecks inactivity under the profile-pointer transaction and delegates prepare/confirm/delete to the journalled capsule lifecycle, holding the canonical lock through completion. The implementation delegates inventory-witness validation and crash recovery to that lifecycle. Its local documentation cites a four-year retention floor and LGT articles 66/67/70.2; I have not independently checked current law or assessed whether that rule fits every record type. The separate all-profile reset command specification includes durable-operation start/status/resume and a reason-bearing retention override; its implementation is outside this slice (single-profile deletion (`src/cadrumo/entrypoints/cli/config/_profile_delete.py`), all-profile reset command contract (`src/cadrumo/entrypoints/cli/config/_reset_command_specs.py`)).

Profile `view` and `validate` operate on an authenticated profile projection; blocking results exit with status 2. `view` can inspect a named or active target, while `validate` can also address a tombstoned profile for diagnosis. Helpers distinguish a missing profile record from an unreadable one and attach a resolved precondition action rather than guessing a recovery command. Repeatable-row add/edit/remove reads the same pinned schema that validates values, accepts field assignments with duplicate detection, and uses stable row keys. Edit keeps omitted fields and clears only explicit fields. Each mutation submits expected record revision and content digest, then checks the settled revision through a shared 120-second baseline/write/readback budget; if the readback fails after commit, the refusal says the write succeeded and includes the operation ID (profile inspection (`src/cadrumo/entrypoints/cli/config/_profile_inspect.py`), profile readiness (`src/cadrumo/entrypoints/cli/config/_profile_readiness.py`), repeatable-row mutations (`src/cadrumo/entrypoints/cli/config/_profile_repeatable_row.py`), mutation settlement (`src/cadrumo/entrypoints/cli/config/_runtime_profile_mutation.py`)).

Repair commands expose profile-pointer diagnosis/repair, workflow-progress reset, unreadable secure-object quarantine, integrity counts, connectivity, and log-tail reads. Quarantine and reset-progress require `--yes` unless `--dry-run` is selected; no active profile yields a no-op report for those two operations. Profile pointer repair requires a named target to match the active pointer and redacts unresolved internal IDs in its result. Logs default to 20 lines and are read from the configured path with replacement decoding. The workstation doctor reports active capabilities, dependencies, and preflight rows, but its schema explicitly derives `ok` from capability/dependency issues: an unhealthy preflight row by itself does not change the exit code. Preflight rows must still carry a resolved outcome. Command policies distinguish local reads, encrypted reads, browser connectivity, and network effects; these declarations are not a substitute for inspecting each delegated repair/provision service (repair handlers (`src/cadrumo/entrypoints/cli/config/_repair_cli.py`), repair policies and commands (`src/cadrumo/entrypoints/cli/config/_repair_command_specs.py`), profile repair (`src/cadrumo/entrypoints/cli/config/_repair_profile.py`), workstation report (`src/cadrumo/entrypoints/cli/config/check_cli.py`), workstation payload contract (`src/cadrumo/entrypoints/cli/config/check_payloads.py`), provision command policy map (`src/cadrumo/entrypoints/cli/config/_provision_command_specs.py`), storage commands (`src/cadrumo/entrypoints/cli/config/_storage_command_specs.py`)).

Archive reconciliation is a local-only sweep over interrupted bundle-publication journals. The source explains its purpose: after a crash, a mode-0600 `.export-tmp` may contain a cleartext staged profile bundle. Reconciled entries report that staging was cleared; failures remain journalled and produce a warning, because an unreconciled journal can still describe cleartext bundle bytes. When publication had already completed, the sweep records the owed export event in encrypted storage. This behavior is the strongest recovery boundary visible here, but the file/journal transitions themselves live in the application operation (archive reconciliation handler (`src/cadrumo/entrypoints/cli/config/archive_reconcile.py`), reconciliation payloads (`src/cadrumo/entrypoints/cli/config/_archive_reconcile_payloads.py`)).

## Custody and taxpayer facts

Profile login admits one exact runtime profile before changing the default pointer. It resolves a label or ID, tries a persisted receipt when no secret channel was selected, otherwise accepts a bounded strict-JSON passphrase or a no-echo prompt. The secret becomes a bytearray and is overwritten after login; the client is always closed. Before pointer selection, the handler confirms the connected runtime reports the expected authenticated profile and session, then compare-and-selects against the pointer state captured at entry. Notices distinguish resumed sessions, prior-profile handover, and a session that could not be persisted. `logout` clears only this CLI context’s default selection; its docstring states that it does not revoke independent access. Per-source certificate secrets have a separate bounded, extra-forbidden payload and are likewise kept off argv; certificate register/list/check surfaces expose configured filesystem paths, while passphrases never enter their output schemas. Python immutable input strings are rebound after use, which is not physical memory erasure (custody handlers (`src/cadrumo/entrypoints/cli/config/custody.py`), custody secret command declarations (`src/cadrumo/entrypoints/cli/config/_custody_command_specs.py`), certificate source handlers (`src/cadrumo/entrypoints/cli/config/certificate.py`), profile command family composition (`src/cadrumo/entrypoints/cli/config/command_specs.py`)).

The descendant interface reads and validates governed family facts against the pinned registry, then rewrites the full declared set through a registered operation with a revision witness. Full replacement removes stale higher-index facts when a row is removed. The paged door and add/list/remove commands expose birth and event dates, relationship, disability, residence/dependence, custody, work months, childcare, income/declaration/proration, and NIF fields. Add reports an advisory when the relationship is ambiguous alongside declared mother-work months; the calculation-time check remains authoritative for already-stored rows. These are the CLI module’s stated modeling links to the Modelo 100 derived facts; formula and legal correctness are outside this pass (descendant commands (`src/cadrumo/entrypoints/cli/config/descendiente.py`)).

## Google, recipients, and external actions

Google configuration uses registered exact-profile requests for Desktop-client registration, login/refresh, status, logout, credential-source selection, Drive-folder configuration, and provider probing. Result schemas omit OAuth client secrets and refresh tokens; status exposes account email, scopes, and timestamps. Logout removes token/metadata while preserving the registered client. Credential-source payload validation rebuilds a canonical selection, requiring a target principal when impersonation fields are present; the documented service-account token is re-derived from Application Default Credentials and is absent from the payload. Folder ID and probe status describe configured location and observed reachability/writability, not proof of a successful mirror (Google handlers (`src/cadrumo/entrypoints/cli/config/google.py`), credential-source payload (`src/cadrumo/entrypoints/cli/config/_google_credential_source_payloads.py`)).

The Google correlation layer checks request class against the registered definition and projection, exact profile/session/frontend, terminal condition, refusal code, and permitted operation effect. It also correlates returned folder IDs, credential-source fields, login mode, client registration, and status completeness to the request/result. Human login consent is bounded to a finite timeout of at most 420 seconds and pins profile/session identity around each runtime exchange. It validates the registered request/review/response schema bindings, operation identity, revision, and proposal digest before requiring an interactive terminal. A noninteractive attempt tries to reject that exact proposal when transport permits, then returns the terminal refusal; apply/reject responses are tied to the available interaction revision and session actor. This is strong transport correlation, while OAuth/provider behavior remains delegated (Google contract map (`src/cadrumo/entrypoints/cli/config/google_configuration_contract_map.py`), receipt checks (`src/cadrumo/entrypoints/cli/config/google_configuration_receipt_correlation.py`), consent admission (`src/cadrumo/entrypoints/cli/config/google_consent_admission.py`), consent review (`src/cadrumo/entrypoints/cli/config/google_consent_review.py`), response checks (`src/cadrumo/entrypoints/cli/config/google_consent_response.py`), exchange boundary (`src/cadrumo/entrypoints/cli/config/google_consent_exchange.py`), observation and result checks (`src/cadrumo/entrypoints/cli/config/google_consent_observation.py`)).

One bounded receipt-contract question remains: `correlate_probe` verifies that the result echoes the request’s `read_only` flag and identifies Google Drive, but `google_success_effects` permits `NONE`, `UPDATED`, or `UNKNOWN` for every probe request. Thus this local admission code would accept an `UPDATED` receipt even when `read_only=True`. The effect guarantee of the underlying probe operation/provider path is not in this slice, so this is a confirmed permissive correlation rule, not enough evidence by itself to claim a reachable remote-write defect (Google receipt correlation (`src/cadrumo/entrypoints/cli/config/google_configuration_receipt_correlation.py`), probe request correlation (`src/cadrumo/entrypoints/cli/config/google_configuration_session_correlation.py`)).

The Drive archive-push handler reports totals and per-namespace counts and uses HMAC-derived object identifiers in error output. A cleanup-delete failure receives a warning because it can leave a durable remote ciphertext object without a manifest that enumerates it. It is distinct from local portable archive export/import, and no claim is made here that one format can restore the other. Review-package collaboration commands persist public recipients through the profile worker and validate the fingerprint against the public-key bytes; no private key is present in these CLI result schemas. The actual key-quality/trust policy and remote storage semantics remain delegated (archive mirror handler (`src/cadrumo/entrypoints/cli/config/google.py`), recipient commands (`src/cadrumo/entrypoints/cli/config/collab.py`), recipient fingerprint schema (`src/cadrumo/entrypoints/cli/config/collab_payloads.py`)).

## Evidence and limits

The main strengths are explicit destructive preflights, pointer-lock and revision checks, truthful “committed but unreadable” outcomes, redaction of internal profile identifiers on repair surfaces, typed per-source secrets, and close correlation of Google runtime receipts to the submitted request. The principal limits are delegated lifecycle, provider, parser, and cryptographic implementations; profile and tax facts are not independently checked for legal correctness; and the local Google probe-effect mismatch needs its operation contract to determine practical reachability. `ConfigBoundaryError` provides a typed fallback for unexpected errors, and the config schema/policy aggregators make the declared command family auditable, but policy metadata alone does not prove implementation behavior (config error boundary (`src/cadrumo/entrypoints/cli/config/errors.py`), config command graph (`src/cadrumo/entrypoints/cli/config/command_specs.py`), shared config schema helper (`src/cadrumo/entrypoints/cli/config/_command_spec_schema.py`), capability result schemas (`src/cadrumo/entrypoints/cli/config/capabilities_payloads.py`), connectivity renderer (`src/cadrumo/entrypoints/cli/config/connectivity_rendering.py`), profile inventory declarations (`src/cadrumo/entrypoints/cli/config/_profile_inventory_specs.py`), profile lookup helpers (`src/cadrumo/entrypoints/cli/config/_profile_support.py`)).

## Coverage appendix

All 42 assigned files are linked below.

- `src/cadrumo/entrypoints/cli/config/_profile_delete.py`
- `src/cadrumo/entrypoints/cli/config/_profile_inspect.py`
- `src/cadrumo/entrypoints/cli/config/_profile_inventory_specs.py`
- `src/cadrumo/entrypoints/cli/config/_profile_readiness.py`
- `src/cadrumo/entrypoints/cli/config/_profile_repeatable_row.py`
- `src/cadrumo/entrypoints/cli/config/_profile_support.py`
- `src/cadrumo/entrypoints/cli/config/_provision_command_specs.py`
- `src/cadrumo/entrypoints/cli/config/_repair_cli.py`
- `src/cadrumo/entrypoints/cli/config/_repair_command_specs.py`
- `src/cadrumo/entrypoints/cli/config/_repair_profile.py`
- `src/cadrumo/entrypoints/cli/config/_reset_command_specs.py`
- `src/cadrumo/entrypoints/cli/config/_runtime_profile_mutation.py`
- `src/cadrumo/entrypoints/cli/config/_spec_policies.py`
- `src/cadrumo/entrypoints/cli/config/_storage_command_specs.py`
- `src/cadrumo/entrypoints/cli/config/archive_reconcile.py`
- `src/cadrumo/entrypoints/cli/config/capabilities_payloads.py`
- `src/cadrumo/entrypoints/cli/config/certificate.py`
- `src/cadrumo/entrypoints/cli/config/check_cli.py`
- `src/cadrumo/entrypoints/cli/config/check_payloads.py`
- `src/cadrumo/entrypoints/cli/config/collab.py`
- `src/cadrumo/entrypoints/cli/config/collab_payloads.py`
- `src/cadrumo/entrypoints/cli/config/command_specs.py`
- `src/cadrumo/entrypoints/cli/config/connectivity_rendering.py`
- `src/cadrumo/entrypoints/cli/config/custody.py`
- `src/cadrumo/entrypoints/cli/config/descendiente.py`
- `src/cadrumo/entrypoints/cli/config/errors.py`
- `src/cadrumo/entrypoints/cli/config/google.py`
- `src/cadrumo/entrypoints/cli/config/google_configuration_contract_map.py`
- `src/cadrumo/entrypoints/cli/config/google_configuration_folder_correlation.py`
- `src/cadrumo/entrypoints/cli/config/google_configuration_projection.py`
- `src/cadrumo/entrypoints/cli/config/google_configuration_receipt_correlation.py`
- `src/cadrumo/entrypoints/cli/config/google_configuration_refusals.py`
- `src/cadrumo/entrypoints/cli/config/google_configuration_request_correlation.py`
- `src/cadrumo/entrypoints/cli/config/google_configuration_session_correlation.py`
- `src/cadrumo/entrypoints/cli/config/google_configuration_source_correlation.py`
- `src/cadrumo/entrypoints/cli/config/google_configuration_status_correlation.py`
- `src/cadrumo/entrypoints/cli/config/google_consent_admission.py`
- `src/cadrumo/entrypoints/cli/config/google_consent_exchange.py`
- `src/cadrumo/entrypoints/cli/config/google_consent_observation.py`
- `src/cadrumo/entrypoints/cli/config/google_consent_response.py`
- `src/cadrumo/entrypoints/cli/config/google_consent_review.py`
- `src/cadrumo/entrypoints/cli/config/google_errors.py`
<!-- /preserved:article -->
