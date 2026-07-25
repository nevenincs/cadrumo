---
tags:
  - '#plan'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-25'
tier: L2
related:
  - '[[2026-07-15-cli-authority-verb-conformance-adr]]'
  - '[[2026-07-15-cli-authority-verb-conformance-research]]'
  - '[[2026-07-15-cli-authority-verb-conformance-reference]]'
  - '[[2026-07-16-cli-authority-verb-conformance-duplication-authority-audit]]'
  - '[[2026-07-17-cli-authority-verb-conformance-audit]]'
  - '[[2026-07-15-cli-authority-verb-conformance-plan]]'
  - '[[2026-07-17-auth-cert-recovery-custody-audit]]'
  - '[[2026-07-17-auth-cert-recovery-custody-adr]]'
---

# `auth-cert-recovery-custody` plan

### Phase `P01` - Authentication custody backend

Separate typed auth logout and reset operations with explicit provider or all scope and target-scoped cleanup. Landed.

- [x] `P01.S01` - Atomically replace broad auth clear across backend and live CLI contracts with typed target-scoped logout_operator_auth and reset_operator_auth, complete provider session coverage, safe secret and lock cleanup, distinct schemas and events, exact contract, risk, help and write metadata, four-locale help, and real workflow and command tests without a compatibility wrapper; `src/cadrumo/application/auth/_operator.py`.
- [x] `P01.S02` - Prove logout preserves provider and certificate-source configuration while clearing real sessions; `src/cadrumo/application/auth/tests/test_operator_storage_session.py`.
- [x] `P01.S03` - Prove reset removes provider state, sessions, locks, registrations, and secrets only for the explicit target; `src/cadrumo/application/auth/tests/test_operator.py`.
- [x] `P01.S04` - Prove provider and all-provider deletion leave unrelated bucket session files byte-identical; `src/cadrumo/application/auth/tests/test_sessions_storage_state_paths.py`.
- [x] `P01.S05` - Prove acquisition-lock cleanup is target scoped and repeatable with real lock files; `src/cadrumo/application/auth/tests/test_acquisition_lock.py`.

### Phase `P02` - Certificate credential custody backend

Selected-profile secure storage becomes the sole certificate-secret authority; the certificate-specific keyring backend is deleted. Landed.

- [x] `P02.S06` - Delete the certificate keyring backend, backend-kind selector, factory branch, exports, and certificate-specific keyring service and account code while retaining secure storage as the only certificate-secret backend and preserving independent master-key OS-keyring custody; `src/cadrumo/application/auth/_certificate_secret_backend.py`.
- [x] `P02.S07` - Make the active certificate credential resolver and named-source certificate check use only selected-profile secure storage with explicit fail-closed absence, and make ordinary certificate-secret set and remove crash-resumable through one secret-free durable intent carrying a stable operation id, event kind, timestamp, prior-presence state, and non-secret completion witness; `src/cadrumo/application/auth/_certificate_sources_operator.py`.
- [x] `P02.S08` - Route auth status, test, login, central session acquisition, live callers, state projection, and modelo provider construction through the active certificate credential resolver by centralizing exact certificate credential projection in the application provider factory; `src/cadrumo/application/auth/_certificate_sources.py`.
- [x] `P02.S09` - Make the certificate authenticator and adapter provider factory consume the resolved typed active certificate credential directly, eliminating their independent path and password projection from Settings; `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `P02.S10` - Prove certificate secrets set, resolve, and remove only through real secure storage, force real event-commit failure after set and remove, prove retry resumes the original operation and emits the original stable event exactly once, and prove no certificate keyring backend, selector, fallback, migration, probe, or parallel secret writer remains; `src/cadrumo/application/auth/tests/test_certificate_secret_backend.py`.
- [x] `P02.S11` - Prove register, select, check, status, test, and login consume the same resolved certificate bytes; `src/cadrumo/application/auth/tests/test_certificate_sources_check.py`.

### Phase `P03` - Passphrase and recovery custody backend

Passphrase change and recovery remain distinct typed authorities with file custody and secret-free envelopes. Landed.

- [x] `P03.S12` - Expose distinct recovery status, create, rotate, verify, and recover application operations; `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [x] `P03.S13` - Make recovery create refuse an existing enrollment and rotate require an existing enrollment; `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [x] `P03.S14` - Preserve the prior recovery envelope until a candidate mnemonic has been fully verified; `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`.
- [x] `P03.S15` - Restrict recovery to file custody and return typed refusals for keyring and unsecured custody; `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [x] `P03.S16` - Preserve the established recovery fingerprint across verification and recovery operations; `src/cadrumo/adapters/persistence/storage/master_key/_recovery_record.py`.
- [x] `P03.S17` - Prove create refusal, rotate preconditions, candidate verification, and old-envelope survival with real encrypted files; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery_facade.py`.
- [x] `P03.S18` - Prove mnemonic verification and recovery never serialize secret material; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py`.
- [x] `P03.S19` - Prove file-only custody and typed keyring or unsecured refusals across the custody matrix; `src/cadrumo/application/user_profile/tests/test_custody_store_matrix.py`.
- [x] `P03.S20` - Prove passphrase change preserves encrypted data and survives failed candidate confirmation; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py`.
- [x] `P03.S21` - Re-export only the explicit passphrase and recovery lifecycle operations; `src/cadrumo/adapters/persistence/storage/master_key/__init__.py`.
- [x] `P03.S47` - Emit non-secret bucket events for passphrase change and the recovery-code create, rotate, and recover mutations, degrading the trail to a logged no-op when profile storage is locked so it never gates the mutation; `src/cadrumo/application/user_profile/_custody.py`.

### Phase `P04` - Passphrase and recovery CLI door

Cut the passphrase and recovery command grammar over to the landed backend authorities with secure input and no mnemonic argv.

- [x] `P04.S22` - Replace config rekey with only config passphrase change and secure input handling; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [x] `P04.S23` - Replace recovery display and rotation spellings with recovery status, create, and rotate; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [x] `P04.S24` - Register only recovery verify and flat recover with secrets-stdin and no mnemonic argv; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [x] `P04.S25` - Write create and rotate candidates directly to the controlling terminal and require full no-echo retype before commit; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [x] `P04.S26` - Replace obsolete bootstrap exemptions with the exact accepted passphrase and recovery paths; `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`.
- [x] `P04.S27` - Prove passphrase change through a real encrypted vault; `src/cadrumo/entrypoints/cli/_config/tests/test_config.py`.
- [x] `P04.S28` - Prove recovery status, create, rotate, verify, and recover without serialized mnemonic material; `src/cadrumo/entrypoints/cli/tests/test_config_recovery_lifecycle.py`.
- [x] `P04.S29` - Prove passphrases, mnemonics, and secret-input values are absent from help and examples; `src/cadrumo/entrypoints/cli/tests/test_help_without_secrets.py`.
- [x] `P04.S30` - Prove secure TTY failures and strict bounded secrets-stdin JSON through localized CLI execution; `src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py`.
- [x] `P04.S31` - Align bootstrap and repair-policy inventories with the recovery family and flat recover exception; `src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py`.
- [x] `P04.S46` - Refuse in prompt_secret_no_echo when getpass cannot guarantee echo suppression, guarding the win32 sys.__stdin__ identity precondition, promoting GetPassWarning to a typed refusal, and catching OSError, proven by real-subprocess regressions; `src/cadrumo/entrypoints/cli/_config/_secure_input.py`.
- [x] `P04.S48` - Discriminate a real console from a bare character device before prompting, so a NUL or console-less stdin refuses instead of blocking forever in msvcrt.getwch, and apply the same precondition to the recovery-code terminal display; `src/cadrumo/entrypoints/cli/_config/_secure_input.py`.

### Phase `P05` - Certificate and auth CLI door

Cut the certificate and auth command grammar over to secure storage and remove backend selection and keyring spellings.

- [x] `P05.S32` - Remove certificate backend selection and key set, remove certificate secrets only by name through secure storage, and expose no compatibility alias or migration surface; `src/cadrumo/entrypoints/cli/_config/_certificate.py`.
- [x] `P05.S33` - Prove certificate secret set and remove against real secure storage, including command failure after the secret mutation but before event commit followed by an idempotent retry with one correctly classified event, and reject backend selection, keyring spellings, migration, fallback, and duplicate mutation paths; `src/cadrumo/entrypoints/cli/_config/tests/test_certificate.py`.
- [x] `P05.S34` - Require yes for auth reset while keeping auth status and auth test non-destructive; `src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py`.

### Phase `P06` - Contract migration for these families

Move payload schemas, write-policy tokens, locales, MCP mirrors, help and risk metadata, and generated documentation for the auth, certificate, and recovery families.

- [x] `P06.S35` - Remove certificate backend selectors from every payload and schema projection while preserving independent master-key keyring custody contracts; `src/cadrumo/entrypoints/cli/_config_payloads.py`.
- [x] `P06.S36` - Migrate the auth, certificate, and recovery help and risk metadata to the accepted grammar; `src/cadrumo/application/operator_surface/_help.py`.
- [x] `P06.S37` - Migrate the four locale catalogues for the auth, certificate, and recovery families through the locales CLI; `src/cadrumo/locales/en.yml`.
- [x] `P06.S38` - Re-arm the MCP mirror for the accepted auth, certificate, and recovery verbs; `src/cadrumo/agent/`.
- [x] `P06.S39` - Regenerate the CLI reference and operator how-to pages for the auth, certificate, and recovery families from the frozen live surface; `docs/how-to/authenticate-with-aeat.md`.
- [x] `P06.S40` - Prove the removed auth, certificate, and recovery spellings are absent from every source and generated surface; `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`.

### Phase `P07` - Secret-store DI seam removal

Remove the module-global test-double seam from the production secret-store factory: thread constructor dependency-injection into the certificate-secret backend, certificate-sources check, and materialisation helpers, delete the override setter and its global, and add a recurrence gate so the seam cannot return.

- [x] `P07.S41` - Thread constructor secret_store: SecretStore|None=None dependency-injection through the secret-store factory, certificate-secret backend, certificate-sources check, and materialisation helpers; `delete override_secret_store, the module-global _override_store, its if-override branch, and both blob_store and storage __init__ facade exports; migrate the four consuming tests to pass an EphemeralMasterKeyProvider-backed SecretStore explicitly, in one atomic relocation commit including apidocs scaffold; `src/cadrumo/adapters/persistence/storage/blob_store/_materialisation.py`.
- [x] `P07.S42` - Add an AST recurrence gate, patterned on test_wizard_prompter_singularity.py, that bans module-global _override_* factory state and public override_* setters in production, exempting only the sanctioned core.config.override_settings; `src/cadrumo/adapters/persistence/storage/blob_store/tests/test_materialisation.py`.
- [x] `P07.S43` - Sweep the storage facade and generated API docs for the removed override_secret_store export and update the import-hygiene baseline after the seam removal; `src/cadrumo/adapters/persistence/storage/__init__.py`.

### Phase `P08` - Certificate secret input hardening (deferred to P04 door)

The cert-secret door safety review returned PASS with one Low hardening item: certificate secret set accepts the PKCS12 passphrase as an argv value, which lands the secret in the process table and shell history even though the hidden-prompt and stdin default is safe. This phase removes the argv affordance, deferred until the operator P04 passphrase door commits so it reuses that door bounded-stdin no-echo secret-input infrastructure rather than building a parallel authority.

- [x] `P08.S44` - DEFERRED until the operator P04 passphrase door commits: make certificate secret set reject the passphrase as an argv value and read it only via the hidden prompt or bounded stdin, reusing the P04 door _secure_input.py bounded-stdin no-echo infrastructure rather than building a parallel secret-input authority, gated on a test proving the passphrase cannot be supplied as an argv value and is read only through hidden prompt or bounded stdin; `src/cadrumo/entrypoints/cli/_config/_certificate.py`.
- [x] `P08.S45` - Perform and persist the independent safety review of the P04 passphrase and recovery CLI door that the close honesty review found was never carried out, covering secure TTY handling, no-echo retype, secrets-stdin bounds, and mnemonic absence from argv, envelopes, logs and help, with the review persisted as a vault audit and every item it surfaces tracked as a Step or formally deferred; `.vault/audit`.
- [x] `P08.S49` - Convert recovery-key, mnemonic, unwrapped master-key, and enrollment-time DEK material from immutable bytes and str to wipeable mutable buffers so the substrate zeroise primitive can reach them, closing the plaintext-DEK exposure window that the P04 door safety review found is structurally wider here than on the BucketSession steady-state path because it opens on every recovery mint, unwrap, and passphrase change, deferred by that review as a pre-existing disclosed project-wide Python immutability limitation rather than a new regression, and tracked here so a later pass over this surface cannot re-introduce it as a false already-covered assumption; `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`.
- [x] `P08.S50` - Make the recovery-enrollment manifest flag write atomic with the verified envelope install, or reconcile the flag from the envelope on read, so a process kill between the two cannot leave recovery_enrolled reading false while a genuinely enrolled envelope exists on disk, deferred by the P04 door safety review as cosmetic because recovery status and verify both read the envelope file directly rather than the manifest flag, whose only untraced exposure is wherever it is consumed as a UI hint rather than a security-relevant gate, and tracked here so a later pass over this surface cannot re-introduce it as a false already-covered assumption; `src/cadrumo/application/user_profile/_custody.py`.
- [x] `P08.S51` - Thread an explicit no-echo secure-input callback into the recovery create and rotate enrollment path so it stops prompting through bare getpass, closing the P04 door safety review HIGH finding that a console-less host blocks past 45 seconds in the very hang the real-console precondition exists to prevent and that a rebound stdin enters the echoing fallback with GetPassWarning swallowed, gated on a regression that drives the verb itself and fails on timeout rather than exercising the helper in isolation; `src/cadrumo/application/user_profile/_custody.py`.
- [x] `P08.S52` - Reject duplicate keys in the secrets-stdin JSON payload before strict validation runs, because json.loads collapses them to the last value before extra forbid can observe the collision, allowing silent custody drift on the automation channel; `src/cadrumo/entrypoints/cli/_config/_secure_input.py`.
- [x] `P08.S53` - Decide and document which channels may supply the secret-store passphrase, reconciling the undeclared CADRUMO_SECRET_PASSPHRASE environment channel that is consulted first against the exactly-two-channels claim the module docstring makes, as a follow-on ADR; `src/cadrumo/adapters/persistence/storage/master_key/_master_key_io.py`.
- [x] `P08.S54` - Re-check the create-mode already-enrolled refusal at install time, closing the window between the precondition check and the atomic install that stays open across an unbounded 24-word operator retype; `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [x] `P08.S55` - Cover the 8192-byte secrets-stdin size cap with an oversize-input regression, the one bound the existing bounds tests never exercise while covering malformed input, wrong fields, and non-object payloads; `src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py`.
- [x] `P08.S56` - Record a formal decision on whether the custody verbs need a failed-attempt throttle, documenting the same-user offline-attack equivalence that makes the present absence defensible so the gap is a declared position rather than an oversight; `src/cadrumo/application/user_profile/_login_session.py`.

## Description

Consolidate authentication, certificate, and recovery custody onto single typed authorities and cut their command grammar over to match. The decision record keeps these families distinct on purpose: profile logout closes local profile resources, auth logout removes scoped AEAT sessions while preserving provider and certificate configuration, auth reset destructively clears scoped provider configuration, sessions, locks, certificate registrations, and bound secrets, passphrase change rotates access to the existing vault, and recovery creates, rotates, verifies, or consumes an independent recovery capability. This plan preserves those distinctions; it does not merge them.

The backend authorities for all three families have landed. Authentication custody replaced the broad clear with typed target-scoped logout and reset operations carrying complete provider session coverage, safe secret and lock cleanup, and distinct schemas and events. Certificate custody deleted the certificate-specific keyring backend, selector, factory branch, and exports, leaving selected-profile secure storage as the sole certificate-secret authority while independent master-key operating-system keyring custody remains untouched; ordinary set and remove are crash-resumable through one secret-free durable intent. Recovery custody exposed distinct status, create, rotate, verify, and recover operations restricted to file custody with secret-free envelopes and preserved prior envelopes across verification.

What remains is the operator-facing half: the passphrase, recovery, certificate, and auth CLI doors, and the per-family contract migration. The real atomicity invariant is per family, not per campaign: a removed spelling and its payload schema, write-policy token, four locales, Model Context Protocol mirror, help and risk metadata, error suggestions, and regenerated documentation move in one change for that family. The logout family already proved a family can land independently without breaking the surface.

The twenty-one checked steps below carry their execution evidence under the originating campaign feature stem rather than this one, because the successor plans inherit the campaign decision record instead of minting duplicates. The rescope record documents this explicitly and the archive preserves those records. Do not re-execute them.

## Steps

## Parallelization

The three backend phases have landed and are not re-executed. The passphrase and recovery CLI door and the certificate and auth CLI door share no files and may run in parallel; each depends only on its own landed backend phase. The contract-migration phase runs after both doors are cut, because it regenerates documentation from the frozen live surface and asserts the removed spellings are absent.

Two surfaces are shared with peer campaigns and must be serialized rather than co-edited: the config payload module and the four locale catalogues. Confirm ownership before editing either, and route all locale work through the locales CLI rather than hand-editing the catalogues.

## Verification

The auth family conformance suite passes: logout preserves provider and certificate-source configuration while clearing real sessions, reset removes provider state, sessions, locks, registrations, and secrets only for the explicit target, deletion leaves unrelated bucket session files byte-identical, and acquisition-lock cleanup is target-scoped and repeatable against real lock files.

The certificate family conformance suite passes: set, resolve, and remove operate only through real secure storage; a forced event-commit failure after the secret mutation is followed by an idempotent retry emitting the original stable event exactly once with its set versus rotated classification preserved; and no certificate keyring backend, selector, fallback, migration, probe, or parallel secret writer remains.

The recovery family conformance suite passes: create refuses an existing enrollment, rotate requires one, the prior envelope survives until a candidate mnemonic is fully verified, custody is file-only with typed refusals elsewhere, and no operation serializes secret material. Passphrases, mnemonics, and secret-input values are absent from help and examples.

The removed spellings for these three families are proven absent from every source and generated surface, and the standing root grammar, documented-command, JSON schema, locale parity, and self-referential string gates run green after each family lands.

A fresh-context honesty review runs against this plan's closure summary before the plan is declared complete.
