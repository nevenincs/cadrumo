---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# CLI testimonial - Diego, modelo 130 preparer

## What I was trying to do

I am a self-employed management consultant (estimación directa, régimen general IVA, resident in Madrid). It is the end of Q1/early Q2 2026 and I want to prepare Modelo 130 — the quarterly IRPF fractional payment. I have never used this tool before. I want to: create a profile, discover Modelo 130, create a work unit for it, feed in my income and expenses, and get a calculated borrador with casilla values, legal references, and provenance I can review before heading to the AEAT portal.

## My session

### Step 1 — First contact

**Command:** `AEAT_LOCAL_STORAGE_ROOT=.../persona-diego uv run --no-sync aeat --help`

**Expectation:** See a list of commands and understand where to start.

**Real output (excerpt):**
```
aeat - local-first Spanish tax workflow

The CLI has exactly two roots: config and app.
...
Section modelo lifecycle
  aeat app modelo list           Modelo list
  aeat app modelo bindings list  Modelo bindings list
  aeat app modelo work           Modelo work
```

**How it felt:** Clean and reassuring. The sections are logical. "modelo lifecycle" is exactly what I need.

---

### Step 2 — List available modelos

**Command:** `aeat app modelo list`

**Expectation:** See Modelo 130 in the list.

**Real output (excerpt):**
```
code  title                                         cadence     domain  revisions
...
130   IRPF pago fraccionado estimacion directa      quarterly   irpf    1
...
```

**How it felt:** Excellent. One command, the full catalog, machine-readable. I can see 130 is quarterly, IRPF, and has 1 revision. Exactly what I needed.

---

### Step 3 — Create a profile

**Command (first attempt):**
```
aeat config profile create "diego-consulting" --quiet --tax-id 12345678Z ...
  --no-pays-professionals-with-retention
```

**Expectation:** Profile created.

**Real output:**
```
Error. No such option: --no-pays-professionals-with-retention
(Possible options: --no-pays-professionals-with-retencion, ...)
```

**How it felt:** Confusing. The `--help` output showed the option as `--pays-professionals-with-retention` but the actual flag uses the Spanish suffix `-retencion`. The help text is inconsistent. Required three correction rounds before the full command worked:
- `--no-pays-professionals-with-retencion` (Spanish suffix, but English verb)
- `--no-pays-capital-income-with-retencion` (not `--no-pays-capital-income`)
- `--no-uses-objective-estimation-irpf` (not `--no-uses-objective-estimation`)
- `--tax-residence-ccaa` (not `--tax-residence-region`)

After four failed invocations, profile created silently (no output confirming success — exit 0 but blank stdout).

---

### Step 4 — Check profile status

**Command:** `aeat config profile status`

**Real output:**
```
profile     diego-consulting
identity.tax_id  12345678Z
activities.description  Consultoría de gestión
iva.regime  GENERAL
tax_residence.ccaa  madrid
Próximo paso: `aeat app overview status`
```

**How it felt:** Good — the "next step" hint is helpful for onboarding.

---

### Step 5 — Overview status

**Command:** `aeat app overview status`

**Real output:**
```
Estado del espacio de trabajo
Estas trabajando en el perfil `diego-consulting`.
Aun no se han importado movimientos bancarios.
...
No se encontraron borradores de declaraciones guardados.
```

**How it felt:** Fine. I expected it would tell me about Modelo 130 obligations but it only mentions ledger import. No mention of quarterly obligations even though my profile clearly describes a self-employed person with quarterly filing cadence.

---

### Step 6 — Discover the revision ID for Modelo 130

**Command:** `aeat app modelo bindings list --modelo 130 --year 2026 --period Q1`

**Real output:**
```
binding_count  2
modelo  revision         period  binding_id                                          source            readiness
130     2019-y-siguientes  1T    modelo-130-resultados-negativos-anteriores          previous_filing   prior filed revision
130     2019-y-siguientes  1T    irpf.previous_year_economic_activity_net_income     previous_filing   prior filed revision
```

**How it felt:** Useful — I can see the revision ID is `2019-y-siguientes` and the two bindings I need to provide (previous-period negative results and prior-year net income). However: I passed `--period Q1` and got results for period `1T`. The normalisation is invisible and there is no documentation on what period token formats are accepted.

---

### Step 7 — Create the work unit

**Command:**
```
aeat app modelo work create --modelo 130 --year 2026 --period 1T
  --revision "2019-y-siguientes" --name "Modelo 130 Q1 2026 - Diego"
```

**Real output:**
```
work_unit_id  3925b2655bdd7b00a1e5a144725e1782cc1ec4f332a06abe01c64f6718104960
estado        borrador
```

**How it felt:** Clean and fast. State is `borrador`. The SHA-256 work-unit ID is unwieldy to type but I can copy it.

---

### Step 8 — First calculation attempt (casilla 03 rejected)

**Command:**
```
aeat app modelo work calculate <id> --casilla "01=18500.00" --casilla "02=4200.00"
  --casilla "03=750.00" --by "diego"
```

**Real output:**
```
Error. No se pueden suministrar como entrada las casillas calculadas: 03.
```

**How it felt:** The error message is clear and correct — casilla 03 is computed. I removed it.

---

### Step 9 — Second attempt (missing binding)

**Command:**
```
aeat app modelo work calculate <id> --casilla "01=18500.00" --casilla "02=4200.00"
  --by "diego"
```

**Real output:**
```
Error. La vinculación irpf.previous_year_economic_activity_net_income
no tiene valor asignado.
```

**How it felt:** Useful error. It tells me exactly which binding is missing. But the tool never told me upfront (before attempting calculation) that I would need to supply prior-year data. A pre-flight check listing required bindings before attempting calculate would prevent this round-trip.

---

### Step 10 — Successful calculation

**Command:**
```
aeat app modelo work calculate <id>
  --casilla "01=18500.00"
  --casilla "02=4200.00"
  --binding "irpf.previous_year_economic_activity_net_income=42000.00"
  --binding "modelo-130-resultados-negativos-anteriores=0"
  --by "diego"
```

**Real output:**
```
operation   modelo.work.calculate
calculation_revision_id  794236aee2f7d11728bc1a7a855c24a206a075773dbd9df50a18849ce9ecd2be
state       borrador
casilla  01   18500.00
casilla  02   4200.00
casilla  03   14300.00    ← rendimiento neto (01 - 02), correct
casilla  04   2860.00     ← 20% of 14300, correct
casilla  05   0
casilla  06   0
casilla  07   2860.00
casilla  08   0
casilla  09   0.00
casilla  10   0
casilla  11   0.00
casilla  12   2860.00
casilla  13   0.00
casilla  14   2860.00
casilla  15   0
casilla  16   0
casilla  17   2860.00
casilla  18   0
casilla  19   2860.00     ← result to pay
casilla  saldo-negativo-fin-periodo  0.00
```

**How it felt:** The arithmetic is correct (18500 - 4200 = 14300; 14300 × 20% = 2860). All casillas are emitted, including those I did not supply. However: **no legal references** are shown (no BOE cites, no formula_ids, no source_refs), no provenance labels, and no explanation of what each casilla means. The calculation engine claims to carry legal grounding but none is surfaced at the CLI output layer.

---

### Step 11 — Verify the Q1 draft

**Command:** `aeat app modelo work verify <calculation_id> --by diego`

**Real output:**
```
Error. workflow gate aborted run_id='250433edf57b300e' final_stage='ABORTED'
reason='DEADLINE_PASSED': Deadline for modelo=130 period=2026Q1
closed on 2026-04-20
```

**How it felt:** Correct enforcement — the Q1 window is closed. But this should have been surfaced when the work unit was created for 1T, not silently accepted and only rejected at verify time. The create command accepted an out-of-window period with no warning.

---

### Step 12 — Retry with Q2 (current quarter)

Created a Q2 2026 work unit and calculated it with the same inputs.

**Verify attempt:**
```
Error. workflow gate aborted ... reason='PREFLIGHT_FAILED':
Preflight failed: deadline window for modelo 130 period 2026Q2
is not open on 2026-05-20
```

**How it felt:** Unexpected and blocking. Today is 20 May 2026. The Q2 2026 window for Modelo 130 runs 1–20 July 2026. The tool correctly enforces this — but the result is that there is **no period I can currently verify**. Q1 is closed, Q2 is not yet open. The calculate step works fine (producing the borrador) but the lifecycle cannot advance past `borrador` for any current period on this date.

This is technically correct AEAT behaviour but there is no in-tool explanation. A real user would be confused about whether the tool is broken.

---

### Step 13 — Post-calculate CLI instability

After the verify failure, subsequent commands began failing with `ModuleNotFoundError` — first for `aeat.application.workflow._bucket_pointer_io`, then for `aeat.core.resources._registry`. The errors were non-deterministic: some commands succeeded, others failed with different missing modules depending on which `.pyc` files were cached.

After clearing the `__pycache__` directories, the errors became consistent:
```
ImportError: cannot import name 'resources' from 'aeat.core.resources'
```
This reflects the current mid-refactor state of the `chore/eliminate-shims` branch — `aeat.core.resources.__init__.py` has been restructured but not all importers have been updated.

---

## Did it work?

**Partially.** The core happy path — create profile → list modelos → create work unit → calculate — worked and produced arithmetically correct casilla values. The numbers for Modelo 130 (casillas 01–19 plus saldo-negativo) are coherent with the 20% fractional payment formula.

What did not work:
- The lifecycle could not advance past `borrador` because no currently open filing window exists for this date (both Q1 closed and Q2 not yet open). This is factually correct but silently frustrating.
- Legal references, formula provenance, and casilla descriptions are absent from the calculation output — the tool's primary advertised strength.
- CLI stability is intermittent on this branch due to mid-refactor missing modules (`_bucket_pointer_io`, `aeat.core.resources._registry`).

---

## Bugs and gaps

### 1

**Command:** `aeat config profile create` with boolean flag variants  
**Expected:** Flag names in `--help` match flag names accepted at runtime  
**Actual:** Flags shown as `--pays-professionals-with-retention` but only `--pays-professionals-with-retencion` is accepted; `--tax-residence-region` shown but `--tax-residence-ccaa` required; four successive failures before a working invocation  
**Severity:** Major — breaks first-use flow for any user attempting non-interactive profile creation

### 2

**Command:** `aeat config profile create ...` (success)  
**Expected:** Confirmation output (profile name, key settings, next steps)  
**Actual:** Silent exit — no stdout output on success  
**Severity:** Minor — disorienting but not blocking; the follow-up `profile status` confirms state

### 3

**Command:** `aeat app modelo work calculate <id>` (without `--binding` for required bindings)  
**Expected:** Pre-flight error listing all missing bindings before attempting computation  
**Actual:** Compute attempt runs until first missing binding, surfaces one error per invocation; requires N round-trips for N missing bindings  
**Severity:** Major — two-round-trip discovery loop for required inputs that the tool already knows about from `bindings list`

### 4

**Command:** Calculation output  
**Expected:** Legal references (BOE articles, formula_id, source_refs) and casilla descriptions alongside values, per the tool's documented contract  
**Actual:** Flat `casilla X value` table only — no legal refs, no formula provenance, no casilla labels  
**Severity:** Major — the primary stated value proposition (regulatory grounding at every output surface) is unmet at the CLI layer

### 5

**Command:** `aeat app modelo work create --modelo 130 --year 2026 --period 1T`  
**Expected:** Warning or refusal when the filing window for the requested period is already closed  
**Actual:** Work unit accepted silently; closure only enforced at `verify` time (much later in the lifecycle)  
**Severity:** Minor — allows wasted work but does correctly block the final step

### 6

**Command:** All commands following first `verify` failure  
**Expected:** CLI remains operational  
**Actual:** Non-deterministic `ModuleNotFoundError` crashes (`_bucket_pointer_io`, `aeat.core.resources._registry`) caused by mid-refactor missing modules on the `chore/eliminate-shims` branch; clearing `__pycache__` makes failures deterministic but does not resolve the underlying import breakage  
**Severity:** Blocker — the CLI becomes entirely non-functional after certain command sequences on this branch

### 7

**Command:** `aeat app modelo work verify <id>` for Q2 2026 on 2026-05-20  
**Expected:** Either proceed (window is open or a preview mode exists) or a clear message explaining that the window opens on 2026-07-01 with next-step guidance  
**Actual:** `PREFLIGHT_FAILED: deadline window for modelo 130 period 2026Q2 is not open on 2026-05-20` with no next-step guidance  
**Severity:** Minor — technically correct, but a real user would not know whether to wait, use a different period, or conclude the tool is broken

### 8

**Command:** `aeat app overview status`  
**Expected:** Surface outstanding quarterly filing obligations given my profile (self-employed, quarterly IRPF, Q2 window opening in July)  
**Actual:** Only reports ledger import status and encrypted storage health; no modelo obligation calendar  
**Severity:** Minor — missed UX opportunity; the registry knows the deadlines and the profile declares the cadence
