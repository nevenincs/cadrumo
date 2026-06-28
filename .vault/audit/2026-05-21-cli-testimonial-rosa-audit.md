---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-20-cli-persona-task-catalogue-reference]]"
---

# CLI testimonial - Rosa, Modelo 111

## What I was trying to do

I am Rosa, an autonoma who took on my first employee this quarter. I also paid a professional invoice to a freelancer. I need to file Modelo 111 - retenciones e ingresos a cuenta - for the withholdings I deducted. I have never filed a 111 before and I do not know anything about casillas or revisions. I want to use this CLI to prepare the declaration from scratch.

## My session

### Step 1: What does this CLI even do?

**Command:** `aeat --help`

**Expected:** Some kind of menu to see what the app can do.

**Output:**
```
aeat - local-first Spanish tax workflow

The CLI has exactly two roots: config and app.
Use config for local state and app for tax work.

Section setup
  aeat config profile create NAME  Setup create profile
  ...
Section modelo lifecycle
  aeat app modelo list           Modelo list
  aeat app modelo bindings list  Modelo bindings list
  aeat app modelo work           Modelo work
...
```
**Exit:** 0

**How it felt:** Clear enough. Two roots, "config" and "app". The section headers are helpful. I can see "modelo lifecycle" which sounds like what I need. Good start.

---

### Step 2: What modelos exist?

**Command:** `aeat app modelo list`

**Expected:** A list showing Modelo 111.

**Output:**
```
code	title	cadence	domain	revisions
...
111	IRPF retenciones e ingresos a cuenta	profile_based	irpf	1
...
```
**Exit:** 0

**How it felt:** I can see 111 right there. The title matches what I know from the AEAT paper form. The cadence says "profile_based" which I do not fully understand, but I proceed.

---

### Step 3: What does Modelo 111 need?

**Command:** `aeat app modelo describe 111`

**Expected:** Some explanation of what the form is and how many fields it has.

**Output:**
```
Modelo    111
Title     IRPF retenciones e ingresos a cuenta
Official name   Retenciones e ingresos a cuenta del IRPF. Rendimientos del trabajo y de actividades economicas, premios y determinadas ganancias patrimoniales e imputaciones de renta.
Tax domain  irpf
Cadence     profile_based
Revision    2019-y-siguientes
Periods     01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 1T, 2T, 3T, 4T
Casillas    30
Bindings    0
Formulas    2
```
**Exit:** 0

**How it felt:** Very useful. It tells me the revision ID is `2019-y-siguientes`, which I will need later. 30 casillas sounds like a lot but it is manageable. 0 bindings - I do not know what bindings are but presumably I will enter everything manually. The periods list includes `1T`, `2T`, `3T`, `4T` which are the quarterly tokens - that is helpful.

---

### Step 4: What are all the casillas?

**Command:** `aeat app modelo casillas 111`

**Expected:** A list of the boxes with their numbers and descriptions.

**Output (abridged):**
```
casilla_id  number  input     required  label
01          01      manual    false     Rendimientos del trabajo dinerarios numero de perceptores
02          02      manual    false     Rendimientos del trabajo dinerarios importe de percepciones
03          03      manual    false     Rendimientos del trabajo dinerarios importe de retenciones
...
07          07      manual    false     Rendimientos de actividades economicas dinerarios numero de perceptores
08          08      manual    false     Rendimientos de actividades economicas dinerarios importe de percepciones
09          09      manual    false     Rendimientos de actividades economicas dinerarios importe de retenciones
...
28          28      computed  false     Total retenciones e ingresos a cuenta
29          29      manual    false     Resultado de anteriores autoliquidaciones
30          30      computed  false     Resultado a ingresar
```
**Exit:** 0

**How it felt:** Very clear. I can see casillas 01-03 are for employee salaries and casillas 07-09 are for professional invoices. Both use `manual` input so I will enter numbers myself. Casillas 28 and 30 are `computed` - the app will calculate them. The `required: false` on every row is a bit surprising, I would expect some to be required, but maybe it is the model's way of saying no single field blocks submission. Nothing blocks me here.

---

### Step 5: Set up a profile

Before I can do tax work I need to tell the app who I am. The top-level help told me to start with `aeat config profile create`.

**Command (attempt 1):** `aeat config profile create rosa --quiet --tax-id "12345678A" --name "Rosa" --surnames "Garcia Lopez" --activity "Consultora" --address-postcode "28001" --has-employees --pays-professional-invoices --tax-residence-community madrid`

**Expected:** Profile created.

**Output:**
```
No such option: --pays-professional-invoices (Possible options:
--no-pays-professionals-with-retencion,
--pays-professionals-with-retencion)
```
**Exit:** 2

**How it felt:** The flag name I guessed from the help text (`--pays-professional-invoices`) was wrong. The error message gave me the correct name though. Minor friction.

---

**Command (attempt 2):** `aeat config profile create rosa --quiet --tax-id "12345678A" --name "Rosa" --surnames "Garcia Lopez" --activity "Consultora" --address-postcode "28001" --has-employees --pays-professionals-with-retencion --tax-residence-community madrid`

**Expected:** Profile created.

**Output:**
```
No such option: --tax-residence-community Did you mean --tax-residence-ccaa?
```
**Exit:** 2

**How it felt:** Another wrong flag name. The help text showed `--tax-residence-ccaa` but the description text said "comunidad autonoma" which made me try `--tax-residence-community`. The `Did you mean` correction is helpful.

---

**Command (attempt 3):** `aeat config profile create rosa --quiet --tax-id "12345678Z" --name "Rosa" --surnames "Garcia Lopez" --activity "Consultora" --address-postcode "28001" --has-employees --pays-professionals-with-retencion --tax-residence-ccaa madrid`

**Expected:** Profile created.

**Output:**
```
Refused. NIF/NIE/CIF no válido para wizard.setup.profile.tax-id.prompt: 12345678A. NIF check letter mismatch: expected 'Z', got 'A'.
```
**Exit:** 2

**How it felt:** My NIF was invalid - the check letter was wrong. The error message told me what letter was expected (`Z`). But the error message echoed `12345678A` even though I had already changed it to `12345678Z` in attempt 3 - this is confusing. The error appears to be validating my old NIF from attempt 2 somehow, but that may just be my misreading. In any case I adjusted and tried again.

---

**Command (attempt 4):** `aeat config profile create rosa --quiet --tax-id "12345678Z" --name "Rosa" --surnames "Garcia Lopez" --activity "Consultora" --address-postcode "28001" --has-employees --pays-professionals-with-retencion --tax-residence-ccaa madrid`

**Output:**
```
profile  rosa
status   created
next     aeat app modelo work create
```
**Exit:** 0

**How it felt:** Profile created. The `next` hint is excellent - it tells me exactly what command to run next. This is the clearest UX moment in the whole flow.

---

### Step 6: Create a work unit for Modelo 111 Q1 2026

**Command:** `aeat app modelo work create --modelo 111 --year 2026 --period 1T --revision "2019-y-siguientes"`

**Expected:** A work unit created for the first quarter of 2026.

**Output:**
```
operation       modelo.work.create
work_unit_id    317f85186b3c06561d66dc3bcccc3be5469c4411b0f1ad9be56a1b3d14a64c55
bucket_id       default
modelo          111
filing_year     2026
period          1T
revision_id     2019-y-siguientes
name            111-2026-1T
state           borrador
created_at      2026-05-20T19:46:09.228693+00:00
```
**Exit:** 0

**How it felt:** The work unit was created. I got a long `work_unit_id` which I will need to copy for subsequent commands. The auto-generated name `111-2026-1T` is helpful. State `borrador` (draft) makes sense.

---

### Step 7: Calculate the draft for Q1

I know from my records: 1 employee, gross salary 1800 EUR, withholding 270 EUR (15%); 1 professional invoice, 500 EUR, withholding 75 EUR (15%).

**Command:** `aeat app modelo work calculate 317f85... --casilla "01=1" --casilla "02=1800.00" --casilla "03=270.00" --casilla "07=1" --casilla "08=500.00" --casilla "09=75.00"`

**Expected:** Casillas 28 and 30 computed automatically as 345 EUR (270 + 75).

**Output (abridged):**
```
operation    modelo.work.calculate
calculation_revision_id   d2ff76...
state        borrador
casilla   01   1
casilla   02   1800.00
casilla   03   270.00
casilla   07   1
casilla   08   500.00
casilla   09   75.00
...
casilla   28   345.00
casilla   29   0
casilla   30   345.00
```
**Exit:** 0

**How it felt:** This worked exactly as expected. Casilla 28 (total retenciones) = 270 + 75 = 345 EUR. Casilla 30 (resultado a ingresar) = 345 EUR. The computation is correct. All 30 casillas are shown in the output, including the zeros for sections I did not use (prizes, forestry, image rights). This is complete and reassuring.

---

### Step 8: Verify the draft

I saw `verify` in the work subcommands list and it sounds like the next step.

**Command:** `aeat app modelo work verify d2ff76... --by "Rosa"`

**Expected:** Verification accepted, state moves forward.

**Output:**
```
Invalid value: workflow gate aborted run_id='ae533a8f...'
final_stage='ABORTED' reason='DEADLINE_PASSED': Deadline for modelo=111
period=2026Q1 closed on 2026-04-20
```
**Exit:** 2

**How it felt:** Confusing and jarring. The CLI correctly blocked me from verifying a past-due period, but it gave me no guidance on what to do next. The word "ABORTED" felt alarming. I did not know whether this means my data is lost or whether I should try a different period. The error does not say "try period 2T" or "the filing window for Q2 opens on X". I was stuck.

I reasoned that since today is May 2026, Q2 filing (which covers April-June) must be open. I tried again with period `2T`.

---

### Step 9: Create a Q2 work unit and recalculate

**Command:** `aeat app modelo work create --modelo 111 --year 2026 --period 2T --revision "2019-y-siguientes"`

**Output:**
```
operation    modelo.work.create
work_unit_id 5e3ce7a56e471178d10642944c6648c20ba910abe232635f1002bbde09f17b76
periodo      2T
state        borrador
```
**Exit:** 0

**Command:** `aeat app modelo work calculate 5e3ce7... --casilla "01=1" --casilla "02=1800.00" --casilla "03=270.00" --casilla "07=1" --casilla "08=500.00" --casilla "09=75.00"`

**Output:** casilla 28=345.00, casilla 30=345.00

**Exit:** 0

---

### Step 10: Try to verify Q2

**Command:** `aeat app modelo work verify 55cd07... --by "Rosa"`

**Output:**
```
Invalid value: workflow gate aborted run_id='4d343d4f...'
final_stage='ABORTED' reason='PREFLIGHT_FAILED': Preflight failed: deadline
window for modelo 111 period 2026Q2 is not open on 2026-05-20
```
**Exit:** 2

**How it felt:** Even more confusing. Q1 was rejected because the deadline PASSED. Q2 is rejected because the window is NOT OPEN YET. The Q2 filing window for Modelo 111 opens 1 July 2026. But the CLI gives me no information about this. There is no command to tell me "when does the filing window for 111 2T open?" I am completely stuck. I have a correct draft with accurate numbers but I cannot advance the lifecycle at all.

---

### Step 11: Look at the overview

**Command:** `aeat app overview status`

**Output:**
```
Estado del espacio de trabajo
Estas trabajando en el perfil `rosa`.
Aun no se han importado movimientos bancarios.
Aun no se han importado operaciones de negocio.
No se encontraron borradores de declaraciones guardados.
El almacenamiento local cifrado se puede leer con la clave maestra actual.

Que escribir ahora
  aeat app ledger import <extracto-bancario.csv> --provider csv
  aeat app ledger review
  aeat --help
```
**Exit:** 0

**How it felt:** Confusing. It says "No se encontraron borradores de declaraciones guardados" (no saved drafts found) even though I just calculated two drafts. The `calculate` command output said `state: borrador` but the overview does not find them. The "what to write now" section tells me to import bank movements - but I do not need to import a ledger, I need to file a 111. This overview is not relevant to my journey at all.

---

### Step 12: Check the formulas to understand the math

**Command:** `aeat app modelo formulas 111 --explain`

**Output:**
```
formula_id                                 target  inputs               legal_refs
modelo-111-total-retenciones-ingresos      28      03,06,09,12,15,18,21,24,27   ley-35-2006:art-99, ...
modelo-111-resultado-ingresar              30      28, 29               ley-35-2006:art-99, ...
```
**Exit:** 0

**How it felt:** This is excellent. It tells me exactly which casillas feed into the totals and cites the legal articles. A first-time filer probably does not know what `ley-35-2006:art-99` means but it proves the app is grounded in real law, not guesses. The formula logic (sum all withholding sub-totals for casilla 28) matches the real AEAT form.

---

## Did it work?

Partially. The core objective - prepare a Modelo 111 draft with accurate numbers - succeeded. The CLI accepted my data, computed casilla 28 (345 EUR = 270 + 75) and casilla 30 (345 EUR) correctly, and showed all 30 casillas. The calculation is correct.

However I could not advance past the draft state. Both Q1 (deadline passed) and Q2 (window not yet open) are blocked by deadline gates at the `verify` step. For a first-time filer arriving in mid-May, there is literally no period of Modelo 111 that can be verified right now. The CLI does not explain this situation, does not tell me when the Q2 window opens, and does not suggest that the draft is safe and waiting.

The discovery path (help -> list -> describe -> casillas) was clean and logical. Profile creation had minor friction (two wrong flag names, one NIF validation failure). The calculate step was frictionless. The verify step is a wall with no directions posted.

**Goal achieved: No (draft created successfully, lifecycle advance blocked with no guidance).**

## Bugs and gaps

1. **Flag name mismatch in profile create help**
   - Command: `aeat config profile create rosa --quiet ... --pays-professional-invoices ...`
   - Expected: Either the flag works or the help text lists `--pays-professionals-with-retencion` in a way that matches what a non-expert would type
   - Actual: Error `No such option: --pays-professional-invoices`; the truncated help output showed `--pays-profession…` making the full flag name unreadable
   - Severity: **minor** — error message gives correction, but the help text truncation hides the full flag name

2. **Flag name mismatch: `--tax-residence-community` vs `--tax-residence-ccaa`**
   - Command: `aeat config profile create rosa ... --tax-residence-community madrid`
   - Expected: Works, or help text uses term that matches "comunidad autonoma"
   - Actual: Error `No such option: --tax-residence-community Did you mean --tax-residence-ccaa?`
   - Severity: **minor** — `Did you mean` correction is helpful, but `--tax-residence-ccaa` is jargon a non-expert would not naturally type

3. **No deadline/window guidance when `verify` is blocked**
   - Command: `aeat app modelo work verify <id> --by "Rosa"` for both 1T and 2T
   - Expected: Error explains when the filing window opens/closed and what to do now (e.g., "Q2 window opens 2026-07-01; your draft is saved and ready")
   - Actual: Raw `ABORTED reason='DEADLINE_PASSED'` or `PREFLIGHT_FAILED: deadline window ... is not open` with no further guidance, no next-step suggestion, no information on when the window opens
   - Severity: **major** — a first-time filer is completely stuck with no actionable path forward; the draft is correct but the UX provides no way to know this or what to do next

4. **`overview status` does not show calculation revisions**
   - Command: `aeat app overview status` (after two successful `work calculate` runs)
   - Expected: Overview shows the two drafts or at least acknowledges that work units exist
   - Actual: "No se encontraron borradores de declaraciones guardados" and "what to write now" directs to `ledger import`
   - Severity: **major** — the overview is the natural first check for a user returning to their work; it fails to surface existing modelo work units, creating the false impression that nothing has been saved

5. **`describe` output does not explain what `profile_based` cadence means**
   - Command: `aeat app modelo describe 111`
   - Expected: Some inline explanation of cadence tokens, or at minimum "quarterly" equivalent
   - Actual: Shows `cadence: profile_based` with no explanation; periods listed are both monthly (01-12) and quarterly (1T-4T) with no indication of which applies to a typical autonoma
   - Severity: **minor** — confusing for a first-time filer who does not know whether to file monthly or quarterly

6. **`casillas` output shows `required: false` on all casillas including mandatory groupings**
   - Command: `aeat app modelo casillas 111`
   - Expected: Casillas that must be filled (at least casilla 01 or 03 or 09 as a group) would show `required: true`
   - Actual: All 30 casillas show `required: false`
   - Severity: **minor** — not a blocker but misleads the operator about which fields must be filled

7. **No command to query when a filing window opens for a given model and period**
   - There is no `aeat app modelo deadline` or equivalent command
   - Expected: `aeat app modelo readiness --modelo 111 --year 2026 --period 2T` or a new command surfaces the filing window dates
   - Actual: `readiness` checks profile completeness (which it does correctly: `ready: True, missing: 0`) but says nothing about the temporal filing window
   - Severity: **major** — without this, any operator arriving between quarters cannot determine when they can proceed
