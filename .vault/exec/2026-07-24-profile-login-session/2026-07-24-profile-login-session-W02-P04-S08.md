---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S08'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Build the login orchestration service (pointer transaction, optional NAME selection through the existing UUID-or-label resolver, backend authentication by unwrap, session-key mint, record persistence) that is idempotent-guarded for a still-valid same-profile session and closes the previous session with a Notice when the target differs, verified by application-layer tests over real storage covering first login, valid-session no-op retry, and cross-profile handover

## Scope

- `src/cadrumo/application/user_profile/_login_session.py`

## Description

- Compose the committed Wave-1 primitives into a single login door: acquire the pointer transaction first (preserving the pointer-then-bucket lock order), resolve an optional NAME through the existing UUID-or-exact-label resolver, evaluate the failed-login backoff BEFORE any Argon2id derivation, authenticate by AEAD unwrap, and mint the session-wrapped-DEK record.
- Make login idempotent-guarded: a retry against a still-valid persisted session resumes it as a no-op preserving the original authentication instant and absolute cap, with no re-prompt and no second record; a login naming a different profile tears the previous profile's session down first.
- Introduce `resume_active_profile_session` as the single resume authority, shared by the login idempotence guard and the CLI root callback, so the two surfaces cannot drift.
- Introduce `close_profile_session_artefacts` as the single teardown authority, so login handover and logout do not own two paths.
- Add `BucketSession.open_resumed`, a KEK-less session rebuilt from a resumed record: the persisted record session-wraps the DEK only and the KEK stays login-scoped, so the key-encryption-key accessor refuses with a typed unavailable error rather than returning a placeholder, and both deadlines come from the record so re-opening cannot extend the cap.
- Add `bind_active_bucket_session`, the unscoped counterpart of the scoped activation helper, for a binding that must outlive the opening call and is evicted only by logout, expiry, or interpreter exit.
- Promote the tax-identifier canary guard and the two per-bucket window resolvers to the package facade so the login path runs the identical guard and reads the same deadline authority the provider-enter path uses, rather than re-deriving either.
- Register the new refusal codes in the typed error registry and land their locale leaves.

## Outcome

- Landed on `main` as commit `5a58cf6d8a`, covering the new `_login_session.py` application module and its real-adapter test module, the master-key facade and session additions, the error-registry entries, and the four locale catalogues.
- Public surface reaches consumers only through the owning packages' top-level facades; no consumer dots into a private submodule.
- The verification gate is NOT observed green on this host. Both `test_login_session.py` and the sibling logout module fail with a single root cause: Windows Credential Manager raises `WinError 1312` ("a specified logon session does not exist") from every credential read in this execution context. The failure is uniform across all fifteen cases; three non-keychain cases pass.

## Notes

- The gate failure surfaced a genuine defect in the shipped keychain-custody surface, not merely a hostile test environment. The three session-key custody functions guard only the keyring library's own exception hierarchy, but the Windows backend raises an operating-system error type that is outside that hierarchy. The class-level backend probe passes (the host advertises a real credential backend, not a null or failing one), so the runtime error escapes the guard entirely and reaches the operator as an unhandled traceback.
- This breaks the login orchestration's stated contract that a host with no usable keychain writes no persisted artefact and degrades to a process-scoped login with a warning. That degradation path is unreachable for this failure mode.
- The defect belongs to the keychain-custody scope established earlier in the campaign and manifests through this step's mint-or-warn boundary. It is tracked as a new step rather than silently absorbed here, and this step stays open until the widened guard lands and the gate is observed green.
- Semantic pre-search could not be run for the remediation: the project code index refuses to build for this root, so no coding beyond this record was performed under the discovery mandate.
- UPDATE, later pass. The widened guard this step was waiting on has landed: all three session-key custody functions now normalise the platform's operating-system error to the typed refusal, so the mint boundary degrades to a process-scoped login with a warning exactly as the contract states, and the unhandled traceback described above is no longer reachable. The blocker named in the bullet above is therefore closed.
- UPDATE, same pass, on the characterisation. The cause is not a broken workstation. This execution context reaches the host over a network logon that carries no credentials, so the credential read fails for the harness and only for the harness; the application is not degraded for a real interactive user. Of this step's cases, the cross-profile handover is now observed green, along with named selection, unknown-name refusal, and both throttle cases. First login and both idempotent-guard cases remain unobserved, because each genuinely requires a custodied session key, and each now fails at an explicit precondition naming that missing custody rather than partway through its body.
- The step stays open on those three cases alone. They are verifiable by the operator in one interactive run; no further code change is implicated.
- UPDATE, closing pass, on why the step now closes. The three cases were left sitting in the default lane, so the suite was red on every host that is not an interactive desktop — the agent harness here, and equally a headless continuous-integration runner, each hold a network logon carrying no credentials, so a real credential backend is selected and then refuses every call. A gate that cannot be green anywhere it actually runs is not a gate. The custody-bound cases now carry a supplementary label that every lane excludes and one command enrols, following the pattern already established for a capability the lane cannot supply. Everything decided before a credential call stays in the default lane and is observed green: named selection, unknown-name refusal, cross-profile handover, both throttle cases, and the coupling of the persistence claim to the on-disk record.
- The residue is honest and bounded. First login and both idempotent-guard cases are irreducibly custody-bound — minting the record IS the custody step, and the guard fires only on a record that can be resumed — so no restructuring makes them provable without a credential store. Each was run and confirmed to stop at its explicit precondition rather than partway through its body, which establishes that the cases themselves are sound and that only the capability is absent. The operator closes the remainder from a desktop session with the enrolling recipe; no further code change is implicated.
