---
tags:
  - '#research'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:4cd5f3fd1362343595365dad4ee77622cbe93c6477b132338bdda01d52673c31'
related: []
---

# `cli-machine-secret-channel-unification` research: `Global machine-secret channel contract`

The CLI has one sound bounded parser but no global machine-secret contract. Five
verbs accept caller-supplied scalar secrets; only login, passphrase rotation, and
profile restore expose both explicit machine channels. Profile creation and
certificate-secret mutation omit `--secrets-fd`, descriptor behavior lacks real
end-to-end coverage, command metadata hides the payload shape, and accepted ADR
text conflicts with live stdin and environment behavior. The evidence favors one
hard-cut contract with both explicit channels on every applicable verb, one shared
selector and reader, command-local typed payloads, and discoverable secret-field
schemas. The ADR must settle environment fallback, field vocabulary, metadata
projection, and the descriptor durability claim.

## Findings

### Five scalar-secret verbs form the complete applicable CLI surface

The production census is `config login`, `config profile create`, `config
passphrase change`, `config profile restore`, and `config auth certificate secret
set`. Their payloads are respectively one passphrase, passphrase plus confirmation,
current/new/confirmation, password or recovery mnemonic, and PKCS#12 passphrase.
Only the first, third, and fourth expose stdin and fd today
(`src/cadrumo/entrypoints/cli/_config/_custody.py:23`,
`src/cadrumo/entrypoints/cli/_config/_passphrase.py:40`,
`src/cadrumo/entrypoints/cli/_config/_restore_cli.py:61`). Creation and certificate
mutation expose stdin only (`src/cadrumo/entrypoints/cli/_config/_manager_dispatch.py:166`,
`src/cadrumo/entrypoints/cli/_config/_certificate.py:375`). None consumes stdin for
business data, so no current verb has an evidence-backed exception to both machine
flags.

Certificate registration `--file` and Google registration `--client-json` carry
credential documents rather than scalar secrets; public keys, idempotency keys, and
provider-minted OAuth tokens are also different contracts. Folding them into the
secret JSON object would replace their canonical document/protocol transport without
improving machine operability (`src/cadrumo/entrypoints/cli/_config/_certificate.py:1`,
`src/cadrumo/entrypoints/cli/_config/_google.py:146`).

### Shared mechanics are strong, while declarations and resolution still drift

The shared secure-input module already owns the 8 KiB ceiling, strict UTF-8 JSON
object parsing, recursive duplicate-key refusal, command-local Pydantic validation,
one-shot descriptor closure, channel-conflict refusal, and hardened no-echo prompt
(`src/cadrumo/entrypoints/cli/_config/_secure_input.py:57`, `:76`, `:141`, `:195`,
`:248`, `:377`). These mechanics should remain canonical.

True duplication remains in repeated Typer options, repeated fd/stdin/prompt branching,
repeated strict-model configuration, and creation's hand-built signature injection.
Command-specific payload models and application-level confirmation are not duplication:
they encode distinct semantic contracts and protect non-CLI callers. A shared option
declaration plus typed selector/reader can remove the former without flattening the
latter.

### The live behavior contradicts the accepted headless-secret decision

The accepted custody roll-up states that headless secrets use only bounded one-shot
`--secrets-fd` and forbids argv/environment secrets
(`.vault/adr/2026-08-13-profile-password-custody-rollup-adr.md:87`). The accepted
action-envelope successor repeats that ownership boundary
(`.vault/adr/2026-08-13-cli-action-envelope-successor-adr.md:30`). Live commands also
accept stdin, while login and creation inherit or consult
`CADRUMO_SECRET_PASSPHRASE` (`src/cadrumo/entrypoints/cli/_config/_custody.py:254`,
`src/cadrumo/entrypoints/cli/_config/_scripted_registration.py:87`). The older login
decision that allowed stdin/environment is superseded. A new governing decision must
replace the fd-only rule rather than silently accumulating another accepted sibling.

The evidence favors explicit stdin plus fd on all five verbs and deletion of implicit
CLI environment fallback. Programmatic substrate/keyring resolution is a separate
contract and need not be removed. Retaining CLI environment fallback is an alternative,
but it needs an explicit rationale and uniform applicability; current asymmetry supplies
neither.

### Existing tests and localized diagnostics do not prove the descriptor contract

Exact repository search finds no real functional CLI `--secrets-fd` invocation test;
current assertions cover help or routing predicates. Required proof therefore includes
real inherited-descriptor success for all five verbs, stdin/fd conflict before read or
mutation, invalid UTF-8/JSON/object shapes, duplicate/missing/extra fields, oversize and
unreadable descriptors, fd 0 equivalence, reserved fd 1/2, negative fd, descriptor
closure, and secret-free localized failure output.

All four `secrets_fd_reserved_stream` translations falsely say standard input is
reserved, while production deliberately permits fd 0 and reserves only 1 and 2
(`src/cadrumo/entrypoints/cli/_config/_secure_input.py:65`, `:224`;
`src/cadrumo/locales/en/cli.yml:1649`). The duplicate-key helper also names
`secrets-stdin` internally even when fd parsing invokes it
(`src/cadrumo/entrypoints/cli/_config/_secure_input.py:92`). Locale correction must use
`python -m dev.locales`.

### Machine metadata cannot yet describe how to call the secret channel

Generated command metadata exposes `--secrets-stdin` as boolean and `--secrets-fd` as
integer but omits each strict JSON object's required fields. An autonomous caller must
fail once to discover the payload. The live Click materializer and generated metadata
already provide a parity-gated authority
(`src/cadrumo/entrypoints/cli/_verb_input_schema.py:571`,
`src/cadrumo/entrypoints/cli/_command_schema.py:190`); the ADR should decide whether to
project field names and types there or introduce a separate exact-set secret-command
registry. Values, defaults, and examples must never enter metadata.

Payload vocabulary also drifts: profile operations use `passphrase` except restore's
`password`, while certificates use generic `secret`. Global uniformity can hard-cut to
semantic names such as `passphrase` and `certificate_passphrase`, or deliberately keep
domain-local names. Compatibility aliases are unavailable under the active pre-release
regime.

### Descriptor transport must not claim more ephemerality than it enforces

`read_secrets_fd` accepts any readable inherited descriptor, including a regular file.
Restricting to pipes/sockets may be hard or platform-specific; alternatively, the ADR
can state that one-shot bounded reading and local descriptor closure are guaranteed,
while transport lifetime and backing storage remain caller-owned. Either is honest;
calling every fd ephemeral without enforcement is not.

### The implementation proof must cover runtime and discovery surfaces together

The closure matrix should require both flags exactly once in help, Click parameters,
generated registration metadata, and verb-input schemas for all five commands; safe
payload-field discovery; real stdin and inherited-fd subprocess success; four-locale
errors selected before parsing; no argv, output, repr, log, or mutation leaks; verified
interactive prompting only; explicit environment-policy tests; and generated metadata,
documentation, sequence-contract, locale, schema, and formal security gates. Relevant
history begins with fd commit `2417ff2ec78f08f8a93f8754499191e6a564f76e`, restore
adoption `cfa995697b104087ce4dd697fdd1ca613906fdc1`, and creation stdin commit
`601e90890f5a1822729719e3c76c0c725eb548a3`.

## Sources

- `src/cadrumo/entrypoints/cli/_config/_secure_input.py:1`
- `src/cadrumo/entrypoints/cli/_config/_custody.py:23`
- `src/cadrumo/entrypoints/cli/_config/_scripted_registration.py:51`
- `src/cadrumo/entrypoints/cli/_config/_manager_dispatch.py:166`
- `src/cadrumo/entrypoints/cli/_config/_passphrase.py:40`
- `src/cadrumo/entrypoints/cli/_config/_restore_cli.py:61`
- `src/cadrumo/entrypoints/cli/_config/_certificate.py:1`
- `src/cadrumo/entrypoints/cli/_config/_google.py:146`
- `src/cadrumo/entrypoints/cli/_verb_input_schema.py:571`
- `src/cadrumo/entrypoints/cli/_command_schema.py:190`
- `src/cadrumo/locales/en/cli.yml:1649`
- `.vault/adr/2026-08-13-profile-password-custody-rollup-adr.md:87`
- `.vault/adr/2026-08-13-cli-action-envelope-successor-adr.md:30`
- commits `2417ff2ec78f08f8a93f8754499191e6a564f76e`,
  `cfa995697b104087ce4dd697fdd1ca613906fdc1`, and
  `601e90890f5a1822729719e3c76c0c725eb548a3`
