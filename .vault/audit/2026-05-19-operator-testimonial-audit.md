---
tags:
  - '#audit'
  - '#operator-testimonial'
date: '2026-05-19'
modified: '2026-05-19'
related: []
---

# Operator persona

I am a Spanish autónomo (consultor) who evaluates tools carefully before trusting them with real
tax data. I am comfortable with a terminal but I am not a developer. I read every `--help` page.
I expect: clear on-disk layout, stable `--format json` output for scripting, and explicit
confirmation of what was written and where. I am frustrated by hidden state, opaque errors, and
commands that silently fail.

Environment: fresh `Y:/tmp/operator-blind-curious/` as `AEAT_LOCAL_STORAGE_ROOT`,
`AEAT_SECRET_STORE_BACKEND=unsecured`, `AEAT_ALLOW_UNENCRYPTED=1`, no prior state.

---

# What I tried to inspect

1. `aeat --help` — top-level command surface.
2. `aeat --version` — version string.
3. `aeat config profile create investigator --quiet --tax-id 12345678Z ...` — first profile.
4. `aeat config profile list`, `show`, `switch investigator` — profile inspection.
5. `aeat config profile status` — first-run readiness check.
6. `aeat config repair` — diagnostics.
7. On-disk layout: `ls -laR $AEAT_LOCAL_STORAGE_ROOT`.
8. Contents of `active-profile` pointer file.
9. Contents of `aeat.db` SQLite schema.
10. `aeat app overview status --format json` — JSON output check.
11. `aeat config profile export --to /tmp/bundle.json` — portability check.
12. `python -m aeat.diagnostics --help` — engineer diagnostic surface.

---

# What was transparent and reassuring

- `aeat --help` renders a clean two-section layout (`config` for setup, `app` for daily work).
  The grouping is logical and the Spanish bilingual labels are consistent.
- `aeat config profile create --help` exposes every field as a named flag with a description.
  No hidden required arguments; `--quiet` with all flags is the scripting path.
- The `active-profile` pointer at `<root>/active-profile` is human-readable TOML:
  `bucket_id = "investigator"` and `schema_version = 1`. Exactly what an operator needs
  to understand which profile is active.
- The `secure_objects` table in SQLite has clear metadata columns: `namespace`,
  `object_key`, `classification`, `schema_version`, `written_at`. Payloads are encrypted
  but the structural metadata is plain text and inspectable with any SQLite browser.
- The `aeat config repair` command emits a detailed plaintext report covering registry
  health, missing corpus files, and dependency sync status. The format is readable.
- The `--format json` rendering code is well-designed: handles `Path`, `datetime`,
  `Decimal`, pydantic models. JSON output would be reliable if commands could run.
- The NIF-canary (refusing real-looking NIFs in unsecured mode) is a legitimate
  safety gate. It is documented in source. The allow-list of synthetic test NIFs is small
  and explicit.
- The `profile export` command tells the caller exactly where it wrote the bundle:
  `profile_id`, `out`, and `schema_version` are emitted — no hidden file placement.

---

# What was opaque or suspicious

## Finding 1 — Severity 5: CLI is completely unusable standalone (no session bootstrap)

Every CLI command fails immediately with:

```
NoActiveBucketSessionError: no active bucket session;
run `aeat config profile switch NAME` to unlock a profile before invoking commands
that decrypt stored records.
```

This happens on `profile create`, `profile list`, `profile switch`, `profile status`,
`config repair` (at the command level), and `app overview status`. The error message
says to run `profile switch`, but `profile switch` itself raises the same error.
There is no CLI code path that calls `get_master_key_provider()` to bootstrap the
session. The test suite bootstraps sessions externally with `with get_master_key_provider():`.
For an operator running the CLI directly — with any backend — the tool is inert.
This is a severity-5 gap: I would not trust a tool where the first command I try
is met with a circular error.

## Finding 2 — Severity 4: `AEAT_DATABASE_URL` required but undocumented

Before the session error, the tool refuses with:

```
Failed. aeat_database_url is empty; set AEAT_DATABASE_URL.
```

No `--help` text mentions this variable. The `aeat config repair` output does not
list it as a missing configuration item. There is no getting-started document.
A new operator would have no idea what value to set. (Is it the per-bucket DB path?
A shared DB path? For what purpose does a "local filesystem" tool need a raw
SQLite URL injected by the operator?)

## Finding 3 — Severity 3: Startup emits six internal `UserWarning` lines to stderr

Before any command output, the registry loading phase emits:

```
UserWarning: semantic_role 'payee_country' appears on exactly one casilla ...
UserWarning: semantic_role 'intracomunitario_nif_iva' appears on exactly one ...
[... 4 more ...]
```

These are internal registry-validation notices, not operator-facing diagnostics.
An operator running `aeat --version` gets six lines of internal warning before seeing
`aeat 0.1.0`. This erodes confidence immediately.

## Finding 4 — Severity 3: Startup latency is high (~10-30 seconds for simple commands)

Every invocation loads the full calculation registry at import time. Even
`aeat --version` or `aeat --help` — commands with no business logic — take a long
time to start because the registry validation runs unconditionally. Commands that should
complete in <1 second routinely time out at the 10-20 second range in this environment.

## Finding 5 — Severity 2: No `buckets/<id>/manifest.toml` in the operator filesystem

The architecture documents (and source code for `_manifest.py`) describe a
`<root>/buckets/<bucket-id>/manifest.toml` file containing plaintext KDF parameters.
This file does not appear in the operator storage root. The unsecured backend bypasses
the bucket-directory creation and stores everything in a single root-level `aeat.db`.
An operator expecting to inspect `manifest.toml` to understand their encryption
setup — as the documentation implies — would find nothing.

## Finding 6 — Severity 2: `config repair` floods stdout with hundreds of registry warnings

Running `aeat config repair` with a database URL set produced ~470 KB of output
consisting almost entirely of "missing corpus file" warnings for legal normatives
(ley-35-2006, ley-37-1992, etc.). These are expected-missing files in a development
install. An operator running repair to diagnose a real problem cannot find the signal
among the noise. The repair report does not indicate which findings are fatal vs
expected-missing in a standard install.

## Finding 7 — Severity 2: NIF canary conflict with typical test NIFs

`12345678Z` is a structurally valid Spanish NIF (12345678 mod 23 = 14 = letter Z).
The unsecured backend's NIF-canary would refuse this as a "real" NIF, making the
suggested onboarding flow (create a test profile with a simple test NIF) fail silently
at a layer below the session error. The allow-list of known-synthetic NIFs
(`00000000T`, `X0000000T`) is not communicated to operators anywhere in the CLI.

## Finding 8 — Severity 1: `python -m aeat.diagnostics` does not exist

The engineer diagnostic surface is `aeat.application.diagnostics` (a module), not a
`__main__` runnable. `python -m aeat.diagnostics` fails immediately.

---

# On-disk layout findings

```
Y:/tmp/operator-blind-curious/
├── active-profile      (48 bytes, TOML)
└── aeat.db             (90 KB, SQLite)
```

The `active-profile` file:
```toml
bucket_id = "investigator"
schema_version = 1
```
Human-readable. Good.

The `aeat.db` SQLite tables:
- `secure_objects` (3 rows after manual Python API bootstrap)
  - namespaces: `aeat.application.user_profile.value`, `aeat.domain.buckets.event_history`,
    `aeat.workflow`
  - payloads: encrypted binary blobs (correct; ZERO confidentiality only in unsecured mode)
  - metadata columns plaintext and inspectable
- `modelos`, `rental_fincas`, `portals`, `corpus_artifacts`, `rental_contracts`,
  `rental_expenses`, `rental_amortization_ledger`, `rental_income_records` (all 0 rows)

**No `buckets/` directory was created.** The architecture's per-bucket filesystem layout
described in `_manifest.py` was not materialised by the unsecured backend path. An operator
expecting to find `buckets/investigator/manifest.toml` would find nothing.

**Surprising file: nothing surprising was found on disk.** There are no hidden dot-directories,
no token files, no credentials. The storage root is minimal.

---

# JSON-format spot checks

No `--format json` command completed successfully. Every command failed before producing
output due to `NoActiveBucketSessionError`. Therefore:

- `aeat config profile list --format json`: **DID NOT RUN** (session error)
- `aeat config profile show --format json`: **DID NOT RUN** (session error)
- `aeat app overview status --format json`: **DID NOT RUN** (session error)

The underlying JSON rendering code (`core/output_rendering.py`) was inspected directly.
It is well-designed: `json.dumps` with a `_json_default` fallback handling `Path`,
`date`, `datetime`, `Decimal`, and `set`/`frozenset`. Pydantic models are serialised
via `model_dump(mode="python")`. This code would produce valid JSON if the commands
could execute. But no JSON output was observed at runtime.

---

# Verbatim commands and outputs

```
# Step 1: Create profile
$ AEAT_LOCAL_STORAGE_ROOT=Y:/tmp/operator-blind-curious \
  AEAT_SECRET_STORE_BACKEND=unsecured AEAT_ALLOW_UNENCRYPTED=1 \
  aeat config profile create investigator --quiet --tax-id 12345678Z \
  --name Investigador --activity "Consultoría" --iva-regime GENERAL

Failed. aeat_database_url is empty; set AEAT_DATABASE_URL.

# Step 2: Retry with AEAT_DATABASE_URL
$ AEAT_DATABASE_URL="sqlite:///Y:/tmp/operator-blind-curious/aeat.db" \
  [same as above]

Exit code 6
NoActiveBucketSessionError: no active bucket session;
run `aeat config profile switch NAME` to unlock a profile ...

# Step 3: Try the suggested recovery
$ aeat config profile switch investigator

[same NoActiveBucketSessionError]

# Step 4: Try the repair command
$ aeat config repair
[~470 KB of registry missing-corpus warnings]
Next label: Inspect registry toml
warn: runtime.dependency_sync Venv stale
Next label: uv sync

# Step 5: Check version
$ aeat --version
aeat 0.1.0
[preceded by 6 UserWarning lines about semantic_role typos]

# Step 6: On-disk layout after manual Python API bootstrap
$ ls -laR Y:/tmp/operator-blind-curious/
active-profile  (48 bytes)
aeat.db         (90 KB)

$ cat Y:/tmp/operator-blind-curious/active-profile
bucket_id = "investigator"
schema_version = 1
```

---

# Brutal feedback to the developer

**The CLI cannot be used as a standalone tool.** Every command — including the first-run
`create` command — requires an active bucket session. The session is established by
calling `get_master_key_provider()` as a context manager, but this call appears nowhere
in production CLI code. It exists only in test fixtures. This means the CLI is currently
a library façade, not an operator-facing tool. An operator who follows the README (if
one existed), sets their environment variables, and runs `aeat config profile create`
will be met with a circular error pointing to a command that also fails.

The error message "run `aeat config profile switch NAME`" is actively misleading.
`profile switch` does not establish a session — it also fails with the same error.
This is the kind of circular failure that destroys trust immediately.

**`AEAT_DATABASE_URL` must be documented or auto-derived.** The per-bucket architecture
suggests the tool should create its own SQLite file under `AEAT_LOCAL_STORAGE_ROOT`.
Why does an operator need to supply a raw SQLite URL? If this is a legacy migration
artifact, remove it. If it is intentional, document it prominently.

**Registry warnings on stderr contaminate every command invocation.** Six
`UserWarning` lines before `aeat --version` output tells an operator that the
internals are leaking. These should be suppressed or routed to the log file, not
to the operator-facing terminal.

**Startup time is unacceptable for a CLI.** A tool that takes 10-30 seconds to
respond to `--help` will not be used daily by an autónomo. The registry must be
loaded lazily, not at import time.

**The `aeat config repair` signal-to-noise ratio is 1:100.** Hundreds of
"missing corpus file" notices for legal texts that are never shipped obscure
any real diagnostic signal. Either ship the corpus, remove the references, or
filter expected-missing items from the repair report.

**The NIF-canary allow-list must be visible to operators.** If the tool refuses
common test NIFs without explaining why, operators will assume the tool is broken.
Print a one-line hint: "use a synthetic NIF like 00000000T for test profiles."
