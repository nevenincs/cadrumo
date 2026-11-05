# Canonical test personas

This directory is the single catalogue of synthetic Spanish taxpayers that tests,
acceptance journeys, documentation sequences and generated window fixtures seed
from. It holds data only: TOML, CSV and this file. The reader and materialiser
that turn a persona into a profile live elsewhere and implement the contract
below. A persona reaches a profile only through production operations; nothing
here is written into storage directly.

```
dev/fixtures/personas/
  identities.toml                 every tax identifier, one per role
  <persona-id>/
    persona.toml                  profile facts, household, activity, elections
    ledger.csv                    the persona's bank and invoice rows
    documents.toml                documents attached to rows: specimens, or invoices generated from their rows
    expectations.toml             hand-grounded obligations, deadlines and values
```

## Personas

| id | taxpayer | scenario | modelos |
| --- | --- | --- | --- |
| `autonomo-fontanero` | `fontanero.titular` (primary identity) | Plumber, estimación directa simplificada, IVA 21 % and 10 % (dwelling repairs), rents a workshop with 19 % retención | 303, 390, 130, 115, 180, 347, 100 |
| `autonomo-alta-reciente` | `alta.titular` | Office-cleaning business registered on 1 January of the horizon year, estimación directa simplificada by cobros y pagos, IVA 21 %, no retención on its income; the first quarter only | 303, 130, 390, 347, 100 |
| `traductora-profesional` | `traductora.titular` | Translator whose income is over 70 % withheld (no 130), pays a natural-person tax adviser with 15 % retención | 303, 390, 111, 190, 100 |
| `intracomunitario-desarrollador` | `intracom.titular` (NIE) | Software professional with EU B2B clients, an Irish cloud supplier (reverse charge), ROI enrolled | 303, 349, 390, 130, 100 |
| `minorista-recargo` | `minorista.titular` | Clothing retailer in recargo de equivalencia (no 303/390) | 130, 347, 100 |
| `asalariada-familia` | `asalariada.titular` | Employee, married, individual return, two children (one under three in an escuela infantil), mother at home | 100 |
| `arrendador-jubilado` | `arrendador.titular` | Widowed pensioner letting a dwelling (IVA-exempt, art. 23.2 reduction) | 100 |
| `sociedad-limitada` | `sociedad.titular` | S.L. developing web platforms, quarterly IVA, Impuesto sobre Sociedades | 303, 390, 347, 200, 202 |

Every persona's main fiscal year is `horizon-1` and its clock is the 16th of
February of `horizon`: the January filings of the year are due and past, the
Modelo 347 window is open, and the Renta campaign has not begun.

`autonomo-alta-reciente` is the exception: its activity begins in `horizon`,
so its fiscal year is `horizon` and its clock is the 1st of April of
`horizon`, when the first quarter has closed and its filing window is open.
Windows that close after `horizon` lie outside the envelope and are not stated
as deadlines.

## Common rules

- **No year literals.** Every year is a token (see below). Paths of referenced
  documents carry no filing year.
- **No identifiers outside `identities.toml`.** Persona files name identity
  roles; the reader resolves values.
- **Synthetic data only.** Names are invented; amounts are scenario figures.
- **`format = 1`** heads every TOML file. A reader refuses an unknown format.
- **Amounts** are strings in canonical decimal grammar: dot separator, no
  thousands separator, two decimals for euros (`"1234.50"`). Rates in the
  ledger are fractions (`0.21`).

## Year tokens and dates

A year token is a string: `horizon`, `floor`, or either followed by `+N` or
`-N` (`horizon-1`, `floor+2`). `horizon` and `floor` are the bounds of the
supported filing-year envelope that the registry declares; the reader resolves
them through the supported-years catalogue (`supported_filing_years()`) and
never from a literal. A resolved year outside `floor..horizon` is a refusal
unless the field is a biographical date (birth, marriage, contract start,
activity start), which may lie before the floor.

A date is an inline table `{ year = <token>, month = <1..12>, day = <1..31 | "last"> }`.
`day = "last"` means the last day of that month in the resolved year. The
reader converts it to ISO-8601 before handing it to an operation.

The scenario clock `[clock].as_of` is such a date. Tests that depend on "today"
take it from here; one persona has one clock.

## identities.toml

`[convention]` states the rule; it is the declared synthetic-identifier
convention that an identity gate can verify by pattern and checksum without a
value allowlist. "Synthetic" is a repository convention, not an authority
guarantee: no official reserved NIF/NIE/CIF range exists.

| kind | pattern |
| --- | --- |
| `nif` | `12345678Z` (the single primary taxpayer identity), otherwise an eight-digit zero counter `00000000T`, `00000001R`, ... with the NIF control letter |
| `nie` | `Y0000000Z`, `Z0000000M` (counter zero) and `X0000001R` (counter one, because `X0000000T` is the registry's development mock developer identity) |
| `cif` | letter + seven-digit counter from `0000001` + control: digit for A, B, E, H; letter for P, Q, R, S, N, W; C, D, F, G, J, U, V take either and this catalogue uses the digit (`B00000018`, `H00000018`, `Q0000001H`) |
| `vat_eu` | member-state prefix + zeros + counter digit, shaped to that state's structure (`DE000000001`, `FR00000000001`, `IE0000001A`); never validated against VIES |

`[[identities]]` fields:

| field | type | meaning |
| --- | --- | --- |
| `role` | string | `<persona-prefix>.<role>`; unique |
| `persona` | string | owning persona id |
| `kind` | `nif` \| `nie` \| `cif` \| `vat_eu` | identifier family |
| `value` | string | the identifier; unique across the file |
| `name`, `surnames` | string | natural persons |
| `legal_name` | string | entities |
| `country` | string | `vat_eu` only, ISO 3166-1 alpha-2 |
| `primary` | bool | only on `fontanero.titular` |

Each value is bound to exactly one role and each role to one value. A new value
takes the next free counter of its family. Real identifiers (published
companies, reserved live-probe values) and random-looking checksum-valid values
are never added.

`[[refusals]]` lists checksum-invalid values (`B00000001`, `B12345678`,
`12345678A`) with the mismatch they exhibit. They are never a role and never
appear in a persona; identifier-refusal tests take them from here.

## persona.toml

| table / key | type | meaning |
| --- | --- | --- |
| `[persona].id` | string | equals the directory name |
| `[persona].title`, `summary` | string | Spanish prose for humans |
| `[persona].taxpayer` | identity role | the profile's own identity |
| `[persona].fiscal_year` | year token | the year the ledger and expectations describe |
| `[persona].modelos` | string array | modelos the scenario exercises (applicable or deliberately refused) |
| `[clock].as_of` | date | the scenario instant |
| `[profile]` | table | wizard question id → answer |
| `[fields]` | table | profile schema path → value, for facts no wizard question asks |
| `[[activities]]` | array | censo activity rows: `description`, `iae_epigraph` |
| `[[elections]]` | array | dated elections: `question` (wizard id), `value`, `year` (token) |
| `[[household.descendants]]` | array | one descendant row |
| `[[household.ascendants]]` | array | one ascendant row |
| `[[withholding_certificates]]` | array | retenciones soportadas declared by a payer |
| `[[rental_properties]]` | array | declarative facts for a let dwelling |
| `[[officers]]` | array | company officers (`identity`, `role`, `remunerated`) |

### `[profile]` answers

Keys are wizard question ids (the kebab-case ids of the profile wizard flow,
such as `tax-residence-ccaa`), never schema paths. The materialiser submits them
through the profile patch operation, one `ProfilePatchValue(question_id, value)`
each, in file order. An unknown id is refused by that operation. Value forms:

| TOML value | submitted string |
| --- | --- |
| string | as written (`"GENERAL"`, `"1"`, `"28045"`) |
| bool | `"true"` / `"false"` |
| string array (checkbox questions) | members joined with `,` |
| date table | ISO-8601 date |
| `{ identity = "<role>" }` | the role's `value` |
| `{ identity = "<role>", field = "name" \| "surnames" \| "legal_name" }` | that field of the role |

A question whose subject does not apply to the persona (IVA questions for a
non-entrepreneur, `iva-m303-regime-composition` for a recargo de equivalencia
retailer) is omitted rather than answered with a false fact, even when the flow
marks it required; the materialiser reports any refusal that follows.

### `[fields]`

Schema path → string value, submitted through the profile field mutation for
facts the wizard does not ask (`irpf.activity_kind`). The path must exist in the
profile schema.

### Activities and elections

`[[activities]]` rows go through the repeatable-row mutation of the
`activities` section; keys are that section's field keys. `[[elections]]` submit
the question and its dated year companion (for
`irpf-activity-income-imputation-criterion`, the year goes to
`irpf-activity-income-imputation-year`).

### Household rows

Descendant keys are the canonical descendant leaves: `birth_date`, `relacion`,
`inscripcion_registro_civil`, `acogimiento_resolucion`, `fallecimiento`,
`discapacidad`, `convivencia`, `dependencia_economica`, `custodia_compartida`,
`rentas_anuales`, `declaracion_propia`, `prorrata_minimo`,
`meses_madre_trabajo`, `alta_posterior_nacimiento_mes`,
`segundo_ciclo_infantil_inicio_mes`, `gastos_guarderia`,
`gastos_guarderia_mensuales`. `identity` supplies the `nif` leaf. Ascendant keys
are `birth_date`, `fallecimiento`, `convivientes`, with `identity` for `nif`.
Values are written in the leaf's canonical string form (dates as date tables),
because the descendant and ascendant operations refuse a row whose canonical
re-projection differs from what was supplied: omit a leaf whose value is its
default (`custodia_compartida = false`, ordinary `relacion`).

### Withholding certificates

| key | meaning |
| --- | --- |
| `payer` | identity role of the payer |
| `ejercicio` | year token |
| `income_class` | the suffered-withholding income class token (`trabajo`, `actividad_economica`, `capital_mobiliario`, ...) of the retención-soportada record operation; pensions are `trabajo` |
| `origin` | `payer_certificate` (the certificate's bytes back the record, so the persona must reference a certificate document) or `operator_declaration` (the taxpayer transcribes the figures; what the catalogue uses) |
| `importe_integro`, `retencion` | amounts |
| `cotizaciones_seguridad_social` | optional; employee contributions shown on the certificate. No operation records them, so the materialiser reports them as not materialised |

### Declarative blocks without an operation

`[[rental_properties]]` and `[[officers]]` record scenario facts that
expectations rely on but for which no production operation was located. The
reader parses them, the materialiser reports them as not materialised, and no
test may write them by another route.

## ledger.csv

UTF-8, comma-separated, header row, one row per bank movement. The columns are
a superset of what the bank-statement import accepts; the materialiser imports
the statement columns, then classifies, records invoices and links through the
ledger operations.
Classification takes no recargo, so a row with a `recargo_amount` is classified
without its cuota and recargo and reported as not materialised.

| column | meaning |
| --- | --- |
| `ref` | stable row id; becomes the statement reference (`Referencia`) |
| `year`, `month`, `day` | operation date; `year` is a year token |
| `description` | statement concept |
| `amount` | signed bank amount in EUR: positive incoming, negative outgoing |
| `currency` | `EUR` |
| `counterparty` | identity role, or empty for a movement no invoice backs (a public charge, a card-terminal settlement of retail sales); every invoice row names one, consumers included |
| `classification` | `BUSINESS` or `PERSONAL` |
| `category_id` | expense category id for business expenses |
| `irpf_category` | IRPF category where it differs from the default |
| `iva_category` | canonical IVA category (`domestic_general`, `domestic_reduced`, `intra_community_service_supply`, `intra_community_service_acquisition_reverse_charge`, `recargo_equivalencia`, ...) |
| `taxable_base` | invoice base; for a cost without IVA, the cost |
| `iva_rate` | fraction |
| `iva_amount` | IVA charged or self-assessed |
| `recargo_amount` | recargo de equivalencia charged |
| `deduction_kind` | deduction family of deductible IVA: `domestic_current` for domestic current purchases, `intra_eu_current` for a self-assessed intra-community acquisition |
| `invoice_kind` | `issued` or `received` when an invoice backs the row |
| `invoice_number` | invoice number |
| `retencion_rate`, `retencion_amount` | IRPF retención on the invoice |
| `document` | id of a `documents.toml` entry |

Invariant, checked by the reader for every row with a `taxable_base`:
`|amount| = taxable_base + iva_amount + recargo_amount - retencion_amount`,
except that `iva_amount` is left out for reverse-charge categories, where the
recipient self-assesses and pays only the base. Net payroll and pension rows
carry no base; the gross figures come from `[[withholding_certificates]]`.

A business cost that is no IVA operation at all carries `operacion_no_sujeta`
with `iva_rate` and `iva_amount` 0 and the cost as its base. The fontanero's
RETA contributions (`FON-RETA-*`) are the instance: a Seguridad Social
contribution is not subject to IVA (LIVA art. 7.8.º) and is deductible only
for IRPF.

## documents.toml

| key | meaning |
| --- | --- |
| `id` | referenced from `ledger.csv` `document` |
| `path` | repository path of an existing specimen; files are referenced, never copied |
| `generator` | instead of `path`: `facturae` renders the document from its single `attach_to` row and the identity catalogue (`cadrumo.tests.persona_invoices`), so its number, date, parties, base, rate, cuota and retención are the row's; the row's `document` column names it |
| `media_type` | MIME type |
| `attach_to` | ledger refs |
| `relation` | `specimen`: the document exercises the evidence path but its printed facts are not the row's facts and must not be confirmed into it; `source`: the document is the row's source and its facts match |

A persona without documents writes `documents = []`.

## expectations.toml

Expectations are written by hand from the ledger and the law, with the
derivation shown. They are never recorded from an application run. A test that
disagrees with an expectation has found either an application defect or an
expectation defect; it is resolved by re-deriving, not by copying output.

`[[obligations]]`: `modelo`, `periods` (`1T`..`4T`, `1P`..`3P`, `0A`), `year`
(token), `applicable` (bool, or `"unknown"` when the scenario cannot decide),
`reason`, `legal_ref`, `grounding`.

`[[deadlines]]`: `modelo`, `period`, `year`, `statutory_end` (date), optional
`note`. `statutory_end` is the last day the provision gives, before any shift.
The registry-derived window end must equal it or be the next business day after
it.

`[[values]]`: `modelo`, `period`, `year`, optional `counterparty` (identity
role), `casillas` (registry casilla id → amount or count string), `concepts`
(named quantity → string, for figures that are not a registry casilla id or
whose casilla is not re-derived here), optional `parameters` (statutory rates
and caps the derivation used, so a reader can detect a year whose parameter
differs), `derivation`, `legal_ref`, `grounding`, and `reason` when grounding
is `unverified`.

`legal_ref` entries are legal-source keys of the registry legal catalogue
(`ley-35-2006:art-58`, `rd-1065-2007:art-33.2.i`); each must exist there.

`grounding`:

| value | meaning |
| --- | --- |
| `verified` | the provision text was read in the bundled corpus and supports the figure or obligation |
| `cited` | the provision is named; its text was not re-read for this expectation, or the conclusion rests on administrative practice the text does not spell out |
| `unverified` | a `reason` says what is missing; tests treat the expectation as a known gap, not as an assertion |

Cuotas íntegras, autonomic scales, the Modelo 130 minoración and the Modelo 200
result are not asserted anywhere: they need inputs the scenarios do not fix.

## Existing inline personas and their catalogue replacement

| inline persona | replaced by |
| --- | --- |
| `dev/docs/sequences/sandbox.py` sandbox profile (12345678Z, general IVA) and `docs/_sequences/seeds/*.seq` | `autonomo-fontanero`; `intracomunitario-*.seq` → `intracomunitario-desarrollador`; `renta-*.seq` → `asalariada-familia` |
| `src/cadrumo/application/modelo/tests/profile_fixture_values.py` `MODELO_READY_PROFILE_FACTS` | `autonomo-fontanero` profile |
| `src/cadrumo/domain/user_profile/tests/general_regime_facts.py` `GENERAL_REGIME_NATURAL_PERSON_FACTS` | `autonomo-fontanero` profile |
| same module, `RENTA_UNMARRIED_TAXPAYER_FACTS` | `traductora-profesional` or `minorista-recargo` (unmarried natural persons) |
| `native/desktop/frontend/src/dev/fixtures/userProfile.json`, `household.json` | `asalariada-familia` |
| `native/desktop/frontend/scripts/modelo_fixtures.py` seeded profiles and `RENTA_FILERS` | `autonomo-fontanero` (303/130), `asalariada-familia` and `arrendador-jubilado` (Renta filers) |
| `native/desktop/frontend/src/dev/fixtures/ledger.ts` studio ledger | `autonomo-fontanero` ledger |
| `src/cadrumo/entrypoints/tests/profile_persistence/renta_persona_support.py` Renta persona seeder | `asalariada-familia`, `arrendador-jubilado` |
| `dev/acceptance/income_tax` | `autonomo-fontanero`, `traductora-profesional`, `asalariada-familia` |
| `dev/acceptance/retenciones` | `traductora-profesional` (soportadas and practicadas) |
| `dev/acceptance/export_parity` | `autonomo-fontanero`, `sociedad-limitada` |
| `dev/acceptance/iva` | `autonomo-fontanero`, `intracomunitario-desarrollador`, `minorista-recargo` |
| `dev/acceptance/ledger` (uses a real company identifier as counterparty) | `autonomo-fontanero` counterparties |

A migration keeps the consumer's assertion and replaces only its private
taxpayer, identifiers and ledger with the catalogue's.
