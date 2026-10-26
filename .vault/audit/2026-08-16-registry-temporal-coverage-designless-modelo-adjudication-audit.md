---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:2181e27dad392947c2f0756658af1028619adb14d9b4e2ce829ee73ddf84ef46'
related:
  - "[[2026-08-15-registry-temporal-coverage-legal-grounding-consolidation-audit]]"
  - "[[2026-08-15-registry-temporal-coverage-structural-decisions-audit]]"
---

# `registry-temporal-coverage` audit: `designless modelo adjudication`

## Scope

Every registry revision refused by `validate_export_exemption_declarations` with
"declares no export layout" — 48 revisions across 45 modelos, enumerated from a
real authority load, not from a carried-forward list. For each, a verdict:
implement, or retire.

This closes the item the legal-grounding consolidation audit left open under
`operator-layout-decision`, which named the decisive action as "a direct AEAT
Diseño de Registro index check per modelo number". That check was performed here
against all five live AEAT index pages plus all four `ejercicios anteriores`
pages.

The starting premise under review was an operator worklist marking eleven
modelos (038, 182, 185, 187, 188, 193, 194, 296, 308, 309, 347) as "NO FACTS TO
WRITE". That premise is refuted for all eleven; the detail is below.

## Findings

### premise-refuted-facts-are-bundled | high | All eleven modelos marked "no facts to write" have a bundled, parsed, authoring-grade record design

The bundled `disenos_registro/` corpus holds a source design for every one of the
eleven, each with a committed `.extracted.json` sidecar — 218 sidecars against
216 source files tree-wide, so extraction coverage is complete, and no network
fetch is involved in reading any of them. Running the production
`extract_record_design` facade over each yields typed positions, not prose:

| modelo | source | sheets | fields |
|---|---|---|---|
| 038 | pdf | 2 | 58 |
| 182 | pdf | 2 | 38 |
| 185 | pdf | 2 | 35 |
| 187 | pdf | 2 | 56 |
| 188 | pdf | 2 | 43 |
| 193 | pdf | 3 | 69 |
| 194 | pdf | 2 | 41 |
| 296 | pdf | 2 | 30 |
| 308 | xls | 2 | 68 |
| 309 | xls | 2 | 81 |
| 347 | pdf | 3 | 64 |

Field records carry `offset`, `length`, `type_code`, `description` and the
declared constant or validation note — for 182's declarante NIF, the full
Reglamento General citation and the right-justified control-character rule. This
is the same shape the authored modelos were built from.

**The decisive control is Modelo 180.** It is an informativa, its only design is
a PDF of the identical "POSICIONES / NATURALEZA / DESCRIPCIÓN DE LOS CAMPOS"
shape, it parses to **32 fields — fewer than every modelo in the table above bar
296** and it is fully authored: a two-record fixed-width layout
(declarante + perceptor), 27 casillas on the `cdecl.*`/`cperc.*` convention,
formulas, continuidad evolutions and a `workbook_parity_refs` entry pointing at
that PDF. Modelo 182's stub already carries casillas on that same
`cdecl.`/`ctipo2.` convention, so the route was entered and abandoned, not found
impassable.

"No facts to write" is therefore not a property of these designs. What is true of
the eight informativas in the group is narrower and worth stating precisely:
their content is **detail-record rows** (Tipo 1 declarante + Tipo 2
perceptor/declarado/operación), not M303-style computed casillas. That changes
the authoring shape, not its feasibility, and the repository already models it —
`detail_record` is an established binding family, and the
`test_an_exporting_family_declares_every_drawable_field[donativo_donor]`
parametrisation is Modelo 182's own donor family, already enrolled.

### modelo-038-is-live-not-retired | high | AEAT publishes 038's record design on its CURRENT index, updated 28/06/2024

The worklist recorded 038 as "depreciated ... not fileable". Direct check of
`sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-01-99.html`
— the **current-year** index, not `ejercicios anteriores` — lists Modelo 038 with
"Orden HAC/66/2002, de 15 de enero (actualizado a 28/06/2024)". The registry's
own manifest already cites `orden-hac-66-2002`, and the bundle already holds that
exact file. A tax authority does not reissue a suppressed form's record design.
**Verdict: implement.**

One real caveat separates 038 from its ten neighbours. Its design is a
**graphical byte-ruler PDF**, not a field table, and the extractor says so:
every field carries `type_code = "No consta en gráfico"` and
`content = "Extracted from visual record-design chart geometry."` Offsets and
lengths are recovered soundly, but the descriptions bleed — field 5 reads
"MODELO REGISTRO DE TIPO REGISTRO DE DECLARANTE DENOMINACIÓN O RAZÓN SOCIAL DEL
DECLARANTE", field 6 of the Tipo 2 sheet reads bare "REGISTRO DE TIPO". So 038 is
implementable but its extraction is **positionally trustworthy and semantically
unreliable**; naming its fields requires reading the PDF, not trusting the
sidecar. That is a distinct and weaker evidence class from the other ten and
must not be collapsed into them.

### retirement-requires-legal-suppression | high | Only one of the 48 revisions qualifies for retirement, and it is not one the worklist named

The repository has exactly one retirement precedent, and it fixes the meaning of
the word: `Modelo.M037` sits in `NON_REGISTRY_MODELOS` because it was
**suppressed by Orden HAC/1526/2024** — the form ceased to exist in law. Its
docstring is explicit that these are "known modelos ... which have no registry
definition by design".

Retirement is therefore grounded in the form's legal death, never in "this
application cannot file it". Measured against that bar, of the 45 modelos behind
the 48 refusals, **44 are live AEAT forms** and do not qualify. The single
qualifying case is one the worklist did not raise:

**Modelo 179 — retire.** The obligation to file 179 (cesión de uso de viviendas
con fines turísticos) was abolished for ejercicio 2024 onwards and replaced by
Modelo 238 (DAC7 platform-operator reporting). Its AEAT procedure page (GI44)
confirms the modelo "is no longer in effect" for new periods. The registry
carries it as an open-ended `2021-y-siguientes` revision, which is a factual
error independent of any layout question: the span must be bounded at the last
live ejercicio. This is a registry-data correction to make regardless of what is
decided about the gate.

### seventeen-modelos-have-no-published-design-anywhere | high | AEAT publishes no record design for 17 modelos, confirmed against both the live and the historical index

These 17 have zero bundled design files: 121, 136, 140, 143, 179, 186, 231, 233,
234, 238, 289, 361, 379, 380, 592, 721, 848. The prior audit could class only 7
as "layout probably exists" and left **10 explicitly undecidable**, correctly
refusing to read excerpt-absence as law-absence.

Direct index check closes all 17 in one direction. **None of the seventeen
appears on any of AEAT's four current Diseño de Registro range pages (01-99,
100-199, 200-299, 300-399, resto), nor on any of the four `ejercicios anteriores`
pages.** Every other modelo in this campaign does appear — 182, 185, 187, 188,
193, 194 on the 100-199 page; 296 on 200-299; 308, 309, 347 on 300-399; 763, 840
on resto; 038 on 01-99. The instrument demonstrably resolves positives, so its
negatives carry weight.

This does **not** retire them, because they are live forms. It reclassifies the
blocker: not missing evidence to acquire, but **a filing channel that is not
fixed-width at all**. Positive channel confirmation, by evidence class:

- **XML / SOAP web service, directly confirmed.** M231 — its bundled procedure
  page states "la vía principal para la presentación del modelo 231 es mediante
  servicio web ... también se ha habilitado la presentación del xml". M379 — "la
  presentación del modelo 379 se puede realizar mediante servicio web". M238 —
  AEAT ships a `DPI-DAC7-Presentacion-238-SWeb` manual; messages are "based on
  the native XML design of the EU Commission and OECD", validated as XML with
  SoapFault errors. M289 — already ruled in the structural-decisions audit,
  bundled as an XSD + WSDL zip at `layout_authority` tier. M179 — web form plus
  web service with WSDL, no fichero route.
- **XML web service, by family analogy only.** M234 (DAC6 mecanismos
  transfronterizos) sits in the same EU-directive reporting family as 238/289 and
  was not individually confirmed here.
- **Web form only, directly confirmed.** M380 — procedure page DB06 lists
  presentation, consulta and requerimiento options with no fichero route, and the
  modelo remains in force. M592 — procedure page DR14 lists only "presentación de
  la autoliquidación" and its complementaria, no fichero route. M361 — its
  bundled procedure page shows "presentación del modelo 360 por fichero" for its
  parent while 361 itself is only "alta de solicitudes", consistent with the
  earlier ten-index-page verification that it has no design of its own.
- **Not a taxpayer filing.** M186 (nacimientos y defunciones) is sourced from the
  Registros Civiles. Its sole bundled artefact is a single PNG image of Anexo I
  Tipo 1 — `01-186-anexo-i-tipo1-nacimientos.png`, with no text layer, which is
  why it parsed to zero fields here and why the earlier lane recorded it
  truncated at position 34 of 320.
- **Index-absence only, channel not individually confirmed.** M121, M136, M140,
  M143, M233, M721, M848. Six of these are IRPF advance-payment or communication
  forms filed by an individual (121, 136, 140, 143, 848) or a small informativa
  (233, 721), where a fichero route would be unusual — but that is inference, and
  it is recorded as inference.

### the-gate-admits-no-retire-verdict | high | The refusal the worklist is trying to answer has no sanctioned answer short of deletion

`validate_export_exemption_declarations` states its posture without hedging:
"There is no allowance, no allowlist and no per-modelo exemption; a modelo the
application cannot file is a capability still to build, never a settled state."
That is a deliberate design decision and it is the right default — the mechanism
it replaced returned early on exactly this condition, so the refusal was quietest
where the gap was largest.

The consequence is structural, and it is the real blocker under this whole
worklist: **for the 17 modelos above there is no way to record the true verdict.**
The honest statement is "AEAT publishes no fixed-width design for this modelo; it
is filed by web form or XML web service" — and the registry has no vocabulary for
it. The only currently-available action that clears the refusal is deleting the
registry definition and enrolling the modelo in `NON_REGISTRY_MODELOS`, which
would assert the form does not exist. For 44 live forms that assertion is false.

So the instruction "retire or fully implement" is, for these 17, not satisfiable
as posed: implementation is blocked on a channel the export format vocabulary
does not model, and retirement would require stating something untrue. This needs
a ruling, not an authoring pass, and no allowlist should be added in the
meantime — routing around this gate is precisely what it was built to prevent.

### two-classes-not-one | medium | The 48 refusals are two populations with opposite remedies, and the count conflates them

31 of the 48 revisions have a bundled, parsed design and are blocked only on
authoring effort. 17 have no design because none exists to have. Reported as one
number, the worklist reads as 48 units of the same work; it is not. The 31,
with parsed field counts, are: 036 (1047 fields), 038 (58), 151 (727), 182 (38),
184 (132), 185 ×2 (35), 187 (56), 188 (43), 193 (69), 194 (41), 200 (6808),
202 ×3 (116), 210 (167), 220 (16720), 222 (136), 232 ×2 (263), 296 (68), 303
(430), 308 (68), 309 (81), 322 (255), 347 (69), 353 ×2 (156), 360 (160), 763
(201), 840 (216).

Two observations sharpen the ordering. Modelo 303's refusal is against its
`2009-y-siguientes` revision, not its live one — an old revision inside a modelo
that is otherwise the most heavily authored in the tree, so it is a
span-hygiene item rather than a capability gap, and the same shape applies to
322's and 353's `…-2025` revisions. And 308 and 309 are workbook designs in the
identical `Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido`
tabular format as Modelo 131's, which is fully authored across four revisions —
so those two are the cheapest genuine implementations in the entire set, not the
hardest.

## Recommendations

### implement-the-thirty-one | Author from the bundled designs, cheapest-first

Nothing external is needed for any of the 31. Suggested order: 308 and 309 first
(workbook designs, direct structural analogue in the authored Modelo 131), then
the informativa group 182, 185, 187, 188, 193, 194, 296, 347 against the Modelo
180 template, then 038 last of the small set — its byte-ruler extraction needs
the PDF read by hand for field naming, so it should not lead. The large designs
(200, 220, 036, 151) are separate efforts sized by their field counts, not by
this worklist.

### correct-modelo-179-span | Bound the revision at the last live ejercicio

Independent of any gate decision: 179's `2021-y-siguientes` revision is factually
wrong now that the obligation was abolished for 2024 onwards in favour of Modelo
238. Bound the span and record the successor. This is the one retirement in the
set that meets the `Modelo.M037` bar.

### operator-decision-on-non-fixed-width-channels | The ruling this audit cannot make

An ADR must decide how the registry records a live modelo AEAT publishes no
fixed-width design for. Three shapes are visible and the choice is not
mechanical: extend `ExportLayoutFormat` with a web-service/XSD member (which the
structural-decisions audit already showed is not a small change, since the
existing `xml_dictionary` renderer branches on `draft.modelo == Modelo.M100` at
four points, so it is Modelo 100's format with a general name); or add a declared,
evidence-bearing "no published fixed-width design" state that
`validate_export_exemption_declarations` accepts, carrying the AEAT index
citation as its grounding; or rule that these modelos are out of product scope
and remove them, which requires accepting that `NON_REGISTRY_MODELOS` would then
mean two different things. The evidence class this audit produced — a direct,
reproducible AEAT index check resolving positives and negatives — is what the
second option would need to be honest rather than an allowlist by another name.

### do-not-add-an-allowlist | Standing constraint on whoever executes the above

Until that ADR lands, the 17 refusals stay red. They are an accurate report of a
real capability gap, and the gate's own docstring anticipates exactly the
pressure to silence them.
