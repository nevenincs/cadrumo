---
tags:
  - "#research"
  - "#profile-lifecycle-cli"
date: "2026-05-17"
related:
  - "[[2026-05-16-profile-lifecycle-cli-adr]]"
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
  - "[[2026-05-16-profile-lifecycle-cli-research]]"
  - "[[2026-05-14-profile-bucket-lifecycle-adr]]"
  - "[[2026-05-17-per-bucket-sqlite-cascade-audit]]"
---

# `profile-lifecycle-cli` research: cascade-closure architecture for the remaining 17 plan steps

This research pass synthesises five parallel investigations into the
architectural decisions required to close the unexecuted portion of
the 2026-05-16 profile-lifecycle CLI redesign without violating the
user's hard mandate: no shims, no aliases, no parallel chains, no
mocks, no skeletons, no deprecated code, no duplication, no shadow
code, no legacy support; the previous design dies in the same commit
its replacement lands.

Five questions were investigated by parallel sub-agents
(haiku for breadth, sonnet for structural depth). Each section
records the agent's findings against current code (file:line
citations throughout), evaluates the architectural options, and
records the recommendation plus the open questions the ADR must
rule on.

## Constraints (inherited by the ADR writer)

These constraints apply to every recommendation below and to every
follow-up commit. They are duplicated here so the ADR writer
inherits them without re-reading the meta-conversation.

- no shims, no aliases, no parallel chains, no deprecation paths
- no mocks, no fakes, no stubs in production OR tests
- no skeletons, no deferred work, no half-implementations
- no duplication of functionality across modules
- no legacy code remnants, no shadow code, no backwards-compat
- the runtime is forward-only; the previous design dies in the
  same commit its replacement lands
- shared worktree: no destructive git (no stash, reset, pop,
  checkout, clean); subagents must be briefed explicitly on this
  rule and operate read-only when discovering

## Findings

### 1. Per-bucket SQLite cutover (P02.S20 / S21): Option A — `WorkflowState` moves into the active bucket's database

The chicken-and-egg blocker the 2026-05-17 cascade audit surfaced
collapses once `WorkflowState.profiles` is removed per the May-14
ADR section 1 terminology mandate. The codebase does not need to
preserve a global-state SQLite database under any name.

**Current shape.** `WorkflowState` persists as a single encrypted
secure-object row in the shared engine. The namespace is
`"aeat.workflow"`; the object key is `"state"`
(`src/aeat/application/workflow/_persistence.py:28-29`). Workflow
run history sits in `"aeat.application.workflow.runs"`
(`_persistence.py:31`), same shared engine.
`WorkflowStateRepository.__init__` constructs
`SecureObjectRepository()` with no engine argument, which falls
through to `secure_objects.py:148`: `self._engine = engine or
get_engine()`. `get_engine()` is a URL-keyed dict singleton
(`engine.py:132-168`) reading `settings.aeat_database_url`,
which defaults to `sqlite:///.../var/aeat.db`
(`config.py:325-328`) — one shared file, no bucket dimension.

Production engine callsites: three
(`engine.py:118`, `engine.py:185`, `core/i18n/_render.py:105`),
all via `get_engine()`. `create_engine_from_settings` is a
test-fixture primitive (98 callsites across 59 test files).

**Option A (chosen): `WorkflowState` moves INTO the active
bucket's database.** `aeat_database_url` becomes a Settings
property computed from the active-bucket pointer file
(`<aeat-root>/buckets/<id>/db/aeat.db`). The hard-coded
`var/aeat.db` default disappears. `get_engine()` resolves the
URL at construction time. `initialize_workspace` provisions
`buckets/<id>/db/` via `Path.mkdir` BEFORE the first
`get_engine()` call. The legacy-layout refusal (already shipped
in P02.S22) fires when `var/aeat.db` exists without `buckets/`.

**Option B (rejected): two engines — global state engine plus
per-bucket engines.** Concrete cost: a permanent shadow code
path. `engine.py` splits into `get_state_engine()` and
`get_bucket_engine()`. `SecureObjectRepository.__init__` grows a
namespace-to-engine routing map. The architectural mandate in
`aeat-architecture-boundaries.md` ("Do not introduce shims,
compatibility layers, deprecation paths, or duplicate legacy
APIs") plus the May-14 ADR section 2 ("One database per bucket;
the legacy interleaved `var/aeat.db` is gone") explicitly forbid
this shape. Option B contradicts the ADR text by introducing a
persistent global database the ADR specifically retires.

**Why the chicken-and-egg dissolves under Option A.** The
apparent blocker — `list-buckets` needs `WorkflowState.profiles`
but must not touch the engine — disappears once
`WorkflowState.profiles` is removed per the May-14 section 1
rename mandate. Bucket enumeration comes from a filesystem scan
of `buckets/*/manifest.toml`, which `list-buckets` reads as
plaintext per the May-14 ADR section 4. There is no
engine-without-bucket scenario in the target architecture.

**Single-cut migration recipe (one commit, no parallel chain):**

1. Make `aeat_database_url` a computed property on `Settings`
   that resolves through the active-bucket pointer chain.
   Static default removed.
2. `get_engine()` handles `NoActiveBucketError` on URL
   resolution before first use.
3. `initialize_workspace` provisions `buckets/<id>/db/` via
   `Path.mkdir` BEFORE any engine open.
4. `alembic/env.py` and `migrations_api.py` resolve the per-bucket
   path; `alembic_version` becomes a per-bucket table.
5. Three production read sites (`engine.py:118`, `:185`,
   `core/i18n/_render.py:105`) inherit the computed value with
   no code change required.
6. Test fixtures continue to call `create_engine_from_settings`
   directly with explicit URLs; no test cascades.

**Open questions for the ADR writer:**

- `WorkflowState.profiles` cardinality. Under Option A this dict
  lives inside the active bucket's DB, so iterating all
  registered buckets requires the active bucket to be unlocked.
  The May-14 ADR section 1 rename mandate implies removal of
  `profiles` as a structural noun; bucket enumeration moves to
  manifest scan. The ADR writer must declare the sequence: does
  `profiles` delete in the same commit as the engine cutover, or
  earlier?
- `WorkflowResult` / run history scope. `_persistence.py:31`
  places run history in
  `"aeat.application.workflow.runs"` — the same shared engine.
  Under Option A run history becomes per-bucket; `list_runs`
  returns only the active bucket's history. Is this the intended
  UX, or is a global run log outside any bucket required?
- Alembic per-bucket migration state. `aeat_storage_auto_migrate`
  runs `alembic upgrade head` against the resolved engine. Under
  Option A this runs once per bucket on second-bucket creation.
  The ADR must declare the migration ordering contract.

### 2. `BucketSession` crypto cutover (P03.S27 - S33): Pattern 1+4+5 composition — ContextVar + free-function interface + CLI with-block

The crypto path's three viable patterns compose; the architectural
recommendation is to land all three layers in one cut.

**Current shape.** `_resolve_master_key()` at
`src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py:100`
is the chokepoint — six call sites within
`_encrypted_columns.py` funnel through it.
`_resolve_master_key_provider()` at `:105` checks a module-level
`_provider_override: MasterKeyProvider | None` (`:84`), held
under a `threading.Lock` (`:83`). When the override is `None` it
calls the free function `get_master_key_provider()`
(`master_key/_master_key.py:976`).

The provider chain holds process-global `ClassVar` state:
`KeyringMasterKeyProvider._cache: ClassVar[dict[tuple[str,str],
bytearray]]` (`_master_key.py:361`),
`KeyringMasterKeyProvider._lock: ClassVar[Lock]` (`:360`).
`FileFallbackMasterKeyProvider` mirrors the pattern. These caches
exist BECAUSE the crypto path does not thread a session
reference; replacing them with a module-global session registry
is shape-equivalent (the user's mandate explicitly rules out
"replacing one process-global cache with another").

Production callers of `get_master_key_provider()` are three:
`crypto/_encrypted_columns.py:120`,
`secret_store/_secret_store.py:180`,
`blob_store/_blob_store.py:155`. The latter two already accept
an injected provider via constructor; only `_encrypted_columns`
has no injection seam.

**Pattern 2 (caller-threaded session) is structurally blocked.**
SQLAlchemy's `TypeDecorator.process_bind_param` has the fixed
signature `(self, value, dialect)`; there is no way to inject a
`session` argument through SQLAlchemy's column machinery at
query execution time. Caller-threaded session is mechanically
impossible for the column-level decrypt path.

**Pattern 3 (singleton ClassVar registry) violates the mandate.**
Shape-equivalent to the current ClassVar caches; explicitly
ruled out.

**Recommendation: Patterns 1 + 4 + 5 as a composition.**

- Pattern 4 (interface): replace `_resolve_master_key()` at
  `_encrypted_columns.py:100` with a call to a new free function
  `get_active_master_key() -> bytes` defined in a thin new module
  (e.g. `master_key/_active_session.py`). The column path
  imports this function; it no longer knows about
  `MasterKeyProvider`.
- Pattern 1 (storage): `_active_session.py` holds
  `_active_session: ContextVar[BucketSession | None]`.
  `get_active_master_key()` reads the var; if set and live,
  returns `session.dek`; otherwise raises. The ContextVar
  pattern is per-thread / per-async-task, satisfying the
  no-process-global rule.
- Pattern 5 (composition): the CLI entry point opens a
  `BucketSession` and enters
  `with activate_session(session):` before dispatching. The
  session provides the DEK transparently to all column-level
  decrypt/encrypt calls inside the block.

This is the minimum-cascade path: zero changes to the six
in-module call sites (they call a renamed internal), zero
changes to SQLAlchemy ORM models, zero changes to repository
constructors. The column path becomes session-aware through one
indirection layer rather than through parameter threading.

**Precedent already exists.** The codebase uses `contextvars.ContextVar`
in three places: `core/config.py:969`
(`_settings_override` backing `override_settings()`),
`core/observability/_context.py:90,96` (run + step context for
structured logging), and `entrypoints/cli/_errors.py:58`
(`_UNDER_TEST` gating CLI error-boundary). The
`override_settings` shape at `config.py:990` is the closest
precedent: a module-level `ContextVar`, set inside a
`contextmanager`, restored on exit via `Token`.

**Single-cut migration recipe:**

1. Add `master_key/_active_session.py` exporting
   `_active_session: ContextVar[BucketSession | None]`,
   `activate_session(session)` contextmanager, and
   `get_active_master_key() -> bytes`.
2. Replace `_resolve_master_key()` body at
   `_encrypted_columns.py:100` with
   `return get_active_master_key()`. Delete
   `_resolve_master_key_provider()` and the
   `_provider_override` / `_provider_lock` module-globals.
3. Delete `_lock` / `_cache` ClassVars on
   `KeyringMasterKeyProvider` (`_master_key.py:360-361`) and
   `_cached_passphrase` / `_cached_master_key` on
   `FileFallbackMasterKeyProvider`.
4. Delete `_purge_caches_at_exit` atexit hook (no caches to
   purge). Register a replacement atexit that closes any open
   `BucketSession`.
5. The CLI root callback opens a `BucketSession` based on the
   active-profile passphrase prompt and enters
   `activate_session(session)` as `ctx.with_resource(...)`.
6. Every test that previously called `override_master_key_provider`
   migrates to `activate_session(BucketSession.open(passphrase=...))`
   inside a context manager. The
   `EphemeralMasterKeyProvider` test fixture wraps to mint a
   test-only BucketSession.
7. AST-guard test asserts zero `ClassVar` state on both
   providers (P03.S33 contract).

**Open questions for the ADR writer:**

- Async-task isolation. `asyncio` tasks inherit a copy of the
  `ContextVar` context from their parent at creation time. The
  ADR should state whether async dispatch crosses the session
  boundary in this codebase and whether the inherited-context
  default is correct.
- Thread-pool workers. `ThreadPoolExecutor` workers do NOT
  inherit `ContextVar` state by default (Python < 3.12). The
  ADR should document whether SQLAlchemy's sync execution ever
  crosses a thread boundary in this codebase.
- `BucketSession.dek` as the column key. Today
  `_encrypted_columns` calls `MasterKeyProvider.get_master_key()`
  which returns a 32-byte KEK or DEK depending on provider.
  The ADR must confirm that `session.dek` is the correct
  material for the column-level AES-256-GCM path.
- Fallback when no session active. If the ContextVar is `None`
  (no session activated, e.g. during early init), the resolver
  has nothing to return. The ADR must state whether this is a
  hard refusal (raise) or a fallback to the legacy provider
  chain during one transitional commit (the latter violates
  no-parallel-chain mandate; the former is the honest cut).

### 3. Operator CLI rationalisation (P05.S40 / S44 / S45): wizard-only field edits, modelo-side preflight, init renames to `profile create`

The 2026-05-16 ADR's intent — "operators use plain English; engineer
verbs hide under `python -m aeat.diagnostics`" — resolves the
field-targeted-edit gap. Operators do not need field targeting;
engineers do, and they get it via the diagnostics surface.

**Current shape.** The shipping `aeat config profile` subgroup
mounts: `list` (`__init__.py:236`), `get` (`:260`), `set`
(`:291`), `unset` (`:331`), `validate` (`:352`), `preflight`
(`:388`), `switch` (`:451`), `show` (`:531`), `delete` (`:570`),
`duplicate` (`:606`), `rename` (`:686`), `export`/`import`
(`:768`/`:817`), `status` (`:883`), `logout` (`:903`).
Operator-visible fix-command suggestions referencing the legacy
verbs:

- `overview/__init__.py:230, 320-340` — five suggestion strings
  pointing at `aeat config profile set X Y`
- `core/errors/registry/_domain.py:771` — central registry
  `default_suggestion` pointing at `aeat config profile set
  tax.residence.ccaa madrid`

**Comparable-tool survey.** `gh config`, `git config`,
`gcloud config set`, `aws configure set` all retain
`set KEY VALUE` on their operator surface. These tools target
engineers as operators. The AEAT CLI targets a non-technical
autonomo (the operator transcript that triggered the redesign).
The comparable-tool pattern does not apply.

**Recommendation: Pattern 1 — wizard-only field edits.**

- `aeat config profile validate` deletes. The validation surface
  folds into `show` as a missing-fields warning header. The
  per-issue table that validate emitted today moves to
  `python -m aeat.diagnostics profile validate` for engineers.
- `aeat config profile preflight` moves to
  `aeat app modelo readiness --modelo M --year Y [--period P]`.
  Preflight is a filing-readiness check, not a profile-readiness
  check; it belongs on the modelo surface.
- `aeat config profile get / set / unset` delete. Engineers use
  `python -m aeat.diagnostics profile {get,set,unset}`.
  Operator suggestions in `overview/__init__.py:320-340` and the
  domain error registry flip from
  `aeat config profile set X Y` to
  `aeat config profile edit` (the wizard re-run; P06.S52, already
  landed). The wizard prompts every field; the operator answers
  only the empty ones or the ones they want to change.
- `aeat config init` renames to `aeat config profile create NAME`.
  The wizard `--profile NAME` Typer Option becomes a positional
  `NAME` Argument. The existing wizard backend is reused; only
  the Typer parameter kind changes and the test-caller wave
  flips from `--profile NAME` to `NAME` as positional.

**Single-cut migration recipe:**

1. Delete `validate` + `preflight` Typer commands from
   `_config/__init__.py`. Move ProfileValidationService and
   ProfilePreflightService callers to:
   - `show` verb (validate fold-in): show emits a "missing
     fields: N" header line and exits non-zero if blocking
     issues exist.
   - `aeat app modelo readiness` (preflight relocation): new
     verb under the modelo subgroup.
2. Delete `get` / `set` / `unset` Typer commands from
   `_config/__init__.py`. Mount equivalents under
   `python -m aeat.diagnostics profile get|set|unset KEY [VALUE]`.
3. Rewrite the wizard's profile_name parameter at
   `wizard/_commands.py:352-363` from KEYWORD_ONLY
   `typer.Option("--profile", ...)` to POSITIONAL_OR_KEYWORD
   `typer.Argument(...)`. Update the `_command(**kwargs)`
   closure at `:431` to read `profile_name` from positional
   args, not kwargs. The verb signature flips from
   `aeat config init --profile NAME ...` to
   `aeat config profile create NAME ...`. Delete the `init`
   mount entirely.
4. Flip the 5 fix-command suggestion strings in
   `overview/__init__.py:320-340` from
   `aeat config profile set X Y` to
   `aeat config profile edit`. Flip the registry
   `default_suggestion` at
   `core/errors/registry/_domain.py:771` similarly.
5. Flip the test-caller wave (~10 sites passing `--profile NAME`)
   to positional. The locale catalogues regenerate.

**Open questions for the ADR writer:**

- Is field-targeting for scripted automation, or operator
  interaction? The current `aeat config profile set X Y`
  serves both. If automation is in scope for an operator,
  `python -m aeat.diagnostics profile set X Y` is awkward to
  type; if automation belongs to engineers / CI, the diagnostics
  surface is the right home.
- `aeat app modelo readiness` vs a separate `aeat app modelo
  check` verb. The May-14 / May-16 ADRs leave the verb name
  open. `readiness` matches the operator-facing intent;
  `check` is shorter but conflicts with broader filing-check
  patterns elsewhere in the codebase.

### 4. CI / quality gates (P08.S65 - S69): per-feature surface gate plus trunk-wide cleanup wave

The factory-direct shared-worktree model precludes "every gate
green at every commit" without ejecting all of the parallel
agents from the same branch. The honest discipline is path-scoped
gates per feature plus a dedicated post-feature cleanup wave.

**Current CI configuration.** `.github/workflows/ci.yml:10-15`
triggers only on push-to-main and pull-request-to-main; no
branch-push CI feedback. Matrix: Ubuntu + Windows, Python 3.13.
Sequential gates: lint, typecheck, semgrep, registry verify,
audit oracles, unit tests, hooks. Ruff is configured at
`pyproject.toml:188-241` with `src = ["src"]` and accepts
`[FILES]...` positional arguments. Pytest is scoped to
`src/aeat`. `prek.toml` has all hooks verify-only; pre-commit
is NOT installed locally. `vault check all --feature <tag>`
exists and scopes vault validation to one feature's
documents.

Branch tip carries:

- 76 pre-existing ruff diagnostics in files untouched by this
  feature
- 183 vault validator errors across parallel features' plans /
  exec records
- Pre-existing `AuthenticatedAeatSessionResult` pydantic
  forward-ref failure in `test_ensure_session.py`

None of these are introduced by the profile-lifecycle-cli work;
they belong to other agents' WIP on the shared branch.

**Recommendation: per-feature surface gate + trunk CI unchanged +
post-feature cleanup wave.**

Per-feature surface gate runs at landing time, against the
files the feature touches:

```
git diff main...HEAD --name-only  →  filter to *.py under src/aeat
uv run ruff check $(those files)
uv run pytest $(test files in those directories)
uv run vaultspec-core vault check all --feature profile-lifecycle-cli
```

Trunk-wide CI (`.github/workflows/ci.yml`) stays as-is. It
fails on unrelated work in the shared branch; that failure is
visible to all agents and is not a blocker on individual
feature commits. The trunk-wide cleanup wave is a dedicated
plan-phase run AFTER every feature lands, with explicit
ownership.

**Single-cut migration recipe:**

1. Document the per-feature surface gate in a new short skill
   or convention doc under `.vaultspec/rules/skills/` (e.g.
   `feature-surface-gate.md`). The ADR references it.
2. The `P08.S65 - S69` plan steps explicitly scope to the
   touched-files filter; the closing condition becomes "ruff
   clean on touched files, pytest green on touched modules,
   vault audit no new errors on the feature tag."
3. A separate plan (not in this cascade-closure ADR) sequences
   the trunk-wide cleanup wave. That plan's owner is the
   project coordinator, not any individual feature owner.

**Open questions for the ADR writer:**

- Branch-push CI trigger: should `.github/workflows/ci.yml`
  also trigger on push to `chore/*` branches (not just main)?
  Async parallel feedback would help. Cost: GitHub Actions
  minutes.
- Owner of trunk-wide cleanup. The user works factory-direct
  with no PRs; a dedicated cleanup feature could be the next
  ADR's scope, or a continuous-background audit role could be
  enlisted (per the `continuous-background-code-review`
  memory).
- Prek `--files` support. If prek accepts a narrowed file
  list on `run`, the per-feature gate can route through it
  consistently; otherwise the gate composes ruff + pytest +
  vault directly.

### 5. Industry-standard compliance: P03 cluster is the highest-priority gate

The remaining work maps cleanly against five external standards.
P03 (crypto cutover) closes the most security-critical gaps and
should be sequenced first.

**OWASP 2024 Password Storage Cheat Sheet (Argon2id baseline).**
`src/aeat/adapters/persistence/storage/master_key/_kdf_params.py:8-13`
declares the exact OWASP baseline (memory_cost=19 MiB,
time_cost=2, parallelism=1, salt=16 bytes, output_length=32).
`KdfParams.default()` at `:81-93` materialises these values
under fresh `secrets.token_bytes`. The `KdfParams` model is
strict pydantic v2 — a tampered manifest cannot drive the KDF
weaker. `application/setup/_service.py:19-27` cross-pins the
same constants and writes them into every manifest at init.
**Compliant.**

**NIST SP 800-63B (memorised secrets).** Section 5.1.1.1
mandates verifier-enforced minimum 8 characters; explicitly
forbids composition rules; recommends a 64-character (or
higher) maximum. `_master_key.py:548-552` accepts any non-empty
non-whitespace passphrase. Test fixtures at
`_test_master_key.py:203, 219, 231, 244, 250` use `"x"`
(1 char). **Non-compliant.** The fix lands in P03 because P03
is already opening `_master_key.py`; the enrolment UI must
inherit the verifier-side gate from the provider layer.

**Twelve-Factor App.** Factor III (Config) — compliant via
`pydantic-settings` BaseSettings at `core/config.py:90-199` with
single `.env` source. Factor X (Dev/prod parity) — compliant
via `SecretStoreBackend.UNSECURED` gated behind
`AEAT_ALLOW_UNENCRYPTED=1` plus a NIF canary. Factor VI
(Processes — stateless) — non-compliant via the ClassVar caches
in `KeyringMasterKeyProvider` and `FileFallbackMasterKeyProvider`;
P03 closes this gap.

**GNU CLI Standards / POSIX CLI conventions.** Verb-noun
grammar — compliant via the landed verbs (`switch`, `show`,
`edit`, etc.). `--help` / `-h` surface — compliant
(`_config/__init__.py:62`). Single operator surface per intent
— partial drift via S40 (`init` still present), S44
(`validate`/`preflight` still present), S45 (`get`/`set`/`unset`
still on operator side). All three close in the cascade.

**AEAT Sede Electrónica locale requirements.** Compliant
infrastructure via `python -m aeat.locales scaffold + audit`
pipeline. Spanish default at `core/config.py:169-173`
(`aeat_browser_locale = "es-ES"`, timezone Europe/Madrid).
Drift: some `cli.app.ledger.*` keys carry the dotted path as
the value (`en.yml:68-115`) rather than English prose; the
P05/P06 wave already addressed the new keys but legacy stubs
remain. Hungarian (`hu`) carries no statutory basis; the ADR
should note it as product decision, not compliance gate.

**Standards-priority recommendation.** The P03 cluster (S27 -
S33) closes the last 12-Factor VI and OWASP key-custody gaps
AND opens the file where the NIST minimum-length enforcement
must land. P03 is one logical security boundary; it ships as
one cut. P02.S20 - S21 (12-Factor VI per-bucket isolation) and
P05.S40 / S44 / S45 (GNU CLI hygiene) are important but carry
no security risk if sequenced behind P03.

**Open questions for the ADR writer:**

- NIST passphrase floor aggressiveness. NIST mandates 8 chars;
  recommends 14+. Should the codebase land at 8 (minimum
  compliance) or 14 (recommended)? The test fixture `"x"` must
  replace either way; `secrets.token_hex(8)` avoids hard-coding.
- Breach-list check. NIST §5.1.1.2 recommends verifiers check
  passphrases against known-compromised credential lists. For a
  local CLI with no network in the enrolment path, is this
  advisory (warn) or blocking (refuse)? Likely advisory.
- Passphrase rotation. NIST forbids periodic mandatory rotation;
  permits prompting on evidence of compromise. The ADR should
  state the recovery / re-enrolment contract: re-wrap the DEK
  under a new KEK, keep the salt or rotate it.
- Hungarian locale compliance basis. Product or compliance?
  State explicitly to prevent the locale audit treating missing
  `hu` keys as a defect.

## Synthesis: recommended ADR shape

The cascade-closure ADR should make five rulings:

1. **Engine cutover: Option A.** `WorkflowState` moves into the
   active bucket's database. `aeat_database_url` becomes a
   computed Settings property. `WorkflowState.profiles` removes
   in the same cut; bucket enumeration moves to manifest scan.

2. **Crypto cutover: ContextVar + free-function + CLI with-block.**
   `master_key/_active_session.py` exports
   `_active_session: ContextVar[BucketSession | None]`,
   `activate_session()` contextmanager,
   `get_active_master_key()` free function.
   `_resolve_master_key` becomes a one-line delegation. All
   ClassVar caches and the legacy `override_master_key_provider`
   seam delete.

3. **Operator CLI: wizard-only.** Delete `validate`, `preflight`,
   `get`, `set`, `unset` from the operator surface. Fold
   validate into `show`; relocate preflight to
   `aeat app modelo readiness`; mount get/set/unset under
   `python -m aeat.diagnostics profile *`. Rename
   `aeat config init` to `aeat config profile create NAME`
   (positional). Flip operator suggestion strings to point at
   `aeat config profile edit`.

4. **CI discipline: per-feature surface gate.** Trunk CI
   unchanged. Per-feature gate runs path-scoped ruff + pytest +
   `vault check --feature <tag>`. Trunk-wide cleanup is a
   separate ADR / plan with explicit ownership.

5. **NIST passphrase enforcement.** Minimum 8 characters at
   `_resolve_passphrase`, in the same P03 cut window. Test
   fixtures migrate to `secrets.token_hex(8)`. Breach-list check
   is advisory; passphrase rotation re-wraps DEK under a fresh
   KEK while preserving the salt.

The ADR sequencing recommendation is P03 first (highest security
risk; opens the file all other crypto work needs), then P02 / P05
in parallel (no security risk, independent surfaces), then P08
gate-closure as the final step.
