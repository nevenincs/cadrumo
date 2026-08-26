---
tags:
  - '#audit'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:38564f220e726b27b32ba7a87e9c6d9aaf25ad50895f363f620e9fd7af469dd2'
related:
  - '[[2026-08-23-cli-machine-secret-channel-unification-adr]]'
  - '[[2026-08-23-cli-machine-secret-channel-unification-plan]]'
  - '[[2026-08-23-cli-machine-secret-channel-unification-W02-P11-S21]]'
  - '[[2026-08-23-cli-machine-secret-channel-unification-W02-P11-S22]]'
---

# `cli-machine-secret-channel-unification` audit: `s22 root profile authentication`

## Scope

Independent SOL review of the S22 root profile-authentication changes landed in
`09c599e70b3` and their execution/audit records landed in `c152671f052`. The
review traced the amended ADR and plan through the S21 medium findings, the
typed neutral gate seam, Notice delivery and cleanup, the Windows inherited
HANDLE bootstrap, all four locale catalogues, focused contract tests, and a
real keychain-free login followed by a leaf refusal. Semantic discovery was
narrowed with exact source searches and the settled commit diff rather than the
concurrent working tree.

## Findings

No critical or high finding remains. The concrete `RootAuthenticator` protocol
and type-only imports remove the S21 seam erasure without a runtime import
cycle. Success envelopes and ordinary refusal/crash envelopes each drain the
invocation-scoped Notice once. The committed locale delta changes exactly the
seventeen intended root-authentication/help/Notice leaves in every locale; the
canonical locale semantic tests pass and no unrelated semantic locale value
changed. The inherited-HANDLE wrapper accurately converts ownership to a CRT
descriptor in-process and does not claim that a numeric POSIX descriptor is
inherited on Windows. Canonical descriptor reads close on success and refusal,
with descriptors 1 and 2 reserved and descriptor 0 accepted.

### s22-click-refusal-notice | medium | callback Click refusals still drop the non-persistence Notice

`consume_root_fallback` stages `config.login.session_not_persisted` after a real
keychain-free login, but `command_error_boundary` deliberately re-raises Click
control-flow exceptions and `_emit_click_exception` renders them without
calling `drain_profile_authentication_notices`. These are not only parse-time
failures: many authenticated handlers raise `typer.BadParameter` from their
callback bodies. A real `config profile history` invocation authenticated via
`--profile-secrets-stdin`, then raised its callback `--since`/`--until`
refusal; the JSON error contained `"notices": []`. The passphrase did not leak,
but the promised persistence warning was omitted and the ContextVar remained
staged until process teardown. Thus the first S21 medium is narrowed but not
fully closed. Existing S22 tests cover direct `render_error_payload` refusal
and an ordinary ledger refusal, not this third terminal funnel.

## Recommendations

- Close `s22-click-refusal-notice` before marking S22 complete: make
  `_emit_click_exception` drain the same invocation-scoped Notice queue exactly
  once. Supply the drained notices to `render_error_json` in JSON mode and emit
  the canonical `notice_lines` transport before Click's text rendering in text
  mode. Keep parse-time behavior state-free; its queue is naturally empty.
- Add JSON and text unit coverage for the Click funnel, including one-shot
  cleanup, plus a real keychain-free callback `BadParameter` regression such as
  `config profile history --since ... --until ...`. Assert the Notice code
  appears exactly once and the passphrase never appears.
- Retain S13 ownership of the full POSIX `pass_fds` and Windows
  `STARTUPINFOEX` inherited-HANDLE subprocess matrix; the S22 bootstrap and
  platform-specific low-level test are architecturally honest but are not that
  later end-to-end matrix.

### Closure

The medium finding is closed. `_emit_click_exception` now drains the staged
Notice once before selecting its JSON or text arm, passes the typed Notice into
the JSON error envelope, and emits canonical `notice_lines` before Click text.
Focused JSON/text tests prove one-shot cleanup, and a real keychain-free
`config profile history` invocation proves Argon2 authentication followed by a
callback `BadParameter` still emits `config.login.session_not_persisted` with no
passphrase disclosure. No critical, high, or medium finding remains.
