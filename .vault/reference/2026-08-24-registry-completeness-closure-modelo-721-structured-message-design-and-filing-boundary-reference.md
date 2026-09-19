---
tags:
  - '#reference'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:5efba8270df4aff619bb89affb00e77003595815685cf4ccd039ee02ed8c3714'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` reference: `Modelo 721 structured message design and filing boundary`

## Summary

Modelo 721 revision `2023-y-siguientes` is a valid applicability-grade
obligation, but it is not fileable from Cadrumo for any selected exercise. This
is an authorable, source-backed gap, not a terminal absence of official
authority: the primary BOE order mandates structured messages, and AEAT
publishes the SOAP/XML technical package, validation material, and XSD schemas.
The exported payload is neither a fichero BOE with positional offsets nor an
ordinary printed form.

The shipped record contains two BOE PDFs as `form_spec` sources, seven manual
or informational casillas, no bindings, no export layout, and applicability
grade. That preserves deadline and obligation reach but does not represent the
full electronic declaration. The seven fields omit, among other official
message facts, the declarant/contact header, stable detail-record identifier,
custodian identification and address branches, units, unit valuation, valuation
source, condition-end date, and origin. A narrow informational surface must not
be promoted into a filing schema merely because it is grounded in the annex.

The exact fileable boundary is empty. The outcome does not authorize a remote
AEAT submission, a fixed-width compatibility layout, or a second XML writer.

## Official message-design evidence

BOE-A-2023-17429, Orden HFP/886/2023, establishes the initial authority. Its
article 1 requires annual filing by sending computer messages; articles 5 and 6
require those messages to follow the annex's fields and the format and design
published on the AEAT Sede. The order first applies to exercise 2023, filed in
2024. Its annex is a field-and-group specification for electronic messages,
including operation, model, exercise, schema version, declarant, and repeating
detail records. It is not a byte-position table.

BOE-A-2024-27528 article 9 replaces that annex. Its final provision makes the
replacement first applicable to exercise 2024 declarations submitted in 2025.
The replacement visibly changes the message field specification, including the
decimal precision of `ValorMoneda`; the 2023 and 2024 message designs are
therefore distinct evidence eras. This Step makes no open-ended technical-schema
claim for 2025 onwards.

AEAT's active Modelo 721 procedure publishes a web-service description,
validation document, and a zip of schemas in addition to the content annex.
The service description identifies SOAP 1.1 document/literal over HTTPS,
UTF-8 XML, client-certificate authentication, request and response messages,
and the official WSDL plus `Declaracion721.xsd`,
`DeclaracionInformativa721.xsd`, and response schema locations. The FAQ states
that external software sends XML messages under the annex specification. These
are precisely the technical authorities missing from the shipped source
catalogue; they must be acquired and hash-pinned before any exporter is
declared.

No Modelo 721 SOAP contract package is currently enrolled or hash-pinned. The
open-ended applicability revision cannot make a current Sede document describe
all future exercises. Before a filing claim can be considered, future owner
work must create two distinct immutable inventories: one for exercise 2023 and
one for exercise 2024. Each must identify every governing WSDL, request XSD,
response XSD, and accompanying validation authority by exact member hash and
package hash, with explicit legal and filing-context scope. The registry must
then select the package from the law-selected revision and filing context, not
from the revision id alone or a generic 2023-plus label.

## Shipped boundary and no-redeclaration finding

The source catalogue currently calls the two BOE annex PDFs `form_spec`, and
the revision's `export_layouts` disposition correctly refuses a positional
fixed-width design. Its prose is nevertheless too narrow: the annex is not
merely a printable form, but it is also not a positional record design. It is
the published field grammar for an XML/SOAP declaration. Correct that wording
when the full source and casilla remedy lands; do not use the correction alone
as a filing claim.

Vaultspec-RAG discovery followed by exact-symbol confirmation found no Modelo
721 filing implementation, producer namespace, generator mapping, render
profile, or emitted-export proof. It also found the existing canonical XML
path: `ExportLayoutFormat` has only `fixed_width` and `xml_dictionary`, and
`_export_xml_dictionary.py` reads an official dictionary and XSD to write a
standalone declaration XML document. Modelo 721's published contract is
constraint-shape divergent: it requires SOAP document/literal operation
messages, request and response schemas, and client-certificate transport. The
existing XML-dictionary writer can be reused only where a source-backed
comparison proves a shared primitive; it cannot be relabelled as a Modelo 721
writer or used to infer the SOAP envelope, operation, or response lifecycle.

This confirms there is no code redeclaration to remove today and no existing
canonical implementation that can simply be switched on. The required future
work is an extension of the existing filing authority, not a parallel exporter
or web-service client.

## Owner and reconsideration

`W02.P04.S26` must enroll exact technical-source scope in
`2026-08-14-registry-temporal-coverage-plan`: acquire and hash-pin AEAT's
official 2023/2024 service description, validation document, WSDL, request and
response XSDs, with explicit exercise applicability. It must keep the 2023 and
2024 designs distinct, and it must not let the open-ended applicability revision
turn a current Sede download into unbounded technical-layout authority.

`W04.P07.S97` remains open to turn that scoped acquisition into the single
canonical typed source-artifact taxonomy and machine-filing predicate. It must
persist the distinct 2023 and 2024 contract-package inventories and their exact
member/package hashes, bind each to the law-selected revision and filing
context, and refuse a package whose scope does not match that selection. This
reference records a future obligation, not an enrolled source fact.

`W02.P04.S27` must enroll the source/casilla remedy in
`2026-08-22-source-casilla-integration-plan`: replace the seven-field partial
surface with the complete, source-grounded message grammar, including repeated
detail identity and every taxpayer, custodian, currency, valuation, and
condition branch. It must give each non-casilla fact one existing canonical
owner or approve a new provenance-carrying owner; generic producer keys may be
reused only after their constraints actually cover the AEAT field.

`W02.P04.S28` must enroll the export remedy in
`2026-08-10-aeat-export-fragment-generator-authority-plan`: after an accepted
architecture decision on the new SOAP/XML wire shape, extend the existing
canonical filing exporter and proof path. It must use the hash-pinned XSD/WSDL,
produce the appropriate local request XML, validate it against the official
schema, retain deterministic generation provenance, and prove the local emitted
payload. A remote call, client certificate, response acceptance, CSV, or filing
receipt is outside this registry/export work and must not be fabricated as
proof.

Reconsider filing grade only when every selected exercise has an exact,
immutable technical schema; the complete field and source-owner surface is
reviewed; an approved canonical serializer validates against the official XSD;
and the derived local XML has live generation and emitted-payload proof. That
means S97--S99 must have completed the separate 2023 and 2024 contract-package
inventory, canonical export, and proof work; until then the revision remains
applicability-only and non-fileable.

## Sources

- BOE-A-2023-17429, Orden HFP/886/2023, articles 1, 5, 6, final provision,
  and annex, retrieved 2026-08-24:
  https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-17429
- BOE-A-2024-27528, article 9, final provision, and annex I, retrieved
  2026-08-24:
  https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-27528
- AEAT Modelo 721 procedure and its technical-document catalogue, retrieved
  2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI55.shtml
- AEAT Modelo 721 web-service description, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/GI55/2024/Mod721_Descripcion_SWeb-2024.pdf
- AEAT Modelo 721 FAQ on XML presentation by external programs, retrieved
  2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/declaraciones-informativas/modelo-721-decla-sobre-monedas-extranjero/preguntas-frecuentes-sobre-modelo-721/que-informacion-debe-suministrarse-modelo-721.html
- `src/cadrumo/_data/registry/aeat/legal/monedas-virtuales.toml`
- `src/cadrumo/_data/registry/aeat/modelos/721/revisions/2023-y-siguientes/`
- `src/cadrumo/core/_export_layout_format.py`
- `src/cadrumo/application/filing/_export_xml_dictionary.py`
- `src/cadrumo/core/_filing_producer_key.py`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_721_registry.py`
- `2026-08-14-registry-temporal-coverage-plan`
- `2026-08-22-source-casilla-integration-plan`
- `2026-08-10-aeat-export-fragment-generator-authority-plan`
