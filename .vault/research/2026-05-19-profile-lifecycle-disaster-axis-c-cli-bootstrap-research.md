---
tags:
  - '#research'
  - '#profile-lifecycle-disaster'
date: '2026-05-19'
modified: '2026-05-19'
related: []
---

# profile-lifecycle-disaster research: axis C -- CLI bootstrap orchestration

Research axis C of the profile-lifecycle-disaster recovery campaign.
Maps the current root-callback implementation against a production-grade
five-phase bootstrap contract and proposes the rewrite shape to resolve
Defect A (session lifecycle unwired) and eliminate the operator experience
failures catalogued in F1, F3, F6, F7 of the synthesis audit.

## Root callback today

File: src/aeat/entrypoints/cli/__init__.py, lines 83-155.
Supporting: src/aeat/entrypoints/cli/_common.py.

The _root callback is registered with @app.callback() on a
typer.Typer(invoke_without_command=True, add_help_option=False) app.
Execution sequence on any invocation:

1. configure_stdio_for_utf8() at module import (line 31) -- UTF-8 patch.
2. Language override via ctx.with_resource(override_settings(...)).
3. apply_to_root_logger(resolve_log_level(...)) -- log level from flags.
4. ctx.ensure_object(dict)["format"] stashed in context.
5. if version: (line 131) calls build_cli_version_report() which calls
   _build_registry_version_summary() which calls ValidatedRegistryAuthority.load()
   -- full TOML registry parse. 2-5 s on healthy process; 10+ min when a
   broken import defers the crash after registry work completes (F7).
6. if help_: (line 138) calls build_help_document and emits; exits.
7. if ctx.invoked_subcommand is None (lines 142-155, bare invocation):
   calls workflow_state_repository().load() -- attempts encrypted DB read.
   _active_session ContextVar is None, so every encrypted-column access raises
   NoActiveBucketSessionError immediately (Defect A / F1).

What the callback never does:

- Never calls activate_session() (_active_session.py lines 53-73).
  ContextVar[BucketSession | None] stays None for entire process lifetime.
- Never calls BucketSession.open() (_bucket_session.py lines 64-106).
- Never invokes any MasterKeyProvider.
- Never detects whether local state exists before attempting to read it.
- Never gates --version as a fast-path (registry load fires on --version).
- Never detects TTY vs non-TTY before attempting unlock.
- Never registers teardown via ctx.with_resource(...) for key material
  zeroisation. BucketSession.close() (_bucket_session.py lines 158-203)
  is never called from production code.

activate_session and BucketSession.open are exercised only in test fixtures.
No production CLI code path ever enters the session block.

The six UserWarning lines on every invocation (F6) come from _validate.py
line 2526 during registry validation. No warnings.filterwarnings guard is
registered before registry access begins.

## Root callback contract -- five phases

A production-grade local-state CLI root callback must implement five phases in
strict order. Failure in any phase emits a structured error and exits before
the next phase runs.

### Phase 1 -- Detect

Is there any local state? In what shape?

- Does aeat_local_storage_root exist and is it writable?
- Does the active-profile pointer file exist (<root>/active-profile)?
- Does the named bucket have a <root>/buckets/<name>/manifest.toml?
- Is the manifest structurally valid (readable TOML, required fields present)?

Cold-start (no pointer, no manifests): emit on-ramp landing screen, exit 0.
Do not attempt to open any database.

Owner today: _models.py:resolve_active_bucket_id (lines 189-221) reads pointer
and env var but does not verify manifest presence. No CLI-level manifest check
exists at the entry point.

### Phase 2 -- Boot

Validate state shape; refuse if structurally wrong.

- Does the bucket directory have expected layout (db/aeat.db, manifest.toml)?
- Can the manifest be deserialised into the typed manifest model?
- Is AEAT_DATABASE_URL resolvable from the active bucket path?

Owner today: Settings.aeat_database_url computed validator fires at Settings
construction time -- before any CLI routing can intercept it. On cold start the
chain returns empty and the validator raises "aeat_database_url is empty; set
AEAT_DATABASE_URL" (F3). This belongs in a lazy boot check, not an eager
pydantic validator.

### Phase 3 -- Unlock

Prompt operator or read keystore.

- Select provider via AEAT_SECRET_STORE_BACKEND.
- Check sys.stdin.isatty(). If TTY: prompt via getpass. If not: read
  AEAT_SECRET_PASSPHRASE or refuse with structured error.
- Call MasterKeyProvider.__enter__() / BucketSession.open() to derive KEK
  and DEK. Register activate_session(session) via ctx.with_resource()
  so teardown fires automatically on context exit.

Owner today: providers exist (_master_key.py), activate_session exists
(_active_session.py), BucketSession exists (_bucket_session.py).
None are wired to the CLI bootstrap path.

### Phase 4 -- Dispatch

Run the verb inside the unlock scope. _active_session ContextVar is set;
every encrypted-column access resolves the DEK through get_active_master_key().

Owner today: subcommand handlers are structurally correct. The missing
upstream unlock phase is the sole gap.

### Phase 5 -- Teardown

BucketSession.close() must fire on clean exit or exception. It overwrites
key buffers in place, seals the session, and evicts the SQLAlchemy engine
bound to the bucket database URL.

Owner today: BucketSession.close() implementation is complete
(_bucket_session.py lines 158-203). No production call site registers it
as a teardown.

## Comparable-CLI root flows

Six production-grade CLIs surveyed for their root-callback bootstrap patterns.
All manage local encrypted or authenticated state with first-run / locked /
unlocked / no-state scenarios.

### gh (GitHub CLI)

| Scenario | Behaviour |
|---|---|
| Bare, no state | Welcome + run gh auth login + exit 0 |
| Bare, state present | Shows usage/help |
| Verb, no auth | Defers to verb; auto-prompts auth flow if missing |
| --help | Immediate; no auth check |
| --version | Immediate; no state read |

Key patterns: --version is fast-path; auth is lazy (deferred to verb, not root
callback). No global lock lifecycle; token auth is stateless per-call.

### git

| Scenario | Behaviour |
|---|---|
| Bare, no repo | Usage + fatal: not a git repository |
| Bare, repo present | Short usage summary |
| Verb, no repo | Refuses immediately with structured fatal error |
| --version | Immediate; no repo access |
| --help | Immediate; no repo access |

Key patterns: detect is a single is_git_dir() check before every verb.
No unlock phase. --version and --help bypass all phases.

### gcloud (Google Cloud SDK)

| Scenario | Behaviour |
|---|---|
| Bare, no config | Routes to gcloud init |
| Bare, config present | Prints active account, project, region |
| Verb, no auth | Routes to gcloud auth login |
| --version | Immediate; no config read |
| --help | Immediate; no config read |

Key patterns: detect checks credentials file. No per-invocation passphrase.
--version / --help always fast-path.

### bw (Bitwarden CLI) -- most structurally relevant

Local encrypted vault, per-session unlock, explicit teardown -- closest
analogue to AEAT.

| Scenario | Behaviour |
|---|---|
| Bare, no vault | You are not logged in. Run bw login. |
| Bare, vault locked | Vault is locked. Use bw unlock or set BW_SESSION. |
| Bare, unlocked | Brief status summary |
| Verb, vault locked | Refuses immediately; no data access |
| --version | Immediate; no vault access |
| --help | Immediate; no vault access |

Key patterns for AEAT to adopt:
- Detect: checks ~/.config/Bitwarden CLI/data.json presence.
- Unlock: bw unlock derives a session token (KEK/DEK equivalent) passed as
  BW_SESSION env var -- per-process stateless.
- Teardown: bw lock clears token; key material lives only for that process.
- --version and --help never touch the vault.

### op (1Password CLI)

| Scenario | Behaviour |
|---|---|
| Bare, no account | No accounts found. Add with op account add. |
| Bare, locked | Prompts for biometric or Secret Key + password |
| Bare, unlocked | Lists vaults or shows status |
| Verb, locked | Prompts interactively, or uses OP_SERVICE_ACCOUNT_TOKEN |
| --version | Immediate; no account access |
| --help | Immediate; no account access |

Key patterns: OP_SERVICE_ACCOUNT_TOKEN skips interactive unlock for scripted
callers. --version / --help bypass all state machinery.

### kubectl

| Scenario | Behaviour |
|---|---|
| Bare, no kubeconfig | error: stat ~/.kube/config: no such file or directory |
| Bare, kubeconfig present | Shows usage |
| Verb, no cluster reachable | Verb fails at connection time, not at root |
| --version | Immediate; --client flag skips server contact |
| --help | Immediate; no cluster access |

Key patterns: detect is file-presence only. Root callback is minimal --
most validation deferred to verb level.

## Registry-validation strategy

### Current behaviour

build_cli_version_report() calls _build_registry_version_summary()
(diagnostics.py line 319) which calls ValidatedRegistryAuthority.load()
parsing all registry TOML. On a broken import (F11), the crash defers until
after registry validation completes -- explaining the 10+ minute silent hang
(F7): registry work finishes, then the broken import crashes.

Six UserWarning lines (F6) come from _validate.py line 2526 during registry
validation. No warnings.filterwarnings guard is registered beforehand.

### What should run always (every invocation)

- UTF-8 stdio configuration (already at module top -- correct).
- Log-level application.
- Context dict initialisation.
- Import-error detection (the _app_import_error check at line 143 exists but
  fires after the registry load, not before).

### What should run on-demand (deferred to verb)

- workflow_state_repository().load() -- must run inside activate_session block.
- build_overview_status_report() -- same.
- ValidatedRegistryAuthority.load() -- expensive; defer to verbs that need it.
  --version should read __version__ only, not parse TOML.

### What should never run on bare invocation

- Any encrypted-column access.
- Full registry validation.
- Any I/O beyond reading the pointer file and manifest.

### Recommendation

Gate --version on package metadata only -- no registry, no state:
    typer.echo(f"aeat {__version__}")

Move ValidatedRegistryAuthority.load() out of build_cli_version_report()
into a function called only by config repair.

Add warnings.filterwarnings guard before any registry access in non-diagnostic
paths, or guard the warnings.warn call in _validate.py line 2526 with
warnings.catch_warnings so library users see warnings, CLI operators do not.

Cache the detect result once per process and share through ctx.obj.

## Fast-path verbs

Must bypass all five phases and return immediately:

- aeat --version / aeat -V
- aeat --help / aeat -h
- aeat config --help
- aeat app --help

Today, --version fires build_cli_version_report() (__init__.py lines 132-137)
which loads the full registry. The is_eager=True on the --version option at
line 96 is correct (fires before subcommand dispatch) but the body is not
fast-path. Fix: replace with typer.echo(f"aeat {__version__}").

build_help_document("root") at line 139 must be verified as pure (i18n strings
only, no state or registry access). Same for build_help_document("app") at
app_app.callback() lines 206-216.

## Interactive-vs-scripted detection contract

Confirmed bright spot from the synthesis audit: the wizard correctly declines
to prompt when stdin is not a TTY.

Contract the root callback must enforce at the unlock phase:

- sys.stdin.isatty() is True: unlock phase may call getpass.getpass() or
  invoke the OS keyring. Interactive prompts are acceptable.
- sys.stdin.isatty() is False: unlock phase must NOT attempt any interactive
  prompt. Check AEAT_SECRET_PASSPHRASE env var (file backend) or query the
  keyring silently. If neither resolves, emit a structured error and exit 2.

Current behaviour: FileFallbackMasterKeyProvider calls getpass.getpass()
directly without a TTY guard. On non-TTY stdin (piped input, CI, scripted
call) the call blocks or crashes. The TTY guard must be promoted to the CLI
bootstrap layer, above the unlock phase.

## Recommended root-callback rewrite shape

Structural constraint for the ADR writer -- not executable code:

    @app.callback()
    def _root(ctx, ...):
        # 1. Always: configure stdio, apply log level, stash format.
        # 2. Fast path: if version -> echo __version__ -> exit
        #    (no state, no registry, no session).
        # 3. Fast path: if help_ -> emit static help -> exit
        #    (no state, no registry, no session).
        # 4. Import-error guard before any state access.
        # 5. Bare invocation: detect only (pointer file + manifest) ->
        #    render landing -> exit. No unlock, no DB access.
        # 6. Subcommand present: _bootstrap_session(ctx) runs
        #    detect -> boot -> unlock -> registers teardown via
        #    ctx.with_resource; dispatch follows automatically;
        #    teardown fires on context exit.

_bootstrap_session(ctx) encapsulates:
1. Detect: read pointer file; check manifest presence; exit 0 with on-ramp
   if no state, exit 2 with structured error if state is corrupt.
2. Boot: validate manifest shape; verify db/aeat.db path; confirm
   AEAT_DATABASE_URL is derivable. Exit 2 + repair route if boot fails.
3. Unlock: select provider via AEAT_SECRET_STORE_BACKEND; check
   sys.stdin.isatty(); acquire passphrase or keyring; open BucketSession;
   register activate_session(session) via ctx.with_resource(...).
4. Return; dispatch handled by typer.

## Open questions for the ADR writer

1. Session lifetime model: per-call stateless (bw-style, token via env var) or
   per-process stateful (existing ContextVar design)? The ContextVar suits an
   autonomous desktop tool. Confirm before committing to either model.

2. Cold-start first-run flow: when detect finds no pointer file and no manifests,
   should _root_landing display the on-ramp screen only, or also trigger the
   wizard?

3. AEAT_DATABASE_URL validator timing (F3): Settings model_validator fires at
   construction time before any routing can intercept it. Options:
   (a) relax to allow empty URL, raise only when DB engine is needed;
   (b) replace with lazy check inside _bootstrap_session.

4. aeat.domain.vat stale import (F11): separate bug but root cause of the
   10-minute hang. ADR should recommend fixing this import as a prerequisite.

5. activate_session as ctx.with_resource: ctx.with_resource() calls __enter__
   immediately and registers __exit__ on cleanup. The contextmanager is designed
   for with blocks. ADR must specify: wrap in a class implementing
   __enter__/__exit__, or use ctx.call_on_close() with explicit token reset.

6. Non-TTY passphrase path: should _bootstrap_session read AEAT_SECRET_PASSPHRASE
   itself (application layer) or should this remain inside
   FileFallbackMasterKeyProvider (adapter layer)?

7. Registry validation warnings: should UserWarning from _validate.py be
   suppressed globally by the CLI bootstrap, or should _validate.py guard its
   own warnings.warn calls so library users see them, CLI operators do not?

## Constraints inherited by the ADR writer

Non-negotiable constraints:

- No shims or compatibility layers (aeat-architecture-boundaries.md).
  The rewrite must move callers to the canonical path.

- No bare invocation may touch encrypted storage until the unlock phase
  completes. Every encrypted-column access goes through get_active_master_key()
  which reads _active_session. Session must be set before any subcommand runs.

- --version and --help are unconditional fast-paths. They must never touch
  the registry, state, engine, or master key.

- Non-TTY stdin must never block on getpass. Passphrase acquisition must check
  sys.stdin.isatty() before any prompt.

- BucketSession.close() must fire on process exit for every non-fast-path
  invocation that successfully opens a session, even if dispatch raises.

- activate_session ContextVar is the only permitted production mechanism for
  passing the DEK to the column-level encrypt/decrypt layer.

- No test fixtures as production fallbacks: EphemeralMasterKeyProvider is
  currently test-only. ADR may promote it to the canonical unsecured backend,
  but must not be an implicit fallback when no backend is configured.

- Detect phase must not perform any decryption. The pointer file and manifest.toml
  are plaintext and exist precisely so active-profile identity is resolvable
  without a session.

- AEAT_SECRET_PASSPHRASE env var is the scripted-path equivalent of the
  interactive getpass prompt. Enforce at the CLI layer, not only in the provider.
