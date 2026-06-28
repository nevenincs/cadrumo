---
tags:
  - '#adr'
  - '#profile-lifecycle-disaster'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-profile-lifecycle-disaster-axis-a-session-activation-research]]"
  - "[[2026-05-19-profile-lifecycle-disaster-research]]"
  - "[[2026-05-19-profile-lifecycle-disaster-axis-c-cli-bootstrap-research]]"
  - "[[2026-05-19-profile-lifecycle-disaster-axis-d-state-model-research]]"
  - "[[2026-05-19-profile-lifecycle-disaster-axis-e-failure-mode-research]]"
  - "[[2026-05-19-operator-blind-newcomer-testimony-audit]]"
  - "[[2026-05-19-operator-blind-returning-testimony-audit]]"
  - "[[2026-05-19-operator-blind-dual-testimony-audit]]"
  - "[[2026-05-19-operator-blind-fumbler-testimony-audit]]"
  - "[[2026-05-19-operator-testimonial-audit]]"
---

# `profile-lifecycle-disaster` adr: session-activation wiring, state-model collapse, atomic create | (**status:** `accepted`)

## Problem Statement

The 2026-05-18 cascade-closure plan reported its eight phases complete
but the resulting CLI is non-functional from cold start. Five blind-
operator persona tests on 2026-05-19 all failed to complete the
first task (creating an initial profile). Every CLI verb that
touches the encrypted SQLAlchemy engine crashes with
``NoActiveBucketSessionError``. Every documented recovery hint
(``aeat config profile switch``, ``aeat config repair``,
``aeat config repair reset-state --yes``) raises the same error from
the same code path — the escape hatch is welded shut in a circular
loop.

Five research axes (A through E) grounded the disaster:

- **Axis A — session lifecycle.** The ``activate_session`` /
  ``BucketSession.open`` infrastructure exists but the CLI root
  callback never enters the with-block. The Unsecured provider has
  a working ``__enter__`` that activates a session; Keyring / File /
  Auto providers lack the same pattern. Test fixtures are the only
  callers.
- **Axis B — create / read coherence.** The wizard ``profile create``
  path writes the pointer file and the encrypted ``UserProfileRecord``
  but never invokes ``initialize_workspace`` and therefore never
  writes the per-bucket ``manifest.toml``. ``profile show`` and
  ``profile list`` consult the manifest scan and find nothing,
  yielding ``Unknown profile`` for the profile just created.
- **Axis C — CLI bootstrap.** The root callback calls
  ``build_cli_version_report`` on ``--version`` which triggers a
  full registry TOML parse; and calls
  ``workflow_state_repository().load()`` on bare invocation which
  requires an active session. ``--version`` and ``--help`` must
  never touch state, locks, registries, or the master key. They do.
- **Axis D — state-model coherence.** Six concurrent sources of
  truth for "what profile is active and where does its data live":
  ``Settings.aeat_active_profile`` (env), computed
  ``Settings.aeat_database_url``, the ``active-profile`` pointer
  file, per-bucket ``manifest.toml``, the encrypted ``WorkflowState``
  row, and the ``_active_session`` ContextVar. Five
  read-write disagreement zones; one canonical resolver
  (``resolve_active_bucket_id``) exists and is correct but the
  Settings model validator (introduced in commit ``a5220f71``)
  duplicates the chain inline.
- **Axis E — failure-mode operator experience.** Twenty of
  twenty-eight catalogued failure modes route to
  ``CliUnexpectedBoundaryError`` (a generic catch-all that emits
  "command failed" and points the operator at
  ``aeat config repair``). Zero of six documented recovery verbs
  are functional; every one of them crashes on the same cold-start
  session-activation gap. The idle-timeout contract exists in code
  but is never polled.

The cascade-closure plan landed each piece of structural work
correctly, but the integration that would make the substrate operate
from cold start was never wired. Forcing the CLI surface to mask the
defects has produced traceback storms and welded-shut escape hatches.
The CLI cannot be patched around this; the substrate boot sequence
must be wired correctly.

## Considerations

The research axes converged on a single architectural triad rather
than thirty independent fixes. The convergence is the basis for the
rulings below.

The state-model has six concurrent sources. Three are load-bearing
(env override, pointer file, manifest existence). One is derived
(``aeat_database_url`` is a function of the active-profile and the
storage root). One needs no profile-identity content
(``WorkflowState`` already retired its ``profiles`` field). One is
the in-memory projection of the others (``_active_session``
ContextVar). Collapsing the six to three is structurally well-
defined and the canonical resolver already exists.

The session-activation lifecycle is largely implemented. Only the
root-callback ``ctx.with_resource(provider)`` wire is missing, and
Keyring / File / Auto providers need the ``__enter__`` / ``__exit__``
pattern that Unsecured already has. The 1Password CLI's
``op signin`` → idle-TTL → ``op signout`` model is a direct
structural match: ``BucketSession.is_expired`` already exists with a
configurable idle window.

The atomic create contract is the convergence of axes B and D. Every
``profile create`` (wizard, ``--quiet``, ``import``, ``--copy-from``,
recovery-restore) must route through one provisioner that writes
the bucket directory, the manifest, the pointer file, and the
encrypted ``UserProfileRecord`` in sequence with all-or-nothing
rollback. Today the wizard bypasses this provisioner entirely.

Bootstrap-exempt verbs need an unambiguous boundary. ``--version``,
``--help``, ``aeat config profile create`` (the first-run on-ramp),
``aeat config profile import`` (recovery from a backup), and
``aeat config repair`` family verbs (``reset-state``, ``logs``,
``integrity``) must run without a root session. Every other verb
must refuse with a clean ``CliRefusedBoundaryError`` (translated)
when no session is active. The active-gate at the root callback is
the simpler architecture even at the cost of coupling the transport
layer to the exemption list; the silent-skip alternative requires
every non-exempt verb to independently catch
``NoActiveBucketSessionError``, which the failure-mode catalogue
shows is exactly the broken pattern today.

The Unsecured backend is operationally important — every blind
operator test ran with it because the keyring path requires Touch
ID / Windows Hello prompts that block in non-interactive shells.
Production setups will use Keyring or File backends; the
architecture must make all three first-class.

## Constraints

Project mandates that bind every recommendation below:

- No shims, no aliases, no parallel chains, no deprecation paths.
- No mocks, fakes, stubs in production OR tests.
- No skeletons, no half-implementations.
- No shadow code; no naked English on the operator surface.
- The runtime is forward-only; previous design dies in the same
  commit its replacement lands.
- Shared worktree on ``chore/eliminate-shims``: no destructive git
  (no stash, reset, restore, checkout of paths, clean, rebase).
  Only forward-only ``git add <explicit-paths>`` + ``git commit``.
- Locale-via-CLI: every operator-facing string flows through
  ``tr()`` to the four locale catalogues; edits go through
  ``python -m aeat.locales scaffold`` + ``audit``.
- Settings-not-naked-env: production reads through pydantic-settings
  ``Settings`` only; ``Settings`` reads env exactly once at
  construction.
- CLI root contract: exactly ``aeat config`` and ``aeat app``. No
  third surface. Engineer verbs live under
  ``python -m aeat.diagnostics``.
- Cascade-closure ADR remains in vault as historical context; its
  closure claim is rescinded (see synthesis audit). Its individual
  decisions on operator vocabulary, NIST passphrase floor, AST
  guard test, and ``tr()`` locale coverage all hold; this ADR
  re-uses them.

## Implementation

The disaster recovery has three architectural rulings, each
addressing one defect plane, plus four cleanup rulings that the
research axes flagged as load-bearing.

### Ruling 1 — Session-activation lifecycle wires the CLI root

The CLI root callback in ``entrypoints/cli/__init__.py:_root``
acquires a master-key provider through the canonical resolver and
enters it via ``ctx.with_resource(provider)``. The provider's
``__enter__`` opens a ``BucketSession`` and activates it via
``activate_session(session)``; its ``__exit__`` closes the session
and zeroises the key buffers. The session is available to every
subsequent verb invocation within the same process.

Provider parity. ``KeyringMasterKeyProvider``,
``FileFallbackMasterKeyProvider``, and ``AutoMasterKeyProvider``
gain the same ``__enter__`` / ``__exit__`` pattern that
``UnsecuredMasterKeyProvider`` already has. Each opens a
``BucketSession`` parameterised on the active ``bucket_id``
resolved from the precedence chain — not on a hardcoded literal.

Two-tier bootstrap with active-gate. The root callback resolves
the active bucket id and the requested verb. When the verb is on
the bootstrap-exempt list (``--version``, ``--help``,
``aeat config profile create``, ``aeat config profile import``,
``aeat config repair`` family), the root callback skips the
session open and the verb is dispatched without a session. For
every other verb, the root callback either opens the session (if a
profile pointer resolves) or refuses with a translated
``CliRefusedBoundaryError`` whose message names
``aeat config profile create`` or ``aeat config profile switch``
as the next action. No verb is permitted to raise
``NoActiveBucketSessionError`` from inside its own body — the
gate fires at the root.

Idle-timeout wiring. ``BucketSession.is_expired`` polling is
added to ``SecureObjectRepository`` so every repository call
checks the idle deadline; an expired session raises a translated
``CliRefusedBoundaryError`` whose message names
``aeat config profile switch`` as the next action. The
``evaluate_idle`` helper and ``BucketSession.touch`` are wired
together.

### Ruling 2 — State model collapses from six sources to three

Three load-bearing sources survive:

1. **Env override** — ``Settings.aeat_active_profile`` carries
   ``AEAT_ACTIVE_PROFILE`` per-shell. Highest precedence.
2. **Pointer file** — ``<aeat_local_storage_root>/active-profile``
   plaintext TOML. Written only by ``profile create``,
   ``profile switch``, ``profile import``, ``profile rename``,
   ``profile delete``. Canonical default.
3. **Manifest existence** —
   ``<aeat_local_storage_root>/buckets/<id>/manifest.toml``.
   The presence of a manifest IS the existence-of-profile claim.
   The manifest body carries display label, created-at,
   last-unlocked-at, KDF params, recovery-enrolled flag,
   schema-version.

Three sources retire or collapse:

- ``Settings.aeat_database_url`` survives but is computed by the
  canonical resolver, not by an inline model validator. The
  ``_resolve_database_url_for_active_profile`` validator in
  ``core/config.py`` is rewritten to delegate to
  ``resolve_active_bucket_id`` and to the pointer file's
  ``read_pointer`` helper (not raw ``tomllib.loads``).
- ``WorkflowState`` keeps no profile-identity fields. The
  ``profiles`` retirement from P02b is permanent. The encrypted
  state row remains for workflow runs, declaration pointers, and
  review annotations; not for "which profiles exist".
- ``_active_session: ContextVar[BucketSession]`` is the in-memory
  projection of the three on-disk sources during a process
  lifetime. It is not a fourth source of truth; it is the cached
  resolution.

The canonical resolver is the sole entry point. Every consumer
that asks "is profile X registered?" or "what is the active
bucket id?" calls ``resolve_active_bucket_id()`` or
``read_profile_bucket(name)``. Inline duplicates are forbidden.
The test ``_test_no_classvar_state.py`` pattern is extended with
a second AST guard that asserts no module under ``src/aeat/``
re-implements the precedence-chain parse outside the canonical
helpers.

### Ruling 3 — Every profile-creation path routes through one atomic provisioner

A single function ``initialize_profile_bucket(profile_id, *, facts,
provider_setup, ...)`` in ``application/setup/_service.py`` owns
the create contract. Every entry-point (wizard, ``--quiet``,
``profile import``, ``--copy-from``, recovery restore) calls into
this one function. The function performs five writes in sequence
and rolls back on any failure:

1. Provision ``<root>/buckets/<id>/`` and its three
   subdirectories (``db/``, ``blobs/``, ``audit/``) via
   ``provision_bucket_directory``.
2. Write ``<root>/buckets/<id>/manifest.toml`` with the canonical
   fields. This is the moment the profile becomes visible to
   ``read_profile_bucket`` and ``list_profile_buckets``.
3. Open a transient ``BucketSession`` against the new bucket so
   the next two writes can encrypt.
4. Write the encrypted ``UserProfileRecord`` via the lifecycle
   service.
5. Write the active-profile pointer file (write-then-rename)
   bound to this profile_id.

Rollback contract. A failure at step 4 or 5 must reverse
steps 1-3 (directory tree + manifest + session close) so the
operator does not see a half-created profile. The rename pattern
used for ``profile delete`` (trash-prefix rename + delete) gives
the same crash-resilient semantics for partial-failure cleanup.

The wizard's existing ``register_active_profile`` in
``application/user_profile/_orchestration.py`` retires. Its
responsibilities collapse into ``initialize_profile_bucket``. The
``select_profile`` helper that ``profile switch`` calls is
rewritten to refuse when the manifest does not exist (today it
checks the encrypted ``UserProfileRecord`` only, which is the D5
disagreement).

``profile list`` switches from ``state.active_profile_record()``
to ``list_profile_buckets()`` (the manifest scanner).
``profile show NAME`` keeps its ``read_profile_bucket(name)``
gate.

### Ruling 4 — `--version` and `--help` never touch state, locks, registries, or the master key

``build_cli_version_report`` is rewritten to return only the
package name and version from ``importlib.metadata`` or
``__version__``. The ``ValidatedRegistryAuthority.load()`` call
retires from this path. The full registry validation moves to a
dedicated ``aeat config repair integrity registry`` verb (which
is engineer-facing and opt-in). The 10-minute silent hang from
cold start disappears.

``aeat --help`` and ``aeat config --help`` etc. return
immediately from the help document renderer; the root callback
short-circuits before any state read.

### Ruling 5 — `CliUnexpectedBoundaryError` retires as a runtime escape

Twenty of twenty-eight failure modes route to this generic
catch-all today. Every concrete ``AeatError`` subclass on the
boundary now maps to a named ``CliRefusedBoundaryError`` with a
locale-keyed message and a concrete ``suggestion`` field pointing
at a verb that actually resolves the state when called. The
error-registry catalogues at
``core/errors/registry/_adapters.py`` and ``_application.py``
add entries for every error class that lacks one. Unknown
exception propagation hits a structural test gate that fails CI
when any ``AeatError`` subclass lacks a registry entry.

The eliminated catch-all behaviour does not collapse: a top-level
``except Exception`` survives in the entrypoint for genuinely
unexpected exceptions, but it logs to stderr, emits a structured
exit code, and points the operator at
``python -m aeat.diagnostics report`` rather than at the welded-
shut ``aeat config repair`` family.

### Ruling 6 — `aeat config repair` family is rewritten as bootstrap-exempt + state-free

``aeat config repair`` (the bare verb), ``aeat config repair
logs``, ``aeat config repair reset-state``,
``aeat config repair integrity``, ``aeat config repair
quarantine`` must operate without an active session. Each verb
that today reads from ``secure_objects`` before being permitted
to act gets a parallel implementation that operates on plaintext
fingerprints (file size, mtime, KDF-params hash) rather than
decrypted payloads. The ``reset-state`` verb specifically must
be able to delete the encrypted ``WorkflowState`` row without
first reading it; it uses the SQL DELETE-by-key path, not a
load-then-delete pattern.

``aeat config repair logs`` is rewritten as a streaming tail
(read last N lines via seek-from-end) rather than a full file
load. The MemoryError under normal log sizes retires.

### Ruling 7 — The stale `aeat.domain.vat` import retires

``aeat.application.aggregation._iva_ledger``, ``_oss_ioss``,
``_prorrata``, and ``test_iva_ledger`` retarget from the
non-existent ``aeat.domain.vat`` to the actual
``aeat.domain.iva`` module that survives the recent
spanish-stem-terminology-authority rename. This is the F11
finding; the import retire lifts the residual import error that
defers the F7 10-minute hang.

A second structural-gate test enforces:
``python -c "import aeat"`` must succeed. The gate prevents a
future rename from re-introducing a console-script-only import
failure.

## Rationale

The convergence of all five research axes on the same three
architectural decisions (session activation, state-model collapse,
atomic create) is the strongest possible signal that the disaster
is structural, not surface. Patching the CLI verbs cannot fix the
cold-start session-activation gap because the gap is upstream of
every verb. Patching the read sites cannot fix the manifest-not-
written gap because the create path is the only place that lands
the manifest. Renaming the recovery verbs cannot fix the welded-
shut escape because every recovery verb is gated on the same
session-activation that they were meant to recover from.

The three architectural rulings preserve every cascade-closure
deliverable that was substantively correct (the ContextVar
``BucketSession`` infrastructure, the manifest-scan helpers, the
operator-facing vocabulary, the NIST passphrase floor, the
``tr()`` locale coverage, the ClassVar deletion). They wire those
pieces together into a coherent boot sequence. They do not
introduce a parallel chain; the existing pieces are connected to
each other through the canonical resolver and the atomic
provisioner.

The four cleanup rulings (--version fast-path,
``CliUnexpectedBoundaryError`` elimination, ``repair`` family
rewrite, ``aeat.domain.vat`` import retire) are required for the
operator experience to clear the fumbler-testimony quality bar.
They are not optional polish; the failure-mode catalogue (Axis E)
documents each as a structural contributor to the disaster.

The 1Password CLI precedent (Axis A) and the Bitwarden CLI
precedent (Axis C) anchor the lifecycle shape in production-grade
local-state patterns. The git-init / kubectl-create /
gcloud-configurations-create atomicity precedents (Axis B) anchor
the create contract.

## Consequences

The disaster recovery is a substantive rewrite of the operator-
boot path, not a polish pass. The plan that follows this ADR
sequences the seven rulings into atomic commits. Estimated cost:
each ruling is a one-to-three-commit cut; some unblock others
(ruling 1 must land before rulings 3, 6 can be tested; ruling 7
should land first because it currently masks every other failure).

The cascade-closure plan's individual Step records remain in
``.vault/exec/`` as historical context. The disaster recovery
plan opens its own ``exec`` folder under
``2026-05-19-profile-lifecycle-disaster`` and tracks its own
Steps.

Re-test gate at the end of execution. The same five operator
personas (newcomer, returning, dual, fumbler, curious) re-run
the same scripted scenarios blind against the rebuilt feature.
Pass criterion: every persona scores ≤1 on every previously-rated
pain point. No regression on the three bright spots the fumbler
identified (NIF checksum validation, empty-NIF rejection,
non-TTY interactive refusal).

The trunk-wide ``aeat.domain.vat`` import retire (Ruling 7)
likely breaks tests authored against ``aeat.domain.iva``'s old
``_invoice_classification`` symbol map; those tests get migrated
in the same commit as the production rename. No parallel chain;
both sides flip together.

The CLI surface stays stable in shape — the same verbs, the same
help structure, the same locale catalogue. The substrate beneath
the surface is what changes. Operators do not learn new
vocabulary; they encounter a CLI that actually does what its
vocabulary promises.

## Open questions resolved in this ADR

The five research axes each surfaced open questions for the ADR
writer. The rulings above resolve them:

- (Axis A, Q2) Silent-skip vs active-gate at root callback for
  bootstrap-exempt verbs. **Resolved**: active-gate. The
  exemption list lives at the root callback. See Ruling 1.
- (Axis A, Q3) ``EphemeralMasterKeyProvider`` promotion.
  **Resolved**: the class stays test-only; the ``__enter__`` /
  ``__exit__`` pattern propagates to the three production
  providers. See Ruling 1.
- (Axis B, Q3) Duplicate-name handling on ``profile create``.
  **Resolved**: refuse with translated error; do not overwrite,
  do not auto-rename.
- (Axis C, Q4) Registry-validation timing. **Resolved**: move
  out of ``build_cli_version_report``; lazy-load only when first
  verb requires it; opt-in verb
  ``aeat config repair integrity registry`` for explicit refresh.
  See Ruling 4.
- (Axis D, Q5) Canonical resolver entry. **Resolved**: every
  consumer routes through ``resolve_active_bucket_id`` and
  ``read_profile_bucket``; Settings model validator gets
  rewritten to delegate. See Ruling 2.
- (Axis E, Q1) ``CliUnexpectedBoundaryError`` runtime route.
  **Resolved**: retire as a runtime escape; require named refusal
  per error class. See Ruling 5.
- (Axis E, Q2) ``repair`` family bootstrap exemption. **Resolved**:
  ``repair`` family is bootstrap-exempt and operates on plaintext
  fingerprints. See Ruling 6.
