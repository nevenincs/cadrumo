---
tags:
  - '#adr'
  - '#profile-lifecycle-cli'
date: '2026-05-18'
related:
  - "[[2026-05-17-profile-lifecycle-cli-cascade-closure-research]]"
  - "[[2026-05-16-profile-lifecycle-cli-adr]]"
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
  - "[[2026-05-14-profile-bucket-lifecycle-adr]]"
  - "[[2026-05-14-secure-backend-passkey-custody-adr]]"
  - "[[2026-05-17-per-bucket-sqlite-cascade-audit]]"
---

# `profile-lifecycle-cli` adr: cascade closure — engine cutover, crypto ContextVar, CI surface gate, NIST passphrase floor | (**status:** `accepted`)

## Problem Statement

The 2026-05-16 ADR settled the operator-facing CLI vocabulary and the
six persistence-boundary findings. Forty-seven of sixty-four plan
steps closed against it. Seventeen remain, and they cluster around
three architectural questions the 2026-05-16 ADR did not resolve and
that the project mandate refuses to close with shims:

- **Engine cutover (P02.S20 / S21).** The 2026-05-17 cascade audit
  surfaced a chicken-and-egg: the active-bucket SQLite URL cannot
  resolve before `aeat config profile create` runs, because
  `WorkflowState` currently lives in the shared `var/aeat.db` the
  engine would need to read to learn which bucket exists. Two
  architectural answers exist (move `WorkflowState` into the active
  bucket database, OR run two engines — one global for state, one
  per-bucket for application data); neither ships today. The May-14
  ADR section 2 forbids the second by name (`"One database per bucket;
  the legacy interleaved var/aeat.db is gone"`); the question of
  the single-cut migration shape was left for execution.
- **Crypto cutover (P03.S27 - S33).** The May-14
  `secure-backend-passkey-custody` ADR mandated the elimination of
  the `KeyringMasterKeyProvider._cache` and
  `FileFallbackMasterKeyProvider._cached_master_key` ClassVars in
  favour of an instance-scoped `BucketSession`, but did not specify
  HOW the column-level decrypt path (`process_bind_param` inside a
  SQLAlchemy `TypeDecorator`) acquires the active session reference
  without either threading it through every secure-objects caller
  (mechanically impossible — `TypeDecorator.process_bind_param` has
  a fixed signature) or registering it in a new process-global
  registry (shape-equivalent to the ClassVar caches the May-14 ADR
  retired; user mandate explicitly rules this out).
- **CI surface gate (P08.S65 - S69).** The factory-direct
  shared-worktree model has 76 pre-existing ruff diagnostics, 183
  vault validator errors, and a pre-existing pydantic forward-ref
  failure on `chore/eliminate-shims` — none introduced by this
  feature. Industry-standard CI is per-PR; this codebase has no
  PRs. The honest gate definition for the unexecuted steps was left
  for execution.
- **NIST passphrase floor.** Research §5 mapped the residual work
  against OWASP 2024 (compliant), Twelve-Factor (closed when
  ClassVars retire), GNU CLI (closed by 2026-05-16 §4 verb
  retirements), and NIST SP 800-63B §5.1.1.1 — the last is
  non-compliant. `FileFallbackMasterKeyProvider._resolve_passphrase`
  accepts any non-empty non-whitespace string; test fixtures use
  `"x"`. The 8-character minimum verifier-side gate was not in
  scope for either May-14 ADR.

The 2026-05-17 research investigated all four questions through five
parallel sub-agents and produced concrete recommendations with file
and line citations. This ADR formalises those rulings and stitches
them to their predecessor ADRs.

## Supersession Statement

This ADR does **not** supersede the 2026-05-16
`profile-lifecycle-cli` ADR. That ADR remains in force; it owns the
operator-facing vocabulary, the six persistence-boundary findings,
and the active-profile state model. This ADR resolves the three
architectural questions that one left open for execution and adds
the NIST §5.1.1.1 enforcement.

This ADR does **not** supersede the 2026-05-14
`profile-bucket-lifecycle` ADR. That ADR's section 2 ("One database
per bucket") and section 7 (cache-invalidation invariant) remain
authoritative. This ADR fills in the **single-cut migration
mechanics** the May-14 ADR deferred to execution.

This ADR **partially refines** the 2026-05-14
`secure-backend-passkey-custody` ADR. The May-14 custody ADR mandated
`BucketSession` instance-scoped key material and the elimination of
the ClassVar caches; it did not specify how the SQLAlchemy
column-level path acquires the active session. The May-14 ADR's
text in that area is amended by direct cross-reference here:
the column-level path acquires the session via the ContextVar
pattern specified below. All other May-14 custody decisions
(OWASP Argon2id baseline, BIP-39 recovery, key-ciphertext
separation, no-backwards-compat first-run refusal) remain
authoritative.

Earlier ADRs already marked `superseded by 2026-05-16-profile-lifecycle-cli-adr`
remain superseded; this ADR does not reopen any of them. The
chain is: May-07 / May-12 / May-13 → superseded by 2026-05-16
→ refined by 2026-05-18.

## Considerations

The 2026-05-17 research synthesised five parallel sub-agent
investigations into the cascade. The four findings ruled below
each had at least one rejected alternative; the alternatives are
recorded so the rejection rationale is auditable.

**Engine cutover alternatives.** Option A keeps one engine per
process, computed from the active-bucket pointer chain. Option B
keeps two engines, one for `WorkflowState` and one for
application data. Option B contradicts the May-14 ADR section 2 by
name and persists exactly the shared global database the May-14 ADR
retired; Option B requires a permanent `get_state_engine()` /
`get_bucket_engine()` split in `engine.py` and a namespace-to-engine
routing map on `SecureObjectRepository`. The user mandate against
parallel chains forbids this shape.

**Crypto cutover alternatives.** Pattern 1 (ContextVar storage),
Pattern 2 (caller-threaded session), Pattern 3 (singleton ClassVar
registry), Pattern 4 (free-function interface), Pattern 5 (CLI
with-block composition). Pattern 2 is mechanically impossible —
SQLAlchemy's `TypeDecorator.process_bind_param(self, value,
dialect)` has a fixed signature. Pattern 3 is shape-equivalent to
the ClassVar caches the May-14 ADR retired and is ruled out by the
no-parallel-chain mandate.

**CI gate alternatives.** Three options surveyed:
(a) treat every gate failure on the shared branch as a blocker
(would absorb other agents' WIP into this feature),
(b) skip the gates entirely on the feature branch (would let
silent regressions land), (c) per-feature surface-scoped gate
plus trunk CI unchanged (the honest discipline). Options a and b
violate the factory-direct mandate's intent — (a) by smuggling
unrelated work into a feature commit, (b) by abandoning the
gate.

**NIST passphrase floor alternatives.** 8-character minimum
(strict NIST §5.1.1.1 compliance) or 14-character minimum
(NIST recommendation). The 14-character recommendation is
explicitly framed in NIST as preferred but not mandatory; the
8-character minimum is the verifier-side requirement. Adopting
14 imposes UX friction beyond what the standard requires and
without a security study justifying it.

## Constraints

Inherited from the 2026-05-16 ADR and the project mandates:

- No shims, no aliases, no parallel chains, no deprecation paths.
- No mocks, no fakes, no stubs in production OR tests.
- No skeletons, no deferred work, no half-implementations.
- No duplication of functionality across modules.
- No legacy code remnants, no shadow code, no backwards-compat.
- The runtime is forward-only; the previous design dies in the
  same commit its replacement lands.
- Shared worktree on `chore/eliminate-shims`: no destructive git
  (no stash, reset, pop, checkout, clean); no `git add -A`
  outside scoped paths.
- CLI root contract: exactly `aeat config` and `aeat app`. No
  third surface. Engineer verbs live under
  `python -m aeat.diagnostics`.
- Locale-via-CLI mandate applies to every rename:
  `python -m aeat.locales scaffold` + `audit`, never hand-edit yml.
- Settings-not-naked-env: production reads through pydantic-settings
  `Settings`, never `os.environ` / `os.getenv` directly.

Inherited from the 2026-05-14 `profile-bucket-lifecycle` ADR:
1:1 profile↔bucket cardinality, per-bucket directory layout under
`<aeat-root>/buckets/<bucket-id>/`, per-bucket KEK, per-bucket
recovery mnemonic, per-bucket keystore, per-bucket lockfile,
no-backwards-compat refusal on legacy `var/`.

Inherited from the 2026-05-14 `secure-backend-passkey-custody`
ADR: OWASP 2024 Argon2id baseline (memory_cost = 19 MiB,
time_cost = 2, parallelism = 1, salt = 16 bytes, output = 32
bytes), BIP-39 24-word recovery mnemonic, key-ciphertext
separation, atexit zeroisation of unlocked key bytes.

## Implementation

### 1. Engine cutover — Option A: `WorkflowState` moves into the active bucket's database

`Settings.aeat_database_url` is removed as a static field and
replaced with a computed property that resolves through the
active-profile precedence chain (the May-16 §3 chain:
`--profile` flag → `AEAT_ACTIVE_PROFILE` env → pointer file).
The resolved URL is `sqlite:///<aeat-root>/buckets/<bucket-id>/db/aeat.db`.
The hard-coded `var/aeat.db` default disappears entirely. No
shadow setting field, no transitional default.

`get_engine()` in `src/aeat/adapters/persistence/storage/engine.py`
keeps its URL-keyed singleton cache shape (one engine per
distinct URL); on a profile switch the cache key changes and a
new engine is created on first use of the new bucket.
`BucketSession.close()` (May-14 §7) closes any engine whose URL
key matches the closing bucket and drops it from the cache.

`initialize_workspace` in `src/aeat/application/setup/_service.py`
provisions `<aeat-root>/buckets/<id>/db/` via `Path.mkdir(parents=True,
exist_ok=True)` BEFORE any `get_engine()` call. The
legacy-layout refusal already shipped at P02.S22 — `<aeat-root>/var/`
present without `<aeat-root>/buckets/` raises
`LegacyLayoutDetectedError` at first use.

`WorkflowState.profiles` is removed in the same commit as the
engine cutover. Bucket enumeration moves entirely to a
filesystem scan of `<aeat-root>/buckets/*/manifest.toml` —
plaintext, no engine required, satisfies May-14 ADR section 4
(list operates without unlocking). The chicken-and-egg blocker
dissolves because `list` never needed the engine; only the
shipped implementation routed it through one.

Workflow run history (currently in the `"aeat.application.workflow.runs"`
namespace at `src/aeat/application/workflow/_persistence.py:31`)
becomes per-bucket. `list_runs` returns only the active
bucket's history. A global cross-bucket run log is **not**
introduced — adding one would re-introduce exactly the shared
global database this ADR retires. Engineers needing
cross-bucket activity correlation use
`python -m aeat.diagnostics profile activity` per profile.

Alembic per-bucket migration state: `aeat_storage_auto_migrate`
runs `alembic upgrade head` against the resolved per-bucket
engine on first connect to that bucket. The `alembic_version`
table is per-bucket. No global migration table, no
state-versus-bucket sequencing problem.

### 2. Crypto cutover — ContextVar + free-function + CLI with-block composition

A new module `src/aeat/adapters/persistence/storage/master_key/_active_session.py`
exports three symbols:

```python
_active_session: ContextVar[BucketSession | None] = ContextVar(
    "_active_session", default=None
)


@contextmanager
def activate_session(session: BucketSession) -> Iterator[None]:
    token = _active_session.set(session)
    try:
        yield
    finally:
        _active_session.reset(token)


def get_active_master_key() -> bytes:
    session = _active_session.get()
    if session is None:
        raise NoActiveBucketSessionError(
            "No active bucket session. Run `aeat config profile switch NAME`."
        )
    return session.dek
```

The pattern matches the existing `override_settings` precedent at
`src/aeat/core/config.py:990`. The ContextVar is per-thread and
per-async-task by Python semantics (PEP 567); subprocess
isolation is the operating-system boundary above that.

`src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py`
`_resolve_master_key()` at line 100 becomes a one-line
delegation: `return get_active_master_key()`. The
`_resolve_master_key_provider()` helper at line 105, the
module-level `_provider_override` at line 84, the
`_provider_lock` at line 83, and the `override_master_key_provider`
contextmanager all delete in the same commit. The six in-module
call sites become uniform.

The ClassVar caches retire:

- `KeyringMasterKeyProvider._cache` at
  `_master_key.py:361` — deleted.
- `KeyringMasterKeyProvider._lock` at `_master_key.py:360` — deleted.
- `FileFallbackMasterKeyProvider._cached_passphrase` and
  `_cached_master_key` at `_master_key.py:485` — deleted.

The atexit hook `_purge_caches_at_exit` is replaced with an
atexit that closes any open `BucketSession` (and the
`BucketSession.close()` method zeroises its `_dek_buffer` and
`_kek_buffer` bytearrays in place — the May-14 contract).

The CLI root callback in `src/aeat/entrypoints/cli/__init__.py`
opens the `BucketSession` based on the active-profile passphrase
prompt and enters `ctx.with_resource(activate_session(session))`.
Every subcommand executes inside the with-block. The diagnostics
entrypoint follows the same pattern.

Tests that previously called `override_master_key_provider` are
rewritten to wrap their bodies in `with activate_session(BucketSession.open(passphrase=...))`.
The existing `EphemeralMasterKeyProvider` test fixture is
narrowed to a `BucketSession` factory mint helper, NOT a
master-key-provider override. There is no parallel
provider-override path remaining.

`NoActiveBucketSessionError` is raised when
`get_active_master_key()` is called outside an active
`activate_session(...)` block. There is no fallback to the
legacy provider chain — the user mandate against parallel chains
explicitly forbids a transitional escape hatch.

Async task boundaries: `asyncio.Task` inherits the parent's
`Context` at creation time per PEP 567, so the active session
crosses into spawned tasks correctly. `ThreadPoolExecutor`
workers do NOT inherit `Context` by default; this codebase does
not currently execute encryption under a thread-pool worker
(the sync SQLAlchemy path runs on the calling thread). If a
future codepath introduces one, it MUST use
`contextvars.copy_context()` to propagate the active session
explicitly; the failure mode is loud (`NoActiveBucketSessionError`),
not silent.

`BucketSession.dek` is the column-level encryption key. The
May-14 `secure-backend-passkey-custody` ADR established the
DEK as the AES-256-GCM key for the row-ciphertext layer; this
ADR confirms that `session.dek` (not `session.kek`) is what
`get_active_master_key()` returns. The KEK only ever unwraps
the DEK; it never directly encrypts row ciphertext.

### 3. NIST SP 800-63B §5.1.1.1 passphrase floor

`FileFallbackMasterKeyProvider._resolve_passphrase` at
`_master_key.py:548-552` rejects any passphrase below 8 characters
with a typed `PassphraseTooShortError` whose message names the
NIST minimum and points the operator at `aeat config profile
switch NAME` to retry. No composition rules (no
character-class requirements) — NIST §5.1.1.1 explicitly
forbids verifier-imposed composition rules.

Test fixtures at `src/aeat/adapters/persistence/storage/master_key/_test_master_key.py`
that today pass `"x"` migrate to `secrets.token_hex(8)` (16
hex chars, 64 bits of entropy, exceeds the 8-char floor without
hard-coding). No fixture asserts a literal passphrase value.

Breach-list check (NIST §5.1.1.2): advisory, warn-only. The
local CLI has no network in the enrolment path; this ADR does
not introduce one. A future ADR may add an offline
breach-list snapshot if the threat model warrants it.

Passphrase rotation: re-wrap the DEK under a new KEK derived
from the new passphrase. The salt is rotated as part of the
re-wrap. NIST §5.1.1.2 forbids periodic mandatory rotation;
the codebase emits no rotation prompts on a calendar cadence.
A rotation verb is out of scope for this ADR; the existing
`aeat config profile delete NAME` + `import FILE` (re-enrol
from recovery code with a new passphrase) is the supported
path.

### 4. CI surface gate — per-feature scope + trunk CI unchanged

Trunk CI in `.github/workflows/ci.yml` triggers only on
push-to-main and PR-to-main. The shared `chore/eliminate-shims`
branch carries failures from other agents' WIP; those failures
are not introduced by this feature and are not blockers for
feature commits on the same branch.

A per-feature surface gate is documented as a skill at
`.vaultspec/rules/skills/feature-surface-gate.md` and reads
exactly:

```
git diff main...HEAD --name-only \
    | grep -E '^src/aeat/.*\.py$' \
    | xargs uv run ruff check
git diff main...HEAD --name-only \
    | grep -E '^src/aeat/.*/test_.*\.py$' \
    | xargs uv run pytest
uv run vaultspec-core vault check all --feature profile-lifecycle-cli
```

The closing condition for P08.S65 - S69 is: ruff clean on
touched files, pytest green on touched test modules, vault
audit reports no new errors on the `#profile-lifecycle-cli`
feature tag relative to the baseline at branch tip.

Trunk-wide cleanup (the 76 ruff diagnostics + 183 vault errors
+ the pydantic forward-ref failure) is a separate ADR / plan
with its own owner. That plan does not block any feature's
landing; this ADR's scope explicitly excludes it.

### 5. Verb-name confirmations

The 2026-05-16 ADR left two verb-name questions open; this
ADR rules:

- `aeat app modelo readiness` is the name (not `check`). The
  filing-readiness intent is named directly; `check` collides
  with broader filing-check patterns elsewhere in the modelo
  surface.
- `python -m aeat.diagnostics profile {get,set,unset,activity}`
  is the engineer surface. `secure-objects list` and
  `secure-objects export` remain under `python -m aeat.diagnostics`
  per the May-14 §4 plaintext-discovery rule.

### 6. Sequencing

Implementation order is **P03 first** (highest security risk;
opens the file the other crypto work needs; closes the
12-Factor VI gap; lands the NIST §5.1.1.1 enforcement), then
**P02 in parallel with P05** (engine cutover and remaining
operator-CLI deletions are independent), then **P08** as the
gate-closure step. The plan that follows this ADR sequences
the cuts; no parallel chain is permitted between phases.

## Rationale

**Option A engine cutover** satisfies the May-14 ADR section 2
verbatim. Option B re-introduces a shared global database under
a different name and matches none of the comparable-tool patterns
the May-14 research surveyed (Cryptomator, Borg, restic — all
per-vault, no shared state engine). The chicken-and-egg the
2026-05-17 cascade audit surfaced was real for the current
shipped shape but dissolves under the target architecture
because `WorkflowState.profiles` (the only consumer that
required a cross-bucket index) retires in the same cut.

**ContextVar + free-function + CLI with-block** is the minimum
cascade composition. Pattern 2 (caller-threaded session) is
mechanically blocked by SQLAlchemy's `TypeDecorator` API
contract. Pattern 3 (singleton ClassVar registry) is
shape-equivalent to the caches the May-14 ADR retired. The
ContextVar pattern has direct precedent in this codebase
(`override_settings` at `config.py:990`, observability context
at `core/observability/_context.py:90,96`,
`_UNDER_TEST` at `entrypoints/cli/_errors.py:58`); it is the
idiomatic Python answer (PEP 567) for per-thread / per-task
state that must not be globally mutable.

**NIST SP 800-63B §5.1.1.1 compliance at 8 characters** is the
verifier-side minimum. The 14-character NIST recommendation is
advisory; adopting it raises UX friction at first-run without
narrowing the threat model meaningfully. The 8-character floor
plus the Argon2id baseline plus per-bucket key isolation
(May-14) plus the BIP-39 recovery wrap (May-14) is the
defense-in-depth chain; the passphrase is one layer.

**Per-feature CI surface gate** matches the factory-direct
shared-worktree reality. The honest gate definition is "this
feature's changes do not regress the surfaces this feature
touches"; the trunk-wide gate is "the project compiles and
passes its full suite." Conflating the two would either
import unrelated breakage into feature commits (a) or hide
real feature regressions (b). The per-feature surface gate
matches industry per-PR CI practice as closely as the
no-PR factory-direct model permits.

## Consequences

`WorkflowState.profiles` deletion ripples to every test that
constructs a `WorkflowState` fixture with a populated profiles
dict. The plan that follows this ADR enumerates the call sites
and sequences their migration before the deletion lands.

`Settings.aeat_database_url` becoming computed means existing
test fixtures that override the database URL via environment
variable must switch to `override_settings(aeat_active_profile=NAME)`
plus a per-test bucket directory under `tmp_path`. The
`aeat_local_storage_root` redirect autouse fixture in
`src/aeat/application/conftest.py` already targets `tmp_path`;
extending it to also point the active-profile pointer at a
per-test profile name is a small fixture delta.

The ContextVar pattern requires every CLI entrypoint and every
test that exercises encryption to enter
`activate_session(...)` explicitly. There is no fallback. Tests
that today encrypt without opening a session will fail loudly
with `NoActiveBucketSessionError`; the migration recipe
enumerates them.

The NIST 8-char floor breaks every fixture passing `"x"`. The
migration to `secrets.token_hex(8)` lands in the same commit
as the verifier-side check; no fixture passes through both
states.

The per-feature surface gate documents an explicit asymmetry
between trunk CI and per-commit feedback. New feature owners
must follow the skill at `.vaultspec/rules/skills/feature-surface-gate.md`
or risk shipping silent regressions. The trunk-wide cleanup
backlog is owned by a separate plan, not by any feature.

The May-14 `secure-backend-passkey-custody` ADR text describing
the ClassVar caches is amended by this ADR's section 2 — a
reader of the May-14 text who reaches the cache-mechanics
paragraph follows the cross-link here for the canonical
session-acquisition pattern.

`async` task boundaries propagate the active session by PEP 567
default. `ThreadPoolExecutor` does not; future thread-pool
introductions must use `contextvars.copy_context()` to
preserve correctness. This is documented in the
`_active_session.py` module docstring.
