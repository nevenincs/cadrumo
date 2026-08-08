---
tags:
  - '#reference'
  - '#recovery-mnemonic-surface'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:59ae56ac9479f6caac89fbf149d690e52b0fdd58cd540af1f5cd8daa9dfcf105'
related:
  - '[[2026-08-08-recovery-mnemonic-surface-adr]]'
---

# `recovery-mnemonic-surface` reference: `grounding`

## Summary

Codebase grounding for the decision on whether secret-mnemonic recovery belongs
on a TUI full-screen surface.

## The recovery application layer

`src/cadrumo/application/user_profile/_custody.py` owns the lifecycle:
`create_recovery_code` and `rotate_recovery_code` (both delegating to a shared
`_enroll_recovery_code` taking a `confirm` callback), `verify_recovery_code`
taking a mnemonic and returning a verification record, `recover_secret_store`
taking a mnemonic and a new passphrase — the forgotten-passphrase path —
`inspect_recovery_status`, and `change_passphrase`.

The result records carry only a recovery path, a non-secret recovery
fingerprint, and booleans. The module states that the candidate mnemonic is
never held on the result record and that the plaintext words are never persisted
or returned; the `confirm` callback displayed them during enrollment.

`src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py` is the
storage-side facade. The single point where plaintext words leave the module is
the `confirm(candidate.mnemonic)` call; the module records that the mnemonic is
never returned, that none of the operations serialize the mnemonic or the master
key, and that the confirm call is an unbounded interactive pause after which
enrollment preconditions are re-asserted.

## The CLI verbs

`src/cadrumo/entrypoints/cli/_config/_custody_secret.py` registers
`aeat config recovery status`, `create`, `rotate` and `verify`, the flat
`aeat config recover` forgotten-passphrase verb, and `aeat config passphrase
change`.

The display helper is `_confirm_candidate_on_terminal`, which records that the
words reach only the terminal device — never stdout, the JSON envelope, or a log
— and that the operator must retype all 24 words with echo suppressed before
enrollment commits. The verbs refuse before any custody read when stdin is not a
TTY.

`write_to_controlling_terminal` and `prompt_secret_no_echo` in the shared secure
input helper enforce the device contract: the write must not ride stdout;
opening the console handle succeeds against a console-less host, so a candidate
would otherwise be written to a phantom console while the verb reported success,
and the words are shown exactly once and are unrecoverable afterwards. An
echo-suppression failure is a typed refusal, not a degraded visible read.

## The governing custody record

`2026-07-25-auth-cert-recovery-custody-adr` states in its Considerations that
recovery enrollment is interactive by construction, that "the candidate words
are displayed once on the terminal device and must be fully retyped with echo
suppressed before anything commits, so no automated driver can enroll a recovery
code however the passphrase is sourced", and that an environment channel
therefore buys enrollment nothing it can use.

Its Implementation section records that the interactive door supplies a guarded
terminal prompt built on the hardened no-echo helper, carrying a real-console
precondition, a stdin-identity precondition, and promotion of an
echo-suppression failure to a typed refusal. Its Consequences record that a
console-less host refuses instead of blocking and a rebound stdin refuses
instead of echoing.

## The TUI primitives

Under `src/cadrumo/adapters/inbound/tui/`, the form model is `_form_screen.py`:
`FormPage` carries a title, section and fields; `FormField` carries key, label,
value, kind, choices, hint, validator and a secret flag; `FormFieldKind` admits
only text, multi-choice and single-choice. Every unit of the form model is a
collected, editable value — there is no read-only or display kind.

Display-only rendering exists only as raw framework labels composed inside
specific screens (the confirm dialog's message, the status screen's panels) and
the notice band in `_theme.py`. None is parameterised as secret-bearing.

Modal primitives exist and are used directly: `ConfirmScreen`,
`FieldEditScreen`, and the form package's text and choice edit screens are all
framework modal screens; screens are pushed with `push_screen` from the app, the
form screen, the manager, the question screen and the review screen.

Secrets appear in the TUI only as masked INPUTS: the login and registration
passphrase fields, and the form screen's input driven by the field's secret
flag. `_field_edit_screen.py` deliberately opens a masked field with an empty
value rather than repopulating the masked value.

`StatusRecoveryView` in `_status_screen.py` is documented as carrying no secret
and never a mnemonic; the recovery panel renders enrolled state, the fingerprint
and the literal CLI command strings for create, rotate and verify.

## The leak gates and their blind spot

`src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py`
carries a no-secret-serialization class asserting the persisted envelope never
contains the plaintext mnemonic or master key, and that a failed recover's error
envelope excludes the wrong mnemonic and each of its words.

`src/cadrumo/entrypoints/cli/tests/test_config_recovery_lifecycle.py` proves the
lifecycle round-trips without a serialized mnemonic, that create and rotate
refuse without an interactive terminal, and that the verbs accept no mnemonic on
argv.

`src/cadrumo/adapters/inbound/tui/tests/test_visual_verification.py` carries the
render gate asserting a masked field never paints its secret: it sets sentinel
values into every masked input across enrolled surfaces and asserts absence from
an exported screenshot. Its own docstring records the boundary — it cannot see a
secret collected inside a MODAL the base screen pushes only on a button press,
because it does not drive navigation into nested screens.
