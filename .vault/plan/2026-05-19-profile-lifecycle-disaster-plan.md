---
tags:
  - '#plan'
  - '#profile-lifecycle-disaster'
date: '2026-05-19'
tier: L2
related:
  - "[[2026-05-19-profile-lifecycle-disaster-adr]]"
  - "[[2026-05-19-profile-lifecycle-disaster-axis-a-session-activation-research]]"
  - "[[2026-05-19-profile-lifecycle-disaster-research]]"
  - "[[2026-05-19-profile-lifecycle-disaster-axis-c-cli-bootstrap-research]]"
  - "[[2026-05-19-profile-lifecycle-disaster-axis-d-state-model-research]]"
  - "[[2026-05-19-profile-lifecycle-disaster-axis-e-failure-mode-research]]"
  - "[[2026-05-19-profile-lifecycle-cli-audit]]"
---

# `profile-lifecycle-disaster` recovery plan

Sequences the seven rulings of the disaster ADR into atomic commits.
Ruling 7 (stale `aeat.domain.vat` import retire) lands first because
it currently masks every other failure mode. Ruling 1 (session
activation) lands second because it unblocks every other operator-
facing verb. Rulings 2 (state-model collapse) and 3 (atomic create)
land together because they share the same write paths. Rulings 4
(--version fast-path), 5 (`CliUnexpectedBoundaryError` retire), and
6 (`repair` family bootstrap-exempt) land as polish cuts on top. The
re-test gate at the end dispatches the same five operator personas
blind against the rebuilt feature; pass criterion is every persona
scoring ≤1 on every prior pain point.

## Proposed Changes

Three architectural rulings restructure the lifecycle substrate:

- Wire `activate_session(BucketSession.open(...))` at the CLI root
  via `ctx.with_resource(provider)`. Add the `__enter__`/`__exit__`
  pattern to `KeyringMasterKeyProvider`,
  `FileFallbackMasterKeyProvider`, `AutoMasterKeyProvider`. Two-tier
  bootstrap with active-gate at root for non-exempt verbs. Idle-
  timeout polling wired through `SecureObjectRepository`.
- Collapse six state sources to three (env override → pointer file
  → manifest existence). Settings model validator delegates to the
  canonical `resolve_active_bucket_id` resolver and `read_pointer`
  helper.
- One atomic `initialize_profile_bucket` provisioner owns the
  create contract. Every entry point (wizard, `--quiet`, import,
  `--copy-from`, recovery) calls it. All-or-nothing rollback on
  failure. `profile list` switches to `list_profile_buckets`.

Four cleanup rulings restore the operator-grade quality bar:

- `--version` and `--help` short-circuit before any state, lock,
  registry, or master-key read.
- `CliUnexpectedBoundaryError` retires as a runtime escape; every
  `AeatError` subclass maps to a named `CliRefusedBoundaryError`
  with a functional suggestion.
- `aeat config repair` family becomes bootstrap-exempt and operates
  on plaintext fingerprints; `repair logs` switches to streaming
  tail.
- The stale `aeat.domain.vat` import retargets to
  `aeat.domain.iva`; a structural test ensures
  `python -c "import aeat"` succeeds.

## Steps

### Phase `P01` - lift the import-crash blocker (Ruling 7)

The stale `aeat.domain.vat` import currently crashes the
`aeat` console-script entry on every invocation, after a 10-min
silent hang from registry validation. This Phase lands first
because it currently masks every other failure mode operators see.

- [ ] `P01.S01` - retarget `aeat.application.aggregation._iva_ledger` import from `aeat.domain.vat` to `aeat.domain.iva`; `src/aeat/application/aggregation/_iva_ledger.py`.
- [ ] `P01.S02` - retarget `aeat.application.aggregation._oss_ioss` import from `aeat.domain.vat` to `aeat.domain.iva`; `src/aeat/application/aggregation/_oss_ioss.py`.
- [ ] `P01.S03` - retarget `aeat.application.aggregation._prorrata` import from `aeat.domain.vat` to `aeat.domain.iva`; `src/aeat/application/aggregation/_prorrata.py`.
- [ ] `P01.S04` - retarget `aeat.application.aggregation.test_iva_ledger` import from `aeat.domain.vat` to `aeat.domain.iva`; `src/aeat/application/aggregation/test_iva_ledger.py`.
- [ ] `P01.S05` - add structural-gate test asserting `python -c "import aeat"` succeeds without exception; `src/aeat/tests/test_console_script_imports.py`.
- [ ] `P01.S06` - verify the structural gate fails when reverted; `src/aeat/tests/test_console_script_imports.py`.

### Phase `P02` - session-activation wiring (Ruling 1)

Provider parity, CLI root `ctx.with_resource`, two-tier bootstrap
with active-gate, idle-timeout polling. The substrate change that
unblocks every operator-facing verb.

- [ ] `P02.S07` - add `__enter__`/`__exit__` to `KeyringMasterKeyProvider` mirroring the Unsecured pattern; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `P02.S08` - add `__enter__`/`__exit__` to `FileFallbackMasterKeyProvider`; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `P02.S09` - add `__enter__`/`__exit__` to the auto-resolved provider (`get_master_key_provider`); `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `P02.S10` - parameterise `BucketSession.open` by resolved `bucket_id` from the active-profile chain, not a hardcoded string; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `P02.S11` - define the bootstrap-exempt verb registry as a typed tuple; `src/aeat/entrypoints/cli/_bootstrap_exempt.py`.
- [ ] `P02.S12` - rewrite the CLI root callback to active-gate on the exempt registry plus `ctx.with_resource(provider)` for non-exempt verbs; `src/aeat/entrypoints/cli/__init__.py`.
- [ ] `P02.S13` - emit a translated `CliRefusedBoundaryError` for non-exempt verbs when no profile resolves, naming `profile create` and `profile switch` as next actions; `src/aeat/entrypoints/cli/__init__.py`.
- [ ] `P02.S14` - wire `BucketSession.is_expired` polling into `SecureObjectRepository`; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [ ] `P02.S15` - raise a translated `CliRefusedBoundaryError` on expired session naming `profile switch` as next action; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [ ] `P02.S16` - wire `BucketSession.touch` from the same repository hook; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [ ] `P02.S17` - add roundtrip test exercising session-open → verb → expiry → refusal across the CLI root; `src/aeat/entrypoints/cli/test_session_lifecycle_roundtrip.py`.

### Phase `P03` - state-model collapse + atomic create (Rulings 2 + 3)

Three sources of truth. One atomic provisioner. The cuts that
resolve the create/read disagreement and the dual-profile pain.

- [ ] `P03.S18` - rewrite `Settings._resolve_database_url_for_active_profile` to delegate to `resolve_active_bucket_id` and `read_pointer`; drop the inline `tomllib.loads`; `src/aeat/core/config.py`.
- [ ] `P03.S19` - add AST-guard test asserting no module under `src/aeat/` re-implements the precedence-chain parse outside `resolve_active_bucket_id` and `read_pointer`; `src/aeat/application/workflow/_test_resolver_uniqueness.py`.
- [ ] `P03.S20` - introduce `initialize_profile_bucket(profile_id, *, facts, ...)` owning the atomic five-write sequence (dir + manifest + session + record + pointer) with all-or-nothing rollback; `src/aeat/application/setup/_service.py`.
- [ ] `P03.S21` - rewrite the wizard create path to route through `initialize_profile_bucket`; `src/aeat/application/wizard/_persistence.py`.
- [ ] `P03.S22` - rewrite `aeat config profile import` to route through `initialize_profile_bucket`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P03.S23` - rewrite `aeat config profile create --copy-from SOURCE` to route through `initialize_profile_bucket`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P03.S24` - retire `register_active_profile` from `user_profile/_orchestration.py`; the responsibilities move into `initialize_profile_bucket`; `src/aeat/application/user_profile/_orchestration.py`.
- [ ] `P03.S25` - rewrite `select_profile` to refuse when the manifest does not exist (today it checks only the encrypted UserProfileRecord); `src/aeat/application/user_profile/_orchestration.py`.
- [ ] `P03.S26` - switch `profile list` from `state.active_profile_record()` to `list_profile_buckets()`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P03.S27` - refuse duplicate-name `profile create` with translated error; `src/aeat/application/setup/_service.py`.
- [ ] `P03.S28` - migrate the 4 tests that still call `state.profiles[name]` to call `list_profile_buckets()` or `read_profile_bucket(name)`; `src/aeat/application/`.
- [ ] `P03.S29` - add roundtrip test asserting create → list → show → switch → show all return consistent identity for the same profile; `src/aeat/application/setup/_test_atomic_create_roundtrip.py`.
- [ ] `P03.S30` - add anti-tautology test asserting failure at step 4 of `initialize_profile_bucket` cleanly rolls back steps 1-3; `src/aeat/application/setup/_test_atomic_create_rollback.py`.

### Phase `P04` - --version and --help fast-path (Ruling 4)

Remove every state read from the help/version surfaces.

- [ ] `P04.S31` - rewrite `build_cli_version_report` to return name + version only via `importlib.metadata`; remove `ValidatedRegistryAuthority.load()`; `src/aeat/application/diagnostics.py`.
- [ ] `P04.S32` - short-circuit `--help` and `--version` in the CLI root callback before any state-touching call; `src/aeat/entrypoints/cli/__init__.py`.
- [ ] `P04.S33` - move full registry validation behind a dedicated opt-in verb `aeat config repair integrity registry`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P04.S34` - add roundtrip test asserting `aeat --version` and `aeat --help` complete in under 200 ms on a clean storage root; `src/aeat/entrypoints/cli/test_fast_path_no_state.py`.

### Phase `P05` - `CliUnexpectedBoundaryError` retires + repair family rewrite (Rulings 5 + 6)

Operator-facing error legibility. Every error names a recovery verb
that actually works.

- [ ] `P05.S35` - audit every `raise CliUnexpectedBoundaryError` site and map each to a named `CliRefusedBoundaryError` subclass with a translated message and a working suggestion; `src/aeat/entrypoints/cli/`.
- [ ] `P05.S36` - retire `CliUnexpectedBoundaryError` as a runtime catch-all; keep top-level `except Exception` only for genuinely unexpected exceptions with a stderr log + structured exit code + `python -m aeat.diagnostics report` pointer; `src/aeat/entrypoints/cli/__init__.py`.
- [ ] `P05.S37` - add structural test asserting every `AeatError` subclass has a registry entry; `src/aeat/core/errors/test_registry_completeness.py`.
- [ ] `P05.S38` - rewrite `aeat config repair reset-state` to delete via SQL DELETE-by-key without a load-then-delete pattern; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P05.S39` - rewrite `aeat config repair logs` as a streaming tail (seek-from-end, last N lines); `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P05.S40` - mark every `repair` family verb as bootstrap-exempt; `src/aeat/entrypoints/cli/_bootstrap_exempt.py`.
- [ ] `P05.S41` - add roundtrip test asserting every `repair` verb runs cleanly without an active session on a fresh storage root; `src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py`.

### Phase `P06` - re-test gate (final verification)

Dispatch the same five operator personas blind against the rebuilt
feature. Pass criterion: every persona scores ≤1 on every prior
pain point.

- [ ] `P06.S42` - dispatch persona newcomer for first-time-operator retest and persist testimony; `.vault/audit/2026-05-19-operator-blind-newcomer-retest.md`.
- [ ] `P06.S43` - dispatch persona returning for Monday-morning retest and persist testimony; `.vault/audit/2026-05-19-operator-blind-returning-retest.md`.
- [ ] `P06.S44` - dispatch persona dual for two-profile retest and persist testimony; `.vault/audit/2026-05-19-operator-blind-dual-retest.md`.
- [ ] `P06.S45` - dispatch persona fumbler for error-prone retest and persist testimony; `.vault/audit/2026-05-19-operator-blind-fumbler-retest.md`.
- [ ] `P06.S46` - dispatch persona curious for investigatory retest and persist testimony; `.vault/audit/2026-05-19-operator-blind-curious-retest.md`.
- [ ] `P06.S47` - write closing synthesis comparing pain scores before/after and close the disaster recovery; `.vault/audit/2026-05-19-profile-lifecycle-disaster-retest-synthesis.md`.

## Parallelization

`P01` (import retire) lands first as a standalone commit because
every subsequent verb test depends on the `aeat` console-script
booting at all.

`P02` (session activation) lands after `P01`. Steps S07 through
S10 (provider parity + bucket-id parameterisation) can land as one
commit. Steps S11 through S13 (bootstrap-exempt registry + active-
gate root callback) land as a second commit. Steps S14 through S17
(idle-timeout wiring) land as a third commit. Sequential within the
Phase; the three commits land in order.

`P03` (state-model collapse + atomic create) lands after `P02`.
Step S18 (Settings validator rewrite) and Step S19 (AST guard)
land as one commit. Steps S20 through S30 (atomic provisioner +
caller migration + tests) land as a second commit covering the
full create-path collapse.

`P04` (fast-path) is independent of `P03` and may land in parallel
with it; the changes are in disjoint files. Two commits: Steps
S31 through S33 (registry retire + fast-path wiring), Step S34
(test).

`P05` (error legibility + repair family) lands after `P02` and
`P03` (the verbs depend on the session lifecycle being wired and
the create path being atomic). Three commits: Steps S35 through
S37 (error-class catalogue + retire), Steps S38 through S40
(repair rewrite + exempt registration), Step S41 (test).

`P06` (re-test) runs last; all preceding Phases must close before
the operator personas re-test the rebuilt feature.

## Verification

The plan is complete when every Step is closed and:

- `python -c "import aeat"` succeeds (Ruling 7 verified)
- `aeat --version` and `aeat --help` return in under 200 ms on a
  clean storage root with no `AEAT_LOCAL_STORAGE_ROOT` set
  (Ruling 4 verified)
- `aeat config profile create alice ...` exits 0 and
  `aeat config profile show alice` exits 0 with the alice record
  on the same fresh root (Rulings 1 + 3 verified)
- `aeat config profile list` enumerates every provisioned profile
  via the manifest scan (Ruling 3 verified)
- `aeat config profile switch alice` succeeds and `show` returns
  alice; `switch bob` succeeds and `show` returns bob (Ruling 1
  verified end-to-end)
- `aeat config repair reset-state --yes` succeeds on a corrupted
  workflow-state row without any active session (Ruling 6
  verified)
- Every catalogued failure mode (28 in axis E) routes to a named
  `CliRefusedBoundaryError` with a working suggestion; zero
  `CliUnexpectedBoundaryError` paths fire under any tested
  scenario (Ruling 5 verified)
- AST guard reports no module under `src/aeat/` re-implements the
  precedence-chain parse outside the canonical helpers (Ruling 2
  verified)
- Every operator persona (newcomer, returning, dual, fumbler,
  curious) scores ≤1 on every prior pain point in the re-test
  (P06 final gate)

The disaster recovery closes when P06 reports the pass.
