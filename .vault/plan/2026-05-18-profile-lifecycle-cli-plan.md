---
tags:
  - '#plan'
  - '#profile-lifecycle-cli'
date: '2026-05-18'
tier: L2
related:
  - '[[2026-05-18-profile-lifecycle-cli-adr]]'
  - '[[2026-05-17-profile-lifecycle-cli-cascade-closure-research]]'
  - '[[2026-05-16-profile-lifecycle-cli-adr]]'
  - '[[2026-05-16-profile-lifecycle-cli-plan]]'
  - '[[2026-05-14-profile-bucket-lifecycle-adr]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
  - '[[2026-05-17-per-bucket-sqlite-cascade-audit]]'
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

# `profile-lifecycle-cli` cascade closure plan

### Phase `P01` - crypto cutover + NIST passphrase floor

Replace `MasterKeyProvider` ClassVar caches with `ContextVar`-scoped
`BucketSession` access; introduce `get_active_master_key()` free
function and `activate_session()` contextmanager; wire the CLI root
to enter the with-block; enforce NIST 8-char passphrase floor at the
verifier.

- [x] `P01.S01` - add `_active_session.py` with `ContextVar`, `activate_session()`, `get_active_master_key()`; `src/aeat/adapters/persistence/storage/master_key/_active_session.py`.
- [x] `P01.S02` - add typed `NoActiveBucketSessionError` raised when `get_active_master_key()` is called outside a session block; `src/aeat/adapters/persistence/storage/master_key/_active_session.py`.
- [ ] `P01.S03` - replace `_resolve_master_key()` body with one-line delegation to `get_active_master_key()`; `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py`.
- [ ] `P01.S04` - delete `_resolve_master_key_provider()`, `_provider_override`, `_provider_lock`, `override_master_key_provider`; `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py`.
- [ ] `P01.S05` - delete `KeyringMasterKeyProvider._cache` ClassVar; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `P01.S06` - delete `KeyringMasterKeyProvider._lock` ClassVar; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `P01.S07` - delete `FileFallbackMasterKeyProvider._cached_passphrase` and `_cached_master_key` ClassVars; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `P01.S08` - replace `_purge_caches_at_exit` atexit hook with `_close_active_session_at_exit`; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `P01.S09` - add NIST `PassphraseTooShortError` raised when passphrase length is below 8 characters; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `P01.S10` - enforce 8-character minimum in `FileFallbackMasterKeyProvider._resolve_passphrase`; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `P01.S11` - migrate test fixtures from literal `"x"` to `secrets.token_hex(8)`; `src/aeat/adapters/persistence/storage/master_key/_test_master_key.py`.
- [ ] `P01.S12` - mount `activate_session(BucketSession.open(...))` on the CLI root callback via `ctx.with_resource(...)`; `src/aeat/entrypoints/cli/__init__.py`.
- [ ] `P01.S13` - mount the `activate_session(...)` wiring on the diagnostics entrypoint root; `src/aeat/diagnostics/__main__.py`.
- [ ] `P01.S14` - narrow `EphemeralMasterKeyProvider` fixture to a `BucketSession` factory mint helper; `src/aeat/tests/conftest.py`.
- [ ] `P01.S15` - rewrite call sites of `override_master_key_provider` to `with activate_session(...)`; `src/aeat/adapters/persistence/storage/master_key/_test_master_key.py`.
- [ ] `P01.S16` - add AST-guard test asserting zero ClassVar state on master-key providers; `src/aeat/adapters/persistence/storage/master_key/_test_no_classvar_state.py`.
- [ ] `P01.S17` - add roundtrip test exercising column encrypt + decrypt inside `activate_session(...)`; `src/aeat/adapters/persistence/storage/crypto/_test_active_session_roundtrip.py`.

### Phase `P02` - engine cutover + WorkflowState.profiles retirement

`Settings.aeat_database_url` becomes a computed property resolving
through the active-profile precedence chain. `WorkflowState.profiles`
retires; bucket enumeration moves to filesystem manifest scan. The
shared `var/aeat.db` legacy default disappears entirely.

- [ ] `P02.S18` - convert `Settings.aeat_database_url` from a static field to a computed property resolving the active-profile pointer; `src/aeat/core/config.py`.
- [ ] `P02.S19` - remove the `var/aeat.db` default fallback; `raise `NoActiveProfileError` if no active profile resolves; `src/aeat/core/config.py`.
- [ ] `P02.S20` - update `get_engine()` so its URL-keyed cache honours the new computed URL on profile switch; `src/aeat/adapters/persistence/storage/engine.py`.
- [ ] `P02.S21` - extend `BucketSession.close()` to evict the matching engine from the `get_engine()` cache; `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py`.
- [ ] `P02.S22` - provision `<aeat-root>/buckets/<id>/db/` via `Path.mkdir(parents=True, exist_ok=True)` before any engine open; `src/aeat/application/setup/_service.py`.
- [ ] `P02.S23` - delete the `WorkflowState.profiles` field; `src/aeat/application/workflow/_models.py`.
- [ ] `P02.S24` - rewrite bucket enumeration in `list_profiles` to scan `<aeat-root>/buckets/*/manifest.toml`; `src/aeat/application/user_profile/_lifecycle.py`.
- [ ] `P02.S25` - delete the `WorkflowState.profiles` writers in the orchestration register / remove paths; `src/aeat/application/user_profile/_orchestration.py`.
- [ ] `P02.S26` - migrate test fixtures off `WorkflowState(profiles={...})` to manifest-on-disk fixtures; `src/aeat/application/user_profile/_test_lifecycle.py`.
- [ ] `P02.S27` - wire alembic `env.py` to resolve the per-bucket engine and run `upgrade head` per bucket on first connect; `src/aeat/adapters/persistence/storage/alembic/env.py`.
- [ ] `P02.S28` - relocate workflow run-history persistence to the per-bucket database; `src/aeat/application/workflow/_persistence.py`.
- [ ] `P02.S29` - add per-bucket engine isolation roundtrip test (two buckets, two engines, two distinct histories); `src/aeat/application/workflow/_test_per_bucket_engine_isolation.py`.
- [ ] `P02.S30` - add anti-tautology test mutating one bucket's DB and asserting cross-bucket reads remain unaffected; `src/aeat/application/workflow/_test_per_bucket_isolation_anti_tautology.py`.

### Phase `P03` - operator CLI tail (validate / preflight / get / set / unset / init)

Delete `validate`, `preflight`, `get`, `set`, `unset` from the
operator surface. Rename `init` to `profile create NAME` (positional
Argument, not `--profile` Option). Fold validate into `show`'s
readiness header. Relocate preflight to `aeat app modelo readiness`.
Re-home get/set/unset under `python -m aeat.diagnostics`. Flip
operator-suggestion strings to `aeat config profile edit`.

- [ ] `P03.S31` - delete the `validate` Typer command from the operator surface; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P03.S32` - delete the `preflight` Typer command from the operator surface; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P03.S33` - delete the `get` Typer command from the operator surface; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P03.S34` - delete the `set` Typer command from the operator surface; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P03.S35` - delete the `unset` Typer command from the operator surface; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P03.S36` - fold validate output into `show`'s readiness header with non-zero exit on blocking issues; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P03.S37` - add `aeat app modelo readiness --modelo M --year Y [--period P]` carrying the preflight behaviour; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `P03.S38` - mount `python -m aeat.diagnostics profile get KEY [--profile NAME]`; `src/aeat/diagnostics/__main__.py`.
- [ ] `P03.S39` - mount `python -m aeat.diagnostics profile set KEY VALUE [--profile NAME]`; `src/aeat/diagnostics/__main__.py`.
- [ ] `P03.S40` - mount `python -m aeat.diagnostics profile unset KEY [--profile NAME]`; `src/aeat/diagnostics/__main__.py`.
- [ ] `P03.S41` - rewrite the wizard's `profile_name` parameter from `typer.Option("--profile", ...)` to `typer.Argument(...)`; `src/aeat/entrypoints/cli/wizard/_commands.py`.
- [ ] `P03.S42` - update the `_command(**kwargs)` closure to read `profile_name` from positional args; `src/aeat/entrypoints/cli/wizard/_commands.py`.
- [ ] `P03.S43` - delete the `aeat config init` mount; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P03.S44` - flip the five operator suggestion strings to `aeat config profile edit`; `src/aeat/application/overview/__init__.py`.
- [ ] `P03.S45` - flip the registry `default_suggestion` to `aeat config profile edit`; `src/aeat/core/errors/registry/_domain.py`.
- [ ] `P03.S46` - migrate the test-caller wave from keyword `--profile NAME` to positional `NAME`; `src/aeat/entrypoints/cli/wizard/_test_commands.py`.
- [ ] `P03.S47` - run `python -m aeat.locales scaffold` then `python -m aeat.locales audit` to regenerate catalogues; `locales/`.

### Phase `P04` - per-feature surface gate

Document and enforce the per-feature CI scope. Trunk CI unchanged.

- [ ] `P04.S48` - document the feature-surface-gate skill (path-scoped ruff + pytest + `vault check --feature`); `.vaultspec/rules/skills/feature-surface-gate.md`.
- [ ] `P04.S49` - run `uv run ruff check` against the touched-files filter and resolve every diagnostic in feature-owned files; `src/aeat/`.
- [ ] `P04.S50` - run `uv run pytest` against the touched test-module filter and resolve every failure in feature-owned tests; `src/aeat/`.
- [ ] `P04.S51` - run `uv run vaultspec-core vault check all --feature profile-lifecycle-cli` and resolve every new error against the baseline; `.vault/`.
- [ ] `P04.S52` - capture the surface-gate command output as evidence in the closing step record; `.vault/exec/2026-05-18-profile-lifecycle-cli/`.
