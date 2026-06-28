---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# CLI testimonial - Elena, corporate IVA/IS preparer

## What I was trying to do

I run Soluciones Elena S.L., a small management-consulting limited company (sociedad limitada) based in Madrid. We are registered for IVA régimen general. I wanted to use this tool to:

1. Create a company profile (not a personal/natural-person profile).
2. List all available modelos and see whether Modelo 303 (IVA quarterly) and Modelo 200 (Impuesto sobre Sociedades annual) are present.
3. Inspect the registry to understand how confident I can be in the underlying data.
4. Run the Modelo 303 workflow end-to-end for Q1 2025 and get a draft result.
5. Check whether Modelo 200 is actually calculable, not just listed.
6. Judge whether this tool is genuinely useful for a company tax preparer.

## My session

### Step 1 — Explore the CLI surface

Command: `aeat --help`

Expected: See a top-level menu and understand whether the tool has company-specific concepts.

Output:
```
aeat - local-first Spanish tax workflow

Section setup
  aeat config profile create NAME  Setup create profile
  ...
Section modelo lifecycle
  aeat app modelo list
  aeat app modelo work
  ...
Section diagnostics
  aeat app registry inspect
```

How it felt: Clean, well-organised top-level help. Two roots (`config` and `app`) keeps things unambiguous. No mention of "company" vs "individual" at this level — I needed to dig.

---

### Step 2 — Understand profile creation: does it support a company?

Command: `aeat config profile create --help`

Expected: A flag to designate the profile as a legal entity (CIF vs NIF) or at minimum a `--surnames` / `--razón-social` distinction.

Real output (key flags):
```
--tax-id TEXT      Identificador fiscal (NIF/NIE)
--name TEXT        Nombre visible
--surnames TEXT    Apellidos o razón social para cabeceras de exportación
--iva-regime [GENERAL|SIMPLIFICADO|RECARGO_EQUIVALENCIA|EXENTO]
--taxpayer-sex [H|M]
--taxpayer-marital-status [1|2|3|4]
...spouse-* flags...
--renta-family flags
```

How it felt: There is no explicit "entity type" flag distinguishing a natural person from a legal entity. The `--surnames` field description mentions "razón social" as an aside, and `--tax-id` accepts CIF. But the profile schema still carries `--taxpayer-sex`, `--taxpayer-marital-status`, `--taxpayer-birth-date`, and a full suite of `--spouse-*` and `--renta-family-*` flags. For a company, all of these are noise — and they pollute the wizard with questions irrelevant to any sociedad. There is no entity-type discriminator; the tool treats a company as a person with the personal fields simply left blank.

---

### Step 3 — Create the company profile

Attempt 1 command (abbreviated): `aeat config profile create elena-sl --tax-id B12345678 ... --no-iva-roi-enrollment ...`

Error:
```
No such option: --no-iva-roi-enrollment
(Possible options: --iva-roi-enrolled, --no-iva-oss-enrolled, --no-iva-roi-enrolled)
```

This triggered a chain of seven sequential correction attempts. Each attempt revealed one incorrect flag name. The `--help` output names are longer than the actual accepted names in several cases (e.g., `--iva-roi-enrollment` shown in help description text but `--iva-roi-enrolled` is the real flag; `--tax-residence-region` shown in the enum table header area but actual flag is `--tax-residence-ccaa`).

After six corrections:

Attempt 7 command: `aeat config profile create elena-sl --tax-id B12345674 ...` (CIF corrected to pass check-digit validation)

Intermediate error on attempt 7:
```
Refused. NIF/NIE/CIF no válido: B12345678.
CIF check digit mismatch (digit-only kind 'B'): expected '4', got '8'.
```

This is actually good behaviour — the tool validates CIF check digits. I computed the correct check digit and retried with `B12345674`.

Final attempt succeeded silently (no output, exit 0). Profile confirmed via `aeat config profile show elena-sl`:
```
readiness    ready    issues=0
identity.tax_id    B12345674
iva.regime    GENERAL
...
```

How it felt: CIF validation is genuinely useful. The flag discovery UX is poor — I had to retry seven times because `--help` output does not match actual flag names consistently, and there is no `--help`-driven completion to guide me. A company user trying to script profile creation would be stuck for a long time.

---

### Step 4 — List available modelos

Command: `aeat app modelo list`

Output (excerpt):
```
code  title                                      cadence    domain  revisions
200   IS autoliquidacion anual                   annual     is      1
202   IS pago fraccionado                        quarterly  is      3
303   IVA. Autoliquidacion (trimestral)          quarterly  iva     1
390   IVA. Declaracion-resumen anual             annual     iva     1
```

How it felt: Both 303 and 200 are present. The `domain` column (`iva`, `is`) immediately tells a company preparer which modelos are relevant. The `cadence` column correctly flags 303 as quarterly and 200 as annual. Very readable for a non-developer. This command worked perfectly.

---

### Step 5 — Inspect the registry

Command: `aeat app registry inspect`

Output:
```
Nº modelos=26
Nº revisiones=41
Nº referencias legales=201
Nº referencias de origen=137
Nº casillas=14971
Nº fórmulas=1052
Nº perfiles de extracción=26
Nº referencias cruzadas=68
Nº expectativas de verificación=38
Nº enlaces de aplicación=376
Superficies de enlace de aplicación=approval,calculation,deadline,export,...
Modelos=036,100,...,200,...,303,...
```

How it felt: Numbers feel like internal audit metrics, not user-oriented confidence signals. I cannot tell from "14971 casillas" whether my 303 is correctly covered or whether there are known gaps. A user-facing health signal (e.g. "Modelo 303: all casillas covered, verification expectations met") would give me genuine confidence. As it stands, `registry inspect` is a developer dashboard, not a preparer confidence report.

---

### Step 6 — Check Modelo 303 bindings

Command: `aeat app modelo bindings list --modelo 303 --year 2025 --period Q1`

Output:
```
binding_count    6
modelo    revision    period    binding_id                                     source
303    2009-y-siguientes    1T    modelo-303-iva-repercutido-general-cuota      ledger_iva_aggregation
303    2009-y-siguientes    1T    modelo-303-iva-repercutido-reducido-cuota     ledger_iva_aggregation
303    2009-y-siguientes    1T    modelo-303-iva-repercutido-super-reducido-cuota  ledger_iva_aggregation
303    2009-y-siguientes    1T    modelo-303-iva-soportado-interiores-cuota     ledger_iva_aggregation
303    2009-y-siguientes    1T    modelo-303-iva-autorepercutido-intracomunitaria-cuota  ledger_iva_aggregation
303    2009-y-siguientes    1T    modelo-303-compensacion-pendiente-anteriores  previous_filing
```

How it felt: The binding IDs are human-readable (repercutido-general, soportado-interiores). The table tells me exactly what inputs I need to provide manually via `--binding`. The `borrador_capable: False` column on all rows is unexplained — no help text says what it means. Also: the `period` column shows `1T` but I supplied `Q1` — the command accepted `Q1` for filtering but the actual stored period token is `1T`. This mismatch caused a blocker in the next step.

---

### Step 7 — Create Modelo 303 work unit (first attempt: Q1 fails)

Command: `aeat app modelo work create --modelo 303 --year 2025 --period Q1 --revision 2009-y-siguientes`

Result: Success (work unit created, state `borrador`).

Then: `aeat app modelo work calculate <work_unit_id> --binding ...`

Error:
```
Invalid value: registry snapshot for modelo='303' year=2025 period='Q1'
could not be resolved: modelo 303: no revision for year=2025 period='Q1' revision=None
```

How it felt: The system let me create a work unit with period `Q1` but then refused to calculate because the registry uses `1T`. The work unit creation should either normalise the period token or reject `Q1` with an error at creation time. Instead it silently accepted the wrong token and failed only at calculate time — this is a silent-corruption trap.

---

### Step 8 — Create Modelo 303 work unit (second attempt: 1T succeeds)

Command: `aeat app modelo work create --modelo 303 --year 2025 --period 1T --revision 2009-y-siguientes --name "303 1T 2025 - Soluciones Elena SL"`

Output:
```
work_unit_id    fb42c6584330a1da561454f00465f9eef256357ce081609f2acd8b03c38638fc
state    borrador
```

---

### Step 9 — Calculate Modelo 303 draft

Command: `aeat app modelo work calculate <work_unit_id> --binding modelo-303-iva-repercutido-general-cuota=4200.00 --binding modelo-303-iva-repercutido-reducido-cuota=315.00 --binding modelo-303-iva-repercutido-super-reducido-cuota=0.00 --binding modelo-303-iva-soportado-interiores-cuota=1890.00 --binding modelo-303-iva-autorepercutido-intracomunitaria-cuota=0.00 --by elena`

Output:
```
casilla    iva.cuota-devengada-total      4515.00
casilla    iva.cuota-deducible-total      1890.00
casilla    iva.resultado                  2625.00
casilla    iva.resultado-regimen-general  2625.00
casilla    iva.repercutido.general        4200.00
casilla    iva.repercutido.reducido        315.00
casilla    iva.soportado.interiores       1890.00
...
```

How it felt: The arithmetic is correct (4200+315 = 4515 devengado; 4515-1890 = 2625 resultado). The casilla names are semantic (`iva.resultado` rather than just `47` or `[71]`), which is far more useful than raw box numbers. I can see exactly what went into the calculation. This is the strongest part of the tool.

---

### Step 10 — Attempt to verify the 303 draft

Command: `aeat app modelo work verify <calc_revision_id> --by elena`

Error:
```
Invalid value: workflow gate aborted run_id='d9478b2f75dfe48e'
final_stage='ABORTED' reason='NO_PENDING_OBLIGATION':
No pending filing obligation for this profile
```

How it felt: The verify step requires a pre-existing filing obligation linked to the profile, which was never explained anywhere in the workflow documentation or `--help` text. There is no `aeat app obligation` command or any onboarding step that tells me how to register quarterly obligations. The workflow appears to expect integration with a census/obligation system that is either undocumented or not yet exposed in the CLI. For a first-time user, the workflow terminates here with no actionable next step.

---

### Step 11 — Commands crash after a session

After the verify attempt, all subsequent `aeat app` commands that import the full CLI entry-point began crashing with:

```
ModuleNotFoundError: No module named 'aeat.application.workflow._bucket_pointer_io'
```

or alternatively:

```
ModuleNotFoundError: No module named 'aeat.core.resources._registry'
```

Affected commands: `aeat app modelo work list`, `aeat app modelo work status`, `aeat app modelo work revisions`, `aeat app overview status`, `aeat config repair`, `aeat app review queue`.

Commands that continued working: `aeat config profile show`, `aeat app modelo list`, `aeat app modelo work create`, `aeat app modelo work calculate`, `aeat app modelo bindings list`, `aeat app registry inspect`.

How it felt: A complete session blocker. The working tree carries incomplete WIP that breaks the module import graph. This is a development-branch issue but a user running the tool from this branch encounters it immediately after the first calculate call.

---

### Step 12 — Modelo 200 availability check

Commands: `aeat app modelo bindings list --modelo 200 --year 2025 --period 0A` and `aeat app modelo work create --modelo 200 --year 2025 --period 0A --revision 2024-y-siguientes`

Bindings output:
```
binding_count    1
binding_id    modelo-200-2024-pagos-fraccionados-anuales    source: previous_filing
```

Calculate output: `La relación modelo-200-2024-rel-202-pagos-fraccionados no tiene valor asignado.` (relation required)

After supplying `--relation modelo-200-2024-rel-202-pagos-fraccionados=0.00`, calculation succeeded and produced 500+ casilla rows (raw IS form casillas 00001–00799, all zeroed out).

How it felt: Modelo 200 is present in the registry and produces a calculation. However, it requires a relation value (Modelo 202 pagos fraccionados) whose format is undiscoverable without reading the error message. The output is 500+ numeric casilla IDs with no semantic names — contrast with 303 which uses readable names like `iva.resultado`. This suggests 200 has minimal semantic enrichment. A company preparer would need those labels to cross-check against the paper form.

---

## Did it work?

Partial. The core IVA calculation path for Modelo 303 works and produces correct arithmetic with readable casilla semantics. Modelo 200 is present and calculable in a minimal sense. However, the workflow terminates before verification because the obligation-registration step is missing from the user-visible surface. The tool cannot be called "end-to-end functional" for either modelo until the verify/file path is reachable. The entity-type gap (no company vs individual discriminator in profiles) is also a meaningful gap for a corporate user.

## Bugs and gaps

1. **Flag names in `--help` do not match accepted flag names on `profile create`**
   - Command: `aeat config profile create --no-iva-roi-enrollment`
   - Expected: flag accepted as shown in help
   - Actual: `No such option: --no-iva-roi-enrollment. Possible options: --no-iva-roi-enrolled`; same pattern across six flags (`--tax-residence-region` vs `--tax-residence-ccaa`, `--iva-roi-enrollment` vs `--iva-roi-enrolled`, `--pays-professional-fees-with-retention` vs `--pays-professionals-with-retencion`, `--no-uses-objective-estimation` vs `--no-uses-objective-estimation-irpf`, `--no-third-party-transactions` vs `--no-third-party-transactions-above-347-threshold`, `--no-bienes-extranjero` vs `--no-bienes-extranjero-above-threshold`)
   - Severity: **major** — forces 6-attempt trial-and-error loop; completely blocks scripted profile creation

2. **`work create` silently accepts invalid period token `Q1`; calculate fails later**
   - Command: `aeat app modelo work create --modelo 303 --period Q1`
   - Expected: error at create time, or normalisation to `1T`
   - Actual: work unit created successfully in `borrador` state; `work calculate` then fails with `no revision for year=2025 period='Q1'`
   - Severity: **major** — silent corruption; user cannot diagnose without reading registry bindings output carefully

3. **`work verify` aborts with `NO_PENDING_OBLIGATION`; no path to create one**
   - Command: `aeat app modelo work verify <calc_id>`
   - Expected: verification of the draft against the registry contract
   - Actual: `workflow gate aborted reason='NO_PENDING_OBLIGATION': No pending filing obligation for this profile`; no command exists in the CLI to register an obligation; no help text explains the prerequisite
   - Severity: **blocker** — the verify step of the documented workflow is unreachable from a clean profile

4. **`ModuleNotFoundError: No module named 'aeat.application.workflow._bucket_pointer_io'` crashes most commands**
   - Command: `aeat app modelo work list`, `status`, `revisions`; `aeat app overview status`; `aeat config repair`
   - Expected: commands execute
   - Actual: Python traceback on import; module missing from working tree
   - Severity: **blocker** (branch WIP state) — half the `app` surface is unreachable

5. **No company vs natural-person discriminator in profile schema**
   - Command: `aeat config profile create --help`
   - Expected: `--entity-type [person|company]` or equivalent; company profiles should not expose `--taxpayer-sex`, `--taxpayer-marital-status`, `--spouse-*`, `--renta-family-*`
   - Actual: all personal-tax fields shown alongside company IVA fields; a CIF holder must scroll past irrelevant personal fields
   - Severity: **major** — UX confusion for company users; potential for users to fill in irrelevant fields

6. **Modelo 200 casilla output uses raw numeric IDs, not semantic names**
   - Command: `aeat app modelo work calculate <200_work_id>`
   - Expected: named casillas comparable to 303 (`is.base-imponible-general`, etc.)
   - Actual: 500+ rows of `casilla  00001  0`, `casilla  00002  0`, ... with no labels
   - Severity: **minor** — functional but unusable for a preparer cross-checking against the paper form

7. **`registry inspect` output is developer-internal metrics; no per-modelo health signal**
   - Command: `aeat app registry inspect`
   - Expected: per-modelo summary (casilla coverage, verification status, last update date)
   - Actual: aggregate counts only (`Nº casillas=14971`, `Nº fórmulas=1052`)
   - Severity: **minor** — useful for developers; not actionable for a tax preparer judging reliability
