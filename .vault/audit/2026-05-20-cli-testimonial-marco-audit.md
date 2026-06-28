---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# CLI testimonial - Marco, bookkeeper

## What I was trying to do

I keep the books for three small Spanish businesses. I have a quarter of bank
transactions (Q1 2026, 14 entries) and I wanted to:

1. Create a profile for my practice (autónomo, IVA general, Madrid).
2. Import the Q1 bank extract into the ledger.
3. Classify the business transactions (IVA 21 %, alquiler, suministros, ingresos).
4. See the ledger status to confirm the quarter is accounted for.

The tool advertises this as the "daily ledger" workflow on its help screen.

## My session

### Step 1 — Discover the tool

**Command:** `aeat --help`

Expected: a clear menu of available commands.

Actual:

```
aeat - local-first Spanish tax workflow

The CLI has exactly two roots: config and app.
Use config for local state and app for tax work.

Section setup
  aeat config profile create NAME  Setup create profile
  ...
Section daily ledger
  aeat app ledger import    Ledger import
  aeat app ledger list      Ledger list
  aeat app ledger view      Ledger view
  aeat app ledger status    Ledger status
  ...
```

Felt good. Clear two-root structure, named sections. The "daily ledger"
section is exactly what I need.

---

### Step 2 — Create a profile (first attempt with wrong option name)

**Command:**
```
aeat config profile create marco-contabilidad --quiet \
  --tax-id "B12345678" --name "Marco" --surnames "García Fernández" \
  --activity "Asesoría contable y fiscal" --address-postcode "28001" \
  --taxation-type 1 --output-language en --iva-regime GENERAL \
  --tax-residence-community madrid
```

Expected: profile created.

Actual:
```
Error. No such option: --tax-residence-community Did you mean --tax-residence-ccaa?
```

The `--help` output truncated the option name to `--tax-residence-ccaa…`
(the full name is cut off at 20 characters with an ellipsis in the help
table). I had to guess. The suggestion in the error was helpful and I
recovered quickly.

Friction: **minor** — truncated option names in help table.

---

### Step 3 — Create a profile (wrong CIF check digit)

**Command:** same as above but using `--tax-residence-ccaa madrid`

Actual:
```
Refused. NIF/NIE/CIF no válido para wizard.setup.profile.tax-id.prompt: B12345678.
CIF check digit mismatch (digit-only kind 'B'): expected '4', got '8'.
```

Expected: either accept a test CIF or give a clearer error message.

The error is technically correct — `B12345678` is not a valid CIF. However,
the error exposes internal keys (`wizard.setup.profile.tax-id.prompt`,
`question_id`, `prompt_key`, `raw`) in the user-facing output. That looks
like a debug dump, not a user message.

I corrected to `B12345674` (valid check digit) and it worked silently (no
output on success).

Friction: **minor** — valid CIF rejection with internal debug keys exposed.
Also: **cosmetic** — no success confirmation after `--quiet` profile creation.

---

### Step 4 — Verify profile created

**Command:** `aeat config profile show marco-contabilidad`

Actual: printed a full key/value table of all profile fields. Looked good.
Profile was active, all values I supplied were present.

Felt fine.

---

### Step 5 — Discover import format

**Command:** `aeat app ledger import --help`

Expected: list of supported providers and expected file format.

Actual: help text shows `--provider TEXT` (required) with description
"Proveedor del formato del extracto (p. ej., N26, Revolut)" but **no list
of accepted provider names**.

I tried `--provider INVALID_PROVIDER` and got:
```
Error. unknown ledger provider: INVALID_PROVIDER
```

No list of valid providers. I then tried `revolut` (unknown), `bbva`
(unknown), `sabadell` (unknown), `santander` (unknown), `caixabank`
(unknown), `bankia` (unknown), `ing` (unknown), `openbank` (unknown),
`bunq` (unknown), `wise` (unknown), `monzo` (unknown). Only `n26` was
recognized.

The error on `n26` (when pointing at a missing file) revealed an OFX
parser in the stack trace, so I knew I needed an OFX file.

Friction: **major** — `--provider` accepts only `n26` (so far discovered)
and the help text gives no enumeration of valid values. A real user with
any other bank would be completely stuck.

---

### Step 6 — Create OFX fixture and import

I constructed a standard OFX 1.02 file with 14 realistic Q1 2026
transactions (alquiler, telefonía, suministros, material de oficina,
pagos de clientes, pago a AEAT).

**Command:**
```
aeat app ledger import q1-2026-transacciones.ofx --provider n26 --verbose
```

Actual:
```
Filas                  14
Entradas importadas    14
Omitidos               0
Válido                 Sí
Formato detectado      accounts=ES7620770024003102575766
```

This worked perfectly. Clean output, all 14 rows imported.

---

### Step 7 — Check ledger status

**Command:** `aeat app ledger status`

Actual:
```
Bucket                     marco-contabilidad
Filas                      14
Activas                    14
Archivadas                 0
Apartadas                  0
Pendientes de revisión     14
Revisadas                  0
Omitidos                   0
```

Felt great. All 14 rows are pending review, ready for classification.

---

### Step 8 — List ledger entries

**Command:** `aeat app ledger list`

Actual: printed 14 rows with short ID, full hash, date, amount, memo,
and `pending` status. The short ID (8 hex chars) is usable.

Felt fine, though a more tabular layout would be nicer.

---

### Step 9 — Classify transactions

**Command:**
```
aeat app ledger classify --id c68eb0c6 --classification BUSINESS \
  --taxable-base 100.00 --iva-rate 0.21 --iva-amount 21.00
```

Actual:
```
ID                  c68eb0c614bbdcafbab758c9e7b223b689a63dc81238ad9522e3966df8f7cec5
Fecha               2026-01-03
Importe             -121
Descripción         Factura telefono oficina enero 2026 - IVA 21%
Estado de revisión  reviewed
```

Worked. I classified 5 more transactions (rent x3, office supplies,
two income entries). All returned `reviewed` without error.

Felt good — the short 8-char prefix ID is accepted, no need to type 64
hex chars.

---

### Step 10 — View a single transaction (CRASH)

**Command:** `aeat app ledger view --id c68eb0c6`

Actual:
```
Error. No such option: --id
```

The `view` command takes a positional argument, not `--id`. I corrected:

**Command:** `aeat app ledger view c68eb0c6`

Actual:
```
ModuleNotFoundError: No module named 'aeat.application.workflow._bucket_pointer_io'
```

Python traceback. The entire CLI is now dead — even `aeat --help` crashes
from this point forward with the same `ModuleNotFoundError`.

Full traceback chain:
```
aeat.entrypoints.cli.__init__
  → aeat.application.diagnostics (line 35)
    → aeat.application.workflow._profile_health (line 12)
      → ModuleNotFoundError: No module named
           'aeat.application.workflow._bucket_pointer_io'
```

Previously, `aeat --help` and most `ledger` subcommands loaded fine
(the version fast-path bypasses the broken import). The regression
appears to be a module that was renamed or deleted mid-restructure
(`_bucket_pointer_io`) but whose import was not updated in
`_profile_health.py`.

After this point, **no aeat command is usable**.

---

### Step 11 — Attempt recovery / further commands

All subsequent commands failed with the same traceback:

- `aeat app ledger status` → crash
- `aeat app ledger list` → crash
- `aeat app ledger view c68eb0c6` → crash
- `aeat --help` → crash

Session ended here. Goal not fully achieved.

---

## Did it work?

Partially. The happy path up to and including `classify` worked correctly:

- Profile creation: yes (with two friction points).
- Import (OFX/n26): yes — clean output, 14 rows ingested.
- Ledger status (first call): yes.
- Classification: yes — 6 transactions classified.
- Ledger view / subsequent status: **no** — hard crash, CLI fully dead.

The daily ledger workflow cannot be completed. After the first invocation of
`aeat app ledger view`, the tool stops working entirely due to a missing
module.

---

## Bugs and gaps

1. **`aeat app ledger view` crashes entire CLI**
   - Command: `aeat app ledger view c68eb0c6`
   - Expected: show transaction detail
   - Actual: `ModuleNotFoundError: No module named 'aeat.application.workflow._bucket_pointer_io'`; all subsequent CLI invocations (including `aeat --help`) crash with the same error
   - Severity: **blocker**

2. **`--provider` accepts undocumented values; no enumeration in help or error**
   - Command: `aeat app ledger import myfile.ofx --provider ???`
   - Expected: help text lists valid providers (or `--provider` is an enum with tab-completion)
   - Actual: only `n26` found to work; `revolut`, `bbva`, `sabadell`, `santander`, `caixabank`, `bankia`, `ing` all return "unknown ledger provider"; no list provided in help or on invalid-value error
   - Severity: **major** — any user with a non-N26 bank has no path forward

3. **`aeat app ledger view` uses positional argument but `classify` uses `--id`; inconsistency**
   - Command: `aeat app ledger view --id c68eb0c6` → "No such option: --id"
   - Expected: consistent ID passing convention across ledger subcommands
   - Actual: `view` requires positional; `classify` requires `--id`
   - Severity: **major** — confusing API surface

4. **Help table truncates long option names with ellipsis**
   - Command: `aeat config profile create --help`
   - Expected: full option names visible in the table
   - Actual: `--tax-residence-ccaa…` truncated; user must guess
   - Severity: **minor**

5. **CIF validation error exposes internal debug keys to the user**
   - Command: `aeat config profile create --tax-id B12345678 ...`
   - Expected: plain "Invalid CIF: check digit should be 4" message
   - Actual: raw dict with `prompt_key`, `question_id`, `raw` fields printed to terminal
   - Severity: **minor**

6. **No confirmation output on successful `--quiet` profile create**
   - Command: `aeat config profile create ... --quiet` (valid inputs)
   - Expected: "Profile marco-contabilidad created." or similar
   - Actual: silent exit (exit code 0, no output)
   - Severity: **cosmetic**
