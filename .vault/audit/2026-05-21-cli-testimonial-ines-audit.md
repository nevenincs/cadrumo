---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-20-cli-testimonial-findings-inventory-audit]]"
---

# CLI testimonial - Ines, adversarial error-probing

## What I was trying to do

I am Ines. I do not read docs. I just click things in the wrong order and hope for the best.
I tried to use this tax CLI by doing everything wrong: running commands before setup, typing
garbage into every field, passing files that do not exist, and generally being a nightmare
user. I wanted to see whether the tool would blow up in my face or tell me something useful.

## My session

Commands run with `AEAT_LOCAL_STORAGE_ROOT` isolated to `.vault-scratch/persona-ines`.
Full verbatim output in `.vault-scratch/persona-ines-cmdlog.txt`.

### T01 - app before any profile (overview status)

Command: `aeat app overview status` (no profile exists yet)

Expected: some error telling me to set up first.

Output:
```
Estado del espacio de trabajo

No hay un perfil activo configurado. Ejecuta `aeat config profile create NAME` antes de importar datos.
Aun no se han importado movimientos bancarios.
...
Que escribir ahora
  aeat app ledger import <extracto-bancario.csv> --provider csv - importar movimientos bancarios.
  aeat --help - volver a la guia de comandos.
```
exit=0

Feeling: Actually fine. It told me what to do. The exit=0 on a "no profile" overview is
a minor policy question but the guidance is useful.

### T02 - ledger list before profile

Command: `aeat app ledger list` (no profile)

Output: `Failed. aeat_database_url is empty; set AEAT_DATABASE_URL.` exit=5

Feeling: The message is confusing. It exposes an internal env-var name (`AEAT_DATABASE_URL`)
that a normal user should never see. The right message is "no profile active, run
`aeat config profile create`". This is an **internal detail leak**.

### T03 - modelo list before profile

Command: `aeat app modelo list` (no profile)

Output: Successfully lists all modelo codes with a full table. exit=0

Feeling: Odd that this works with no profile. It is read-only registry data so it is not
harmful, but it is inconsistent with T02 which failed on a simpler command.

### T04/T05 - profile create with bad NIF / empty NIF

T04: `--tax-id NOTANIF!!!` (missing --activity): `Refused. Faltan flags obligatorios...` exit=2
T05: `--tax-id ""` (missing --activity and --tax-id): same refused exit=2

Feeling: The NIF validation error was masked by the missing `--activity` check. When I
finally provided all required flags (T07), the NIF error surfaced clearly:
`Refused. NIF/NIE/CIF no válido para wizard.setup.profile.tax-id.prompt: NOTANIF!!!.`
That is good. But I had to guess what was missing because the first error only told me
about `activity`, not about the bad NIF.

### T06b - valid profile created

Command: `aeat config profile create ines-test --quiet --accept-defaults --tax-id 12345678Z --name Ines --surnames "Garcia Lopez" --activity "servicios informaticos"`

Output: `profile: ines-test / status: created` exit=0. Fine.

Note: `12345678Z` was accepted. This appears to be a valid NIF letter for that DNI number.

### T07 - bad NIF (all required fields provided)

Output: `Refused. NIF/NIE/CIF no válido... not a valid CIF shape: 'NOTANIF!!!'` exit=2

Feeling: Clear and correct. Good.

### T08 - duplicate profile name

Output: `Refused. El perfil 'ines-test' ya existe; ejecuta aeat config profile switch NAME...` exit=2

Feeling: Perfect. Actionable.

### T09 - `aeat config profile` with no subcommand

Output: Shows the help menu. exit=2 (exit=2 for printing help is slightly odd but tolerable).

### T13 - import nonexistent file (N26 provider)

Output includes a stack trace from the OFX parser library printed to stderr, then a user-facing
`Error. auto-detection of N26 format failed...` exit=1

```
2026-05-20 21:38:09,011 [ERROR] aeat.adapters.inbound.financial.providers._ofx: ofx_provider: failed to parse OFX file doesnotexist.csv
Traceback (most recent call last):
  File "..._ofx.py", line 166, in _load_accounts
    with path.open("rb") as handle:
FileNotFoundError: [Errno 2] No such file or directory: ...
```

Feeling: **Internal detail leak**. The full traceback from the OFX provider reaches the
terminal. The user-facing line is fine but the traceback above it exposes internal paths and
library details. This is a minor-severity internal leak; not a crash since the user-facing
error is also shown.

### T14 - import malformed CSV (N26)

Same traceback pattern as T13, from the OFX parser. exit=1.

Feeling: Same issue. Traceback from third-party library leaks to stdout/stderr.

### T15 - import with nonsense provider name ("FAKEBANKXYZ")

**CRASH.** The CLI failed to even start due to an `ImportError`:
```
ImportError: cannot import name 'DisenoCompletenessCasilla' from 'aeat.domain.calculations.registry._schema'
```
exit=1

Feeling: This is a **blocker**. Passing an unknown `--provider` value triggered a code path
that hit a broken import in the registry module. The error has nothing to do with the bad
provider value. The entire CLI process died before any command logic ran. This is a
structural import bug that the refactoring on this branch has broken.

### T22 - nonsense period with all required args

Output: `Invalid value: period must be YYYY, YYYYQn, YYYY-Qn, or YYYY-MM; got '2024-NOTAPERIOD'` exit=2

Feeling: Clear validation with the expected formats listed. Good.

### T23 - modelo work create with nonexistent modelo code 999

Command: `aeat app modelo work create --modelo 999 --year 2024 --period Q1 --revision v1`

Output: **Created successfully.** exit=0

```
operation	modelo.work.create
work_unit_id	6a6f6bf0e112379385d36bed4f55ff2aa9e216d4ae3609b2acd0e20aa95f8ab7
modelo	999
state	borrador
```

Feeling: **Silent wrong behaviour**. Modelo `999` does not exist in the registry. The work
unit was created without any validation that the modelo code is valid. The error only surfaces
later when you try to `calculate` (T30). A work unit for a phantom modelo can sit in the
database indefinitely without being actionable.

### T30 - calculate on the phantom modelo 999 work unit

Output: `Invalid value: registry snapshot for modelo='999' year=2024 period='1T' could not be resolved: modelo '999' is not present in the calculation registry` exit=2

Feeling: At least the error is clear at calculate time. But it should have been caught at
`work create` time.

### T35 - normal calculate on 303

Works. Outputs casilla table. exit=0. Good.

### T36 - file before verifying

Output: `Invalid value: calculation revision '...' is in state 'borrador'; only VERIFICADO_COMPLETO revisions can be filed` exit=2

Feeling: Excellent state-machine guard.

### T37 - verify with no filing obligation

Output: `Invalid value: workflow gate aborted ... reason='NO_PENDING_OBLIGATION': No pending filing obligation for this profile` exit=2

Feeling: Clear, with a diagnostic code. Good.

### T40 / T41 - ledger allocate with business-pct > 1 or negative

Both got `Invalid value: El prefijo de id %'fakeid123' contiene caracteres no hexadecimales` exit=2.

Feeling: The id validation ran first, masking the business-pct check. Business-pct > 1 or < 0
was **never validated** because the id check blocked first. This is an ordering concern; if a
user has a valid hex id but passes `--business-pct 1.5` or `-0.5` the outcome is unknown.

### T42 - ledger allocate with business-pct as plain text ("NotANumber")

**CRASH.** Another `ImportError`:
```
ImportError: cannot import name 'DerivedManifestCasilla' from 'aeat.domain.calculations.registry._record_design'
```
exit=1

Feeling: **Blocker**. Different broken import triggered by a different code path. The text
value `NotANumber` apparently sent Click down a different parse branch that hit a second
broken registry import. Again, totally unrelated to the input error.

### T46 - import empty file

Stack trace from OFX library, then user-facing error. exit=1. Same traceback leak as T13/T14.

### T49 - import CSV with wrong column names for N26 (e.g. "Date,Description,Amount,Balance")

**Silent wrong behaviour.** The N26 provider accepted a non-N26 CSV without complaint.
`Filas 2 / Entradas importadas 2 / Omitidos 0` exit=0

The transactions were stored with amounts and dates parsed from the wrong column mapping.
No warning that the column names did not match the N26 schema was issued.

### T51 - ledger update with iva-rate = 999 (900% IVA)

Command: `aeat app ledger update --id b2fd2ab2 --iva-rate 999`

Output: Shows the transaction record. exit=0

Viewing the record after the update shows the view command output but the iva_rate field
does not appear in the view output (no iva_rate line shown), so it is unclear whether 999
was stored or silently ignored. Regardless, **no validation error was raised** for an
obviously impossible IVA rate of 999 (900%).

### T55 - registry inspect with nonexistent directory

Command: `aeat app registry inspect --registry-root /tmp/doesnotexist`

Output: Prints all zeros for all counts. exit=0

Feeling: **Exit-0 on bad input**. The path does not exist but the command reports zero
results as if it performed a valid scan. No warning that the path was not found.

### T63 - profile create with path-traversal name ("../../evil-name")

Output: Internal traceback followed by user-facing `Internal. The command failed due to an unexpected internal error.` exit=6

```
ValueError: bucket_id must not contain a path separator
Internal. The command failed due to an unexpected internal error.
  -> Run `python -m aeat.diagnostics report`
```

Feeling: **Not a full crash** (exit=6 is a controlled internal error code, user-facing message
is shown) but the internal traceback reached stderr including full file paths. The validation
happens too late (inside bucket provisioning) instead of at the input layer. The recovery
hint `python -m aeat.diagnostics report` is a developer command, not a user-friendly action.

### T71 - live filed list (safety gate)

Output: `Refused. live AEAT reads require AEAT_LIVE_TESTS_ENABLED=1; current value: 'true'` exit=2

Note: the gate checked for the string literal `"1"` but the env had `"true"`. This blocked
the live call correctly (the gate is strict). Whether `"true"` should be accepted is a policy
question.

## Did it fail safely?

Mostly yes. The majority of wrong inputs got a clear `Refused.` or `Invalid value:` message with
exit=2. State-machine guards on the modelo lifecycle (file before verify, calculate before
verify) worked well. NIF validation, duplicate profile detection, hex prefix validation, period
syntax checks, and unknown command rejection all behaved correctly.

The unsafe failures are:
- Two distinct `ImportError` crashes on specific input patterns (T15, T42) — these indicate
  broken imports in the registry module introduced by the current branch refactoring.
- OFX parser tracebacks leaking to the terminal on any failed import (T13, T14, T46).
- Silent acceptance of a nonexistent modelo code at work-unit creation time (T23).
- Silent acceptance of a wrong-format CSV by the N26 importer (T49).
- No validation of impossible IVA rates (T51).
- `registry inspect` returning exit=0 and zeroed output for a nonexistent directory (T55).
- Path-traversal profile name producing an internal error instead of input validation (T63).

## Bugs and gaps

1. **CRASH — broken import on unknown `--provider` value (T15)**
   Command: `aeat app ledger import /tmp/junk.csv --provider FAKEBANKXYZ`
   Expected: `Invalid value: unknown provider 'FAKEBANKXYZ'` exit=2
   Actual: `ImportError: cannot import name 'DisenoCompletenessCasilla' from 'aeat.domain.calculations.registry._schema'` exit=1
   Severity: **BLOCKER** — the CLI cannot start when this code path is reached; a structural
   import is broken in the current branch state.

2. **CRASH — broken import on non-numeric `--business-pct` (T42)**
   Command: `aeat app ledger allocate --id fakeid123 --business-pct NotANumber`
   Expected: `Invalid value: NotANumber is not a valid decimal for --business-pct` exit=2
   Actual: `ImportError: cannot import name 'DerivedManifestCasilla' from 'aeat.domain.calculations.registry._record_design'` exit=1
   Severity: **BLOCKER** — second distinct broken import on a different code path.

3. **Internal detail leak — `aeat_database_url` env-var exposed to user (T02)**
   Command: `aeat app ledger list` with no profile active
   Expected: "No active profile. Run `aeat config profile create`."
   Actual: `Failed. aeat_database_url is empty; set AEAT_DATABASE_URL.`
   Severity: **Major** — exposes internal configuration detail; not actionable for a normal user.

4. **Internal traceback leak — OFX parse failures printed to terminal (T13, T14, T46)**
   Command: `aeat app ledger import <any non-OFX file> --provider N26`
   Expected: user-facing error only, no traceback
   Actual: full Python traceback from `ofxparse` third-party library printed before the
   user-facing error line
   Severity: **Major** — leaks internal file paths and third-party library internals.

5. **Silent wrong behaviour — modelo work create accepts nonexistent modelo code (T23)**
   Command: `aeat app modelo work create --modelo 999 --year 2024 --period Q1 --revision v1`
   Expected: `Invalid value: modelo '999' is not in the registry` exit=2
   Actual: Work unit created silently with `modelo=999`. Error only surfaces at calculate time.
   Severity: **Major** — creates a zombie work unit that can never be completed.

6. **Silent wrong behaviour — N26 importer accepts non-N26 CSV without warning (T49)**
   Command: `aeat app ledger import file.csv --provider N26` where file has `Date,Description,Amount,Balance` headers
   Expected: parse error or at least a warning that column names did not match N26 schema
   Actual: `Filas 2 / Entradas importadas 2` exit=0, no warning
   Severity: **Major** — tax data ingested silently from the wrong format; ledger integrity
   is compromised.

7. **No validation of impossible IVA rates (T51)**
   Command: `aeat app ledger update --id b2fd2ab2 --iva-rate 999`
   Expected: `Invalid value: iva-rate must be between 0 and 1 (or 0-100 as percentage)`
   Actual: exit=0, no error. Whether 999 was persisted is unclear from the view output.
   Severity: **Major** — allows entry of a 900% IVA rate without complaint.

8. **Exit-0 on nonexistent registry root (T55)**
   Command: `aeat app registry inspect --registry-root /tmp/doesnotexist`
   Expected: error or warning that the path does not exist exit=1
   Actual: zeroed counts, exit=0
   Severity: **Minor** — misleading but read-only.

9. **Path-traversal profile name causes internal error too late (T63)**
   Command: `aeat config profile create "../../evil-name" ...`
   Expected: `Invalid value: profile name must not contain path separators` exit=2 (at CLI
   argument parsing)
   Actual: internal traceback reaching stderr + `Internal. The command failed...` exit=6.
   The ValueError is only caught inside bucket provisioning, not at the CLI input layer.
   Severity: **Minor** — does not succeed so no data escapes, but the error path is wrong
   and the internal traceback leaks file paths.

10. **Inconsistent behaviour — ledger list fails without profile, modelo list succeeds (T02 vs T03)**
    Both are `app` commands. T02 (`ledger list`) fails with an internal env-var error.
    T03 (`modelo list`) succeeds because it reads static registry data.
    The inconsistency is confusing; both should either require a profile or explain why one
    does not.
    Severity: **Minor** — no data loss, just inconsistent UX.
