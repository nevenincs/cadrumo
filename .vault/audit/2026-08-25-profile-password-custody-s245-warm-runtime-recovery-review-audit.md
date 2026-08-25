---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:ce418aa8b22e9db830d5e9954003921aadf8581c22ddfda1f4d48e07f90f15d8'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `profile-password-custody` audit: `S245 warm-runtime recovery review`

## Scope

Reviewed `W06.P12.S245` against the accepted profile-password custody rollup,
the machine-secret channel decision, and the current complete implementation in
`_inprocess.py`, `_profile_secret_channel.py`, `_transport.py`, `_profile.py`,
`test_harness_delivery.py`, `test_inprocess_runtime.py`, and
`test_server_loop_responsiveness.py`. The review
covered mandatory exact
recovery enrollment during real profile provisioning, reuse of the canonical
root `--profile-secrets-stdin` CLI path by the warm transport, process-global
stdin capture and restoration, per-call session relock, crash restart, and the
strength and honesty of the real-behavior tests. It also inspected the working
diff on top of the intermediate test-file state captured by commit
`2be1f36529`. Final execution evidence is complete: the full responsiveness
module passed 6 tests; the combined harness-delivery and in-process-runtime
modules passed 34 tests; the exact stdin-restoration selection passed both
success and refusal cases; and Ruff and ty passed over the complete S245
surface. After canonical session-artifact removal, both warm success lanes
re-authenticated through the stdin source and the cleared-channel anti-tautology
returned the exact `AUTH_STORAGE_KEYRING_UNAVAILABLE` refusal.

The expanded test-fixture consolidation has the correct responsibility shape:
all four harness registration sites now consume one exact mnemonic-possession
callback and one constraint-complete ready-facts tuple from `_profile.py`; a
targeted symbol search found no surviving local recovery callback or ready-facts
redeclaration in the harness test package. This is test-fixture reuse, not a
second production recovery implementation, and preserves the application-owned
`register_profile_with_credentials` boundary.

## Findings

### warm-keychain-free-proof | medium | The runtime success test does not establish that persisted-session resume was unavailable

`_provisioned_profile_env` creates the profile under the ordinary `auto`
secret-store setting and does not remove the registration-created acceleration
receipt or make the OS keychain unavailable before either warm read. A usable
host keychain can therefore satisfy the root profile-session precondition by
persisted-session resume, making the supplied `--profile-secrets-stdin` source
unused; on another host registration can merely fail to persist acceleration
and exercise the intended stdin fallback. The successful active-profile
projection proves real encrypted startup, but not the Step's stronger,
platform-independent claim that a genuinely keychain-free warm runtime consumed
the canonical root secret path. The test is consequently host-dependent and
does not bite if the new warm stdin wiring is removed on a host where resume is
available.

Disposition: **resolved in the reviewed working state**. The fixture now calls
the canonical `close_profile_session_artefacts` operation for the exact created
profile after loading the in-memory channel. That operation closes process-local
record authority and revokes the real durable acceleration receipt and keychain
account, leaving the canonical stdin payload as the only authentication source.
The paired test then clears that source and requires the same real warm command
to return `AUTH_STORAGE_KEYRING_UNAVAILABLE`, so removal of the warm stdin wiring now reds
the gate rather than silently resuming. The remediation adds no alternate
session or recovery implementation.

### stdin-restoration-witness | low | The global stdin restoration guarantee is implemented but not observed

`_redirect_stdin` correctly saves `sys.stdin` and restores it in a `finally`
block while the same global capture lock serialises stdin, stdout, and stderr.
The integration tests exercise repeated secret-bearing calls, but they never
observe that the original stdin object is restored after success or after a CLI
refusal. A regression that leaves the temporary stream installed can therefore
escape this focused suite even though the current implementation is correct.

Disposition: **resolved**. `test_inprocess_stdin_is_restored_after_success_and_refusal`
records the process's original stdin object and proves exact identity restoration
after both a normal command and an inapplicable-secret CLI refusal. Both cases
pass through the real in-process CLI entry point with a real stdin payload.

### session-relock-witness | low | Repeated success is not a direct proof that the prior worker session was zeroised

`_run_inprocess_tool` closes the active bucket session unconditionally in the
worker's `finally`, including eventual completion after a timeout, and the fresh
raw thread prevents its context-local binding from entering the server context.
The test's second successful read and crash-restart read exercise the intended
behavior, but repeated success alone does not distinguish the explicit close
from simply abandoning a still-live session in an unreachable worker context.
The production cleanup is sound by inspection; the named idle-lock proof lacks
an observable postcondition that would fail if the `finally` close were removed.

Disposition: **resolved**. The final gate first removes every process and
durable session artefact, proves the same call refuses when its channel is
cleared, then performs two independently re-authenticated warm calls successfully.
Together with the unconditional worker `finally` close and the raw thread's
non-inherited context, this establishes that no resumable or process-bound key
serves either subsequent call and that cleanup does not strand the runtime.

## Recommendations

- For `warm-keychain-free-proof`, force a real unavailable-resume state without
  mocks: remove the actual acceleration receipt and its keychain account through
  the owning production cleanup operation, verify resume refuses, then require
  the same warm read to succeed from the already loaded profile-secret channel.
  Add an anti-tautology direction showing that clearing the channel makes that
  same state refuse.
- For `stdin-restoration-witness`, add a real success and refusal witness that
  records the original stdin identity and proves it is restored after dispatch.
- For `session-relock-witness`, expose or use an existing production observation
  of live-session absence from inside the worker before it exits, and pair the
  positive close assertion with a gate that reds when the explicit relock is
  absent. Do not replace the real encrypted profile or runtime with a mock.

All recommendations are satisfied by the current fixture cleanup,
cleared-channel anti-tautology, repeated re-authenticated warm calls, and direct
stdin identity-restoration tests. No CRITICAL, HIGH, MEDIUM, or LOW finding
remains open.
