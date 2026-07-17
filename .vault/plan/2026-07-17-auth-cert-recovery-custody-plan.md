---
tags:
  - '#plan'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
tier: L2
related:
  - '[[2026-07-15-cli-authority-verb-conformance-adr]]'
  - '[[2026-07-16-cli-authority-verb-conformance-duplication-authority-audit]]'
  - '[[2026-07-17-cli-authority-verb-conformance-audit]]'
  - '[[2026-07-15-cli-authority-verb-conformance-plan]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace auth-cert-recovery-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries the AUTHORIZING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution Record artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorizing documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `auth-cert-recovery-custody` plan

### Phase `P01` - Authentication custody backend

Separate typed auth logout and reset operations with explicit provider or all scope and target-scoped cleanup. Landed.


<!-- One-line headline summary plan. -->

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

### Phase `P04` - Passphrase and recovery CLI door

Cut the passphrase and recovery command grammar over to the landed backend authorities with secure input and no mnemonic argv.

- [ ] `P04.S22` - Replace config rekey with only config passphrase change and secure input handling; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [ ] `P04.S23` - Replace recovery display and rotation spellings with recovery status, create, and rotate; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [ ] `P04.S24` - Register only recovery verify and flat recover with secrets-stdin and no mnemonic argv; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [ ] `P04.S25` - Write create and rotate candidates directly to the controlling terminal and require full no-echo retype before commit; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [ ] `P04.S26` - Replace obsolete bootstrap exemptions with the exact accepted passphrase and recovery paths; `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`.
- [ ] `P04.S27` - Prove passphrase change through a real encrypted vault; `src/cadrumo/entrypoints/cli/_config/tests/test_config.py`.
- [ ] `P04.S28` - Prove recovery status, create, rotate, verify, and recover without serialized mnemonic material; `src/cadrumo/entrypoints/cli/tests/test_config_recovery_lifecycle.py`.
- [ ] `P04.S29` - Prove passphrases, mnemonics, and secret-input values are absent from help and examples; `src/cadrumo/entrypoints/cli/tests/test_help_without_secrets.py`.
- [ ] `P04.S30` - Prove secure TTY failures and strict bounded secrets-stdin JSON through localized CLI execution; `src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py`.
- [ ] `P04.S31` - Align bootstrap and repair-policy inventories with the recovery family and flat recover exception; `src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py`.

### Phase `P05` - Certificate and auth CLI door

Cut the certificate and auth command grammar over to secure storage and remove backend selection and keyring spellings.

- [ ] `P05.S32` - Remove certificate backend selection and key set, remove certificate secrets only by name through secure storage, and expose no compatibility alias or migration surface; `src/cadrumo/entrypoints/cli/_config/_certificate.py`.
- [ ] `P05.S33` - Prove certificate secret set and remove against real secure storage, including command failure after the secret mutation but before event commit followed by an idempotent retry with one correctly classified event, and reject backend selection, keyring spellings, migration, fallback, and duplicate mutation paths; `src/cadrumo/entrypoints/cli/_config/tests/test_certificate.py`.
- [ ] `P05.S34` - Require yes for auth reset while keeping auth status and auth test non-destructive; `src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py`.

### Phase `P06` - Contract migration for these families

Move payload schemas, write-policy tokens, locales, MCP mirrors, help and risk metadata, and generated documentation for the auth, certificate, and recovery families.

- [ ] `P06.S35` - Remove certificate backend selectors from every payload and schema projection while preserving independent master-key keyring custody contracts; `src/cadrumo/entrypoints/cli/_config_payloads.py`.
- [ ] `P06.S36` - Migrate the auth, certificate, and recovery help and risk metadata to the accepted grammar; `src/cadrumo/application/operator_surface/_help.py`.
- [ ] `P06.S37` - Migrate the four locale catalogues for the auth, certificate, and recovery families through the locales CLI; `src/cadrumo/locales/en.yml`.
- [ ] `P06.S38` - Re-arm the MCP mirror for the accepted auth, certificate, and recovery verbs; `src/cadrumo/agent/`.
- [ ] `P06.S39` - Regenerate the CLI reference and operator how-to pages for the auth, certificate, and recovery families from the frozen live surface; `docs/how-to/authenticate-with-aeat.md`.
- [ ] `P06.S40` - Prove the removed auth, certificate, and recovery spellings are absent from every source and generated surface; `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`.

## Description

Consolidate authentication, certificate, and recovery custody onto single typed authorities and cut their command grammar over to match. The decision record keeps these families distinct on purpose: profile logout closes local profile resources, auth logout removes scoped AEAT sessions while preserving provider and certificate configuration, auth reset destructively clears scoped provider configuration, sessions, locks, certificate registrations, and bound secrets, passphrase change rotates access to the existing vault, and recovery creates, rotates, verifies, or consumes an independent recovery capability. This plan preserves those distinctions; it does not merge them.

The backend authorities for all three families have landed. Authentication custody replaced the broad clear with typed target-scoped logout and reset operations carrying complete provider session coverage, safe secret and lock cleanup, and distinct schemas and events. Certificate custody deleted the certificate-specific keyring backend, selector, factory branch, and exports, leaving selected-profile secure storage as the sole certificate-secret authority while independent master-key operating-system keyring custody remains untouched; ordinary set and remove are crash-resumable through one secret-free durable intent. Recovery custody exposed distinct status, create, rotate, verify, and recover operations restricted to file custody with secret-free envelopes and preserved prior envelopes across verification.

What remains is the operator-facing half: the passphrase, recovery, certificate, and auth CLI doors, and the per-family contract migration. The real atomicity invariant is per family, not per campaign: a removed spelling and its payload schema, write-policy token, four locales, Model Context Protocol mirror, help and risk metadata, error suggestions, and regenerated documentation move in one change for that family. The logout family already proved a family can land independently without breaking the surface.

The twenty-one checked steps below carry their execution evidence under the originating campaign feature stem rather than this one, because the successor plans inherit the campaign decision record instead of minting duplicates. The rescope record documents this explicitly and the archive preserves those records. Do not re-execute them.

## Steps

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorizing documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

The three backend phases have landed and are not re-executed. The passphrase and recovery CLI door and the certificate and auth CLI door share no files and may run in parallel; each depends only on its own landed backend phase. The contract-migration phase runs after both doors are cut, because it regenerates documentation from the frozen live surface and asserts the removed spellings are absent.

Two surfaces are shared with peer campaigns and must be serialized rather than co-edited: the config payload module and the four locale catalogues. Confirm ownership before editing either, and route all locale work through the locales CLI rather than hand-editing the catalogues.

## Verification

The auth family conformance suite passes: logout preserves provider and certificate-source configuration while clearing real sessions, reset removes provider state, sessions, locks, registrations, and secrets only for the explicit target, deletion leaves unrelated bucket session files byte-identical, and acquisition-lock cleanup is target-scoped and repeatable against real lock files.

The certificate family conformance suite passes: set, resolve, and remove operate only through real secure storage; a forced event-commit failure after the secret mutation is followed by an idempotent retry emitting the original stable event exactly once with its set versus rotated classification preserved; and no certificate keyring backend, selector, fallback, migration, probe, or parallel secret writer remains.

The recovery family conformance suite passes: create refuses an existing enrollment, rotate requires one, the prior envelope survives until a candidate mnemonic is fully verified, custody is file-only with typed refusals elsewhere, and no operation serializes secret material. Passphrases, mnemonics, and secret-input values are absent from help and examples.

The removed spellings for these three families are proven absent from every source and generated surface, and the standing root grammar, documented-command, JSON schema, locale parity, and self-referential string gates run green after each family lands.

A fresh-context honesty review runs against this plan's closure summary before the plan is declared complete.

