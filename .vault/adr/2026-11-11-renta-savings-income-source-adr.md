---
tags:
  - '#adr'
  - '#renta-savings-income-source'
date: '2026-11-11'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:2950b04ea5c60e45510eb8b2c06d8e4d57ba4562a9bce269cd512e2a64aff932'
related:
  - "[[2026-11-01-export-parity-suffered-withholding-schemas-adr]]"
  - "[[2026-11-08-prior-carry-attestation-adr]]"
  - "[[2026-08-14-registry-temporal-coverage-adr]]"
  - '[[2026-11-12-renta-savings-income-source-reference]]'
---
# `renta-savings-income-source` adr: `savings income source for Modelo 100 capital mobiliario rows` | (**status:** `accepted`)

Accepted 2026-11-11 22:50 by CADRUMO-PRIME with three corrections, written into Implementation: per-payer reconciliation, the governed-rate split for a payer feeding several occurrences, and the finding for a declared category with no rows, whose manual clearing is bound to the rows present at entry. Ruling text: the 22:50 entry of PRIME's rulings log.

## Problem Statement

Modelo 100 has no source for rendimientos del capital mobiliario. Casillas 0027 to 0040 (base del ahorro) and 0046 to 0056 (base general) are manual in every supported edition. Only their totals (0036, 0038, 0040, 0041, 0060) carry formulas, inherited from the 2020 edition (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/formulas/0001-declarations.toml:623-729`). A ledger row with `irpf_category = capital_mobiliario` (vocabulary `src/cadrumo/_data/registry/aeat/facts/0128-irpf-income-category-vocabulary.toml:52`) reaches no casilla and raises nothing, so a saver's interest and dividends are silently absent from the return. The withholding credit already has a source: the per-payer suffered-withholding record feeds 0597 (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml:216`; record `src/cadrumo/domain/renta/retencion_soportada.py:56`). So today the credit can be claimed while its income is missing.

This record decides how interest on accounts and deposits (0027) and dividends (0029) reach the return from records. It also decides how every capital-mobiliario figure the application does not compute is held unresolved. It is decision A1 of the CALCULATORS roadmap; disposals (A2) and personal reductions (A3) are separate records.

## Considerations

- Official design. The input dictionary of every edition from 2020 to 2025 carries a repeating detail record under 0027 (`RegistroB11`: IMP1DB11 ingresos íntegros, IMP2DB11 retenciones, IMP3DB11 gastos) and under 0029 (`RegistroB13`, with the same three amounts). Locations:
  - 2025: `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/02-100-diccionario-declaracion-individual-toma-de-datos-ejercicio-2025-actualizado-14-04-2026-9.properties:237-246`;
  - 2024 (`13-100`): lines 231-240; 2023 (`12-100`): lines 207-216; 2022 (`11-100`): lines 200-209; 2020 (`09-100`) and 2021 (`10-100`) carry the same six rows.
  - The XSD admits 20 `RegistroB11` occurrences (`03-100-esquema-xsd-ejercicio-2025-actualizado-24-06-2026-793-kb-ejecutable.xsd:4399`). The casilla labels are stable (2025 `01-100-…properties:129-142`). There is no design difference between supported years.
- Gross, not net. Interest is integrated "por el importe íntegro, sin descontar la retención practicada" (manual Renta 2025, `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:13662-13664`). The withholding is credited in 0597 (lines 15176-15241). The 2022 manual says the same (2022 manual lines 12257-12317).
- Timing. Capital income is imputed to the period in which the perceptor can demand it (exigibilidad), whatever the date of collection (LIRPF art. 14.1.a; manual 2025 lines 15049-15052, 2022 lines 12134-12137).
- Expenses. Only administration and custody of valores negociables are deductible; discretionary portfolio management is not (LIRPF art. 26.1.a; manual 2025 lines 13745-13772). A plain bank account has no deductible expense.
- Rates. The withholding rate is 19 per cent in every supported year (manual 2025 lines 13467, 13916; 2022 lines 10543, 10976). The legal interest rate for estimated income differs by year (3 per cent in 2022, 3.25 in 2025); that is a registry parameter and out of scope here.
- The suffered-withholding record already holds, per payer and class, `importe_integro_dinerario`, `valoracion_especie`, `retencion`, `ingreso_a_cuenta` and the derived `importe_integro` (`src/cadrumo/domain/renta/retencion_soportada.py:68-128`).
  - Its states are recorded, attested_absent, declared_absent, missing and contradicted (`src/cadrumo/application/aggregation/retencion_soportada_source.py:114-121`).
  - Its doors already exist: `app ledger retencion-soportada record|attest-absence` (`src/cadrumo/entrypoints/cli/app_ledger_retencion_soportada_command_specs.py`).
  - The accepted `2026-11-01-export-parity-suffered-withholding-schemas-adr` makes it the one source of a credit.
- `Transaction` carries no withholding and no reference to an account or security (`src/cadrumo/domain/transactions/models.py:557-633`). Bank cash rows show the net credit.
- Repeated rows reach XML through the existing row-grain path (`src/cadrumo/application/filing/export_xml_dictionary.py:762-875`). The `activity_asset_disposal` family already uses it (`src/cadrumo/domain/calculations/registry/actividad_asset_disposal_bindings.py:232`).
- Pattern. The rental decision (accepted, landing on lane/calc-renta) sets the shape this record follows: a profile record, a typed ledger link and one row-grain family.
- Oracles. Manual 2025 worked examples:
  - deposit interest 400 with 76 withheld (lines 13843-13945);
  - current-account interest 37 with 7.03 withheld, and dividends 1,502 with 285.38 withheld and a 90 custody expense (caso práctico, lines 15093-15241);
  - the fund-participation dividend example (lines 13430-13472) is not used as an oracle: its stated withholding total of 250.80 omits the 399 withheld on the usufruct.
- Filing obligation. Capital income and gains subject to withholding do not oblige a return up to a joint 1,600 euros a year (LIRPF art. 96.2.b; manual 2025 lines 1060-1064, 1152).

## Considered options

- Typed totals on the profile or on the form. Rejected by the coordinator's condition: amounts come from ledger rows, and a typed total cannot be reconciled with its rows.
- A withholding amount field on each ledger row. Rejected: it would create a second source of the withheld figure beside the payer record. The coordinator ruled that out and the suffered-withholding decision forbids it.
- Gross taken only from the payer certificate. Rejected: the figure would rest on one document with nothing in the ledger to prove it, and a payer without a certificate would have no figure.
- Reuse `concepto_ingreso` or `category_id`. Rejected: both carry activity meaning and IVA treatment, and a mixed vocabulary invites misrouting, as the rental record found.
- Chosen: a profile position record, one typed ledger link plus a registry concept vocabulary, and one row-grain source family. The gross is rebuilt from linked net cash rows plus the payer record's withholding, then checked against the payer record's own gross.

## Constraints

- Amounts come only from ledger rows linked to a typed position record. No record holds an annual total.
- The withheld figure has exactly one source: the suffered-withholding payer record of class `capital_mobiliario`. Gross and withholding reconcile with that record. A disagreement is a blocking finding, never a silent pick.
- One mechanism serves every supported year. No year appears in any key, id, field, fact or parameter. Bindings are authored at the earliest registry edition whose design carries `RegistroB11` and `RegistroB13`, and later editions inherit them. An edition override exists only where an official design differs.
- A missing fact is a typed refusal that names the position or payer and its door. Three kinds of income are blocking findings that keep the affected casillas unresolved:
  - foreign-source income;
  - income in kind;
  - every capital-mobiliario kind this record does not compute.
- Private facts (payer NIF, account and security identifiers) persist only in exact-profile encrypted custody.
- Refusal shape follows LIFECYCLE's contract, agreed on 2026-11-11:
  - a new source-diagnostic reason, `income_family_not_computed`, blocking, source kind ledger;
  - message key `application.modelo.findings.income_family_not_computed`, with the family token and the row count as parameters;
  - the words say that the application does not compute the family yet and that the return stays unresolved until the figures are entered;
  - primary door: manual entry of the family's casillas through the modelo work edit action. Where those casillas are row fields the edit refuses, the finding says it is terminal until a calculator lands;
  - secondary door: `aeat app ledger classify TX --irpf-category ...`, only for a misclassified row.

## Implementation

We will source 0027 and 0029, their `RegistroB11` and `RegistroB13` detail rows and their expenses from profile position records and the ledger rows linked to them. One row-grain source family serves pull, preview, calculation and export for every supported year. Every other capital-mobiliario income stays unresolved behind a blocking finding.

First unit, which lands alone. Today the ledger cannot carry these families at all: its IRPF category taxonomy declares only `actividad_economica`, `arrendamiento_local`, `arrendamiento_vivienda_afecto` and `trabajo` (`src/cadrumo/_data/registry/aeat/facts/0081-irpf-ledger-category-taxonomy.toml:20`), and every operator write refuses any other token (`src/cadrumo/domain/transactions/irpf_categories.py:117-131`). Interest credited to a bank account is therefore left unclassified and reaches nothing. The unit adds `capital_mobiliario` (incoming) and `ganancias_patrimoniales` (incoming and outgoing) to that taxonomy, with purposes that none of the activity, rent or employment predicates match (`irpf_categories.py:133-163`), so the rows become classifiable without entering any existing route. Then the `income_family_not_computed` finding fires when the ledger scope of a Modelo 100 calculation holds a row whose `irpf_category` names a family with no calculator; today that is `capital_mobiliario` and `ganancias_patrimoniales`. It also fires, under correction 3 of the acceptance ruling, when the profile declares the income category (`taxpayer.irpf_income_categories`) for the ejercicio and the family has no calculator, even with no ledger rows. It clears for a family once that family's casillas carry values entered through the primary door. That clearing is bound to the set of the family's ledger rows present at entry, so a later row of the family that the entry did not cover raises the finding again. Each later slice narrows the set as it lands. No persona ledger carries such rows today (checked 2026-11-11), so no table row changes. A test on real ledger rows of each covered family proves that the finding fires.

Position record. A repeatable, effective-dated profile record `inversiones.posicion` with a stable row key, entered through the existing `config profile add-row|edit-row|remove-row` door. Fields:

- kind: `cuenta` (current or savings account), `deposito` (term deposit) or `valores_negociables` (a securities account holding listed shares or similar). Later records extend this closed set;
- payer: the entity's NIF and name. The NIF is the key that joins the position to the payer record;
- source country: Spain or another state. Any other state is a blocking finding, because international double taxation is not computed here;
- the taxpayer's ownership share of the position, required, with its start and end dates;
- an identifier (the tail of the account number, or the securities account reference), for the operator only.

Ledger link. `Transaction` gains one optional typed field, `posicion_ref`. A registry-declared concept vocabulary, `concepto_capital_mobiliario`, is held as a new dated registry fact that maps each token to its detail record:

- `intereses` maps to `RegistroB11`;
- `dividendos` maps to `RegistroB13`;
- `gasto_administracion_deposito` maps to the IMP3 expense of the same record and is admitted only on a `valores_negociables` position.

The link makes a row a capital-mobiliario row, as PRIME's R6 ruling of 2026-11-11 23:25 settles for rental links (`model_validation.py:149-162` refuses `irpf_category` on personal rows). A linked personal row carries no `irpf_category`. A linked row with a business-bearing classification (a position held by the activity) must carry `irpf_category = capital_mobiliario`. The activity income and expense aggregations exclude every linked row. A business-bearing row with `irpf_category = capital_mobiliario` and no link, or a linked row whose concept is outside the computed set, raises `income_family_not_computed`. An unlinked personal row cannot be recognised as savings income; the profile-declared category (correction 3) is the trigger that covers it. The profile refuses to remove a position that a ledger row references. Door: `aeat app ledger classify TX --posicion REF --concepto-capital-mobiliario TOKEN`.

Amounts and reconciliation. Corrections 1 and 2 of the acceptance ruling (CADRUMO-PRIME, 2026-11-11 22:50) govern this part. The payer record is stored once per ejercicio, income class and payer (`src/cadrumo/domain/renta/retencion_soportada.py:52`), and its figures are the taxpayer's own share, as the payer's certificate states them per perceptor (RIRPF art. 108.3). So reconciliation is per payer, never per position:

- an occurrence is one position and one token (interest or dividends). Its net cash is the sum of its linked income rows, imputed to the ejercicio by exigibilidad. The row's value date is the exigibility date unless the row carries its own accrual date;
- payer check: the sum, over every occurrence of the payer, of `share × net cash`, plus the payer record's `retencion` taken once, must equal the payer record's `importe_integro` within one cent. Otherwise a blocking finding states both figures and offers the payer-record and ledger doors;
- a payer that feeds exactly one occurrence: that occurrence's withholding is the payer record's `retencion` and its gross is `share × net cash + retencion`;
- a payer that feeds several occurrences (two accounts at one bank, or interest and dividends from one bank): each occurrence's withholding is determined by the governed rate on its gross. The base of withholding is the full consideration (RIRPF art. 93.1, `src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md:1656-1658`) and the rate is 19 per cent (RIRPF art. 90.1, same file line 1619; LIRPF art. 101.4, `src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:2109`). The rate is held as a dated registry rate citing those lines. So an occurrence's gross is `share × net cash / (1 − rate)` and its withholding is `rate × gross`, rounded to the cent. The sum of the occurrences' withholding must equal the payer record's `retencion` within one cent per occurrence, and their gross must pass the payer check. A disagreement is a blocking finding. There is never a proportional allocation;
- a payer feeding several occurrences where the governed rate does not apply is a typed refusal naming the payer, because the bundled text grounds no other split. Examples: the 60 per cent reduction of RIRPF art. 90.2, an exempt instrument, or an attested absence for only some occurrences;
- a payer with linked rows and no payer record is refused through the existing doors: record the certificate, or attest that no withholding was practised. After an attested absence every occurrence of that payer has zero withholding and its gross equals the share of net cash;
- a payer record with no linked ledger rows is a blocking finding: income on a certificate that the ledger does not show;
- income in kind (`valoracion_especie` above zero) is a blocking finding.

Rows. Each interest-bearing position gives one `RegistroB11` occurrence, and each dividend-paying position gives one `RegistroB13` occurrence. Each occurrence carries gross, withholding and expenses.

- 0027 and 0029 are the sums of their occurrences.
- 0036 to 0041 follow from the inherited formulas.
- 0597 keeps its existing binding, which already sums the payer records.
- More occurrences than the XSD admits are refused at export.

Source family. The capital-mobiliario rows get one `BindingSourceKind` member, enrolled in the shared dispatch beside `activity_asset_disposal` with its registration row, validator and resolver. There is no modelo-name branch. The calculation revision records the profile and ledger revisions it consumed, so the drift gate sees later edits.

Not computed here. Each item is classified under PRIME's ruling of 2026-11-11 23:25, which binds every slice. An item the application does not compute is a blocking finding when leaving it out could lower the tax or misstate an identifying fact. It may be a served non-blocking limitation only when leaving it out can only raise the tax and no stored fact shows that it applies.

Blocking findings, each leaving the affected casilla unresolved, because each is income whose omission lowers the tax:

- 0028, bonified interest (DT 6.a);
- 0030, Letras del Tesoro;
- 0031, other financial assets;
- 0032 to 0035, insurance, capitalisation and preferentes;
- the whole base-general block, 0046 to 0056;
- foreign-source income and income in kind;
- related-party loans (the general-base share under LIRPF art. 46.a);
- the prima de emisión and capital-reduction rules (art. 25.1.e). No concept token admits such a receipt, so its row stays unlinked and raises `income_family_not_computed`. Classifying it as a dividend would misstate both the income and the later acquisition cost.

Not computed and not offered, shown as a non-blocking limitation:

- 0039, the DT 4.a reduction, and 0043 and 0044, its accumulated deferred capital. The reduction applies only to insurance income (0032), which is itself a blocking finding above. So leaving it out can only raise the tax, and no stored fact shows that it applies. The limitation is served at verification and in the export result, names the casillas, and says that the return may overstate the tax.

Hypotheses that may change within these constraints: the field and token names; the source-kind name; whether the concept vocabulary is its own fact or a family in an existing one; whether the position record lives in the profile or in a ledger-side register with the same custody.

## Rationale

The payer record already holds the withheld figure, the gross and an evidence fingerprint, and it is the accepted single source of the credit. The gross is built from linked cash rows plus that one withheld figure, then checked against the record's own gross. That gives two independent paths to one number without a second source of withholding. The profile supplies custody, effective dating, row keys and a door at no new cost. The row-grain path is the one the rental and asset-disposal families already use. The blocking finding turns today's silent omission into a visible, unresolved state that the operator can resolve by hand; the coordinator approved it as the first unit.

## Consequences

- Interest and domestic dividends reach the return from records, for any number of positions up to the XSD bound, and the credit and the income from the same payer agree.
- A saver must record the payer certificate or attest that nothing was withheld. A mismatch blocks verification.
- Every other capital-mobiliario income stays unresolved until its slice lands, so some returns that export silently today will refuse.
- Reconsider if a later design changes `RegistroB11` or `RegistroB13`, if joint returns (tributación conjunta) come into scope, or when A2 adds securities disposals that share the position record.
