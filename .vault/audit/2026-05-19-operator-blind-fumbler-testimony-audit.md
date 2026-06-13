---
tags:
  - "#audit"
  - "#operator-testimonial"
date: '2026-05-19'
modified: '2026-05-19'
related: []
---

# Operator persona

I am Pedro Fumbler, a Spanish autónomo doing my own books. I know nothing about databases, encryption, or key sessions. I have a NIF, an activity, and a very short patience. I use this tool to set up my tax profile so I can file my declarations.

I tried everything a confused real user would do: typed the wrong NIF, forgot what comes next, ran commands in the wrong order, deleted things I shouldn't, tried to restart when stuck.

# What I tried to mess up

1. Created a profile with a wrong NIF checksum (`12345678X`, correct letter is `Z`)
2. Created a profile with an empty NIF (`--tax-id ""`)
3. Tried to run any command at all with a fresh, empty `AEAT_LOCAL_STORAGE_ROOT`
4. Ran `aeat config repair` and `aeat config repair reset-state --yes` when stuck in the cold-start deadlock
5. Ran `aeat config repair logs` to diagnose what was wrong
6. Ran `aeat config profile show nobody-here` — a nonexistent profile
7. Ran `aeat config profile switch nobody-here` — nonexistent profile
8. Ran `aeat config profile create fumbler-test` in a cold-start environment with no active session
9. Observed CLI startup time when running the first command

# What the tool caught (safe)

**NIF validation (Test 1):** When I passed `--tax-id "12345678X"`, the tool refused cleanly:

```
Refused. NIF/NIE/CIF no válido para wizard.setup.profile.tax-id.prompt: 12345678X.
NIF check letter mismatch: expected 'Z', got 'X'.
  detail: NIF check letter mismatch: expected 'Z', got 'X'
  prompt_key: wizard.setup.profile.tax-id.prompt
  question_id: tax-id
  raw: 12345678X
```

This is good. Clear error, tells me exactly what went wrong and what the right value should be. No traceback. No data loss.

**Empty NIF (Test 2):** When I passed `--tax-id ""`, the tool refused cleanly:

```
Refused. Faltan flags obligatorios para una ejecución del asistente con --quiet.
  flow_id: setup
  missing: ('tax-id',)
```

Also clean. But it says "missing" which is confusing when I deliberately passed an empty string. It treated it as unset.

**Interactive mode in non-TTY (Test 3b):** When I piped stdin instead of using `--quiet`, the tool refused with a friendly message:

```
Refused. No pude abrir el asistente guiado en esta ejecución.
Todavía no se ha guardado nada.
Prueba otra vez el asistente desde una sesión de terminal interactiva:
  aeat config init
...
```

This is correct and safe. It doesn't partially-create a broken profile.

**`repair reset-state` without `--yes` (Test 4b):** Refused cleanly:

```
Refused. Esta operación es destructiva. Vuelve a ejecutar con --yes para confirmar o pasa --dry-run para inspeccionar la huella.
```

Good safety gate.

# What the tool let happen (UNSAFE)

## UNSAFE-1: Cold-start deadlock — Severity 5 (data access completely blocked)

**Scenario:** Fresh installation or fresh `AEAT_LOCAL_STORAGE_ROOT` directory.

**What happens:** Every single CLI command, including `aeat config profile create`, `aeat config repair`, and `aeat config repair reset-state --yes`, fails with the same 80-line SQLAlchemy traceback ending in:

```
sqlalchemy.exc.StatementError: (aeat.adapters.persistence.storage.master_key._active_session.NoActiveBucketSessionError)
no active bucket session; run `aeat config profile switch NAME` to unlock a profile before invoking commands that decrypt stored records.
```

The recovery hint says: `Run aeat config repair`. But `aeat config repair` crashes with the same error. The recovery hint inside `repair reset-state` says `Run aeat config repair`. This is a closed loop. A new user or anyone who has wiped their local directory cannot perform any action whatsoever, including creating a first profile.

The correct bootstrap requires manually creating the `buckets/<name>/` directory structure and `active-profile` pointer file with the correct TOML format. There is no CLI command that does this from zero.

**Severity: 5 — complete lockout, no CLI escape path exists.**

## UNSAFE-2: `aeat config repair logs` crashes with MemoryError — Severity 4

**Scenario:** I ran `aeat config repair logs` hoping to diagnose why everything was broken.

**What happened:** The command loaded the log file (which was large from registry validation warnings), tried to read the entire file into memory at once, and crashed:

```
MemoryError
Internal. The command failed due to an unexpected internal error.
  -> Run `aeat config repair`
  recovery: aeat config repair
```

The operator's diagnostic tool crashes on a large log file, showing a full Python traceback, and refers them back to `aeat config repair` which also crashes. The operator is completely stuck with no actionable path.

**Severity: 4 — diagnostic tool fails on a real-world log file, hides all information.**

## UNSAFE-3: `aeat config repair reset-state --yes` deadlocked by same session requirement — Severity 5

**Scenario:** I ran the documented recovery command `aeat config repair reset-state --yes` to clear a broken workflow state.

**What happened:** Same `NoActiveBucketSessionError` traceback. The reset-state command itself reads from the encrypted secure_objects table before deleting it, requiring the same active session that is causing the problem. The recovery command cannot work in the exact situation it is designed for.

**Severity: 5 — the designated escape hatch is welded shut.**

## UNSAFE-4: Silent CLI startup (no progress indicator) — Severity 3

**Scenario:** I ran any profile command from a cold process.

**What happened:** The CLI produces zero output, zero progress indication, for 10+ minutes while the registry validates itself (loading BOE normatives, traversing binding graphs, emitting semantic_role warnings). A real user would kill the process within 30 seconds, assuming it has crashed.

The `aeat config repair` output (which does complete when a session exists) emits hundreds of lines of `UserWarning: semantic_role ...` diagnostics to stderr. These are not errors but they flood the terminal.

**Severity: 3 — operator kills the process, re-runs it, doubles load time, gives up.**

## UNSAFE-4b: Codebase import is broken (ModuleNotFoundError) — Severity 5

**Scenario:** After 30+ minutes of waiting, the bash-invoked `aeat config profile create` (against a pre-seeded storage root) finally produced output. It was a Python `ModuleNotFoundError`:

```
File "Y:\code\aeat-worktrees\chore-476-restructure-execution\src\aeat\application\aggregation\_iva_ledger.py",
line 24, in <module>
    from ...domain.vat import (
    ...
    )
ModuleNotFoundError: No module named 'aeat.domain.vat'
```

The codebase on this branch (`chore/eliminate-shims`) is in a broken state: `aeat.application.aggregation._iva_ledger` imports from `aeat.domain.vat`, which does not exist. Every CLI invocation eventually crashes during module import — which is what was causing all the "silent 10+ minutes" timeouts in earlier tests. The CLI is currently unusable on this branch from any cold-start path.

The operator's takeaway: "I waited half an hour and then got a Python crash. The tool is broken and I can't even file a bug because I don't know which command broke it."

**Severity: 5 — CLI is completely broken on this branch; every command path crashes during module import. This also revises the meaning of UNSAFE-1: it is not just a session-bootstrap deadlock, it is that no command can run at all on this branch.**

## UNSAFE-5: `--quiet` requires ALL optional fields to be provided — Severity 2

**Scenario:** I tried `aeat config profile create ... --quiet --accept-defaults` with just `--tax-id`, `--name`, `--surnames`, `--activity`. The tool refused with:

```
Refused. Faltan flags obligatorios para una ejecución del asistente con --quiet.
  flow_id: setup
  missing: ('activity',)
```

Wait — I DID provide `--activity`. The issue is that `--quiet` requires more fields than `--accept-defaults` would supply. There is no documentation of which fields are mandatory vs. defaultable when `--quiet` is used. The operator discovers the required fields one error at a time.

**Severity: 2 — annoying, not data-loss, but makes scripting impossible to discover.**

# Stack traces I saw

All verbatim Python tracebacks seen during the operator session:

## Traceback 1: Cold-start profile create / any command

```
2026-05-19 11:00:33,889 [ERROR] aeat.entrypoints.cli._errors: command_error_boundary: unexpected exception in repair_reset_state
Traceback (most recent call last):
  File "...\sqlalchemy\engine\base.py", line 1815, in _execute_context
    context = constructor(...)
  File "...\sqlalchemy\engine\default.py", line 1496, in _init_compiled
    flattened_processors[key](compiled_params[key])
  File "...\aeat\adapters\persistence\storage\crypto\_encrypted_columns.py", line 250, in process_bind_param
    return self.compute(value)
  File "...\aeat\adapters\persistence\storage\crypto\_encrypted_columns.py", line 242, in compute
    key = _resolve_master_key()
  File "...\aeat\adapters\persistence\storage\master_key\_active_session.py", line 93, in get_active_master_key
    raise NoActiveBucketSessionError(...)
aeat.adapters.persistence.storage.master_key._active_session.NoActiveBucketSessionError:
no active bucket session; run `aeat config profile switch NAME` to unlock a profile
before invoking commands that decrypt stored records.

The above exception was the direct cause of the following exception:
  [... 40 more lines of SQLAlchemy internals ...]
sqlalchemy.exc.StatementError: (aeat...NoActiveBucketSessionError) no active bucket session;
run `aeat config profile switch NAME` to unlock a profile before invoking commands that decrypt stored records.
[SQL: SELECT secure_objects.id, secure_objects.namespace, secure_objects.object_key, ...]
[parameters: [{}]]
Internal. The command failed due to an unexpected internal error.
  -> Run `aeat config repair`
  recovery: aeat config repair
```

This traceback was seen for ALL of the following commands in cold-start state:
- `aeat config profile create`
- `aeat config profile list`
- `aeat config profile show`
- `aeat config profile status`
- `aeat config profile switch`
- `aeat config repair reset-state --yes`

## Traceback 2: aeat config repair logs MemoryError

```
2026-05-19 11:07:13,955 [ERROR] aeat.entrypoints.cli._errors: command_error_boundary: unexpected exception in repair_logs
Traceback (most recent call last):
  File "...\aeat\entrypoints\cli\_config\__init__.py", line 90, in repair_logs
    tail = _tail_lines(path, lines) if path.exists() and lines > 0 else ()
  File "...\aeat\entrypoints\cli\_config\__init__.py", line 124, in _tail_lines
    return tuple(path.read_text(encoding="utf-8", errors="replace").splitlines()[-count:])
MemoryError
Internal. The command failed due to an unexpected internal error.
  -> Run `aeat config repair`
  recovery: aeat config repair
```

# Verbatim commands and outputs

## Session 1: Testing NIF validation

```
$ export AEAT_LOCAL_STORAGE_ROOT=Y:/tmp/operator-blind-fumbler
$ export AEAT_SECRET_STORE_BACKEND=unsecured
$ export AEAT_ALLOW_UNENCRYPTED=1

# Test 1: Wrong NIF checksum
$ aeat config profile create fumbler-test --quiet \
    --tax-id "12345678X" --name "Pedro Fumbler" --surnames "Fumbler García" \
    --activity "Consultor" --address-postcode "28001" \
    --taxation-type 1 --output-language es

Exit code: 2
Refused. NIF/NIE/CIF no válido para wizard.setup.profile.tax-id.prompt: 12345678X.
NIF check letter mismatch: expected 'Z', got 'X'.
  detail: NIF check letter mismatch: expected 'Z', got 'X'
  prompt_key: wizard.setup.profile.tax-id.prompt
  question_id: tax-id
  raw: 12345678X
```

## Session 2: Empty NIF

```
$ aeat config profile create nif-empty --quiet --tax-id "" \
    --name "Pedro" --surnames "Fumbler" --activity "Consultor" --accept-defaults

Exit code: 2
Refused. Faltan flags obligatorios para una ejecución del asistente con --quiet.
  flow_id: setup
  missing: ('tax-id',)
```

## Session 3: Cold-start — no active session — every command fails

```
$ aeat config profile create fumbler-test --quiet \
    --tax-id "12345678Z" --name "Pedro Fumbler" --activity "Consultor" --accept-defaults

Exit code: 6
[... 80 lines of SQLAlchemy traceback ...]
sqlalchemy.exc.StatementError: (aeat...NoActiveBucketSessionError) no active bucket session;
run `aeat config profile switch NAME` to unlock a profile before invoking commands that decrypt stored records.
Internal. The command failed due to an unexpected internal error.
  -> Run `aeat config repair`
  recovery: aeat config repair
```

## Session 4: Following the recovery hint — repair is also stuck

```
$ aeat config repair

[... Same 80-line traceback ...]
Internal. The command failed due to an unexpected internal error.
  -> Run `aeat config repair`
  recovery: aeat config repair
```

## Session 5: Trying the escape hatch — reset-state also stuck

```
$ aeat config repair reset-state

Exit code: 2
Refused. Esta operación es destructiva. Vuelve a ejecutar con --yes para confirmar...

$ aeat config repair reset-state --yes

Exit code: 6
[... Same 80-line traceback ...]
sqlalchemy.exc.StatementError: (aeat...NoActiveBucketSessionError) ...
Internal. The command failed due to an unexpected internal error.
  -> Run `aeat config repair`
  recovery: aeat config repair
```

## Session 6: Trying the diagnostic log viewer

```
$ aeat config repair logs

Exit code: 6
[... MemoryError traceback ...]
MemoryError
Internal. The command failed due to an unexpected internal error.
  -> Run `aeat config repair`
  recovery: aeat config repair
```

## Session 7: Show nonexistent profile (before getting a session)

```
$ aeat config profile show nobody-here

Exit code: 6
[... Same 80-line NoActiveBucketSessionError traceback ...]
```

Note: the error is NOT "profile not found" — it crashes before even getting to the lookup.

# Brutal feedback to the developer

**You have built a tool that cannot bootstrap itself.** A fresh install — or any user who points `AEAT_LOCAL_STORAGE_ROOT` at a new directory — is completely locked out with no CLI escape path. The error message tells them to run `aeat config repair`, but repair crashes. `repair reset-state --yes` crashes. `repair logs` crashes. The operator is presented with 80-line SQLAlchemy stack traces for actions as innocent as `profile create`. This is not a UX issue — it is a correctness bug that makes the tool unusable for first-time setup.

The `aeat config profile create` command **must be able to run from a cold-start state**. The session should be created lazily or bootstrapped on first create. `repair reset-state` must not require a session to delete the state that is blocking the session.

`repair logs` reads the entire log file into memory. The log file grows forever and eventually OOMs. Use `tail -n N` semantics, not `read_text().splitlines()[-N:]`.

The CLI takes 10+ minutes to start before showing any output. From a cold process, every single invocation re-validates the entire registry. There is no progress indicator, no spinner, no "Loading..." message. A real user kills the process in under a minute. Add a progress indicator or lazy-load the registry for config commands that don't need it.

NIF validation error messages are excellent. The quality of user-facing error text for successful validation catches is high. This goodness needs to extend to the bootstrap path.

The `--quiet` mode mandatory-field discovery loop is tedious. The error message should tell me ALL missing fields in one shot and suggest a complete example command. It currently tells me one field at a time.
