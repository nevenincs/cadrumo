---
tags:
  - '#research'
  - '#export-parity'
date: '2026-11-01'
modified: '2026-11-01'
body_schema: 'body-v2'
body_hash: 'sha256:c1a91ea62128cb795f05f39881d306e5d58b37d06159c399003ec8fc1d27cd51'
related:
  - "[[2026-09-27-export-parity-renta-withholding-sources-adr]]"
---

# `export-parity` research: `datos-fiscales-format`

Question: in what official format does AEAT deliver a taxpayer's IRPF datos fiscales, and has AEAT published a record design or schema that would let Cadrumo build the parser that export-parity ADR Step 6 pins "to the official download format"? Plan Steps `P06.S23`, `P06.S24` and `P06.S10` depend on the answer. The evidence shows two official delivery shapes. The first is an authenticated HTML consultation with a "Generar PDF" print. The second is a "fichero DFP o DF" that the datos fiscales procedure produces and that Renta Web consumes. AEAT publishes a value dictionary for the concepts and claves in that file. It publishes no positional layout, no schema and no encoding for it, and none of the PDF view either. The Modelo 100 record-design page lists only the declaration's dictionaries and XSD. A parser pinned to an official published design therefore cannot be built now, and a synthetic specimen cannot be authored from a design, because no such design exists. Any pin has to come from an operator-supplied, redacted specimen.

## Findings

### Legal basis: the orden grants access but names no format

- Orden HAC/242/2025, art. 5.2, lets taxpayers obtain the borrador and the datos fiscales electronically from 2 April 2025, "a través del Servicio de tramitación del borrador/declaración" at the Sede. Art. 5.3 says that failing to obtain them does not relieve the filing obligation. The article names no file format, record design or schema (`src/cadrumo/_data/corpus/normatives/html/orden-hac-242-2025.html.extracted.md:51-56`). Art. 9 (line 101) makes only the latest reference number valid for access to the borrador or the datos fiscales (`:101`).
- The registry cites this orden only for arts. 3 and 8 (`src/cadrumo/_data/registry/aeat/legal/irpf.toml:5637`, `:5657`). Lines 51-55 of `irpf.toml` hold the RIRPF art. 14 entry, not art. 5 of the orden. No registry legal key exists for art. 5.
- The 2025 Renta manual repeats the access rule for campaign 2025 (8 April to 30 June 2026). It names a separate Sede trámite, "Datos fiscales", and the APP-AEAT mobile view, and it describes no file format (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:1375-1438`). This is consistent with the earlier research's "What AEAT prefills" finding (`2026-09-27-export-parity-renta-withholding-sources-research`).

### Format 1: consultation view with a PDF print

- Who and how: the taxpayer, or a representative acting by certificate, authenticates with Cl@ve Móvil, a certificate or DNIe ("en nombre propio o como representante"), DNI or NIE plus a reference number, or eIDAS. The trámite is "Consulta de datos fiscales <ejercicio>". Earlier years sit under the Modelo 100 trámites, "Ejercicios anteriores" (https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/renta-ayuda-tecnica/renta-2023/consulta-datos-fiscales-2023.html).
- Structure: an index of the concepts for which data exist. Each concept expands to its detail, and a "Generar PDF" action prints the current page or every index page. APP-AEAT offers the same list (https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/renta-ayuda-tecnica/servicios-app/datos-fiscales.html). Neither help page lists per-payer columns. The PDF is a rendering of the HTML view, and AEAT publishes no layout, field list or stability promise for it.
- UNVERIFIED (general knowledge, not checked here): the trabajo and actividad entries show payer NIF and name, clave, dinerarias and especie amounts, retenciones and ingresos a cuenta. Pagos fraccionados appear per Modelo 130 or 131 period. Only a specimen can confirm these columns.

### Format 2: the "fichero DFP o DF" consumed by Renta Web

- The 2025 Renta Web presentation manual, section 6.1, states that a Renta Web declaration "parte de la existencia de un fichero de datos fiscales y personales". The declarant can be the holder only with a "fichero DFP o DF". Downloading it requires a certificate or DNIe, Cl@ve PIN, or a reference number for the ejercicio. The procedure "concluye con la descarga de un fichero DFP o DF", whose contents are refreshed during the campaign. The page names no format, encoding, encryption or design (https://sede.agenciatributaria.gob.es/Sede/Ayuda/25Presentacion/100/6_1.html).
- AEAT's technical library holds "Renta WEB 2022 - Instrucciones para la incorporación de datos fiscales y personales" (AEAT, PDF of 20 April 2023, 108 pages; https://www3.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Tecnicos/Renta/2022/R2022df.pdf). It is the closest thing to a published design, and it is semantic only:
  - Section 2 sorts concepts into four groups by how Renta Web treats them: incorporated without display, incorporated optionally, displayed only with a note, and note only. For example, pagos fraccionados are always incorporated, "ingresos y aplazamientos", while activity income is not (pp. 6-17).
  - Section 3 names the record families by two- or three-letter codes, for example RTA trabajo, RTC actividades económicas, REA and REG explicit capital mobiliario, LT, RI, CT autónomo contributions, PHD mortgages, UR catastro and PF pagos fraccionados (pp. 35-84).
  - Section 4, "Traducción de las claves", enumerates 64 value vocabularies. Examples are the trabajo claves A, B1-B3, C, E1-E4 and F1-F2, which mirror the Modelo 190 perceptor claves; the activity claves G1-G3 and H1-H2; the attribution-entity retention subclaves (item 33); and the pagos fraccionados statuses I, N, C, D, F, A, M, S, E, G and V (item 40, p. 102).
  - Nowhere does it give record positions, lengths, separators, character set, record-type identifiers, a per-payer field order, a checksum, a signature or encryption. A text search for "posición", "longitud", "XML" and "formato" finds none.
- The same document exists for 2016 (67 pages, 23 May 2017), with the same opening DFP/DF paragraph and its own pagos fraccionados claves list (https://sede.agenciatributaria.gob.es/static_files/Sede/Renta_ejercicios_anteriores/2016/DatosFisc/R2016df.pdf). Search also surfaces a 2021 edition (https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Tecnicos/Renta/2021/Instrucciones_renta_2021.pdf, not read). The guessed 2025 path `.../Tecnicos/Renta/2025/R2025df.pdf` returned HTTP 404 on 2026-11-01. No 2023, 2024 or 2025 edition was found.
- Stability: across 2016 and 2022 the concept-family and claves structure persists while the claves lists grow, from about 52 numbered items in 2016 to 64 in 2022. Nothing shows the byte format to be stable. The documents never describe it, and the claves change with the Modelo 190 and other informative designs every year.
- Whether a current Renta Web user can save the DFP or DF file to disk, or whether it now exists only server-side within the session, is not established by any page read. The wording "descarga" is retained from the PADRE era. UNVERIFIED either way.

### No published record design or schema

- The official Modelo 100 record-design page lists only "Diccionario declaración individual", "Diccionario ... (toma de datos)" and "Esquema XSD" for ejercicio 2025. It has no entry for datos fiscales, DFP or borrador (https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html, fetched 2026-11-01). The in-repo snapshot agrees: 29 artefacts, all declaration designs (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/manifest.json:1-20`).
- The only "datos fiscales" strings in the in-repo designs are request flags inside the declaration itself, such as "Borrador ... o datos fiscales 2015. Obtener tributación individual" (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/19-100-ejercicio-2014-417-kb-pdf.pdf.extracted.md:390`, likewise `14-100-ejercicio-2009-205-kb-pdf.pdf.extracted.md:332-334`). They do not describe the datos fiscales file.
- No public AEAT developer documentation for a datos fiscales web service for third-party software was found. Commercial products advertise importing datos fiscales, for example the Wolters Kluwer a3asesor Ren product sheet (https://assets.contenthub.wolterskluwer.com/api/public/content/2411621-ficha-producto-a3asesor-ren-d74afcf279). That is third-party and UNVERIFIED as to mechanism, and it presumably runs on colaboración social channels that are not public. Impuesto sobre Sociedades datos fiscales are explicitly online-only, with no printable or downloadable format (https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/impuesto-sobre-sociedades-ayuda-tecnica/consulta-datos-fiscales-sociedades.html). That page is a contrast case, not IRPF evidence.

### What this means for the parser and plan Steps

- The repo pins other inbound formats to published designs, or, failing that, refuses. The censal certificate parser refuses every PDF until a specimen pins the layout (`src/cadrumo/adapters/inbound/censo/parser.py:25-41`). For datos fiscales, the published R20xxdf vocabularies can ground the semantic mapping: RTA claves to trabajo and 0596, RTC G and H claves to actividad and 0599, capital-mobiliario families to 0597, PF to 0604, and the attribution subclaves. They cannot ground byte or page geometry, so a synthetic specimen authored from them would encode Cadrumo's guess and fall under the oracle discipline's ban on self-derived expectations.
- Candidate pins, as evidence for the ADR amendment rather than a choice:
  - The "Generar PDF" print of the consulta. It is user-obtainable today and is the realistic manual-import artefact, but its layout is unpublished and may shift each campaign.
  - The DFP or DF file. It is the machine-readable form Renta Web consumes, but its obtainability by the taxpayer is unverified and its encoding is unpublished.
  - The live HTML consultation. It is reachable only through `P06.S10`'s attended live session.
- For a specimen, the operator must supply, for one named ejercicio (2025 preferred), one of: the "Generar PDF" output of "Consulta de datos fiscales" with "Todas las páginas del índice", or, if Renta Web or the trámite actually offers it, the saved DFP or DF file. The specimen must cover at least one trabajo payer, one actividad profesional payer (clave G), one capital-mobiliario payer and one pagos fraccionados row. Before the file enters the repo, every NIF, name, address, reference number, CSV and amount must be replaced with synthetic values that keep geometry and claves. The operator should also state the campaign date it was obtained and the exact Sede path used.
- `P06.S23` (pinned parser, record and namespaces): the record type, the encrypted namespaces and a parser that refuses everything, on the censal precedent, are buildable now. Pinned extraction waits for the specimen, and the parser must key its pin to the ejercicio and refuse other years.
- `P06.S24` (manual import with identity refusal and content-addressed capture): the CLI, identity refusal, digest-keyed capture and idempotency are buildable against the refusing parser. End-to-end acceptance waits for the specimen.
- `P06.S10` (read-only live pull): already gated on the live-write guard and an attended session (`.vault/plan/2026-11-01-export-parity-plan.md:251`). That session is also the earliest moment the HTML view's structure can be observed. Its capture must likewise be redacted before any fixture is derived from it.
- Not investigated: the Renta Web client code or network traffic, which would be an authenticated service and is out of bounds; editions for 2023 to 2025 of the incorporation instructions beyond the 404 probe; the 2021 edition's contents; and the colaboración social channels.

## Sources

- `src/cadrumo/_data/corpus/normatives/html/orden-hac-242-2025.html.extracted.md:51-56`, `:101`
- `src/cadrumo/_data/registry/aeat/legal/irpf.toml:51-55`, `:5637`, `:5657`
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:1375-1438`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/manifest.json:1-20`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/19-100-ejercicio-2014-417-kb-pdf.pdf.extracted.md:390`
- `src/cadrumo/adapters/inbound/censo/parser.py:25-41`
- `.vault/plan/2026-11-01-export-parity-plan.md:236-239`, `:251`
- https://sede.agenciatributaria.gob.es/Sede/Ayuda/25Presentacion/100/6_1.html (fetched 2026-11-01)
- https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/renta-ayuda-tecnica/renta-2023/consulta-datos-fiscales-2023.html (fetched 2026-11-01)
- https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/renta-ayuda-tecnica/servicios-app/datos-fiscales.html (fetched 2026-11-01)
- https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html (fetched 2026-11-01)
- https://www3.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Tecnicos/Renta/2022/R2022df.pdf (fetched 2026-11-01; pdfinfo title "INSTRUCCIONES PARA LA INCORPORACIÓN DE DATOS FISCALES", created 2023-04-20)
- https://sede.agenciatributaria.gob.es/static_files/Sede/Renta_ejercicios_anteriores/2016/DatosFisc/R2016df.pdf (fetched 2026-11-01)
- https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Tecnicos/Renta/2021/Instrucciones_renta_2021.pdf (search result only, not read)
- https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/impuesto-sobre-sociedades-ayuda-tecnica/consulta-datos-fiscales-sociedades.html (search-result summary only; contrast case)
- https://assets.contenthub.wolterskluwer.com/api/public/content/2411621-ficha-producto-a3asesor-ren-d74afcf279 (third party, UNVERIFIED)
- Per-payer columns of the consultation view: general knowledge, UNVERIFIED
