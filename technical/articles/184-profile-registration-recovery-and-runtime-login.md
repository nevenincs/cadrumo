# Profile registration, recovery and runtime login

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-184` · **Topic:** [Installed runtime, terminal workbench, and agent harness](../topics/runtime-tui-and-agent-harness.md)

<!-- preserved:article -->
## Scope

This chunk contains the first-run credential registration/recovery screens and the existing-profile runtime login screen. The two files total 1,649 lines, 74,676 bytes, and 14,864 `o200k_base` proxy tokens. All three planned pages and every declared line range were read. The 935-line registration module and the 714-line login module were reread as smaller contiguous slices after combined output clipped. This is static inspection only; no app, module, or tests were run.

## Product capabilities and flow

`RegistrationScreen` is the offline first-run entrypoint: it collects an editable profile label, password, confirmation, and profile output language. It supplies live password assessment but leaves canonical acceptability to the injected application door; local validation only handles blank labels, rejected assessments, and mismatched confirmation. The production adapter calls `register_profile_with_credentials` with the selected output-language fact and contexts from the bundled indexed authority operation. A translated application refusal is carried as structured key/context and rendered at the UI boundary (registration form and submission (`src/cadrumo/entrypoints/tui/secret/registration.py`), production registration adapter (`src/cadrumo/entrypoints/tui/secret/registration.py`), credential worker base (`src/cadrumo/entrypoints/tui/secret/credentials.py`)).

The page can change language before a profile exists. Each supported language is named in its own language, and changing the selection rewrites existing labels in place while preserving typed fields. The selected language is kept on this screen rather than placed in an ambient context-local setting, because Textual lifecycle hooks may execute under different asyncio contexts (language choices and activation (`src/cadrumo/entrypoints/tui/secret/registration.py`), localized in-place rendering (`src/cadrumo/entrypoints/tui/secret/registration.py`)).

After successful creation, if a recovery door was supplied, the screen presents a separate optional recovery offer with skip as the default. Enrolling runs on a worker: the worker asks the UI to show a one-time recovery code, blocks on an event while the operator records and re-enters it, and returns the exact proof only on a match. Case and separators are normalized for comparison; a mismatch clears the entered value, while cancel, screen removal, or app shutdown resolves the handoff as a decline. The recovery adapter treats decline as “nothing installed,” and only maps expected, translated application errors into display data (recovery offer and code handoff (`src/cadrumo/entrypoints/tui/secret/registration.py`), verification and decline (`src/cadrumo/entrypoints/tui/secret/registration.py`), application adapters (`src/cadrumo/entrypoints/tui/secret/registration.py`)).

`RuntimeLoginScreen` admits an existing profile through a supplied profile inventory and runtime-client opener. It offers password, API key, API reference when its opener is available, and receipt-based login. It also exposes runtime status, optional automation-request entry, and a separate explicit recovery action for selected grant IDs. Profile UUIDs in the inventory must be canonical and distinct (login methods and admission inputs (`src/cadrumo/entrypoints/tui/secret/runtime_login.py`), screen setup (`src/cadrumo/entrypoints/tui/secret/runtime_login.py`)).

Each login attempt pins the selected profile/method and opens a client to completion even if the screen is cancelled mid-open. The client is checked for the requested profile and TUI frontend. Password/API-key proof is exchanged on a worker; API-reference and receipt paths request status or resume a receipt. Before handoff, the status must admit a current session for the exact profile and client session, and API-based access must satisfy the automation-grant requirement. A synchronous acceptor must confirm receipt of the live client before the screen transfers ownership; otherwise the screen closes it. Cancellation and failed close retain cleanup ownership (client-open lifecycle (`src/cadrumo/entrypoints/tui/secret/runtime_login.py`), authentication, admission and transfer (`src/cadrumo/entrypoints/tui/secret/runtime_login.py`), close ownership (`src/cadrumo/entrypoints/tui/secret/runtime_login.py`)).

Recovery is separate from login. It opens a fresh client, sends a mutable password buffer and an explicit set of grant IDs, checks the returned profile/grants, then closes the client. Once a dispatch may have happened, any unconfirmed outcome fences another recovery attempt for that profile instead of inviting a blind replay. The input password and grant list are cleared before work starts, and the mutable proof is zeroed on completion/unmount (recovery attempt and uncertainty fence (`src/cadrumo/entrypoints/tui/secret/runtime_login.py`), recovery form parsing (`src/cadrumo/entrypoints/tui/secret/runtime_login.py`)).

## Knowledge, data and trust boundaries

The registration surface uses the shared password-assessment service and delegates profile creation, key provisioning, unlock, and recovery custody to the application layer. The only profile fact it constructs itself is the chosen output language. Runtime login consumes nonsecret `ProfileLoginChoice` rows and runtime status/receipt data, then hands off a client only after local binding checks. Neither screen independently authorizes storage or grant scope. No model/LLM or legal-reference content appears in the assigned files; use of the bundled authority operation here is for the registration operation context, not evidence that this UI validates current law.

## Security and implementation assessment

The code has clear controls for one-at-a-time attempts, masked credential widgets, exact profile/frontend/session checks, unique canonical profile identities, one-time recovery display, explicit recovery proof, and transfer only after a receiver accepts the client. Runtime login clears proof buffers before callbacks and closes every client that was not transferred. Recovery likewise fences an uncertain post-dispatch effect. The worker lifecycle handles cancellation as a request to settle owned native work, not as proof that the underlying thread stopped.

Secret cleanup is best-effort. Registration retains a mutable passphrase copy until the optional recovery offer is resolved and wipes that buffer on skip, completion, or unmount. It also decodes the copy into an immutable Python string for the recovery callback, and the original masked password field is not explicitly cleared when registration succeeds; its lifetime therefore depends partly on Textual screen disposal. Login/passphrase proof is converted to mutable bytes and wiped, but runtime-created immutable string or native-library copies cannot be shown erased from these modules.

One bounded UX question remains in recovery enrollment: on an expected enrollment refusal or worker failure, the code updates the registration screen’s status and immediately calls `_finish_registration`, which dismisses that screen and returns only the profile-registration outcome. The message may be briefly visible, but this chunk does not preserve recovery status in the returned outcome; confirm whether the host provides another durable indication before treating this as a user-visible defect (recovery-worker settlement (`src/cadrumo/entrypoints/tui/secret/registration.py`), final handoff (`src/cadrumo/entrypoints/tui/secret/registration.py`)).

Static inspection cannot establish the cryptographic strength or one-time semantics of the recovery code, runtime receipt validity, encrypted-store behavior, or Textual’s actual widget/worker teardown. Synthesis should trace the injected registration/recovery adapters, runtime login client, handoff acceptor, status admission policy, and configured error/logging redaction. No tests were included in this chunk, so those runtime boundaries remain unverified here.

## Complete assigned-file coverage

All 2 manifest files and complete declared ranges were read: `registration.py` lines 1–935 and `runtime_login.py` lines 1–714. Source coverage totals 1,649 lines and 14,864 measured proxy tokens. The three helper pages were complete after smaller rereads of clipped output; no source remains unread.

- secret/registration.py (`src/cadrumo/entrypoints/tui/secret/registration.py`) — 935 lines
- secret/runtime_login.py (`src/cadrumo/entrypoints/tui/secret/runtime_login.py`) — 714 lines
<!-- /preserved:article -->
