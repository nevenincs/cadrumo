# Profile custody, provisioning, and runtime configuration

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-168` · **Topic:** [Operator interfaces, part 1: command graph and principal workflows](../topics/operator-interfaces-part-1.md)

<!-- preserved:article -->
## Scope

This chunk covers 28 CLI modules and all 5,895 assigned lines (47,117 measured proxy tokens). I read the full source, using nine bounded helper pages and smaller exact line slices to recover one tool-truncated range in `profile_command_specs.py`. This is static inspection only: I did not import or run the application, connect to a runtime/provider, or verify delegated storage, browser, model, or worker effects. The measured-token count is a proxy, not an authoritative native-model limit.

## Operator capabilities and flows

The command declarations expose profile passphrase rotation and reset, recovery enrollment, capsule restoration, profile list/status, profile setup/edit and archive/census operations, local model-runtime provisioning, access/session controls, authentication-provider actions, and censal review. The profile command graph assigns read, encrypted-write, bootstrap, and destructive policies, plus explicit secret channels and result schemas. It is an import-light declaration surface: some registry-backed wizard choice constants are deliberately empty there, with comments pointing to an operation-scoped choice builder. That declaration alone does not show a user-reachable missing-choice defect; the create/edit handler and the builder admission path need to be considered together (profile command declarations (`src/cadrumo/entrypoints/cli/config/profile_command_specs.py`)).

Profile listing combines one summary-inventory observation and one active-pointer read, then sorts and renders the in-memory join. It does not authenticate or reopen storage while formatting rows; an unrecognized inventory produces an advisory instead of silently claiming that profiles are absent. Status keeps empty and dangling-pointer diagnostics public, but requires a profile-bound client for a live registered profile. It accepts exactly one status projection, correlates the profile ID and allowed fact paths, and renders the supplied health/baseline outcome rather than reevaluating readiness in the CLI (profile list (`src/cadrumo/entrypoints/cli/config/profile_list_cli.py`), status (`src/cadrumo/entrypoints/cli/config/profile_status_cli.py`)).

The template workforce command accepts decimal values rather than binary floats, checks its declared bounds, and mutates through revision/content-digest compare-and-swap with a readback. Its local computation is not an independent validation of tax law. Passphrase rotation reads bounded `SecretStr` input only from an explicit machine channel or no-echo prompt, binds the target profile before use, converts values into mutable bytearrays, and wipes those buffers after the operation. Reset targets an explicitly resolved login profile and rewraps the same data key; the CLI reports recovery retention and does not itself revoke existing holders. The Pydantic secret object is not explicitly wiped, so the buffer-clearing claim applies only to the bytearrays visible here (template workforce (`src/cadrumo/entrypoints/cli/config/plantilla_media.py`), passphrase operations (`src/cadrumo/entrypoints/cli/config/passphrase.py`)).

Recovery is optional and off by default. Enable requires the active profile’s current passphrase. A minted recovery code is shown once at the controlling terminal and must be typed back, or sent through a bounded descriptor pair and returned on a second descriptor. The code never enters the ordinary result envelope, stdout, arguments, environment, or logs; the implementation validates descriptor pairing/collisions, limits and wipes transfer buffers, and closes descriptors on success or refusal. The recovery code is installed only after its possession proof. Disable also requires the passphrase. Archive restore accepts either a capsule directory or sealed archive, reads the public source before requesting the passphrase, then delegates to one restore authority. It reports that recovery is not carried into the restored profile. Reset start and resume require `--yes`; a retention override also requires a nonblank reason. Status observes a journal without resuming it, while resume targets one exact incomplete operation (recovery (`src/cadrumo/entrypoints/cli/config/recovery.py`), restore (`src/cadrumo/entrypoints/cli/config/restore_cli.py`), reset transport (`src/cadrumo/entrypoints/cli/config/reset_cli.py`)).

Local inference lifecycle actions are explicit commands, not implicit side effects of a read. `status` reads runtime/model readiness without loading models; `probe` checks text-model fitness now; report measures hardware, role selections, runtime residents, and load contention. Install and setup require explicit consent before installation; pull checks model selection and admission before fetching bytes; load/verify/remove are separate operations. The CLI delegates process control, model selection, resource admission, and fitness to application/adapter services and projects typed outcomes into JSON/text envelopes. It starts only the configured local runtime according to its declared boundary; this slice does not verify installer provenance, process ownership, model contents, or runtime behavior (provisioning CLI (`src/cadrumo/entrypoints/cli/config/provision_cli.py`), provisioning schemas (`src/cadrumo/entrypoints/cli/config/provision_payloads.py`)).

The runtime access surface reports allowlisted sessions, lists and inspects public automation inventory, approves or declines one exact current review, revokes a key/grant/profile automation, locks selected/current/all sessions, and resumes with explicitly selected grants. Approval checks request ID and review digest before reading fresh password proof. Password buffers are cleared in `finally`; public result schemas carry receipts and credential references, not credential material. A separate requester flow reads a strict proposal from the secret channel, runs an enrollment journey, and exposes only the terminal receipt and public credential reference. Own-grant changes correlate the requested kind, stage the payload before native root admission, and reconcile through a fresh exact-profile credential connection (access handlers (`src/cadrumo/entrypoints/cli/config/runtime_access_management.py`), access command contracts (`src/cadrumo/entrypoints/cli/config/runtime_access_management_specs.py`), access payloads (`src/cadrumo/entrypoints/cli/config/runtime_access_management_payloads.py`), automation request flow (`src/cadrumo/entrypoints/cli/config/runtime_automation_request.py`)).

Authentication bridges pin operations to the invocation’s exact profile worker. Configure, login, read, logout/reset, and diagnostic-report handlers correlate profile/provider/operation identity, terminal status, and mutation effect before returning public results. Apoderado configuration sends the represented NIF as a one-use protected secret and verifies the returned profile, NIF, notes, operation ID, and effect; status and clear similarly require matching operation receipts. Failures are translated into typed CLI refusals. These are strong local correlation checks, while actual provider/browser work and secret handling inside the worker are delegated (apoderado bridge (`src/cadrumo/entrypoints/cli/config/runtime_auth_apoderado.py`), auth configure (`src/cadrumo/entrypoints/cli/config/runtime_auth_configure.py`), auth login (`src/cadrumo/entrypoints/cli/config/runtime_auth_login.py`), auth reads (`src/cadrumo/entrypoints/cli/config/runtime_auth_read.py`), auth teardown (`src/cadrumo/entrypoints/cli/config/runtime_auth_teardown.py`), diagnostic reporting (`src/cadrumo/entrypoints/cli/config/runtime_auth_diagnostic_report.py`)).

Censal preparation, preview, file-fact import, and interactive review are separate worker-owned operations. Preparation checks exact profile identity and a no-effect receipt; preview reads the prepared baseline and reconciles live census/auth state; file import accepts only string-valued facts without validity ranges and checks the exact applied paths. Review transport pins the session around every exchange, correlates request IDs, operation definition, subject, and schema bindings, then checks the pending review reference before responding. The censal observation loop is deadline-bounded and polls one observation page. Runtime receipt state is retained separately so later submitted-operation failures do not erase the last admitted terminal facts (censal preparation (`src/cadrumo/entrypoints/cli/config/runtime_censal_prepare.py`), preview (`src/cadrumo/entrypoints/cli/config/runtime_censal_preview.py`), file import (`src/cadrumo/entrypoints/cli/config/runtime_censal_file_import.py`), exchange and observation (`src/cadrumo/entrypoints/cli/config/runtime_censal_exchange.py`), censal observation (`src/cadrumo/entrypoints/cli/config/runtime_censal_observation.py`), review state (`src/cadrumo/entrypoints/cli/config/runtime_censal_contracts.py`)).

## Evidence, risks, and follow-up

The strongest local controls are exact-profile binding, narrowly shaped operation payloads, explicit confirmation for broad reset/install actions, fresh proof for access recovery/approval, descriptor admission and cleanup, and correlation between a submitted operation and its terminal receipt. Typed payloads distinguish “not measured” from false and avoid putting recovery or automation credentials in normal output. The config root and profile listing defer heavier service imports until needed, keeping metadata/help and listing paths comparatively narrow (config root (`src/cadrumo/entrypoints/cli/config/root_cli.py`), profile-list result schemas (`src/cadrumo/entrypoints/cli/config/profile_list_payloads.py`), runtime access result schemas (`src/cadrumo/entrypoints/cli/config/runtime_access_management_payloads.py`)).

One bounded consistency question is visible in `runtime_censal_preview.py`: its function describes the operation as a read-only preview, while the CLI accepts either `NONE` or `UPDATED` as the completed effect. This is a confirmed permissive local receipt check, not proof of a reachable mutation defect; the operation contract may define an update for an internal/read-related reason, and that layer is outside this chunk. Synthesis should compare the declared effect contract and producer path before assigning product impact. Similarly, empty import-time wizard enum choices appear intentional and need assessment at the operation-scoped builder and shared validator rather than as a defect on their own.

The key dependencies for synthesis are the application custody/reset/restore services, local-reader provisioning and hardware admission, registered-operation worker contracts, auth/provider workers, and censal request/review definitions. The available on-disk snapshot omits tests, so this report makes no test-coverage or runtime-correctness claim. Bundled profile facts, model catalogue data, and legal/tax inputs are not independently validated here. No external legal verification was performed, and static inspection cannot certify filesystem, network, installer, cryptographic, or provider behavior.

## Coverage appendix

All 28 assigned source files were read in full.

- `src/cadrumo/entrypoints/cli/config/passphrase.py`
- `src/cadrumo/entrypoints/cli/config/plantilla_media.py`
- `src/cadrumo/entrypoints/cli/config/profile_command_specs.py`
- `src/cadrumo/entrypoints/cli/config/profile_list_cli.py`
- `src/cadrumo/entrypoints/cli/config/profile_list_payloads.py`
- `src/cadrumo/entrypoints/cli/config/profile_status_cli.py`
- `src/cadrumo/entrypoints/cli/config/provision_cli.py`
- `src/cadrumo/entrypoints/cli/config/provision_payloads.py`
- `src/cadrumo/entrypoints/cli/config/recovery.py`
- `src/cadrumo/entrypoints/cli/config/reset_cli.py`
- `src/cadrumo/entrypoints/cli/config/restore_cli.py`
- `src/cadrumo/entrypoints/cli/config/root_cli.py`
- `src/cadrumo/entrypoints/cli/config/runtime_access_management.py`
- `src/cadrumo/entrypoints/cli/config/runtime_access_management_payloads.py`
- `src/cadrumo/entrypoints/cli/config/runtime_access_management_specs.py`
- `src/cadrumo/entrypoints/cli/config/runtime_auth_apoderado.py`
- `src/cadrumo/entrypoints/cli/config/runtime_auth_configure.py`
- `src/cadrumo/entrypoints/cli/config/runtime_auth_diagnostic_report.py`
- `src/cadrumo/entrypoints/cli/config/runtime_auth_login.py`
- `src/cadrumo/entrypoints/cli/config/runtime_auth_read.py`
- `src/cadrumo/entrypoints/cli/config/runtime_auth_teardown.py`
- `src/cadrumo/entrypoints/cli/config/runtime_automation_request.py`
- `src/cadrumo/entrypoints/cli/config/runtime_censal_contracts.py`
- `src/cadrumo/entrypoints/cli/config/runtime_censal_exchange.py`
- `src/cadrumo/entrypoints/cli/config/runtime_censal_file_import.py`
- `src/cadrumo/entrypoints/cli/config/runtime_censal_observation.py`
- `src/cadrumo/entrypoints/cli/config/runtime_censal_prepare.py`
- `src/cadrumo/entrypoints/cli/config/runtime_censal_preview.py`
<!-- /preserved:article -->
