---
tags:
  - '#audit'
  - '#modelo-347-fileability'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:47442c418a2a90d777e8a75a081986f6b551523a841a4ebaf05efef0384008bc'
related:
  - "[[2026-08-27-tui-architecture-modelo-347-counterparty-residency-scope-adr]]"
---

# `modelo-347-fileability` audit: `Modelo 347 fileability discovery`

## Scope

Read-only discovery of whether Modelo 347 (declaración anual de operaciones con terceras personas) is fileable
from data Cadrumo holds, at committed `HEAD` `f5d5f29454`, across three surfaces: the filing calendar and
obligation, ledger extraction through bindings to the fichero, and taxpayer profile and regime enrollment.
Evidence: real-code reproductions through `derive_modelo_applicability`, `build_overview_calendar`,
`InvoiceCatalogueSourceResolver`, `build_draft` and `export_draft` against the published authority, plus the
focused 347, applicability and profile tests (91, 148 and 229 passed; the 6 failures were unrelated to 347).
Law is quoted from the bundled consolidated texts: `corpus/normatives/html/rd-1065-2007.html` (RGAT),
`rd-1624-1992.html` (RIVA), `orden-eha-3012-2008-art-10.html`, and the 347 diseños de registro under
`corpus/aeat_official/disenos_registro/modelo_347/`.

## Findings

### live-path-no-declarado-rows | critical | the live resolver returns no type 2 rows, so no 347 fichero can be produced

`application/invoices/source_resolver.py:209-258` returns only `binding_values`; the canonical row builder
`resolve_invoice_binding_row_values` (`domain/calculations/registry/invoice_bindings.py:712`) is wired for 349
only (`source_resolver.py:1032`). The export then refuses "required export record 'm347-declarado' has no
applicable occurrence". The existing `row_binding_values` channel (`source_mesh.py:888`, used by
`atribucion_member.py:123-129`) is the route. `Modelo347ContraparteRow` (`domain/modelos/row_models.py:859`) is
a parallel row shape with no projection into the `modelo-347-contraparte-row-*` bindings, and 349 re-sums its
rows in `_calculation_modelo_adjustments.py:512-554`; both are duplication to retire with this fix.

### signed-amount-fields | critical | declarado amount fields are typed text and refuse the decimal values

Declarado positions 83, 136, 168, 200, 232 (and the unbound 116, 152, 184, 216, 248, 284) and type 1 145-160
are `data_type = "text"`. aeat-dr-347-2025 pos. 83: "Se consignará una "N" cuando el importe anual de las
operaciones sea menor que 0 (cero). En cualquier otro caso … un espacio" (same in the 2011 design). The generic
`signed_monetary_composite` rule (`dev/registry/pipeline/render_profile_rules.py:253`, grammar
`render_profile_authority.py:190`) exists; the separate `_validate_reviewed_m180_composite` branch
(`render_profile_authority.py:223,346`) is existing drift to fold into it.

### threshold-not-split-by-direction | high | the 3.005,06 floor sums a counterparty's entregas and adquisiciones together

RGAT art. 33.1: "A tales efectos, se computarán de forma separada las entregas y las adquisiciones de bienes y
servicios." `invoice_bindings.py:845-878` keys `general_totals` by party only and feeds both the row family and
the declarante summary; docstrings in `m347_threshold.py:103-125` and `_invoice_row_materialization.py:227-238`
state the combined reading; `test_source_resolver.py:357` asserts it. Reproduced: 2,000 sales plus 2,000
purchases with one customer emits two declarado rows instead of none. `validate_m347_threshold`
(`row_models.py:1151-1180`) re-implements the comparison instead of `_declarable_party_ids` and ignores the
clave C floor. Clave buckets per the corpus: entregas B and F (RD 1619/2012 DA 4ª.7.a "En concepto de ventas"),
adquisiciones A and G (DA 4ª.7.b), C its own 300,51 floor per beneficiary (arts. 32.c, 33.4), D its own bucket
(art. 33.3, reading, ambiguous), E with no floor from 2025 (art. 33.3 "cualquiera que sea su importe"; the 2011
design says "superiores a 3.005,06", ambiguous for 2014-2024).

### type-1-totals-unbound | high | declarante pos. 136-144 and 145-160 are manual casillas

Binding the casillas is refused by `validate_informative_class_invariant`
(`dev/registry/compiler/validate_revision_rules.py:235`), which correctly keeps 17 informative modelos free of
bound casillas, and the class/domain coherence gate (`registry_classification_coherence.py:220`) forbids
reclassifying 347. Export fields can render a binding directly (`BindingConsumerKind.EXPORT_FIELD`,
`binding_targets.py:98,176`; precedent modelo 232); the summary values already reach `draft.binding_values`.

### sii-filers-not-exempt | high | SII filers are told they must file

RGAT art. 32: "No estarán obligados a presentar la declaración anual: … e) Los obligados tributarios a que se
refiere el artículo 62.6 del Reglamento del Impuesto sobre el Valor Añadido"; RIVA art. 62.6 covers mandatory
("deberán llevarse a través de la Sede electrónica …") and voluntary ("podrán optar …") SII. The 347 rule
(`modelos/347/revisions/2011-2024/applicability/0001-declarations.toml:1-7`) and `ApplicabilityRuleDefinition`
(`schema_revision_members.py:198-216`, evaluator `applicability.py:354-400`) can only express positive gates;
`iva.sii_enrolled` and `iva.voluntary_sii_enrolled` exist but are ignored. Reproduced: SII sociedad gets
`applicable`.

### art-32b-estimacion-objetiva | high | the módulos plus special-IVA-regime carve-out is not encoded

Art. 32.b exempts estimación objetiva filers simultaneously in simplificado, REAGP or recargo de equivalencia
"salvo por las operaciones por las que emitan factura", while simplificado filers "incluirán … las adquisiciones
de bienes y servicios … que deban ser objeto de anotación en el libro registro de facturas recibidas". This
scopes operations, so it belongs in the resolver's observation filter, not applicability.

### goods-imports-exports-declared | high | art. 33.2.g exclusions are not applied

Art. 33.2.g: "Las importaciones y exportaciones de mercancías". `_m347_invoice_observation`
(`source_resolver.py:767-822`) excludes only 349 operations; `test_source_resolver.py:860` asserts that an
`export_third_country_zero_rated` sale is declared. The accepted ADR on counterparty residency reasons from the
permanent-establishment clause of letter g only; its non-residency conclusion stands, its implicit goods-export
inclusion does not. The category catalogue (fact `0084`, `iva_category_catalogue.py:106`) is the mechanism.

### other-art-33-2-exclusions | medium | letters c, e, f, h and the withholding part of i are unimplemented

Implemented: letter a partly (no NIF) and i for 349 only. Missing: c (gratuitous non-subject or exempt), d
(exempt leases outside activity), e (stamps and postage), f (art. 20.tres social entities), h (Canarias, Ceuta,
Melilla shipments) and i for received invoices with withholding (RIRPF art. 108.2 annual declaration).

### obligation-ignores-ledger-and-year | high | the obligation is one undated operator boolean never compared with the ledger

`TaxpayerProfile.third_party_transactions_above_347_threshold` (`models.py:633`; schema `schema.toml:1546-1553`;
payer fact `0139`) is the only trigger; it is not read per filing year although the section is effective-dated,
and the ledger's own per-counterparty totals (`m347_threshold.m347_declarable_party_ids`) are never compared.
A profile "no" with an above-threshold counterparty silently suppresses the obligation. The clave C 300,51
floor is absent from the gate (art. 32.c), so a fee collector answering "no" gets `not_applicable`.

### activity-requirement | medium | a salaried filer with the flag set is told to file

Art. 31.1 binds those "que desarrollen actividades empresariales o profesionales"; no activity or income
category gate is declared on the 347 rule.

### per-row-fields-stamped | high | single-valued casillas are stamped on every declarado row

`_casilla_field_value` ignores the row index (`application/filing/_record_field_renderer.py:242`): provincia,
seguro, arrendamiento, metálico (art. 34.1.h, no cash fact), transmisiones de inmuebles, criterio de caja (pos.
281, 284-299; `Transaction.cash_accounting_treatment` exists but is unread; quarters must be blank), inversión
del sujeto pasivo (pos. 282, from the `domestic_reverse_charge` category), depósito and BDNS. The 2025 design
requires these operations "consignarlas separadamente del resto", so they belong in the key of the existing
`_build_contraparte_clave_rows` (`_invoice_row_materialization.py:249`).

### inmueble-record-and-nonresident-rows | medium | the inmueble record is always emitted and foreign NIFs overflow

`m347-inmueble` is required and non-repeating, so an empty record is always emitted; the referencia catastral
family in `detail_record_bindings.py:260,317` is the mechanism to extend. A non-resident counterparty's foreign
NIF is bound into pos. 18-26 ("Sólo se cumplimentará con los NIF asignados en España") and overflows; the
design requires blank NIF, provincia 99, country code and pos. 264-280 for EU operators.

### grounding-and-legal-registry | medium | the art. 31 citation points at a stand-in and arts. 32 and 62.6 are not registered

`legal/operaciones-terceros.toml:1-19` cites `rd-1065-2007-art-31.html`, a hand-written split whose text is not
the BOE consolidated article and which carries "3.005,06", absent from the real art. 31. No
`rd-1065-2007:art-32` or `rd-1624-1992:art-62` entity exists; `sii_enrolled` cites RIVA art. 71.

### edition-2014-2024-grounding | medium | the 2011-2024 edition lacks pos. 264-299 required from 2014

RGAT art. 34.1.j/k/l (RD 828/2013) apply from 2014; the 2014-2024 diseño is not in the corpus, yet the
revision claims filing grade for those years.

### quality-items | low | dating, tipo de soporte, census, explain, locales, role loading, weekend shift

Received invoices are dated by `issued_at` (art. 35.1 points to registry entry). Type 1 pos. 58 is manual
(`telematic_transport_choice` precedent exists). Census sync adopts no regime or SII facts although the 036
casillas exist. The explain view omits the deciding facts. es, ca and hu carry formal register in the SII and
criterio de caja prompts. `_m347_filer_declaration_roles` reopens an authority lease per invoice and reads the
latest window instead of the filing period. The calendar does not apply the weekend shift when a holiday
calendar is unavailable (Ley 39/2015 art. 30.5). Expenses booked without an invoice are invisible with no
advisory.

### verified-correct | low | items confirmed against the law

Threshold fact 3.005,06 EUR (`facts/0030`) cited to art. 33; strict "superado" comparison; amounts include IVA
(art. 34.2.a); quarters sum to the annual amount; clave C uses the beneficiary NIF; C, D and E need a filer
role and an invoice fact; F and G follow RD 1619/2012 DA 4ª; type 1 totals are read off the same rows as the
declarado family; foreign-currency invoices without a euro value are withheld; the February window per Orden
EHA/3012/2008 art. 10, unchanged by Orden HAC/1431/2025; CLI and TUI share one applicability, calendar and
work-create backend.

## Recommendations

- Decide the type 1 totals route (export fields reading the summary bindings), the per-direction threshold
  bucket model as dated registry data, a shared applicability exclusion mechanism for art. 32, the art. 33.2
  exclusion mechanism on the category catalogue, and the amendment of the residency-scope ADR for goods
  imports and exports: one follow-on ADR, `2026-10-03-modelo-347-fileability-adr`.
- Every repair extends the canonical mechanism named in its finding; the duplicates named in
  live-path-no-declarado-rows and threshold-not-split-by-direction are retired in the same change.
