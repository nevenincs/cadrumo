# Secure CLI input, profile bridges, and storage controls

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-169` · **Topic:** [Operator interfaces, part 2: secure transport and operation bridges](../topics/operator-interfaces-part-2.md)

<!-- preserved:article -->
## Scope

This chunk covers 20 CLI modules and all 4,533 assigned lines (37,732 measured proxy tokens). I read the complete helper plan in seven bounded pages, including the full secure-input module and both slices of the shared config payload module. Inspection was static: no application imports, CLI execution, worker calls, filesystem mutation, or external provider access. The token count is a measured proxy, not an authoritative native-model context limit.

## Capabilities and main flows

The secret-input layer is shared by profile custody, scripted creation, and other protected commands. It admits either stdin or a caller-owned descriptor, refuses a two-channel conflict before reading either, caps input at 8,192 bytes, rejects duplicate JSON keys, enforces command-specific strict Pydantic payloads with no extra fields, and closes descriptors on both success and refusal. It wipes the mutable raw-byte buffers after parse. Terminal prompting fails closed unless a real console is available; `getpass` echo-fallback warnings become refusals, and minted secrets are written to the controlling terminal instead of ordinary captured output. The module documents that fd inheritance differs on Windows and that decoded immutable strings and pre-dispatch transport are outside its buffer-clearing guarantee (secure input (`src/cadrumo/entrypoints/cli/config/secure_input.py`)).

Scripted profile creation gives noninteractive callers a real create path: it validates the label and profile facts before asking for credentials, accepts a strict passphrase/confirmation object or a no-echo prompt, and refuses if neither safe route exists. Creation can start incomplete, with supplied facts carried into the registration transaction. Machine callers are never prompted to enroll recovery; an attached console may opt in after creation, with “no” as the default. The emitted result warns that the next process must log in and degrades to a generic guidance warning if notice rendering fails after commit. The passphrase is held as a Python string during registration and the code deletes an alias afterward; this does not demonstrate overwriting immutable string memory (scripted registration (`src/cadrumo/entrypoints/cli/config/scripted_registration.py`)).

Profile reads and writes are assembled from authenticated worker projections. The view path reads facts, chooses output language by explicit option/settings/profile/default precedence, then requests issues and overview against the same revision and content digest; it checks that profile/setup/schema/readiness identity agrees before rendering. Validation reports canonical readiness issues. Wizard patch persistence rereads a mutation baseline, validates the proposed patch against that baseline and pinned authority, submits revision plus content-digest preconditions, and returns only a complete settled fact page. The descendant flow seeds the interactive form from one runtime-authorized revision and keeps that original revision through human input; the write goes through the same baseline-checked mutation seam and verifies the resulting count. A post-commit readback failure is surfaced with operation ID and committed state rather than disguised as a failed write (profile view projection (`src/cadrumo/entrypoints/cli/config/runtime_profile_view.py`), wizard patch (`src/cadrumo/entrypoints/cli/config/runtime_profile_patch.py`), descendant flow (`src/cadrumo/entrypoints/cli/config/runtime_descendant_door.py`), descendant persistence (`src/cadrumo/entrypoints/cli/config/runtime_descendants.py`)).

Certificate commands register, list, select, check, and remove named sources through the exact profile worker. Caller-relative certificate paths are resolved before crossing into a worker with a different current directory. The bridge checks typed projection, exact profile, terminal success, expected mutation effect, and selected result facts. A passphrase is passed as a mutable one-shot secret and cleared in `finally`; removal reports whether a secret was present, never its value (certificate bridge (`src/cadrumo/entrypoints/cli/config/runtime_certificate.py`)). Google client registration similarly reads at most 65,536 bytes, hashes and submits path/digest publicly while sending JSON bytes as a protected secret, and wipes its mutable buffer on every path. Human Google login goes through a dedicated consent flow that pins profile/session, checks the registered contract, waits for the exact terminal review, and returns a correlated result; other typed configuration requests use the registered-operation bridge (Google configuration (`src/cadrumo/entrypoints/cli/config/runtime_google_configuration.py`), Google consent (`src/cadrumo/entrypoints/cli/config/runtime_google_consent.py`), Google registration (`src/cadrumo/entrypoints/cli/config/runtime_google_registration.py`)).

Censal review validates the registered operation/schema contract and profile baseline before submission, enforces a payload-size limit, starts only after the runtime confirms no ephemeral secret is required, and exchanges requests on the same exact session. It reads and validates the canonical review projection, compares the reviewed field intents with the request, obtains operation/interaction/revision-specific response authority, and correlates the accepted apply/reject response. After response it observes to settlement under a deadline, keeps the most recent admitted receipt facts if a later operation fails, and checks the result document against the exact contract, outcome, and reviewed-proposal digest. The CLI response path therefore controls explicit human apply/reject; the actual census/provider operation remains worker-owned (censal review (`src/cadrumo/entrypoints/cli/config/runtime_censal_review.py`), review projection (`src/cadrumo/entrypoints/cli/config/runtime_censal_projection.py`), response authority (`src/cadrumo/entrypoints/cli/config/runtime_censal_response.py`)).

Storage commands list and view declared areas, inspect tree health without repairing, materialize the declared tree while preserving existing content, and request reclaim of an area. Relocation is intentionally manual through `CADRUMO_LOCAL_STORAGE_ROOT`; the CLI exposes resolved paths and footprints but has no move verb. Check results distinguish hosts where root mode could not be enforced from hosts where it was checked. Reclaim delegates lifecycle/confirmation refusals to the storage service and reports retained entries instead of counting them as removed. These handlers do not themselves define the storage taxonomy or deletion safeguards; the service and taxonomy do (storage handlers (`src/cadrumo/entrypoints/cli/config/storage_cli.py`), storage result schemas (`src/cadrumo/entrypoints/cli/config/storage_payloads.py`)).

## Data contracts, security, and quality

The shared `config_payloads.py` module defines strict envelope result schemas for login, passphrase change/reset, archive operations, status, reset journals, auth/apoderado, repairs, certificates, and diagnostics. Several result validators reconcile reset target counts, pause IDs, effect timestamps, and completion state, while comments and shapes deliberately exclude key material, passphrases, recovery codes, and provider tokens. It keeps wizard schemas owned by their actual producer to avoid pulling the wizard import graph into every config command (shared config payload contracts (`src/cadrumo/entrypoints/cli/config_payloads.py`)). Status text rendering is pure and serializes the exact resolved precondition-action DTO rather than inventing recovery prose. Recovery-status and workstation-check readers similarly require exact profile/result and no-mutation receipt checks (status rendering (`src/cadrumo/entrypoints/cli/config/status_rendering.py`), recovery status (`src/cadrumo/entrypoints/cli/config/runtime_recovery_status.py`), workstation check (`src/cadrumo/entrypoints/cli/config/runtime_workstation_check.py`)).

The storage and shared payload surfaces are notably explicit about degraded cases: missing versus unreadable profile state, absent versus unverified permission checks, partial reclamation, and reset-operation completion reconciliation remain distinct. `counterparty_correlation.py` also checks action-specific result shapes, exact profile/action/identifier and country/scope identity, expected mutation effect, and that recorded facts correspond to the request. These checks reduce the chance that a malformed or stale worker result is rendered as an ordinary success (counterparty receipt correlation (`src/cadrumo/entrypoints/cli/counterparty_correlation.py`)).

Limits remain at the boundary of these modules. The worker owns certificate parsing, private key custody, Google OAuth/provider behavior, actual storage traversal/deletion, profile mutations, and census exchange. The secret layer wipes bytearrays, not immutable Python strings retained by Pydantic or downstream calls; this is a memory-erasure limitation rather than evidence of secret leakage. `AuthStatusPayload` includes a certificate path for an operator-facing status projection, so synthesis should assess whether that path is intended to be public in machine output. No tests were present in the supplied snapshot; none were run. Nothing here verifies tax-law correctness, certificate validation policy, provider correctness, or runtime filesystem/network behavior.

## Dependencies and follow-up

Synthesis should connect these CLI guards to the application registration and custody services, shared profile mutation executor, registered auth/certificate/Google operation contracts, censal operation definitions, and storage-management service. In particular, inspect the producer contracts for all worker receipts, the consumer policy for certificate paths in `AuthStatusPayload`, and the lifecycle guard behind storage reclaim before making end-to-end safety claims. No legal or external provider validation was performed.

## Coverage appendix

All 20 assigned source files were read in full.

- `src/cadrumo/entrypoints/cli/config/runtime_censal_projection.py`
- `src/cadrumo/entrypoints/cli/config/runtime_censal_response.py`
- `src/cadrumo/entrypoints/cli/config/runtime_censal_review.py`
- `src/cadrumo/entrypoints/cli/config/runtime_certificate.py`
- `src/cadrumo/entrypoints/cli/config/runtime_descendant_door.py`
- `src/cadrumo/entrypoints/cli/config/runtime_descendants.py`
- `src/cadrumo/entrypoints/cli/config/runtime_google_configuration.py`
- `src/cadrumo/entrypoints/cli/config/runtime_google_consent.py`
- `src/cadrumo/entrypoints/cli/config/runtime_google_registration.py`
- `src/cadrumo/entrypoints/cli/config/runtime_profile_patch.py`
- `src/cadrumo/entrypoints/cli/config/runtime_profile_view.py`
- `src/cadrumo/entrypoints/cli/config/runtime_recovery_status.py`
- `src/cadrumo/entrypoints/cli/config/runtime_workstation_check.py`
- `src/cadrumo/entrypoints/cli/config/scripted_registration.py`
- `src/cadrumo/entrypoints/cli/config/secure_input.py`
- `src/cadrumo/entrypoints/cli/config/status_rendering.py`
- `src/cadrumo/entrypoints/cli/config/storage_cli.py`
- `src/cadrumo/entrypoints/cli/config/storage_payloads.py`
- `src/cadrumo/entrypoints/cli/config_payloads.py`
- `src/cadrumo/entrypoints/cli/counterparty_correlation.py`
<!-- /preserved:article -->
