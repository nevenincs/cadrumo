---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-20-cli-testimonial-findings-inventory-audit]]"
---

# CLI testimonial - Carmen, regression check

## What I was trying to do

I am a returning autonoma. I used aeat a few weeks ago and hit several rough edges. I came back to set up my profile for 2025, configure my digital certificate, do some ledger work, and start thinking about my Modelo 303. I tested eight specific flows I had been told were improved.

All commands were run with `AEAT_LOCAL_STORAGE_ROOT` pointed at an isolated scratch directory so my session would not touch any other state.

---

## My session

### 1. First look at the tool

**Command:** `aeat --help`

**What I expected:** The top-level help to orient me quickly.

**What I got:**
```
aeat - local-first Spanish tax workflow

The CLI has exactly two roots: config and app.
Use config for local state and app for tax work.

Section setup
  aeat config profile create NAME  Setup create profile
  ...
```
**How it felt:** Clean and readable. The two-root structure made sense. I knew where to go next.

---

### 2. Creating my profile

**Command:** `aeat config profile create carmen-test --quiet --tax-id 12345678Z --name Carmen --surnames "Garcia Lopez" --activity "Consultora TI" --address-postcode 28001 --taxation-type 1 --output-language es`

**What I expected:** Confirmation the profile was created successfully with no ambiguity.

**What I got:**
```
profile	carmen-test
status	created
next	aeat app modelo work create
```
Exit code: 0

**How it felt:** Good. Short and unambiguous. The `status: created` line told me exactly what happened. The `next` hint was a nice touch — I knew what to do next.

---

### 3. Profile status right after creation

**Command:** `aeat config profile status`

**What I expected:** A summary of my new profile showing it is healthy.

**What I got:**
```
profile	carmen-test
identity.tax_id	12345678Z
activities.description	Consultora TI
iva.regime	GENERAL
tax_residence.ccaa	madrid
Próximo paso: `aeat app overview status`
```
Exit code: 0

**How it felt:** Good. It showed the key fields I cared about and confirmed the profile is ready. The `Próximo paso` guidance was helpful.

---

### 4. Configuring auth with a certificate I had not set up yet

**Command:** `aeat config auth configure --provider certificate` (no file path given)

**What I got:**
```
provider	certificate
file	
active_profile	carmen-test
next_action	aeat config auth test --provider certificate
```
Exit code: 0

**How it felt:** The empty `file` field with no warning was a bit odd. I did not know if this was a problem or just "not yet configured." No error, no warning.

**Command:** `aeat config auth status`

**What I got:**
```
provider	certificate
configured	False
authenticated	False
available	False
active_profile	carmen-test
active_profile_status	ready
...
health_summary	certificate path not configured
```
Exit code: 0

**How it felt:** Now it was clear. The `health_summary` told me the path was not configured. The `configured: False` row was honest. The exit code being 0 despite auth not being ready is a minor oddity — I would have expected a non-zero code here, but the explanation was clear enough.

---

### 5. Auth test

**Command:** `aeat config auth test`

**What I got:**
```
provider	certificate
configured	False
...
active_profile	carmen-test
active_profile_status	ready
...
health_summary	certificate path not configured
```
Exit code: 0

**How it felt:** It did report my active profile (`carmen-test`). But the output was identical to `auth status` — I could not tell what "test" did differently. There was no explicit statement like "no live test performed — certificate not configured." The distinction between `auth status` and `auth test` was opaque to me.

---

### 6. Renaming my profile

**Command:** `aeat config profile rename carmen-test carmen-2025`

**What I got:**
```
source_profile_id	carmen-test
target_profile_id	carmen-2025
display_name	carmen-test
EXIT: 0
```

**Command:** `aeat config profile list`
```
active_profile	carmen-2025
*	carmen-2025
EXIT: 0
```

The list looked correct. No ghost entry. But then I ran profile status:

**Command:** `aeat config profile status`
```
profile	carmen-2025
readiness	missing_profile_record
registered_profile	present
profile_record	missing
next_action	aeat config repair profile --clear-active --yes
EXIT: 2
```

**How it felt:** Alarming. The rename worked at the pointer level but the actual profile record was not moved. The tool told me to run a repair command, which is not what I expected after a rename that returned exit 0. I had to run `aeat config repair profile` to confirm the state and discovered the repair deletes the active pointer rather than fixing the missing record. This felt like data loss waiting to happen.

---

### 7. Bad period tokens for modelo creation

**Command:** `aeat app modelo work create --modelo 303 --year 2025 --period Q9 --revision 303-2024`

**What I got:**
```
┌─ Error ─────────────────────────────────────────────────────────────────────┐
│ Invalid value: period must be YYYY, YYYYQn, YYYY-Qn, or YYYY-MM; got        │
│ '2025Q9'                                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
EXIT: 2
```

**Command:** `aeat app modelo work create --modelo 303 --year 2025 --period xyz --revision 303-2024`

**What I got:**
```
┌─ Error ─────────────────────────────────────────────────────────────────────┐
│ Invalid value: period must be YYYY, YYYYQn, YYYY-Qn, or YYYY-MM; got        │
│ '2025-xyz'                                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
EXIT: 2
```

**How it felt:** Exactly what I wanted. Fast rejection, clear message, acceptable formats listed inline. No stack trace. Both bad inputs caught immediately.

---

### 8. Ledger import and allocate

**Command:** `aeat app ledger import /tmp/carmen-n26.csv --provider N26 --verbose`

**What I got:**
```
Filas	3
Entradas importadas	3
Omitidos	0
Válido	Sí
Formato detectado	delimiter=',',quotechar='"'
Avisos	N26 CSV has no currency column; falling back to EUR
EXIT: 0
```

Good. The warning about the missing currency column was helpful rather than a silent failure.

**Command:** `aeat app ledger allocate --id b23e8030 --business-pct 1.0`

**What I got:**
```
ID	b23e8030459c155b9d6be470ca98326a498acf5ef0b1cc1c3cac20b5ced02654
Fecha	2025-01-22
Importe	-89.99
Descripción	Compra material oficina
Estado de revisión	reviewed
EXIT: 0
```

**How it felt:** The transaction moved from `pending` to `reviewed`. But I never saw the word BUSINESS in the output. When I ran `aeat app ledger view b23e8030` afterwards, I got the same output — only `Estado de revisión: reviewed`. There was no classification label (BUSINESS / PERSONAL / MIXED) visible anywhere in the view or list output. I could not confirm whether the 100% business allocation had actually been recorded.

---

### 9. NIF validation error

**Command (structurally invalid):** `aeat config profile create nif-test --quiet --tax-id BADNIF999 ...`

**What I got:**
```
Refused. NIF/NIE/CIF no válido para wizard.setup.profile.tax-id.prompt: BADNIF999. not a valid CIF shape: 'BADNIF999'.
  detail: not a valid CIF shape: 'BADNIF999'
  raw: BADNIF999
EXIT: 2
```

**Command (wrong check digit):** `aeat config profile create nif-test --quiet --tax-id 99999999X ...`

**What I got:**
```
Refused. NIF/NIE/CIF no válido para wizard.setup.profile.tax-id.prompt: 99999999X. NIF check letter mismatch: expected 'R', got 'X'.
  detail: NIF check letter mismatch: expected 'R', got 'X'
  raw: 99999999X
EXIT: 2
```

**How it felt:** The message contained the internal field path `wizard.setup.profile.tax-id.prompt` which is not user-facing language. A real non-expert would not know what that means. However, the actual error reason ("NIF check letter mismatch: expected 'R'") was plain and useful. Mixed result.

---

### 10. App subtree import crash (incidental discovery)

**Command:** `aeat app --help`

**What I got:**
```
Traceback (most recent call last):
  ...
ImportError: cannot import name 'DisenoCompletenessCasilla' from 'aeat.domain.calculations.registry._schema'
EXIT: 1
```

**How it felt:** Completely broken. The `app` subtree help itself crashed. Direct subcommands like `aeat app ledger import` still worked because they lazy-load, but `aeat app --help`, `aeat app overview status`, and anything that eagerly loads the full app tree would fail. I discovered this when I tried a couple of diagnostic commands.

---

## Did each flow behave?

- [PASS] **Flow 1 — `aeat config profile create`:** Confirms success visibly with `status: created` and a `next` hint. Clear, unambiguous.
- [PASS] **Flow 2 — `auth configure --provider certificate` then `auth status`:** Status report is self-consistent. `configured: False` and `health_summary: certificate path not configured` agree. Exit code 0 for an unconfigured state is a mild oddity but not a blocker.
- [PARTIAL] **Flow 3 — `auth test` reports active profile:** Does show `active_profile: carmen-test`. However the output is identical to `auth status` — there is no indication that a live test was attempted or skipped. The distinction between the two commands is unclear to a user.
- [FAIL] **Flow 4 — `profile rename` cleanly with no ghost:** The rename returned exit 0 and removed the old name from the list. But the profile record was not migrated — `profile status` afterwards returned `missing_profile_record` with exit 2. The profile was broken after a successful-looking rename.
- [PASS] **Flow 5 — bad period token rejected immediately:** Both `Q9` and `xyz` produced a clean error box with valid format examples. Fast, clear, no stack trace.
- [FAIL] **Flow 6 — `profile status` sensible output and exit 0:** Profile status returned exit 0 immediately after creation (good). But after the rename in Flow 4, the same command returned exit 2 with `missing_profile_record`. The rename broke the profile record, making this flow fail post-rename.
- [PARTIAL] **Flow 7 — ledger import then allocate shows BUSINESS classification:** Import worked correctly. Allocate completed with exit 0. But neither `ledger allocate` output nor `ledger view` showed a BUSINESS/PERSONAL/MIXED classification label. The user cannot confirm the allocation was recorded as BUSINESS.
- [PARTIAL] **Flow 8 — NIF validation error is plain-language:** The error reason is plain and specific. However the message includes the internal field path `wizard.setup.profile.tax-id.prompt` before the human-readable part, which is not user-facing language.

**Summary: 3 PASS, 3 PARTIAL, 2 FAIL**

---

## Bugs and gaps

1. **`profile rename` drops the profile record — BLOCKER**
   - Command: `aeat config profile rename carmen-test carmen-2025`
   - Expected: profile record migrated to new name; `profile status` returns exit 0 in healthy state
   - Actual: rename returns exit 0; `profile status` immediately returns `missing_profile_record` with exit 2; tool suggests repair (which clears the pointer, not fixes the record)
   - Severity: **BLOCKER** — rename is the standard flow for annual profile duplication; it silently corrupts the profile

2. **`aeat app --help` crashes with ImportError — BLOCKER**
   - Command: `aeat app --help`
   - Expected: app subtree help displayed
   - Actual: `ImportError: cannot import name 'DisenoCompletenessCasilla' from 'aeat.domain.calculations.registry._schema'`; exit 1
   - Severity: **BLOCKER** — the entire app diagnostics tree (overview, live filed, review queue, registry inspect) is inaccessible; lazy-loaded subcommands still work but any eager-load path crashes

3. **`ledger allocate` does not confirm BUSINESS classification in output — MAJOR**
   - Command: `aeat app ledger allocate --id b23e8030 --business-pct 1.0`
   - Expected: output includes explicit classification label (e.g. `clasificación: BUSINESS`)
   - Actual: output shows only `Estado de revisión: reviewed`; `ledger view` and `ledger list` also omit the classification label
   - Severity: **MAJOR** — user cannot verify that `--business-pct 1.0` was actually stored as BUSINESS; silent acceptance with no confirmation

4. **`auth test` is indistinguishable from `auth status` — MINOR**
   - Command: `aeat config auth test`
   - Expected: clearly indicates whether a live connectivity test was attempted and what the result was; distinct from a static status report
   - Actual: output is byte-for-byte identical to `auth status`; no indication a test was performed or skipped
   - Severity: **MINOR** — misleading command semantics; a user will assume "test" performed an active check

5. **NIF validation error includes internal field path in user-facing message — MINOR**
   - Command: `aeat config profile create nif-test --quiet --tax-id BADNIF999 ...`
   - Expected: plain-language error only, e.g. "NIF/NIE no válido: BADNIF999 — formato no reconocido"
   - Actual: `Refused. NIF/NIE/CIF no válido para wizard.setup.profile.tax-id.prompt: BADNIF999. not a valid CIF shape: 'BADNIF999'.` — the `wizard.setup.profile.tax-id.prompt` path leaks implementation detail
   - Severity: **MINOR** — confusing to non-technical users; the actual error reason that follows is good

6. **`auth configure --provider certificate` (no file) exits 0 without warning — MINOR**
   - Command: `aeat config auth configure --provider certificate`
   - Expected: either prompt for path or warn that the configuration is incomplete
   - Actual: exits 0 with empty `file` row and a `next_action` hint that says to run `auth test`; a user may think configuration succeeded
   - Severity: **MINOR** — ambiguous success signal; `auth status` immediately clarifies, but the configure step itself is silent about the missing path
