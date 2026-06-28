---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-20-cli-testimonial-findings-inventory-audit]]"
---

# CLI testimonial - Javier, explain & review deep path

## What I was trying to do

I am Javier García López, a freelance software developer (autonomo) in Madrid, registered under the GENERAL IVA regime. I wanted to understand whether the CLI could actually help me — a non-expert — learn which tax declarations I owe, why they apply to me, what data the tool still needs from me, and whether the review queue gives me anything useful to act on. I focused on the surfaces not usually explored in quick demos: `modelo describe`, `modelo bindings list`, `overview` sub-verbs (status, calendar, agenda, backlog, explain), `review queue` and `review view`, and `registry inspect`.

## My session

### Step 1 — Create my profile

**Command:** `aeat config profile create javier --quiet --tax-id 12345678Z --name Javier --surnames "García López" --activity "Desarrollo de software" --address-postcode 28001 --taxation-type 1 --output-language es --taxpayer-sex H --taxpayer-marital-status 1 --taxpayer-birth-date 1985-03-15 --iva-regime GENERAL --tax-residence-community madrid`

**Expectation:** Profile created, told what to do next.

**Real output:**
```
Error: No such option: --tax-residence-community Did you mean --tax-residence-ccaa?
```
Exit 2.

**How it felt:** Annoying. The help text shows `--tax-residence-ccaa` with a long truncated list of comunidades. The name `community` feels natural in English but `ccaa` is an internal Spanish acronym. A newcomer would not guess this.

**Second attempt** dropped the flag entirely and succeeded. Output: `profile javier / status created / next aeat app modelo work create`. Clear and terse.

---

### Step 2 — What modelos exist?

**Command:** `aeat app modelo list`

**Real output (excerpt):**
```
code  title                                       cadence     domain    revisions
036   Censo de empresarios, profesionales ...     ad_hoc      census    1
100   IRPF declaracion anual                      annual      irpf      6
130   IRPF pago fraccionado estimacion directa    quarterly   irpf      1
303   IVA. Autoliquidacion (trimestral)           quarterly   iva       1
...
```
Exit 0.

**How it felt:** Good. 26 modelos, cadence and domain visible at a glance. A non-expert could identify the quarterly ones.

---

### Step 3 — What is modelo 303?

**Command:** `aeat app modelo describe 303`

**Real output:**
```
Modelo     303
Title      IVA. Autoliquidacion (trimestral)
Cadence    quarterly
Revision   2009-y-siguientes
Casillas   20
Bindings   6
Formulas   9
```
Exit 0.

**How it felt:** Useful as a summary count, but tells me nothing about what the casillas mean. The numbers "20 casillas, 9 formulas" are opaque — I can see the scaffolding counts but not what I need to fill in. There is no prose description, no link to an AEAT page, no worked example.

**Command:** `aeat app modelo describe 100`

20 casillas → 2235 casillas for the annual renta. That jump is honest but the surface doesn't explain the difference in complexity.

---

### Step 4 — What data does the tool need to compute 303?

**Command:** `aeat app modelo bindings list --modelo 303 --year 2026 --period 1T`

**Real output:**
```
binding_id                                      source                  readiness         borrador_capable
modelo-303-iva-repercutido-general-cuota        ledger_iva_aggregation  ledger source     False
modelo-303-iva-repercutido-reducido-cuota       ledger_iva_aggregation  ledger source     False
modelo-303-iva-repercutido-super-reducido-cuota ledger_iva_aggregation  ledger source     False
modelo-303-iva-soportado-interiores-cuota       ledger_iva_aggregation  ledger source     False
modelo-303-iva-autorepercutido-intracomunitaria-cuota  ledger_iva_aggregation  ledger source  False
modelo-303-compensacion-pendiente-anteriores    previous_filing         prior filed revision  False
```
Exit 0.

**How it felt:** Semi-useful. I can see the binding IDs are descriptive (repercutido-general, soportado-interiores etc.). The `readiness` column header sounds like it should tell me whether I've satisfied that data requirement, but it shows static labels like "ledger source" and "prior filed revision", not a resolved/unresolved status. The `--missing` flag returned exactly the same 6 rows as without it — no difference — suggesting the filter has no effect when no ledger data exists. I cannot tell whether "ledger source" means "go import ledger" or "already found in ledger". `borrador_capable` is False for every row without explanation.

---

### Step 5 — Overview status

**Command:** `aeat app overview status`

**Real output (translated):**
```
Working on profile `javier`.
Bank movements not yet imported.
Business operations not yet imported.
No declaration drafts saved.
Encrypted local storage readable.

What to write next:
  aeat app ledger import <extracto-bancario.csv> --provider csv
  aeat app ledger review
  aeat --help
```
Exit 0.

**How it felt:** Very good for a first-run. Spanish throughout, actionable next steps, no jargon. This one works well.

---

### Step 6 — Am I behind on anything?

**Command:** `aeat app overview agenda --date 2026-05-21`

**Real output:**
```
as_of          2026-05-21
horizon_days   14
next_due       (none)
due_today      0
due_soon       0
overdue        2
  130  2026Q1  2026-04-20
  303  2026-1T 2026-04-20
```
Exit 0.

**How it felt:** Very useful. Two overdue filings, I can see the deadlines. `next_due (none)` with a 14-day horizon is correct because Q2 is July. The output is machine-readable but readable by a human too. Good.

**Command:** `aeat app overview agenda --date 2026-05-21 --horizon 60`

Next due becomes `130 2026Q2 closes=2026-07-20`, due_soon shows both Q2 modelos. Works.

---

### Step 7 — Full year calendar

**Command:** `aeat app overview calendar --from 2026-01-01 --to 2026-12-31`

**Real output (excerpt):**
```
130  2026Q1  late  opens=2026-04-01  closes=2026-04-20  adjusted=2026-04-20  shift=business_day
303  2026-1T late  opens=2026-04-01  closes=2026-04-20  ...
130  2026Q2  due   opens=2026-07-01  closes=2026-07-20  ...
303  2026-2T due   ...
130  2026Q3  due   opens=2026-10-01  closes=2026-10-20  ...
303  2026-3T due   ...
computable 2  defaulted 0
```
Exit 0.

**How it felt:** Excellent. Six entries, clearly dated, late/due status at a glance. Q4 and the annual 100/390 are absent — that would worry a real user who doesn't know why. No explanation of the `computable` / `defaulted` summary line. Annual declarations (100, 390) are entirely missing from the calendar output despite being relevant.

---

### Step 8 — Backlog of overdue filings

**Command:** `aeat app overview backlog`

**Real output:**
```
from        2025-05-20
to          2026-05-20
late_count  5
303  2025-2T  closes=2025-07-21
303  2025-3T  closes=2025-10-20
303  2025-4T  closes=2026-01-30
130  2026Q1   closes=2026-04-20
303  2026-1T  closes=2026-04-20
```
Exit 0.

**How it felt:** Useful. Seeing Q2 and Q3 2025 as overdue was unexpected — the profile was just created but the tool looks back a year regardless. No explanation that this is because the profile says I have been operating, not because I actually filed late. For a real taxpayer this could cause confusion or anxiety.

---

### Step 9 — Why does 130 apply to me?

**Command:** `aeat app overview explain 130`

**Real output:**
```
modelo   130
year     2026
applicable  true
rationale   Autonomo en estimacion directa salvo la excepcion de ingresos profesionales ya retenidos.
profile_fact  professional_income_withholding_ge_70pct  False
profile_fact  iva_regime                                GENERAL
... (14 profile_facts total)
```
Exit 0.

**How it felt:** The rationale sentence is the most human-readable explanation in the entire session. "Autonomo en estimacion directa salvo la excepcion..." tells me exactly why. The 14 profile_facts are developer-facing; a taxpayer cares about 2-3 of them at most.

**Command:** `aeat app overview explain 111`

applicable=false. Correct (I have no employees, no `pays_professionals`). Good.

**Command:** `aeat app overview explain 347`

```
Error: could not evaluate modelo '347' for year 2026: No registry deadline windows registered for modelo '347' in year 2026
```
Exit 2.

This is a blocker. Modelo 347 is a common informativa obligation for autonomos exceeding the 3.005 EUR third-party threshold. The error is unintelligible to a user — "no registry deadline windows" — and gives no guidance. The same error fires for 100, 390, and any annual modelo when `explain` is called.

---

### Step 10 — Review queue

**Command:** `aeat app review queue`

**Real output:**
```
ID  Tipo  Tipo origen  Objeto  Bucket  Periodo  Severidad  Siguiente
No hay elementos pendientes de revisión.
```
Exit 0.

**How it felt:** Clean empty state. The column headers are in Spanish. Good.

**Command:** `aeat app review view nonexistent-id-001`

```
Error: Invalid value: review item not found: nonexistent-id-001
```
Exit 2. Clean error.

---

### Step 11 — Registry inspect and verify

**Command:** `aeat app registry inspect`

**Real output:**
```
Nº modelos=26
Nº revisiones=41
Nº referencias legales=201
Nº casillas=14975
Nº fórmulas=1052
...
Superficies de enlace de aplicación=approval,calculation,deadline,export,...
```
Exit 0.

**How it felt:** Pure developer/operator dump. The counts are meaningful to someone who maintains the registry. For a taxpayer this communicates nothing actionable. There is no filter by relevant modelos.

**Command:** `aeat app registry verify`

Output: `Verificado=True` followed by same stats, plus two `UserWarning` lines on stderr about `semantic_role` singletons on modelo 369.

**How it felt:** Warnings surface on stderr in developer tracebacks format (`_validate.py:500`). Exit 0 despite the warnings. A non-expert would be alarmed by the traceback-style output but not know whether it matters.

---

### Step 12 — Period token discovery

**Command:** `aeat app modelo describe 303 --period 2026Q1`

**Real output:** Full Python ImportError traceback, crash, exit 1.

This is a blocker. The help text for `--period` says "ejemplos periodicos incluyen 2026Q1 y 2026-01". Following the documented example literally crashes the process with `ImportError: cannot import name 'DerivedManifestCasilla'`.

Correct token is `2026-Q1` (with hyphen before Q). `1T` gives a validation error. The discrepancy between documented example and working format is a real usability fault.

---

## Did it work?

Partially. The core daily navigation (`overview status`, `agenda`, `calendar`, `backlog`, `explain` for quarterly modelos) works well and is genuinely useful for a self-employed person tracking obligations. The `review queue` runs cleanly. `modelo list` and `modelo describe` provide orientation. The Spanish-language output is consistent and readable.

What did not work:

- `overview explain` crashes on annual modelos (100, 390, 347, 184) with an internal "no registry deadline windows" error.
- `modelo describe --period 2026Q1` crashes with an ImportError despite the help text citing `2026Q1` as a valid example.
- `modelo bindings list --missing` does not filter; returns all rows identically with or without the flag when no ledger data is loaded.
- `registry verify` leaks internal Python warning tracebacks to stderr.
- The `explain` rationale for 303 says only "Aplica segun la ventana registral del modelo" — opaque to a taxpayer.
- The `backlog` silently projects obligations from day one of the profile window (a year back) with no explanation, which could alarm users.
- Annual modelos (100, 390, 190) are absent from `calendar` output with no indication.

## Bugs and gaps

1. **`aeat app overview explain <annual-modelo>` crashes for 100, 347, 390, 184 with "No registry deadline windows registered"**
   Command: `aeat app overview explain 347`
   Expected: applicability result with rationale, or a graceful "no deadline data for this modelo in this year"
   Actual: Exit 2, "Invalid value: could not evaluate modelo '347' for year 2026: No registry deadline windows registered for modelo '347' in year 2026"
   Severity: **blocker** — the most important annual declarations (renta, IVA summary, informativas) cannot be explained.

2. **`aeat app modelo describe --period 2026Q1` crashes with ImportError**
   Command: `aeat app modelo describe 303 --period 2026Q1`
   Expected: describe output identical to the no-period call, or a period-filtered revision view
   Actual: Exit 1, full Python ImportError traceback (`cannot import name 'DerivedManifestCasilla'`)
   Severity: **blocker** — documented example in help text triggers an import crash.

3. **`aeat app modelo bindings list --missing` does not filter**
   Command: `aeat app modelo bindings list --modelo 303 --year 2026 --period 1T --missing`
   Expected: only bindings with no resolved value (i.e. those I still need to supply)
   Actual: same 6 rows returned as without `--missing`; readiness column shows "ledger source" / "prior filed revision" static labels not resolved/unresolved status
   Severity: **major** — the flag advertised as "filter to bindings without resolved value" is silent no-op when ledger is empty.

4. **`aeat config profile create --tax-residence-community` option name mismatch**
   Command: `aeat config profile create javier ... --tax-residence-community madrid`
   Expected: accepted, profile created
   Actual: "No such option: --tax-residence-community Did you mean --tax-residence-ccaa?"
   Severity: **minor** — the suggestion was correct but `community` is the natural English equivalent and the help text truncates the option name in the display.

5. **`aeat app registry verify` leaks UserWarning tracebacks to stderr**
   Command: `aeat app registry verify`
   Expected: verification result only; internal warnings suppressed or summarised
   Actual: Two `UserWarning: semantic_role ... appears on exactly one casilla` lines with full file path and line number printed to stderr before the result
   Severity: **minor** — alarming to non-developers; confuses the clean verification output.

6. **`aeat app overview explain` rationale for 303 is registry-internal boilerplate**
   Command: `aeat app overview explain 303`
   Expected: human-readable sentence explaining why I as an autonomo with IVA GENERAL must file quarterly
   Actual: "Aplica segun la ventana registral del modelo." (applies per the registry window)
   Severity: **minor** — not wrong, but unhelpful. Compare with 130's rationale which is genuinely informative.

7. **`aeat app overview calendar` silently omits annual declarations (100, 390, 190)**
   Command: `aeat app overview calendar --from 2026-01-01 --to 2026-12-31`
   Expected: all applicable obligations including annual ones (renta April–June, IVA resumen January)
   Actual: only 2 quarterly modelos (130, 303) shown; no annual entries; `computable 2 defaulted 0` gives no clue about omissions
   Severity: **major** — a taxpayer relying on this calendar would miss the renta annual filing entirely.

8. **`aeat app overview backlog` silently projects obligations from profile epoch without explanation**
   Command: `aeat app overview backlog`
   Expected: clear indication that obligations are computed from profile start date, not from actual AEAT filing history
   Actual: shows 5 overdue items starting from 2025-2T with no note that these are computed, not verified late
   Severity: **minor** — can cause confusion or alarm for new profiles; a one-line caveat ("computed from profile registration date; not verified against AEAT") would resolve this.
