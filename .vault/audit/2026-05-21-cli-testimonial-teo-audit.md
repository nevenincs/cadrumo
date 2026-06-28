---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-20-cli-persona-task-catalogue-reference]]"
---

# CLI testimonial - Teo, complementaria correction

## What I was trying to do

I am Teo, a freelance IT consultant (autónomo). Last quarter I filed my
Modelo 303 for Q1 2025, declaring €2,100 of output VAT and €630 of input
VAT — a net €1,470 to pay. After filing I found a forgotten invoice for
€420 net + 21% IVA (€88.20 extra output VAT). Spanish tax law says I
cannot simply refile the same period; I must submit a *declaración
complementaria* that adds only the extra amount on top of what I already
declared. I wanted the tool to help me: set up my profile, prepare the
original 303, "file" it internally, then produce the correction showing
the delta.

## My session

### Step 1 — find my way around

```
aeat --help
```

Expectation: overview of what the tool can do.
Output: clean two-root structure (`config` and `app`), showed the modelo
lifecycle section including `aeat app modelo work`. A `next step` hint
pointed straight to `aeat app modelo work create`. Felt welcoming.

### Step 2 — create my profile

```
aeat config profile create teo \
  --tax-id 12345678Z --name Teo --surnames "Martínez García" \
  --activity "Consultoría informática" --address-postcode 28001 \
  --taxation-type 1 --output-language es --iva-regime GENERAL --quiet
```

Expectation: profile created without interactive prompts.
Output:
```
profile	teo
status	created
next	aeat app modelo work create
```
Exit 0. Smooth. The `--quiet` flag worked and the `next` hint kept me
on track without needing to re-read the manual.

### Step 3 — explore the modelo work subcommands

```
aeat app modelo work --help
```

Output listed: `create`, `list`, `status`, `rename`, `discard`,
`calculate`, `revisions`, `history`, `verify`, `file`, `resume`,
**`amend`**. The description for `amend` read:
*"Construir una declaración complementaria sobre una declaración presentada
externamente."*

That is exactly what I need. Good sign.

### Step 4 — try amend --help directly

```
aeat app modelo work amend --help
```

Expected: parameter list for the amend command.
Actual:
```
Traceback (most recent call last):
  ...
ImportError: cannot import name 'DisenoCompletenessCasilla' from
'aeat.domain.calculations.registry._schema'
```
Exit 1. **Crash.** The CLI dies before rendering help. A real user hitting
this first would assume the feature is broken or the install is corrupted.
Very discouraging.

(Later in the session I discovered that once the CLI is further into its
startup path — past the lazy-import gate — `amend --help` works fine and
`amend` itself also works. The crash is a mid-refactor import symbol that
is missing, not a feature that is absent.)

### Step 5 — prepare my 303

```
aeat app modelo list
aeat app modelo describe 303
```

303 is present, revision `2009-y-siguientes`, periods `1T/2T/3T/4T`,
6 bindings. Good.

```
aeat app modelo work create \
  --modelo 303 --year 2025 --period 1T --revision 2009-y-siguientes
```

Output:
```
work_unit_id  fb42c658...
state         borrador
name          303-2025-1T
```
Exit 0.

### Step 6 — enter my figures and calculate

```
aeat app modelo bindings list --modelo 303 --year 2025 --period 1T
```

Showed 6 bindings; the main ones are `iva-repercutido-general-cuota`
and `iva-soportado-interiores-cuota`. I need to supply them manually
since I have no ledger import.

```
aeat app modelo work calculate fb42c658... \
  --binding "modelo-303-iva-repercutido-general-cuota=2100.00" \
  --binding "modelo-303-iva-soportado-interiores-cuota=630.00" \
  --by teo
```

Output: all casillas shown, `iva.resultado = 1470.00`. Correct. The
engine did the maths right.

### Step 7 — try to verify

```
aeat app modelo work verify 7a1f21e8... --by teo
```

Expected: state transitions to `VERIFICADO_COMPLETO`.
Actual:
```
Error: workflow gate aborted
reason='NO_PENDING_OBLIGATION': No pending filing obligation for this profile
```
Exit 2. Gate refuses because I have no pending obligation configured.
There is no CLI command to register or declare an obligation manually
without going through the live AEAT path or ledger import. I am stuck.

### Step 8 — try to file the draft directly

```
aeat app modelo work file 7a1f21e8... --by teo
```

Expected: internal filing record created.
Actual:
```
Error: calculation revision '7a1f21e8...' is in state 'borrador';
only VERIFICADO_COMPLETO revisions can be filed
```
Exit 2. Expected — the gate is coherent — but I cannot reach
`VERIFICADO_COMPLETO` without the obligation gate passing.

### Step 9 — investigate live filed path

```
aeat app live filed list
```

Output:
```
Refused. live AEAT reads require AEAT_LIVE_TESTS_ENABLED=1; current value: 'true'
```
Exit 2. Confusing error: the message says `current value: 'true'` but
still refuses. Either the env var check is comparing a string `'true'`
against an integer `1`, or the error message is wrong about what the
current value is.

### Step 10 — try capture-sources --help

```
aeat app live filed capture-sources --help
```

Expected: help for importing filed declarations.
Actual:
```
ImportError: cannot import name 'DerivedManifestCasilla' from
'aeat.domain.calculations.registry._record_design'
```
Exit 1. Second import crash, different missing symbol. Entire `live
filed capture-sources` command is unreachable.

### Step 11 — try amend with a fictional filing record ID

```
aeat app modelo work amend \
  --from-filing-record nonexistent \
  --kind complementaria \
  --reason "forgot invoice" \
  --set "iva.repercutido.general=2520.00" \
  --by teo
```

Expected: either work or give a clear "no such record" error.
Actual:
```
Error: "no filing record with id='nonexistent'"
```
Exit 2. Correct error — the validation is there. But there is no way
to *create* a filing record in the local-only path without passing
verify and file first, which requires the obligation gate.

### Step 12 — review the history and revisions

```
aeat app modelo work revisions --work-unit-id fb42c658...
aeat app modelo work history fb42c658...
```

Both worked. One `borrador` revision visible. History shows one event
(`modelo.calculation.created`). No `filed` or `complementaria` events
possible without crossing the gates.

## Did it work?

**No.** The complementaria workflow is architecturally present and the
`amend` command exists with the right parameters (`--kind complementaria`,
`--from-filing-record`, `--set CASILLA=VALUE`). However, Teo cannot
reach it through the local-only CLI path:

1. `verify` is gated on `NO_PENDING_OBLIGATION` — there is no way to
   satisfy this gate without a live AEAT connection or ledger data.
2. `file` requires `VERIFICADO_COMPLETO` — unreachable without verify.
3. `amend` requires a filing record — unreachable without file.
4. The `live filed capture-sources` command that would import official
   AEAT evidence crashes on import.

The full path is: `calculate → verify → file → amend`. Only the first
step is reachable in the local-only path.

## Bugs and gaps

**1. Import crash: `aeat app modelo work amend --help`**
- Command: `aeat app modelo work amend --help`
- Expected: parameter help rendered.
- Actual: `ImportError: cannot import name 'DisenoCompletenessCasilla'
  from 'aeat.domain.calculations.registry._schema'` — exit 1.
- Severity: **blocker** (the complementaria feature appears completely
  broken to a user who tries help first; discoverability of the feature
  is destroyed).

**2. Import crash: `aeat app live filed capture-sources --help`**
- Command: `aeat app live filed capture-sources --help`
- Expected: parameter help rendered.
- Actual: `ImportError: cannot import name 'DerivedManifestCasilla'
  from 'aeat.domain.calculations.registry._record_design'` — exit 1.
- Severity: **blocker** (the import path needed to bring AEAT evidence
  into the local workflow is fully unreachable).

**3. `live filed list` gives misleading env-var error**
- Command: `aeat app live filed list`
- Expected: either list or a clear "requires AEAT_LIVE_TESTS_ENABLED=1"
  refusal.
- Actual: `Refused. live AEAT reads require AEAT_LIVE_TESTS_ENABLED=1;
  current value: 'true'`. The guard says `current value: 'true'` but
  still refuses — either the comparison is wrong (`'true' != 1`) or the
  diagnostic is reporting the wrong current value.
- Severity: **major** (confusing diagnostic; operator cannot tell if the
  gate is a string/int mismatch or whether AEAT_LIVE_TESTS_ENABLED=true
  is simply not accepted).

**4. No local path through `verify` without obligation data**
- Command: `aeat app modelo work verify <rev_id>`
- Expected: verify succeeds for a locally-calculated draft.
- Actual: `NO_PENDING_OBLIGATION` gate aborts. No CLI command exists to
  register an obligation or bypass the gate for local-only testing.
- Severity: **major** (the entire modelo lifecycle — calculate → verify →
  file → amend — is blocked at the second step for any user who does not
  have live AEAT obligations wired up; effectively no one can rehearse the
  complementaria path offline).

**5. `amend --help` works only after CLI is past the lazy import**
- Note: once the import crash (bug 1) is fixed, `amend --help` works and
  the command itself correctly validates its arguments. The feature is
  structurally present but gated behind unreachable prerequisites. This
  is not a separate bug — it is a consequence of bug 1 — but worth
  noting that the underlying amend logic appears sound.
- Severity: **cosmetic** (observation only; resolved by fixing bug 1).

**6. No `--dry-run` or `--simulate-obligation` flag on `verify`**
- Command: `aeat app modelo work verify --help`
- Expected: a way to bypass or simulate the obligation gate for local
  testing / rehearsal.
- Actual: no such option exists. The only path is live AEAT.
- Severity: **minor** (UX gap; a non-expert user who wants to rehearse
  the complementaria workflow before the filing deadline has no local
  path).
