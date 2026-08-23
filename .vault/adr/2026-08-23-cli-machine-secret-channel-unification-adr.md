---
tags:
  - '#adr'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:13aeaa845d648cff554420b7282181ae4fc5e518fbedce810ec308c202ff84d8'
related:
  - '[[2026-08-23-cli-machine-secret-channel-unification-global-machine-secret-contract-research]]'
  - '[[2026-08-13-profile-password-custody-rollup-adr]]'
  - '[[2026-08-13-cli-action-envelope-successor-adr]]'
  - '[[2026-08-23-cli-machine-secret-channel-unification-keychain-free-cross-process-machine-operation-research]]'
---
# `cli-machine-secret-channel-unification` adr: `Uniform explicit machine-secret channels for every scalar-secret CLI verb` | (**status:** `accepted`)

## Problem Statement

The CLI has one secure machine-secret parser but no global contract governing
which secret-bearing verbs expose it, how their options are declared, which
fallback sources are permitted, or how automation discovers each payload. The
affected commands, conflicting decisions, and migration surface are grounded in
`2026-08-23-cli-machine-secret-channel-unification-global-machine-secret-contract-research`.
This decision establishes one global CLI authority for caller-supplied scalar
secrets without merging credential domains or document transports.

## Considerations

- Every applicable verb must serve portable stdin callers and supervisors whose
  stdin has another owner.
- Secrets may not enter argv, output, diagnostics, logs, or generated examples.
- Naming two machine channels is a refusal, not a precedence choice.
- Interactive prompting is valid only through the verified no-echo terminal path.
- Command-local payload models are domain contracts rather than duplication.
- Metadata must describe payload structure without containing values.
- Descriptor closure makes the local read one-shot but cannot make its backing
  transport ephemeral.
- Credential documents and provider-mediated authorization are not scalar-secret
  input.
- Obsolete declarations, fallbacks, fields, and helpers are deleted without aliases.

## Considered options

- **Add fd independently to two verbs — rejected.** This leaves declarations,
  fallback policy, metadata, and future adoption divergent.
- **Use stdin only — rejected.** Stdin is singular and may already carry business
  data or belong to the supervisor.
- **Use fd only — rejected.** Inherited descriptors are less portable and needlessly
  burden callers whose stdin is free.
- **Retain environment fallback — rejected.** It is implicit process-lifetime state
  and conflicts with the explicit-channel security boundary.
- **Use one universal payload — rejected.** The credential capabilities have
  different fields and invariants.
- **Adopt one transport contract with command-local models — accepted.** It
  centralizes substitutable mechanics and preserves semantic validation.

## Constraints

- The closed scalar-secret verb inventory is `config login`, `config profile
  create`, `config passphrase change`, `config profile restore`, and `config auth
  certificate secret set`.
- Each exposes exactly one `--secrets-stdin` and one `--secrets-fd` with identical
  names, types, defaults, ordering, help intent, and schema projection.
- Conflict refusal precedes source reads, prompts, KDF work, sessions, transactions,
  and mutation.
- With no explicit channel, only a verified interactive terminal may prompt;
  otherwise the CLI emits a typed localized refusal.
- CLI entrypoints never resolve caller-supplied scalar secrets from environment,
  settings, keyrings, or an implicit adapter fallback. Separately governed
  programmatic substrate configuration remains outside this CLI decision.
- Both channels accept one bounded strict UTF-8 JSON object, reject repeated keys at
  every depth and missing or unexpected fields, and retain no secret in refusal
  context.
- Descriptors 1 and 2 are refused; descriptor 0 remains a valid stdin-equivalent.
  A selected descriptor is closed on success and on every refusal after reading
  begins.
- Descriptor guarantees are process-local: the caller owns whether the backing
  object is a pipe, socket, regular file, or another readable transport.
- No secret enters argv, stdout, stderr, metadata values, localized interpolation,
  logs, or result envelopes.
- Document inputs such as `--file` and `--client-json`, capsule and recovery artifact
  files, OS-keychain gestures, and provider OAuth flows are excluded.
- No alias, deprecated spelling, dual-field acceptance, hidden environment route, or
  parser shim is permitted.

## Implementation

### Canonical options, selector, and reader

One CLI-owned abstraction declares both options for static Typer commands and dynamic
lazy wrappers. One typed selector refuses coexistence and returns stdin, descriptor,
interactive, or absent. One bounded reader consumes the selected machine source and
validates it against a supplied command model. These replace local option declarations,
fd/stdin branches, signature injection, and the standalone conflict helper.

### Command-local strict payloads

A shared strict payload base owns frozen-model and unexpected-field behavior. Local
models declare only:

- login: `passphrase`;
- profile create: `passphrase`, `passphrase_confirmation`;
- passphrase change: `current_passphrase`, `new_passphrase`,
  `new_passphrase_confirmation`;
- profile restore without `--artifact`: `passphrase`;
- profile restore with `--artifact`: `recovery_secret`;
- certificate secret set: `certificate_passphrase`.

These names are a hard cut. Retired restore `password` and certificate `secret` fields
are unexpected. Confirmation and prospective credential policy remain surface and
application responsibilities; proof paths remain non-oracular.

### Explicit CLI resolution

The precedence is one explicitly selected machine channel, otherwise the hardened
prompt on a verified terminal, otherwise refusal. Login and creation cease inheriting
or reading `CADRUMO_SECRET_PASSPHRASE`; CLI handlers always provide explicit values or
callbacks and cannot fall through to substrate configuration.

### Safe machine discovery

Registration metadata and verb-input schemas project both flags, their canonical
types/defaults, the bounded strict-object contract, required field names and non-secret
JSON types, repeated/extra-field prohibition, and conditional variants. Restore exposes
mutually exclusive variants keyed by public `--artifact` presence. Metadata contains no
values, examples, hashes, invocation-derived lengths, or persisted credential facts.

A closed verb-secret inventory makes adoption enforceable: any production command that
owns a scalar secret must inherit both transports and metadata. The distinct root
profile-authentication precondition defined below is not a sixth verb-owned secret and
has its own typed command-graph authority.

### Hard-cut deletion and decision reconciliation

Implementation deletes the manual create injection, certificate stdin-only declaration,
all local canonical-option declarations and selection branches, CLI environment
fallbacks, retired payload fields, stale help/locales/docs/sequences, and superseded
helpers moved into the selector/reader. Local payload models remain beside their
commands.

This ADR is the global scalar-secret transport authority. The fd-only sentence in
`2026-08-13-profile-password-custody-rollup-adr` is replaced by deference to this
paired-channel contract while its cryptographic and lifecycle decisions remain. The
secret-FD ownership sentence in `2026-08-13-cli-action-envelope-successor-adr` likewise
defers option, payload-metadata, and selection ownership here while retaining its command
tree and action-envelope decisions. Neither narrower ADR is superseded as a whole.

### Keychain-free root profile-authentication amendment

The root profile-session precondition exposes exactly `--profile-secrets-stdin` and
`--profile-secrets-fd`. Its strict frozen JSON object contains exactly
`profile_passphrase: SecretStr` and inherits the canonical 8 KiB, strict UTF-8 JSON,
recursive duplicate refusal, missing/extra-field refusal, fd 0 acceptance, negative and
fd 1/2 refusal, one-shot read, descriptor-close, secret-free diagnostic, and verified
prompt prohibitions. It accepts no argv value, environment variable, alias, executable
callback, ticket, persisted bearer credential, or fallback store.

This root capability is a profile precondition, not a verb-owned secret. The five
`--secrets-stdin` / `--secrets-fd` leaf contracts and their exact local models remain
closed. Root applicability is derived from typed command-graph/session-exemption
authority rather than a parallel handwritten command inventory.

Help, version, metadata, bare-group output, unknown commands, and parse or usage failures
take precedence and never read or semantically validate a profile source. After Click
has resolved an executable leaf, dispatch preflights root and leaf selections together
without reading: each scope is internally exclusive, at most one scope may select
stdin, and selected descriptor numbers must differ. Collision or inapplicability refuses
before either read, authentication, KDF, session activation, transaction entry, or leaf
mutation. Valid dual-secret combinations are profile fd plus leaf stdin, profile stdin
plus leaf fd, or two distinct descriptors. The preflight derives from parsed command
specification authority; argv scanning and duplicated grammar are forbidden.

The root source applies only when an exact profile target is resolved, the leaf requires
a profile session, no live session serves that target, and persisted-session resume has
refused. Login, create, restore, logout, and passphrase change are inapplicable. A live
or successfully resumed exact-target session makes a supplied root source unused and
therefore a refusal without consumption. Machine authentication never invokes an
interactive chooser.

Before root authentication may persist activation, every required root and leaf machine
payload is bounded-read and strict-validated. The root then calls canonical
`login_profile` for the exact target; both returned bucket and serving live session must
match it before binding and leaf dispatch. Explicitly targeted profile show, validate,
and history route through this same gate. Passphrase change is restored as the sole
rotation verb with `current_passphrase`, `new_passphrase`, and
`new_passphrase_confirmation`; it is self-authenticating and root-gate-exempt, so a
root source supplied to it refuses unread.

Without a root source, keychain unavailability retains the typed refusal. With a valid
source, canonical login may establish a process-scoped session and continue the same
parsed command. Persistence failure stages a non-secret Notice that authentication must
be supplied again next process. Repeated Argon2 work on keychain-free hosts is
intentional; no parallel authenticator, credential store, or bearer format is added.

Registration metadata exposes a value-free `profile_authentication` posture of
`not-applicable`, `resume-fallback`, or `self-authenticating`, plus public field/type,
bound, exclusivity, and cross-scope collision rules. It contains no values, examples,
hashes, runtime-derived lengths, or credential state.

Mutable raw read buffers are wiped in `finally` blocks and secret-bearing references are
released promptly. The implementation does not claim guaranteed erasure of immutable
Python strings created by decoding, JSON, Pydantic, or `SecretStr`. POSIX subprocesses
may inherit numeric descriptors. On Windows the supported descriptor route uses an
allowlisted inherited HANDLE converted by a bootstrap wrapper through
`msvcrt.open_osfhandle`; documentation must not claim direct numeric CRT-fd inheritance
parity. Stdin remains the portable direct-executable route.

## Rationale

A machine-oriented CLI needs a portable channel and a composable channel when stdin has
another owner. Providing both everywhere makes operator knowledge transferable and
turns missing support into a gate failure. Centralizing declarations, selection, bounded
reading, and metadata removes substitutable mechanics that drift; retaining local strict
models preserves distinctions between proof, establishment, rotation, recovery, and
certificate protection. Removing implicit environment fallback leaves one observable
CLI precedence model without changing separately governed programmatic configuration.

## Consequences

Every scalar-secret verb becomes uniformly automatable through stdin or an inherited
descriptor. The hard-cut field renames and environment removal intentionally break
callers using restore `password`, certificate `secret`, or implicit environment fallback;
accepting both contracts would preserve the ambiguity this decision removes.

Machine metadata becomes sufficient to construct valid payloads without trial failure,
expanding generator and conformance obligations without exposing values. Descriptor
input remains caller-sensitive: this process closes what it reads, but documentation
must recommend an anonymous inherited pipe rather than promise one.

Acceptance requires runtime stdin and fd coverage on all five verbs; conflict-before-read
and no-mutation proofs; closure and fd 0/1/2/unreadable/negative coverage; malformed,
duplicate, missing, extra, invalid UTF-8, and oversize refusal; verified prompt-only and
environment-absence tests; field hard-cut refusal; conditional restore metadata;
four-locale parity; generated schema/help parity; secret-free output; obsolete-symbol
absence; docs/sequence reconciliation; and full CLI, locale, generation, Vaultspec, and
formal-review gates.
