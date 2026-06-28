---
tags:
  - "#audit"
  - "#operator-testimonial"
date: '2026-05-19'
modified: '2026-05-19'
related: []
---

# Operator persona

María, autónoma, fontanera. Set up the tool last week with NIF `12345678Z`, régimen
IVA general, actividad Fontanería. Coming back on a Monday morning to check where she
left off and import last week's bank statement.

She vaguely remembers: `create`, `show`, `switch`. Does not remember the profile name.
Does not type English. Is using `AEAT_SECRET_STORE_BACKEND=unsecured` because a
colleague told her it is the simpler mode.

# What I tried to do

1. Run `aeat` bare — expected to see "you are logged in as X" or a dashboard.
2. Figure out what profile is active and what state I am in.
3. Run `aeat config profile list` to rediscover my profile name.
4. Run `aeat config profile show` to see my profile data.
5. Run `aeat app overview` and `aeat app overview status`.
6. Try `aeat app ledger import` to import a bank statement.
7. Explore `aeat config profile edit` and `aeat config profile logout`.

# What worked

- `aeat --help` rendered a clean, well-structured overview with four sections (setup,
  daily ledger, modelo lifecycle, diagnostics). The section grouping is good.
- `aeat config --help` correctly listed all profile lifecycle verbs under labelled
  sections (`first run`, `profile lifecycle`, `profile inspection`, `authentication`,
  `diagnostics`). The section labels are helpful.
- `aeat app ledger --help` showed a comprehensive verb list in Spanish. All verbs
  have one-line descriptions.
- `aeat config profile edit --help` exists and accepts the same flags as `create`.
  Good symmetry.
- `aeat config profile logout --help` exists with a clear one-line description
  (`Cierra la sesión del perfil activo limpiando el puntero local`).
- `aeat app overview status --help` showed `--period` and `--verbose`. Clean.

# What hurt

**PAIN-1 — The CLI is completely unusable without an active session (SEVERITY: 5/5 — I would uninstall)**

Every command that touches the database — including `profile create`, `profile list`,
`profile switch`, `profile status`, and even the bare `aeat` root command — crashes
with `NoActiveBucketSessionError`. The CLI tells me to run
`aeat config profile switch NAME` to fix this. But `profile switch` crashes with
the same error. It is a deadlock. There is no path from a fresh shell to any working
state. `AEAT_SECRET_STORE_BACKEND=unsecured` and `AEAT_ALLOW_UNENCRYPTED=1` are both
set; the unsecured provider is configured; but the CLI never calls its `__enter__`
lifecycle method before trying to decrypt the first row. This is the single most
severe bug in the current branch.

**PAIN-2 — Bare `aeat` dumps a raw Python stacktrace (SEVERITY: 4/5)**

When no session is active, `aeat` (with no subcommand) does not show a friendly
"please log in" screen. It throws a 60-line SQLAlchemy traceback with internal module
paths, ORM internals, and a dead-end recovery hint (`aeat config repair`). A new
operator will think the tool is broken or uninstalled incorrectly. The only command
that succeeds without a session is `aeat --help`.

**PAIN-3 — `aeat config repair` hangs on stdin without a session (SEVERITY: 4/5)**

The error text says "Internal error → run `aeat config repair`". Running repair
hangs indefinitely — it is an interactive command that waits for stdin input. An
operator following the recovery instruction will have a frozen terminal with no
explanation. There is no `--non-interactive` flag and no timeout.

**PAIN-4 — `profile show` vs `profile view`: inconsistent verb in help vs command (SEVERITY: 2/5)**

The `aeat config` section lists `aeat config profile view [NAME]` as "Profile view".
But the actual command is `aeat config profile show` (as revealed by `--help`). The
top-level summary and the actual verb disagree. I would try `view`, get an error or
different output, and not understand why.

**PAIN-5 — Enum values in `--iva-regime` are truncated in help tables (SEVERITY: 2/5)**

In `profile create --help` and `profile edit --help`, the enum column for
`--iva-regime` is truncated: `[GENERAL|SIMPLI FICADO|RECARGO_ EQUIVALENCIA|EX ENTO]`.
The line-breaks fall mid-word inside the table cell. The first run with `--iva-regime
general` (lowercase) was also silently rejected with only the enum values listed —
no hint that the values must be SCREAMING_SNAKE_CASE. First-run failure before any
data is written.

**PAIN-6 — `profile create` requires a session that does not yet exist (SEVERITY: 5/5 — same root as PAIN-1)**

`profile create` is the "First run bootstrap" command per `aeat config --help`. Yet
it calls `workflow_state_repository().load()` before writing anything, which requires
an active bucket session. A completely fresh setup — no database, no existing profile,
first ever run — immediately fails with the deadlock error. There is no
"database is empty, bootstrapping" path. This makes the tool impossible to set up
without a developer workaround.

**PAIN-7 — No "currently active profile" line anywhere (SEVERITY: 3/5)**

None of the help screens, error messages, or the bare-`aeat` output show who is
currently logged in. Coming back after a week, the first thing I want is "Active:
maria-plomera". There is no such indicator. I would have to remember the profile name
I gave it last week and type it into `profile switch`, which also crashes (PAIN-1).

# Verbatim commands and outputs

```
$ aeat
[60-line SQLAlchemy traceback]
sqlalchemy.exc.StatementError: (aeat.adapters.persistence.storage.master_key._active_session.NoActiveBucketSessionError) no active bucket session; run `aeat config profile switch NAME` to unlock a profile before invoking commands that decrypt stored records.
Internal. The command failed due to an unexpected internal error.
  -> Run `aeat config repair`
  recovery: aeat config repair
EXIT: 6

$ aeat config profile create maria-plomera --tax-id 12345678Z --activity "Fontanería" --iva-regime general --quiet
Invalid value for '--iva-regime': 'general' is not one of 'GENERAL', 'SIMPLIFICADO', 'RECARGO_EQUIVALENCIA', 'EXENTO'.
EXIT: 2

$ aeat config profile create maria-plomera --tax-id 12345678Z --activity "Fontanería" --iva-regime GENERAL --quiet
[60-line stacktrace, same NoActiveBucketSessionError]
EXIT: 6

$ aeat config profile switch maria-plomera
[60-line stacktrace, same NoActiveBucketSessionError]
EXIT: 6

$ aeat config profile list
[60-line stacktrace, same NoActiveBucketSessionError]
EXIT: 6

$ aeat config repair
[hangs, waiting for stdin, no output, no timeout]
^C

$ aeat --help
[clean 4-section help, EXIT: 0]

$ aeat config profile switch --help
 Usage: aeat config profile switch [OPTIONS] NAME
 Activa un perfil existente
EXIT: 0
```

# Brutal feedback to the developer

The unsecured backend is completely broken as a CLI entry point in this branch.
Every single database-touching command fails immediately because the unsecured
master-key provider `__enter__` is never called by the CLI lifecycle. The tests work
because each fixture wraps the invocation in `with get_master_key_provider():`. The
production CLI has no equivalent. The effect is that no operator can run any command
after a fresh shell — not create, not list, not switch, not repair. The error message
tells the operator to run `switch`, but `switch` fails with the same error. The
recovery hint is a lie.

Before any UX polish, this deadlock must be fixed. The fix is probably: the CLI
entrypoint should call `get_master_key_provider().__enter__()` at startup when the
unsecured backend is configured, or alternatively `profile switch` should not require
an active session to read the profile list. Either path unblocks everything.

The help text structure (sectioned, Spanish, short verbs) is genuinely good. Once the
session lifecycle is fixed, the discoverability will be acceptable. The verb mismatch
(`view` vs `show`) and the truncated enum help table are minor polish issues. The
missing "active profile" indicator in the bare-`aeat` output is a real quality-of-life
gap for returning operators, but it is a P2 after the P0 deadlock is resolved.
