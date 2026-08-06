---
tags:
  - '#audit'
  - '#auth-cert-recovery-custody'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:aebd5351fad89403243ae618e088aeb9eb5ed302ff9d408bd87d4782744c29f7'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
  - "[[2026-07-17-auth-cert-recovery-custody-adr]]"
---

# `auth-cert-recovery-custody` audit: `P04 passphrase and recovery CLI door safety review`

## Scope

Independent, fresh-context safety review of the P04 passphrase and recovery CLI
door, carried out because the campaign close honesty review found this review
had been claimed but never performed. Nothing in the prior claim was taken as
evidence; every verdict below is grounded in code read at HEAD `5467b60b86`,
and the two load-bearing ones are grounded in executed reproduction probes.

Surfaces read in full: `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`,
`src/cadrumo/entrypoints/cli/_config/_secure_input.py`,
`src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`,
`src/cadrumo/application/user_profile/_custody.py`,
`src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`,
`_recovery_facade.py`, and `_recovery_record.py`. Followed outward where the
call graph left the nominal scope: `_master_key_io.py`, `_master_key.py`,
`_login_throttle.py`, `_login_session.py`, `_config_payloads.py`,
`core/logging.py`, `core/config.py`, and the four locale catalogues.

Five axes were covered: secure TTY discrimination, no-echo retype, secrets-stdin
bounds, mnemonic and passphrase absence from argv / envelopes / logs / help, and
open review for anything else security-relevant.

Two items already tracked as plan steps were confirmed present and deliberately
NOT re-raised as new findings: immutable `bytes` / `str` key material out of
reach of the zeroise primitive (step S49), and the recovery-enrollment manifest
flag write not being atomic with the envelope install, visible at
`_custody.py:274` (step S50).

Verification limits, stated plainly rather than implied away. Agents here run
over an SSH network logon, so Windows keychain operations fail with
`WinError 1312`; every assertion below is therefore about the file secret-store
backend, and the keyring custody path was not exercised at runtime — it was read
only. No production source file was modified during this review.

The existing gates over these surfaces were run rather than assumed: 81 passed,
with a single timeout in the redirected-pipe case of the echo-guard module under
parallel execution. Re-run sequentially it passes in 68 seconds, so the cause is
interpreter-spawn cost on a loaded box rather than a regression; the figure is
recorded because a 120-second subprocess budget is thin for a test whose child
must import the whole package before it can refuse.

Three reviewed files carried live uncommitted peer work at review time — the
recovery primitives, the recovery facade, and the custody module — evidently the
in-flight implementation of the wipeable-key-material step S49. Every line cited
below was therefore re-derived against HEAD rather than the working tree, and
the two findings that touch those files were re-checked against the peer's diff:
the enrollment ordering it changes preserves `get_master_key()` before
`confirm`, and it does not alter how the enrollment resolves its passphrase
callback, so both findings stand under the in-flight change as well as at HEAD.
The four files the reproduction probes exercised carry no uncommitted change, so
the probe results describe HEAD exactly.

## Findings

### enrollment-passphrase-prompt-unhardened | high | `config recovery create` and `rotate` reach a bare `getpass.getpass` that hangs forever on a console-less host and can fall back to an echoing read

The hardened prompt is not on the path the enrollment verbs actually take. The
chain is `_custody_secret.py:399` calling the application enrollment, which at
`_custody.py:262` resolves a provider with `get_master_key_provider(settings_override=resolved)`
and passes NO `passphrase_callback`. `_master_key.py:1163-1166` therefore builds
`FileFallbackMasterKeyProvider(store_dir=..., passphrase_callback=None)`, and
`_master_key.py:409` binds `self._passphrase_callback = passphrase_callback or _default_passphrase_callback`.
`_recovery_facade.py:344` then calls `file_provider.get_master_key()`, which
resolves the secret-store passphrase through `_master_key_io.py:53-73` — whose
only guard is the `isatty` pair at line 65 before it calls bare
`getpass.getpass` at lines 72-73.

That bare call has none of the three guards `prompt_secret_no_echo` installs at
`_secure_input.py:167-195`: no `_stdin_is_a_real_console()` probe, no
`sys.__stdin__` identity precondition, and no promotion of `GetPassWarning` to a
typed refusal. The exposure is not theoretical; both halves were reproduced.

A detached-process probe (Windows, stdin and stderr on `NUL`) recorded
`stdin_isatty: true`, `stderr_isatty: true`, `stdin_is_dunder: true` — so line
65 admits it, `win_getpass` takes the `msvcrt` branch, and `msvcrt.getwch()`
blocks. The child was still alive with no result after 45 seconds and had to be
killed. This is precisely the hang that `_stdin_is_a_real_console()` at
`_secure_input.py:71-110` was written to eliminate, and that the gate
`test_secure_input_echo_guard.py:173` proves is eliminated for
`prompt_secret_no_echo` — still fully reachable through `aeat config recovery
create`. An operator invoking enrollment from a service context, a scheduled
task, a CI lane, or a GUI-launched detached process hangs indefinitely with no
diagnostic and no way to tell a hang from a slow KDF.

A second probe on a genuine console with `sys.stdin` rebound to a readable
character device recorded `getpass_warning_emitted: true`, proving control
reached `fallback_getpass` — the ECHOING read — with the warning swallowed
rather than promoted. On that channel the master-store passphrase is typed in
cleartext. The probe terminated with `EOFError` only because the rebound device
yields EOF immediately; a channel carrying real keystrokes would have echoed
them. Note also that `EOFError` escapes `_default_passphrase_callback` untyped,
so the operator meets a raw traceback rather than a localised refusal.

The cheap `sys.stdin.isatty()` pre-check at `_custody_secret.py:389` does not
save this: on a console-less host `isatty()` is `True`, so it passes. And the
one guard that WOULD refuse — the real-console check inside
`write_to_controlling_terminal` at `_secure_input.py:128` — sits downstream of
the blocking `get_master_key()` call at `_recovery_facade.py:344` and is never
reached. Ordering is load-bearing here.

Remediation: have the enrollment path supply the hardened prompt explicitly
rather than inheriting the module default — pass a `passphrase_callback` built
on `prompt_secret_no_echo` from the CLI layer down through
`_enroll_recovery_code`, the way `change_passphrase` and `recover_secret_store`
already do at `_custody.py:305-313`. Both of those construct
`_file_provider_with_passphrase` with an explicit callback and are therefore NOT
affected; only `create_recovery_code` and `rotate_recovery_code` are. Add a
regression in the shape of `test_secure_input_echo_guard.py:173`, driving the
enrollment verb rather than the prompt helper, so the hang cannot silently
return.

### secrets-stdin-duplicate-keys-collapse-silently | low | A duplicated JSON key in a `--secrets-stdin` payload is silently resolved to the last occurrence

`_secure_input.py:54` parses the payload with plain `json.loads`, which accepts
duplicate object keys and keeps the last one. The strict model does catch the
cases it can see — `extra="forbid"`, `SecretStr` fields, non-object and
malformed input all refuse at `_secure_input.py:59-68` — but a duplicate key is
already collapsed by the time pydantic sees the mapping, so `extra="forbid"`
cannot fire. Confirmed by execution: a payload carrying `recovery_code` twice
validated cleanly against `_RecoverSecrets` and yielded the second value.

No privilege boundary is crossed, since the caller supplies every field, so this
is not an escalation. The real hazard is silent custody drift on the channel
that exists for automated drivers: a payload assembled from concatenated
fragments or a templating bug can rewrap the secret store under a passphrase the
author never intended, and the new/confirmation mismatch guard at
`_custody_secret.py:186` compares post-collapse values, so it agrees with the
mistake instead of catching it.

Remediation: parse with an `object_pairs_hook` that rejects repeated keys and
refuse on the existing `secrets_stdin_invalid_json` key, so the strict-parse
contract the module docstring claims is actually total.

### passphrase-env-var-is-an-undeclared-third-channel | low | The module contract says secrets arrive by exactly two channels; an environment variable is consulted before both

`_custody_secret.py:3-8` states that secrets reach the custody verbs through
"exactly two channels, never the command line" — no-echo prompt or bounded
stdin JSON — and concludes that passphrases "never appear in the process table,
shell history, or logs". `_master_key_io.py:57` consults
`load_settings().cadrumo_secret_passphrase`, sourced from the
`CADRUMO_SECRET_PASSPHRASE` environment variable declared at
`_master_key_io.py:25`, and returns it BEFORE any prompt is considered. That is
a third channel, and it takes precedence. Refusal copy actively advertises it at
`_master_key.py:437` and `:444`.

The value itself is well handled — `core/config.py:556` types it as `SecretStr`,
which masks in both `repr` and `model_dump_json`, verified by execution, so the
settings fingerprint blob at `observability/_fingerprint.py:140` emits only
`**********`. The gap is contractual, not a live leak: an environment variable
is readable by same-user processes and lands in shell history when set inline,
so the docstring's absolute claim overstates the guarantee that the door
provides. A reader hardening an adjacent surface will trust that sentence.

Remediation: amend the docstring to name the environment channel and its
precedence, or route the enrollment verbs so the env var is not consulted for
interactive custody operations. This should be settled together with the high
finding above, since both concern which callback the enrollment path resolves.

### create-mode-enrollment-toctou | low | The "already enrolled" refusal is evaluated before an unbounded interactive pause and never re-checked at install

`_recovery_facade.py:332` reads `already_enrolled = path.is_file()` and refuses a
CREATE against an existing enrollment. The install at `_recovery_facade.py:356`
then writes unconditionally through `atomically_install_verified_recovery`,
which by design at `_recovery.py:320-323` only sequences verify-before-write and
does not re-assert the mode precondition. Between those two points sits
`confirm` at line 346 — an operator transcribing and retyping 24 words, an
unbounded wall-clock window. A recovery envelope enrolled by a concurrent
invocation inside that window is silently replaced by the CREATE that was
supposed to refuse, and the displaced envelope's mnemonic becomes worthless.

Severity is low because this needs two concurrent enrollments on one secret
store, which is not a normal operator shape. It is nonetheless a real
lost-custody outcome rather than a mere race, and the fix is cheap.

Remediation: re-assert the mode precondition inside the verify callback at
`_recovery_facade.py:349-354`, so the check lands on the same side of the pause
as the write, or perform the install with `O_EXCL` semantics for CREATE mode.

### custody-verbs-carry-no-failed-attempt-throttle | low | The failed-attempt backoff guards `config login` only; the custody verbs are unthrottled, though not materially exploitable

`evaluate_login_throttle` and `record_login_failure` have exactly one production
consumer, `_login_session.py:426` and `:538`. `config passphrase change`,
`config recovery verify`, and `config recover` call none of them, and all three
are bootstrap-exempt at `_bootstrap_exempt.py:74-77`, so they run with no
session. `config passphrase change` is therefore an unlimited passphrase-check
oracle and `config recovery verify` an unlimited mnemonic oracle.

Reported honestly rather than inflated: this is very likely not exploitable. Any
caller able to run these verbs already has same-user read access to `master.key`
and `master.kdf` and can mount the identical Argon2id attack offline at the same
cost, so the CLI confers no advantage; and the mnemonic carries 256 bits of
entropy from `secrets.token_bytes` at `_recovery.py:210`, which is not
guessable. The finding is recorded because the asymmetry is undocumented and a
future change that makes these verbs remotely or cross-user reachable would turn
it into a real exposure with nothing flagging the regression.

Remediation: either extend the existing throttle to the custody verbs, or record
the deliberate exemption and its reasoning in the custody module docstring so
the asymmetry is a decision rather than an oversight.

### stdin-size-cap-implemented-but-unproven | low | The 8192-byte secrets-stdin bound is correct in code and has no test

`_secure_input.py:47-51` reads `_MAX_SECRETS_STDIN_BYTES + 1` and refuses when
the read exceeds the cap — correct, and genuinely bounded, since
`BufferedReader.read(n)` stops at `n`. The bounds test at
`test_config_recovery_lifecycle.py:345` covers malformed, wrong-field, and
non-object payloads but never an oversize one, so the one branch that exists
specifically to stop an unbounded hostile stream is the one branch with no
coverage. No exposure today; an unguarded regression here would be invisible.

Remediation: add an oversize case to that test, asserting exit 2 and the
`secrets_stdin_too_large` key.

### axis-verdicts-that-are-genuinely-clean | low | No-echo retype, mnemonic non-serialisation, and log safety hold under inspection and execution

Recorded so the clean results are auditable rather than assumed.

The no-echo retype axis is clean. The candidate mnemonic is written to the
terminal DEVICE, not stdout: `_custody_secret.py:200` calls
`write_to_controlling_terminal`, which opens `CONOUT$` or `/dev/tty` at
`_secure_input.py:132-136` and refuses when that is not a real console at
`:128`. The retype at `_custody_secret.py:212` goes through
`prompt_secret_no_echo`, and the confirmation is a real AEAD unwrap, not a
string comparison — `_recovery_facade.py:350` calls `verify_recovery_mnemonic`,
and the install is gated behind it by `atomically_install_verified_recovery` at
`_recovery.py:320`, so a mistyped or cancelled retype leaves any prior envelope
byte-identical.

The argv, envelope, and help axis is clean. No custody verb declares a secret
option; the only options are `--secrets-stdin` and `--output-language`
(`_custody_secret.py:79-89`, `:221-231`, `:334-344`). Every result payload
carries fingerprints and booleans only (`_config_payloads.py:293-369`), matching
the application records at `_custody.py:59-116`. `RecoveryRecord` stores wrap
material and never the words (`_recovery_record.py:37-57`), and its fingerprint
is derived only from ciphertext, nonce, tag, and constants (`:71-80`). The four
locale catalogues carry prompts and descriptions but no specimen mnemonic or
passphrase; `secrets_stdin_help` in all four is a plain one-line description
with no example payload. This axis is also independently gated by
`test_config_recovery_lifecycle.py:207` and `:412`.

The log axis is clean. The two `exc_info=True` sites at `_custody.py:190` and
`:296` emit standard-library tracebacks — `core/logging.py:46` uses a plain
`logging.Formatter()`, and a repository-wide search found no `show_locals`,
`RichHandler`, or `rich.traceback` installation — so no frame locals, and
therefore no mnemonic or passphrase, can reach a log record. Error text is safe
by construction too: the decode failures at `_recovery.py:181-198` report a word
POSITION and never the word, and the `str(exc)` re-raises at
`_custody_secret.py:113`, `:247`, and `:356` carry only these static or
positional messages.

Secure TTY discrimination is clean for the prompt helper itself:
`_stdin_is_a_real_console` at `_secure_input.py:71-110` discriminates a real
console from a bare character device via `GetConsoleMode`, fails closed on any
exception at `:109-110`, and `GetPassWarning` IS promoted to a typed refusal at
`_secure_input.py:180-185`. The axis fails only where the enrollment flow
bypasses this helper, which is the high finding above.

## Recommendations

Route the enrollment passphrase prompt through the hardened helper, closing
`enrollment-passphrase-prompt-unhardened`. Thread an explicit
`passphrase_callback` built on `prompt_secret_no_echo` from the CLI layer into
`_enroll_recovery_code`, mirroring the shape `change_passphrase` and
`recover_secret_store` already use, so no custody verb inherits the module
default. Pair it with a regression modelled on the existing console-less gate but
driving `aeat config recovery create`, so the test fails on timeout and a
reintroduced hang cannot pass by hanging. This is the one finding that warrants
its own plan Step; everything else below is smaller.

Decide, and record, which channels may supply the secret-store passphrase,
resolving `passphrase-env-var-is-an-undeclared-third-channel` together with the
finding above. The two are entangled: fixing the callback resolution settles
whether `CADRUMO_SECRET_PASSPHRASE` remains reachable from interactive custody
verbs. If the environment channel is deliberate — plausible, given automated
drivers — the door's docstring must say so and stop claiming exactly two
channels. If it is not deliberate for these verbs, the callback change removes
it. This is the one item whose resolution is a decision rather than a repair, so
it belongs in a follow-on ADR rather than being settled by an implementer.

Make the strict-parse contract total, closing
`secrets-stdin-duplicate-keys-collapse-silently`. Reject repeated keys with an
`object_pairs_hook` and refuse on the existing invalid-JSON locale key, so no
new operator-facing copy is needed.

Move the CREATE-mode precondition to the write side, closing
`create-mode-enrollment-toctou`, by re-asserting it inside the verify callback
that already gates the install, or by using exclusive-create semantics.

Settle the throttle question explicitly, closing
`custody-verbs-carry-no-failed-attempt-throttle` — either extend the existing
backoff to the custody verbs or document the exemption and its reasoning, so a
later reachability change cannot silently inherit an undefended surface. A
formal deferral is an acceptable outcome here given the honest low-exploitability
assessment; leaving it unrecorded is not.

Add the missing oversize case, closing `stdin-size-cap-implemented-but-unproven`.

Verify the keyring custody path on an operator console session. This review
could not exercise it: agent sessions run over an SSH network logon where
Windows keychain calls fail with `WinError 1312`, an environment artefact rather
than a defect. The file-backend refusals for keyring and unsecured custody at
`_recovery_facade.py:289-306` were read and appear correct, but they were not
executed, and this audit should not be read as covering them.
