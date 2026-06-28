---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-20-cli-persona-task-catalogue-reference]]"
---

# CLI testimonial - Marta, live filed records

## What I was trying to do

I am Marta, an autonoma. I work freelance and I file my declarations
myself — mostly quarterly IVA and the annual Renta. I do not fully
trust my own memory of what I have actually submitted to AEAT this
year, especially the exact dates and reference numbers. Someone told me
this tool can read back what is on file at AEAT without submitting
anything new. I want to check my Modelo 100 history for 2024 and 2025.
I am not a developer; I follow the help text and try to make sense of
what the tool asks me for.

## My session

### Step 1 — discovering the live commands

**Command:**
```
uv run --no-sync aeat app live --help
```

**What I expected:** A list of things I can read from AEAT.

**Real output:**
```
 Usage: aeat app live [OPTIONS] COMMAND [ARGS]...

 Comandos de observación AEAT en vivo de solo lectura

┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ filed          Observaciones de declaraciones presentadas de solo lectura   │
│ iva-wallet     Captura de la cartera de compensación de IVA de la AEAT      │
│ notifications  Snapshots de notificaciones DEHú de solo lectura             │
│ portals        Catálogo local de portales AEAT de solo lectura              │
│ expedientes    Snapshots de expedientes AEAT de solo lectura                │
│ verify         Registro de auditoría de verificaciones NIF de solo lectura  │
│ borrador       Snapshots de borrador del modelo 100                         │
└─────────────────────────────────────────────────────────────────────────────┘
```
**Exit code:** 0

**How it felt:** Good. The word `filed` jumped out — that is exactly
what I want. "Declaraciones presentadas" is the right language. I felt
confident this was the right path.

---

### Step 2 — exploring `filed`

**Command:**
```
uv run --no-sync aeat app live filed --help
```

**What I expected:** More detail about reading my filed declarations.

**Real output:**
```
 Usage: aeat app live filed [OPTIONS] COMMAND [ARGS]...

 Observaciones de declaraciones presentadas de solo lectura

┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ list             Listar declaraciones presentadas sin descargar artefactos  │
│ capture          Capturar datos de declaraciones presentadas desde AEAT     │
│ capture-sources  Capturar observaciones presentadas requeridas por una      │
│                  declaración objetivo                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```
**Exit code:** 0

**How it felt:** Three commands: `list`, `capture`, `capture-sources`.
`list` sounded like what I wanted first — just see what is there. Good
progression.

---

### Step 3 — `filed list --help`

**Command:**
```
uv run --no-sync aeat app live filed list --help
```

**What I expected:** A way to filter by year and model number.

**Real output:**
```
 Usage: aeat app live filed list [OPTIONS]

 Listar declaraciones presentadas sin descargar artefactos

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --modelo           TEXT                         Código de modelo            │
│ --from-year        INTEGER RANGE [2000<=x<=2099] Primer ejercicio           │
│ --to-year          INTEGER RANGE [2000<=x<=2099] Último ejercicio           │
│ --help                                          Show this message and exit. │
└─────────────────────────────────────────────────────────────────────────────┘
```
**Exit code:** 0

**How it felt:** Clear. The options are sensible — filter by modelo and
year range. All optional, so I can list everything. No `[required]`
markers anywhere. I felt ready to just run it.

---

### Step 4 — `filed capture --help`

**Command:**
```
uv run --no-sync aeat app live filed capture --help
```

**Real output:**
```
 Usage: aeat app live filed capture [OPTIONS]

 Capturar datos de declaraciones presentadas desde AEAT

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ *  --modelo             TEXT              Código de modelo [required]       │
│ *  --year               INTEGER RANGE ... Ejercicio de presentación [req.]  │
│    --output-root        DIRECTORY         Directorio para observaciones...  │
│    --period             TEXT              Periodo de presentación           │
│    --expediente         TEXT              Identificador de expediente AEAT  │
│    --limit              INTEGER RANGE     Número máximo de filas a capturar │
│    --help                                 Show this message and exit.       │
└─────────────────────────────────────────────────────────────────────────────┘
```
**Exit code:** 0

**How it felt:** Reasonable. Two required fields — `--modelo` and
`--year`. I know my modelo (100) and my year (2025). The `--output-root`
default was truncated though: it showed
`var\aeat\filed-declarati…` — I cannot see the full default path. Minor
annoyance.

---

### Step 5 — `filed capture-sources --help`

**Command:**
```
uv run --no-sync aeat app live filed capture-sources --help
```

**Real output:**
```
 Usage: aeat app live filed capture-sources [OPTIONS]

 Capturar observaciones presentadas requeridas por una declaración objetivo

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ *  --modelo               TEXT              Código de modelo [required]     │
│ *  --year                 INTEGER RANGE ... Ejercicio [required]            │
│ *  --period               TEXT              Periodo de presentación [req.]  │
│    --output-root          DIRECTORY         ...                             │
│    --registry-root        DIRECTORY         Raíz del registro               │
│    --source-root          DIRECTORY         Raíz del proyecto               │
│    --help                                   Show this message and exit.     │
└─────────────────────────────────────────────────────────────────────────────┘
```
**Exit code:** 0

**How it felt:** Three required args here. The `--period` concept was not
obvious to me — I would need to know the period code format (e.g. `0A`
for annual). `--registry-root` and `--source-root` look internal and
technical — not something I would know to supply. Their descriptions
("raíz del registro", "raíz del proyecto") did not help me understand
whether I need them at all.

---

### Step 6 — trying to actually list my declarations

**Command:**
```
uv run --no-sync aeat app live filed list
```

**What I expected:** Either my declarations or a prompt asking me to log in.

**Real output:**
```
Refused. live AEAT reads require AEAT_LIVE_TESTS_ENABLED=1; current value: 'true'
```
**Exit code:** 2

**How it felt:** Confusing and alarming. It says `AEAT_LIVE_TESTS_ENABLED=1`
is required, but also says the current value is `'true'`. Those two
things contradict each other. Does it want `1` or `true`? If it already
has `true`, why is it refusing? I do not know what an environment
variable is, and this message gives me nothing actionable as a user. A
non-developer would stop here, baffled.

---

### Step 7 — trying with the environment flag (setting to `1`)

I guessed that maybe `true` was not the same as `1`.

**Command:**
```
AEAT_LIVE_TESTS_ENABLED=1 uv run --no-sync aeat app live filed list
```

**What I expected:** My declarations or a clear auth error.

**Real output:**
```
Traceback (most recent call last):
  ...
  ImportError: cannot import name 'DisenoCompletenessCasilla' from
  'aeat.domain.calculations.registry._schema'
```
**Exit code:** 1

**How it felt:** A Python crash. The program exploded internally. This is
not my fault — I have not done anything wrong — but it looks like the
software is broken. No user-facing error message. No guidance. A wall of
technical traceback. I would assume the tool is broken and give up.

---

### Step 8 — trying `capture` with required args and live flag

**Command:**
```
AEAT_LIVE_TESTS_ENABLED=1 uv run --no-sync aeat app live filed capture --modelo 100 --year 2025
```

**What I expected:** A login prompt or clear auth error.

**Real output:**
```
Refused. No hay un perfil activo.
```
**Exit code:** 2

**How it felt:** Finally a message in Spanish that I understand. "There
is no active profile." I know what a profile is from the `config`
section. This is helpful — it tells me the next step. But I only reached
this message because the `list` command crashed first, so I lost
confidence in the tool before I could discover this coherent error.

---

### Step 9 — trying `capture-sources` with all required args and live flag

**Command:**
```
AEAT_LIVE_TESTS_ENABLED=1 uv run --no-sync aeat app live filed capture-sources --modelo 100 --year 2025 --period 0A
```

**What I expected:** A login prompt or profile error.

**Real output:**
```
Refused. No hay un perfil activo.
```
**Exit code:** 2

**How it felt:** Same as above — coherent message once past the live-flag
gate. Consistent.

---

### Step 10 — confirming the error for missing `--year`

**Command:**
```
uv run --no-sync aeat app live filed capture --modelo 100
```

**Real output:**
```
Usage: aeat app live filed capture [OPTIONS]
Try 'aeat app live filed capture --help' for help.
┌─ Error ─────────────────────────────────────────────────────────────────────┐
│ Missing option '--year'.                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```
**Exit code:** 2

**How it felt:** Good. Click's built-in validation is working and
delivers a clean, actionable error message.

---

### Step 11 — `filed list` with year filters

**Command:**
```
AEAT_LIVE_TESTS_ENABLED=1 uv run --no-sync aeat app live filed list --from-year 2024 --to-year 2025
```

**Real output:**
```
Refused. No hay un perfil activo.
```
**Exit code:** 2

**How it felt:** Same profile error. Consistent. I have hit the wall
where I would need real credentials. Stopping here.

---

## Did it work?

**Partial.** The help text and surface discovery worked well. The
command tree is coherent — the Spanish descriptions are accurate, the
required/optional distinction is clear in help, and Click validation for
missing required options is clean.

The live execution surface fails in two distinct ways before real
authentication is reached:

1. `aeat app live filed list` (and any `live` command without the live
   flag) produces a contradictory error message: it says the flag is
   required but simultaneously reports the current value is already
   `true`. Confusing enough to block a non-expert entirely.

2. Setting `AEAT_LIVE_TESTS_ENABLED=1` reveals an **import crash**
   (`ImportError: cannot import name 'DisenoCompletenessCasilla'`) that
   kills the `list` command before it can even check for a profile.
   `capture` and `capture-sources` do NOT crash — they reach the correct
   "no active profile" refusal. So `list` is broken while `capture` and
   `capture-sources` are coherent.

I could not get to the authentication gate via `list` at all. The tool
does clearly tell me it needs a profile once I use `capture` correctly.
Stopping point: "No hay un perfil activo" — this is the expected wall
for a user without AEAT credentials configured.

---

## Bugs and gaps

**1. `filed list` import crash under `AEAT_LIVE_TESTS_ENABLED=1`**
- Command: `AEAT_LIVE_TESTS_ENABLED=1 uv run --no-sync aeat app live filed list`
- Expected: "No hay un perfil activo" refusal (same as `capture`)
- Actual: `ImportError: cannot import name 'DisenoCompletenessCasilla' from 'aeat.domain.calculations.registry._schema'`; traceback dumped raw to terminal; exit 1
- Severity: **blocker** — the command is unreachable; a user who follows the help surface hits an internal crash

**2. Contradictory live-gate refusal message**
- Command: `uv run --no-sync aeat app live filed list` (any live command without the flag)
- Expected: "Live reads require AEAT_LIVE_TESTS_ENABLED=1 (set it to 1 to proceed)"
- Actual: "Refused. live AEAT reads require AEAT_LIVE_TESTS_ENABLED=1; current value: 'true'" — implies the check is already satisfied, but the command is still refused
- Severity: **major** — the message is internally inconsistent; the correct check should compare against the literal string `"1"` or the logic should normalise truthy values; a non-expert cannot interpret this

**3. `--output-root` default path truncated in help**
- Command: `uv run --no-sync aeat app live filed capture --help`
- Expected: Full default path visible or a concise placeholder like `(default dir)`
- Actual: Default shown as `var\aeat\filed-declarati…` — truncated mid-word; no way to know the full path
- Severity: **minor** — cosmetic but reduces trust; user cannot know where captures are saved without running the command

**4. `capture-sources` exposes internal infrastructure options without guidance**
- Command: `uv run --no-sync aeat app live filed capture-sources --help`
- Expected: Either hidden infrastructure options or a brief explanation of when `--registry-root` / `--source-root` are needed
- Actual: Options appear with terse technical descriptions ("Raíz del registro", "Raíz del proyecto"); no indication whether they are needed for normal use or only for developers
- Severity: **minor** — non-expert users will not know if they need to supply these and may be blocked by uncertainty

**5. `--period` format not documented**
- Command: `uv run --no-sync aeat app live filed capture-sources --help`
- Expected: A hint or example of valid period values (e.g. `0A` for annual, `1T` for first quarter)
- Actual: `--period TEXT  Periodo de presentación [required]` — no format hint
- Severity: **minor** — a user who does not know the period code format cannot proceed; common codes should appear in the description or metavar
