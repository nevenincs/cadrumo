---
tags:
  - '#audit'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:0d0d461ab5a285c0a0121a8a74bd559c594c3526f9333acac3462f7c94db60ab'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# `cli-machine-secret-channel-unification` audit: `s10 certificate machine secret`

## Scope

Formal review of S10 commit `fb28b4bbab`, limited to the certificate
secret-set migration in `_certificate.py`, its command declaration in
`_auth_command_specs.py`, and the focused certificate machine-secret tests.
The review traced the shared selector and bounded reader used by this handler,
the closed payload-model registry, and the governing research, ADR, plan, and
S10 execution record. It also reproduced the reported full integration-file
failures against the current HEAD to classify whether S10 caused them.

## Findings

### certificate-handler-proof | medium | The focused tests do not exercise either machine channel through the certificate handler

`test_certificate_machine_secret.py` proves only model registration, the
single canonical field, redacted model representation, legacy-field model
refusal, and static command-spec ordering. It never invokes
`certificate_secret_set`. Consequently S10 has no command-level test proving
that stdin and fd payloads reach `set_operator_certificate_source_secret`, that
a dual-channel conflict occurs before importing or calling the application
service, that fd 0 and descriptor closure survive this handler integration, or
that the retired `secret` field is refused through the real CLI without
mutation or secret-bearing output. Generic tests of `_secure_input.py` establish
the reader's mechanics, and `test_config.py` covers only the absent-channel
non-TTY refusal; neither detects a future certificate-specific wiring or
ordering regression. The implementation currently delegates correctly at
`certificate_secret_set`, but its security boundary is under-proved until the
certificate handler or the planned subprocess matrix exercises these paths.

Resolved in the S10 remediation: near-handler tests now drive stdin and a real
pipe descriptor through `certificate_secret_set`, observe the supplied value at
the application boundary, prove the descriptor closes, preserve unread pipe
bytes during a dual-channel conflict, and prove both conflict and retired-field
refusals occur without application mutation or emitted output. They also assert
that the supplied value is absent from emitted and refusal representations. fd 0
remains proven by the canonical reader tests and is reserved for the later real
subprocess matrix, avoiding unsafe process-global descriptor replacement in
this unit lane.

### stale-certificate-carrier-description | low | The existing absent-channel integration test describes superseded channel and login behavior

The prose in `test_config.py` still describes the refusal as naming only
`--secrets-stdin` and says login defers to environment-backed substrate
precedence. The accepted contract and landed login migration require the paired
explicit channels and forbid CLI environment fallback. The assertions remain
useful and pass, but the explanation is now misleading to future maintainers
auditing why this certificate command is the carrier.

## Recommendations

- Add direct certificate-secret handler coverage for stdin success, inherited-fd
  success including fd 0 and closure, dual-channel conflict before application
  import/call, strict `certificate_passphrase` acceptance, retired `secret`
  refusal, non-TTY prompt refusal, no mutation on every refusal, and
  secret-free rendered output. The planned cross-command subprocess matrix may
  satisfy the end-to-end portion, but the mutation-order assertion should remain
  close to this handler.
- Refresh the stale `test_config.py` carrier description during the scheduled
  obsolete-code and documentation purge so it names both explicit channels and
  no longer advertises removed environment fallback.
- Treat the two reproduced `test_config.py` failures as unrelated to S10: both
  assert command identity on `config.profile.show`, while S10 changes only the
  certificate secret-set declaration, payload, and tests. The remaining eleven
  integration tests, including certificate absent-channel refusal, pass.
- No HIGH or CRITICAL finding was identified. The S10 implementation has the
  exact paired declarations and strict registered `certificate_passphrase`
  model, refuses legacy `secret`, selects conflicts before application import
  and mutation, inherits fd 0 and unconditional closure from the canonical
  reader, uses the hardened non-TTY prompt refusal, emits only non-secret result
  facts, and introduces no duplicate parser or local channel implementation.
- Close `certificate-handler-proof`: the focused remediation supplies the
  missing handler-level mutation-order, routing, closure, hard-cut, and
  non-disclosure evidence without duplicating the planned subprocess matrix.
