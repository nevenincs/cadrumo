---
tags:
  - '#research'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:3da5508358344a0db4aeaabb88416f19d5d3f71d407dac6f3e84dcfe46549333'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-s12-obsolete-code-purge-audit]]"
  - "[[2026-08-23-cli-machine-secret-channel-unification-adr]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---




# `cli-machine-secret-channel-unification` research: `Keychain-free explicit profile authentication`

Removing ambient environment authentication correctly closes an implicit secret route, but it exposes an older custody limitation: when the OS keychain cannot persist the random session key, `config login` authenticates only its own process and every later profile-bound process refuses before reaching its verb. The smallest evidence-backed repair is explicit per-invocation profile authentication at the root gate through a distinct paired stdin/fd payload, used only when session resume fails and never persisted or emitted. It repeats Argon2 work on degraded hosts but reuses the existing login proof and in-process session, adds no durable bearer capability or nested command runner, and preserves fail-closed keychain semantics. This necessarily expands the scalar-secret inventory and therefore requires an ADR amendment and new plan steps before production work resumes.

## Findings

### The HIGH finding is a real closed loop, not merely stale test intent

The application deliberately returns `session_persisted=False` when keychain custody fails while retaining a valid in-process bucket session (`src/cadrumo/application/user_profile/_login_session.py:1515`). The next process cannot reconstruct that session: the root gate receives `KEYRING_UNAVAILABLE` and raises before the command handler (`src/cadrumo/entrypoints/cli/__init__.py:578`). The existing subprocess contract explicitly expects a follow-on process to fail in this branch (`src/cadrumo/entrypoints/cli/tests/test_profile_login_session_lifecycle.py:159`). Commit `8a508fbe42` removed the only branch that had called `login_profile` from ambient settings, so a successful machine login cannot make a second command machine-operable on this host.

The keychain refusal itself must remain. The accepted custody design permits only a random session key in the OS keychain and refuses to write reconstructive key material to disk; keychain failure leaves only process memory (`.vault/adr/2026-08-13-profile-password-custody-rollup-adr.md`, “Sessions and profile handover”; `src/cadrumo/core/_profile_session.py:16`). Restoring an environment or adapter fallback would cure availability by reopening the exact implicit process-lifetime secret route the current ADR forbids.

### Explicit root-gate authentication is the smallest complete capability

The root already owns the profile-session precondition and already continues the requested command after an interactive in-place login (`src/cadrumo/entrypoints/cli/__init__.py:456`, `:578`). A machine equivalent can reuse that seam: accept one explicit root profile-auth selection, attempt ordinary session resume first, and only on a resumable authentication refusal call the same application `login_profile` door with a callback over the bounded value. The live session then serves the already parsed command in the same process. No new session format, disk artefact, output channel, application authentication algorithm, or command redispatcher is required.

The root capability should be distinct from command-local `--secrets-stdin` and `--secrets-fd`, for example `--profile-secrets-stdin` and `--profile-secrets-fd`, with strict payload `{"profile_passphrase": string}`. Combining them would force unrelated command payloads into the gate: certificate mutation needs a certificate passphrase that cannot authenticate the profile, while rotation and restore carry different proof fields (`src/cadrumo/entrypoints/cli/_config/_certificate.py:283`, `src/cadrumo/entrypoints/cli/_config/_passphrase.py:40`, `src/cadrumo/entrypoints/cli/_config/_restore_cli.py:61`). Distinct names also allow conflict selection before either source is read and avoid overloading one JSON object with two credential domains.

Both transports are applicable. Exact source search found no production business-data stdin reader outside the canonical secret reader; file/document inputs use explicit paths. Stdin therefore supplies the portable route and fd the composable route, with the same 8 KiB, strict UTF-8 JSON, duplicate-field, descriptor, closure, and no-leak rules already implemented in `src/cadrumo/entrypoints/cli/_config/_secure_input.py:57`. The root must consume the payload only for a selected profile-bound invocation: help, metadata, bootstrap-exempt commands, a valid resumed session, and commands without an active target must neither read nor prompt. A supplied but inapplicable payload should refuse rather than be ignored.

### Global replacement of every leaf secret flag would create coupling rather than uniformity

Moving the existing `--secrets-*` pair entirely to the root looks globally uniform but makes the root parse every command-local payload before command dispatch. Certificate mutation would require both profile and PKCS#12 secrets; profile creation has no prior profile to authenticate; restore has conditional password and recovery forms. The root would import or duplicate local models and metadata variants, reversing the closed command-owned payload design in the accepted ADR. It is broader than the defect and increases cycles and schema surface.

A separate root authentication pair is still globally uniform within its own capability: it has identical declarations and payload on every profile-bound invocation, while the existing pair remains uniform across the five domain-secret verbs. The ADR must explicitly distinguish “profile precondition proof” from “verb-owned scalar secret”; otherwise this is an illicit sixth adopter under the current closed inventory (`.vault/adr/2026-08-23-cli-machine-secret-channel-unification-adr.md`, “Constraints”).

### Login-and-exec solves the process boundary with more grammar and envelope ambiguity

A composite such as `config login --exec ...` or `config exec` can authenticate then dispatch one command in the same process. It avoids root flags but adds a second command parser, nesting or suppressing one of two action envelopes, policy re-evaluation, help/metadata projection for an arbitrary tail, and a new authority for command execution. It also requires the same passphrase on every degraded-host invocation, so it offers no operational advantage over root-gate authentication. The current root already owns continuing an authenticated gated invocation, making the composite runner duplicative (`src/cadrumo/entrypoints/cli/__init__.py:578`).

### A transferable session capability is secure in principle but is not the smallest repair

Replacing the unavailable keychain with caller custody would require login to mint a bearer key, write it only to a caller-supplied descriptor, persist a DEK wrap bound to deadlines and profile identity, and let later roots read the bearer from stdin/fd. This can preserve split knowledge, but adds a durable receipt variant, secret-output protocol, revocation and expiry rules, caller lifecycle obligations, Windows descriptor-transfer constraints, metadata, and recovery tests. Emitting the bearer on stdout or argv is prohibited; accepting a file path would merely move secret-at-rest custody to an ungoverned file.

This option earns its complexity only if avoiding repeated Argon2 authentication on keychain-free hosts becomes a separate requirement. The current defect requires operability, not login-once without a secure persistence anchor. The existing design already documents process-scoped degradation rather than a weaker persistence fallback (`src/cadrumo/application/user_profile/_login_session.py:1521`).

### The accepted decision and approved plan cannot absorb this as an implementation detail

The accepted ADR says the inventory is exactly five commands and that commands outside it may not use the scalar-secret reader; it also places explicit resolution inside command handlers. Root-gate authentication changes both facts. An amendment must settle option names, payload, applicability/refusal order, target selection, session-resume precedence, keychain-unavailable behavior, prompt prohibition at the machine root path, and the distinction from verb-local secrets. Without that change, implementing the favored option would contradict rather than execute the ADR.

The L3 plan also needs explicit work before its subprocess and closure waves:

- add a canonical root profile-auth declaration/model/metadata step, including safe schema projection and exact non-adopter gates;
- add a root-gate integration step that authenticates only after failed resume, binds the session to the selected profile, continues the original handler, and zeroises/refuses without mutation on conflict or malformed input;
- extend locale/help/generated documentation for the distinct root pair and remove the remaining ambient-channel prose;
- extend the real subprocess matrix with forced keychain-unavailable stdin and inherited-fd success on representative read and write profile-bound commands, valid-session non-consumption, wrong-profile and no-profile refusal, conflict before read, hostile-environment non-interference, fd closure, and secret-free four-locale errors;
- replace the obsolete ambient-gate integration contract and add an Argon2-per-invocation expectation so degraded operation is honest rather than advertised as persisted login-once.

The research did not benchmark repeated Argon2 cost or design a transferable-ticket wire format; neither is needed to decide the minimum operability repair.

## Sources

- `.vault/audit/2026-08-23-cli-machine-secret-channel-unification-s12-obsolete-code-purge-audit.md`
- `.vault/adr/2026-08-23-cli-machine-secret-channel-unification-adr.md`
- `.vault/adr/2026-08-13-profile-password-custody-rollup-adr.md`
- `.vault/adr/2026-07-24-profile-login-session-adr.md`
- `.vault/research/2026-07-24-profile-login-session-research.md`
- `src/cadrumo/entrypoints/cli/__init__.py:456`
- `src/cadrumo/entrypoints/cli/__init__.py:578`
- `src/cadrumo/entrypoints/cli/_config/_secure_input.py:57`
- `src/cadrumo/entrypoints/cli/_config/_certificate.py:283`
- `src/cadrumo/entrypoints/cli/_config/_passphrase.py:40`
- `src/cadrumo/entrypoints/cli/_config/_restore_cli.py:61`
- `src/cadrumo/application/user_profile/_login_session.py:1515`
- `src/cadrumo/core/_profile_session.py:16`
- `src/cadrumo/entrypoints/cli/tests/test_profile_login_session_lifecycle.py:159`
- commit `8a508fbe42`
