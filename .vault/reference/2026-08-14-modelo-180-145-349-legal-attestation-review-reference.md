---
tags:
  - '#reference'
  - '#modelo-180-145-349-legal-attestation-review'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:ead6e2214910d367aa0f10281235ed06ceea85869d76afce236edb8988807c2f'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-14-registry-campaign-sequencing-operator-attestation-ledger-audit]]"
---

# `modelo-180-145-349-legal-attestation-review` reference: `Modelo 180, 145 and 349 legal-reference attestation review packet`

This packet exists to make fifteen personal legal attestations a bounded,
reviewable act instead of fifteen bare identifiers, across three modelos:
Modelo 180 (2 references, shared across both its revisions, `2019-2022` and
`2023-y-siguientes`), Modelo 145 (4 references, its one revision
`2012-01-31-y-siguientes`), and Modelo 349 (9 references, its one revision
`2020-y-siguientes`). All fifteen are currently at `agent_reviewed`, computed
from the bundled registry's own revision snapshots (`_collect_snapshot_ref_ids`
against `bundled_authority()`), not by grep -- so this is the exact slice each
revision's snapshot build checks.

Two of the fifteen references, `ley-35-2006:art-99` and `rd-439-2007:art-100`,
are also cited by Modelo 100's much larger legal-reference tranche.
Attesting them here clears them for Modelo 100 as well, since a legal
reference's `operator_reviewed` stamp is one stamp shared tree-wide across
every modelo and revision that cites it -- it is not modelo-scoped.

For each reference this packet places the registry's own claim next to the
actual bundled corpus text it points at, quoted verbatim, and lists what in
the citing revision(s) depends on it. It does not state whether the claim and
the source agree -- that is the operator's act, and stating it here would turn
the operator's sign-off into a rubber stamp on agent work. The one exception is
a structural discrepancy: a broken `corpus_ref`, a `required_text` phrase
absent from the quoted text, or a citation that plainly names a different
subject. None of the fifteen references below triggered that exception; each
`corpus_ref` resolved and each declared `required_text` phrase is present in
the quoted text (the production check normalises case, diacritics and
whitespace before comparing -- `cadrumo.core.normalise_corpus_text` -- so a
sentence-initial capital in the corpus against a lower-case `required_text`
transcription is not a mismatch). That is reported as a mechanical fact --
text is present or absent -- and is not a judgement that the provision legally
supports what the casilla, binding, formula or construct claims about it.

**Standing caveat on the `notes` field.** Every `notes` value quoted in this
packet is agent-authored registry content, not operator-verified prose. Where
a note asserts that the bundled text was already checked against a live BOE
or AEAT source, that assertion is itself an unverified agent claim, carrying
exactly the same weight as any other agent claim in this packet -- it is not
independent confirmation, and it may have been written by the same agent that
authored the entry it purports to validate. That is the same shape as a
`required_text` cross-check that passes because one author wrote both the
excerpt and the phrase validating it: self-attesting and unfalsifiable from
inside the packet. None of the fifteen entries below carry that
self-verification shape in their own `notes` -- it does not recur from the
Modelo 390 packet's `art-69`/`art-70` entries, which are not part of this
worklist. This caveat is stated here as a standing practice for every packet
in this attestation series, not because it fires in this one.

**Numeric grounding flag.** Per project rule, the bundled corpus text is
preferred evidence but not infallible on numbers: for any reference
establishing a rate, amount or threshold, a live BOE or AEAT consolidated-text
cross-check is the operator's to make -- no such fetch was performed here.
Unlike the Modelo 390 packet, where this flag did not apply to any of the ten
references, it applies here: these are IRPF/retenciones and IVA-recapitulativa
provisions and five of the fifteen state a numeric figure. Each is called out
explicitly in its own section below, not left to be discovered by reading the
quoted text:

- `rd-439-2007:art-100` -- the 19 percent withholding rate on arrendamiento
  urbano rents, and the 60 percent Ceuta/Melilla reduction of that rate.
- `rd-439-2007:art-88` -- the 33.007,2 euros annual-retribution ceiling
  gating the vivienda-habitual retention-reduction communication.
- `resolucion-dgt-2013-12-17-modelo-145:amendment` -- the same 33.007,20 euros
  ceiling, restated in the Modelo 145 form-content resolution.
- `rd-1624-1992:art-81` -- the 50.000 euros quarterly-volume threshold that
  decides quarterly versus monthly recapitulativa cadence.
- `ley-37-1992:art-80` -- the 50 euros minor-credit floor and the
  6.010.121,04 euros volumen-de-operaciones ceiling inside the
  base-imponible-modification bad-debt procedure.

The remaining ten references state no numeric rate, amount or threshold.

This document is read-only working material. No `operator_reviewed` stamp was
applied or could be applied through any path available to this session, and
nothing under `modelos/180/**`, `modelos/145/**` or `modelos/349/**` was
touched to produce it.

## Summary

Fifteen sections follow, grouped by modelo: Modelo 180
(`ley-35-2006:art-99`, `rd-439-2007:art-100`), Modelo 145
(`rd-439-2007:art-88`, `resolucion-dgt-2011-01-03-modelo-145:aprobacion`,
`resolucion-dgt-2013-12-17-modelo-145:amendment`,
`resolucion-dgt-2014-12-18-modelo-145:amendment`), Modelo 349
(`ley-37-1992:art-27`, `art-69`, `art-70`, `art-80`, `art-86`, `art-9-bis`,
`rd-1624-1992:art-79`, `art-80`, `art-81`). Each section carries the same four
parts in the same order: the registry's current entry, the bundled corpus text
quoted verbatim, what depends on it in the citing revision(s), and the entry's
current review status.

## Modelo 180

### 1. `ley-35-2006:art-99` -- Obligación de practicar pagos a cuenta

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a99`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2016-01-01
- `required_text`:
  - "Obligación de practicar pagos a cuenta"
  - "tendrán la consideración de deuda tributaria"
  - "Retenciones."
  - "Ingresos a cuenta."
  - "Pagos fraccionados."
  - "estarán obligadas a practicar retención e ingreso a cuenta"
  - "estarán obligados a efectuar pagos fraccionados a cuenta"
- `notes` (verbatim): "LIRPF art 99: obligacion general de practicar pagos a cuenta del IRPF. Define los pagos a cuenta como retenciones, ingresos a cuenta y pagos fraccionados; obliga a retenedores/pagadores a practicar retencion e ingreso a cuenta; y obliga a contribuyentes con actividades economicas a efectuar pagos fraccionados."

#### Bundled corpus text (verbatim, from the anchored `#a99` unit)

> Artículo 99. Obligación de practicar pagos a cuenta.
>
> 1. En el Impuesto sobre la Renta de las Personas Físicas, los pagos a cuenta
> que, en todo caso, tendrán la consideración de deuda tributaria, podrán
> consistir en: a) Retenciones. b) Ingresos a cuenta. c) Pagos fraccionados.
>
> 2. Las entidades y las personas jurídicas [...] que satisfagan o abonen
> rentas sujetas a este impuesto, estarán obligadas a practicar retención e
> ingreso a cuenta, en concepto de pago a cuenta del Impuesto sobre la Renta
> de las Personas Físicas correspondiente al perceptor [...]. Estarán
> sujetos a las mismas obligaciones los contribuyentes por este impuesto que
> ejerzan actividades económicas respecto a las rentas que satisfagan o
> abonen en el ejercicio de dichas actividades [...].
>
> [Apartados 3 through 6 -- exemptions from retention on Letras del Tesoro
> and prima de emisión, the retenedor's Treasury-payment obligation, and the
> perceptor's computation and deduction rules when retention was omitted or
> under-practised -- present in full in the bundled file.]
>
> 7. Los contribuyentes que ejerzan actividades económicas estarán obligados
> a efectuar pagos fraccionados a cuenta del Impuesto sobre la Renta de las
> Personas Físicas, autoliquidando e ingresando su importe en las
> condiciones que reglamentariamente se determinen. [...]
>
> [Apartados 8 through 11 -- change-of-residence pago-a-cuenta treatment,
> impatriate worker communication, judicial/administrative resolution
> retention, and the Directiva 2003/48/CE savings-income retention credit --
> present in full in the bundled file, followed by BOE amendment-history
> footnotes: Ley 20/2015 disposición adicional 11.1, Ley 26/2014 art. 1.63.]

Apartados 3-6 and 8-11 are elided above (`[...]`) for length; both are
present in full in the bundled file and neither elision touches a
`required_text` phrase. `corpus_ref` resolves; all seven declared
`required_text` phrases are present in the text above.

#### Modelo 180 dependents (both revisions: `2019-2022`, `2023-y-siguientes`)

Cited identically across both revisions -- AEAT re-split Modelo 180's design
epoch without changing this reference's dependent population. 36 dependents
per revision: 30 casillas covering the full declarante/perceptor/inmueble
block (`decl.base-total`, `decl.retenciones-total`, `decl.total-perceptores`,
`perc.base`, `perc.porcentaje-retencion`, `perc.retenciones`, and every
perceptor identity/inmueble-address casilla), 3 bindings
(`modelo-180-115-base-anual`, `modelo-180-115-perceptores-anual`,
`modelo-180-115-retenciones-anual`), 2 formulas (`modelo-180-base-total`,
`modelo-180-retenciones-total`), and the construct
`modelo-180-annual-summary`.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-06-28`.

### 2. `rd-439-2007:art-100` -- Importe de las retenciones sobre arrendamientos y subarrendamientos de inmuebles

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/rd-439-2007-art-100.html#a100`
- `document_id`: `BOE-A-2007-6820`; `effective_from`: 2018-12-23
- `required_text`:
  - "arrendamiento o subarrendamiento de inmuebles urbanos"
  - "19 por ciento"
  - "excluido el Impuesto sobre el Valor Añadido"
  - "se reducirá en el 60 por ciento"
- `notes` (verbatim): "RIRPF art 100: base reglamentaria del importe de las retenciones sobre arrendamientos y subarrendamientos de inmuebles urbanos. Current consolidated text sets the 19 percent withholding rate on amounts paid to the lessor, excluding IVA, and the 60 percent Ceuta/Melilla reduction."

#### Bundled corpus text (verbatim, from the anchored `#a100` unit)

> Artículo 100. Importe de las retenciones sobre arrendamientos y
> subarrendamientos de inmuebles.
>
> La retención a practicar sobre los rendimientos procedentes del
> arrendamiento o subarrendamiento de inmuebles urbanos, cualquiera que sea
> su calificación, será el resultado de aplicar el porcentaje del 19 por
> ciento sobre todos los conceptos que se satisfagan al arrendador, excluido
> el Impuesto sobre el Valor Añadido.
>
> Este porcentaje se reducirá en el 60 por ciento cuando el inmueble urbano
> esté situado en Ceuta o Melilla, en los términos previstos en el artículo
> 68.4 de la Ley del Impuesto.

`corpus_ref` resolves; all four declared `required_text` phrases are present
verbatim in the text above. The article is two short paragraphs; nothing is
elided. **Numeric flag:** this reference states the 19 percent withholding
rate and the 60 percent Ceuta/Melilla reduction directly -- see the packet
preamble.

#### Modelo 180 dependents (both revisions: `2019-2022`, `2023-y-siguientes`)

11 dependents per revision, a narrower slice than `art-99` above: 5 casillas
(`decl.base-total`, `decl.retenciones-total`, `perc.base`,
`perc.porcentaje-retencion`, `perc.retenciones`), the same 3 bindings
(`modelo-180-115-base-anual`, `modelo-180-115-perceptores-anual`,
`modelo-180-115-retenciones-anual`), the same 2 formulas
(`modelo-180-base-total`, `modelo-180-retenciones-total`), and the construct
`modelo-180-annual-summary`. This reference is specifically the base and
retention-percentage/amount casillas, not the perceptor-identity or
inmueble-address casillas `art-99` also covers.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-06-28`.

## Modelo 145

### 3. `rd-439-2007:art-88` -- Comunicación de datos del perceptor de rentas del trabajo a su pagador

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/rd-439-2007-art-88.html#a88`
- `document_id`: `BOE-A-2007-6820`; `effective_from`: 2007-04-01
- `required_text`:
  - "Comunicación de datos del perceptor de rentas del trabajo a su pagador"
  - "deberán comunicar al pagador la situación personal y familiar"
  - "El contenido de las comunicaciones se ajustará al modelo que se apruebe por Resolución"
  - "no será preciso reiterar en cada ejercicio la comunicación de datos al pagador"
- `notes` (verbatim): "RIRPF art 88: comunicacion de datos del perceptor de rentas del trabajo a su pagador. Base reglamentaria del Modelo 145: el perceptor comunica circunstancias personales y familiares al pagador, el pagador conserva la comunicacion firmada, y el contenido se ajusta al modelo aprobado por resolucion del Departamento de Gestion Tributaria de la AEAT."

#### Bundled corpus text (verbatim, from the anchored `#a88` unit)

> Artículo 88. Comunicación de datos del perceptor de rentas del trabajo a
> su pagador.
>
> 1. Los contribuyentes deberán comunicar al pagador la situación personal y
> familiar que influye en el importe excepcionado de retener, en la
> determinación del tipo de retención o en las regularizaciones de éste,
> quedando obligado asimismo el pagador a conservar la comunicación
> debidamente firmada. [...] A efectos de poder aplicar la reducción del
> tipo de retención prevista en el último párrafo del artículo 86.1 de este
> Reglamento, el contribuyente deberá comunicar al pagador que está
> destinando cantidades para la adquisición o rehabilitación de su vivienda
> habitual utilizando financiación ajena [...]. En el supuesto de que el
> contribuyente perciba rendimientos del trabajo procedentes de forma
> simultánea de dos o más pagadores, solamente podrá efectuar la
> comunicación a que se refiere el párrafo anterior cuando la cuantía total
> de las retribuciones correspondiente a todos ellos sea inferior a
> 33.007,2 euros. En el supuesto de que los rendimientos del trabajo se
> perciban de forma sucesiva de dos o más pagadores, sólo se podrá efectuar
> la comunicación cuando la cuantía total de la retribución sumada a la de
> los pagadores anteriores sea inferior a 33.007,2 euros. [...] El
> contenido de las comunicaciones se ajustará al modelo que se apruebe por
> Resolución del Departamento de Gestión Tributaria de la Agencia Estatal
> de Administración Tributaria.
>
> 2. La falta de comunicación al pagador de estas circunstancias personales
> y familiares o de su variación, determinará que aquél aplique el tipo de
> retención correspondiente sin tener en cuenta dichas circunstancias [...].
>
> 3. La comunicación de datos a la que se refiere el apartado anterior
> deberá efectuarse con anterioridad al día primero de cada año natural o
> del inicio de la relación [...]. No será preciso reiterar en cada
> ejercicio la comunicación de datos al pagador, en tanto no varíen las
> circunstancias personales y familiares del contribuyente. [...] No será
> preciso reiterar en cada ejercicio la comunicación en tanto no se
> produzcan variaciones en los datos inicialmente comunicados.
>
> 4. Las variaciones en las circunstancias personales y familiares que se
> produzcan durante el año [...] podrán ser comunicadas a efectos de la
> regularización prevista en el artículo 87 del presente Reglamento [...].
>
> 5. Los contribuyentes podrán solicitar en cualquier momento de sus
> correspondientes pagadores la aplicación de tipos de retención superiores
> a los que resulten de lo previsto en los artículos anteriores, con
> arreglo a las siguientes normas: a) La solicitud se realizará por escrito
> ante los pagadores [...]. b) El nuevo tipo de retención solicitado se
> aplicará, como mínimo hasta el final del año [...].

Portions of apartados 1-5 (procedural detail not touching a `required_text`
phrase, such as the ten-day communication deadline and the five-day payroll
cutoff) are elided above (`[...]`) for length; present in full in the bundled
file. `corpus_ref` resolves; all four declared `required_text` phrases are
present in the text above. **Numeric flag:** apartado 1 states the
33.007,2 euros annual-retribution ceiling twice, gating eligibility to
communicate the vivienda-habitual retention reduction -- see the packet
preamble.

#### Modelo 145 dependents (revision `2012-01-31-y-siguientes`)

56 casillas -- every declarative field on the Modelo 145 comunicación:
`perceptor.nif`, `perceptor.nombre`, `perceptor.situacion-familiar`,
`perceptor.discapacidad-grado`, the four `ascendiente-N.*` and four
`descendiente-N.*` blocks, `pension-compensatoria.importe-anual`,
`anualidades-alimentos.importe-anual`, `vivienda-habitual.financiacion-ajena`,
the `acuse-recibo.*` and `comunicacion.*` metadata fields. No bindings,
formulas or constructs cite this reference directly in this revision --
Modelo 145 has no calculation layer; it is a pure data-communication form,
so the citation lands entirely on the declared casillas.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-06-28`.

### 4. `resolucion-dgt-2011-01-03-modelo-145:aprobacion` -- Aprobación del modelo 145

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/boe-a-2011-208-modelo-145.html#primero`
- `document_id`: `BOE-A-2011-208`; `effective_from`: 2011-01-05
- `required_text`:
  - "Aprobación del modelo 145"
  - "comunicación de datos del perceptor de rentas del trabajo a su pagador"
  - "un ejemplar para la empresa o entidad pagadora y otro para el perceptor"
- `notes` (verbatim): "Resolucion de 3 de enero de 2011 que aprueba el Modelo 145 como comunicacion de datos del perceptor de rentas del trabajo a su pagador."

#### Bundled corpus text (verbatim, from the anchored `#primero` unit)

> Primero. Aprobación del modelo 145, de comunicación de datos del perceptor
> de rentas del trabajo a su pagador.
>
> Se aprueba el modelo 145, de comunicación de datos del perceptor de
> rentas del trabajo a su pagador, que figura en el Anexo de la presente
> resolución, que consta de dos ejemplares, un ejemplar para la empresa o
> entidad pagadora y otro para el perceptor.
>
> Serán válidos también, aquellos formularios que, ajustados al contenido
> del modelo que aprueba la presente resolución, respondan a un formato
> diferente.

`corpus_ref` resolves; all three declared `required_text` phrases are
present verbatim in the text above. The excerpt is three short paragraphs;
nothing is elided.

#### Modelo 145 dependents (revision `2012-01-31-y-siguientes`)

50 casillas -- the same declarative-field population as `art-88` above,
minus the six `acuse-recibo.*` fields (this founding approval resolution
predates the acuse-de-recibo mechanics the 2013 amendment below introduces).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-05-14`.

### 5. `resolucion-dgt-2013-12-17-modelo-145:amendment` -- Modificación de la Resolución de 3 de enero de 2011 (modelo 145)

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/boe-a-2014-59-modelo-145-amendment.html#apartado-unico`
- `document_id`: `BOE-A-2014-59`; `effective_from`: 2014-01-03
- `required_text`:
  - "queda modificada como sigue"
  - "El pagador acusará recibo de la presentación"
  - "El pagador deberá conservar a disposición de la Administración tributaria"
- `notes` (verbatim): "Resolucion de 17 de diciembre de 2013 que modifica el Modelo 145 con efectos para comunicaciones de datos al pagador desde 2014."

#### Bundled corpus text (verbatim, from the anchored `#apartado-unico` unit)

> Apartado único. Modificación de la Resolución de 3 de enero de 2011, del
> Departamento de Gestión Tributaria de la Agencia Estatal de Administración
> Tributaria, por la que se aprueba el modelo 145 [...] queda modificada
> como sigue:
>
> Uno. El apartado quinto queda redactado de la siguiente forma: «Quinto.
> Contenido de la comunicación de los datos relativos a pensiones
> compensatorias a favor del cónyuge y anualidades por alimentos a favor de
> los hijos, fijadas ambas por decisión judicial. [...] se referirá al
> importe anual que el perceptor esté obligado a satisfacer por dichos
> conceptos.»
>
> Dos. El apartado sexto queda redactado de la siguiente forma: «Sexto.
> Contenido de la comunicación de los datos relativos a los pagos
> realizados por la adquisición o rehabilitación de la vivienda habitual
> utilizando financiación ajena. -- Para que resulte aplicable la reducción
> del tipo de retención prevista en el último párrafo del artículo 86.1 del
> Reglamento del Impuesto, los perceptores de rendimientos del trabajo cuyas
> retribuciones totales sean inferiores a 33.007,20 euros anuales deberán
> comunicar a su pagador que están destinando cantidades para la
> adquisición o rehabilitación de su vivienda habitual utilizando
> financiación ajena [...]. En el supuesto de que el contribuyente perciba
> rendimientos del trabajo procedentes, de forma simultánea o sucesiva, de
> dos o más pagadores, solamente podrá efectuar la comunicación a que se
> refiere el párrafo anterior cuando la cuantía total de las retribuciones
> íntegras correspondientes a todos ellos sea inferior a 33.007,20 euros
> anuales. [...]»
>
> Tres. El apartado séptimo.1 queda redactado de la siguiente forma: «1. De
> acuerdo con lo dispuesto en el artículo 88.1 del Reglamento del Impuesto
> [...] el perceptor deberá presentar la correspondiente comunicación de
> datos. La presentación de la comunicación de datos al pagador, debidamente
> firmada, deberá efectuarse en el modelo 145 [...]. El pagador acusará
> recibo de la presentación devolviendo al contribuyente el ejemplar para
> el perceptor del citado modelo, una vez cumplimentando a tal efecto el
> apartado 7 del mismo. [...]»
>
> Cuatro. El apartado séptimo.4 queda redactado de la siguiente forma: «4.
> El pagador deberá conservar a disposición de la Administración tributaria
> las comunicaciones presentadas por los perceptores debidamente firmadas.»
>
> Quinto. El apartado noveno.4 queda redactado de la siguiente forma: «4. El
> pagador deberá conservar a disposición de la Administración tributaria
> las comunicaciones de variación de datos presentadas por los perceptores
> debidamente firmadas.»
>
> Seis. El modelo 145 que figura en el anexo queda sustituido por el modelo
> 145 que figura en el anexo de la presente resolución.

Procedural detail inside apartados Uno through Seis not touching a
`required_text` phrase (the impatriate-communication constancy language,
the disposición transitoria undécima carve-out, and the telematic-filing
mechanics) is elided above (`[...]`) for length; present in full in the
bundled file. `corpus_ref` resolves; all three declared `required_text`
phrases are present verbatim in the text above (apartado Tres carries "El
pagador acusará recibo de la presentación"; apartados Cuatro and Quinto both
carry "El pagador deberá conservar a disposición de la Administración
tributaria"). **Numeric flag:** apartado Dos restates the 33.007,20 euros
annual-retribution ceiling already established by `rd-439-2007:art-88`
above -- see the packet preamble.

#### Modelo 145 dependents (revision `2012-01-31-y-siguientes`)

6 casillas, all in the `acuse-recibo.*` block this amendment introduces:
`acuse-recibo.empresa-entidad`, `acuse-recibo.fecha-anio`,
`acuse-recibo.fecha-dia`, `acuse-recibo.fecha-mes`, `acuse-recibo.lugar`,
`acuse-recibo.tipo-firma`. A materially narrower dependent set than
`aprobacion` above, consistent with this amendment introducing only the
acuse-de-recibo mechanics rather than re-founding the whole form.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-05-14`.

### 6. `resolucion-dgt-2014-12-18-modelo-145:amendment` -- Modificación de la Resolución de 3 de enero de 2011 (modelo 145, sustitución de anexo)

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/boe-a-2014-13679-modelo-145-amendment.html#apartado-unico`
- `document_id`: `BOE-A-2014-13679`; `effective_from`: 2014-12-31
- `required_text`:
  - "queda modificada como sigue"
  - "queda sustituido por el modelo 145"
- `notes` (verbatim): "Resolucion de 18 de diciembre de 2014 que modifica el Modelo 145 con efectos para comunicaciones de datos al pagador desde 2015."

#### Bundled corpus text (verbatim, from the anchored `#apartado-unico` unit)

> Apartado único. Modificación de la Resolución de 3 de enero de 2011, del
> Departamento de Gestión Tributaria de la Agencia Estatal de Administración
> Tributaria, por la que se aprueba el modelo 145, de comunicación de datos
> del perceptor de rentas del trabajo a su pagador o de la variación de los
> datos previamente comunicados, queda modificada como sigue:
>
> Uno. El modelo 145 que figura en el anexo queda sustituido por el modelo
> 145 que figura en el anexo de la presente resolución.

`corpus_ref` resolves; both declared `required_text` phrases are present
verbatim in the text above. This is the shortest of the fifteen entries --
one operative sentence naming an annex substitution, nothing elided.

#### Modelo 145 dependents (revision `2012-01-31-y-siguientes`)

No dependents found in this revision -- no casilla, binding, formula or
construct in `2012-01-31-y-siguientes` carries this citation in its
`legal_refs` or `source_refs`. Traced by walking the revision's compiled
casilla/binding/formula/construct fragments directly, not by the snapshot
ref-id sweep that first surfaced it (that sweep confirmed the snapshot
*builds against* this reference -- the revision-level legal catalogue cites
it -- but no individual field-level entry does). This is consistent with the
excerpt itself: it is a pure annex-substitution notice, replacing the visual
form layout without redefining any data field's legal basis, so no
individual casilla's own provenance changes.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-05-14`.

## Modelo 349

### 7. `ley-37-1992:art-27` -- Importaciones de bienes cuya entrega en el interior estuviese exenta del impuesto

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-37-1992.html#a27`
- `document_id`: `BOE-A-1992-28740`; `effective_from`: 2011-01-01
- `required_text`:
  - "Importaciones de bienes cuya entrega en el interior estuviese exenta del impuesto"
  - "los bienes cuya expedición o transporte tenga como punto de llegada un lugar situado en otro Estado miembro"
  - "representante fiscal"
- `notes` (verbatim): "LIVA art 27.12: importaciones exentas followed by onward delivery to another Member State. Base sustantiva de las claves M349 M y H when the M349 instructions cite importacion exenta and representative-fiscal flows."

#### Bundled corpus text (verbatim, from the anchored `#a27` unit)

> Artículo 27. Importaciones de bienes cuya entrega en el interior estuviese
> exenta del impuesto.
>
> Estarán exentas del impuesto las importaciones de los siguientes bienes:
>
> 1.º-11.º [Sangre y fluidos humanos; buques y aeronaves y sus
> avituallamientos con las remisiones a las exenciones del art. 22;
> divisas/billetes/monedas de curso legal; títulos-valores; 9.º suprimido;
> oro importado por el Banco de España; bienes destinados a las plataformas
> del art. 23.uno.2.º -- present in full in the bundled file.]
>
> 12.º Los bienes cuya expedición o transporte tenga como punto de llegada
> un lugar situado en otro Estado miembro, siempre que la entrega ulterior
> de dichos bienes efectuada por el importador o su representante fiscal
> estuviese exenta en virtud de lo dispuesto en el artículo 25 de esta Ley.
>
> La exención prevista en este número quedará condicionada al cumplimiento
> de los requisitos que se establezcan reglamentariamente.
>
> Se modifican los apartados 12º y 7º por el art. 78.1 y 79.4 de la ley
> 39/2010, de 22 de diciembre. Ref. BOE-A-2010-19703. Se suprime el
> apartado 9º por el art. 17.4 de la Ley 42/1994, de 30 de diciembre. Ref.
> BOE-A-1994-28968.

Enumerated items 1.º through 11.º are elided above (`[...]`) for length;
present in full in the bundled file, and no elision touches a
`required_text` phrase -- all three declared phrases sit inside apartado
12.º, quoted in full. `corpus_ref` resolves.

#### Modelo 349 dependents (revision `2020-y-siguientes`)

35 dependents: 34 bindings covering both the "operaciones" declarante/row
layer and the "rectificaciones" declarante/row layer, for both the
delivery-side and adquisición-side variants (`iva-349-declarante-*`,
`iva-349-operador-row-*`, `iva-349-rectificacion-row-*`, each with an
`-adquisicion` counterpart), plus the construct `modelo-349-informative`. No
individual casilla carries this citation in this revision -- Modelo 349's
per-key data fields are declared as row-level bindings rather than
standalone casillas, so the citation lands on the binding layer.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-06-27`.

### 8. `ley-37-1992:art-69` -- Lugar de realización de las prestaciones de servicios. Reglas generales

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-37-1992.html#a69`
- `document_id`: `BOE-A-1992-28740`; `effective_from`: 2010-01-01
- `required_text`:
  - "Lugar de realización de las prestaciones de servicios. Reglas generales"
  - "Cuando el destinatario sea un empresario o profesional que actúe como tal"
- `notes` (verbatim): "LIVA art 69: general place-of-supply rules for services. Grounds M349 intracommunity service prestation/acquisition keys S and I together with the RIVA recapitulativa obligation. With arts. 68 and 70 it is also the rule set that decides WHICH IVA category a cross-border service belongs to; that selection is a declared judgement made by the operator, never derived by the system from the counterparty's country alone. Bundled text checked against the live BOE consolidated text on 2026-08-05: the anchored #a69 unit of the bundled ley-37-1992.html is character-identical to the current redaction BOE-A-2014-12329 (in force 2015-01-01), apart from the BOE amendment-history footnotes the consolidated page appends after the article body."

This entry's `notes` field is one of the two self-verification-claim entries
identified in the packet series (the other, `art-70` immediately below, is
also cited by Modelo 349 here); see the Modelo 390 packet
(`2026-08-14-modelo-390-legal-attestation-review-reference`), where both were
first documented and caveated. That caveat is repeated in this packet's own
preamble as a standing practice and is not restated per-entry.

#### Bundled corpus text (verbatim, from the anchored `#a69` unit)

> Artículo 69. Lugar de realización de las prestaciones de servicios.
> Reglas generales.
>
> Uno. Las prestaciones de servicios se entenderán realizadas en el
> territorio de aplicación del Impuesto [...] en los siguientes casos:
>
> 1.º Cuando el destinatario sea un empresario o profesional que actúe como
> tal y radique en el citado territorio la sede de su actividad económica,
> o tenga en el mismo un establecimiento permanente [...], con
> independencia de dónde se encuentre establecido el prestador de los
> servicios y del lugar desde el que los preste.
>
> 2.º Cuando el destinatario no sea un empresario o profesional actuando
> como tal, siempre que los servicios se presten por un empresario o
> profesional y la sede de su actividad económica [...] se encuentre en el
> territorio de aplicación del Impuesto.
>
> Dos. Por excepción [...] no se entenderán realizados en el territorio de
> aplicación del Impuesto los servicios que se enumeran a continuación
> cuando el destinatario [...] esté establecido o tenga su domicilio o
> residencia habitual fuera de la Comunidad [...] [enumerates: propiedad
> intelectual/industrial; cesión de fondos de comercio; publicidad;
> asesoramiento/auditoría/ingeniería/abogacía; tratamiento de datos;
> traducción; seguros/servicios financieros; cesión de personal; doblaje;
> arrendamiento de bienes muebles corporales salvo transporte; acceso a
> redes de gas/electricidad/calefacción; obligaciones de no prestar los
> anteriores].
>
> Tres. A efectos de esta Ley, se entenderá por: 1.º Sede de la actividad
> económica [...]; 2.º Establecimiento permanente [...]; 3.º Servicios de
> telecomunicación [...]; 4.º Servicios prestados por vía electrónica
> [...]; 5.º Servicios de radiodifusión y televisión [...].
>
> [Followed by BOE amendment-history footnotes: Ley 28/2014 art. 1.12/13,
> Ley 39/2010 art. 79.8, Ley 2/2010 art. 1.6 with effects from 2010-01-01.]

The apartado Dos enumeration and apartado Tres definitions are elided above
(`[...]`) for length; both present in full in the bundled file, and no
elision touches a `required_text` phrase. `corpus_ref` resolves; both
declared `required_text` phrases are present verbatim in the text above.

#### Modelo 349 dependents (revision `2020-y-siguientes`)

Same dependent population as `art-27` above: 34 bindings across the
"operaciones"/"rectificaciones" declarante/row layer (both delivery-side and
`-adquisicion` variants) plus the construct `modelo-349-informative`.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-06-27`.

### 9. `ley-37-1992:art-70` -- Lugar de realización de las prestaciones de servicios. Reglas especiales

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-37-1992.html#a70`
- `document_id`: `BOE-A-1992-28740`; `effective_from`: 2010-01-01
- `required_text`:
  - "Lugar de realización de las prestaciones de servicios. Reglas especiales"
  - "Los relacionados con bienes inmuebles que radiquen en el citado territorio"
- `notes` (verbatim): "LIVA art 70: special place-of-supply rules for services. Complements art 69 for M349 service keys S and I where official instructions distinguish services localized in or outside the TAI. Its apartado Uno reglas (inmuebles, transporte, acceso a manifestaciones, servicios electronicos, restauracion, mediacion, trabajos sobre bienes muebles, arrendamiento de medios de transporte) override the art. 69 general rule, so category selection for a cross-border service must be read here before art. 69 is applied; the selection stays a declared operator judgement. Bundled text checked against the live BOE consolidated text on 2026-08-05: the anchored #a70 unit of the bundled ley-37-1992.html is character-identical to the current redaction BOE-A-2023-12204 (in force 2023-05-26), apart from the BOE amendment-history footnotes the consolidated page appends after the article body."

The second of this packet series' two self-verification-claim entries; see
the standing preamble caveat and the cross-reference at `art-69` above.

#### Bundled corpus text (verbatim, from the anchored `#a70` unit)

> Artículo 70. Lugar de realización de las prestaciones de servicios.
> Reglas especiales.
>
> Uno. Se entenderán prestados en el territorio de aplicación del Impuesto
> los siguientes servicios:
>
> 1.º Los relacionados con bienes inmuebles que radiquen en el citado
> territorio. Se considerarán relacionados con bienes inmuebles, entre
> otros, los siguientes servicios: a) El arrendamiento o cesión de uso
> [...]; b) los relativos a ejecuciones de obra inmobiliarias; c) los de
> carácter técnico sobre dichas obras; d) los de gestión relativos a bienes
> inmuebles; e) los de vigilancia o seguridad; f) los de alquiler de cajas
> de seguridad; g) la utilización de vías de peaje; h) los de alojamiento
> hostelero.
>
> 2.º Los de transporte [...]. 3.º El acceso a manifestaciones culturales,
> artísticas, deportivas, científicas, educativas, recreativas o similares
> [...]. 4.º-9.º [Servicios electrónicos/telecomunicaciones/radiodifusión;
> restauración y catering; mediación; servicios accesorios a transportes y
> ejecuciones de obra sobre bienes muebles; arrendamiento de medios de
> transporte -- full enumerations with sub-conditions present in the
> bundled file.]
>
> Dos. Asimismo, se considerarán prestados en el territorio de aplicación
> del Impuesto los servicios que se enumeran a continuación cuando [...] no
> se entiendan realizados en la Comunidad, Islas Canarias, Ceuta o Melilla,
> pero su utilización o explotación efectivas se realicen en dicho
> territorio: 1.º Los enunciados en el apartado dos del artículo 69 [...];
> 2.º Los de arrendamiento de medios de transporte.
>
> [Followed by an extensive BOE amendment-history footnote list running
> from Ley 13/2023 back to Real Decreto-Ley 12/1995, present in full in the
> bundled file.]

Apartados 2.º-3.º and 4.º-9.º are elided above (`[...]`) for length;
present in full in the bundled file, and no elision touches a
`required_text` phrase. `corpus_ref` resolves; both declared `required_text`
phrases are present verbatim in the text above (both sit inside apartado
Uno.1.º).

#### Modelo 349 dependents (revision `2020-y-siguientes`)

Same dependent population as `art-27`/`art-69` above: 34 bindings across the
"operaciones"/"rectificaciones" declarante/row layer (both delivery-side and
`-adquisicion` variants) plus the construct `modelo-349-informative`.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-06-27`.

### 10. `ley-37-1992:art-80` -- Modificación de la base imponible

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-37-1992.html#a80`
- `document_id`: `BOE-A-1992-28740`; `effective_from`: 1993-01-01
- `required_text`:
  - "Modificación de la base imponible"
  - "la base imponible se modificará en la cuantía correspondiente"
- `notes` (verbatim): "LIVA art 80: modificacion de la base imponible. Grounds rectified M349 bases where the declared intracommunity operation base changes because the taxable base is reduced or otherwise modified."

#### Bundled corpus text (verbatim, from the anchored `#a80` unit)

> Artículo 80. Modificación de la base imponible.
>
> Uno. La base imponible determinada con arreglo a lo dispuesto en los
> artículos 78 y 79 anteriores se reducirá en las cuantías siguientes: 1.º
> El importe de los envases y embalajes susceptibles de reutilización que
> hayan sido objeto de devolución. 2.º Los descuentos y bonificaciones
> otorgados con posterioridad al momento en que la operación se haya
> realizado siempre que sean debidamente justificados.
>
> Dos. Cuando por resolución firme, judicial o administrativa o con arreglo
> a Derecho o a los usos de comercio queden sin efecto total o parcialmente
> las operaciones gravadas o se altere el precio después del momento en que
> la operación se haya efectuado, la base imponible se modificará en la
> cuantía correspondiente.
>
> Tres. La base imponible podrá reducirse cuando el destinatario de las
> operaciones sujetas al Impuesto no haya hecho efectivo el pago de las
> cuotas repercutidas y siempre que [...] se dicte auto de declaración de
> concurso. [...]
>
> Cuatro. La base imponible también podrá reducirse proporcionalmente
> cuando los créditos correspondientes a las cuotas repercutidas por las
> operaciones gravadas sean total o parcialmente incobrables. [...] Que el
> destinatario de la operación actúe en la condición de empresario o
> profesional, o, en otro caso, que la base imponible de aquella, Impuesto
> sobre el Valor Añadido excluido, sea superior a 50 euros. [...] Cuando el
> titular del derecho de crédito cuya base imponible se pretende reducir
> sea un empresario o profesional cuyo volumen de operaciones, calculado
> conforme a lo dispuesto en el artículo 121 de esta Ley, no hubiese
> excedido durante el año natural inmediato anterior de 6.010.121,04 euros,
> el plazo [...] podrá ser, de seis meses o un año. [...]
>
> Cinco.-Siete. [Exclusion rules for guaranteed/insured/related-party/ente-
> público credits; the destinatario-not-established exclusion and its EU-
> insolvency-regime carve-out; partial-payment proration; the destinatario's
> deduction rectification duty and correlative Hacienda Pública credit --
> present in full in the bundled file, followed by an extensive BOE
> amendment-history footnote list running from Ley 31/2022 back to Ley
> 22/1993.]

Portions of apartado Tres (the auto-de-concurso two-month deadline
mechanics) and apartados Cinco through Siete (the exclusion-rule detail not
touching a `required_text` phrase) are elided above (`[...]`) for length;
present in full in the bundled file. `corpus_ref` resolves; both declared
`required_text` phrases are present verbatim in the text above. **Numeric
flag:** apartado Cuatro states two figures directly -- the 50 euros minor-
credit floor (condición 3.ª) and the 6.010.121,04 euros volumen-de-
operaciones ceiling that shortens the bad-debt waiting period to six months
-- see the packet preamble.

#### Modelo 349 dependents (revision `2020-y-siguientes`)

Same dependent population as `art-27`/`art-69`/`art-70` above: 34 bindings
across the "operaciones"/"rectificaciones" declarante/row layer (both
delivery-side and `-adquisicion` variants) plus the construct
`modelo-349-informative`. This citation specifically grounds the
rectificación-row bindings' base-imponible-modification basis, shared with
the same binding population the place-of-supply and exemption references
above cite.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-06-27`.

### 11. `ley-37-1992:art-86` -- Sujetos pasivos (importaciones)

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-37-1992.html#a86`
- `document_id`: `BOE-A-1992-28740`; `effective_from`: 2011-01-01
- `required_text`:
  - "Sujetos pasivos"
  - "cuando se trate de las importaciones a que se refiere el número 12.º del artículo 27"
  - "representante fiscal"
- `notes` (verbatim): "LIVA art 86.3: import representative-fiscal obligation for importations covered by art 27.12. Base sustantiva for M349 key H where the instructions require representative-fiscal deliveries after exempt import."

#### Bundled corpus text (verbatim, from the anchored `#a86` unit)

> Artículo 86. Sujetos pasivos.
>
> Uno. Serán sujetos pasivos del Impuesto quienes realicen las
> importaciones.
>
> Dos. Se considerarán importadores, siempre que se cumplan en cada caso
> los requisitos previstos en la legislación aduanera: 1.º Los
> destinatarios de los bienes importados, sean adquirentes, cesionarios o
> propietarios de los mismos o bien consignatarios que actúen en nombre
> propio en la importación de dichos bienes. 2.º Los viajeros, para los
> bienes que conduzcan al entrar en el territorio de aplicación del
> Impuesto. 3.º Los propietarios de los bienes en los casos no
> contemplados en los números anteriores. 4.º Los adquirentes o, en su
> caso, los propietarios, los arrendatarios o fletadores de los bienes a
> que se refiere el artículo 19 de esta Ley.
>
> Tres. Sin perjuicio de lo dispuesto en el apartado uno de este artículo,
> cuando se trate de las importaciones a que se refiere el número 12.º del
> artículo 27 de esta Ley y el importador actúe mediante representante
> fiscal, este último quedará obligado al cumplimiento de las obligaciones
> materiales y formales derivadas de dichas importaciones en los términos
> que se establezcan reglamentariamente.
>
> Se modifica por el art. 78.2 de la Ley 39/2010, de 22 de diciembre. Ref.
> BOE-A-2010-19703. Se modifica el punto 4º por el art. 6.11 de la Ley
> 66/1997, de 30 de diciembre. Ref. BOE-A-1997-28053.

`corpus_ref` resolves; all three declared `required_text` phrases are
present verbatim in the text above (the third, "representante fiscal", sits
inside apartado Tres). Nothing is elided -- the full article is quoted, and
the entry's own note correctly identifies apartado Tres, numbered "3" in the
note but rendered "Tres" in the bundled text, as the operative provision for
M349 key H.

#### Modelo 349 dependents (revision `2020-y-siguientes`)

Same dependent population as the other `ley-37-1992` entries above: 34
bindings across the "operaciones"/"rectificaciones" declarante/row layer
(both delivery-side and `-adquisicion` variants) plus the construct
`modelo-349-informative`.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-06-27`.

### 12. `ley-37-1992:art-9-bis` -- Acuerdo de ventas de bienes en consigna

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-37-1992.html#articulo-9-bis-acuerdo-de-ventas-de-bienes-en-consigna`
- `document_id`: `BOE-A-1992-28740`; `effective_from`: 2020-03-01
- `required_text`:
  - "Acuerdo de ventas de bienes en consigna"
  - "declaración recapitulativa a que se refiere el artículo 164"
  - "plazo de los doce meses"
- `notes` (verbatim): "LIVA art 9 bis: acuerdo de ventas de bienes en consigna. Define las transferencias intracomunitarias en consigna, el plazo de doce meses, y la inclusion reglamentaria en declaracion recapitulativa. Base sustantiva de las claves M349 R, D y C desde la revision 2020."

#### Bundled corpus text (verbatim, from the anchored unit)

> Artículo 9 bis. Acuerdo de ventas de bienes en consigna.
>
> Uno. A los efectos de lo dispuesto en esta Ley, se entenderá por acuerdo
> de ventas de bienes en consigna aquel en el que se cumplan los siguientes
> requisitos: a) Que los bienes sean expedidos o transportados a otro
> Estado miembro [...]. b) Que el vendedor [...] no tenga la sede de su
> actividad económica o un establecimiento permanente en el Estado miembro
> de llegada [...]. c) Que el empresario o profesional que va a adquirir
> los bienes esté identificado a efectos del Impuesto sobre el Valor
> Añadido en el Estado miembro de llegada [...]. d) Que el vendedor haya
> incluido el envío de dichos bienes tanto en el libro registro que se
> determine reglamentariamente como en la declaración recapitulativa a que
> se refiere el artículo 164, apartado uno, número 5.º, de esta Ley, en la
> forma que se determine reglamentariamente.
>
> Dos. Cuando, en el plazo de los doce meses siguientes a la llegada de los
> bienes al Estado miembro de destino en el marco de un acuerdo de ventas
> de bienes en consigna, el empresario o profesional mencionado en la
> letra c) del apartado anterior [...] adquiera el poder de disposición de
> los bienes, se entenderá que en el territorio de aplicación del Impuesto
> se realiza, según los casos: a) Una entrega de bienes [...], por el
> vendedor, a la que resultará aplicable la exención prevista en el
> artículo 25 de esta Ley, o b) una adquisición intracomunitaria de bienes
> [...], por el empresario o profesional que los adquiere.
>
> Tres. Se entenderá que se ha producido una transferencia de bienes a la
> que se refiere el artículo 9.3.º de esta Ley cuando [...] dentro del
> plazo de los doce meses previsto en el apartado anterior, se incumplan
> cualquiera de las condiciones establecidas en el apartado uno anterior
> [...]. No obstante, se entenderán cumplidos los requisitos [...] cuando
> dentro del referido plazo: a') Los bienes sean adquiridos por un
> empresario o profesional que sustituya al referido en la letra c) [...].
> b') No se haya transmitido el poder de disposición de los bienes y estos
> sean devueltos al Estado miembro desde el que se expidieron o
> transportaron. c') Las circunstancias previstas en las letras a') y b')
> hayan sido incluidas por el vendedor en el libro registro [...].
>
> Cuatro. Se entenderá que se ha producido una transferencia de bienes
> [...] al día siguiente de la expiración del plazo de 12 meses [...] sin
> que el empresario o profesional [...] haya adquirido el poder de
> disposición de los bienes.
>
> Cinco. Los empresarios o profesionales que suscriban un acuerdo de
> ventas de bienes en consigna [...] deberán llevar un libro registro de
> estas operaciones en las condiciones que se establezcan
> reglamentariamente.
>
> Se añade por el art. 214.3 del Real Decreto-ley 3/2020, de 4 de febrero.
> Ref. BOE-A-2020-1651. Este artículo entra en vigor el 1 de marzo de 2020
> [...].

Sub-condition detail inside apartados Uno through Tres not touching a
`required_text` phrase is elided above (`[...]`) for length; present in
full in the bundled file. `corpus_ref` resolves; all three declared
`required_text` phrases are present verbatim in the text above (the second,
about the declaración recapitulativa, sits in apartado Uno.d); the third,
"plazo de los doce meses", recurs in apartados Dos and Tres). "Doce meses"
and "12 meses" both appear in the text (apartado Cuatro uses the numeral);
the declared phrase quotes the spelled-out form, which is present.

#### Modelo 349 dependents (revision `2020-y-siguientes`)

Same dependent population as the other `ley-37-1992` entries above: 34
bindings across the "operaciones"/"rectificaciones" declarante/row layer
(both delivery-side and `-adquisicion` variants) plus the construct
`modelo-349-informative`. This is the reference whose `notes` field most
directly names its Modelo 349 clave mapping (R, D, C) among the fifteen in
this packet.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-06-27`.

### 13. `rd-1624-1992:art-79` -- Obligación de presentar la declaración recapitulativa

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/rd-1624-1992-art-79.html#a79`
- `document_id`: `BOE-A-1992-28925`; `effective_from`: 2020-03-01
- `required_text`:
  - "Obligación de presentar la declaración recapitulativa"
  - "Las prestaciones intracomunitarias de servicios"
  - "acuerdo de ventas de bienes en consigna"
- `notes` (verbatim): "Reglamento del IVA art 79: obligation to present the declaracion recapitulativa. Enumerates the M349 operation universe: intracommunity deliveries, acquisitions, services, triangular subsequent deliveries, and consignment-sale movements."

#### Bundled corpus text (verbatim, from the anchored `#a79` unit)

> Articulo 79. Obligacion de presentar la declaracion recapitulativa.
>
> 1. Estaran obligados a presentar la declaracion recapitulativa los
> empresarios y profesionales que realicen cualquiera de las siguientes
> operaciones: 1.º Las entregas de bienes destinados a otro Estado miembro
> que se encuentren exentas en virtud de lo dispuesto en el articulo 25 de
> la Ley del Impuesto. 2.º Las adquisiciones intracomunitarias de bienes
> sujetas al Impuesto realizadas por personas o entidades identificadas a
> efectos del mismo en el territorio de aplicacion del Impuesto. 3.º Las
> prestaciones intracomunitarias de servicios. 4.º Las adquisiciones
> intracomunitarias de servicios. 5.º Las entregas subsiguientes a las
> adquisiciones intracomunitarias de bienes a que se refiere el apartado
> tres del articulo 26 de la Ley del Impuesto.
>
> Asimismo, deberan presentar la declaracion recapitulativa los empresarios
> o profesionales que envien o transporten bienes desde el territorio de
> aplicacion del Impuesto con destino a otro Estado miembro en el marco de
> un acuerdo de ventas de bienes en consigna.

`corpus_ref` resolves; all three declared `required_text` phrases are
present verbatim in the text above. This standalone excerpt is one
paragraph plus its five-item enumeration; nothing is elided. (This bundled
excerpt does not carry the accented characters `ó`/`í` present in the
Ley 37/1992 text above -- "Articulo", "Obligacion", "recapitulativa" are
unaccented in this file; the check is diacritic-folding, per
`normalise_corpus_text`, so this rendering difference does not affect
`required_text` presence.)

#### Modelo 349 dependents (revision `2020-y-siguientes`)

Same dependent population as the other `ley-37-1992`/`rd-1624-1992` entries
above: 34 bindings across the "operaciones"/"rectificaciones"
declarante/row layer (both delivery-side and `-adquisicion` variants) plus
the construct `modelo-349-informative`. This reference is the reglamentario
counterpart establishing the same operation universe the substantive
`ley-37-1992` articles above ground individually.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-06-27`.

### 14. `rd-1624-1992:art-80` -- Contenido de la declaración recapitulativa

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/rd-1624-1992-art-80.html#a80`
- `document_id`: `BOE-A-1992-28925`; `effective_from`: 2020-03-01
- `required_text`:
  - "Contenido de la declaración recapitulativa"
  - "Los datos de identificación de los proveedores y adquirentes"
  - "deberán rectificarse cuando se haya incurrido en errores"
- `notes` (verbatim): "Reglamento del IVA art 80: content of the declaracion recapitulativa, including identification data, operation bases/importes, consignment-sale information, and rectification of erroneous recapitulativa data."

#### Bundled corpus text (verbatim, from the anchored `#a80` unit)

> Articulo 80. Contenido de la declaracion recapitulativa.
>
> 1. En la declaracion recapitulativa se consignaran los datos de
> identificacion de los proveedores y adquirentes de los bienes y los
> prestadores y destinatarios de los servicios, asi como la base imponible
> total correspondiente a las operaciones efectuadas con cada uno de ellos.
>
> Tambien deberan consignarse los datos de identificacion del empresario o
> profesional al que vayan destinados los bienes expedidos o transportados
> en el marco de un acuerdo de ventas de bienes en consigna.
>
> Los datos contenidos en las declaraciones recapitulativas deberan
> rectificarse cuando se haya incurrido en errores o se hayan producido
> alteraciones derivadas de las circunstancias a que se refiere el
> articulo 80 de la Ley del Impuesto.

`corpus_ref` resolves; all three declared `required_text` phrases are
present (diacritic-folded, per the same rendering note as `rd-1624-1992:
art-79` above). Nothing is elided -- the full excerpt is three short
paragraphs. Note the excerpt's own internal cross-reference: its final
sentence cites "el articulo 80 de la Ley del Impuesto" -- that is
`ley-37-1992:art-80` (section 10 of this packet, above), a different
article sharing the same number "80" in a different instrument. This is not
a discrepancy in this entry's own citation (the entry correctly identifies
itself as `rd-1624-1992:art-80`); it is the source text's own cross-
reference to a same-numbered article in the Ley, noted here for clarity
since both `art-80` entries appear in this packet.

#### Modelo 349 dependents (revision `2020-y-siguientes`)

Same dependent population as the other `ley-37-1992`/`rd-1624-1992` entries
above: 34 bindings across the "operaciones"/"rectificaciones"
declarante/row layer (both delivery-side and `-adquisicion` variants) plus
the construct `modelo-349-informative`.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-06-27`.

### 15. `rd-1624-1992:art-81` -- Lugar, forma y plazos de presentación de la declaración recapitulativa

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/rd-1624-1992-art-81.html#a81`
- `document_id`: `BOE-A-1992-28925`; `effective_from`: 2020-03-01
- `required_text`:
  - "Lugar, forma y plazos de presentacion de la declaracion recapitulativa"
  - "por cada mes natural durante los veinte primeros dias naturales"
  - "en cada uno de los cuatro trimestres naturales anteriores"
  - "50.000 euros"
  - "durante los veinte primeros dias naturales del mes inmediato siguiente al correspondiente periodo trimestral"
- `notes` (verbatim): "Reglamento del IVA art 81: place, form, filing periods, and deadlines for the declaracion recapitulativa. Grounds Modelo 349 monthly cadence and the 50,000 EUR quarterly-threshold exception across the reference quarter and four prior natural quarters."

#### Bundled corpus text (verbatim, from the anchored `#a81` unit)

> Articulo 81. Lugar, forma y plazos de presentacion de la declaracion
> recapitulativa.
>
> 1. La presentacion de la declaracion recapitulativa se realizara en el
> lugar, forma y a traves del modelo aprobados por el Ministro de Economia
> y Hacienda.
>
> 2. El periodo de declaracion y los plazos para la presentacion de la
> declaracion recapitulativa seran los siguientes:
>
> 1.º Con caracter general, la declaracion recapitulativa debera
> presentarse por cada mes natural durante los veinte primeros dias
> naturales del mes inmediato siguiente, salvo la correspondiente al mes de
> julio, que podra presentarse durante el mes de agosto y los veinte
> primeros dias naturales del mes de septiembre.
>
> 2.º Cuando ni durante el trimestre de referencia ni en cada uno de los
> cuatro trimestres naturales anteriores el importe total acumulado de las
> entregas de bienes que deban consignarse en la declaracion recapitulativa
> y de las prestaciones intracomunitarias de servicios efectuadas sea
> superior a 50.000 euros, excluido el Impuesto sobre el Valor Anadido, la
> declaracion recapitulativa debera presentarse durante los veinte primeros
> dias naturales del mes inmediato siguiente al correspondiente periodo
> trimestral.
>
> Si al final de cualquiera de los meses que componen cada trimestre
> natural se superara el importe mencionado en el parrafo anterior, debera
> presentarse una declaracion recapitulativa para el mes o los meses
> transcurridos desde el comienzo de dicho trimestre natural durante los
> veinte primeros dias naturales inmediatos siguientes.
>
> 3. En todos los casos a que se refiere el apartado 2 este articulo, la
> declaracion recapitulativa correspondiente al ultimo periodo del ano
> debera presentarse durante los treinta primeros dias naturales del mes de
> enero.

`corpus_ref` resolves; all five declared `required_text` phrases are
present (diacritic-folded, per the same rendering note as the two preceding
`rd-1624-1992` entries). Nothing is elided -- the full article is quoted.
**Numeric flag:** apartado 2.2.º states the 50.000 euros quarterly-volume
threshold directly, deciding whether the recapitulativa cadence is monthly
(general rule, apartado 2.1.º) or quarterly (this exception) -- see the
packet preamble.

#### Modelo 349 dependents (revision `2020-y-siguientes`)

1 dependent: the construct `modelo-349-informative` only. No individual
binding in this revision carries this citation -- unlike the other eight
Modelo 349 references in this packet, which each ground 34 row-level
bindings, this reference governs filing cadence and the periodicity
threshold rather than any individual declared data field, so it is cited
only at the construct level.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-06-28`.
