---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# CLI testimonial - Sofia, deadline-checking owner

## What I was trying to do

I am a small-business owner (consultora autónoma). I do not want to learn tax law.
I want the tool to answer one question: **what do I need to file, and when?**
I opened the CLI for the first time to find out whether it can orient a non-expert
with no prior data loaded.

---

## My session

### Step 1 — discover the tool

**Command:** `aeat --help`

**Expectation:** A single sentence telling me what this tool does, followed by a
short list of things I can actually do today.

**Real output (quoted):**
```
aeat - local-first Spanish tax workflow

The CLI has exactly two roots: config and app.
Use config for local state and app for tax work.

Section setup
  aeat config profile create NAME  Setup create profile
  ...
Section daily ledger
  aeat app ledger import ...
  ...
Section modelo lifecycle
  aeat app modelo list ...
Section diagnostics
  aeat app overview status   Diagnostics overview
  aeat app review queue      Diagnostics review queue
  ...
```

**How it felt:** The two-root structure (`config` / `app`) is sensible and the
grouping into sections helps. However the word "Diagnostics" as the section label
for `overview status` and `review queue` is off-putting — to a business owner,
"diagnostics" means something is broken. The word I want is "agenda" or "what's
due". Overall: acceptable start, but labelling friction.

---

### Step 2 — create a profile

**Command:** `aeat config profile create Sofia`

**Expectation:** A guided questionnaire or at least a clear list of required flags.

**Real output:**
```
Refused. No pude abrir el asistente guiado en esta ejecución.
Todavía no se ha guardado nada.

Prueba otra vez el asistente desde una sesión de terminal interactiva:
  aeat config profile create NAME
...
-> Run `aeat config profile create NAME --quiet --tax-id NIF --activity ACTIVITY`
```

**How it felt:** Confusing — the command itself told me to run the same command
again in "an interactive terminal session". The fallback hint pointing to `--quiet`
flags was buried after the error. A non-expert reading "Refused" + "No pude abrir
el asistente" would likely give up. The recovery path is only visible if you scroll
past the alarming error block.

---

### Step 3 — first quiet profile attempt (wrong NIF)

**Command:** `aeat config profile create Sofia --quiet --tax-id 12345678A --activity "Consultoría" --taxation-type 1`

**Expectation:** Either accept or tell me what a valid NIF looks like.

**Real output:**
```
Refused. NIF/NIE/CIF no válido para wizard.setup.profile.tax-id.prompt: 12345678A.
NIF check letter mismatch: expected 'Z', got 'A'.
  detail: NIF check letter mismatch: expected 'Z', got 'A'
  prompt_key: wizard.setup.profile.tax-id.prompt
  question_id: tax-id
  raw: 12345678A
```

**How it felt:** The raw internal fields `prompt_key`, `question_id`, `raw` are
developer noise — completely meaningless to Sofia. The one useful fact (expected
letter `'Z'`) is there, but buried. The word "Refused" as a header for every
error is harsh and unhelpful.

---

### Step 4 — second quiet profile attempt (valid NIF)

**Command:** `aeat config profile create Sofia --quiet --tax-id 12345678Z --activity "Consultoría" --taxation-type 1`

**Real output:** *(no output, exit 0)*

**How it felt:** Succeeded silently. No confirmation, no "Profile Sofia created
successfully. Next: run `aeat app overview status`." — just nothing. A non-expert
would not know whether the command worked.

---

### Step 5 — profile status

**Command:** `aeat config profile status`

**Real output:**
```
profile	Sofia
identity.tax_id	12345678Z
activities.description	Consultoría
iva.regime	GENERAL
tax_residence.ccaa	madrid
Próximo paso: `aeat app overview status`
```

**How it felt:** The tab-separated key-value format is readable. The "Próximo paso"
line is excellent — exactly the kind of nudge a non-expert needs. Minor: the key
names use dot-notation (`identity.tax_id`, `activities.description`) which looks
like internal field paths, not plain language.

---

### Step 6 — the main overview

**Command:** `aeat app overview status`

**Real output:**
```
Estado del espacio de trabajo

Estas trabajando en el perfil `Sofia`.
Aun no se han importado movimientos bancarios.
Aun no se han importado operaciones de negocio.
No se encontraron borradores de declaraciones guardados.
El almacenamiento local cifrado se puede leer con la clave maestra actual.

Que escribir ahora
  aeat app ledger import <extracto-bancario.csv> --provider csv - importar movimientos bancarios.
  aeat app ledger review - revisar filas importadas.
  aeat --help - volver a la guia de comandos.
```

**How it felt:** This is the most important screen and it is a mixed result.

Good things:
- Plain-language prose ("Aún no se han importado…") — feels approachable.
- "Qué escribir ahora" section with concrete next commands — genuinely helpful.

Missing things that matter most to Sofia:
- **No deadlines anywhere.** The question I came to answer — "what do I need to
  file and when?" — is completely unanswered. There is no mention that quarterly
  IVA (303) is due 20 July, or that quarterly IRPF advance (130) follows the
  same date, or any other upcoming obligation.
- **No list of forms that apply to my profile.** Given I told it my activity
  (Consultoría) and taxation type, the tool knows I am obligated to file 303 and
  130 quarterly. It does not say so.
- **"El almacenamiento local cifrado se puede leer con la clave maestra actual"**
  is technical reassurance that means nothing to a business owner. It should be
  invisible unless there is a problem.

---

### Step 7 — overview with a period

**Command:** `aeat app overview status --period 2026-Q1`

**Real output:**
```
Periodo	2026Q1
Borradores	0
```

**How it felt:** Two fields. That is all. "Borradores: 0" tells me nothing about
whether Q1 filings are overdue, complete, or irrelevant to me. A non-expert
reading this would not understand what "borradores" means or why zero is good
or bad.

**Command:** `aeat app overview status --period 2026-Q2 --verbose`

**Real output:** Same two fields. `--verbose` had no visible effect.

---

### Step 8 — review queue

**Command:** `aeat app review queue`

**Real output:**
```
ID	Tipo	Tipo origen	Objeto	Bucket	Periodo	Severidad	Siguiente
No hay elementos pendientes de revisión.
```

**How it felt:** Clean empty-state message. But the column header "Tipo origen"
and "Tipo" are jargon. More importantly, showing a column header row before the
empty message makes it look like a table with missing data rather than a
confirmed-empty state. A dedicated message like "Todo en orden — no hay nada en
cola" would feel more reassuring.

---

### Step 9 — modelo list (exploring what applies to me)

**Command:** `aeat app modelo list`

**Real output:** 26 rows of modelos with columns `code`, `title`, `cadence`,
`domain`, `revisions`.

**How it felt:** An unfiltered catalogue of all Spanish tax forms — from Modelo
036 to Modelo 840. For a non-expert this is overwhelming. There is no indication
of which of these 26 forms actually apply to my profile. No "applies to you"
column, no filtering by profile.

---

### Step 10 — modelo describe (trying to find a deadline)

**Command:** `aeat app modelo describe 303 --period 2026Q2`

**Real output:**
```
Modelo	303
Title	IVA. Autoliquidacion (trimestral)
...
Cadence	quarterly
Periods	1T, 2T, 3T, 4T
Casillas	20
Bindings	6
Formulas	9
```

**How it felt:** Technical inventory — casillas, bindings, formulas. No deadline
date, no "for Q2 2026 this is due on 20 July 2026", no plain-language explanation
of what IVA autoliquidación means or why I should care.

---

### Step 11 — checking for a calendar or agenda

I looked at every command under `aeat app --help` seeking any concept of a
deadline, calendar, agenda, or "what is due when". There is none. The closest
is `aeat app modelo list` but that is a catalogue with no dates and no
profile-relevance filter.

**Commands tried:** `aeat app --help`, `aeat app modelo work list`, `aeat app
ledger status`.

**All empty-state results confirmed** — the tool has no deadline or calendar
surface whatsoever.

---

## Did it work?

**No.** The tool did not answer "what do I need to file and when?"

The profile creation works (though it is rough for non-experts). The overview
command loads and gives a reasonable empty-state orientation. But the core
question — upcoming filing obligations with concrete due dates — has no answer
anywhere in the CLI. The tool is oriented around data-import and form-calculation
workflows, not around orienting a non-expert to their filing calendar.

The empty-state experience for a fresh profile is partially usable: the overview
tells me what to import next, and the profile status hints at the next command.
But none of these surfaces tells me "you are obligated to file Modelo 303 by
20 July 2026 for Q2".

---

## Bugs and gaps

**1.**
- Command: `aeat config profile create Sofia` (interactive mode in non-interactive shell)
- Expected: A clear message saying "use `--quiet` with these flags: `--tax-id`, `--activity`"
- Actual: "Refused. No pude abrir el asistente guiado en esta ejecución." followed by the same command as the suggestion, with `--quiet` buried at the bottom
- Severity: **major** — a non-expert will not understand the error and will not find the recovery path

**2.**
- Command: `aeat config profile create Sofia --quiet --tax-id 12345678Z ...` (success)
- Expected: Confirmation output ("Profile Sofia created. Run `aeat app overview status` to continue.")
- Actual: Silent exit with no output
- Severity: **major** — silent success is indistinguishable from silent failure for a non-expert

**3.**
- Command: `aeat app overview status` (and `--period`, `--verbose`)
- Expected: A list of upcoming filing deadlines for this profile (303, 130, etc.) with due dates
- Actual: No deadline information anywhere; "Qué escribir ahora" only directs to ledger import
- Severity: **blocker** — the tool cannot answer the user's primary question

**4.**
- Command: `aeat app overview status --period 2026-Q1`
- Expected: Meaningful period-scoped status (obligations, deadlines, completion state)
- Actual: `Periodo	2026Q1` / `Borradores	0` — two raw fields with no context
- Severity: **major** — the period flag exists but the output is not useful to a non-expert

**5.**
- Command: `aeat app overview status --verbose`
- Expected: Additional detail vs the non-verbose output
- Actual: Identical output — `--verbose` has no visible effect on empty profile
- Severity: **minor** — flag exists but does nothing observable at this state

**6.**
- Command: `aeat app modelo list`
- Expected: A profile-filtered list showing only the modelos that apply to Sofia's activity and tax type
- Actual: All 26 modelos in the registry — an unfiltered catalogue with no "applies to you" signal
- Severity: **major** — overwhelming for a non-expert; makes the registry feel like internal scaffolding

**7.**
- Command: `aeat app modelo describe 303 --period 2026Q2`
- Expected: Plain-language explanation plus the actual deadline date for Q2 2026
- Actual: Technical inventory (casillas, bindings, formulas) with no deadline date
- Severity: **major** — model describe is a developer-facing schema dump, not a user-facing calendar entry

**8.**
- Command (any): looking for an agenda/calendar/deadline surface
- Expected: A command like `aeat app agenda` or `aeat app deadlines` listing upcoming obligations by date
- Actual: No such command exists anywhere in the CLI
- Severity: **blocker** — the entire deadline-orientation use-case is absent

**9.**
- Error output (profile NIF validation): fields `prompt_key`, `question_id`, `raw` exposed in error
- Expected: Plain-language: "NIF format error: the check letter for 12345678 should be Z, not A."
- Actual: Raw internal field dump with developer-facing key names
- Severity: **minor** — ugly and confusing but the answer is technically present
