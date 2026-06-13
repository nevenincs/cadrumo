---
tags:
  - '#plan'
  - '#profile-lifecycle-disaster'
date: '2026-05-19'
modified: '2026-05-19'
tier: L2
related:
  - '[[2026-05-19-profile-lifecycle-disaster-adr]]'
  - '[[2026-05-19-profile-lifecycle-disaster-axis-a-session-activation-research]]'
  - '[[2026-05-19-profile-lifecycle-disaster-research]]'
  - '[[2026-05-19-profile-lifecycle-disaster-axis-c-cli-bootstrap-research]]'
  - '[[2026-05-19-profile-lifecycle-disaster-axis-d-state-model-research]]'
  - '[[2026-05-19-profile-lifecycle-disaster-axis-e-failure-mode-research]]'
---


# `profile-lifecycle-disaster` recovery plan

### Phase `P01` - lift the import-crash blocker (Ruling 7)

The stale `aeat.domain.vat` import currently crashes the
`aeat` console-script entry on every invocation, after a 10-min
silent hang from registry validation. This Phase lands first
because it currently masks every other failure mode operators see.

- [x] `P01.S01` - retarget `aeat.application.aggregation._iva_ledger` import from `aeat.domain.vat` to `aeat.domain.iva`; `src/aeat/application/aggregation/_iva_ledger.py`.
- [x] `P01.S02` - retarget `aeat.application.aggregation._oss_ioss` import from `aeat.domain.vat` to `aeat.domain.iva`; `src/aeat/application/aggregation/_oss_ioss.py`.
- [x] `P01.S03` - retarget `aeat.application.aggregation._prorrata` import from `aeat.domain.vat` to `aeat.domain.iva`; `src/aeat/application/aggregation/_prorrata.py`.
- [x] `P01.S04` - retarget `aeat.application.aggregation.test_iva_ledger` import from `aeat.domain.vat` to `aeat.domain.iva`; `src/aeat/application/aggregation/test_iva_ledger.py`.
- [x] `P01.S05` - add structural-gate test asserting `python -c "import aeat"` succeeds without exception; `src/aeat/tests/test_console_script_imports.py`.
- [x] `P01.S06` - verify the structural gate fails when reverted; `src/aeat/tests/test_console_script_imports.py`.

### Phase `P02` - session-activation wiring (Ruling 1)

Provider parity, CLI root `ctx.with_resource`, two-tier bootstrap
with active-gate, idle-timeout polling. The substrate change that
unblocks every operator-facing verb.

- [x] `P02.S07` - add `__enter__`/`__exit__` to `KeyringMasterKeyProvider` mirroring the Unsecured pattern; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [x] `P02.S08` - add `__enter__`/`__exit__` to `FileFallbackMasterKeyProvider`; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [x] `P02.S09` - add `__enter__`/`__exit__` to the auto-resolved provider (`get_master_key_provider`); `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [x] `P02.S10` - parameterise `BucketSession.open` by resolved `bucket_id` from the active-profile chain, not a hardcoded string; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [x] `P02.S11` - define the bootstrap-exempt verb registry as a typed tuple; `src/aeat/entrypoints/cli/_bootstrap_exempt.py`.
- [x] `P02.S12` - rewrite the CLI root callback to active-gate on the exempt registry plus `ctx.with_resource(provider)` for non-exempt verbs; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `P02.S13` - emit a translated `CliRefusedBoundaryError` for non-exempt verbs when no profile resolves, naming `profile create` and `profile switch` as next actions; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `P02.S14` - wire `BucketSession.is_expired` polling into `SecureObjectRepository`; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [x] `P02.S15` - raise a translated `CliRefusedBoundaryError` on expired session naming `profile switch` as next action; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [x] `P02.S16` - wire `BucketSession.touch` from the same repository hook; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [x] `P02.S17` - add roundtrip test exercising session-open → verb → expiry → refusal across the CLI root; `src/aeat/entrypoints/cli/test_session_lifecycle_roundtrip.py`.

### Phase `P03` - state-model collapse + atomic create (Rulings 2 + 3)

Three sources of truth. One atomic provisioner. The cuts that
resolve the create/read disagreement and the dual-profile pain.

- [x] `P03.S18` - rewrite `Settings._resolve_database_url_for_active_profile` to delegate to `resolve_active_bucket_id` and `read_pointer`; `drop the inline `tomllib.loads`; `src/aeat/core/config.py`.
- [x] `P03.S19` - add AST-guard test asserting no module under `src/aeat/` re-implements the precedence-chain parse outside `resolve_active_bucket_id` and `read_pointer`; `src/aeat/application/workflow/_test_resolver_uniqueness.py`.
- [x] `P03.S20` - introduce `initialize_profile_bucket(profile_id, *, facts, ...)` owning the atomic five-write sequence (dir + manifest + session + record + pointer) with all-or-nothing rollback; `src/aeat/application/setup/_service.py`.
- [x] `P03.S21` - rewrite the wizard create path to route through `initialize_profile_bucket`; `src/aeat/application/wizard/_persistence.py`.
- [x] `P03.S22` - rewrite `aeat config profile import` to route through `initialize_profile_bucket`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P03.S23` - rewrite `aeat config profile create --copy-from SOURCE` to route through `initialize_profile_bucket`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P03.S24` - retire `register_active_profile` from `user_profile/_orchestration.py`; `the responsibilities move into `initialize_profile_bucket`; `src/aeat/application/user_profile/_orchestration.py`.
- [x] `P03.S25` - rewrite `select_profile` to refuse when the manifest does not exist (today it checks only the encrypted UserProfileRecord); `src/aeat/application/user_profile/_orchestration.py`.
- [x] `P03.S26` - switch `profile list` from `state.active_profile_record()` to `list_profile_buckets()`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P03.S27` - refuse duplicate-name `profile create` with translated error; `src/aeat/application/setup/_service.py`.
- [x] `P03.S28` - migrate the 4 tests that still call `state.profiles[name]` to call `list_profile_buckets()` or `read_profile_bucket(name)`; `src/aeat/application/`.
- [x] `P03.S29` - add roundtrip test asserting create → list → show → switch → show all return consistent identity for the same profile; `src/aeat/application/setup/_test_atomic_create_roundtrip.py`.
- [x] `P03.S30` - add anti-tautology test asserting failure at step 4 of `initialize_profile_bucket` cleanly rolls back steps 1-3; `src/aeat/application/setup/_test_atomic_create_rollback.py`.

### Phase `P04` - --version and --help fast-path (Ruling 4)

Remove every state read from the help/version surfaces.

- [x] `P04.S31` - rewrite `build_cli_version_report` to return name + version only via `importlib.metadata`; `remove `ValidatedRegistryAuthority.load()`; `src/aeat/application/diagnostics.py`.
- [x] `P04.S32` - short-circuit `--help` and `--version` in the CLI root callback before any state-touching call; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `P04.S33` - move full registry validation behind a dedicated opt-in verb `aeat config repair integrity registry`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P04.S34` - add roundtrip test asserting `aeat --version` and `aeat --help` complete in under 200 ms on a clean storage root; `src/aeat/entrypoints/cli/test_fast_path_no_state.py`.

### Phase `P05` - `CliUnexpectedBoundaryError` retires + repair family rewrite (Rulings 5 + 6)

Operator-facing error legibility. Every error names a recovery verb
that actually works.

- [x] `P05.S35` - audit every `raise CliUnexpectedBoundaryError` site and map each to a named `CliRefusedBoundaryError` subclass with a translated message and a working suggestion; `src/aeat/entrypoints/cli/`.
- [x] `P05.S36` - retire `CliUnexpectedBoundaryError` as a runtime catch-all; `keep top-level `except Exception` only for genuinely unexpected exceptions with a stderr log + structured exit code + `python -m aeat.diagnostics report` pointer; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `P05.S37` - add structural test asserting every `AeatError` subclass has a registry entry; `src/aeat/core/errors/test_registry_completeness.py`.
- [x] `P05.S38` - rewrite `aeat config repair reset-state` to delete via SQL DELETE-by-key without a load-then-delete pattern; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P05.S39` - rewrite `aeat config repair logs` as a streaming tail (seek-from-end, last N lines); `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P05.S40` - mark every `repair` family verb as bootstrap-exempt; `src/aeat/entrypoints/cli/_bootstrap_exempt.py`.
- [x] `P05.S41` - add roundtrip test asserting every `repair` verb runs cleanly without an active session on a fresh storage root; `src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py`.

### Phase `P06` - re-test gate (final verification)

Dispatch the same five operator personas blind against the rebuilt
feature. Pass criterion: every persona scores ≤1 on every prior
pain point.

- [x] `P06.S42` - dispatch persona newcomer for first-time-operator retest and persist testimony; `.vault/audit/2026-05-19-operator-blind-newcomer-retest.md`.
- [x] `P06.S43` - dispatch persona returning for Monday-morning retest and persist testimony; `.vault/audit/2026-05-19-operator-blind-returning-retest.md`.
- [x] `P06.S44` - dispatch persona dual for two-profile retest and persist testimony; `.vault/audit/2026-05-19-operator-blind-dual-retest.md`.
- [x] `P06.S45` - dispatch persona fumbler for error-prone retest and persist testimony; `.vault/audit/2026-05-19-operator-blind-fumbler-retest.md`.
- [x] `P06.S46` - dispatch persona curious for investigatory retest and persist testimony; `.vault/audit/2026-05-19-operator-blind-curious-retest.md`.
- [x] `P06.S47` - write closing synthesis comparing pain scores before/after and close the disaster recovery; `.vault/audit/2026-05-19-profile-lifecycle-disaster-retest-synthesis.md`.
