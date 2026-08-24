---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:cede6537f8884dad900f32fe185a1fbd5bb647ae7acad45b2b7db204b107349e'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# `profile-password-custody` audit: `S206 recovery parity review`

## Scope

Reviewed the S206 recovery-parity implementation against the accepted per-profile custody, recovery-mnemonic presentation, CLI action-envelope, and machine-secret decisions. The review covered only the recovery-related changes in `_scripted_registration.py`, `_profile_command_specs.py`, `_manager_frontend.py`, the TUI registration and recovery-word screens and their tests, the four CLI catalogues, and `protect-data-access.md`; unrelated password-policy, TUI invocation-policy, registry, and peer work in the shared worktree was excluded. The review inspected confidentiality, exact possession verification, zeroisation reachability, descriptor preflight and platform behavior, failure atomicity, blocking/thread behavior, command-schema truth, and test adequacy. A targeted integration run collected twenty tests but was interrupted after more than three minutes with only its first test complete, so it supplies no green closeout evidence.

## Findings

### tui-possession-proof | high | The full-screen lane enrolls recovery without exact possession verification

`RecoveryWordsScreen` renders the mnemonic and treats pressing `btn-confirm-words` as proof; it has no secret-entry control and never compares a reproduced sequence. `RegistrationApp._confirm_recovery_possession` releases the pre-publication callback solely from that button. An operator can therefore confirm without possessing any words and the capsule is published as recovery-enrolled. This contradicts the accepted requirement that possession be verified explicitly before enrollment and the updated operator guide's claim that the terminal surface requires re-entry. The TUI tests reinforce the defect by asserting button confirmation rather than exact sequence equality, and include no wrong-sequence refusal.

### windows-recovery-descriptors | high | The headless recovery lane has no Windows inherited-handle implementation or proof

The new handoff uses `os.write` on a caller-supplied numeric descriptor and the proof uses the ordinary numeric-fd reader. The accepted machine-secret decision states that Windows needs an allowlisted inherited HANDLE converted by the bootstrap wrapper through `msvcrt.open_osfhandle`, and explicitly forbids claiming direct CRT-fd inheritance parity. The recovery options are not enrolled as command-spec secret channels and no bootstrap integration or real subprocess inherited-handle test exists. The only tests use `os.pipe()` and invoke the CLI in-process, so they cannot prove either POSIX inheritance or Windows HANDLE conversion. As written, the guide's platform-neutral headless instructions promise a lane that is not established on Windows.

### tui-handover-wait | medium | An unbounded cross-thread wait can deadlock registration shutdown

`RegistrationApp._confirm_recovery_possession` schedules `_show` with `call_from_thread` and then calls `Event.wait()` with no timeout or application-shutdown predicate. The event is set only by the recovery screen's confirm/cancel callbacks. If shutdown begins before `_show` runs, `push_screen` fails, the message loop stops before unmount dispatch, or the worker is cancelled while the modal is pending, the registration worker can remain blocked forever; worker teardown can then wait on the same worker. No test closes the app during the handoff, forces `push_screen` failure, or proves worker termination and pre-publication rollback.

### recovery-command-contract | medium | Discovery and tests omit the recovery descriptor contract and refusal matrix

The generated `config.profile.create` schema exposes `recovery_handoff_fd` and `recovery_verification_fd` only as optional integer parameters. It does not project that they are a required pair, their write/read directions, strict one-object shape, 8 KiB bound, descriptor closure, reserved 0/1/2 rule, mutual inequality, or collision with `secrets_fd`. Handler-local preflight therefore duplicates command semantics outside the command-schema authority. The added tests assert only option presence, one in-process success, missing-both refusal, and wrong phrase. They do not exercise one-sided pairs, negative or reserved descriptors, same/cross-channel collisions before reads, unwritable/unreadable descriptors, malformed/duplicate/missing/extra/invalid-UTF-8/oversize proof payloads, closure on every refusal, or real subprocess behavior. This is insufficient for the accepted descriptor contract and leaves failure atomicity largely unproved.

## Recommendations

- Replace the TUI confirmation button as possession proof with a no-echo exact-sequence re-entry step and add correct, wrong, malformed, cancel, and secret-free rendering tests before allowing publication.
- Define an authoritative recovery-handoff descriptor capability in the command schema, including direction, pair/bounds/collision semantics, and a Windows HANDLE bootstrap path; make the operator guide platform-specific until real Windows and POSIX subprocess matrices pass.
- Replace the unbounded modal `Event.wait()` protocol with a lifecycle-aware, cancellation-safe synchronization path that always releases on shutdown or screen-push failure, and test those exits with no committed capsule.
- Add a real subprocess refusal matrix covering preflight-before-read, all parser failures, descriptor closure, confidentiality, rollback, POSIX inheritance, and Windows inherited-HANDLE conversion. Schema tests must assert the complete machine-discoverable contract rather than option names alone.

## Resolution review

Re-reviewed the current remediation against every HIGH and MEDIUM finding. Focused integration checks passed: exact wrong-sequence TUI refusal, shutdown release without publication, the real Windows base-interpreter inherited-HANDLE creation path, and the base-interpreter invariant passed as four tests in 11.46 seconds. The schema/preflight/closure selection passed seven cases in 3.76 seconds. The POSIX test is correctly platform-gated on this Windows host and was inspected to confirm a real interpreter subprocess with `pass_fds`, two anonymous pipes, bounded handoff/proof exchange, and successful profile creation; it was not executable on this host.

### tui-possession-proof-resolution | low | Resolved by masked exact-sequence re-entry before publication

`RecoveryWordsScreen` now owns a password-masked verification input, compares its complete value byte-for-semantic-string against the displayed canonical mnemonic, clears the widget value, wipes the enrollment container, and refuses without publishing on mismatch. Dedicated real-registration tests prove both exact success and wrong-sequence non-publication. The previous HIGH finding is resolved.

### windows-recovery-descriptors-resolution | low | Resolved by the inherited-HANDLE bootstrap and real Windows process proof

The Windows bootstrap now accepts distinct recovery handoff and verification HANDLEs, starts the resolved base CPython interpreter rather than a virtual-environment launcher, converts only the allowlisted inherited HANDLEs through `msvcrt.open_osfhandle` with the correct write/read access, and injects the ordinary recovery descriptor options. The focused Windows test passed through a real process, real anonymous pipes, real recovery enrollment, and the direct base interpreter. A complementary inspected POSIX test uses real `pass_fds`. The previous HIGH finding is resolved.

### tui-handover-wait-resolution | low | Resolved by lifecycle release and a bounded final guard

Registration now tracks pending handoff events, releases them from application unmount, catches scheduling failure through the surrounding `try/finally`, and bounds the wait to thirty seconds as a final message-loop guard. The real shutdown test terminates the worker with no committed capsule and passed. The previous MEDIUM finding is resolved.

### recovery-command-contract-resolution | medium | Refusal coverage is repaired but the contract still bypasses command-spec authority

Runtime coverage now exercises malformed, repeated, extra, missing, invalid-UTF-8, and oversized proofs; one-sided, negative, reserved, and equal descriptor refusal; unwritable handoff closure; exact mismatch; and real Windows/POSIX process transport. Discovery now reports directions, pairing, strict-object shape, bound, closure, reservations, collisions, and the Windows bootstrap. However, `RecoveryHandoffContract` is instantiated in `build_verb_input_schemas` through `if key == "config.profile.create"` with all semantics authored as projector defaults, while `_profile_command_specs.py` still declares the two options only as ordinary integers. The supposedly authoritative command graph therefore cannot validate or project this capability itself, and a rename, removal, or semantic change can drift from the hard-coded projection without the spec object failing. The previous MEDIUM finding remains open in this narrowed architectural form.

## Updated recommendations

- Move the paired recovery-handoff capability and its complete value-free semantics into the `CommandSpec` authority, then derive `RecoveryHandoffContract` from that declaration with anti-tautology tests that mutate or remove the spec and observe discovery change or refusal.
- Retain the now-green exact-possession, lifecycle-cancellation, descriptor-refusal, Windows base-interpreter HANDLE, and POSIX `pass_fds` tests as mandatory closure gates.

## Final command-authority review

The final narrow review confirmed that `RecoveryHandoffSpec` is now a typed field of `CommandSpec`, the profile-create leaf authors the complete handoff declaration, and `build_verb_input_schemas` generically projects the selected command graph's declaration. There is no remaining profile-create identity branch and `RecoveryHandoffContract` carries no synthesized semantic defaults. The mutation test proves a changed graph bound flows into discovery, and the missing/stale declaration tests prove those two drift modes refuse. The three focused tests passed in 2.25 seconds.

### recovery-command-contract-final | medium | Runtime validation still accepts directionally invalid declarations

The ownership/projection half of the prior finding is resolved, but validation is not yet closed over bad declarations. `RecoveryHandoffSpec.__post_init__` never checks that `handoff_direction` equals `write` or `verification_direction` equals `read`; `Literal` annotations are not enforced by a dataclass at runtime. A direct construction with the two values reversed succeeds and the generic projector would faithfully advertise the reversed, unusable protocol. `CommandSpec.__post_init__` also builds its descriptor-option map only from `OptionSpec` objects but does not require all referenced parameters to appear in that map, so an integer positional argument bearing a referenced name can pass the missing-reference and integer-option checks. The focused tests cover changed metadata plus missing and stale names, but no reversed direction or non-option declaration. A malformed graph can therefore validate and publish false discovery, so one MEDIUM remains.

## Final recommendation

- Enforce the two closed direction values at runtime, require every handoff, verification, and collision reference to resolve to an integer `OptionSpec`, and add negative construction tests for reversed/unknown directions and argument/non-integer references before closing S206.

## Final validation resolution

### recovery-command-contract-validation | low | Resolved by closed runtime direction and option-reference guards

`RecoveryHandoffSpec.__post_init__` now refuses every direction pair except handoff `write` followed by verification `read`. `CommandSpec.__post_init__` now requires the complete referenced set to equal the resolved `OptionSpec` key set before applying the integer-type check, so an `ArgumentSpec` substitution cannot pass by omission. Focused verification exercised the valid graph and discovery projection, reversed handoff direction, reversed verification direction, an unknown direction, and an integer positional argument replacing the descriptor option; all five tests passed in 2.20 seconds. The last MEDIUM finding is resolved. No HIGH or MEDIUM finding remains in the S206 recovery-parity scope.

## Post-gate regression-test delta

The two machine-secret profile-create cases still independently prove the original stdin and inherited-descriptor passphrase channels through a real subprocess. Mandatory recovery is driven through separate handoff and verification pipes/HANDLEs without replacing the credential channel under test; the fd case retains the subprocess closure canary and both retain real successful-profile assertions. The composed TUI case now waits for the recovery screen and its mounted word widget before supplying the exact masked re-entry, then still joins the worker and proves the committed profile, so the adaptation removes a mount race without weakening the original creation property. The focused selection passed seven cases in 89.54 seconds. These are test-only adaptations and introduce no production behavior. No new finding arose, and no HIGH or MEDIUM remains.
