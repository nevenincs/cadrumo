---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# CLI testimonial - Lucia, first-time autonoma

## What I was trying to do

I registered as autónoma (self-employed, freelance graphic designer) in Valencia this year. A friend told me this tool helps with Spanish taxes. I wanted to:

1. Create a profile for myself so the tool knows who I am
2. Tell it I am self-employed doing graphic design
3. Find out which taxes I will have to deal with this year as a new autónoma

I have never used this tool before. I know about taxes — Modelo 303 every quarter, IRPF payments — but I am not a software person.

---

## My session

### Step 1 — First look

I ran `aeat --help` (prefixed with the storage variable). The output was clear and reassuring. Two sections: `config` for setup, `app` for tax work. It told me to start with `aeat config profile create NAME`. Good — that is logical.

```
aeat - local-first Spanish tax workflow

The CLI has exactly two roots: config and app.
Use config for local state and app for tax work.

Section setup
  aeat config profile create NAME  Setup create profile
  ...
```

*Feeling: pleased — the help is clear and in Spanish (mostly).*

---

### Step 2 — Try to create a profile interactively

The help said `aeat config profile create NAME`, so I tried that with my name piped through standard input, expecting the tool to ask me questions one by one like a wizard. I typed answers for NIF, name, postcode, etc.

**Command:**
```
echo "48001\nLucia\n..." | aeat config profile create lucia
```

**Output:**
```
Exit code 2
Refused. No pude abrir el asistente guiado en esta ejecución.
Todavía no se ha guardado nada.

Prueba otra vez el asistente desde una sesión de terminal interactiva:
  aeat config profile create NAME
...
-> Run `aeat config profile create NAME --quiet --tax-id NIF --activity ACTIVITY`
```

*Feeling: confused and slightly frustrated. The tool detected I was not in an interactive terminal (I was piping input). The error message is in Spanish — good — but it says "try again from an interactive terminal session." This is helpful. It also suggests the `--quiet` fallback. I follow that suggestion.*

---

### Step 3 — Read the help for profile create

I ran `aeat config profile create --help` to understand what flags I need for `--quiet` mode. The help is very long — almost overwhelming — with ~40 options. I do not know what "taxation-type [1|2]" means, or what "taxpayer-marital-status [1|2|3|4]" codes represent. There are no descriptions of what 1 vs 2 means for taxation type — just a code list.

I guessed: taxation-type 1 = estimación directa (normal for freelancers), output-language es (Spanish), sex M (mujer), marital-status 1 (soltera). I also noticed the option name shown in the help was `--tax-residence-ccaa` but in some places the truncated label was confusingly cut off mid-word.

*Feeling: slightly lost. The codes like `[1|2]` are opaque without explanation. A real autónoma would not know that "1" means estimación directa without googling. The option names are truncated in the table display.*

---

### Step 4 — First attempt at --quiet creation (wrong option name)

I tried `--tax-residence-region` because the help table showed a truncated option name and I guessed the full name. 

**Command:**
```
aeat config profile create lucia --quiet --tax-id "48123456L" --name "Lucia" ... --tax-residence-region comunidad_valenciana
```

**Output:**
```
No such option: --tax-residence-region Did you mean --tax-residence-ccaa?
```

*Feeling: okay, the error is helpful — it suggested the right name. One correction.*

---

### Step 5 — Second attempt (wrong NIF check letter)

I used a made-up NIF `48123456L`. The tool validated it properly and rejected it.

**Command:**
```
aeat config profile create lucia --quiet --tax-id "48123456L" ... --tax-residence-ccaa comunidad_valenciana
```

**Output:**
```
Exit code 2
Refused. NIF/NIE/CIF no válido para wizard.setup.profile.tax-id.prompt: 48123456L.
NIF check letter mismatch: expected 'G', got 'L'.
  detail: NIF check letter mismatch: expected 'G', got 'L'
  prompt_key: wizard.setup.profile.tax-id.prompt
  question_id: tax-id
  raw: 48123456L
```

*Feeling: good that it validates — that is correct behaviour. The error message is a bit technical (prompt_key, question_id) but the core message "expected 'G', got 'L'" is clear enough. I corrected the check letter to G.*

Note: there is a developer-facing leak here. `prompt_key: wizard.setup.profile.tax-id.prompt` and `question_id: tax-id` are internal identifiers that a real user should never see. An autónoma does not know what a "prompt_key" or "question_id" is.

---

### Step 6 — Profile created successfully

With the corrected NIF `48123456G`, the command succeeded silently (no output, exit 0).

**Command:**
```
aeat config profile create lucia --quiet --tax-id "48123456G" --name "Lucia" --surnames "Martinez Garcia" --activity "diseno grafico" --address-postcode "46001" --taxation-type 1 --output-language es --taxpayer-sex M --taxpayer-marital-status 1 --taxpayer-birth-date "1990-03-15" --tax-residence-ccaa comunidad_valenciana
```

**Output:** *(nothing — completely silent, exit 0)*

*Feeling: confused. Did it work? There is no confirmation message. No "¡Perfil creado!" No summary. Silence is unnerving after all those flags.*

---

### Step 7 — Verify the profile exists

I ran `aeat config profile show` and got a nice flat table confirming the profile was created with all my data.

**Output (excerpt):**
```
readiness    ready   issues=0
profile_id   lucia
display_name lucia
status       active
activities.description   diseno grafico
identity.name    Lucia
identity.tax_id  48123456G
tax_residence.ccaa   comunidad_valenciana
...
```

*Feeling: relieved. It worked. The table format is readable. I can see my data.*

---

### Step 8 — What taxes do I owe?

I ran `aeat app overview status` hoping to see something like "as an autónoma you need to file: Modelo 303 quarterly, Modelo 130 quarterly..."

**Output:**
```
Estado del espacio de trabajo

Estas trabajando en el perfil `lucia`.
Aun no se han importado movimientos bancarios.
Aun no se han importado operaciones de negocio.
No se encontraron borradores de declaraciones guardados.
El almacenamiento local cifrado se puede leer con la clave maestra actual.

Que escribir ahora
  aeat app ledger import <extracto-bancario.csv> --provider csv - importar movimientos bancarios.
  aeat app ledger review - revisar filas importadas.
  aeat --help - volver a la guia de comandos.
```

*Feeling: disappointed. I asked "what taxes do I owe?" and got "you haven't imported bank movements yet." That is not an answer to my question. I wanted a list of obligations based on my profile. The tool knows I am autónoma, I pay IVA régimen general, I do not have employees — surely it can say "you will need to file 303 every quarter and 130 every quarter." Instead it pushed me toward importing bank statements without explaining why.*

---

### Step 9 — Explore modelo list

I ran `aeat app modelo list` and got a full list of 26 modelos. This is the closest thing to an answer — I can see 303, 130, 100, 390 etc. But there is no indication of which ones apply to *me*. Everything is listed with no filtering by profile.

*Feeling: overwhelmed. 26 modelos. Which ones are mine? I do not know if I need Modelo 200 (that is for companies — I am not a company). I do not know if I need 347. The list gives me no guidance.*

---

### Step 10 — Try profile status (CRASH)

I ran `aeat config profile status` hoping for a readiness summary or obligations overview.

**Output:**
```
Exit code 1
Traceback (most recent call last):
  ...
  File "src/aeat/application/user_profile/_orchestration.py", line 33, in <module>
    from ..workflow._bucket_pointer import BucketPointer
ModuleNotFoundError: No module named 'aeat.application.workflow._bucket_pointer'
```

*Feeling: shocked and panicked. A Python traceback appeared. I do not know what this means. I have broken something? Is my data lost? What do I do now?*

---

### Step 11 — The CLI is completely broken

After the crash, I tried `aeat --help` again. 

**Output:**
```
Exit code 1
Traceback (most recent call last):
  ...
ModuleNotFoundError: No module named 'aeat.application.workflow._bucket_pointer'
```

Every single command now crashes with the same traceback. The entire CLI is dead. `aeat --help` itself crashes. I cannot do anything. The profile I just created is inaccessible. I am completely stuck.

*Feeling: very upset and confused. I did not do anything wrong. I just typed `aeat config profile status` — a command that was listed in the help — and now nothing works at all. I would uninstall the tool and call my gestora.*

---

## Did it work?

**Partially — then completely broken.**

I successfully created a profile (Step 6) and confirmed the data was saved (Step 7). I found the list of available modelos (Step 9). But:

- I never got an answer to "which taxes apply to me as a new autónoma" — the tool has no profile-aware obligation summary.
- Running `aeat config profile status` (a documented command) triggered a Python crash that made the entire CLI unusable for the rest of the session. Goal blocked.

---

## Bugs and gaps

**1. `aeat config profile status` crashes with `ModuleNotFoundError`**

- Command: `aeat config profile status`
- Expected: A summary of the profile's readiness and/or which tax obligations apply.
- Actual: `ModuleNotFoundError: No module named 'aeat.application.workflow._bucket_pointer'` — Python traceback, exit 1.
- Severity: **BLOCKER** — the import error propagates to the module-level `__init__.py` import, which means ALL subsequent `aeat` commands crash identically, including `aeat --help`. The tool is entirely unusable after this one command.

**2. `aeat config profile show` also crashes after bug #1 triggers**

- Command: `aeat config profile show` (and all other commands)
- Expected: Normal operation.
- Actual: Same `ModuleNotFoundError` traceback, exit 1. Once the module import fails on any command, the entire process is poisoned for the session.
- Severity: **BLOCKER** — consequence of bug #1. Every aeat invocation crashes. User cannot recover without reinstalling or fixing the code.

**3. No profile-aware obligation summary**

- Command: `aeat app overview status` after profile creation
- Expected: "Based on your profile (autónoma, IVA régimen general, no employees, Comunitat Valenciana), you are required to file: Modelo 303 quarterly, Modelo 130 quarterly, Modelo 390 annually, Modelo 100 annually."
- Actual: "You haven't imported bank movements yet." — no tax obligation guidance at all.
- Severity: **Major** — this is the core use case for a first-time autónoma: "what do I need to file?" The tool has all the information (activity, IVA regime, profile) but does not surface it.

**4. Silent success on profile creation**

- Command: `aeat config profile create lucia --quiet ...` (successful run)
- Expected: A confirmation message, e.g. "Perfil 'lucia' creado. Activo ahora."
- Actual: No output whatsoever (exit 0, complete silence).
- Severity: **Major** — a new user cannot tell whether the command succeeded or was silently dropped. They must run a second command (`profile show`) to verify. This pattern causes anxiety and double-entry.

**5. Developer-internal field names leaked in NIF validation error**

- Command: `aeat config profile create lucia --quiet --tax-id "48123456L" ...`
- Expected: "NIF no válido: la letra de control debe ser G, no L."
- Actual: `prompt_key: wizard.setup.profile.tax-id.prompt` and `question_id: tax-id` are shown in the error output alongside the user-readable message.
- Severity: **Minor** — confusing to a non-technical user, but the core error message is understandable. The internal keys should be stripped from user-facing output.

**6. Taxation-type option has undocumented codes**

- Command: `aeat config profile create --help`
- Expected: `--taxation-type [1|2]` with an explanation of what 1 and 2 mean (e.g., "1 = estimación directa, 2 = estimación objetiva").
- Actual: Only the code list `[1|2]` is shown. No description of what each code means.
- Severity: **Major** — an autónoma registering for the first time must choose the correct taxation type. Codes without labels are not actionable. Same applies to `--taxpayer-marital-status [1|2|3|4]`.

**7. Interactive wizard refused from non-TTY but offers no clear fallback path in the error message**

- Command: `aeat config profile create lucia` (with piped stdin)
- Expected: Either run interactively or clearly explain all required flags.
- Actual: Error says "run from an interactive terminal session" and hints at `--quiet`. The `--quiet` mode requires knowing ~10+ flags upfront — there is no intermediate guided path.
- Severity: **Minor** — the error message does point toward `--quiet` as the workaround, which is acceptable, but the flag count needed is daunting for a first-time user.

**8. `aeat app modelo list` shows all 26 modelos without profile-based filtering**

- Command: `aeat app modelo list`
- Expected: Filtered list showing only modelos relevant to Lucia's profile (autónoma, graphic design, IVA general, no employees).
- Actual: All 26 modelos listed, including corporate ones (200, 202, 232) that do not apply.
- Severity: **Major** — a first-time user has no way to distinguish which modelos apply to them. Seeing Modelo 200 (Impuesto sobre Sociedades) is actively misleading for an individual autónoma.

**9. Period format is inconsistent between commands**

- `aeat app modelo bindings list --period 2026Q1` (with `--year 2026`) produces: `Invalid value: period must be YYYY, YYYYQn, YYYY-Qn, or YYYY-MM; got '2026-2026Q1'` — the year was prepended to the period internally, creating `2026-2026Q1`. The `--year` and `--period` flags interact in a non-obvious way.
- `aeat app modelo work create --period Q1` fails on calculate with "no revision for year=2026 period='Q1'". The period token `1T` (Spanish format) works where `Q1` does not, but the help shows both as examples without distinguishing which commands prefer which format.
- Severity: **Major** — inconsistent period handling between subcommands. A user trying `Q1` in one place and `1T` in another gets silent or confusing failures.
