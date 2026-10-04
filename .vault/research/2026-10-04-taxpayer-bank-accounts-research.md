---
tags:
  - '#research'
  - '#taxpayer-bank-accounts'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:28427787c5a4b4eb6a7dcb99b3cf8d49f2300274716de3a9c697f9b81853c9c4'
related:
  - "[[2026-06-24-m303-refund-fichero-block-adr]]"
  - "[[2026-06-21-m303-carry-reconciliation-adr]]"
  - "[[2026-10-04-modelo-360-solicitud-custody-adr]]"
---

# `taxpayer-bank-accounts` research: `Official AEAT rules for charge and refund accounts and result disposition`

Question: what do the official AEAT record designs, statutory forms and payment órdenes require of the taxpayer's own bank accounts and of the forma de pago / result disposition for Modelos 303, 390, 100, 111, 115, 130, 131 and 360? It matters because every 303 refund, domiciliación and Nota 3 export refuses today for lack of an account supplier, and the store that will supply it must hold exactly the account shapes and elections the designs admit. Conclusion: the account data needed across these modelos reduces to one account shape (IBAN, optional SWIFT-BIC, optional foreign-bank block, holder) used in two roles, debit for domiciliación and credit for devolución; 303 alone puts both roles in one slot on its `DID00` page; 390 carries no account; 360 carries a mandatory IBAN plus BIC whose holder may be the representative; NRC and reconocimiento de deuda are presentation-time payment modes absent from every fichero design. Three premises of the originating brief are wrong and are corrected below (360 audience, domiciliación entity restriction, 303 refund-only account). Discovery ran without semantic search (targeted grep and listing).

## Findings

### 303 "Tipo de declaración" admits eight keys and no others

Page `DP30301` position 13, length 1, mandatory: C compensación, D devolución, G cuenta corriente tributaria ingreso, I ingreso, N sin actividad / resultado cero, V cuenta corriente tributaria devolución, U domiciliación del ingreso en CCC, X devolución por transferencia al extranjero (2026 design `.../modelo_303/files/01-303-ejercicio-2026-y-siguientes-actualizado-28-01-26-378-kb-xlsx.xlsx.extracted.md:47`, `:135-138`; same list in the 2025 design `06-303-ejercicio-2025-...extracted.md:135-136`). The 2021-07 and 2022 designs restricted X to 3T, 4T and 07-12 (`02-303-...2022...extracted.md:121`); later designs drop that restriction. The repository vocabulary `src/cadrumo/core/result_disposition.py:63` already holds these codes plus B and R for other modelos. High confidence.

### 303 has one IBAN slot for both domiciliación and devolución, on the `DID00` page

`DID00` (823 positions): position 12 SWIFT-BIC (11, "Devolución"), 23 IBAN (34, "Domiciliación/Devolución - IBAN"), 57 bank name (70), 127 address (35), 162 city (30), 192 country code (2), 194 Marca SEPA (0 vacía, 1 Cuenta España, 2 UE SEPA, 3 Resto Países) (2026 design `:607-633`). Design note 6: "Para el IBAN español deberá empezar por ES y únicamente se usan las primeras 24 posiciones" (`:627`). Nota 3: a rectificativa with content in casilla 111 must carry bank data even when the forma de pago is not devolución, unless page 3 field 33 (position 440, cancel/modify the prior domiciliación) is X; casilla 111 is at 441 (`:434-435`, `:634-635`). The 2024 and 2025 designs keep the same `DID00` offsets (`05-303-ejercicio-2024-hasta-periodos-08-y-2t-...extracted.md:576-590`); before 2023 the block sat on page 3 (2022 design SWIFT 389, IBAN 400, `02-303-...extracted.md:329-337`). The registry already places these slots as record `m303-domiciliacion` with `selected_account.*` producer keys (`src/cadrumo/_data/registry/aeat/modelos/303/revisions/2026-y-siguientes/export/0010-record-m303-domiciliacion.toml:5-172`). Consequence for the store: the 303 account page is required for U, D, X and Nota 3, so a charge-only or refund-only design would leave half the cases unfillable. This agrees with the DID predicate in the amended `2026-06-21-m303-carry-reconciliation-adr` and contradicts the "emit DID only for D/X" wording in `2026-06-24-m303-refund-fichero-block-adr`. High confidence.

### The statutory 303 form requires the taxpayer to hold the refund account and offers three account kinds

Orden HAC/27/2026 form (BOE-A-2026-1761, pág. 12134): "Devolución (8)", casilla 73: "Solicito que el importe a devolver reseñado, me sea abonado mediante transferencia bancaria a la cuenta indicada de la que soy titular"; "Rectificación (9)", casilla 111, same wording; account kinds: "cuenta bancaria abierta en España" (IBAN), "Unión Europea/SEPA" (IBAN plus SWIFT-BIC), "Resto países" (SWIFT-BIC, account number, bank name, address, city, country) (`src/cadrumo/_data/corpus/normatives/pdf/boe-a-2026-1761-modelo-390-form.pdf.extracted.md:878-899`). A "Resto países" account need not be an IBAN. No residency condition for choosing X was found in the corpus or the órdenes read; treat X eligibility beyond the form as ungrounded. High confidence on the form text.

### Domiciliación: holder is the obligado; since 1 February 2024 a SEPA account at a non-collaborating entity is admitted

Orden EHA/1658/2009 art. 2: the account must be held by the obligado al pago (any declarant on a joint Renta), be a cuenta a la vista or de ahorro, and sit at an entidad colaboradora, save art. 5 bis (https://www.boe.es/buscar/act.php?id=BOE-A-2009-10326; medium confidence, tool-extracted text). Art. 5 bis, added by Orden HFP/1397/2023 with effect 1 February 2024, admits a SEPA account at a non-collaborating entity, with a collaborating entity as intermediary. Orden HAP/2194/2013 art. 8.b binds the domiciliación IBAN to EHA/1658/2009 art. 2 (https://www.boe.es/eli/es/o/2013/11/22/hap2194/con). The bundled 111, 130 and 131 instructions state the 2024 change (`src/cadrumo/_data/corpus/aeat_official/instructions/modelo_111/files/modelo-111-instrucciones.html` text line 342; `.../modelo_130/files/modelo-130-instrucciones.html` lines 195, 214; `.../modelo_131/files/modelo-131-instrucciones-2026-late.html` line 232). For Renta the SEPA non-collaborating route applies only when the taxpayer has no account at a collaborating entity (`src/cadrumo/_data/corpus/normatives/html/orden-hac-277-2026.html.extracted.md:154`). For 303 the rule is inferred through Orden EHA/3786/2008's reference to HAP/2194/2013 arts. 6-11 (`.../orden-eha-3786-2008.html.extracted.md:32`), and the 303 design note 6 speaks only to the Spanish IBAN shape. The brief's premise "domiciliación requires a Spanish IBAN at an entidad colaboradora" is therefore outdated for 111/130/131 and unproven either way for 303's fichero. High confidence for 111/130/131; open for 303.

### Domiciliación closes before the voluntary period ends; the registry already stores the cutoff

EHA/1658/2009 art. 3 orders domiciliación at presentation, and the domiciliación window closes "tres días hábiles o cinco naturales" before the end of the plazo; art. 5.2 has the collaborating entity charge on the due date (medium confidence, tool extract). The AEAT 2026 calendar: 303 quarterly 1-15 April, July, October and to 27 January for 4T 2025; 303 monthly generally 1-25; 111 and 115 1-15; 130 and 131 1-15 and to 27 January; 100 to 25 June (https://sede.agenciatributaria.gob.es/Sede/ayuda/calendario-contribuyente/calendario-contribuyente-2026/plazos-presentacion-autoliquidaciones-domiciliacion-bancaria.html). The registry already models this per filing window as `payment_cutoff_on` (e.g. `src/cadrumo/_data/registry/aeat/modelos/111/revisions/2019-y-siguientes/deadline_windows/*.toml`, "present only where the bundled calendar explicitly publishes bank domiciliation"); 303 declares it in the `2024-hasta-08-y-2t`, `2025` and `2026-y-siguientes` revisions only, and 131/2025 omits it as ungrounded (`.../131/revisions/2025/deadline_windows/0001-declarations.toml:6-7`). No export path consults it (only advisory context at `src/cadrumo/application/modelo/work_plazo.py:352`).

### Refunds outside REDEME are available only for the last period of the year

RIVA art. 30.1 (`src/cadrumo/_data/corpus/normatives/html/rd-1624-1992.html.extracted.md:779`), already applied by `refund_disposition_available` and recorded in `2026-06-24-m303-refund-election-adr`. REDEME indicator: 303 page 1 position 110 ("1"/"2") (2026 design `:53`). No new finding beyond the existing records.

### NRC and reconocimiento de deuda are not fichero keys

None of the 303, 111, 115, 130, 131 designs carries a key for reconocimiento de deuda or NRC; 303 has only C/D/G/I/N/V/U/X, 111 and 115 I/U/G/N, 130 and 131 I/U/G/N/B. Orden HAP/2194/2013 art. 9 puts the NRC on the payment receipt (9.1.a), lets the clave carry a compensación, aplazamiento or fraccionamiento request (9.1.d), and forbids combining aplazamiento/fraccionamiento with simple reconocimiento de deuda. The 130 instructions list "reconocimiento de deuda con solicitud de aplazamiento o compensación, el pago por transferencia, o anotación en cuenta corriente tributaria" and "Realizar pago (obtener NRC)" as presentation choices (`.../modelo_130/files/modelo-130-instrucciones.html` lines 197, 211). So an exported I result stays I; NRC, transferencia and reconocimiento are chosen when the operator presents it. High confidence on absence from the designs; medium that the choice exists only at presentation.

### 390 carries no account and no payment key

390 page 1 position 13 is "RESERVADO PARA LA A.E.A.T. (Dejar en blanco)" and the 2025 design has no IBAN field (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/files/01-390-ejercicio-2025-actualizado-05-12-2025-544-kb-xlsx.xlsx.extracted.md:47`); casillas 97 (a compensar) and 98 (a devolver) report the last-period result as information (`boe-a-2026-1761-modelo-390-form.pdf.extracted.md:1266-1268`). The 390 consumes the 303 disposition only as carry information, never an account. High confidence.

### 100 has separate structured payment, refund and rectification account blocks

`TIPODECLARACION`: I, U, N, D, R (renuncia), X (devolución en cuenta extranjera), others reserved. The ingreso block holds an IBAN for unsplit payment, IBANs for first and second instalments and a second-instalment domiciliación flag; the devolución block is a choice of Spanish IBAN, `DEVSEPA` (IBAN plus SWIFT) or `DEVNOSEPA` (account plus SWIFT plus bank name, address, city, country); `NEGATIVA` has a parallel `RECT*` block (`.../modelo_100/files/03-100-esquema-xsd-ejercicio-2025-actualizado-24-06-2026-793-kb-ejecutable.xsd:12-28`, `:1062-1074`, `:1137-1220`; dictionary `01-100-diccionario-...properties:64-90`). The second instalment may be domiciliated to a different account than the first, so the 100 charge role can need two accounts in one filing. High confidence.

### 111, 115, 130 and 131 carry a domiciliación IBAN only

111 IBAN at 553 (34), 115 at 206, 130 at 446, 131 on a `DID00` page at position 12; keys 111/115 I/U/G/N, 130/131 I/U/G/N/B (`.../modelo_111/files/01-...extracted.md:39,78,83`; `.../modelo_115/files/01-...extracted.md:42,55,60`; `.../modelo_130/files/01-...extracted.md:41,68,73`; `.../modelo_131/files/09-131-ejercicio-2026-actualizado-28-09-26.xlsx.extracted.md:47,114,271-282`). No refund account. High confidence for 131 (2026 design); medium for 111/115/130, whose bundled designs date 2019-2021. The application currently refuses U for every modelo except 303 by a modelo-name branch (`src/cadrumo/application/modelo/result_disposition_resolution.py:261-265`) although these designs admit U.

### 360 is a refund application by businesses established in Spain; its account may be the representative's

Design title: "Solicitud de devolución del IVA soportado por determinados empresarios o profesionales establecidos en el territorio de aplicación del Impuesto"; AEAT forwards it to the Member State of refund (RIVA art. 30 ter.1) (`.../modelo_360/files/01-360-orden-eha-789-2010.pdf.extracted.md:3-8`; `rd-1624-1992.html.extracted.md:834-838`, `:846`; `.../instructions/modelo_360/files/modelo-360-procedure.html`). Non-established businesses use art. 31 / 31 bis and modelo 361, so the brief's premise is wrong. Section 4 "Devolución solicitada" carries field 103 "Importe solicitado" and 104 "Divisa"; section 6 "Datos bancarios" fields 113-117 are all obligatorio: holder name (25), "En calidad de" A solicitante / R representante, IBAN (34), Banco-BIC (11), Divisa ISO 4217 default EUR (design fields 103-117 at `01-360-orden-eha-789-2010.pdf.extracted.md:118-133`). There is no Tipo de declaración, no Marca SEPA and no ingreso field; the 360 export layout declares no `filing.result_disposition` producer key (`src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/export/0002-record-m360-solicitud.toml:228-284` lists the account keys only). The only disposition the design expresses is a refund request; the current INGRESO fallback (`result_disposition_resolution.py:88`, applied at 196) has no grounding. High confidence.

### Options the ADR must weigh

- Account home: user-profile schema fields (the route of `2026-06-24-m303-refund-fichero-block-adr`, later retired: `src/cadrumo/application/user_profile/tests/test_retired_filing_export_paths.py`), a filing-only account register, or a ledger-owned own-account register that transactions also reference. The evidence that one account shape serves both roles across 303/100/111/115/130/131/360, and that the holder must be the taxpayer for domiciliación and 303/100 refunds, favours a single own-account entity with role designations rather than per-modelo copies.
- Role election: standing designation, per-modelo designation, per-filing choice. 100's two-instalment domiciliación and 303's per-period choice argue for per-filing override over a default.
- Non-ES accounts: the evidence supports SEPA IBAN plus BIC and non-SEPA account plus bank block for refunds (303 X, 100 X/DEVNOSEPA, 360); for domiciliación, art. 5 bis admits SEPA accounts for 111/130/131 but the 303 fichero rule is not grounded.
- 360 disposition: no fichero code exists; the ADR must settle whether the system records a semantic refund disposition or none.

Not investigated: full consolidated text of Orden HAP/2194/2013 and EHA/1658/2009 art. 5 bis (BOE pages truncated); current post-2021 designs for 111/115/130; Directive 2008/9/EC; 200, 202 and 210 account blocks (their producer fact sets exist in code but were out of scope for the official reading).

## Sources

- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_303/files/01-303-ejercicio-2026-y-siguientes-actualizado-28-01-26-378-kb-xlsx.xlsx.extracted.md`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_303/files/02-303-ejercicio-2022-y-siguientes-actualizado-27-12-2021-332-kb-xlsx.xlsx.extracted.md`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_303/files/05-303-ejercicio-2024-hasta-periodos-08-y-2t-actualizado-01-04-24-376-kb-xlsx.xlsx.extracted.md`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_303/files/06-303-ejercicio-2025-actualizado-04-12-2025-380-kb-xlsx.xlsx.extracted.md`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/files/01-390-ejercicio-2025-actualizado-05-12-2025-544-kb-xlsx.xlsx.extracted.md`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/03-100-esquema-xsd-ejercicio-2025-actualizado-24-06-2026-793-kb-ejecutable.xsd`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_111/files/01-111-orden-eha-3127-2009-ejercicios-2019-y-siguientes-actualizado-mayo-2021-179-kb-xls.xls.extracted.md`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_115/files/01-115-orden-eha-3435-2007-ejercicios-2019-y-siguientes-actualizado-febrero-2019-172-kb-xls.xls.extracted.md`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_130/files/01-130-orden-hap-258-2015-ejercicios-2019-y-siguientes-actualizado-marzo-2019-176-kb-xls.xls.extracted.md`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_131/files/09-131-ejercicio-2026-actualizado-28-09-26.xlsx.extracted.md`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_360/files/01-360-orden-eha-789-2010.pdf.extracted.md`
- `src/cadrumo/_data/corpus/normatives/pdf/boe-a-2026-1761-modelo-390-form.pdf.extracted.md`
- `src/cadrumo/_data/corpus/normatives/html/orden-eha-3786-2008.html.extracted.md`
- `src/cadrumo/_data/corpus/normatives/html/orden-hac-277-2026.html.extracted.md`
- `src/cadrumo/_data/corpus/normatives/html/rd-1624-1992.html.extracted.md`
- `src/cadrumo/_data/corpus/aeat_official/instructions/modelo_111/files/modelo-111-instrucciones.html`
- `src/cadrumo/_data/corpus/aeat_official/instructions/modelo_130/files/modelo-130-instrucciones.html`
- `src/cadrumo/_data/corpus/aeat_official/instructions/modelo_131/files/modelo-131-instrucciones-2026-late.html`
- `src/cadrumo/_data/corpus/aeat_official/instructions/modelo_360/files/modelo-360-procedure.html`
- `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2026-y-siguientes/export/0010-record-m303-domiciliacion.toml`
- `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/export/0002-record-m360-solicitud.toml`
- `src/cadrumo/_data/registry/aeat/modelos/131/revisions/2025/deadline_windows/0001-declarations.toml`
- `src/cadrumo/application/modelo/result_disposition_resolution.py:88`
- `src/cadrumo/application/modelo/result_disposition_resolution.py:261`
- `src/cadrumo/application/modelo/work_plazo.py:352`
- `src/cadrumo/core/result_disposition.py:63`
- https://www.boe.es/eli/es/o/2013/11/22/hap2194/con
- https://www.boe.es/buscar/act.php?id=BOE-A-2009-10326
- https://sede.agenciatributaria.gob.es/Sede/ayuda/calendario-contribuyente/calendario-contribuyente-2026/plazos-presentacion-autoliquidaciones-domiciliacion-bancaria.html
