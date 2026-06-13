---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-cli-testimonial-findings-inventory-audit]]"
---

# CLI testimonial - Teresa, export and filed records

## What I was trying to do

I am Teresa, an autónoma (freelance consultant in Madrid). I had already heard
the tool can prepare a tax draft and I am past the point of setting up - I want
the **output**. Specifically:

1. Prepare a Modelo 303 quarterly IVA draft.
2. Export it as a fichero-BOE so I can upload it at the AEAT sede electrónica.
3. Check what declarations I have filed before using `app live filed list`.

I am practical: I do not want to understand the internals. I want a file I can
upload and a list showing my history.

---

## My session

### Step 1 — discover the CLI surface

**Command:** `AEAT_LOCAL_STORAGE_ROOT=... uv run --no-sync aeat --help`

**Expectation:** See the top-level commands and find something that says "export".

**Real output (quoted):**
```
aeat - local-first Spanish tax workflow

Section modelo lifecycle
  aeat app modelo list           Modelo list
  aeat app modelo bindings list  Modelo bindings list
  aeat app modelo work           Modelo work

Section diagnostics
  aeat app live filed list   Diagnostics live filed
```

**How it felt:** The top-level help does not mention `modelo export` at all.
The export command is nested under `app modelo` but the root help only exposes
`modelo list`, `bindings list`, and `work`. I only found `export` by running
`aeat app modelo --help` separately. The live filed commands are correctly listed
under "diagnostics". Not catastrophic, but I missed the export verb on first scan.

---

### Step 2 — create a profile

**Command:**
```
aeat config profile create teresa --quiet --tax-id "12345678T" ...
```

**Expectation:** Profile created; silent is fine because I used `--quiet`.

**Real output:**
```
Exit code 2
Refused. NIF/NIE/CIF no válido para wizard.setup.profile.tax-id.prompt: 12345678T.
NIF check letter mismatch: expected 'Z', got 'T'.
  detail: NIF check letter mismatch: expected 'Z', got 'T'
  prompt_key: wizard.setup.profile.tax-id.prompt
  question_id: tax-id
  raw: 12345678T
```

**How it felt:** Good - it caught my typo. The NIF validation works. But
the error leaks internal schema keys (`prompt_key`, `question_id`, `raw`).
A real user sees developer metadata. Minor issue but noisy.

I corrected to `12345678Z` and it succeeded silently (exit 0, no output).

---

### Step 3 — discover that `--tax-residence-community` is wrong

**Command attempt:**
```
aeat config profile create teresa --quiet ... --tax-residence-community madrid
```

**Real output:**
```
Exit code 2
No such option: --tax-residence-community Did you mean --tax-residence-ccaa?
```

**How it felt:** Reasonable error. The auto-suggest (`--tax-residence-ccaa`) is
helpful. I had to guess from English "community" - the help text in the `--help`
output says `--tax-residence-ccaa` clearly but the column is truncated and I missed
it. Minor friction.

---

### Step 4 — find available modelos and create a work unit

**Command:** `aeat app modelo list`

**Real output (26 rows):**
```
code	title	cadence	domain	revisions
303	IVA. Autoliquidacion (trimestral)	quarterly	iva	1
...
```

**How it felt:** 26 modelos, no filter for "which apply to me". I knew I wanted
303 - but a first-time user without tax knowledge cannot tell which of the 26 are
their obligation.

**Command:** `aeat app modelo work create --modelo 303 --year 2025 --period Q1 --revision "2009-y-siguientes"`

**Real output:** Created work unit successfully in `borrador` state.

**How it felt:** Fine - but I used period `Q1` which is wrong. The tool
accepted it silently. The error only surfaced later.

---

### Step 5 — discover the period token problem

**Command:**
```
aeat app modelo work calculate <WU_ID> --casilla "01=10000.00" --casilla "03=2100.00"
```

**Real output:**
```
Exit code 2
Invalid value: registry snapshot for modelo='303' year=2025 period='Q1'
could not be resolved: modelo 303: no revision for year=2025 period='Q1'
revision=None
```

**How it felt:** Confusing. The `work create` command accepted `Q1` without
complaint, but `calculate` fails with a registry resolution error. The error
message does not say "wrong period format, use 1T instead". I had to try `1T`
by intuition from the bindings list output (which showed period `1T`).

I created a second work unit with `--period 1T` and calculation succeeded.

---

### Step 6 — discover the correct casilla input syntax

**Command:**
```
aeat app modelo work calculate <WU_ID> --casilla "01=10000.00" --casilla "03=2100.00"
```

**Real output:**
```
Exit code 1
Error. Identificadores de casilla de entrada desconocidos: 01,03.
  casilla_ids: 01,03
```

**How it felt:** The error is clear but unhelpful. I used the printed form
numbers from the paper modelo (01, 03). The CLI uses semantic IDs
(`iva.repercutido.general`, `iva.soportado.interiores`). There is no discovery
path in the output to tell me the correct IDs.

I ran `aeat app modelo casillas 303 --input-kind manual` which showed only 3
manual casillas (prorrata, regularizacion). Bound casillas are not shown as
enterable. I had to use `--binding` with the binding IDs from `bindings list`
instead of `--casilla`. That worked:

```
aeat app modelo work calculate <WU_ID> \
  --binding "modelo-303-iva-repercutido-general-cuota=2100.00" \
  --binding "modelo-303-iva-soportado-interiores-cuota=1050.00"
```

**Output:**
```
casilla	iva.repercutido.general	2100.00
casilla	iva.cuota-devengada-total	2100.00
casilla	iva.cuota-deducible-total	1050.00
casilla	iva.resultado	1050.00
...
```

The calculation ran and the result looks arithmetically correct.

---

### Step 7 — attempt to verify the draft

**Command:**
```
aeat app modelo work verify <REVISION_ID> --by "teresa"
```

**Expectation:** Move the revision from `borrador` to `verificado-completo`
so I can export it.

**Real output:**
```
Exit code 2
Invalid value: workflow gate aborted run_id='429079dc2f3c2394'
final_stage='ABORTED' reason='NO_PENDING_OBLIGATION':
No pending filing obligation for this profile
```

**How it felt:** Hard stop. I had no idea what a "pending filing obligation" is
or how to register one. I checked `aeat app modelo readiness --modelo 303
--revision-id "2009-y-siguientes" --year 2025 --period 1T` and it said:

```
ready	True
missing	0
```

So readiness says I am ready, but verify says I have no obligation. The two
commands give contradictory answers. There is no CLI command to register or
create an obligation. I tried every `aeat app modelo --help` subcommand
(readiness, work create/calculate/verify/file, filing-record, audit, casillas,
formulas, describe, bindings, reconcile, aggregate, history) and found nothing
that would register an obligation.

This is a dead end. I cannot reach the export path.

---

### Step 8 — attempt to export directly with the draft revision

**Command:**
```
aeat app modelo export <WU_ID> --output m303.bod --revision <REVISION_ID>
```

**Real output:**
```
Exit code 2
Invalid value: calculation revision '<id>' is in state 'borrador';
only verified-complete or filed revisions can be exported
```

**How it felt:** Consistent with the verify gate, but confirms the full
export path is blocked. There is no `--force` or `--skip-verification` flag.

---

### Step 9 — explore the filed-records surface

**Command:** `aeat app live filed list`

**Real output:**
```
Exit code 2
Refused. live AEAT reads require AEAT_LIVE_TESTS_ENABLED=1; current value: 'true'
```

**How it felt:** Interesting - the environment already had `AEAT_LIVE_TESTS_ENABLED`
set to the string `"true"` (probably from some previous session or config file).
The gate requires the integer `1`, not the boolean string `true`. There is no
documentation of this at the command surface. I would have no idea this was the
problem as a real user - the error message says "current value: 'true'" which
sounds like it should work.

I set `AEAT_LIVE_TESTS_ENABLED=1` explicitly. The command then prompted for
Cl@ve Móvil authentication, which requires a real session. Correct behavior -
I cannot authenticate in this test session.

**Command:** `aeat app modelo filing-record list`

**Real output:**
```
operation	modelo.filing_record.list
record_count	0
```

Zero records, as expected for a new profile. The list format is clean.

---

### Step 10 — inspect the overall state

**Command:** `aeat app overview status`

**Real output:**
```
Estado del espacio de trabajo
Estas trabajando en el perfil `teresa`.
Aun no se han importado movimientos bancarios.
Aun no se han importado operaciones de negocio.
No se encontraron borradores de declaraciones guardados.
El almacenamiento local cifrado se puede leer con la clave maestra actual.
```

**How it felt:** Mixes English profile messages with Spanish interface text.
Also, the overview does not mention the two work units I created - they are
apparently not "borradores de declaraciones" in overview's vocabulary.
The output language `en` in my profile was ignored for the body text.

---

## Did it work?

**No.** My primary goal - export a fichero-BOE I could upload to AEAT - was not
achievable. The path create → calculate → verify → export is structurally
blocked: `verify` requires a "pending filing obligation" that has no CLI
registration path. The export command itself is correctly designed and its
error messages are precise, but it is unreachable from the normal workflow.

The filed-records surface (`live filed list`, `filing-record list`) works at
the structural level but is gated on live AEAT authentication for real data.
The local filing-record list runs and returns an empty table correctly.

The calculation core works. I got a coherent Modelo 303 draft with arithmetically
correct values. That part of the tool is solid.

---

## Bugs and gaps

1. **Command:** `aeat app modelo work verify <id>` /
   **Expected:** Revision transitions to `verificado-completo` /
   **Actual:** `NO_PENDING_OBLIGATION` abort with no CLI path to register an
   obligation /
   **Severity:** blocker — the entire verify → export path is unreachable

2. **Command:** `aeat app modelo readiness --modelo 303 --year 2025 --period 1T`
   reports `ready: True` while `verify` immediately aborts with
   `NO_PENDING_OBLIGATION` /
   **Expected:** Readiness and verify agree /
   **Actual:** Contradictory signals — readiness says go, workflow says stop /
   **Severity:** blocker — contradictory CLI surface erodes trust

3. **Command:** `aeat app modelo export <WU_ID> --output ... --revision <borrador-id>` /
   **Expected:** At minimum, a `--force` flag to export a draft for review
   (even without official filing intent) /
   **Actual:** Hard refusal; no way to inspect what the fichero-BOE would look
   like without completing verify /
   **Severity:** major — the export format is unknowable without live auth

4. **Command:** `aeat app live filed list` with `AEAT_LIVE_TESTS_ENABLED=true` (string) /
   **Expected:** Accepted or clear documentation that the value must be integer `1` /
   **Actual:** Refused with "current value: 'true'" - the message implies the
   value is set but wrong, with no hint that `1` vs `true` matters /
   **Severity:** major — silent gate mismatch; standard `.env` boolean syntax fails

5. **Command:** `aeat app modelo work create --periodo Q1` /
   **Expected:** Validation error at create-time if `Q1` is not a valid period
   token for this modelo /
   **Actual:** Silent accept at create; opaque resolution error at calculate /
   **Severity:** major — late validation with a misleading error (already
   confirmed in findings inventory #9, reproduced here)

6. **Command:** `aeat app modelo work calculate <id> --casilla "01=10000.00"` /
   **Expected:** Error message names valid input casilla IDs, or points to
   the discovery command /
   **Actual:** "Identificadores de casilla de entrada desconocidos: 01,03" with
   no hint that bound-casilla values require `--binding` with semantic IDs /
   **Severity:** major — the `--casilla` vs `--binding` distinction is
   undiscoverable from the error

7. **Command:** `aeat config profile create teresa --quiet --tax-id "12345678T"` /
   **Expected:** Clean "invalid NIF" message /
   **Actual:** Message includes `prompt_key`, `question_id`, `raw` internal schema
   fields /
   **Severity:** minor — information leak of internal field names to operator

8. **Command:** `aeat app overview status` with `output-language: en` profile /
   **Expected:** English output /
   **Actual:** Spanish body text; the `output-language` profile setting appears
   to have no effect on the overview body /
   **Severity:** minor — profile localisation not applied to overview

9. **Command:** `aeat app overview status` after creating two work units /
   **Expected:** Work units visible as draft declarations /
   **Actual:** "No se encontraron borradores de declaraciones guardados" — the
   overview does not surface work units as draft declarations /
   **Severity:** minor — incomplete overview vocabulary
