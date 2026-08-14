---
tags:
  - '#reference'
  - '#modelo-100-legal-attestation-review-batch-b'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:7bf25dfdae215574a0771d861d45a20341d5f1901bfcadea02d65ccf0311fdf6'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-14-registry-campaign-sequencing-operator-attestation-ledger-audit]]"
  - "[[2026-08-14-legal-attestation-packet-methodology-audit]]"
---

# `modelo-100-legal-attestation-review-batch-b` reference: `Modelo 100 legal-reference attestation review packet, Batch B (numeric rate/bracket/threshold tranche)`

This is **Batch B** of the Modelo 100 legal-attestation review series (119
references total, 74% of the remaining attestation burden across the seven
layout-capable modelos). Batch A (49 references, already self-flagged as
agent-transcribed and awaiting re-stamp) was written and accepted first.
Batch B is the 41 references, among the 70 that remain after Batch A, that
state a rate, bracket, threshold or amount somewhere in their bundled corpus
text -- isolated into its own sitting deliberately, so the live BOE
cross-check this class of reference needs becomes the explicit mode of the
whole batch rather than an occasional interruption across an undifferentiated
list. Batch C (the remaining 29, no numeric content) follows separately.

**This count moved twice, and both corrections are recorded rather than
silently absorbed, because the second one caught something the first
correction's own method still missed.**

First correction (31 to 37): the characterisation that originally proposed
this three-batch split computed the numeric flag from the legal catalogue's
own `required_text` and `notes` fields only. Resolving every reference's full
bundled corpus text to build this batch found six more references stating a
rate or amount only in body text a `required_text` anchor phrase never
quoted: `ley-35-2006:art-17`, `art-25`, `art-30`, `art-31`, `art-37`, and
`real-decreto-ley-7-2024:art-11`. This was already reported when this batch
was first submitted, and the general shape -- a catalogue-field scan
undercounts because `required_text` is usually a title or definitional
phrase, not the number-bearing sentence -- is recorded in
`legal-attestation-packet-methodology-audit`.

**Second correction (37 to 41), found while characterising Batch C and
applied here before either batch was finalized.** The phrase-adjacency text
scan used for the first correction looks for a number immediately followed
by "por ciento", "%", or "euros". That pattern misses a rate or threshold
laid out as a TABLE -- AEAT's own bracket-scale articles print "Base
liquidable / Cuota íntegra / Resto base liquidable / Tipo aplicable /
Porcentaje" as column headers with the actual figures (9,50 / 12,00 / 15,00
/ 18,50 / 22,50 / 24,50 and thresholds like 12.450,00 / 300.000,00) as bare
table cells, with no "por ciento" or "euros" token anywhere near the number
itself. Four references have exactly this shape and were misclassified into
the non-numeric remainder by the phrase-adjacency scan alone:
`ley-35-2006:art-63` (the state general IRPF scale itself -- the single
most consequential rate table in the whole Modelo 100 corpus),
`ley-35-2006:art-66` (the state savings-income scale), and `art-76` /
`art-76-2015` (the autonomous-community savings-income scale, current and
2015 redactions). A third detection signal -- table-header markers
("Tipo aplicable", "Porcentaje", "Base liquidable", "escala", "tipo de
gravamen") co-occurring with two or more bare decimal-comma numbers or a
euro-thousands-shaped figure -- was added and run against every reference in
Batches A and B; it found these four and nothing else (Batch A's own
non-numeric set was rechecked with the same detector and returned no
additional misses).

The trend across all three corrections is the finding worth stating plainly:
**every refinement of the numeric-flag method has moved references INTO this
batch, never out of it, and the two hardest-to-detect misses -- a number
with no adjacent unit word, and the state scale itself -- were also the two
most consequential to miss.** A catalogue-only scan is not merely
imprecise; it fails in the direction that would have sent an operator past a
bracket table with no signal to slow down. Both corrections are written up
in `legal-attestation-packet-methodology-audit` as a durable finding for
Batch C and any future packet, not just as history here.

For each reference this packet places the registry's own claim next to the
actual bundled corpus text it points at, quoted verbatim, and lists what in
Modelo 100 depends on it. It does not state whether the claim and the source
agree -- that is the operator's act, and stating it here would turn the
operator's sign-off into a rubber stamp on agent work. The one exception is a
structural discrepancy: a broken `corpus_ref`, a `required_text` phrase absent
from the quoted text, or a citation that plainly names a different subject.
**Zero of the 119 references across all three batches have triggered that
exception so far** (ten checked in Batch A's predecessor packets, forty-nine
in Batch A, forty-one here); all 41 `corpus_ref`s in this batch resolve and
every declared `required_text` phrase is present in the quoted text, checked
against the same production normaliser (`cadrumo.core.normalise_corpus_text`)
used throughout this series.

**Standing caveat on the `notes` and `reviewed_by` fields.** Every `notes` and
`reviewed_by` value quoted below is agent-authored registry content, not
operator-verified prose. Unlike Batch A, this is not this batch's defining
property -- Batch B is defined by numeric content, not by a self-verification
claim -- so most entries below carry a plain `"agent-review"` `reviewed_by`
value rather than a stated "already checked" claim. The caveat is stated once
here as a standing practice across the whole series, not because it recurs
distinctively in this batch the way it did in Batch A.

**Numeric grounding flag -- the defining property of this batch, not an
occasional note.** Per project rule, the bundled corpus text is preferred
evidence but not infallible on numbers: for any reference establishing a
rate, amount or threshold, a live BOE or AEAT consolidated-text cross-check
is the operator's to make -- no such fetch was performed here. Every one of
the 41 sections below carries its own `**Numeric flag**` line for that
reason; the whole batch is built around the assumption that this check is the
sitting's primary work, not an interruption inside it. The four table-shaped
entries carry a longer version of that line naming the detection method
explicitly, since their own registry `required_text` and `notes` gave no hint
of the figures inside.

**Quotation discipline, carried forward unchanged from Batch A and
`legal-attestation-packet-methodology-audit`'s finding.** Every substantive
paragraph of every bundled corpus text below is quoted in full, including the
bracket-scale tables of the four table-shaped entries above -- the actual
figures, not a description of them. The only material ever omitted is the
trailing BOE amendment-history citation footer ("Se modifica...", "Se
añade...", "Texto añadido..."), which is pure metadata and never carries a
`required_text` phrase or a numeric figure.

This document is read-only working material. No `operator_reviewed` stamp was
applied or could be applied through any path available to this session, and
nothing under `modelos/100/**` was touched to produce it.

## Summary

Forty-one sections follow, grouped into nine concept clusters so an operator
can work through related provisions together rather than an alphabetised
list: datos identificativos y familia, rendimientos del trabajo, rendimientos
de capital inmobiliario, rendimientos de capital mobiliario, actividades
económicas (estimación directa / objetiva), ganancias y pérdidas
patrimoniales, mínimos y base imponible / liquidable, deducciones y
regímenes especiales, cálculo del impuesto y regularización (which now
includes the four bracket-scale articles: `art-63`, `art-66`, `art-76`,
`art-76-2015`), and a short procedural cluster (the annual form-approval
órdenes' rate/threshold citations). Each section carries the same four parts
in the same order: the registry's current entry, the bundled corpus text
quoted verbatim, what in Modelo 100 depends on it, and the entry's current
review status, plus the `**Numeric flag**` line every section in this batch
carries.

## Datos identificativos y familia

### 1. `ley-35-2006:art-75`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a75`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2025-04-03
- `required_text`:
  - "Especialidades aplicables en los supuestos de anualidades por alimentos a favor de los hijos."
  - "satisfagan las anualidades por alimentos a sus hijos"
  - "aplicarán la escala prevista"
  - "mínimo personal y familiar"
  - "incrementado en 1.980 euros anuales"
  - "sin que pueda resultar negativa"
- `notes` (verbatim): "LIRPF art 75: autonomic-side special rule for judicial child-support annuities, applying the art 74 scale separately to those annuities and to the rest of the general taxable base. It is not the generic autonomic quota article; art 73 is the generic autonomic integral-quota article. Base legal for Modelo 100 annualidades por alimentos surfaces."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 75. Especialidades aplicables en los supuestos de anualidades por alimentos a favor de los hijos.
>
> Los contribuyentes que satisfagan las anualidades por alimentos a sus hijos previstas en la letra k) del artículo 7 sin derecho a la aplicación por estos últimos del mínimo por descendientes previsto en el artículo 58, cuando el importe de aquellas sea inferior a la base liquidable general, aplicarán la escala prevista en el número 1.º del apartado 1 del artículo anterior separadamente al importe de las anualidades por alimentos y al resto de la base liquidable general. La cuantía total resultante se minorará en el importe derivado de aplicar la escala prevista en el número 1.º del apartado 1 del artículo 74 a la parte de la base liquidable general correspondiente al mínimo personal y familiar que resulte de los incrementos o disminuciones a que se refiere el artículo 56.3, incrementado en 1.980 euros anuales, sin que pueda resultar negativa como consecuencia de tal minoración.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2025. 34 casilla(s); 3 construct(s); 4 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 2. `ley-35-2006:art-75-2015`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-75-2015.html#a75`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "aplicarán la escala prevista"
  - "mínimo personal y familiar"
  - "incrementado en 1.980 euros anuales"
  - "sin que pueda resultar negativa"
- `notes` (verbatim): "LIRPF art 75, redaction selected by BOE at 2014-11-28 (art. 1.50 Ley 26/2014, BOE-A-2014-12327), in force 2015-01-01 to 2025-04-02: unchanged text through the 2020-2023 filing years, before the Ley 1/2025 amendment took effect 2025-04-03. Grounds the 2020-2023 Modelo 100 anualidades por alimentos autonomic-quota specialty casillas and formulas."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 75. Especialidades aplicables en los supuestos de anualidades por alimentos a favor de los hijos.
>
> Los contribuyentes que satisfagan anualidades por alimentos a sus hijos por decisión judicial sin derecho a la aplicación por estos últimos del mínimo por descendientes previsto en el artículo 58 de esta Ley, cuando el importe de aquéllas sea inferior a la base liquidable general, aplicarán la escala prevista en el número 1.º del apartado 1 del artículo anterior separadamente al importe de las anualidades por alimentos y al resto de la base liquidable general. La cuantía total resultante se minorará en el importe derivado de aplicar la escala prevista en el número 1.º del apartado 1 del artículo 74 de esta Ley a la parte de la base liquidable general correspondiente al mínimo personal y familiar que resulte de los incrementos o disminuciones a que se refiere el artículo 56.3 de esta Ley, incrementado en 1.980 euros anuales, sin que pueda resultar negativa como consecuencia de tal minoración.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024. 1 binding(s); 34 casilla(s); 7 construct(s); 18 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-02`.

## Rendimientos del trabajo

### 3. `ley-35-2006:art-17`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a17`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2020-02-06
- `required_text`:
  - "Rendimientos íntegros del trabajo."
  - "contraprestaciones o utilidades"
  - "trabajo personal o de la relación laboral o estatutaria"
  - "Las pensiones y haberes pasivos percibidos"
  - "se calificarán como rendimientos de actividades económicas"
- `notes` (verbatim): "LIRPF art 17: defines rendimientos integros del trabajo from employment, statutory, pension and similar sources, while excluding items that qualify as economic-activity income. Current consolidated redaction was published 2020-02-05 and is in force from 2020-02-06."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 17. Rendimientos íntegros del trabajo.
>
> 1. Se considerarán rendimientos íntegros del trabajo todas las contraprestaciones o utilidades, cualquiera que sea su denominación o naturaleza, dinerarias o en especie, que deriven, directa o indirectamente, del trabajo personal o de la relación laboral o estatutaria y no tengan el carácter de rendimientos de actividades económicas.
>
> Se incluirán, en particular:
>
> a) Los sueldos y salarios.
>
> b) Las prestaciones por desempleo.
>
> c) Las remuneraciones en concepto de gastos de representación.
>
> d) Las dietas y asignaciones para gastos de viaje, excepto los de locomoción y los normales de manutención y estancia en establecimientos de hostelería con los límites que reglamentariamente se establezcan.
>
> e) Las contribuciones o aportaciones satisfechas por los promotores de planes de pensiones previstos en el texto refundido de la Ley de regulación de los planes y fondos de pensiones, aprobado por el Real Decreto Legislativo 1/2002, de 29 de noviembre, o por las empresas promotoras previstas en la Directiva 2003/41/CE del Parlamento Europeo y del Consejo, de 3 de junio de 2003, relativa a las actividades y la supervisión de fondos de pensiones de empleo.
>
> f) Las contribuciones o aportaciones satisfechas por los empresarios para hacer frente a los compromisos por pensiones en los términos previstos por la disposición adicional primera del texto refundido de la Ley de regulación de los planes y fondos de pensiones, y en su normativa de desarrollo, cuando aquellas sean imputadas a las personas a quienes se vinculen las prestaciones. Esta imputación fiscal tendrá carácter voluntario en los contratos de seguro colectivo distintos de los planes de previsión social empresarial, debiendo mantenerse la decisión que se adopte respecto del resto de primas que se satisfagan hasta la extinción del contrato de seguro. No obstante, la imputación fiscal tendrá carácter obligatorio en los contratos de seguro de riesgo. Cuando los contratos de seguro cubran conjuntamente las contingencias de jubilación y de fallecimiento o incapacidad, será obligatoria la imputación fiscal de la parte de las primas satisfechas que corresponda al capital en riesgo por fallecimiento o incapacidad, siempre que el importe de dicha parte exceda de 50 euros anuales. A estos efectos se considera capital en riesgo la diferencia entre el capital asegurado para fallecimiento o incapacidad y la provisión matemática.
>
> No obstante lo previsto en el párrafo anterior, en todo caso, la imputación fiscal de primas de los contratos de seguro antes señalados será obligatoria por el importe que exceda de 100.000 euros anuales por contribuyente y respecto del mismo empresario, salvo en los seguros colectivos contratados a consecuencia de despidos colectivos realizados de conformidad con lo dispuesto en el artículo 51 del Estatuto de los Trabajadores.
>
> 2. En todo caso, tendrán la consideración de rendimientos del trabajo:
>
> a) Las siguientes prestaciones:
>
> 1.ª Las pensiones y haberes pasivos percibidos de los regímenes públicos de la Seguridad Social y clases pasivas y demás prestaciones públicas por situaciones de incapacidad, jubilación, accidente, enfermedad, viudedad, o similares, sin perjuicio de lo dispuesto en el artículo 7 de esta Ley.
>
> 2.ª Las prestaciones percibidas por los beneficiarios de mutualidades generales obligatorias de funcionarios, colegios de huérfanos y otras entidades similares.
>
> 3.ª Las prestaciones percibidas por los beneficiarios de planes de pensiones y las percibidas de los planes de pensiones regulados en la Directiva (UE) 2016/2341 del Parlamento Europeo y del Consejo, de 14 de diciembre de 2016, relativa a las actividades y la supervisión de fondos de pensiones de empleo.
>
> Asimismo, las cantidades percibidas en los supuestos contemplados en el artículo 8.8 del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones, aprobado por el Real Decreto Legislativo 1/2002, de 29 de noviembre, tendrán el mismo tratamiento fiscal que las prestaciones de los planes de pensiones.
>
> 4.ª Las prestaciones percibidas por los beneficiarios de contratos de seguros concertados con mutualidades de previsión social, cuyas aportaciones hayan podido ser, al menos en parte, gasto deducible para la determinación del rendimiento neto de actividades económicas, u objeto de reducción en la base imponible del Impuesto.
>
> En el supuesto de prestaciones por jubilación e invalidez derivadas de dichos contratos, se integrarán en la base imponible en el importe de la cuantía percibida que exceda de las aportaciones que no hayan podido ser objeto de reducción o minoración en la base imponible del Impuesto, por incumplir los requisitos subjetivos previstos en el párrafo a) del apartado 2 del artículo 51 o en la disposición adicional novena de esta Ley.
>
> 5.ª Las prestaciones percibidas por los beneficiarios de los planes de previsión social empresarial.
>
> Asimismo, las prestaciones por jubilación e invalidez percibidas por los beneficiarios de contratos de seguro colectivo, distintos de los planes de previsión social empresarial, que instrumenten los compromisos por pensiones asumidos por las empresas, en los términos previstos en la disposición adicional primera del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones, y en su normativa de desarrollo, en la medida en que su cuantía exceda de las contribuciones imputadas fiscalmente y de las aportaciones directamente realizadas por el trabajador.
>
> 6.ª Las prestaciones percibidas por los beneficiarios de los planes de previsión asegurados.
>
> 7.ª Las prestaciones percibidas por los beneficiarios de los seguros de dependencia conforme a lo dispuesto en la Ley de promoción de la autonomía personal y atención a las personas en situación de dependencia.
>
> b) Las cantidades que se abonen, por razón de su cargo, a los diputados españoles en el Parlamento Europeo, a los diputados y senadores de las Cortes Generales, a los miembros de las asambleas legislativas autonómicas, concejales de ayuntamiento y miembros de las diputaciones provinciales, cabildos insulares u otras entidades locales, con exclusión, en todo caso, de la parte de aquellas que dichas instituciones asignen para gastos de viaje y desplazamiento.
>
> c) Los rendimientos derivados de impartir cursos, conferencias, coloquios, seminarios y similares.
>
> d) Los rendimientos derivados de la elaboración de obras literarias, artísticas o científicas, siempre que se ceda el derecho a su explotación.
>
> e) Las retribuciones de los administradores y miembros de los Consejos de Administración, de las Juntas que hagan sus veces y demás miembros de otros órganos representativos.
>
> f) Las pensiones compensatorias recibidas del cónyuge y las anualidades por alimentos, sin perjuicio de lo dispuesto en el artículo 7 de esta Ley.
>
> g) Los derechos especiales de contenido económico que se reserven los fundadores o promotores de una sociedad como remuneración de servicios personales.
>
> h) Las becas, sin perjuicio de lo dispuesto en el artículo 7 de esta Ley.
>
> i) Las retribuciones percibidas por quienes colaboren en actividades humanitarias o de asistencia social promovidas por entidades sin ánimo de lucro.
>
> j) Las retribuciones derivadas de relaciones laborales de carácter especial.
>
> k) Las aportaciones realizadas al patrimonio protegido de las personas con discapacidad en los términos previstos en la disposición adicional decimoctava de esta Ley.
>
> 3. No obstante, cuando los rendimientos a que se refieren los párrafos c) y d) del apartado anterior y los derivados de la relación laboral especial de los artistas en espectáculos públicos y de la relación laboral especial de las personas que intervengan en operaciones mercantiles por cuenta de uno o más empresarios sin asumir el riesgo y ventura de aquéllas supongan la ordenación por cuenta propia de medios de producción y de recursos humanos o de uno de ambos, con la finalidad de intervenir en la producción o distribución de bienes o servicios, se calificarán como rendimientos de actividades económicas.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 36 casilla(s); 10 construct(s); 18 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 4. `ley-35-2006:art-18`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a18`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Porcentajes de reducción aplicables a determinados rendimientos del trabajo."
  - "El 30 por ciento de reducción"
  - "período de generación superior a dos años"
  - "300.000 euros anuales"
- `notes` (verbatim): "LIRPF art 18: governs reduction percentages for certain work income, including the 30 percent reduction for qualifying irregular or multi-year work income and the 300,000 EUR annual base cap. Current consolidated redaction was published 2014-11-28 and is in force from 2015-01-01."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 18. Porcentajes de reducción aplicables a determinados rendimientos del trabajo.
>
> 1. Como regla general, los rendimientos íntegros se computarán en su totalidad, salvo que les resulte de aplicación alguno de los porcentajes de reducción a los que se refieren los apartados siguientes. Dichos porcentajes no resultarán de aplicación cuando la prestación se perciba en forma de renta.
>
> 2. El 30 por ciento de reducción, en el caso de rendimientos íntegros distintos de los previstos en el artículo 17.2. a) de esta Ley que tengan un período de generación superior a dos años, así como aquellos que se califiquen reglamentariamente como obtenidos de forma notoriamente irregular en el tiempo, cuando, en ambos casos, sin perjuicio de lo dispuesto en el párrafo siguiente, se imputen en un único período impositivo.
>
> Tratándose de rendimientos derivados de la extinción de una relación laboral, común o especial, se considerará como período de generación el número de años de servicio del trabajador. En caso de que estos rendimientos se cobren de forma fraccionada, el cómputo del período de generación deberá tener en cuenta el número de años de fraccionamiento, en los términos que reglamentariamente se establezcan. Estos rendimientos no se tendrán en cuenta a efectos de lo establecido en el párrafo siguiente.
>
> No obstante, esta reducción no resultará de aplicación a los rendimientos que tengan un período de generación superior a dos años cuando, en el plazo de los cinco períodos impositivos anteriores a aquél en el que resulten exigibles, el contribuyente hubiera obtenido otros rendimientos con período de generación superior a dos años, a los que hubiera aplicado la reducción prevista en este apartado.
>
> La cuantía del rendimiento íntegro a que se refiere este apartado sobre la que se aplicará la citada reducción no podrá superar el importe de 300.000 euros anuales.
>
> Sin perjuicio del límite previsto en el párrafo anterior, en el caso de rendimientos del trabajo cuya cuantía esté comprendida entre 700.000,01 euros y 1.000.000 de euros y deriven de la extinción de la relación laboral, común o especial, o de la relación mercantil a que se refiere el artículo 17.2 e) de esta Ley, o de ambas, la cuantía del rendimiento sobre la que se aplicará la reducción no podrá superar el importe que resulte de minorar 300.000 euros en la diferencia entre la cuantía del rendimiento y 700.000 euros.
>
> Cuando la cuantía de tales rendimientos fuera igual o superior a 1.000.000 de euros, la cuantía de los rendimientos sobre la que se aplicará la reducción del 30 por ciento será cero.
>
> A estos efectos, la cuantía total del rendimiento del trabajo a computar vendrá determinada por la suma aritmética de los rendimientos del trabajo anteriormente indicados procedentes de la propia empresa o de otras empresas del grupo de sociedades en las que concurran las circunstancias previstas en el artículo 42 del Código de Comercio, con independencia del período impositivo al que se impute cada rendimiento.
>
> 3. El 30 por ciento de reducción, en el caso de las prestaciones establecidas en el artículo 17.2.a) 1.ª y 2.ª de esta Ley que se perciban en forma de capital, siempre que hayan transcurrido más de dos años desde la primera aportación.
>
> El plazo de dos años no resultará exigible en el caso de prestaciones por invalidez.
>
> 4. Las reducciones previstas en este artículo no se aplicarán a las contribuciones empresariales imputadas que reduzcan la base imponible, de acuerdo con lo dispuesto en los artículos 51, 53 y en la disposición adicional undécima de esta Ley.
>
> Se modifican los apartados 2 y 3 por el art. 1.10 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 20 casilla(s); 10 construct(s); 12 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 5. `ley-35-2006:art-19`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a19`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Rendimiento neto del trabajo."
  - "disminuir el rendimiento íntegro en el importe de los gastos deducibles"
  - "cotizaciones a la Seguridad Social"
  - "gastos de defensa jurídica"
  - "2.000 euros anuales"
- `notes` (verbatim): "LIRPF art 19: defines rendimiento neto del trabajo as gross work income reduced by deductible expenses, including Social Security or mutualidad contributions, passive-rights deductions, union/professional fees, legal-defence expenses and the general 2,000 EUR other-expenses deduction."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 19. Rendimiento neto del trabajo.
>
> 1. El rendimiento neto del trabajo será el resultado de disminuir el rendimiento íntegro en el importe de los gastos deducibles.
>
> 2. Tendrán la consideración de gastos deducibles exclusivamente los siguientes:
>
> a) Las cotizaciones a la Seguridad Social o a mutualidades generales obligatorias de funcionarios.
>
> b) Las detracciones por derechos pasivos.
>
> c) Las cotizaciones a los colegios de huérfanos o entidades similares.
>
> d) Las cuotas satisfechas a sindicatos y colegios profesionales, cuando la colegiación tenga carácter obligatorio, en la parte que corresponda a los fines esenciales de estas instituciones, y con el límite que reglamentariamente se establezca.
>
> e) Los gastos de defensa jurídica derivados directamente de litigios suscitados en la relación del contribuyente con la persona de la que percibe los rendimientos, con el límite de 300 euros anuales.
>
> f) En concepto de otros gastos distintos de los anteriores, 2.000 euros anuales.
>
> Tratándose de contribuyentes desempleados inscritos en la oficina de empleo que acepten un puesto de trabajo que exija el traslado de su residencia habitual a un nuevo municipio, en las condiciones que reglamentariamente se determinen, se incrementará dicha cuantía, en el periodo impositivo en el que se produzca el cambio de residencia y en el siguiente, en 2.000 euros anuales adicionales.
>
> Tratándose de personas con discapacidad que obtengan rendimientos del trabajo como trabajadores activos, se incrementará dicha cuantía en 3.500 euros anuales. Dicho incremento será de 7.750 euros anuales, para las personas con discapacidad que siendo trabajadores activos acrediten necesitar ayuda de terceras personas o movilidad reducida, o un grado de discapacidad igual o superior al 65 por ciento.
>
> Los gastos deducibles a que se refiere esta letra f) tendrán como límite el rendimiento íntegro del trabajo una vez minorado por el resto de gastos deducibles previstos en este apartado.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 29 casilla(s); 10 construct(s); 29 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 6. `ley-35-2006:art-20`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a20`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2024-01-01
- `required_text`:
  - "Reducción por obtención de rendimientos del trabajo."
  - "rendimientos netos del trabajo inferiores a 19.747,5 euros"
  - "no tengan rentas, excluidas las exentas, distintas de las del trabajo superiores a 6.500 euros"
  - "iguales o inferiores a 14.852 euros: 7.302 euros anuales"
  - "multiplicar por 1,75 la diferencia"
  - "multiplicar por 1,14 la diferencia"
  - "el saldo resultante no podrá ser negativo"
- `notes` (verbatim): "LIRPF art 20: current reduction for obtaining work income, modified by RDL 4/2024 art 3.1 with effects from 2024-01-01. The BOE selector redaction was published 2024-06-27 and is in force from 2024-06-28. Grounds M100 art-20 casillas, the reduced work-income formula, and the application advisory threshold."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 20. Reducción por obtención de rendimientos del trabajo.
>
> Los contribuyentes con rendimientos netos del trabajo inferiores a 19.747,5 euros siempre que no tengan rentas, excluidas las exentas, distintas de las del trabajo superiores a 6.500 euros, minorarán el rendimiento neto del trabajo en las siguientes cuantías:
>
> a) Contribuyentes con rendimientos netos del trabajo iguales o inferiores a 14.852 euros: 7.302 euros anuales.
>
> b) Contribuyentes con rendimientos netos del trabajo superiores a 14.852 euros, pero iguales o inferiores a 17.673,52 euros: 7.302 euros menos el resultado de multiplicar por 1,75 la diferencia entre el rendimiento del trabajo y 14.852 euros anuales.
>
> c) Contribuyentes con rendimientos netos del trabajo comprendidos entre 17.673,52 y 19.747,5 euros: 2.364,34 euros menos el resultado de multiplicar por 1,14 la diferencia entre el rendimiento del trabajo y 17.673,52 euros anuales.
>
> A estos efectos, el rendimiento neto del trabajo será el resultante de minorar el rendimiento íntegro en los gastos previstos en las letras a), b), c), d) y e) del artículo 19.2 de esta Ley.
>
> Como consecuencia de la aplicación de la reducción prevista en este artículo, el saldo resultante no podrá ser negativo.
>
> Se modifica, con efectos desde el 1 de enero de 2024, por el art. 3.1 del Real Decreto-ley 4/2024, de 26 de junio. Ref. BOE-A-2024-12944
>
> Se modifica por el art. 59.1 de la Ley 31/2022, de 23 de diciembre. Ref. BOE-A-2022-22128
>
> Se modifica por el art. 59.1 de la Ley 6/2018, de 3 de julio. Ref. BOE-A-2018-9268
>
> Se modifica por el art. 1.12 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Se modifica, con efectos desde 1 de enero de 2011, por el art. 60.1 de la Ley 39/2010, de 22 de diciembre. Ref. BOE-A-2010-19703.
>
> Se modifica, con vigencia exclusiva para el ejercicio 2010 por el art. 66.1 del a Ley 26/2009, de 23 de diciembre. Ref. BOE-A-2009-20765
>
> Se modifica, con vigencia exclusiva para el ejercicio 2009 por el art. 65.1 de la Ley 2/2008, de 23 de diciembre. Ref. BOE-A-2008-20744
>
> Se modifica, con vigencia exclusiva para el ejercicio 2008 por el art. 65.1 de la Ley 51/2007, de 28 de diciembre. Ref. BOE-A-2007-22295
>
> Sección 2.ª Rendimientos del capital

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 20 casilla(s); 10 construct(s); 6 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 7. `ley-35-2006:art-42.3.f`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a42`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2023-01-01
- `required_text`:
  - "Estarán exentos los siguientes rendimientos del trabajo en especie"
  - "entrega a los trabajadores en activo"
  - "acciones o participaciones"
  - "12.000 euros anuales"
  - "50.000 euros anuales"
- `notes` (verbatim): "LIRPF art 42.3.f: exencion de rendimientos del trabajo en especie por entrega gratuita o bajo precio de acciones o participaciones a trabajadores en activo, con limite general de 12.000 euros anuales y limite de 50.000 euros anuales para empresas emergentes."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 42. Rentas en especie.
>
> 1. Constituyen rentas en especie la utilización, consumo u obtención, para fines particulares, de bienes, derechos o servicios de forma gratuita o por precio inferior al normal de mercado, aun cuando no supongan un gasto real para quien las conceda.
>
> Cuando el pagador de las rentas entregue al contribuyente importes en metálico para que éste adquiera los bienes, derechos o servicios, la renta tendrá la consideración de dineraria.
>
> 2. No tendrán la consideración de rendimientos del trabajo en especie:
>
> a) Las cantidades destinadas a la actualización, capacitación o reciclaje del personal empleado, cuando vengan exigidos por el desarrollo de sus actividades o las características de los puestos de trabajo.
>
> b) Las primas o cuotas satisfechas por la empresa en virtud de contrato de seguro de accidente laboral o de responsabilidad civil del trabajador.
>
> 3. Estarán exentos los siguientes rendimientos del trabajo en especie:
>
> a) Las entregas a empleados de productos a precios rebajados que se realicen en cantinas o comedores de empresa o economatos de carácter social. Tendrán la consideración de entrega de productos a precios rebajados que se realicen en comedores de empresa las fórmulas indirectas de prestación del servicio cuya cuantía no supere la cantidad que reglamentariamente se determine, con independencia de que el servicio se preste en el propio local del establecimiento de hostelería o fuera de éste, previa recogida por el empleado o mediante su entrega en su centro de trabajo o en el lugar elegido por aquel para desarrollar su trabajo en los días en que este se realice a distancia o mediante teletrabajo.
>
> b) La utilización de los bienes destinados a los servicios sociales y culturales del personal empleado. Tendrán esta consideración, entre otros, los espacios y locales, debidamente homologados por la Administración pública competente, destinados por las empresas o empleadores a prestar el servicio de primer ciclo de educación infantil a los hijos de sus trabajadores, así como la contratación, directa o indirectamente, de este servicio con terceros debidamente autorizados, en los términos que reglamentariamente se establezcan.
>
> c) Las primas o cuotas satisfechas a entidades aseguradoras para la cobertura de enfermedad, cuando se cumplan los siguientes requisitos y límites:
>
> 1.º Que la cobertura de enfermedad alcance al propio trabajador, pudiendo también alcanzar a su cónyuge y descendientes.
>
> 2.º Que las primas o cuotas satisfechas no excedan de 500 euros anuales por cada una de las personas señaladas en el párrafo anterior o de 1.500 euros para cada una de ellas con discapacidad. El exceso sobre dicha cuantía constituirá retribución en especie.
>
> d) La prestación del servicio de educación preescolar, infantil, primaria, secundaria obligatoria, bachillerato y formación profesional por centros educativos autorizados, a los hijos de sus empleados, con carácter gratuito o por precio inferior al normal de mercado.
>
> e) Las cantidades satisfechas a las entidades encargadas de prestar el servicio público de transporte colectivo de viajeros con la finalidad de favorecer el desplazamiento de los empleados entre su lugar de residencia y el centro de trabajo, con el límite de 1.500 euros anuales para cada trabajador. También tendrán la consideración de cantidades satisfechas a las entidades encargadas de prestar el citado servicio público, las fórmulas indirectas de pago que cumplan las condiciones que se establezcan reglamentariamente.
>
> f) En los términos que reglamentariamente se establezcan, la entrega a los trabajadores en activo, de forma gratuita o por precio inferior al normal de mercado, de acciones o participaciones de la propia empresa o de otras empresas del grupo de sociedades, en la parte que no exceda, para el conjunto de las entregadas a cada trabajador, de 12.000 euros anuales, siempre que la oferta se realice en las mismas condiciones para todos los trabajadores de la empresa, grupo o subgrupos de empresa.
>
> La exención prevista en el párrafo anterior será de 50.000 euros anuales en el caso de entrega de acciones o participaciones concedidas a los trabajadores de una empresa emergente a las que se refiere la Ley 28/2022, de 21 de diciembre, de fomento del ecosistema de las empresas emergentes. En este supuesto, no será necesario que la oferta se realice en las condiciones señaladas en el párrafo anterior, debiendo efectuarse la misma dentro de la política retributiva general de la empresa y contribuir a la participación de los trabajadores en esta última. En el caso de que la entrega de acciones o participaciones sociales a que se refiere este párrafo derive del ejercicio de opciones de compra sobre acciones o participaciones previamente concedidas a los trabajadores por la empresa emergente, los requisitos para la consideración como empresa emergente deberán cumplirse en el momento de la concesión de la opción.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2023, 2024, 2025. 1 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-30`.

## Rendimientos de capital inmobiliario

### 8. `ley-35-2006:art-23`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a23`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2024-01-01
- `required_text`:
  - "Gastos deducibles y reducciones."
  - "gastos necesarios para la obtención de los rendimientos"
  - "el 3 por ciento sobre el mayor"
  - "el coste de adquisición satisfecho o el valor catastral"
  - "En un 90 por ciento"
  - "En un 70 por ciento"
  - "En un 60 por ciento"
  - "En un 50 por ciento"
- `notes` (verbatim): "LIRPF art 23: governs deductible expenses and reductions for real-estate capital income. Current consolidated redaction, published 2023-05-25 and effective for housing lease contracts from 2024-01-01, replaces the prior flat housing-rental reduction with 90/70/60/50 percent tiers and keeps the 3 percent amortization effectiveness rule."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 23. Gastos deducibles y reducciones.
>
> 1. Para la determinación del rendimiento neto, se deducirán de los rendimientos íntegros los gastos siguientes:
>
> a) Todos los gastos necesarios para la obtención de los rendimientos. Se considerarán gastos necesarios para la obtención de los rendimientos, entre otros, los siguientes:
>
> 1.º Los intereses de los capitales ajenos invertidos en la adquisición o mejora del bien, derecho o facultad de uso y disfrute del que procedan los rendimientos, y demás gastos de financiación, así como los gastos de reparación y conservación del inmueble. El importe total a deducir por estos gastos no podrá exceder, para cada bien o derecho, de la cuantía de los rendimientos íntegros obtenidos. El exceso se podrá deducir en los cuatro años siguientes de acuerdo con lo señalado en este número 1.º
>
> 2.º Los tributos y recargos no estatales, así como las tasas y recargos estatales, cualquiera que sea su denominación, siempre que incidan sobre los rendimientos computados o sobre el bien o derecho productor de aquéllos y no tengan carácter sancionador.
>
> 3.º Los saldos de dudoso cobro en las condiciones que se establezcan reglamentariamente.
>
> 4.º Las cantidades devengadas por terceros como consecuencia de servicios personales.
>
> b) Las cantidades destinadas a la amortización del inmueble y de los demás bienes cedidos con éste, siempre que respondan a su depreciación efectiva, en las condiciones que reglamentariamente se determinen. Tratándose de inmuebles, se entiende que la amortización cumple el requisito de efectividad si no excede del resultado de aplicar el 3 por ciento sobre el mayor de los siguientes valores: el coste de adquisición satisfecho o el valor catastral, sin incluir el valor del suelo.
>
> En el supuesto de rendimientos derivados de la titularidad de un derecho o facultad de uso o disfrute, será igualmente deducible en concepto de depreciación, con el límite de los rendimientos íntegros, la parte proporcional del valor de adquisición satisfecho, en las condiciones que reglamentariamente se determinen.
>
> 2. En los supuestos de arrendamiento de bienes inmuebles destinados a vivienda, el rendimiento neto positivo calculado con arreglo a lo dispuesto en el apartado anterior, se reducirá:
>
> a) En un 90 por ciento cuando se hubiera formalizado por el mismo arrendador un nuevo contrato de arrendamiento sobre una vivienda situada en una zona de mercado residencial tensionado, en el que la renta inicial se hubiera rebajado en más de un 5 por ciento en relación con la última renta del anterior contrato de arrendamiento de la misma vivienda, una vez aplicada, en su caso, la cláusula de actualización anual del contrato anterior.
>
> b) En un 70 por ciento cuando no cumpliéndose los requisitos señalados en la letra a) anterior, se produzca alguna de las circunstancias siguientes:
>
> 1.º Que el contribuyente hubiera alquilado por primera vez la vivienda, siempre que ésta se encuentre situada en una zona de mercado residencial tensionado y el arrendatario tenga una edad comprendida entre 18 y 35 años. Cuando existan varios arrendatarios de una misma vivienda, esta reducción se aplicará sobre la parte del rendimiento neto que proporcionalmente corresponda a los arrendatarios que cumplan los requisitos previstos en esta letra.
>
> 2.º Cuando el arrendatario sea una Administración Pública o entidad sin fines lucrativos a las que sea de aplicación el régimen especial regulado en el título II de la Ley 49/2002, de 23 de diciembre, de régimen fiscal de las entidades sin fines lucrativos y de los incentivos fiscales al mecenazgo, que destine la vivienda al alquiler social con una renta mensual inferior a la establecida en el programa de ayudas al alquiler del plan estatal de vivienda, o al alojamiento de personas en situación de vulnerabilidad económica a que se refiere la Ley 19/2021, de 20 de diciembre, por la que se establece el ingreso mínimo vital, o cuando la vivienda esté acogida a algún programa público de vivienda o calificación en virtud del cual la Administración competente establezca una limitación en la renta del alquiler.
>
> c) En un 60 por ciento cuando, no cumpliéndose los requisitos de las letras anteriores, la vivienda hubiera sido objeto de una actuación de rehabilitación en los términos previstos en el apartado 1 del artículo 41 del Reglamento del Impuesto que hubiera finalizado en los dos años anteriores a la fecha de la celebración del contrato de arrendamiento.
>
> d) En un 50 por ciento, en cualquier otro caso.
>
> Los requisitos señalados deberán cumplirse en el momento de celebrar el contrato de arrendamiento, siendo la reducción aplicable mientras se sigan cumpliendo los mismos.
>
> Estas reducciones sólo resultarán aplicables sobre los rendimientos netos positivos que hayan sido calculados por el contribuyente en una autoliquidación presentada antes de que se haya iniciado un procedimiento de verificación de datos, de comprobación limitada o de inspección que incluya en su objeto la comprobación de tales rendimientos.
>
> En ningún caso resultarán de aplicación las reducciones respecto de la parte de los rendimientos netos positivos derivada de ingresos no incluidos o de gastos indebidamente deducidos en la autoliquidación del contribuyente y que se regularicen en alguno de los procedimientos citados en el párrafo anterior, incluso cuando esas circunstancias hayan sido declaradas o aceptadas por el contribuyente durante la tramitación del procedimiento. Tampoco resultarán de aplicación las reducciones en relación con aquellos contratos de arrendamiento que incumplan lo dispuesto en el apartado 6 del artículo 17 de la Ley de Arrendamientos Urbanos.
>
> Las zonas de mercado residencial tensionado a las que podrá resultar de aplicación lo previsto en este apartado serán las recogidas en la resolución que, de acuerdo con lo dispuesto en la legislación estatal en materia de vivienda, apruebe el Ministerio de Transportes, Movilidad y Agenda urbana.
>
> 3. Los rendimientos netos con un período de generación superior a dos años, así como los que se califiquen reglamentariamente como obtenidos de forma notoriamente irregular en el tiempo, se reducirán en un 30 por ciento, cuando, en ambos casos, se imputen en un único período impositivo.
>
> La cuantía del rendimiento neto a que se refiere este apartado sobre la que se aplicará la citada reducción no podrá superar el importe de 300.000 euros anuales.
>
> Se modifica el apartado 2 por la disposición final 2.1 de la Ley 12/2023, de 24 de mayo, con efectos para los contratos de arrendamiento de vivienda celebrados a partir de la entrada en vigor de esta Ley. Ref. BOE-A-2023-12203
>
> Esta modificación entra en vigor el 1 de enero de 2024, según establece la disposición final 9 de la citada Ley.
>
> Se modifica el apartado 2 por el art. 3.2 de la Ley 11/2021, de 9 de julio. Ref. BOE-A-2021-11473
>
> Se modifican los apartados 2 y 3 por el art. 1.13 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 1 binding(s); 136 casilla(s); 18 construct(s); 39 formula(s); 60 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 9. `ley-35-2006:art-25`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a25`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Rendimientos íntegros del capital mobiliario."
  - "Rendimientos obtenidos por la participación en los fondos propios"
  - "Los dividendos"
  - "Rendimientos obtenidos por la cesión a terceros de capitales propios"
  - "intereses y cualquier otra forma de retribución"
  - "Otros rendimientos del capital mobiliario"
- `notes` (verbatim): "LIRPF art 25: defines gross movable-capital income: participation in entity own funds, third-party lending/interest, capitalization and life/disability insurance operations, and other movable-capital yields such as intellectual-property, assistance, movable-rental and image-right income."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 25. Rendimientos íntegros del capital mobiliario.
>
> Tendrán la consideración de rendimientos íntegros del capital mobiliario los siguientes:
>
> 1. Rendimientos obtenidos por la participación en los fondos propios de cualquier tipo de entidad.
>
> Quedan incluidos dentro de esta categoría los siguientes rendimientos, dinerarios o en especie:
>
> a) Los dividendos, primas de asistencia a juntas y participaciones en los beneficios de cualquier tipo de entidad.
>
> b) Los rendimientos procedentes de cualquier clase de activos, excepto la entrega de acciones liberadas que, estatutariamente o por decisión de los órganos sociales, faculten para participar en los beneficios, ventas, operaciones, ingresos o conceptos análogos de una entidad por causa distinta de la remuneración del trabajo personal.
>
> c) Los rendimientos que se deriven de la constitución o cesión de derechos o facultades de uso o disfrute, cualquiera que sea su denominación o naturaleza, sobre los valores o participaciones que representen la participación en los fondos propios de la entidad.
>
> d) Cualquier otra utilidad, distinta de las anteriores, procedente de una entidad por la condición de socio, accionista, asociado o partícipe.
>
> e) La distribución de la prima de emisión de acciones o participaciones. El importe obtenido minorará, hasta su anulación, el valor de adquisición de las acciones o participaciones afectadas y el exceso que pudiera resultar tributará como rendimiento del capital mobiliario.
>
> No obstante lo dispuesto en el párrafo anterior, en el caso de distribución de la prima de emisión correspondiente a valores no admitidos a negociación en alguno de los mercados regulados de valores definidos en la Directiva 2004/39/CE del Parlamento Europeo y del Consejo, de 21 de abril de 2004, relativa a los mercados de instrumentos financieros, y representativos de la participación en fondos propios de sociedades o entidades, cuando la diferencia entre el valor de los fondos propios de las acciones o participaciones correspondiente al último ejercicio cerrado con anterioridad a la fecha de la distribución de la prima y su valor de adquisición sea positiva, el importe obtenido o el valor normal de mercado de los bienes o derechos recibidos se considerará rendimiento del capital mobiliario con el límite de la citada diferencia positiva.
>
> A estos efectos, el valor de los fondos propios a que se refiere el párrafo anterior se minorará en el importe de los beneficios repartidos con anterioridad a la fecha de la distribución de la prima de emisión, procedentes de reservas incluidas en los citados fondos propios, así como en el importe de las reservas legalmente indisponibles incluidas en dichos fondos propios que se hubieran generado con posterioridad a la adquisición de las acciones o participaciones.
>
> El exceso sobre el citado límite minorará el valor de adquisición de las acciones o participaciones conforme a lo dispuesto en el primer párrafo de esta letra e).
>
> Cuando por aplicación de lo dispuesto en el párrafo segundo de esta letra e) la distribución de la prima de emisión hubiera determinado el cómputo como rendimiento del capital mobiliario de la totalidad o parte del importe obtenido o del valor normal de mercado de los bienes o derechos recibidos, y con posterioridad el contribuyente obtuviera dividendos o participaciones en beneficios conforme al artículo 25.1 a) de esta Ley procedentes de la misma entidad en relación con acciones o participaciones que hubieran permanecido en su patrimonio desde la distribución de la prima de emisión, el importe obtenido de los dividendos o participaciones en beneficios minorará, con el límite de los rendimientos del capital mobiliario previamente computados que correspondan a las citadas acciones o participaciones, el valor de adquisición de las mismas conforme a lo dispuesto en el primer párrafo de esta letra e).
>
> 2. Rendimientos obtenidos por la cesión a terceros de capitales propios.
>
> Tienen esta consideración las contraprestaciones de todo tipo, cualquiera que sea su denominación o naturaleza, dinerarias o en especie, como los intereses y cualquier otra forma de retribución pactada como remuneración por tal cesión, así como las derivadas de la transmisión, reembolso, amortización, canje o conversión de cualquier clase de activos representativos de la captación y utilización de capitales ajenos.
>
> a) En particular, tendrán esta consideración:
>
> 1.º Los rendimientos procedentes de cualquier instrumento de giro, incluso los originados por operaciones comerciales, a partir del momento en que se endose o transmita, salvo que el endoso o cesión se haga como pago de un crédito de proveedores o suministradores.
>
> 2.º La contraprestación, cualquiera que sea su denominación o naturaleza, derivada de cuentas en toda clase de instituciones financieras, incluyendo las basadas en operaciones sobre activos financieros.
>
> 3.º Las rentas derivadas de operaciones de cesión temporal de activos financieros con pacto de recompra.
>
> 4.º Las rentas satisfechas por una entidad financiera, como consecuencia de la transmisión, cesión o transferencia, total o parcial, de un crédito titularidad de aquélla.
>
> b) En el caso de transmisión, reembolso, amortización, canje o conversión de valores, se computará como rendimiento la diferencia entre el valor de transmisión, reembolso, amortización, canje o conversión de los mismos y su valor de adquisición o suscripción.
>
> Como valor de canje o conversión se tomará el que corresponda a los valores que se reciban.
>
> Los gastos accesorios de adquisición y enajenación serán computados para la cuantificación del rendimiento, en tanto se justifiquen adecuadamente.
>
> Los rendimientos negativos derivados de transmisiones de activos financieros, cuando el contribuyente hubiera adquirido activos financieros homogéneos dentro de los dos meses anteriores o posteriores a dichas transmisiones, se integrarán a medida que se transmitan los activos financieros que permanezcan en el patrimonio del contribuyente.
>
> 3. Rendimientos procedentes de operaciones de capitalización, de contratos de seguro de vida o invalidez y de rentas derivadas de la imposición de capitales.
>
> a) Rendimientos dinerarios o en especie procedentes de operaciones de capitalización y de contratos de seguro de vida o invalidez, excepto cuando, con arreglo a lo previsto en el artículo 17.2.a) de esta Ley, deban tributar como rendimientos del trabajo.
>
> En particular, se aplicarán a estos rendimientos de capital mobiliario las siguientes reglas:
>
> 1.º) Cuando se perciba un capital diferido, el rendimiento del capital mobiliario vendrá determinado por la diferencia entre el capital percibido y el importe de las primas satisfechas.
>
> No obstante lo anterior, si el contrato de seguro combina la contingencia de supervivencia con las de fallecimiento o incapacidad y el capital percibido corresponde a la contingencia de supervivencia, podrá detraerse también la parte de las primas satisfechas que corresponda al capital en riesgo por fallecimiento o incapacidad que se haya consumido hasta el momento, siempre que durante toda la vigencia del contrato, el capital en riesgo sea igual o inferior al cinco por ciento de la provisión matemática. A estos efectos se considera capital en riesgo la diferencia entre el capital asegurado para fallecimiento o incapacidad y la provisión matemática.
>
> 2.º) En el caso de rentas vitalicias inmediatas, que no hayan sido adquiridas por herencia, legado o cualquier otro título sucesorio, se considerará rendimiento de capital mobiliario el resultado de aplicar a cada anualidad los porcentajes siguientes:
>
> 40 por ciento, cuando el perceptor tenga menos de 40 años.
>
> 35 por ciento, cuando el perceptor tenga entre 40 y 49 años.
>
> 28 por ciento, cuando el perceptor tenga entre 50 y 59 años.
>
> 24 por ciento, cuando el perceptor tenga entre 60 y 65 años.
>
> 20 por ciento, cuando el perceptor tenga entre 66 y 69 años.
>
> 8 por ciento, cuando el perceptor tenga más de 70 años.
>
> Estos porcentajes serán los correspondientes a la edad del rentista en el momento de la constitución de la renta y permanecerán constantes durante toda su vigencia.
>
> 3.º) Si se trata de rentas temporales inmediatas, que no hayan sido adquiridas por herencia, legado o cualquier otro título sucesorio, se considerará rendimiento del capital mobiliario el resultado de aplicar a cada anualidad los porcentajes siguientes:
>
> 12 por ciento, cuando la renta tenga una duración inferior o igual a 5 años.
>
> 16 por ciento, cuando la renta tenga una duración superior a 5 e inferior o igual a 10 años.
>
> 20 por ciento, cuando la renta tenga una duración superior a 10 e inferior o igual a 15 años.
>
> 25 por ciento, cuando la renta tenga una duración superior a 15 años.
>
> 4.º) Cuando se perciban rentas diferidas, vitalicias o temporales, que no hayan sido adquiridas por herencia, legado o cualquier otro título sucesorio, se considerará rendimiento del capital mobiliario el resultado de aplicar a cada anualidad el porcentaje que corresponda de los previstos en los números 2.º) y 3.º) anteriores, incrementado en la rentabilidad obtenida hasta la constitución de la renta, en la forma que reglamentariamente se determine. Cuando las rentas hayan sido adquiridas por donación o cualquier otro negocio jurídico a título gratuito e inter vivos, el rendimiento del capital mobiliario será, exclusivamente, el resultado de aplicar a cada anualidad el porcentaje que corresponda de los previstos en los números 2.º) y 3.º) anteriores.
>
> No obstante lo previsto en el párrafo anterior, en los términos que reglamentariamente se establezcan, las prestaciones por jubilación e invalidez percibidas en forma de renta por los beneficiarios de contratos de seguro de vida o invalidez, distintos de los establecidos en el artículo 17.2. a), y en los que no haya existido ningún tipo de movilización de las provisiones del contrato de seguro durante su vigencia, se integrarán en la base imponible del impuesto, en concepto de rendimientos del capital mobiliario, a partir del momento en que su cuantía exceda de las primas que hayan sido satisfechas en virtud del contrato o, en el caso de que la renta haya sido adquirida por donación o cualquier otro negocio jurídico a título gratuito e inter vivos, cuando excedan del valor actual actuarial de las rentas en el momento de la constitución de éstas. En estos casos no serán de aplicación los porcentajes previstos en los números 2.º) y 3.º) anteriores. Para la aplicación de este régimen será necesario que el contrato de seguro se haya concertado, al menos, con dos años de anterioridad a la fecha de jubilación.
>
> 5.º) En el caso de extinción de las rentas temporales o vitalicias, que no hayan sido adquiridas por herencia, legado o cualquier otro título sucesorio, cuando la extinción de la renta tenga su origen en el ejercicio del derecho de rescate, el rendimiento del capital mobiliario será el resultado de sumar al importe del rescate las rentas satisfechas hasta dicho momento y de restar las primas satisfechas y las cuantías que, de acuerdo con los párrafos anteriores de este apartado, hayan tributado como rendimientos del capital mobiliario. Cuando las rentas hayan sido adquiridas por donación o cualquier otro negocio jurídico a título gratuito e inter vivos, se restará, adicionalmente, la rentabilidad acumulada hasta la constitución de las rentas.
>
> 6.°) Los seguros de vida o invalidez que prevean prestaciones en forma de capital y dicho capital se destine a la constitución de rentas vitalicias o temporales, siempre que esta posibilidad de conversión se recoja en el contrato de seguro, tributarán de acuerdo con lo establecido en el primer párrafo del número 4.° anterior. En ningún caso, resultará de aplicación lo dispuesto en este número cuando el capital se ponga a disposición del contribuyente por cualquier medio.
>
> b) Las rentas vitalicias u otras temporales que tengan por causa la imposición de capitales, salvo cuando hayan sido adquiridas por herencia, legado o cualquier otro título sucesorio. Se considerará rendimiento del capital mobiliario el resultado de aplicar a cada anualidad los porcentajes previstos por los números 2.º) y 3.º) de la letra a) de este apartado para las rentas, vitalicias o temporales, inmediatas derivadas de contratos de seguro de vida.
>
> 4. Otros rendimientos del capital mobiliario.
>
> Quedan incluidos en este apartado, entre otros, los siguientes rendimientos, dinerarios o en especie:
>
> a) Los procedentes de la propiedad intelectual cuando el contribuyente no sea el autor y los procedentes de la propiedad industrial que no se encuentre afecta a actividades económicas realizadas por el contribuyente.
>
> b) Los procedentes de la prestación de asistencia técnica, salvo que dicha prestación tenga lugar en el ámbito de una actividad económica.
>
> c) Los procedentes del arrendamiento de bienes muebles, negocios o minas, así como los procedentes del subarrendamiento percibidos por el subarrendador, que no constituyan actividades económicas.
>
> d) Los procedentes de la cesión del derecho a la explotación de la imagen o del consentimiento o autorización para su utilización, salvo que dicha cesión tenga lugar en el ámbito de una actividad económica.
>
> 5. No tendrá la consideración de rendimiento de capital mobiliario, sin perjuicio de su tributación por el concepto que corresponda, la contraprestación obtenida por el contribuyente por el aplazamiento o fraccionamiento del precio de las operaciones realizadas en desarrollo de su actividad económica habitual.
>
> 6. En relación con los activos representativos de la captación y utilización de capitales ajenos a que se refiere el apartado 2 de este artículo, se estimará que no existe rendimiento del capital mobiliario en las transmisiones lucrativas de los mismos, por causa de muerte del contribuyente, ni se computará el rendimiento del capital mobiliario negativo derivado de la transmisión lucrativa de aquellos por actos "inter vivos".
>
> Se modifica la letra e) del apartado 1, el apartado 3.a).1 y el apartado 6 por el art. 1.14 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Redactado el apartado 3.2, párrafo 6 conforme a la corrección de errores publicada en BOE núm. 57, de 7 de marzo de 2007. Ref. BOE-A-2007-4731

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 45 casilla(s); 17 construct(s); 78 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 123, 126, 128, 193.

### 10. `ley-35-2006:art-26`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a26`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Gastos deducibles y reducciones."
  - "gastos de administración y depósito de valores negociables"
  - "arrendamiento de bienes muebles, negocios o minas"
  - "se reducirán en un 30 por ciento"
  - "300.000 euros anuales"
- `notes` (verbatim): "LIRPF art 26: governs deductible expenses and reductions for movable-capital income, including administration/deposit expenses for negotiable securities, necessary expenses for art 25.4-type income, and the 30 percent reduction for qualifying irregular or multi-year net income capped at 300,000 EUR."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 26. Gastos deducibles y reducciones.
>
> 1. Para la determinación del rendimiento neto, se deducirán de los rendimientos íntegros exclusivamente los gastos siguientes:
>
> a) Los gastos de administración y depósito de valores negociables. A estos efectos, se considerarán como gastos de administración y depósito aquellos importes que repercutan las empresas de servicios de inversión, entidades de crédito u otras entidades financieras que, de acuerdo con la Ley 24/1988, de 28 de julio, del Mercado de Valores, tengan por finalidad retribuir la prestación derivada de la realización por cuenta de sus titulares del servicio de depósito de valores representados en forma de títulos o de la administración de valores representados en anotaciones en cuenta.
>
> No serán deducibles las cuantías que supongan la contraprestación de una gestión discrecional e individualizada de carteras de inversión, en donde se produzca una disposición de las inversiones efectuadas por cuenta de los titulares con arreglo a los mandatos conferidos por éstos.
>
> b) Cuando se trate de rendimientos derivados de la prestación de asistencia técnica, del arrendamiento de bienes muebles, negocios o minas o de subarrendamientos, se deducirán de los rendimientos íntegros los gastos necesarios para su obtención y, en su caso, el importe del deterioro sufrido por los bienes o derechos de que los ingresos procedan.
>
> 2. Los rendimientos netos previstos en el apartado 4 del artículo 25 de esta Ley con un período de generación superior a dos años o que se califiquen reglamentariamente como obtenidos de forma notoriamente irregular en el tiempo, se reducirán en un 30 por ciento, cuando, en ambos casos, se imputen en un único período impositivo.
>
> La cuantía del rendimiento neto a que se refiere este apartado sobre la que se aplicará la citada reducción no podrá superar el importe de 300.000 euros anuales.
>
> Se modifica el apartado 2 por el art. 1.15 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Sección 3.ª Rendimientos de actividades económicas

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 28 casilla(s); 11 construct(s); 42 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 11. `ley-35-2006:art-30`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a30`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2018-01-01
- `required_text`:
  - "Normas para la determinación del rendimiento neto en estimación directa"
  - "método de estimación directa"
  - "normal y la simplificada"
  - "gastos de difícil justificación"
- `notes` (verbatim): "LIRPF art 30: regula la determinacion del rendimiento neto de actividades economicas por estimacion directa, sus modalidades normal y simplificada, y reglas especiales de gastos deducibles."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 30. Normas para la determinación del rendimiento neto en estimación directa.
>
> 1. La determinación de los rendimientos de actividades económicas se efectuará, con carácter general, por el método de estimación directa, admitiendo dos modalidades, la normal y la simplificada.
>
> La modalidad simplificada se aplicará para determinadas actividades económicas cuyo importe neto de cifra de negocios, para el conjunto de actividades desarrolladas por el contribuyente, no supere los 600.000 euros en el año inmediato anterior, salvo que renuncie a su aplicación, en los términos que reglamentariamente se establezcan.
>
> En los supuestos de renuncia o exclusión de la modalidad simplificada del método de estimación directa, el contribuyente determinará el rendimiento neto de todas sus actividades económicas por la modalidad normal de este método durante los tres años siguientes, en las condiciones que reglamentariamente se establezcan.
>
> 2. Junto a las reglas generales del artículo 28 de esta Ley se tendrán en cuenta las siguientes especiales:
>
> 1.ª No tendrán la consideración de gasto deducible las aportaciones a mutualidades de previsión social del propio empresario o profesional, sin perjuicio de lo previsto en el artículo 51 de esta Ley.
>
> No obstante, tendrán la consideración de gasto deducible las cantidades abonadas en virtud de contratos de seguro, concertados con mutualidades de previsión social por profesionales no integrados en el régimen especial de la Seguridad Social de los trabajadores por cuenta propia o autónomos, cuando, a efectos de dar cumplimiento a la obligación prevista en la disposición adicional decimoquinta de la Ley 30/1995, de 8 de noviembre, de ordenación y supervisión de los seguros privados, actúen como alternativas al régimen especial de la Seguridad Social mencionado, en la parte que tenga por objeto la cobertura de contingencias atendidas por dicho régimen especial, con el límite de la cuota máxima por contingencias comunes que esté establecida, en cada ejercicio económico, en el citado régimen especial.
>
> 2.ª Cuando resulte debidamente acreditado, con el oportuno contrato laboral y la afiliación al régimen correspondiente de la Seguridad Social, que el cónyuge o los hijos menores del contribuyente que convivan con él, trabajan habitualmente y con continuidad en las actividades económicas desarrolladas por el mismo, se deducirán, para la determinación de los rendimientos, las retribuciones estipuladas con cada uno de ellos, siempre que no sean superiores a las de mercado correspondientes a su cualificación profesional y trabajo desempeñado. Dichas cantidades se considerarán obtenidas por el cónyuge o los hijos menores en concepto de rendimientos de trabajo a todos los efectos tributarios.
>
> 3.ª Cuando el cónyuge o los hijos menores del contribuyente que convivan con él realicen cesiones de bienes o derechos que sirvan al objeto de la actividad económica de que se trate, se deducirá, para la determinación de los rendimientos del titular de la actividad, la contraprestación estipulada, siempre que no exceda del valor de mercado y, a falta de aquella, podrá deducirse la correspondiente a este último. La contraprestación o el valor de mercado se considerarán rendimientos del capital del cónyuge o los hijos menores a todos los efectos tributarios.
>
> Lo dispuesto en esta regla no será de aplicación cuando se trate de bienes y derechos que sean comunes a ambos cónyuges.
>
> 4.ª Reglamentariamente podrán establecerse reglas especiales para la cuantificación de determinados gastos deducibles en el caso de empresarios y profesionales en estimación directa simplificada, incluidos los de difícil justificación. La cuantía que con arreglo a dichas reglas especiales se determine para el conjunto de provisiones deducibles y gastos de difícil justificación no podrá ser superior a 2.000 euros anuales.
>
> 5.ª Tendrán la consideración de gasto deducible para la determinación del rendimiento neto en estimación directa:
>
> a) Las primas de seguro de enfermedad satisfechas por el contribuyente en la parte correspondiente a su propia cobertura y a la de su cónyuge e hijos menores de veinticinco años que convivan con él. El límite máximo de deducción será de 500 euros por cada una de las personas señaladas anteriormente o de 1.500 euros por cada una de ellas con discapacidad.
>
> b) En los casos en que el contribuyente afecte parcialmente su vivienda habitual al desarrollo de la actividad económica, los gastos de suministros de dicha vivienda, tales como agua, gas, electricidad, telefonía e Internet, en el porcentaje resultante de aplicar el 30 por ciento a la proporción existente entre los metros cuadrados de la vivienda destinados a la actividad respecto a su superficie total, salvo que se pruebe un porcentaje superior o inferior.
>
> c) Los gastos de manutención del propio contribuyente incurridos en el desarrollo de la actividad económica, siempre que se produzcan en establecimientos de restauración y hostelería y se abonen utilizando cualquier medio electrónico de pago, con los límites cuantitativos establecidos reglamentariamente para las dietas y asignaciones para gastos normales de manutención de los trabajadores.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 7 application_link(s); 35 binding(s); 190 casilla(s); 15 construct(s); 66 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 130.

### 12. `ley-35-2006:art-31`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a31`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2016-01-01
- `required_text`:
  - "Normas para la determinación del rendimiento neto en estimación objetiva"
  - "método de estimación objetiva"
  - "salvo que renuncien a su aplicación"
  - "signos, índices o módulos"
- `notes` (verbatim): "LIRPF art 31: regula la determinacion del rendimiento neto en estimacion objetiva, su renuncia o exclusion, sus limites reglamentarios y el uso de signos, indices o modulos."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 31. Normas para la determinación del rendimiento neto en estimación objetiva.
>
> 1. El método de estimación objetiva de rendimientos para determinadas actividades económicas se aplicará, en los términos que reglamentariamente se establezcan, con arreglo a las siguientes normas:
>
> 1.ª Los contribuyentes que reúnan las circunstancias previstas en las normas reguladoras de este método determinarán sus rendimientos conforme al mismo, salvo que renuncien a su aplicación, en los términos que reglamentariamente se establezcan.
>
> 2.ª El método de estimación objetiva se aplicará conjuntamente con los regímenes especiales establecidos en el Impuesto sobre el Valor Añadido o en el Impuesto General Indirecto Canario, cuando así se determine reglamentariamente.
>
> 3.ª Este método no podrá aplicarse por los contribuyentes cuando concurra cualquiera de las siguientes circunstancias, en las condiciones que se establezcan reglamentariamente:
>
> a) Que determinen el rendimiento neto de alguna actividad económica por el método de estimación directa.
>
> b) Que el volumen de rendimientos íntegros en el año inmediato anterior supere cualquiera de los siguientes importes:
>
> a´) Para el conjunto de sus actividades económicas, excepto las agrícolas, ganaderas y forestales, 150.000 euros anuales.
>
> A estos efectos se computará la totalidad de las operaciones con independencia de que exista o no obligación de expedir factura de acuerdo con lo dispuesto en el Reglamento por el que se regulan las obligaciones de facturación, aprobado por el Real Decreto 1619/2012, de 30 de noviembre.
>
> Sin perjuicio del límite anterior, el método de estimación objetiva no podrá aplicarse cuando el volumen de los rendimientos íntegros del año inmediato anterior que corresponda a operaciones por las que estén obligados a expedir factura cuando el destinatario sea un empresario o profesional que actúe como tal, de acuerdo con lo dispuesto en el artículo 2.2.a) del Reglamento por el que se regulan las obligaciones de facturación, supere 75.000 euros anuales.
>
> b´) Para el conjunto de sus actividades agrícolas, ganaderas y forestales, 250.000 euros anuales.
>
> A estos efectos, sólo se computarán las operaciones que deban anotarse en el Libro registro de ventas o ingresos previsto en el artículo 68.7 del Reglamento de este Impuesto.
>
> No obstante, a efectos de lo previsto en esta letra b), deberán computarse no solo las operaciones correspondientes a las actividades económicas desarrolladas por el contribuyente, sino también las correspondientes a las desarrolladas por el cónyuge, descendientes y ascendientes, así como por entidades en régimen de atribución de rentas en las que participen cualquiera de los anteriores, en las que concurran las siguientes circunstancias:
>
> – Que las actividades económicas desarrolladas sean idénticas o similares. A estos efectos, se entenderán que son idénticas o similares las actividades económicas clasificadas en el mismo grupo en el Impuesto sobre Actividades Económicas.
>
> – Que exista una dirección común de tales actividades, compartiéndose medios personales o materiales.
>
> Cuando en el año inmediato anterior se hubiese iniciado una actividad, el volumen de ingresos se elevará al año.
>
> c) Que el volumen de las compras en bienes y servicios, excluidas las adquisiciones de inmovilizado, en el ejercicio anterior supere la cantidad de 150.000 euros anuales. En el supuesto de obras o servicios subcontratados, el importe de los mismos se tendrá en cuenta para el cálculo de este límite.
>
> A estos efectos, deberán computarse no solo el volumen de compras correspondientes a las actividades económicas desarrolladas por el contribuyente, sino también las correspondientes a las desarrolladas por el cónyuge, descendientes y ascendientes, así como por entidades en régimen de atribución de rentas en las que participen cualquiera de los anteriores, en las que concurran las circunstancias señaladas en la letra b) anterior.
>
> Cuando en el año inmediato anterior se hubiese iniciado una actividad, el volumen de compras se elevará al año.
>
> d) Que las actividades económicas sean desarrolladas, total o parcialmente, fuera del ámbito de aplicación del Impuesto al que se refiere el artículo 4 de esta Ley.
>
> 4.ª El ámbito de aplicación del método de estimación objetiva se fijará, entre otros extremos, bien por la naturaleza de las actividades y cultivos, bien por módulos objetivos como el volumen de operaciones, el número de trabajadores, el importe de las compras, la superficie de las explotaciones o los activos fijos utilizados, con los límites que se determinen reglamentariamente para el conjunto de actividades desarrolladas por el contribuyente y, en su caso, por el cónyuge, descendientes y ascendientes, así como por entidades en régimen de atribución de rentas en las que participen cualquiera de los anteriores.
>
> 5.ª En los supuestos de renuncia o exclusión de la estimación objetiva, el contribuyente determinará el rendimiento neto de todas sus actividades económicas por el método de estimación directa durante los tres años siguientes, en las condiciones que reglamentariamente se establezcan.
>
> 2. El cálculo del rendimiento neto en la estimación objetiva se regulará por lo establecido en este artículo y las disposiciones que lo desarrollen.
>
> Las disposiciones reglamentarias se ajustarán a las siguientes reglas:
>
> 1.ª En el cálculo del rendimiento neto de las actividades económicas en estimación objetiva, se utilizarán los signos, índices o módulos generales o referidos a determinados sectores de actividad que determine el Ministro de Economía y Hacienda, habida cuenta de las inversiones realizadas que sean necesarias para el desarrollo de la actividad.
>
> 2.ª La aplicación del método de estimación objetiva nunca podrá dar lugar al gravamen de las ganancias patrimoniales que, en su caso, pudieran producirse por las diferencias entre los rendimientos reales de la actividad y los derivados de la correcta aplicación de estos métodos.
>
> Se modifica el apartado 1 por el art. 1.18 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Esta modificación entra en vigor el 1 de enero de 2016, según establece la disposición final 6.b.
>
> Se modifica el apartado 1, con efectos desde el 1 de enero de 2013, por el art. 3.1 de la Ley 7/2012, de 29 de octubre. Ref. BOE-A-2012-13416.
>
> Redactado conforme a la corrección de errores publicada en BOE núm. 31, de 5 de febrero de 2013. Ref. BOE-A-2013-1182.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 7 application_link(s); 1 binding(s); 189 casilla(s); 11 construct(s); 52 formula(s); 2 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 131.

### 13. `ley-35-2006:art-32`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a32`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2023-01-01
- `required_text`:
  - "Reducciones."
  - "rendimientos netos con un período de generación superior a dos años"
  - "el saldo resultante no podrá ser negativo"
  - "inicien el ejercicio de una actividad económica"
  - "no podrá superar el importe de 300.000 euros anuales"
- `notes` (verbatim): "LIRPF art 32: regula las reducciones aplicables a determinados rendimientos netos de actividades economicas, incluidos rendimientos irregulares, reducciones por requisitos reglamentarios y reduccion por inicio de actividad en estimacion directa."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 32. Reducciones.
>
> 1. Los rendimientos netos con un período de generación superior a dos años, así como aquéllos que se califiquen reglamentariamente como obtenidos de forma notoriamente irregular en el tiempo, se reducirán en un 30 por ciento, cuando, en ambos casos, se imputen en un único período impositivo.
>
> La cuantía del rendimiento neto a que se refiere este apartado sobre la que se aplicará la citada reducción no podrá superar el importe de 300.000 euros anuales.
>
> No resultará de aplicación esta reducción a aquellos rendimientos que, aun cuando individualmente pudieran derivar de actuaciones desarrolladas a lo largo de un período que cumpliera los requisitos anteriormente indicados, procedan del ejercicio de una actividad económica que de forma regular o habitual obtenga este tipo de rendimientos.
>
> 2. 1.º Cuando se cumplan los requisitos previstos en el número 2.º de este apartado, los contribuyentes podrán reducir el rendimiento neto de las actividades económicas en 2.000 euros.
>
> Adicionalmente, el rendimiento neto de estas actividades económicas se minorará en las siguientes cuantías:
>
> a) Cuando los rendimientos netos de actividades económicas sean inferiores a 19.747,5 euros, siempre que no tengan rentas, excluidas las exentas, distintas de las de actividades económicas superiores a 6.500 euros:
>
> a) Contribuyentes con rendimientos netos de actividades económicas iguales o inferiores a 14.047,5 euros: 6.498 euros anuales.
>
> b) Contribuyentes con rendimientos netos de actividades económicas comprendidos entre 14.047,5 y 19.747,5 euros: 6.498 euros menos el resultado de multiplicar por 1,14 la diferencia entre el rendimiento de actividades económicas y 14.047,5 euros anuales.
>
> b) Cuando se trate de personas con discapacidad que obtengan rendimientos netos derivados del ejercicio efectivo de estas actividades económicas, 3.500 euros anuales.
>
> Dicha reducción será de 7.750 euros anuales, para las personas con discapacidad que ejerzan de forma efectiva estas actividades económicas y acrediten necesitar ayuda de terceras personas o movilidad reducida, o un grado de discapacidad igual o superior al 65 por ciento.
>
> 2.º Para la aplicación de la reducción prevista en el número 1.º de este apartado será necesario el cumplimiento de los requisitos que se establezcan reglamentariamente, y en particular los siguientes:
>
> a) El rendimiento neto de la actividad económica deberá determinarse con arreglo al método de estimación directa. No obstante, si se determina con arreglo a la modalidad simplificada del método de estimación directa, la reducción será incompatible con lo previsto en la regla 4.ª del artículo 30.2 de esta Ley.
>
> b) La totalidad de sus entregas de bienes o prestaciones de servicios deben efectuarse a una única persona, física o jurídica, no vinculada en los términos del artículo 18 de la Ley 27/2014, de 27 de noviembre, del Impuesto sobre Sociedades, o que el contribuyente tenga la consideración de trabajador autónomo económicamente dependiente conforme a lo dispuesto en el Capítulo III del Título II de la Ley 20/2007, de 11 de julio, del Estatuto del trabajo autónomo y el cliente del que dependa económicamente no sea una entidad vinculada en los términos del artículo 18 de la Ley del Impuesto sobre Sociedades.
>
> c) El conjunto de gastos deducibles correspondientes a todas sus actividades económicas no puede exceder del 30 por ciento de sus rendimientos íntegros declarados.
>
> d) Deberán cumplirse durante el período impositivo todas las obligaciones formales y de información, control y verificación que reglamentariamente se determinen.
>
> e) Que no perciban rendimientos del trabajo en el período impositivo. No obstante, no se entenderá que se incumple este requisito cuando se perciban durante el período impositivo prestaciones por desempleo o cualesquiera de las prestaciones previstas en la letra a) del artículo 17.2 de esta Ley, siempre que su importe no sea superior a 4.000 euros anuales.
>
> f) Que al menos el 70 por ciento de los ingresos del período impositivo estén sujetos a retención o ingreso a cuenta.
>
> g) Que no realice actividad económica alguna a través de entidades en régimen de atribución de rentas.
>
> 3.º Cuando no se cumplan los requisitos previstos en el número 2.º de este apartado, los contribuyentes con rentas no exentas inferiores a 12.000 euros, incluidas las de la propia actividad económica, podrán reducir el rendimiento neto de las actividades económicas en las siguientes cuantías:
>
> a) Cuando la suma de las citadas rentas sea igual o inferior a 8.000 euros anuales: 1.620 euros anuales.
>
> b) Cuando la suma de las citadas rentas esté comprendida entre 8.000,01 y 12.000 euros anuales: 1.620 euros menos el resultado de multiplicar por 0,405 la diferencia entre las citadas rentas y 8.000 euros anuales.
>
> La reducción prevista en este número 3.º conjuntamente con la reducción prevista en el artículo 20 de esta Ley no podrá exceder de 3.700 euros.
>
> 4.º Como consecuencia de la aplicación de las reducciones previstas en este apartado, el saldo resultante no podrá ser negativo.
>
> 3. Los contribuyentes que inicien el ejercicio de una actividad económica y determinen el rendimiento neto de la misma con arreglo al método de estimación directa, podrán reducir en un 20 por ciento el rendimiento neto positivo declarado con arreglo a dicho método, minorado en su caso por las reducciones previstas en los apartados 1 y 2 anteriores, en el primer período impositivo en que el mismo sea positivo y en el período impositivo siguiente.
>
> A efectos de lo dispuesto en el párrafo anterior se entenderá que se inicia una actividad económica cuando no se hubiera ejercido actividad económica alguna en el año anterior a la fecha de inicio de la misma, sin tener en consideración aquellas actividades en cuyo ejercicio se hubiera cesado sin haber llegado a obtener rendimientos netos positivos desde su inicio.
>
> Cuando con posterioridad al inicio de la actividad a que se refiere el párrafo primero anterior se inicie una nueva actividad sin haber cesado en el ejercicio de la primera, la reducción prevista en este apartado se aplicará sobre los rendimientos netos obtenidos en el primer período impositivo en que los mismos sean positivos y en el período impositivo siguiente, a contar desde el inicio de la primera actividad.
>
> La cuantía de los rendimientos netos a que se refiere este apartado sobre la que se aplicará la citada reducción no podrá superar el importe de 100.000 euros anuales.
>
> No resultará de aplicación la reducción prevista en este apartado en el período impositivo en el que más del 50 por ciento de los ingresos del mismo procedan de una persona o entidad de la que el contribuyente hubiera obtenido rendimientos del trabajo en el año anterior a la fecha de inicio de la actividad.
>
> Se modifica el apartado 2.1º.a) por el art. 60.1 de la Ley 31/2022, de 23 de diciembre. Ref. BOE-A-2022-22128
>
> Se modifican los apartados 1 y 2 por el art. 1.19 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Se añade el apartado 3, con efectos desde 1 de enero de 2013, por el art. 8.3 de la Ley 11/2013, de 26 de julio. Ref. BOE-A-2013-8187.
>
> Téngase en cuenta que el apartado 3 ya fue añadido por el Real Decreto-ley 4/2013, de 22 de febrero.
>
> Se añade el apartado 3, con efectos desde 1 de enero de 2013, por el art. 8.3 del Real Decreto-ley 4/2013, de 22 de febrero. Ref. BOE-A-2013-2030.
>
> Se modifica el apartado 2.1, con efectos desde 1 de enero de 2010, por el art. 43 de la Ley 2/2011, de 4 de marzo. Ref. BOE-A-2011-4117.
>
> Se modifica el apartado 2.1, con efectos desde 1 de enero de 2011, por el art. 60.2 de la Ley 39/2010, de 22 de diciembre. Ref. BOE-A-2010-19703.
>
> Se modifica el apartado 2.1, con vigencia exclusiva para el ejercicio 2010 por el art. 66.2 de la Ley 26/2009, de 23 de diciembre. Ref. BOE-A-2009-20765
>
> Se modifica el apartado 2.1, con vigencia exclusiva para el ejercicio 2009 por el art. 65.2 de la Ley 2/2008, de 23 de diciembre. Ref. BOE-A-2008-20744
>
> Se modifica el apartado 2.1, con vigencia exclusiva para el ejercicio 2008 por el art. 65.2 de la Ley 51/2007, de 28 de diciembre. Ref. BOE-A-2007-22295
>
> Sección 4.ª Ganancias y pérdidas patrimoniales

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 7 application_link(s); 1 binding(s); 189 casilla(s); 15 construct(s); 27 formula(s); 2 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 14. `rd-439-2007:art-100`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/rd-439-2007-art-100.html#a100`
- `document_id`: `BOE-A-2007-6820`; `effective_from`: 2018-12-23
- `required_text`:
  - "arrendamiento o subarrendamiento de inmuebles urbanos"
  - "19 por ciento"
  - "excluido el Impuesto sobre el Valor Añadido"
  - "se reducirá en el 60 por ciento"
- `notes` (verbatim): "RIRPF art 100: base reglamentaria del importe de las retenciones sobre arrendamientos y subarrendamientos de inmuebles urbanos. Current consolidated text sets the 19 percent withholding rate on amounts paid to the lessor, excluding IVA, and the 60 percent Ceuta/Melilla reduction."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 100. Importe de las retenciones sobre arrendamientos y subarrendamientos de inmuebles.
>
> La retención a practicar sobre los rendimientos procedentes del arrendamiento o subarrendamiento de inmuebles urbanos, cualquiera que sea su calificación, será el resultado de aplicar el porcentaje del 19 por ciento sobre todos los conceptos que se satisfagan al arrendador, excluido el Impuesto sobre el Valor Añadido.
>
> Este porcentaje se reducirá en el 60 por ciento cuando el inmueble urbano esté situado en Ceuta o Melilla, en los términos previstos en el artículo 68.4 de la Ley del Impuesto.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 2 casilla(s); 4 construct(s); 2 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 115, 180.

## Actividades economicas (estimacion directa / objetiva)

### 15. `rd-439-2007:art-30`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/rd-439-2007-art-30.html#a30`
- `document_id`: `BOE-A-2007-6820`; `effective_from`: 2007-03-31
- `required_text`:
  - "Determinación del rendimiento neto en el método de estimación directa simplificada"
  - "gastos de difícil justificación"
  - "5 por ciento"
  - "2.000 euros anuales"
- `notes` (verbatim): "RIRPF art 30: reglas de estimacion directa simplificada para actividades economicas. Grounded in the bundled BOE HTML excerpt for the 5 percent difficult-to-justify-expenses rate and 2,000 EUR annual cap."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 30. Determinación del rendimiento neto en el método de estimación directa simplificada.
>
> El rendimiento neto de las actividades económicas, a las que sea de aplicación la modalidad simplificada del método de estimación directa, se determinará según las normas contenidas en los artículos 28 y 30 de la Ley del Impuesto, con las especialidades siguientes:
>
> 1.ª Las amortizaciones del inmovilizado material se practicarán de forma lineal, en función de la tabla de amortizaciones simplificada que se apruebe por el Ministro de Hacienda y Administraciones Públicas. Sobre las cuantías de amortización que resulten de estas tablas serán de aplicación las normas del régimen especial de entidades de reducida dimensión previstas en la Ley del Impuesto sobre Sociedades que afecten a este concepto.
>
> 2.ª El conjunto de las provisiones deducibles y los gastos de difícil justificación se cuantificará aplicando el porcentaje del 5 por ciento sobre el rendimiento neto, excluido este concepto, sin que la cuantía resultante pueda superar 2.000 euros anuales. No obstante, no resultará de aplicación dicho porcentaje de deducción cuando el contribuyente opte por la aplicación de la reducción prevista en el artículo 26.1 de este Reglamento.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 1 casilla(s); 6 construct(s); 11 formula(s); 12 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

## Ganancias y perdidas patrimoniales

### 16. `ley-35-2006:art-77`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a77`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Cuota líquida autonómica."
  - "La cuota líquida autonómica será el resultado de disminuir"
  - "50 por ciento del importe total de las deducciones"
  - "deducciones establecidas por la Comunidad Autónoma"
  - "no podrá ser negativo"
- `notes` (verbatim): "LIRPF art 77: defines the cuota liquida autonomica by reducing the prior autonomic tax amount through 50 percent of the art 68.2-68.5 deductions and the deductions established by the Comunidad Autonoma under Ley 22/2009, with a non-negative floor. Base legal para Modelo 100 casillas 0571 and 0586 and autonomic-deduction framework grounding."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 77. Cuota líquida autonómica.
>
> 1. La cuota líquida autonómica será el resultado de disminuir la cuota íntegra autonómica en la suma de:
>
> a) El 50 por ciento del importe total de las deducciones previstas en los apartados 2, 3, 4 y 5 del artículo 68 de esta Ley, con los límites y requisitos de situación patrimonial previstos en sus artículos 69 y 70.
>
> b) El importe de las deducciones establecidas por la Comunidad Autónoma en el ejercicio de las competencias previstas en la Ley 22/2009, de 18 de diciembre, por la que se regula el sistema de financiación de las Comunidades Autónomas de régimen común y Ciudades con Estatuto de Autonomía y se modifican determinadas normas tributarias.
>
> 2. El resultado de las operaciones a que se refiere el apartado anterior no podrá ser negativo.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 2 binding(s); 799 casilla(s); 9 construct(s); 85 formula(s); 4 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

## Minimos y base imponible / liquidable

### 17. `ley-35-2006:art-49`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-49.html#a49`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "La base imponible del ahorro estará constituida"
  - "con el límite del 25 por ciento"
  - "se compensará en los cuatro años siguientes"
  - "Las compensaciones previstas en el apartado anterior deberán efectuarse"
- `notes` (verbatim): "Base legal para la integracion y compensacion de rentas en la base imponible del ahorro en Modelo 100. The current consolidated text, effective from 2015-01-01 after Ley 26/2014, establishes the cross-bucket 25 percent limit and four-year carry-forward for negative savings-base balances. Distinct from art.48, which governs the base imponible general."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Ley 35/2006 Art. 49 — Integración y compensación de rentas en la base imponible del ahorro
>
> Artículo 49. Integración y compensación de rentas en la base imponible del ahorro.
>
> 1. La base imponible del ahorro estará constituida por el saldo positivo de sumar los
>
> siguientes saldos:
>
> a) El saldo positivo resultante de integrar y compensar, exclusivamente entre sí, en cada
>
> período impositivo, los rendimientos a que se refiere el artículo 46 de esta Ley. Si el
>
> resultado de la integración y compensación a que se refiere este párrafo arrojase saldo
>
> negativo, su importe se compensará con el saldo positivo de las rentas previstas en la letra b)
>
> de este apartado, obtenido en el mismo período impositivo, con el límite del 25 por ciento de
>
> dicho saldo positivo. Si tras dicha compensación quedase saldo negativo, su importe se
>
> compensará en los cuatro años siguientes en el mismo orden establecido en los párrafos
>
> anteriores.
>
> b) El saldo positivo resultante de integrar y compensar, exclusivamente entre sí, en cada
>
> período impositivo, las ganancias y pérdidas patrimoniales obtenidas en el mismo a que se
>
> refiere el artículo 46 de esta Ley. Si el resultado de la integración y compensación a que se
>
> refiere este párrafo arrojase saldo negativo, su importe se compensará con el saldo positivo de
>
> las rentas previstas en la letra a) de este apartado, obtenido en el mismo período impositivo,
>
> con el límite del 25 por ciento de dicho saldo positivo. Si tras dicha compensación quedase
>
> saldo negativo, su importe se compensará en los cuatro años siguientes en el mismo orden
>
> establecido en los párrafos anteriores.
>
> 2. Las compensaciones previstas en el apartado anterior deberán efectuarse en la cuantía
>
> máxima que permita cada uno de los ejercicios siguientes y sin que puedan practicarse fuera del
>
> plazo a que se refiere el apartado anterior mediante la acumulación a saldos negativos de
>
> ejercicios posteriores.
>
> IRPF — Ley 35/2006, compensación de saldos negativos del ahorro (Modelo 100)
>
> Los saldos negativos de la base imponible del ahorro (rendimientos del capital mobiliario y
>
> ganancias/pérdidas patrimoniales del ahorro) que no se compensen en el período impositivo se
>
> arrastran y compensan en los cuatro años siguientes, con el límite del 25 por
>
> ciento del saldo positivo de la otra clase de renta. Este arrastre de cuatro ejercicios es la
>
> ventana de compensación cross-renta que el Modelo 100 (declaración anual de IRPF) consume.
>
> Fuente: Ley 35/2006, de 28 de noviembre, del IRPF, artículo 49, redacción vigente
>
> (BOE-A-2006-20764, texto consolidado). Texto extraído verbatim del PDF consolidado oficial del
>
> BOE; grounding registrado en registry/aeat/legal/irpf.toml (ley-35-2006:art-49).

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 46 casilla(s); 19 construct(s); 78 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 714.

### 18. `ley-35-2006:art-52`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a52`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2023-01-01
- `required_text`:
  - "Límite de reducción."
  - "límite máximo conjunto"
  - "apartados 1, 2, 3, 4 y 5 del artículo 51"
  - "El 30 por 100 de la suma"
  - "1.500 euros anuales"
  - "En 8.500 euros anuales"
  - "rendimientos íntegros del trabajo superiores a 60.000 euros"
  - "En 4.250 euros anuales"
  - "cuantía máxima de reducción por aplicación de los incrementos"
  - "5.000 euros anuales para las primas a seguros colectivos de dependencia"
  - "podrán reducir en los cinco ejercicios siguientes"
- `notes` (verbatim): "LIRPF art 52: maximum joint limit for art 51.1-5 reductions. Current consolidated redaction was published 2022-12-24 and is in force from 2023-01-01 after Ley 31/2022 art 62.1; it sets the lesser-of 30 percent / 1,500 EUR limit, employment-plan/autonomo increments, the 8,500 EUR maximum increment cap, 5,000 EUR collective-dependence insurance amount, and five-year carry-forward for unapplied eligible contributions. Grounds M100 pension/prevision-social reductions and casilla 0468/2025 equivalent aggregation."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 52. Límite de reducción.
>
> 1. Como límite máximo conjunto para las reducciones previstas en los apartados 1, 2, 3, 4 y 5 del artículo 51 de esta ley, se aplicará la menor de las cantidades siguientes:
>
> a) El 30 por 100 de la suma de los rendimientos netos del trabajo y de actividades económicas percibidos individualmente en el ejercicio.
>
> b) 1.500 euros anuales.
>
> Este límite se incrementará en los siguientes supuestos, en las cuantías que se indican:
>
> 1.º En 8.500 euros anuales, siempre que tal incremento provenga de contribuciones empresariales, o de aportaciones del trabajador al mismo instrumento de previsión social por importe igual o inferior a las cantidades que resulten del siguiente cuadro en función del importe anual de la contribución empresarial:
>
> Importe anual de la contribución
>
> Aportación máxima del trabajador
>
> Igual o inferior a 500 euros.
>
> El resultado de multiplicar la contribución empresarial por 2,5.
>
> Entre 500,01 y 1.500 euros.
>
> 1.250 euros, más el resultado de multiplicar por 0,25 la diferencia entre la contribución empresarial y 500 euros.
>
> Más de 1.500 euros.
>
> El resultado de multiplicar la contribución empresarial por 1.
>
> No obstante, en todo caso se aplicará el multiplicador 1 cuando el trabajador obtenga en el ejercicio rendimientos íntegros del trabajo superiores a 60.000 euros procedentes de la empresa que realiza la contribución, a cuyo efecto la empresa deberá comunicar a la entidad gestora o aseguradora del instrumento de previsión social que no concurre esta circunstancia.
>
> A estos efectos, las cantidades aportadas por la empresa que deriven de una decisión del trabajador tendrán la consideración de aportaciones del trabajador.
>
> 2.º En 4.250 euros anuales, siempre que tal incremento provenga de aportaciones a los planes de pensiones sectoriales previstos en la letra a) del apartado 1 del artículo 67 del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones, realizadas por trabajadores por cuenta propia o autónomos que se adhieran a dichos planes por razón de su actividad; aportaciones a los planes de pensiones de empleo simplificados de trabajadores por cuenta propia o autónomos previstos en la letra c) del apartado 1 del artículo 67 del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones; o de aportaciones propias que el empresario individual o el profesional realice a planes de pensiones de empleo, de los que sea promotor y, además, partícipe o a Mutualidades de Previsión Social de las que sea mutualista, así como las que realice a planes de previsión social empresarial o seguros colectivos de dependencia de los que, a su vez, sea tomador y asegurado.
>
> En todo caso, la cuantía máxima de reducción por aplicación de los incrementos previstos en los números 1.º y 2.º anteriores será de 8.500 euros anuales.
>
> Además, 5.000 euros anuales para las primas a seguros colectivos de dependencia satisfechas por la empresa.
>
> 2. Los partícipes, mutualistas o asegurados que hubieran efectuado aportaciones a los sistemas de previsión social a que se refiere el artículo 51 de esta Ley, podrán reducir en los cinco ejercicios siguientes las cantidades aportadas incluyendo, en su caso, las aportaciones del promotor o las realizadas por la empresa que les hubiesen sido imputadas, que no hubieran podido ser objeto de reducción en la base imponible por insuficiencia de la misma o por aplicación del límite porcentual establecido en el apartado 1 anterior. Esta regla no resultará de aplicación a las aportaciones y contribuciones que excedan de los límites máximos previstos en el apartado 6 del artículo 51.
>
> Se modifica el apartado 1 por el art. 62.1 de la Ley 31/2022, de 23 de diciembre. Ref. BOE-A-2022-22128
>
> Se modifica el apartado 1 por la disposición final 1.1 de la Ley 12/2022, de 30 de junio. Ref. BOE-A-2022-10852
>
> Redactado conforme a la corrección de errores publicada en BOE núm. 240, de 6 de octubre de 2022. Ref. BOE-A-2022-16278

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2023, 2024, 2025. 83 casilla(s); 1 construct(s); 4 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 19. `ley-35-2006:art-52-2015`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-52-2015.html#a52`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Límite de reducción."
  - "límite máximo conjunto"
  - "apartados 1, 2, 3, 4 y 5 del artículo 51"
  - "El 30 por 100 de la suma"
  - "8.000 euros anuales"
  - "5.000 euros anuales para las primas a seguros colectivos de dependencia"
  - "podrán reducir en los cinco ejercicios siguientes"
- `notes` (verbatim): "LIRPF art 52, redaction selected by BOE at 2014-11-28 (art. 1.32 Ley 26/2014, BOE-A-2014-12327), in force 2015-01-01 to 2020-12-31: joint reduction limit was the lesser of 30 percent of net trabajo/actividades income or 8.000 euros annually, plus 5.000 euros for dependencia insurance premiums, before Ley 11/2020 art. 62.2 reduced the flat amount to 2.000 euros with effect from 2021-01-01. Grounds the 2020 Modelo 100 previsión social reduction casillas for the filing year the pre-2021 limit applied."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 52. Límite de reducción.
>
> 1. Como límite máximo conjunto para las reducciones previstas en los apartados 1, 2, 3, 4 y 5 del artículo 51 de esta Ley, se aplicará la menor de las cantidades siguientes:
>
> a) El 30 por 100 de la suma de los rendimientos netos del trabajo y de actividades económicas percibidos individualmente en el ejercicio.
>
> b) 8.000 euros anuales.
>
> Además, 5.000 euros anuales para las primas a seguros colectivos de dependencia satisfechas por la empresa.
>
> 2. Los partícipes, mutualistas o asegurados que hubieran efectuado aportaciones a los sistemas de previsión social a que se refiere el artículo 51 de esta Ley, podrán reducir en los cinco ejercicios siguientes las cantidades aportadas incluyendo, en su caso, las aportaciones del promotor o las realizadas por la empresa que les hubiesen sido imputadas, que no hubieran podido ser objeto de reducción en la base imponible por insuficiencia de la misma o por aplicación del límite porcentual establecido en el apartado 1 anterior. Esta regla no resultará de aplicación a las aportaciones y contribuciones que excedan de los límites máximos previstos en el apartado 6 del artículo 51.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020. 75 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-02`.

### 20. `ley-35-2006:art-52-2021`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-52-2021.html#a52`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2021-01-01
- `required_text`:
  - "Límite de reducción."
  - "El 30 por 100 de la suma"
  - "2.000 euros anuales"
  - "incrementará en 8.000 euros"
  - "contribuciones empresariales"
  - "5.000 euros anuales para las primas a seguros colectivos de dependencia"
- `notes` (verbatim): "LIRPF art 52, redaction selected by BOE at 2020-12-31 (art. 62.2 Ley 11/2020, BOE-A-2020-17339), in force 2021-01-01 to 2021-12-31: joint reduction limit was the lesser of 30 percent of net trabajo/actividades income or 2.000 euros annually, increased by 8.000 euros for empresarial contributions, plus 5.000 euros for dependencia insurance premiums, before the further tiered increase Ley 22/2021 introduced with effect from 2022-01-01. Grounds the 2021 Modelo 100 previsión social reduction casillas."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 52. Límite de reducción.
>
> 1. Como límite máximo conjunto para las reducciones previstas en los apartados 1, 2, 3, 4 y 5 del artículo 51 de esta Ley, se aplicará la menor de las cantidades siguientes:
>
> a) El 30 por 100 de la suma de los rendimientos netos del trabajo y de actividades económicas percibidos individualmente en el ejercicio.
>
> b) 2.000 euros anuales.
>
> Este límite se incrementará en 8.000 euros, siempre que tal incremento provenga de contribuciones empresariales.
>
> Las aportaciones propias que el empresario individual realice a planes de pensiones de empleo o a mutualidades de previsión social, de los que, a su vez, sea promotor y partícipe o mutualista, así como las que realice a planes de previsión social empresarial o seguros colectivos de dependencia de los que, a su vez, sea tomador y asegurado, se considerarán como contribuciones empresariales, a efectos del cómputo de este límite.
>
> Además, 5.000 euros anuales para las primas a seguros colectivos de dependencia satisfechas por la empresa.
>
> 2. Los partícipes, mutualistas o asegurados que hubieran efectuado aportaciones a los sistemas de previsión social a que se refiere el artículo 51 de esta Ley, podrán reducir en los cinco ejercicios siguientes las cantidades aportadas incluyendo, en su caso, las aportaciones del promotor o las realizadas por la empresa que les hubiesen sido imputadas, que no hubieran podido ser objeto de reducción en la base imponible por insuficiencia de la misma o por aplicación del límite porcentual establecido en el apartado 1 anterior. Esta regla no resultará de aplicación a las aportaciones y contribuciones que excedan de los límites máximos previstos en el apartado 6 del artículo 51.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2021. 96 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-02`.

### 21. `ley-35-2006:art-52-2022`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-52-2022.html#a52`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2022-07-02
- `required_text`:
  - "Límite de reducción."
  - "El 30 por 100 de la suma"
  - "1.500 euros anuales"
  - "En 8.500 euros anuales"
  - "5.000 euros anuales para las primas a seguros colectivos de dependencia"
- `notes` (verbatim): "LIRPF art 52, redaction selected by BOE at 2022-07-01 (disposición final 1.1 Ley 12/2022, BOE-A-2022-10852, corrected by the errata published 2022-10-06, BOE-A-2022-16278), in force 2022-07-02 to 2022-12-31: joint reduction limit is 1.500 euros annually, increased by 8.500 euros for empresarial/worker contributions (via the coeficiente table this redaction introduces) or 4.250 euros for autónomo sectorial plans, plus 5.000 euros for dependencia insurance premiums. The headline 1.500/8.500 euros figures were already in force from 2022-01-01 (art. 59.2 Ley 22/2021, BOE-A-2021-21653) and are numerically unchanged by this redaction and by the 2023-01-01 redaction; only the worker-contribution coefficient mechanics changed. Grounds the 2022 Modelo 100 previsión social reduction casillas for the redaction actually in force at that revision's devengo date (2022-12-31) — distinct from the 2021-only art-52-2021 entry (2.000/8.000 euros) and cited instead of the bare current entry, whose effective_from (2023-01-01) postdates the 2022 devengo date even though its required_text figures happen to match."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 52. Límite de reducción.
>
> 1. Como límite máximo conjunto para las reducciones previstas en los apartados 1, 2, 3, 4 y 5 del artículo 51 de esta ley, se aplicará la menor de las cantidades siguientes:
>
> a) El 30 por 100 de la suma de los rendimientos netos del trabajo y de actividades económicas percibidos individualmente en el ejercicio.
>
> b) 1.500 euros anuales.
>
> Este límite se incrementará en los siguientes supuestos, en las cuantías que se indican:
>
> 1.º En 8.500 euros anuales, siempre que tal incremento provenga de contribuciones empresariales, o de aportaciones del trabajador al mismo instrumento de previsión social por importe igual o inferior al resultado de aplicar a la respectiva contribución empresarial el coeficiente que resulte del siguiente cuadro:
>
> Importe anual de la contribución
>
> Coeficiente
>
> Igual o inferior a 500 euros.
>
> 2,5
>
> Entre 500,01 y 1.000 euros.
>
> 2
>
> Entre 1.000,01 y 1.500 euros.
>
> 1,5
>
> Más de 1.500 euros.
>
> 1
>
> No obstante, en todo caso se aplicará el coeficiente 1 cuando el trabajador obtenga en el ejercicio rendimientos íntegros del trabajo superiores a 60.000 euros procedentes de la empresa que realiza la contribución, a cuyo efecto la empresa deberá comunicar a la entidad gestora o aseguradora del instrumento de previsión social que no concurre esta circunstancia.
>
> A estos efectos, las cantidades aportadas por la empresa que deriven de una decisión del trabajador tendrán la consideración de aportaciones del trabajador.
>
> 2.º En 4.250 euros anuales, siempre que tal incremento provenga de aportaciones a los planes de pensiones de empleo simplificados de trabajadores por cuenta propia o autónomos previstos en las letras a) y c) del apartado 1 del artículo 67 del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones; o de aportaciones propias que el empresario individual o el profesional realice a planes de pensiones de empleo, de los que sea promotor y, además, partícipe o a Mutualidades de Previsión Social de las que sea mutualista, así como las que realice a planes de previsión social empresarial o seguros colectivos de dependencia de los que, a su vez, sea tomador y asegurado.
>
> En todo caso, la cuantía máxima de reducción por aplicación de los incrementos previstos en los números 1.º y 2.º anteriores será de 8.500 euros anuales.
>
> Además, 5.000 euros anuales para las primas a seguros colectivos de dependencia satisfechas por la empresa.
>
> 2. Los partícipes, mutualistas o asegurados que hubieran efectuado aportaciones a los sistemas de previsión social a que se refiere el artículo 51 de esta Ley, podrán reducir en los cinco ejercicios siguientes las cantidades aportadas incluyendo, en su caso, las aportaciones del promotor o las realizadas por la empresa que les hubiesen sido imputadas, que no hubieran podido ser objeto de reducción en la base imponible por insuficiencia de la misma o por aplicación del límite porcentual establecido en el apartado 1 anterior. Esta regla no resultará de aplicación a las aportaciones y contribuciones que excedan de los límites máximos previstos en el apartado 6 del artículo 51.
>
> Se modifica el apartado 1 por la disposición final 1.1 de la Ley 12/2022, de 30 de junio. Ref. BOE-A-2022-10852
>
> Redactado conforme a la corrección de errores publicada en BOE núm. 240, de 6 de octubre de 2022. Ref. BOE-A-2022-16278

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2022. 75 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-02`.

### 22. `ley-35-2006:art-84`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a84`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2010-01-01
- `required_text`:
  - "Normas aplicables en la tributación conjunta."
  - "idéntica cuantía en la tributación conjunta"
  - "se reducirá en 3.400 euros anuales"
  - "se reducirá en 2.150 euros anuales"
  - "No se aplicará esta reducción cuando el contribuyente conviva"
- `notes` (verbatim): "LIRPF art 84: joint-taxation rules, including unchanged quantitative limits, family-unit reduction of 3,400 EUR for art 82 first modality and 2,150 EUR for art 82 second modality, and the cohabiting-parent exclusion for the second-modality reduction. Current consolidated redaction was published 2009-12-19 and is in force from 2010-01-01."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 84. Normas aplicables en la tributación conjunta.
>
> 1. En la tributación conjunta serán aplicables las reglas generales del impuesto sobre determinación de la renta de los contribuyentes, determinación de las bases imponible y liquidable y determinación de la deuda tributaria, con las especialidades que se fijan en los apartados siguientes.
>
> 2. Los importes y límites cuantitativos establecidos a efectos de la tributación individual se aplicarán en idéntica cuantía en la tributación conjunta, sin que proceda su elevación o multiplicación en función del número de miembros de la unidad familiar.
>
> No obstante:
>
> 1.º Los límites máximos de reducción en la base imponible previstos en los artículos 52, 53 y 54 y en la disposición adicional undécima de esta Ley, serán aplicados individualmente por cada partícipe o mutualista integrado en la unidad familiar.
>
> 2.º En cualquiera de las modalidades de unidad familiar, se aplicará, con independencia del número de miembros integrados en la misma, el importe del mínimo previsto en el apartado 1 del artículo 57, incrementado o disminuido en su caso para el cálculo del gravamen autonómico en los términos previstos en el artículo 56.3 de esta Ley.
>
> Para la cuantificación del mínimo a que se refiere el apartado 2 del artículo 57 y el apartado 1 del artículo 60, ambos de esta Ley, se tendrán en cuenta las circunstancias personales de cada uno de los cónyuges integrados en la unidad familiar.
>
> En ningún caso procederá la aplicación de los citados mínimos por los hijos, sin perjuicio de la cuantía que proceda por el mínimo por descendientes y discapacidad.
>
> 3.º En la primera de las modalidades de unidad familiar del artículo 82 de esta ley, la base imponible, con carácter previo a las reducciones previstas en los artículos 51, 53 y 54 y en la disposición adicional undécima de esta Ley, se reducirá en 3.400 euros anuales. A tal efecto, la reducción se aplicará, en primer lugar, a la base imponible general sin que pueda resultar negativa como consecuencia de tal minoración. El remanente, si lo hubiera, minorará la base imponible del ahorro, que tampoco podrá resultar negativa.
>
> 4.º En la segunda de las modalidades de unidad familiar del artículo 82 de esta ley, la base imponible, con carácter previo a las reducciones previstas en los artículos 51, 53 y 54 y en la disposición adicional undécima de esta Ley, se reducirá en 2.150 euros anuales. A tal efecto, la reducción se aplicará, en primer lugar, a la base imponible general sin que pueda resultar negativa como consecuencia de tal minoración. El remanente, si lo hubiera, minorará la base imponible del ahorro, que tampoco podrá resultar negativa.
>
> No se aplicará esta reducción cuando el contribuyente conviva con el padre o la madre de alguno de los hijos que forman parte de su unidad familiar.
>
> 3. En la tributación conjunta serán compensables, con arreglo a las normas generales del impuesto, las pérdidas patrimoniales y las bases liquidables generales negativas, realizadas y no compensadas por los contribuyentes componentes de la unidad familiar en períodos impositivos anteriores en que hayan tributado individualmente.
>
> 4. Los mismos conceptos determinados en tributación conjunta serán compensables exclusivamente, en caso de tributación individual posterior, por aquellos contribuyentes a quienes correspondan de acuerdo con las reglas sobre individualización de rentas contenidas en esta ley.
>
> 5. Las rentas de cualquier tipo obtenidas por las personas físicas integradas en una unidad familiar que hayan optado por la tributación conjunta serán gravadas acumuladamente.
>
> 6. Todos los miembros de la unidad familiar quedarán conjunta y solidariamente sometidos al impuesto, sin perjuicio del derecho a prorratear entre sí la deuda tributaria, según la parte de renta sujeta que corresponda a cada uno de ellos.
>
> Se modifica el apartado 2.2 por la disposición final 2.14 de la Ley 22/2009, de 18 de diciembre. Ref. BOE-A-2009-20375
>
> Esta modificación entra en vigor y surte efectos desde el 1 de enero de 2010, según establece la disposición final 5.
>
> Se modifica el apartado 2.2, con efectos desde el 1 de enero de 2008 por el art. 68 de la Ley 2/2008, de 23 de diciembre. Ref. BOE-A-2008-20744
>
> TÍTULO X
>
> Regímenes especiales
>
> Sección 1.ª Imputación de rentas inmobiliarias

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2024, 2025. 1 casilla(s); 1 construct(s); 2 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

## Deducciones y regimenes especiales

### 23. `ley-35-2006:art-91`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a91`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2021-07-11
- `required_text`:
  - "Imputación de rentas en el régimen de transparencia fiscal internacional."
  - "Los contribuyentes imputarán las rentas positivas obtenidas"
  - "entidad no residente en territorio español"
  - "participación igual o superior al 50 por ciento"
  - "inferior al 75 por ciento del que hubiera correspondido"
  - "organización de medios materiales y personales"
  - "Titularidad de bienes inmuebles rústicos y urbanos"
  - "Participación en fondos propios de cualquier tipo de entidad"
  - "Operaciones de capitalización y seguro"
  - "se imputarán en la base imponible general"
  - "Será deducible de la cuota líquida"
  - "deberán presentar conjuntamente con la declaración por este Impuesto los siguientes datos"
- `notes` (verbatim): "LIRPF art 91, current consolidated redaction after Ley 11/2021 art 3.4, published 2021-07-10 and in force from 2021-07-11: imputes income under the international fiscal transparency regime for controlled non-resident entities with low analogous corporate taxation. It grounds M100 TFI entity/name and imputation amount fields, the aggregate TFI imputation formula, and the transparency-related double-taxation deduction; paragraph 6 fixes the imputation period and paragraph 11 lists accompanying entity data."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 91. Imputación de rentas en el régimen de transparencia fiscal internacional.
>
> 1. Los contribuyentes imputarán las rentas positivas obtenidas por una entidad no residente en territorio español a que se refieren los apartados 2 o 3 de este artículo cuando se cumplan las circunstancias siguientes:
>
> a) Que por sí solos o conjuntamente con entidades vinculadas en el sentido del artículo 18 de la Ley del Impuesto sobre Sociedades o con otros contribuyentes unidos por vínculos de parentesco, incluido el cónyuge, en línea directa o colateral, consanguínea o por afinidad hasta el segundo grado inclusive, tengan una participación igual o superior al 50 por ciento en el capital, los fondos propios, los resultados o los derechos de voto de la entidad no residente en territorio español, en la fecha del cierre del ejercicio social de esta última.
>
> b) Que el importe satisfecho por la entidad no residente en territorio español, imputable a alguna de las clases de rentas previstas en el apartado 2 o 3 de este artículo por razón de gravamen de naturaleza idéntica o análoga al Impuesto sobre Sociedades, sea inferior al 75 por ciento del que hubiera correspondido de acuerdo con las normas de aquel.
>
> 2. Los contribuyentes imputarán la renta total obtenida por la entidad no residente en territorio español, cuando esta no disponga de la correspondiente organización de medios materiales y personales para su obtención, incluso si las operaciones tienen carácter recurrente.
>
> Se entenderá por renta total el importe de la base imponible que resulte de aplicar los criterios y principios establecidos en la Ley del Impuesto sobre Sociedades y en las restantes disposiciones relativas al Impuesto sobre Sociedades para la determinación de aquella.
>
> Este apartado no resultará de aplicación cuando el contribuyente acredite que las referidas operaciones se realizan con los medios materiales y personales existentes en una entidad no residente en territorio español perteneciente al mismo grupo, en el sentido del artículo 42 del Código de Comercio, con independencia de su residencia y de la obligación de formular cuentas anuales consolidadas, o bien que su constitución y operativa responde a motivos económicos válidos.
>
> La aplicación de lo dispuesto en el primer párrafo de este apartado prevalecerá sobre lo previsto en el apartado siguiente.
>
> 3. En el supuesto de no aplicarse lo establecido en el apartado anterior, se imputará únicamente la renta positiva que provenga de cada una de las siguientes fuentes:
>
> a) Titularidad de bienes inmuebles rústicos y urbanos o de derechos reales que recaigan sobre estos, salvo que estén afectos a una actividad económica, o cedidos en uso a entidades no residentes, pertenecientes al mismo grupo de sociedades de la titular en el sentido del artículo 42 del Código de Comercio, con independencia de su residencia y de la obligación de formular cuentas anuales consolidadas, e igualmente estuvieren afectos a una actividad económica.
>
> b) Participación en fondos propios de cualquier tipo de entidad y cesión a terceros de capitales propios, que tengan tal consideración con arreglo a lo dispuesto en los apartados 1 y 2 del artículo 25 de esta Ley.
>
> No se entenderá incluida en esta letra la renta positiva que proceda de los siguientes activos financieros:
>
> 1.º Los tenidos para dar cumplimiento a obligaciones legales y reglamentarias originadas por el ejercicio de actividades económicas.
>
> 2.º Los que incorporen derechos de crédito nacidos de relaciones contractuales establecidas como consecuencia del desarrollo de actividades económicas.
>
> 3.º Los tenidos como consecuencia del ejercicio de actividades de intermediación en mercados oficiales de valores.
>
> 4.º Los tenidos por entidades de crédito y aseguradoras como consecuencia del ejercicio de sus actividades, sin perjuicio de lo establecido en la letra i).
>
> La renta positiva derivada de la cesión a terceros de capitales propios se entenderá que procede de la realización de actividades crediticias y financieras a que se refiere la letra i) cuando el cedente y el cesionario pertenezcan a un grupo de sociedades en el sentido del artículo 42 del Código de Comercio, con independencia de la residencia y de la obligación de formular cuentas anuales consolidadas, y los ingresos del cesionario procedan, al menos en el 85 por ciento, del ejercicio de actividades económicas.
>
> c) Operaciones de capitalización y seguro, que tengan como beneficiaria a la propia entidad.
>
> d) Propiedad industrial e intelectual, asistencia técnica, bienes muebles, derechos de imagen y arrendamiento o subarrendamiento de negocios o minas, que tengan tal consideración con arreglo a lo dispuesto en el apartado 4 del artículo 25 de esta Ley.
>
> No obstante, no será objeto de imputación la renta procedente de derechos de imagen que deba imputarse conforme a lo dispuesto en el artículo 92 de esta Ley.
>
> e) Transmisión de los bienes y derechos referidos en las letras a), b), c) y d) anteriores que genere rentas.
>
> f) Instrumentos financieros derivados, excepto los designados para cubrir un riesgo específicamente identificado derivado de la realización de actividades económicas.
>
> g) Actividades de seguros, crediticias, operaciones de arrendamiento financiero y otras actividades financieras salvo que se trate de rentas obtenidas en el ejercicio de actividades económicas, sin perjuicio de lo establecido en la letra i).
>
> h) Operaciones sobre bienes y servicios realizados con personas o entidades vinculadas en el sentido del artículo 18 de la Ley del Impuesto sobre Sociedades, en las que la entidad no residente o establecimiento añade un valor económico escaso o nulo.
>
> i) Actividades crediticias, financieras, aseguradoras y de prestación de servicios realizadas, directa o indirectamente, con personas o entidades residentes en territorio español y vinculadas en el sentido del artículo 18 de la Ley del Impuesto sobre Sociedades, en cuanto determinen gastos fiscalmente deducibles en dichas personas o entidades residentes.
>
> No se incluirá la renta positiva prevista en esta letra cuando al menos dos tercios de los ingresos derivados de las actividades crediticias, financieras, aseguradoras o de prestación de servicios realizadas por la entidad no residente procedan de operaciones efectuadas con personas o entidades no vinculadas en el sentido del artículo 18 de la Ley del Impuesto sobre Sociedades.
>
> 4. No se imputarán las rentas previstas en el apartado 3 de este artículo cuando la suma de sus importes sea inferior al 15 por ciento de la renta total obtenida por la entidad no residente.
>
> No obstante, se imputarán en todo caso las rentas a las que se refiere la letra i) del apartado 3 sin perjuicio de que, asimismo, sean tomadas en consideración a efectos de determinar la suma a la que se refiere el párrafo anterior.
>
> No se imputará en la base imponible del contribuyente el impuesto o impuestos de naturaleza idéntica o similar al Impuesto sobre Sociedades efectivamente satisfecho por la sociedad no residente por la parte de renta a incluir.
>
> 5. Estarán obligados a la imputación prevista en este artículo los contribuyentes comprendidos en la letra a) del apartado 1, que participen directamente en la entidad no residente o bien indirectamente a través de otra u otras entidades no residentes. En este último caso, el importe de la renta positiva será el correspondiente a la participación indirecta.
>
> El importe de la renta positiva a imputar se determinará en proporción a la participación en los resultados y, en su defecto, en proporción a la participación en el capital, los fondos propios o los derechos de voto.
>
> Las rentas positivas a que se refieren los apartados 2 y 3 se imputarán en la base imponible general, de acuerdo con lo previsto en el artículo 45 de esta Ley.
>
> 6. La imputación se realizará en el período impositivo que comprenda el día en que la entidad no residente en territorio español haya concluido su ejercicio social que, a estos efectos, no podrá entenderse de duración superior a 12 meses.
>
> 7. El importe de las rentas positivas a imputar se calculará de acuerdo con los principios y criterios establecidos en la Ley del Impuesto sobre Sociedades y en las restantes disposiciones relativas al Impuesto sobre Sociedades para la determinación de la base imponible.
>
> A estos efectos se utilizará el tipo de cambio vigente al cierre del ejercicio social de la entidad no residente en territorio español.
>
> En ningún caso se imputará una cantidad superior a la renta total de la entidad no residente.
>
> 8. No se integrarán en la base imponible los dividendos o participaciones en beneficios en la parte que corresponda a la renta positiva que haya sido imputada. El mismo tratamiento se aplicará a los dividendos a cuenta.
>
> En caso de distribución de reservas se atenderá a la designación contenida en el acuerdo social, entendiéndose aplicadas las últimas cantidades abonadas a dichas reservas.
>
> Una misma renta positiva solamente podrá ser objeto de imputación por una sola vez, cualquiera que sea la forma y la entidad en que se manifieste.
>
> 9. Será deducible de la cuota líquida el impuesto o gravamen efectivamente satisfecho en el extranjero por razón de la distribución de los dividendos o participaciones en beneficios, sea conforme a un convenio para evitar la doble imposición o de acuerdo con la legislación interna del país o territorio de que se trate, en la parte que corresponda a la renta positiva imputada con anterioridad en la base imponible.
>
> Esta deducción se practicará aun cuando los impuestos correspondan a períodos impositivos distintos a aquel en el que se realizó la imputación.
>
> En ningún caso se deducirán los impuestos satisfechos en países o territorios calificados como jurisdicciones no cooperativas.
>
> Esta deducción no podrá exceder de la cuota íntegra que en España corresponda pagar por la renta positiva incluida en la base imponible.
>
> 10. Para calcular la renta derivada de la transmisión de la participación, directa o indirecta, se emplearán las reglas contenidas en la letra a) del apartado 2 de la disposición transitoria décima de la Ley del Impuesto sobre Sociedades, en relación a la renta positiva imputada en la base imponible. Los beneficios sociales a que se refiere el citado precepto serán los correspondientes a la renta positiva imputada.
>
> 11. Los contribuyentes a quienes sea de aplicación lo previsto en el presente artículo deberán presentar conjuntamente con la declaración por este Impuesto los siguientes datos relativos a la entidad no residente en territorio español:
>
> a) Nombre o razón social y lugar del domicilio social.
>
> b) Relación de administradores y lugar de su domicilio fiscal.
>
> c) El balance, la cuenta de pérdidas y ganancias y la memoria.
>
> d) Importe de la renta positiva que deba ser objeto de imputación en la base imponible.
>
> e) Justificación de los impuestos satisfechos respecto de la renta positiva que deba ser objeto de imputación.
>
> 12. Cuando la entidad participada resida en un país o territorio calificado como jurisdicción no cooperativa, se presumirá que:
>
> a) Se cumple la circunstancia prevista en la letra b) del apartado 1.
>
> b) Las rentas de la entidad participada reúnen las características del apartado 3 de este artículo.
>
> c) La renta obtenida por la entidad participada es el 15 por ciento del valor de adquisición de la participación.
>
> Las presunciones contenidas en los párrafos anteriores admitirán prueba en contrario.
>
> 13. A los efectos del presente artículo se entenderá que el grupo de sociedades a que se refiere el artículo 42 del Código de Comercio incluye las entidades multigrupo y asociadas en los términos de la legislación mercantil.
>
> 14. Lo previsto en este artículo no será de aplicación cuando la entidad no residente en territorio español sea residente en otro Estado miembro de la Unión Europea o que forme parte del Acuerdo del Espacio Económico Europeo, siempre que el contribuyente acredite que realiza actividades económicas o se trate de una institución de inversión colectiva regulada en la Directiva 2009/65/CE del Parlamento Europeo y del Consejo, de 13 de julio de 2009, por la que se coordinan las disposiciones legales, reglamentarias y administrativas sobre determinados organismos de inversión colectiva en valores mobiliarios, distintas de las previstas en el artículo 95 de esta Ley, constituida y domiciliada en algún Estado miembro de la Unión Europea.
>
> Se modifica por el art. 3.4 de la Ley 11/2021, de 9 de julio. Ref. BOE-A-2021-11473
>
> Se modifica por el art. 1.58 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Sección 4.ª Derechos de imagen

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2021, 2022, 2023, 2024, 2025. 3 casilla(s); 1 construct(s); 1 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 24. `ley-35-2006:art-91-2015`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-91-2015.html#a91`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Los contribuyentes imputarán las rentas positivas obtenidas"
  - "entidad no residente en territorio español"
  - "participación igual o superior al 50 por ciento"
  - "inferior al 75 por ciento del que hubiera correspondido"
  - "organización de medios materiales y personales"
  - "Titularidad de bienes inmuebles rústicos y urbanos"
  - "Participación en fondos propios de cualquier tipo de entidad"
  - "Operaciones de capitalización y seguro"
- `notes` (verbatim): "LIRPF art 91, redaction selected by BOE at 2014-11-28 (art. 1.58 Ley 26/2014, BOE-A-2014-12327), in force 2015-01-01 to 2021-07-10: imputes income under the international fiscal transparency regime for controlled non-resident entities, before Ley 11/2021 art. 3.4 (antifraude) amended the article with effect from 2021-07-11. Grounds the 2020 Modelo 100 TFI entity/name and imputation amount casillas for the filing year the pre-2021 redaction applied."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 91. Imputación de rentas en el régimen de transparencia fiscal internacional.
>
> 1. Los contribuyentes imputarán las rentas positivas obtenidas por una entidad no residente en territorio español a que se refieren los apartados 2 o 3 de este artículo cuando se cumplan las circunstancias siguientes:
>
> a) Que por sí solas o conjuntamente con entidades vinculadas en el sentido del artículo 18 de la Ley del Impuesto sobre Sociedades o con otros contribuyentes unidos por vínculos de parentesco, incluido el cónyuge, en línea directa o colateral, consanguínea o por afinidad hasta el segundo grado inclusive, tengan una participación igual o superior al 50 por ciento en el capital, los fondos propios, los resultados o los derechos de voto de la entidad no residente en territorio español, en la fecha del cierre del ejercicio social de esta última.
>
> El importe de la renta positiva a imputar se determinará en proporción a la participación en los resultados y, en su defecto, a la participación en el capital, los fondos propios o los derechos de voto de la entidad.
>
> b) Que el importe satisfecho por la entidad no residente en territorio español, imputable a alguna de las clases de rentas previstas en el apartado 2 o 3 de este artículo, por razón de gravamen de naturaleza idéntica o análoga al Impuesto sobre Sociedades, sea inferior al 75 por ciento del que hubiera correspondido de acuerdo con las normas de aquel.
>
> 2. Los contribuyentes imputarán la renta total obtenida por la entidad no residente en territorio español cuando esta no disponga de la correspondiente organización de medios materiales y personales para su realización, incluso si las operaciones tienen carácter recurrente. No obstante, en el caso de dividendos, participaciones en beneficios o rentas derivadas de la transmisión de participaciones, se atenderá, en todo caso, a lo dispuesto en el apartado 4 de este artículo.
>
> Se entenderá por renta total el importe de la base imponible que resulte de aplicar los criterios y principios establecidos en la Ley del Impuesto sobre Sociedades y en las restantes disposiciones relativas al Impuesto sobre Sociedades para la determinación de aquella.
>
> Este apartado no resultará de aplicación cuando el contribuyente acredite que las referidas operaciones se realizan con los medios materiales y personales existentes en una entidad no residente en territorio español perteneciente al mismo grupo, en el sentido del artículo 42 del Código de Comercio, con independencia de su residencia y de la obligación de formular cuentas anuales consolidadas, o bien que su constitución y operativa responde a motivos económicos válidos.
>
> La aplicación de lo dispuesto en el primer párrafo de este apartado prevalecerá sobre lo previsto en el apartado siguiente.
>
> 3. En el supuesto de no aplicarse lo establecido en el apartado anterior, se imputará únicamente la renta positiva que provenga de cada una de las siguientes fuentes:
>
> a) Titularidad de bienes inmuebles rústicos y urbanos o de derechos reales que recaigan sobre estos, salvo que estén afectos a una actividad económica o cedidos en uso a entidades no residentes, pertenecientes al mismo grupo de sociedades de la titular, en el sentido del artículo 42 del Código de Comercio con independencia de su residencia y de la obligación de formular cuentas anuales consolidadas, e igualmente estuvieren afectos a una actividad económica.
>
> b) Participación en fondos propios de cualquier tipo de entidad y cesión a terceros de capitales propios, en los términos previstos en los apartados 1 y 2 del artículo 25 de esta Ley.
>
> No se entenderá incluida en esta letra la renta positiva que proceda de los siguientes activos financieros:
>
> 1.º Los tenidos para dar cumplimiento a obligaciones legales y reglamentarias originadas por el ejercicio de actividades económicas.
>
> 2.º Los que incorporen derechos de crédito nacidos de relaciones contractuales establecidas como consecuencia del desarrollo de actividades económicas.
>
> 3.º Los tenidos como consecuencia del ejercicio de actividades de intermediación en mercados oficiales de valores.
>
> 4.º Los tenidos por entidades de crédito y aseguradoras como consecuencia del ejercicio de sus actividades empresariales, sin perjuicio de lo establecido en la letra g).
>
> La renta positiva derivada de la cesión a terceros de capitales propios se entenderá que procede de la realización de actividades crediticias y financieras a que se refiere la letra g), cuando el cedente y el cesionario pertenezcan a un grupo de sociedades en el sentido del artículo 42 del Código de Comercio, con independencia de la residencia y de la obligación de formular cuentas anuales consolidadas y los ingresos del cesionario procedan, al menos en el 85 por ciento, del ejercicio de actividades económicas.
>
> c) Operaciones de capitalización y seguro, que tengan como beneficiaria a la propia entidad.
>
> d) Propiedad industrial e intelectual, asistencia técnica, bienes muebles, derechos de imagen y arrendamiento o subarrendamiento de negocios o minas, en los términos establecidos en el apartado 4 del artículo 25 de esta Ley.
>
> No obstante, no será objeto de imputación la renta procedente de derechos de imagen que deba imputarse conforme a lo dispuesto en el artículo 92 de esta Ley.
>
> e) Transmisión de los bienes y derechos referidos en las letras a), b), c) y d) anteriores que genere rentas.
>
> f) Instrumentos financieros derivados, excepto los designados para cubrir un riesgo específicamente identificado derivado de la realización de actividades económicas.
>
> g) Actividades crediticias, financieras, aseguradoras y de prestación de servicios, realizadas, directa o indirectamente, con personas o entidades residentes en territorio español y vinculadas en el sentido del artículo 18 de la Ley del Impuesto sobre Sociedades, en cuanto determinen gastos fiscalmente deducibles en dichas personas residentes.
>
> No se incluirá la renta positiva prevista en esta letra g) cuando más del 50 por ciento de los ingresos derivados de las actividades crediticias, financieras, aseguradoras o de prestación de servicios realizadas por la entidad no residente procedan de operaciones efectuadas con personas o entidades no vinculadas en el sentido del artículo 18 de la Ley del Impuesto sobre Sociedades.
>
> 4. No se imputarán las rentas previstas en las letras b) y e) anteriores, en el supuesto de valores derivados de la participación en el capital o en los fondos propios de entidades que otorguen, al menos, el 5 por ciento del capital de una entidad y se posean durante un plazo mínimo de un año, con la finalidad de dirigir y gestionar la participación, siempre que disponga de la correspondiente organización de medios materiales y personales, y la entidad participada no tenga como actividad principal la gestión de un patrimonio mobiliario o inmobiliario en los términos previstos en el artículo 4.Ocho.Dos a) de la Ley 19/1991, de 6 de junio, del Impuesto sobre el Patrimonio.
>
> En el supuesto de entidades que formen parte del mismo grupo de sociedades según los criterios establecidos en el artículo 42 del Código de Comercio, con independencia de la residencia y de la obligación de formular cuentas anuales consolidadas, los requisitos relativos al porcentaje de participación así como la existencia de una dirección y gestión de la participación se determinarán teniendo en cuenta a todas las que formen parte del mismo.
>
> 5. No se imputarán las rentas previstas en el apartado 3 de este artículo cuando la suma de sus importes sea inferior al 15 por ciento de la renta total obtenida por la entidad no residente, excepto las rentas a que se refiere la letra g) de dicho apartado que se imputarán en su totalidad.
>
> No se imputará en la base imponible del contribuyente el impuesto o impuestos de naturaleza idéntica o similar al Impuesto sobre Sociedades efectivamente satisfecho por la sociedad no residente por la parte de renta a incluir.
>
> Las rentas positivas a que se refieren los apartados 2 y 3 se imputarán en la base imponible general, de acuerdo con lo previsto en el artículo 45 de esta Ley.
>
> 6. Estarán obligados a la imputación prevista en este artículo los contribuyentes comprendidos en la letra a) del apartado 1, que participen directamente en la entidad no residente o bien indirectamente a través de otra u otras entidades no residentes. En este último caso, el importe de la renta positiva será el correspondiente a la participación indirecta.
>
> 7. La imputación se realizará en el período impositivo que comprenda el día en que la entidad no residente en territorio español haya concluido su ejercicio social que, a estos efectos, no podrá entenderse de duración superior a 12 meses.
>
> 8. El importe de las rentas positivas a imputar se calculará de acuerdo con los principios y criterios establecidos en la Ley del Impuesto sobre Sociedades, y en las restantes disposiciones relativas al Impuesto sobre Sociedades para la determinación de la base imponible.
>
> A estos efectos, se utilizará el tipo de cambio vigente al cierre del ejercicio social de la entidad no residente en territorio español.
>
> En ningún caso se imputará una cantidad superior a la renta total de la entidad no residente.
>
> 9. No se integrarán en la base imponible los dividendos o participaciones en beneficios en la parte que corresponda a la renta positiva que haya sido imputada. El mismo tratamiento se aplicará a los dividendos a cuenta.
>
> En caso de distribución de reservas se atenderá a la designación contenida en el acuerdo social, entendiéndose aplicadas las últimas cantidades abonadas a dichas reservas.
>
> Una misma renta positiva solamente podrá ser objeto de imputación por una sola vez, cualquiera que sea la forma y la entidad en que se manifieste.
>
> 10. Será deducible de la cuota líquida el impuesto o gravamen efectivamente satisfecho en el extranjero por razón de la distribución de los dividendos o participaciones en beneficios, sea conforme a un convenio para evitar la doble imposición o de acuerdo con la legislación interna del país o territorio de que se trate, en la parte que corresponda a la renta positiva imputada con anterioridad en la base imponible.
>
> Esta deducción se practicará aun cuando los impuestos correspondan a períodos impositivos distintos a aquél en el que se realizó la inclusión.
>
> En ningún caso se deducirán los impuestos satisfechos en países o territorios considerados como paraísos fiscales.
>
> Esta deducción no podrá exceder de la cuota íntegra que en España correspondería pagar por la renta positiva imputada en la base imponible.
>
> 11. Para calcular la renta derivada de la transmisión de la participación, directa o indirecta, se emplearán las reglas contenidas en la letra a) del apartado 2 de la disposición transitoria décima de la Ley del Impuesto sobre Sociedades, en relación a la renta positiva imputada en la base imponible. Los beneficios sociales a que se refiere el citado precepto serán los correspondientes a la renta positiva imputada.
>
> 12. Los contribuyentes a quienes sea de aplicación lo previsto en este artículo deberán presentar conjuntamente con la declaración por el Impuesto sobre la Renta de las Personas Físicas los siguientes datos relativos a la entidad no residente en territorio español:
>
> a) Nombre o razón social y lugar del domicilio social.
>
> b) Relación de administradores y lugar del domicilio fiscal.
>
> c) Balance, la cuenta de pérdidas y ganancias y la memoria.
>
> d) Importe de la renta positiva que deba ser imputada.
>
> e) Justificación de los impuestos satisfechos respecto de la renta positiva que deba ser imputada.
>
> 13. Cuando la entidad participada sea residente en países o territorios considerados como paraísos fiscales o en un país o territorio de nula tributación se presumirá que:
>
> a) Se cumple la circunstancia prevista en la letra b) del apartado 1.
>
> b) Las rentas de la entidad participada reúnen las características del apartado 3 de este artículo.
>
> c) La renta obtenida por la entidad participada es el 15 por ciento del valor de adquisición de la participación.
>
> Las presunciones contenidas en los párrafos anteriores admitirán prueba en contrario.
>
> 14. A los efectos del presente artículo se entenderá que el grupo de sociedades a que se refiere el artículo 42 del Código de Comercio incluye las entidades multigrupo y asociadas en los términos de la legislación mercantil.
>
> 15. Lo previsto en este artículo no será de aplicación cuando la entidad no residente en territorio español sea residente en otro Estado miembro de la Unión Europea, siempre que el contribuyente acredite que su constitución y operativa responde a motivos económicos válidos y que realiza actividades económicas, o se trate de una institución de inversión colectiva, regulada por la Directiva 2009/65/CE del Parlamento Europeo y del Consejo, de 13 de julio de 2009, por la que se coordinan las disposiciones legales, reglamentarias y administrativas sobre determinados organismos de inversión colectiva en valores mobiliarios, distintas de las previstas en el artículo 95 de esta Ley, constituida y domiciliada en algún Estado miembro de la Unión Europea.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020. 3 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-02`.

## Calculo del impuesto y regularizacion

### 25. `ley-35-2006:art-37`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a37`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Normas específicas de valoración"
  - "valores admitidos a negociación"
  - "valores no admitidos a negociación"
  - "instituciones de inversión colectiva"
- `notes` (verbatim): "LIRPF art 37: fija normas especificas de valoracion de ganancias y perdidas patrimoniales para valores cotizados/no cotizados, instituciones de inversion colectiva, aportaciones no dinerarias, permutas y otros supuestos."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 37. Normas específicas de valoración.
>
> 1. Cuando la alteración en el valor del patrimonio proceda:
>
> a) De la transmisión a título oneroso de valores admitidos a negociación en alguno de los mercados regulados de valores definidos en la Directiva 2004/39/CE del Parlamento Europeo y del Consejo, de 21 de abril de 2004, relativa a los mercados de instrumentos financieros, y representativos de la participación en fondos propios de sociedades o entidades, la ganancia o pérdida se computará por la diferencia entre su valor de adquisición y el valor de transmisión, determinado por su cotización en dichos mercados en la fecha en que se produzca aquélla o por el precio pactado cuando sea superior a la cotización.
>
> El importe obtenido por la transmisión de derechos de suscripción procedentes de estos valores tendrá la consideración de ganancia patrimonial para el transmitente en el período impositivo en que se produzca la citada transmisión.
>
> Cuando se trate de acciones parcialmente liberadas, su valor de adquisición será el importe realmente satisfecho por el contribuyente. Cuando se trate de acciones totalmente liberadas, el valor de adquisición tanto de éstas como de las que procedan resultará de repartir el coste total entre el número de títulos, tanto los antiguos como los liberados que correspondan.
>
> b) De la transmisión a título oneroso de valores no admitidos a negociación en alguno de los mercados regulados de valores definidos en la Directiva 2004/39/CE del Parlamento Europeo y del Consejo, de 21 de abril de 2004, relativa a los mercados de instrumentos financieros, y representativos de la participación en fondos propios de sociedades o entidades, la ganancia o pérdida se computará por la diferencia entre su valor de adquisición y el valor de transmisión.
>
> Salvo prueba de que el importe efectivamente satisfecho se corresponde con el que habrían convenido partes independientes en condiciones normales de mercado, el valor de transmisión no podrá ser inferior al mayor de los dos siguientes:
>
> El valor del patrimonio neto que corresponda a los valores transmitidos resultante del balance correspondiente al último ejercicio cerrado con anterioridad a la fecha del devengo del Impuesto.
>
> El que resulte de capitalizar al tipo del 20 por ciento el promedio de los resultados de los tres ejercicios sociales cerrados con anterioridad a la fecha del devengo del Impuesto. A este último efecto, se computarán como beneficios los dividendos distribuidos y las asignaciones a reservas, excluidas las de regularización o de actualización de balances.
>
> El valor de transmisión así calculado se tendrá en cuenta para determinar el valor de adquisición de los valores o participaciones que corresponda al adquirente.
>
> El importe obtenido por la transmisión de derechos de suscripción procedentes de estos valores o participaciones tendrá la consideración de ganancia patrimonial para el transmitente en el período impositivo en que se produzca la citada transmisión.
>
> Cuando se trate de acciones parcialmente liberadas, su valor de adquisición será el importe realmente satisfecho por el contribuyente. Cuando se trate de acciones totalmente liberadas, el valor de adquisición, tanto de éstas como de las que procedan, resultará de repartir el coste total entre el número de títulos, tanto los antiguos como los liberados que correspondan.
>
> c) De la transmisión o el reembolso a título oneroso de acciones o participaciones representativas del capital o patrimonio de las instituciones de inversión colectiva a las que se refiere el artículo 94 de esta Ley, la ganancia o pérdida patrimonial se computará por la diferencia entre su valor de adquisición y el valor de transmisión, determinado por el valor liquidativo aplicable en la fecha en que dicha transmisión o reembolso se produzca o, en su defecto, por el último valor liquidativo publicado. Cuando no existiera valor liquidativo se tomará el valor del patrimonio neto que corresponda a las acciones o participaciones transmitidas resultante del balance correspondiente al último ejercicio cerrado con anterioridad a la fecha del devengo del Impuesto.
>
> En supuestos distintos del reembolso de participaciones, el valor de transmisión así calculado no podrá ser inferior al mayor de los dos siguientes:
>
> – El precio efectivamente pactado en la transmisión.
>
> – El valor de cotización en mercados secundarios oficiales de valores definidos en la Directiva 2004/39/CE del Parlamento Europeo y del Consejo, de 21 de abril de 2004, relativa a los mercados de instrumentos financieros y, en particular, en sistemas multilaterales de negociación de valores previstos en el Capítulo I del Título X de la Ley 24/1988, de 28 de julio, del Mercado de Valores, en la fecha de la transmisión.
>
> A los efectos de determinar el valor de adquisición, resultará de aplicación, cuando proceda, lo dispuesto en la letra a) de este apartado 1.
>
> No obstante lo dispuesto en los párrafos anteriores, en el caso de transmisiones de participaciones en los fondos de inversión cotizados o de acciones de SICAV índice cotizadas, a los que se refiere el artículo 79 del Reglamento de la Ley 35/2003, de 4 de noviembre, de instituciones de inversión colectiva, aprobado por el Real Decreto 1082/2012, de 13 de julio, realizadas en bolsa de valores, el valor de transmisión se determinará conforme a lo previsto en la letra a) de este apartado.
>
> d) De las aportaciones no dinerarias a sociedades, la ganancia o pérdida se determinará por la diferencia entre el valor de adquisición de los bienes o derechos aportados y la cantidad mayor de las siguientes:
>
> Primera.-El valor nominal de las acciones o participaciones sociales recibidas por la aportación o, en su caso, la parte correspondiente del mismo. A este valor se añadirá el importe de las primas de emisión.
>
> Segunda.-El valor de cotización de los títulos recibidos en el día en que se formalice la aportación o el inmediato anterior.
>
> Tercera.-El valor de mercado del bien o derecho aportado.
>
> El valor de transmisión así calculado se tendrá en cuenta para determinar el valor de adquisición de los títulos recibidos como consecuencia de la aportación no dineraria.
>
> e) En los casos de separación de los socios o disolución de sociedades, se considerará ganancia o pérdida patrimonial, sin perjuicio de las correspondientes a la sociedad, la diferencia entre el valor de la cuota de liquidación social o el valor de mercado de los bienes recibidos y el valor de adquisición del título o participación de capital que corresponda.
>
> En los casos de escisión, fusión o absorción de sociedades, la ganancia o pérdida patrimonial del contribuyente se computará por la diferencia entre el valor de adquisición de los títulos, derechos o valores representativos de la participación del socio y el valor de mercado de los títulos, numerario o derechos recibidos o el valor del mercado de los entregados.
>
> f) De un traspaso, la ganancia patrimonial se computará al cedente en el importe que le corresponda en el traspaso.
>
> Cuando el derecho de traspaso se haya adquirido mediante precio, éste tendrá la consideración de precio de adquisición.
>
> g) De indemnizaciones o capitales asegurados por pérdidas o siniestros en elementos patrimoniales, se computará como ganancia o pérdida patrimonial la diferencia entre la cantidad percibida y la parte proporcional del valor de adquisición que corresponda al daño. Cuando la indemnización no fuese en metálico, se computará la diferencia entre el valor de mercado de los bienes, derechos o servicios recibidos y la parte proporcional del valor de adquisición que corresponda al daño. Sólo se computará ganancia patrimonial cuando se derive un aumento en el valor del patrimonio del contribuyente.
>
> h) De la permuta de bienes o derechos, incluido el canje de valores, la ganancia o pérdida patrimonial se determinará por la diferencia entre el valor de adquisición del bien o derecho que se cede y el mayor de los dos siguientes:
>
> - El valor de mercado del bien o derecho entregado.
>
> - El valor de mercado del bien o derecho que se recibe a cambio.
>
> i) De la extinción de rentas vitalicias o temporales, la ganancia o pérdida patrimonial se computará, para el obligado al pago de aquéllas, por diferencia entre el valor de adquisición del capital recibido y la suma de las rentas efectivamente satisfechas.
>
> j) En las transmisiones de elementos patrimoniales a cambio de una renta temporal o vitalicia, la ganancia o pérdida patrimonial se determinará por diferencia entre el valor actual financiero actuarial de la renta y el valor de adquisición de los elementos patrimoniales transmitidos.
>
> k) Cuando el titular de un derecho real de goce o disfrute sobre inmuebles efectúe su transmisión, o cuando se produzca su extinción, para el cálculo de la ganancia o pérdida patrimonial el importe real a que se refiere el artículo 35.1.a) de esta ley se minorará de forma proporcional al tiempo durante el cual el titular no hubiese percibido rendimientos del capital inmobiliario.
>
> l) En las incorporaciones de bienes o derechos que no deriven de una transmisión, se computará como ganancia patrimonial el valor de mercado de aquéllos.
>
> m) En las operaciones realizadas en los mercados de futuros y opciones regulados por el Real Decreto 1814/1991, de 20 de diciembre, se considerará ganancia o pérdida patrimonial el rendimiento obtenido cuando la operación no suponga la cobertura de una operación principal concertada en el desarrollo de las actividades económicas realizadas por el contribuyente, en cuyo caso tributarán de acuerdo con lo previsto en la sección 3.ª de este capítulo.
>
> n) En las transmisiones de elementos patrimoniales afectos a actividades económicas, se considerará como valor de adquisición el valor contable, sin perjuicio de las especialidades que reglamentariamente puedan establecerse respecto a las amortizaciones que minoren dicho valor.
>
> 2. A efectos de lo dispuesto en las letras a), b) y c) del apartado anterior, cuando existan valores homogéneos se considerará que los transmitidos por el contribuyente son aquéllos que adquirió en primer lugar.
>
> Cuando se trate de acciones totalmente liberadas, se considerará como antigüedad de las mismas la que corresponda a las acciones de las cuales procedan.
>
> 3. Lo dispuesto en los párrafos d), e) y h), para el canje de valores, del apartado 1 de este artículo se entenderá sin perjuicio de lo establecido en el capítulo VIII del título VII del texto refundido de la Ley del Impuesto sobre Sociedades.
>
> 4. (Suprimido)
>
> Se modifican las letras a), b) y c) del apartado 1 y el apartado 2 y se suprime el apartado 4 por el art. 1.22 y 23 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 5 casilla(s); 23 construct(s); 305 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 26. `ley-35-2006:art-63`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a63`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2021-01-01
- `required_text`:
  - "Escala general del Impuesto."
  - "base liquidable general que exceda del importe del mínimo personal y familiar"
  - "A la base liquidable general se le aplicarán los tipos"
  - "se minorará en el importe derivado de aplicar"
  - "tipo medio de gravamen general estatal"
- `notes` (verbatim): "LIRPF art 63: current state general scale for the part of the base liquidable general exceeding the personal and family minimum, including the deduction of the minimum's scale amount and the state average general tax rate. Base legal para the Modelo 100 state general-scale parameters and formulas."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 63. Escala general del Impuesto.
>
> 1. La parte de la base liquidable general que exceda del importe del mínimo personal y familiar a que se refiere el artículo 56 de esta Ley será gravada de la siguiente forma:
>
> 1.º A la base liquidable general se le aplicarán los tipos que se indican en la siguiente escala:
>
> Base liquidable
>
> –
>
> Hasta euros
>
> Cuota íntegra
>
> –
>
> Euros
>
> Resto base liquidable
>
> –
>
> Hasta euros
>
> Tipo aplicable
>
> –
>
> Porcentaje
>
> 0,00
>
> 0,00
>
> 12.450,00
>
> 9,50
>
> 12.450,00
>
> 1.182,75
>
> 7.750,00
>
> 12,00
>
> 20.200,00
>
> 2.112,75
>
> 15.000,00
>
> 15,00
>
> 35.200,00
>
> 4.362,75
>
> 24.800,00
>
> 18,50
>
> 60.000,00
>
> 8.950,75
>
> 240.000,00
>
> 22,50
>
> 300.000,00
>
> 62.950,75
>
> En adelante
>
> 24,50
>
> 2.º La cuantía resultante se minorará en el importe derivado de aplicar a la parte de la base liquidable general correspondiente al mínimo personal y familiar, la escala prevista en el número 1.º anterior.
>
> 2. Se entenderá por tipo medio de gravamen general estatal el derivado de multiplicar por 100 el cociente resultante de dividir la cuota obtenida por la aplicación de lo previsto en el apartado anterior por la base liquidable general. El tipo medio de gravamen general estatal se expresará con dos decimales.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate/bracket table (percentages and euro thresholds laid out as table rows rather than in a sentence carrying "por ciento" or "euros" adjacent to the figure -- caught by a dedicated table-shape check after the phrase-adjacency scan first missed it; see the packet preamble) -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2021, 2022, 2023, 2024, 2025. 15 casilla(s); 6 construct(s); 35 formula(s); 5 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 714.

### 27. `ley-35-2006:art-66`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a66`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2024-12-22
- `required_text`:
  - "Tipos de gravamen del ahorro."
  - "base liquidable del ahorro que exceda"
  - "A la base liquidable del ahorro se le aplicarán los tipos"
  - "se minorará en el importe derivado de aplicar"
  - "contribuyentes que tuviesen su residencia habitual en el extranjero"
- `notes` (verbatim): "LIRPF art 66: current state savings-scale article for base liquidable del ahorro, including resident and certain foreign-resident scales and the minimum personal/family reduction mechanism. The selected BOE redaction is published 2024-12-21 and in force from 2024-12-22; the source note states effects from 2025-01-01 for the Ley 7/2024 change. Base legal para Modelo 100 savings-base state scale parameters and formulas."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 66. Tipos de gravamen del ahorro.
>
> 1. La parte de base liquidable del ahorro que exceda, en su caso, del importe del mínimo personal y familiar a que se refiere el artículo 56 de esta ley será gravada de la siguiente forma:
>
> 1.º A la base liquidable del ahorro se le aplicarán los tipos que se indican en la siguiente escala:
>
> Base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Cuota íntegra
>
> –
>
> Euros
>
> Resto base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Tipo aplicable
>
> –
>
> Porcentaje
>
> 0
>
> 0
>
> 6.000
>
> 9,5
>
> 6.000,00
>
> 570
>
> 44.000
>
> 10,5
>
> 50.000,00
>
> 5.190
>
> 150.000
>
> 11,5
>
> 200.000,00
>
> 22.440
>
> 100.000
>
> 13,5
>
> 300.000,00
>
> 35.940
>
> En adelante
>
> 15
>
> 2.º La cuantía resultante se minorará en el importe derivado de aplicar a la parte de la base liquidable del ahorro correspondiente al mínimo personal y familiar, la escala prevista en el número 1.º anterior.
>
> 2. En el caso de los contribuyentes que tuviesen su residencia habitual en el extranjero por concurrir alguna de las circunstancias a las que se refieren el apartado 2 del artículo 8 y el apartado 1 del artículo 10 de esta ley, la parte de base liquidable del ahorro que exceda, en su caso, del importe del mínimo personal y familiar a que se refiere el artículo 56 de esta ley será gravada de la siguiente forma:
>
> 1.º A la base liquidable del ahorro se le aplicarán los tipos que se indican en la siguiente escala:
>
> Base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Cuota íntegra
>
> –
>
> Euros
>
> Resto base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Tipo aplicable
>
> –
>
> Porcentaje
>
> 0
>
> 0
>
> 6.000
>
> 19
>
> 6.000,00
>
> 1.140
>
> 44.000
>
> 21
>
> 50.000,00
>
> 10.380
>
> 150.000
>
> 23
>
> 200.000,00
>
> 44.880
>
> 100.000
>
> 27
>
> 300.000,00
>
> 71.880
>
> En adelante
>
> 30
>
> 2.º La cuantía resultante se minorará en el importe derivado de aplicar a la parte de la base liquidable del ahorro correspondiente al mínimo personal y familiar, la escala prevista en el número 1.º anterior.
>
> Se modifica, con efectos desde el 1 de enero de 2025, por la disposicion final 7.1 de la Ley 7/2024, de 20 de diciembre. Ref. BOE-A-2024-26694
>
> Se modifica por el art. 63.1 de la Ley 31/2022, de 23 de diciembre. Ref. BOE-A-2022-22128
>
> Se modifica, con efectos desde 1 de enero de 2021, por el art. 59.1 de la Ley 11/2020, de 30 de diciembre. Ref. BOE-A-2020-17339
>
> Se modifica por el art. 1.42 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Se modifica el apartado 1, con efectos desde 1 de enero de 2010, por el art. 63.1 de la Ley 39/2010, de 22 de diciembre. Ref. BOE-A-2010-19703.
>
> Se modifica, con efectos desde el 1 de enero de 2010 por el art. 69.1 de la Ley 26/2009, de 23 de diciembre. Ref. BOE-A-2009-20765
>
> Se modifica el apartado 1 por la disposición final 2.6 de la Ley 22/2009, de 18 de diciembre. Ref. BOE-A-2009-20375
>
> Esta modificación entra en vigor y surte efectos desde el 1 de enero de 2010, según establece la disposición final 5.
>
> CAPÍTULO II
>
> Determinación de la cuota líquida estatal

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate/bracket table (percentages and euro thresholds laid out as table rows rather than in a sentence carrying "por ciento" or "euros" adjacent to the figure -- caught by a dedicated table-shape check after the phrase-adjacency scan first missed it; see the packet preamble) -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2024, 2025. 24 casilla(s); 3 construct(s); 12 formula(s); 2 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 28. `ley-35-2006:art-66-2015`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-66-2015.html#a66`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Tipos de gravamen del ahorro."
  - "base liquidable del ahorro que exceda"
  - "A la base liquidable del ahorro se le aplicarán los tipos"
  - "50.000,00"
  - "5.190"
  - "En adelante"
  - "11,5"
- `notes` (verbatim): "LIRPF art 66, redaction selected by BOE at 2014-11-28 (art. 1.42 Ley 26/2014, BOE-A-2014-12327), in force 2015-01-01 to 2020-12-31: three-bracket estatal savings scale (9,5/10,5/11,5 percent up to 6.000/44.000/en adelante euros), before Ley 11/2020 art. 59.2 added the fourth bracket (13,00 percent above 200.000 euros) with effect from 2021-01-01. Grounds the 2020 Modelo 100 base liquidable del ahorro estatal scale casillas and formulas."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 66. Tipos de gravamen del ahorro.
>
> 1. La parte de base liquidable del ahorro que exceda, en su caso, del importe del mínimo personal y familiar a que se refiere el artículo 56 de esta Ley será gravada de la siguiente forma:
>
> 1.º A la base liquidable del ahorro se le aplicarán los tipos que se indican en la siguiente escala:
>
> Base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Cuota íntegra
>
> –
>
> Euros
>
> Resto base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Tipo aplicable
>
> –
>
> Porcentaje
>
> 0
>
> 0
>
> 6.000
>
> 9,5
>
> 6.000,00
>
> 570
>
> 44.000
>
> 10,5
>
> 50.000,00
>
> 5.190
>
> En adelante
>
> 11,5
>
> 2.º La cuantía resultante se minorará en el importe derivado de aplicar a la parte de la base liquidable del ahorro correspondiente al mínimo personal y familiar, la escala prevista en el número 1.º anterior.
>
> 2. En el caso de los contribuyentes que tuviesen su residencia habitual en el extranjero por concurrir alguna de las circunstancias a las que se refieren el apartado 2 del artículo 8 y el apartado 1 del artículo 10 de esta Ley, la parte de base liquidable del ahorro que exceda, en su caso, del importe del mínimo personal y familiar a que se refiere el artículo 56 de esta Ley será gravada de la siguiente forma:
>
> 1.º A la base liquidable del ahorro se le aplicarán los tipos que se indican en la siguiente escala:
>
> Base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Cuota íntegra
>
> –
>
> Euros
>
> Resto base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Tipo aplicable
>
> –
>
> Porcentaje
>
> 0
>
> 0
>
> 6.000
>
> 19
>
> 6.000,00
>
> 1.140
>
> 44.000
>
> 21
>
> 50.000,00
>
> 10.380
>
> En adelante
>
> 23
>
> 2.º La cuantía resultante se minorará en el importe derivado de aplicar a la parte de la base liquidable del ahorro correspondiente al mínimo personal y familiar, la escala prevista en el número 1.º anterior.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020. 12 casilla(s); 2 construct(s); 6 formula(s); 1 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-02`.

### 29. `ley-35-2006:art-66-2021`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-66-2021.html#a66`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2021-01-01
- `required_text`:
  - "Tipos de gravamen del ahorro."
  - "base liquidable del ahorro que exceda"
  - "150.000"
  - "200.000,00"
  - "22.440"
  - "En adelante"
  - "13,00"
- `notes` (verbatim): "LIRPF art 66, redaction selected by BOE at 2020-12-31 (art. 59.2 Ley 11/2020, BOE-A-2020-17339), in force 2021-01-01 to 2022-12-31: four-bracket estatal savings scale adding the 13,00 percent tranche above 200.000 euros, before Ley 31/2022 art. 63.2 restructured the top brackets with effect from 2023-01-01. Grounds the 2021 and 2022 Modelo 100 base liquidable del ahorro estatal scale casillas and formulas."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 66. Tipos de gravamen del ahorro.
>
> 1. La parte de base liquidable del ahorro que exceda, en su caso, del importe del mínimo personal y familiar a que se refiere el artículo 56 de esta Ley será gravada de la siguiente forma:
>
> 1.º A la base liquidable del ahorro se le aplicarán los tipos que se indican en la siguiente escala:
>
> Base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Cuota íntegra
>
> –
>
> Euros
>
> Resto base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Tipo aplicable
>
> –
>
> Porcentaje
>
> 0
>
> 0
>
> 6.000
>
> 9,5
>
> 6.000,00
>
> 570
>
> 44.000
>
> 10,5
>
> 50.000,00
>
> 5.190
>
> 150.000
>
> 11,5
>
> 200.000,00
>
> 22.440
>
> En adelante
>
> 13,00
>
> 2.º La cuantía resultante se minorará en el importe derivado de aplicar a la parte de la base liquidable del ahorro correspondiente al mínimo personal y familiar, la escala prevista en el número 1.º anterior.
>
> 2. En el caso de los contribuyentes que tuviesen su residencia habitual en el extranjero por concurrir alguna de las circunstancias a las que se refieren el apartado 2 del artículo 8 y el apartado 1 del artículo 10 de esta Ley, la parte de base liquidable del ahorro que exceda, en su caso, del importe del mínimo personal y familiar a que se refiere el artículo 56 de esta Ley será gravada de la siguiente forma:
>
> 1.º A la base liquidable del ahorro se le aplicarán los tipos que se indican en la siguiente escala:
>
> Base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Cuota íntegra
>
> –
>
> Euros
>
> Resto base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Tipo aplicable
>
> –
>
> Porcentaje
>
> 0
>
> 0
>
> 6.000
>
> 19
>
> 6.000,00
>
> 1.140
>
> 44.000
>
> 21
>
> 50.000,00
>
> 10.380
>
> 150.000
>
> 23
>
> 200.000,00
>
> 44.880
>
> En adelante
>
> 26
>
> 2.º La cuantía resultante se minorará en el importe derivado de aplicar a la parte de la base liquidable del ahorro correspondiente al mínimo personal y familiar, la escala prevista en el número 1.º anterior.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2021, 2022. 17 casilla(s); 3 construct(s); 12 formula(s); 2 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-02`.

### 30. `ley-35-2006:art-66-2023`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-66-2023.html#a66`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2023-01-01
- `required_text`:
  - "Tipos de gravamen del ahorro."
  - "base liquidable del ahorro que exceda"
  - "150.000"
  - "200.000,00"
  - "22.440"
  - "100.000"
  - "13,5"
- `notes` (verbatim): "LIRPF art 66, redaction selected by BOE at 2022-12-24 (art. 63.2 Ley 31/2022, BOE-A-2022-22128), in force 2023-01-01 to 2024-12-21: five-bracket estatal savings scale adding the 13,5/14 percent tranches above 200.000/300.000 euros, before the 2024-12-22 redaction. Grounds the 2023 Modelo 100 base liquidable del ahorro estatal scale casillas and formulas."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 66. Tipos de gravamen del ahorro.
>
> 1. La parte de base liquidable del ahorro que exceda, en su caso, del importe del mínimo personal y familiar a que se refiere el artículo 56 de esta ley será gravada de la siguiente forma:
>
> 1.º A la base liquidable del ahorro se le aplicarán los tipos que se indican en la siguiente escala:
>
> Base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Cuota íntegra
>
> –
>
> Euros
>
> Resto base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Tipo aplicable
>
> –
>
> Porcentaje
>
> 0
>
> 0
>
> 6.000
>
> 9,5
>
> 6.000,00
>
> 570
>
> 44.000
>
> 10,5
>
> 50.000,00
>
> 5.190
>
> 150.000
>
> 11,5
>
> 200.000,00
>
> 22.440
>
> 100.000
>
> 13,5
>
> 300.000,00
>
> 35.940
>
> En adelante
>
> 14
>
> 2.º La cuantía resultante se minorará en el importe derivado de aplicar a la parte de la base liquidable del ahorro correspondiente al mínimo personal y familiar, la escala prevista en el número 1.º anterior.
>
> 2. En el caso de los contribuyentes que tuviesen su residencia habitual en el extranjero por concurrir alguna de las circunstancias a las que se refieren el apartado 2 del artículo 8 y el apartado 1 del artículo 10 de esta ley, la parte de base liquidable del ahorro que exceda, en su caso, del importe del mínimo personal y familiar a que se refiere el artículo 56 de esta ley será gravada de la siguiente forma:
>
> 1.º A la base liquidable del ahorro se le aplicarán los tipos que se indican en la siguiente escala:
>
> Base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Cuota íntegra
>
> –
>
> Euros
>
> Resto base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Tipo aplicable
>
> –
>
> Porcentaje
>
> 0
>
> 0
>
> 6.000
>
> 19
>
> 6.000,00
>
> 1.140
>
> 44.000
>
> 21
>
> 50.000,00
>
> 10.380
>
> 150.000
>
> 23
>
> 200.000,00
>
> 44.880
>
> 100.000
>
> 27
>
> 300.000,00
>
> 71.880
>
> En adelante
>
> 28
>
> 2.º La cuantía resultante se minorará en el importe derivado de aplicar a la parte de la base liquidable del ahorro correspondiente al mínimo personal y familiar, la escala prevista en el número 1.º anterior.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2023. 22 casilla(s); 2 construct(s); 6 formula(s); 1 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-02`.

### 31. `ley-35-2006:art-67`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a67`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Cuota líquida estatal."
  - "La cuota líquida estatal del Impuesto será el resultado de disminuir la cuota íntegra estatal"
  - "deducción por inversión en empresas de nueva o reciente creación"
  - "50 por ciento del importe total de las deducciones"
  - "no podrá ser negativo"
- `notes` (verbatim): "LIRPF art 67: defines the cuota liquida estatal by reducing the prior state tax amount through the art 68.1 new/recent company investment deduction and 50 percent of the art 68.2-68.5 deductions, with a non-negative floor. Base legal para Modelo 100 casillas 0570 and 0585."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 67. Cuota líquida estatal.
>
> 1. La cuota líquida estatal del Impuesto será el resultado de disminuir la cuota íntegra estatal en la suma de:
>
> a) La deducción por inversión en empresas de nueva o reciente creación prevista en el apartado 1 del artículo 68 de esta Ley.
>
> b) El 50 por ciento del importe total de las deducciones previstas en los apartados 2, 3, 4 y 5 del artículo 68 de esta Ley.
>
> 2. El resultado de las operaciones a que se refiere el apartado anterior no podrá ser negativo.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 30 casilla(s); 8 construct(s); 47 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 32. `ley-35-2006:art-76`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a76`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2024-12-22
- `required_text`:
  - "Tipo de gravamen del ahorro."
  - "base liquidable del ahorro que exceda"
  - "A la base liquidable del ahorro se le aplicarán los tipos"
  - "se minorará en el importe derivado de aplicar"
- `notes` (verbatim): "LIRPF art 76: current autonomic savings-scale article for base liquidable del ahorro, including the personal/family minimum reduction mechanism. The selected BOE redaction is published 2024-12-21 and in force from 2024-12-22; the source note states effects from 2025-01-01 for the Ley 7/2024 change. Base legal para Modelo 100 autonomic savings-scale parameters and formulas."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 76. Tipo de gravamen del ahorro.
>
> La parte de base liquidable del ahorro que exceda, en su caso, del importe del mínimo personal y familiar que resulte de los incrementos o disminuciones a que se refiere el artículo 56.3 de esta ley, será gravada de la siguiente forma:
>
> 1.º A la base liquidable del ahorro se le aplicarán los tipos que se indican en la siguiente escala:
>
> Base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Cuota íntegra
>
> –
>
> Euros
>
> Resto base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Tipo aplicable
>
> –
>
> Porcentaje
>
> 0
>
> 0
>
> 6.000
>
> 9,5
>
> 6.000,00
>
> 570
>
> 44.000
>
> 10,5
>
> 50.000,00
>
> 5.190
>
> 150.000
>
> 11,5
>
> 200.000,00
>
> 22.440
>
> 100.000
>
> 13,5
>
> 300.000,00
>
> 35.940
>
> En adelante
>
> 15
>
> 2.º La cuantía resultante se minorará en el importe derivado de aplicar a la parte de la base liquidable del ahorro correspondiente al mínimo personal y familiar que resulte de los incrementos o disminuciones a que se refiere el artículo 56.3 de esta ley, la escala prevista en el número 1.º anterior.
>
> Se modifica, con efectos desde el 1 de enero de 2025, por la disposicion final 7.2 de la Ley 7/2024, de 20 de diciembre. Ref. BOE-A-2024-26694
>
> Se modifica por el art. 63.2 de la Ley 31/2022, de 23 de diciembre. Ref. BOE-A-2022-22128
>
> Se modifica, con efectos desde 1 de enero de 2021, por el art. 59.2 de la Ley 11/2020, de 30 de diciembre. Ref. BOE-A-2020-17339
>
> Se modifica por el art. 1.51 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Se modifica, con efectos desde 1 de enero de 2010, por el art. 63.2 de la Ley 39/2010, de 22 de diciembre. Ref. BOE-A-2010-19703.
>
> Se modifica, con efectos desde el 1 de enero de 2010 por el art. 69.2 de la Ley 26/2009, de 23 de diciembre. Ref. BOE-A-2009-20765
>
> Redactado conforme a la corrección de errores pubicada en BOE núm. 96, de 21 de abril de 2010. Ref. BOE-A-2010-6285
>
> Se modifica por la disposición final 2.11 de la Ley 22/2009, de 18 de diciembre. Ref. BOE-A-2009-20375
>
> Esta modificación entra en vigor y surte efectos desde el 1 de enero de 2010, según establece la disposición final 5.
>
> Sección 2.ª Determinación de la cuota líquida autonómica

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate/bracket table (percentages and euro thresholds laid out as table rows rather than in a sentence carrying "por ciento" or "euros" adjacent to the figure -- caught by a dedicated table-shape check after the phrase-adjacency scan first missed it; see the packet preamble) -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2024, 2025. 2 casilla(s); 3 construct(s); 12 formula(s); 2 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 33. `ley-35-2006:art-76-2015`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-76-2015.html#a76`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Tipo de gravamen del ahorro."
  - "base liquidable del ahorro que exceda"
  - "50.000,00"
  - "5.190"
  - "En adelante"
  - "11,5"
- `notes` (verbatim): "LIRPF art 76, redaction selected by BOE at 2014-11-28 (art. 1.51 Ley 26/2014, BOE-A-2014-12327), in force 2015-01-01 to 2020-12-31: three-bracket autonómica savings scale mirroring art. 66's pre-2021 brackets, before Ley 11/2020 art. 59.2 added the fourth bracket with effect from 2021-01-01. Grounds the 2020 Modelo 100 base liquidable del ahorro autonómica scale casillas and formulas."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 76. Tipo de gravamen del ahorro.
>
> La parte de base liquidable del ahorro que exceda, en su caso, del importe del mínimo personal y familiar que resulte de los incrementos o disminuciones a que se refiere el artículo 56.3 de esta Ley, será gravada de la siguiente forma:
>
> 1.º A la base liquidable del ahorro se le aplicarán los tipos que se indican en la siguiente escala:
>
> Base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Cuota íntegra
>
> –
>
> Euros
>
> Resto base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Tipo aplicable
>
> –
>
> Porcentaje
>
> 0
>
> 0
>
> 6.000
>
> 9,5
>
> 6.000,00
>
> 570
>
> 44.000
>
> 10,5
>
> 50.000,00
>
> 5.190
>
> En adelante
>
> 11,5
>
> 2.º La cuantía resultante se minorará en el importe derivado de aplicar a la parte de la base liquidable del ahorro correspondiente al mínimo personal y familiar que resulte de los incrementos o disminuciones a que se refiere el artículo 56.3 de esta Ley, la escala prevista en el número 1.º anterior.
>
> Se modifica por el art. 1.51 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Se modifica, con efectos desde 1 de enero de 2010, por el art. 63.2 de la Ley 39/2010, de 22 de diciembre. Ref. BOE-A-2010-19703.
>
> Se modifica, con efectos desde el 1 de enero de 2010 por el art. 69.2 de la Ley 26/2009, de 23 de diciembre. Ref. BOE-A-2009-20765
>
> Redactado conforme a la corrección de errores pubicada en BOE núm. 96, de 21 de abril de 2010. Ref. BOE-A-2010-6285

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate/bracket table (percentages and euro thresholds laid out as table rows rather than in a sentence carrying "por ciento" or "euros" adjacent to the figure -- caught by a dedicated table-shape check after the phrase-adjacency scan first missed it; see the packet preamble) -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020. 2 construct(s); 6 formula(s); 1 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-02`.

### 34. `rd-439-2007:art-109`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/rd-439-2007-art-109.html#a109`
- `document_id`: `BOE-A-2007-6820`; `effective_from`: 2007-03-31
- `required_text`:
  - "Obligados al pago fraccionado"
  - "actividades económicas estarán obligados a autoliquidar e ingresar en el Tesoro"
  - "70 por ciento de los ingresos"
  - "inicio de la actividad"
- `notes` (verbatim): "RIRPF art 109: obligados al pago fraccionado. Establece que los contribuyentes que ejercen actividades economicas autoliquidan e ingresan pagos fraccionados de IRPF y recoge las excepciones por retenciones o ingresos a cuenta iguales o superiores al 70 por ciento."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 109. Obligados al pago fraccionado.
>
> 1. Los contribuyentes que ejerzan actividades económicas estarán obligados a autoliquidar e ingresar en el Tesoro, en concepto de pago a cuenta del Impuesto sobre la Renta de las Personas Físicas, la cantidad que resulte de lo establecido en los artículos siguientes, sin perjuicio de las excepciones previstas en los apartados siguientes.
>
> 2. Los contribuyentes que desarrollen actividades profesionales no estarán obligados a efectuar pago fraccionado en relación con las mismas si, en el año natural anterior, al menos el 70 por ciento de los ingresos de la actividad fueron objeto de retención o ingreso a cuenta.
>
> 3. Los contribuyentes que desarrollen actividades agrícolas o ganaderas no estarán obligados a efectuar pago fraccionado en relación con las mismas si, en el año natural anterior, al menos el 70 por ciento de los ingresos procedentes de la explotación, con excepción de las subvenciones corrientes y de capital y de las indemnizaciones, fueron objeto de retención o ingreso a cuenta.
>
> 4. Los contribuyentes que desarrollen actividades forestales no estarán obligados a efectuar pago fraccionado en relación con las mismas si, en el año natural anterior, al menos el 70 por ciento de los ingresos procedentes de la actividad, con excepción de las subvenciones corrientes y de capital y de las indemnizaciones, fueron objeto de retención o ingreso a cuenta.
>
> 5. A efectos de lo dispuesto en los apartados 2, 3 y 4 anteriores, en caso de inicio de la actividad se tendrá en cuenta el porcentaje de ingresos que hayan sido objeto de retención o ingreso a cuenta durante el período a que se refiere el pago fraccionado.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 6 application_link(s); 12 binding(s); 2 casilla(s); 12 construct(s); 5 deadline_window(s); 12 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-27`.

Also cited by modelo(s): 130.

## Procedural (aprobacion anual del modelo / plazos)

### 35. `ley-19-1994:art-43`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-19-1994-art-43.html#a43`
- `document_id`: `BOE-A-1994-15794`; `effective_from`: 1994-07-08
- `required_text`:
  - "Tipo de gravamen especial"
  - "4%"
- `notes` (verbatim): "Ley 19/1994 art 43: Impuesto sobre Sociedades, tipo de gravamen especial. Grounds the 4 percent ZEC reduced-rate parameter used by Modelo 100."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 43. Impuesto sobre Sociedades. Tipo de gravamen especial.
>
> El tipo de gravamen especial aplicable será del 4%.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2025. 1 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 36. `ley-35-2006:art-68`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a68`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2023-01-01
- `required_text`:
  - "Deducciones."
  - "Deducción por inversión en empresas de nueva o reciente creación"
  - "50 por ciento de las cantidades satisfechas"
  - "La base máxima de deducción será de 100.000 euros anuales"
  - "Deducciones en actividades económicas"
  - "Deducciones por donativos y otras aportaciones"
  - "Deducción por rentas obtenidas en Ceuta o Melilla"
  - "actuaciones para la protección y difusión del Patrimonio Histórico Español"
- `notes` (verbatim): "LIRPF art 68: broad state deduction catalogue for new/recent company investment, economic-activity incentives, donations and other contributions, Ceuta/Melilla income, and cultural-heritage actions. Specific sub-article entries (68.1-68.5) remain the preferred fine-grained refs for formulas; this broad entry grounds aggregate deduction-chain surfaces."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 68. Deducciones.
>
> 1. Deducción por inversión en empresas de nueva o reciente creación.
>
> 1.º Los contribuyentes podrán deducirse el 50 por ciento de las cantidades satisfechas en el período de que se trate por la suscripción de acciones o participaciones en empresas de nueva o reciente creación, cuando se cumpla lo dispuesto en los números 2.º y 3.º de este apartado, pudiendo, además de la aportación temporal al capital, aportar sus conocimientos empresariales o profesionales adecuados para el desarrollo de la entidad en la que invierten, en los términos que establezca el acuerdo de inversión entre el contribuyente y la entidad.
>
> La base máxima de deducción será de 100.000 euros anuales y estará formada por el valor de adquisición de las acciones o participaciones suscritas.
>
> No formarán parte de la base de deducción las cantidades satisfechas por la suscripción de acciones o participaciones cuando respecto de tales cantidades el contribuyente practique una deducción establecida por la Comunidad Autónoma en el ejercicio de las competencias previstas en la Ley 22/2009, de 18 de diciembre, por la que se regula el sistema de financiación de las Comunidades Autónomas de régimen común y Ciudades con Estatuto de Autonomía y se modifican determinadas normas tributarias.
>
> 2.º La entidad cuyas acciones o participaciones se adquieran deberá cumplir los siguientes requisitos:
>
> a) Revestir la forma de Sociedad Anónima, Sociedad de Responsabilidad Limitada, Sociedad Anónima Laboral o Sociedad de Responsabilidad Limitada Laboral, en los términos previstos en el texto refundido de la Ley de Sociedades de Capital, aprobado por el Real Decreto Legislativo 1/2010, de 2 de julio, y en la Ley 44/2015, de 14 de octubre, de Sociedades Laborales y Participadas, y no estar admitida a negociación en ningún mercado organizado, tanto mercado regulado como sistemas multilaterales de negociación.
>
> Este requisito deberá cumplirse durante todos los años de tenencia de la acción o participación.
>
> b) Ejercer una actividad económica que cuente con los medios personales y materiales para el desarrollo de la misma. En particular, no podrá tener por actividad la gestión de un patrimonio mobiliario o inmobiliario a que se refiere el artículo 4.8.dos.a) de la Ley 19/1991, de 6 de junio, del Impuesto sobre el Patrimonio, en ninguno de los períodos impositivos de la entidad concluidos con anterioridad a la transmisión de la participación.
>
> c) El importe de la cifra de los fondos propios de la entidad no podrá ser superior a 400.000 euros en el inicio del período impositivo de la misma en que el contribuyente adquiera las acciones o participaciones.
>
> Cuando la entidad forme parte de un grupo de sociedades en el sentido del artículo 42 del Código de Comercio, con independencia de la residencia y de la obligación de formular cuentas anuales consolidadas, el importe de los fondos propios se referirá al conjunto de entidades pertenecientes a dicho grupo.
>
> 3.º A efectos de aplicar lo dispuesto en el apartado 1.º anterior deberán cumplirse las siguientes condiciones:
>
> a) Las acciones o participaciones en la entidad deberán adquirirse por el contribuyente bien en el momento de la constitución de aquella o mediante ampliación de capital efectuada, con carácter general, en los cinco años siguientes a dicha constitución, o en los siete años siguientes a dicha constitución en el caso de empresas emergentes a las que se refiere el apartado 1 del artículo 3 de la Ley 28/2022, de 21 de diciembre, de fomento del ecosistema de las empresas emergentes, y permanecer en su patrimonio por un plazo superior a tres años e inferior a doce años.
>
> b) La participación directa o indirecta del contribuyente, junto con la que posean en la misma entidad su cónyuge o cualquier persona unida al contribuyente por parentesco, en línea recta o colateral, por consanguinidad o afinidad, hasta el segundo grado incluido, no puede ser, durante ningún día de los años naturales de tenencia de la participación, superior al 40 por ciento del capital social de la entidad o de sus derechos de voto. Lo dispuesto en esta letra no resultará de aplicación a los socios fundadores de una empresa emergente a las que se refiere la Ley 28/2022, de 21 de diciembre, de fomento del ecosistema de las empresas emergentes, entendidos como aquellos que figuren en la escritura pública de constitución de la misma.
>
> c) Que no se trate de acciones o participaciones en una entidad a través de la cual se ejerza la misma actividad que se venía ejerciendo anteriormente mediante otra titularidad.
>
> 4.º Cuando el contribuyente transmita acciones o participaciones y opte por la aplicación de la exención prevista en el apartado 2 del artículo 38 de esta ley, únicamente formará parte de la base de la deducción correspondiente a las nuevas acciones o participaciones suscritas la parte de la reinversión que exceda del importe total obtenido en la transmisión de aquellas. En ningún caso se podrá practicar deducción por las nuevas acciones o participaciones mientras las cantidades invertidas no superen la citada cuantía.
>
> 5.º Para la práctica de la deducción será necesario obtener una certificación expedida por la entidad cuyas acciones o participaciones se hayan adquirido indicando el cumplimiento de los requisitos señalados en el número 2.º anterior en el período impositivo en el que se produjo la adquisición de las mismas.
>
> 2. Deducciones en actividades económicas.
>
> a) A los contribuyentes por este Impuesto que ejerzan actividades económicas les serán de aplicación los incentivos y estímulos a la inversión empresarial establecidos o que se establezcan en la normativa del Impuesto sobre Sociedades con igualdad de porcentajes y límites de deducción, con excepción de lo dispuesto en los apartados 2 y 3 del artículo 39 de la Ley del Impuesto sobre Sociedades.
>
> b) Adicionalmente, los contribuyentes que cumplan los requisitos establecidos en el artículo 101 de la Ley del Impuesto sobre Sociedades podrán deducir los rendimientos netos de actividades económicas del período impositivo que se inviertan en elementos nuevos del inmovilizado material o inversiones inmobiliarias afectos a actividades económicas desarrolladas por el contribuyente.
>
> Se entenderá que los rendimientos netos de actividades económicas del período impositivo son objeto de inversión cuando se invierta una cuantía equivalente a la parte de la base liquidable general positiva del período impositivo que corresponda a tales rendimientos, sin que en ningún caso la misma cuantía pueda entenderse invertida en más de un activo.
>
> La inversión en elementos patrimoniales afectos a actividades económicas deberá realizarse en el período impositivo en que se obtengan los rendimientos objeto de reinversión o en el período impositivo siguiente.
>
> La inversión se entenderá efectuada en la fecha en que se produzca la puesta a disposición de los elementos patrimoniales, incluso en el supuesto de elementos patrimoniales que sean objeto de los contratos de arrendamiento financiero a los que se refiere el apartado 1 de la disposición adicional séptima de la Ley 26/1988, de 29 de julio, sobre disciplina e intervención de las entidades de crédito. No obstante, en este último caso, la deducción estará condicionada, con carácter resolutorio, al ejercicio de la opción de compra.
>
> La deducción se practicará en la cuota íntegra correspondiente al período impositivo en que se efectúe la inversión.
>
> La base de la deducción será la cuantía invertida a que se refiere el segundo párrafo de esta letra b).
>
> El porcentaje de deducción será del 5 por ciento. No obstante, el porcentaje de deducción será del 2,5 por ciento cuando el contribuyente hubiera practicado la reducción prevista en el apartado 3 del artículo 32 de esta Ley o se trate de rentas obtenidas en Ceuta y Melilla respecto de las que se hubiera aplicado la deducción prevista en el artículo 68.4 de esta Ley.
>
> El importe de la deducción no podrá exceder de la suma de la cuota íntegra estatal y autonómica del período impositivo en el que se obtuvieron los rendimientos netos de actividades económicas señalados en el primer párrafo de esta letra b).
>
> Los elementos patrimoniales objeto de inversión deberán permanecer en funcionamiento en el patrimonio del contribuyente, salvo pérdida justificada, durante un plazo de 5 años, o durante su vida útil de resultar inferior.
>
> No obstante, no se perderá la deducción si se produce la transmisión de los elementos patrimoniales objeto de inversión antes de la finalización del plazo señalado en el párrafo anterior y se invierte el importe obtenido o el valor neto contable, si fuera menor, en los términos establecidos en este artículo.
>
> Esta deducción es incompatible con la aplicación de la libertad de amortización, con la deducción por inversiones regulada en el artículo 94 de la Ley 20/1991, de 7 de junio, de modificación de los aspectos fiscales del Régimen Económico Fiscal de Canarias, y con la Reserva para inversiones en Canarias regulada en el artículo 27 de la Ley 19/1994, de 6 de julio, de modificación del Régimen Económico y Fiscal de Canarias.
>
> c) Los contribuyentes por este Impuesto que ejerzan actividades económicas y determinen su rendimiento neto por el método de estimación objetiva sólo les serán de aplicación los incentivos a que se refiere este apartado 2 cuando así se establezca reglamentariamente teniendo en cuenta las características y obligaciones formales del citado método.
>
> 3. Deducciones por donativos y otras aportaciones.
>
> Los contribuyentes podrán aplicar, en este concepto:
>
> a) Las deducciones previstas en la Ley 49/2002, de 23 de diciembre, de régimen fiscal de las entidades sin fines lucrativos y de los incentivos fiscales al mecenazgo.
>
> b) El 10 por ciento de las cantidades donadas a las fundaciones legalmente reconocidas que rindan cuentas al órgano del protectorado correspondiente, así como a las asociaciones declaradas de utilidad pública, no comprendidas en el párrafo anterior.
>
> c) El 20 por ciento de las cuotas de afiliación y las aportaciones a Partidos Políticos, Federaciones, Coaliciones o Agrupaciones de Electores. La base máxima de esta deducción será de 600 euros anuales y estará constituida por las cuotas de afiliación y aportaciones previstas en la letra a) del apartado Dos del artículo 2 de la Ley Orgánica 8/2007, de 4 de julio, sobre financiación de los partidos políticos.
>
> 4. Deducción por rentas obtenidas en Ceuta o Melilla.
>
> 1.º Contribuyentes residentes en Ceuta o Melilla.
>
> a) Los contribuyentes que tengan su residencia habitual y efectiva en Ceuta o Melilla se deducirán el 60 por ciento de la parte de la suma de las cuotas íntegras estatal y autonómica que proporcionalmente corresponda a las rentas computadas para la determinación de las bases liquidables que hubieran sido obtenidas en Ceuta o Melilla.
>
> b) También aplicarán esta deducción los contribuyentes que mantengan su residencia habitual y efectiva en Ceuta o Melilla durante un plazo no inferior a tres años, en los períodos impositivos iniciados con posterioridad al final de ese plazo, por las rentas obtenidas fuera de dichas ciudades cuando, al menos, una tercera parte del patrimonio neto del contribuyente, determinado conforme a la normativa reguladora del Impuesto sobre el Patrimonio, esté situado en dichas ciudades.
>
> La cuantía máxima de las rentas, obtenidas fuera de dichas ciudades, que puede acogerse a esta deducción será el importe neto de los rendimientos y ganancias y pérdidas patrimoniales obtenidos en dichas ciudades.
>
> 2.º Los contribuyentes que no tengan su residencia habitual y efectiva en Ceuta o Melilla, se deducirán el 60 por ciento de la parte de la suma de las cuotas íntegras estatal y autonómica que proporcionalmente corresponda a las rentas computadas para la determinación de las bases liquidables positivas que hubieran sido obtenidas en Ceuta o Melilla.
>
> En ningún caso se aplicará esta deducción a las rentas siguientes:
>
> – Las procedentes de Instituciones de Inversión Colectiva, salvo cuando la totalidad de sus activos esté invertida en Ceuta o Melilla, en las condiciones que reglamentariamente se determinen.
>
> – Las rentas a las que se refieren los párrafos a), e) e i) del apartado siguiente.
>
> 3.º A los efectos previstos en esta Ley, se considerarán rentas obtenidas en Ceuta o Melilla las siguientes:
>
> a) Los rendimientos del trabajo, cuando se deriven de trabajos de cualquier clase realizados en dichos territorios.
>
> b) Los rendimientos que procedan de la titularidad de bienes inmuebles situados en Ceuta o Melilla o de derechos reales que recaigan sobre los mismos.
>
> c) Las que procedan del ejercicio de actividades económicas efectivamente realizadas, en las condiciones que reglamentariamente se determinen, en Ceuta o Melilla.
>
> d) Las ganancias patrimoniales que procedan de bienes inmuebles radicados en Ceuta o Melilla.
>
> e) Las ganancias patrimoniales que procedan de bienes muebles situados en Ceuta o Melilla.
>
> f) Los rendimientos del capital mobiliario procedentes de obligaciones o préstamos, cuando los capitales se hallen invertidos en dichos territorios y allí generen las rentas correspondientes.
>
> g) Los rendimientos del capital mobiliario procedentes del arrendamiento de bienes muebles, negocios o minas, en las condiciones que reglamentariamente se determinen.
>
> h) Las rentas procedentes de sociedades que operen efectiva y materialmente en Ceuta o Melilla que correspondan a rentas a las que resulte de aplicación la bonificación establecida en el artículo 33 de la Ley del Impuesto sobre Sociedades, en los siguientes supuestos:
>
> 1.º Cuando tengan su domicilio y objeto social exclusivo en dichos territorios.
>
> 2.º Cuando operen efectiva y materialmente en Ceuta o Melilla durante un plazo no inferior a tres años y obtengan rentas fuera de dichas ciudades, siempre que respecto de estas rentas tengan derecho a la aplicación de la bonificación prevista en el apartado 6 del artículo 33 de la Ley del Impuesto sobre Sociedades. A estos efectos deberán identificarse, en los términos que reglamentariamente se establezcan, las reservas procedentes de rentas a las que hubieran resultado de aplicación la bonificación establecida en el artículo 33 de la Ley del Impuesto sobre Sociedades.
>
> i) Los rendimientos procedentes de depósitos o cuentas en toda clase de instituciones financieras situadas en Ceuta o Melilla.
>
> 5. Deducción por actuaciones para la protección y difusión del Patrimonio Histórico Español y de las ciudades, conjuntos y bienes declarados Patrimonio Mundial.
>
> Los contribuyentes tendrán derecho a una deducción en la cuota del 15 por ciento del importe de las inversiones o gastos que realicen para:
>
> a) La adquisición de bienes del Patrimonio Histórico Español, realizada fuera del territorio español para su introducción dentro de dicho territorio, siempre que los bienes sean declarados bienes de interés cultural o incluidos en el Inventario general de bienes muebles en el plazo de un año desde su introducción y permanezcan en territorio español y dentro del patrimonio del titular durante al menos cuatro años.
>
> La base de esta deducción será la valoración efectuada por la Junta de calificación, valoración y exportación de bienes del patrimonio histórico español.
>
> b) La conservación, reparación, restauración, difusión y exposición de los bienes de su propiedad que estén declarados de interés cultural conforme a la normativa del patrimonio histórico del Estado y de las comunidades autónomas, siempre y cuando se cumplan las exigencias establecidas en dicha normativa, en particular respecto de los deberes de visita y exposición pública de dichos bienes.
>
> c) La rehabilitación de edificios, el mantenimiento y reparación de sus tejados y fachadas, así como la mejora de infraestructuras de su propiedad situados en el entorno que sea objeto de protección de las ciudades españolas o de los conjuntos arquitectónicos, arqueológicos, naturales o paisajísticos y de los bienes declarados Patrimonio Mundial por la Unesco situados en España.
>
> 6. Deducción por cuenta ahorro-empresa.
>
> (Suprimido)
>
> 7. Deducción por alquiler de la vivienda habitual.
>
> (Suprimido)
>
> Se modifica el apartado 1, con efectos de 1 de enero de 2023, por la disposición final 3.4 de la Ley 28/2022, de 21 de diciembre. Ref. BOE-A-2022-21739
>
> Se modifican, con efectos desde 1 de enero de 2018, los apartados 1.1 y 4.1 y 2 por los arts. 66 y 60 de la Ley 6/2018, de 3 de julio. Ref. BOE-A-2018-9268
>
> Se modifican los apartados 1.1, 2, 3 y 4.3.h) y se suprimen los apartados 6 y 7 por el art. 1.44 a 48 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Se añade el apartado 1 y se modifica el apartado 2 por el art. 27.4 y 5 de la Ley 14/2013, de 27 de septiembre. Ref. BOE-A-2013-10074.
>
> La modificación del apartado 2 surte efectos desde el 1 de enero de 2013, según establece la disposición final 13.f).
>
> Se suprime el apartado 1, con efectos desde el 1 de enero de 2013, por el art. 1.2 de la Ley 16/2012, de 27 de diciembre. Ref. BOE-A-2012-15650.
>
> Se modifica el apartado 1, con efectos desde 1 de enero de 2011, por la disposición final 2.2º.1 del Real Decreto-ley 20/2011, de 30 de diciembre. Ref. BOE-A-2011-20638.
>
> Se modifican los apartados 1 y 7, con efectos desde 1 de enero de 2011, por los arts. 67.1 y 68 de la Ley 39/2010, de 22 de diciembre. Ref. BOE-A-2010-19703.
>
> Se modifica el apartado 1 por la disposición final 2.8 de la Ley 22/2009, de 18 de diciembre. Ref. BOE-A-2009-20375
>
> Esta modificación entra en vigor y surte efectos desde 1 de enero de 2010, según establece la disposición final 5.
>
> Se añade el apartado 7, con efectos desde 1 de enero de 2008 por la disposición final 6.2.2 de la Ley 51/2007, de 28 de diciembre. Ref. BOE-A-2007-22295
>
> Redactado el apartado 1.4.d) conforme a la corrección de errores publicada en BOE núm. 57, de 7 de marzo de 2007. Ref. BOE-A-2007-4731

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2023, 2024, 2025. 4 construct(s); 3 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 37. `ley-35-2006:art-68-2018`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-68-2018.html#a68`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2018-07-05
- `required_text`:
  - "Deducción por inversión en empresas de nueva o reciente creación."
  - "30 por ciento de las cantidades satisfechas"
  - "La base máxima de deducción será de 60.000 euros anuales"
  - "Deducciones en actividades económicas"
  - "Deducciones por donativos y otras aportaciones"
  - "Deducción por rentas obtenidas en Ceuta o Melilla"
- `notes` (verbatim): "LIRPF art 68, redaction selected by BOE at 2018-07-04, in force 2018-07-05 to 2022-12-31: the empresas-de-nueva-creación deduction was 30 percent of the amounts invested with a 60.000 euros annual maximum base, before Ley 28/2022 art. 3 (Startups law) increased it to 50 percent and 100.000 euros with effect from 2023-01-01. Grounds the 2020 and 2021 Modelo 100 deducción por inversión en empresas de nueva o reciente creación casillas and formulas."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 68. Deducciones.
>
> 1. Deducción por inversión en empresas de nueva o reciente creación.
>
> 1.º Los contribuyentes podrán deducirse el 30 por ciento de las cantidades satisfechas en el período de que se trate por la suscripción de acciones o participaciones en empresas de nueva o reciente creación cuando se cumpla lo dispuesto en los números 2.º y 3.º de este apartado, pudiendo, además de la aportación temporal al capital, aportar sus conocimientos empresariales o profesionales adecuados para el desarrollo de la entidad en la que invierten en los términos que establezca el acuerdo de inversión entre el contribuyente y la entidad.
>
> La base máxima de deducción será de 60.000 euros anuales y estará formada por el valor de adquisición de las acciones o participaciones suscritas.
>
> No formarán parte de la base de deducción las cantidades satisfechas por la suscripción de acciones o participaciones cuando respecto de tales cantidades el contribuyente practique una deducción establecida por la Comunidad Autónoma en el ejercicio de las competencias previstas en la Ley 22/2009, de 18 de diciembre, por la que se regula el sistema de financiación de las Comunidades Autónomas de régimen común y Ciudades con Estatuto de Autonomía y se modifican determinadas normas tributarias.
>
> 2.º La entidad cuyas acciones o participaciones se adquieran deberá cumplir los siguientes requisitos:
>
> a) Revestir la forma de Sociedad Anónima, Sociedad de Responsabilidad Limitada, Sociedad Anónima Laboral o Sociedad de Responsabilidad Limitada Laboral, en los términos previstos en el texto refundido de la Ley de Sociedades de Capital, aprobado por el Real Decreto Legislativo 1/2010, de 2 de julio, y en la Ley 4/1997, de 24 de marzo, de Sociedades Laborales, y no estar admitida a negociación en ningún mercado organizado.
>
> Este requisito deberá cumplirse durante todos los años de tenencia de la acción o participación.
>
> b) Ejercer una actividad económica que cuente con los medios personales y materiales para el desarrollo de la misma. En particular, no podrá tener por actividad la gestión de un patrimonio mobiliario o inmobiliario a que se refiere el artículo 4.8.Dos.a) de la Ley 19/1991, de 6 de junio, del Impuesto sobre el Patrimonio, en ninguno de los períodos impositivos de la entidad concluidos con anterioridad a la transmisión de la participación.
>
> c) El importe de la cifra de los fondos propios de la entidad no podrá ser superior a 400.000 euros en el inicio del período impositivo de la misma en que el contribuyente adquiera las acciones o participaciones.
>
> Cuando la entidad forme parte de un grupo de sociedades en el sentido del artículo 42 del Código de Comercio, con independencia de la residencia y de la obligación de formular cuentas anuales consolidadas, el importe de los fondos propios se referirá al conjunto de entidades pertenecientes a dicho grupo.
>
> 3.º A efectos de aplicar lo dispuesto en el apartado 1.º anterior deberán cumplirse las siguientes condiciones:
>
> a) Las acciones o participaciones en la entidad deberán adquirirse por el contribuyente bien en el momento de la constitución de aquélla o mediante ampliación de capital efectuada en los tres años siguientes a dicha constitución y permanecer en su patrimonio por un plazo superior a tres años e inferior a doce años.
>
> b) La participación directa o indirecta del contribuyente, junto con la que posean en la misma entidad su cónyuge o cualquier persona unida al contribuyente por parentesco, en línea recta o colateral, por consanguinidad o afinidad, hasta el segundo grado incluido, no puede ser, durante ningún día de los años naturales de tenencia de la participación, superior al 40 por ciento del capital social de la entidad o de sus derechos de voto.
>
> c) Que no se trate de acciones o participaciones en una entidad a través de la cual se ejerza la misma actividad que se venía ejerciendo anteriormente mediante otra titularidad.
>
> 4.º Cuando el contribuyente transmita acciones o participaciones y opte por la aplicación de la exención prevista en el apartado 2 del artículo 38 de esta Ley, únicamente formará parte de la base de la deducción correspondiente a las nuevas acciones o participaciones suscritas la parte de la reinversión que exceda del importe total obtenido en la transmisión de aquellas. En ningún caso se podrá practicar deducción por las nuevas acciones o participaciones mientras las cantidades invertidas no superen la citada cuantía.
>
> 5.º Para la práctica de la deducción será necesario obtener una certificación expedida por la entidad cuyas acciones o participaciones se hayan adquirido indicando el cumplimiento de los requisitos señalados en el número 2.º anterior en el período impositivo en el que se produjo la adquisición de las mismas.
>
> 2. Deducciones en actividades económicas.
>
> a) A los contribuyentes por este Impuesto que ejerzan actividades económicas les serán de aplicación los incentivos y estímulos a la inversión empresarial establecidos o que se establezcan en la normativa del Impuesto sobre Sociedades con igualdad de porcentajes y límites de deducción, con excepción de lo dispuesto en los apartados 2 y 3 del artículo 39 de la Ley del Impuesto sobre Sociedades.
>
> b) Adicionalmente, los contribuyentes que cumplan los requisitos establecidos en el artículo 101 de la Ley del Impuesto sobre Sociedades podrán deducir los rendimientos netos de actividades económicas del período impositivo que se inviertan en elementos nuevos del inmovilizado material o inversiones inmobiliarias afectos a actividades económicas desarrolladas por el contribuyente.
>
> Se entenderá que los rendimientos netos de actividades económicas del período impositivo son objeto de inversión cuando se invierta una cuantía equivalente a la parte de la base liquidable general positiva del período impositivo que corresponda a tales rendimientos, sin que en ningún caso la misma cuantía pueda entenderse invertida en más de un activo.
>
> La inversión en elementos patrimoniales afectos a actividades económicas deberá realizarse en el período impositivo en que se obtengan los rendimientos objeto de reinversión o en el período impositivo siguiente.
>
> La inversión se entenderá efectuada en la fecha en que se produzca la puesta a disposición de los elementos patrimoniales, incluso en el supuesto de elementos patrimoniales que sean objeto de los contratos de arrendamiento financiero a los que se refiere el apartado 1 de la disposición adicional séptima de la Ley 26/1988, de 29 de julio, sobre disciplina e intervención de las entidades de crédito. No obstante, en este último caso, la deducción estará condicionada, con carácter resolutorio, al ejercicio de la opción de compra.
>
> La deducción se practicará en la cuota íntegra correspondiente al período impositivo en que se efectúe la inversión.
>
> La base de la deducción será la cuantía invertida a que se refiere el segundo párrafo de esta letra b).
>
> El porcentaje de deducción será del 5 por ciento. No obstante, el porcentaje de deducción será del 2,5 por ciento cuando el contribuyente hubiera practicado la reducción prevista en el apartado 3 del artículo 32 de esta Ley o se trate de rentas obtenidas en Ceuta y Melilla respecto de las que se hubiera aplicado la deducción prevista en el artículo 68.4 de esta Ley.
>
> El importe de la deducción no podrá exceder de la suma de la cuota íntegra estatal y autonómica del período impositivo en el que se obtuvieron los rendimientos netos de actividades económicas señalados en el primer párrafo de esta letra b).
>
> Los elementos patrimoniales objeto de inversión deberán permanecer en funcionamiento en el patrimonio del contribuyente, salvo pérdida justificada, durante un plazo de 5 años, o durante su vida útil de resultar inferior.
>
> No obstante, no se perderá la deducción si se produce la transmisión de los elementos patrimoniales objeto de inversión antes de la finalización del plazo señalado en el párrafo anterior y se invierte el importe obtenido o el valor neto contable, si fuera menor, en los términos establecidos en este artículo.
>
> Esta deducción es incompatible con la aplicación de la libertad de amortización, con la deducción por inversiones regulada en el artículo 94 de la Ley 20/1991, de 7 de junio, de modificación de los aspectos fiscales del Régimen Económico Fiscal de Canarias, y con la Reserva para inversiones en Canarias regulada en el artículo 27 de la Ley 19/1994, de 6 de julio, de modificación del Régimen Económico y Fiscal de Canarias.
>
> c) Los contribuyentes por este Impuesto que ejerzan actividades económicas y determinen su rendimiento neto por el método de estimación objetiva sólo les serán de aplicación los incentivos a que se refiere este apartado 2 cuando así se establezca reglamentariamente teniendo en cuenta las características y obligaciones formales del citado método.
>
> 3. Deducciones por donativos y otras aportaciones.
>
> Los contribuyentes podrán aplicar, en este concepto:
>
> a) Las deducciones previstas en la Ley 49/2002, de 23 de diciembre, de régimen fiscal de las entidades sin fines lucrativos y de los incentivos fiscales al mecenazgo.
>
> b) El 10 por ciento de las cantidades donadas a las fundaciones legalmente reconocidas que rindan cuentas al órgano del protectorado correspondiente, así como a las asociaciones declaradas de utilidad pública, no comprendidas en el párrafo anterior.
>
> c) El 20 por ciento de las cuotas de afiliación y las aportaciones a Partidos Políticos, Federaciones, Coaliciones o Agrupaciones de Electores. La base máxima de esta deducción será de 600 euros anuales y estará constituida por las cuotas de afiliación y aportaciones previstas en la letra a) del apartado Dos del artículo 2 de la Ley Orgánica 8/2007, de 4 de julio, sobre financiación de los partidos políticos.
>
> 4. Deducción por rentas obtenidas en Ceuta o Melilla.
>
> 1.º Contribuyentes residentes en Ceuta o Melilla.
>
> a) Los contribuyentes que tengan su residencia habitual y efectiva en Ceuta o Melilla se deducirán el 60 por ciento de la parte de la suma de las cuotas íntegras estatal y autonómica que proporcionalmente corresponda a las rentas computadas para la determinación de las bases liquidables que hubieran sido obtenidas en Ceuta o Melilla.
>
> b) También aplicarán esta deducción los contribuyentes que mantengan su residencia habitual y efectiva en Ceuta o Melilla durante un plazo no inferior a tres años, en los períodos impositivos iniciados con posterioridad al final de ese plazo, por las rentas obtenidas fuera de dichas ciudades cuando, al menos, una tercera parte del patrimonio neto del contribuyente, determinado conforme a la normativa reguladora del Impuesto sobre el Patrimonio, esté situado en dichas ciudades.
>
> La cuantía máxima de las rentas, obtenidas fuera de dichas ciudades, que puede acogerse a esta deducción será el importe neto de los rendimientos y ganancias y pérdidas patrimoniales obtenidos en dichas ciudades.
>
> 2.º Los contribuyentes que no tengan su residencia habitual y efectiva en Ceuta o Melilla, se deducirán el 60 por ciento de la parte de la suma de las cuotas íntegras estatal y autonómica que proporcionalmente corresponda a las rentas computadas para la determinación de las bases liquidables positivas que hubieran sido obtenidas en Ceuta o Melilla.
>
> En ningún caso se aplicará esta deducción a las rentas siguientes:
>
> – Las procedentes de Instituciones de Inversión Colectiva, salvo cuando la totalidad de sus activos esté invertida en Ceuta o Melilla, en las condiciones que reglamentariamente se determinen.
>
> – Las rentas a las que se refieren los párrafos a), e) e i) del apartado siguiente.
>
> 3.º A los efectos previstos en esta Ley, se considerarán rentas obtenidas en Ceuta o Melilla las siguientes:
>
> a) Los rendimientos del trabajo, cuando se deriven de trabajos de cualquier clase realizados en dichos territorios.
>
> b) Los rendimientos que procedan de la titularidad de bienes inmuebles situados en Ceuta o Melilla o de derechos reales que recaigan sobre los mismos.
>
> c) Las que procedan del ejercicio de actividades económicas efectivamente realizadas, en las condiciones que reglamentariamente se determinen, en Ceuta o Melilla.
>
> d) Las ganancias patrimoniales que procedan de bienes inmuebles radicados en Ceuta o Melilla.
>
> e) Las ganancias patrimoniales que procedan de bienes muebles situados en Ceuta o Melilla.
>
> f) Los rendimientos del capital mobiliario procedentes de obligaciones o préstamos, cuando los capitales se hallen invertidos en dichos territorios y allí generen las rentas correspondientes.
>
> g) Los rendimientos del capital mobiliario procedentes del arrendamiento de bienes muebles, negocios o minas, en las condiciones que reglamentariamente se determinen.
>
> h) Las rentas procedentes de sociedades que operen efectiva y materialmente en Ceuta o Melilla que correspondan a rentas a las que resulte de aplicación la bonificación establecida en el artículo 33 de la Ley del Impuesto sobre Sociedades, en los siguientes supuestos:
>
> 1.º Cuando tengan su domicilio y objeto social exclusivo en dichos territorios.
>
> 2.º Cuando operen efectiva y materialmente en Ceuta o Melilla durante un plazo no inferior a tres años y obtengan rentas fuera de dichas ciudades, siempre que respecto de estas rentas tengan derecho a la aplicación de la bonificación prevista en el apartado 6 del artículo 33 de la Ley del Impuesto sobre Sociedades. A estos efectos deberán identificarse, en los términos que reglamentariamente se establezcan, las reservas procedentes de rentas a las que hubieran resultado de aplicación la bonificación establecida en el artículo 33 de la Ley del Impuesto sobre Sociedades.
>
> i) Los rendimientos procedentes de depósitos o cuentas en toda clase de instituciones financieras situadas en Ceuta o Melilla.
>
> 5. Deducción por actuaciones para la protección y difusión del Patrimonio Histórico Español y de las ciudades, conjuntos y bienes declarados Patrimonio Mundial.
>
> Los contribuyentes tendrán derecho a una deducción en la cuota del 15 por ciento del importe de las inversiones o gastos que realicen para:
>
> a) La adquisición de bienes del Patrimonio Histórico Español, realizada fuera del territorio español para su introducción dentro de dicho territorio, siempre que los bienes sean declarados bienes de interés cultural o incluidos en el Inventario general de bienes muebles en el plazo de un año desde su introducción y permanezcan en territorio español y dentro del patrimonio del titular durante al menos cuatro años.
>
> La base de esta deducción será la valoración efectuada por la Junta de calificación, valoración y exportación de bienes del patrimonio histórico español.
>
> b) La conservación, reparación, restauración, difusión y exposición de los bienes de su propiedad que estén declarados de interés cultural conforme a la normativa del patrimonio histórico del Estado y de las comunidades autónomas, siempre y cuando se cumplan las exigencias establecidas en dicha normativa, en particular respecto de los deberes de visita y exposición pública de dichos bienes.
>
> c) La rehabilitación de edificios, el mantenimiento y reparación de sus tejados y fachadas, así como la mejora de infraestructuras de su propiedad situados en el entorno que sea objeto de protección de las ciudades españolas o de los conjuntos arquitectónicos, arqueológicos, naturales o paisajísticos y de los bienes declarados Patrimonio Mundial por la Unesco situados en España.
>
> 6. Deducción por cuenta ahorro-empresa.
>
> (Suprimido)
>
> 7. Deducción por alquiler de la vivienda habitual.
>
> (Suprimido)
>
> Se modifican, con efectos desde 1 de enero de 2018, los apartados 1.1 y 4.1 y 2 por los arts. 66 y 60 de la Ley 6/2018, de 3 de julio. Ref. BOE-A-2018-9268
>
> Se modifican los apartados 1.1, 2, 3 y 4.3.h) y se suprimen los apartados 6 y 7 por el art. 1.44 a 48 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Se añade el apartado 1 y se modifica el apartado 2 por el art. 27.4 y 5 de la Ley 14/2013, de 27 de septiembre. Ref. BOE-A-2013-10074.
>
> La modificación del apartado 2 surte efectos desde el 1 de enero de 2013, según establece la disposición final 13.f).
>
> Se suprime el apartado 1, con efectos desde el 1 de enero de 2013, por el art. 1.2 de la Ley 16/2012, de 27 de diciembre. Ref. BOE-A-2012-15650.
>
> Se modifica el apartado 1, con efectos desde 1 de enero de 2011, por la disposición final 2.2º.1 del Real Decreto-ley 20/2011, de 30 de diciembre. Ref. BOE-A-2011-20638.
>
> Se modifican los apartados 1 y 7, con efectos desde 1 de enero de 2011, por los arts. 67.1 y 68 de la Ley 39/2010, de 22 de diciembre. Ref. BOE-A-2010-19703.
>
> Se modifica el apartado 1 por la disposición final 2.8 de la Ley 22/2009, de 18 de diciembre. Ref. BOE-A-2009-20375
>
> Esta modificación entra en vigor y surte efectos desde 1 de enero de 2010, según establece la disposición final 5.
>
> Se añade el apartado 7, con efectos desde 1 de enero de 2008 por la disposición final 6.2.2 de la Ley 51/2007, de 28 de diciembre. Ref. BOE-A-2007-22295
>
> Redactado el apartado 1.4.d) conforme a la corrección de errores publicada en BOE núm. 57, de 7 de marzo de 2007. Ref. BOE-A-2007-4731

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022. 4 construct(s); 3 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-02`.

### 38. `ley-35-2006:art-76-2021`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-76-2021.html#a76`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2021-01-01
- `required_text`:
  - "Tipo de gravamen del ahorro."
  - "150.000"
  - "200.000,00"
  - "22.440"
  - "En adelante"
- `notes` (verbatim): "LIRPF art 76, redaction selected by BOE at 2020-12-31 (art. 59.2 Ley 11/2020, BOE-A-2020-17339), in force 2021-01-01 to 2022-12-31: four-bracket autonómica savings scale adding the 13,00 percent tranche above 200.000 euros, before Ley 31/2022 art. 63.2 restructured the top brackets with effect from 2023-01-01. Grounds the 2021 and 2022 Modelo 100 base liquidable del ahorro autonómica scale casillas and formulas."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 76. Tipo de gravamen del ahorro.
>
> La parte de base liquidable del ahorro que exceda, en su caso, del importe del mínimo personal y familiar que resulte de los incrementos o disminuciones a que se refiere el artículo 56.3 de esta Ley, será gravada de la siguiente forma:
>
> 1.º A la base liquidable del ahorro se le aplicarán los tipos que se indican en la siguiente escala:
>
> Base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Cuota íntegra
>
> –
>
> Euros
>
> Resto base liquidable
>
> del ahorro
>
> –
>
> Hasta euros
>
> Tipo aplicable
>
> –
>
> Porcentaje
>
> 0
>
> 0
>
> 6.000
>
> 9,5
>
> 6.000,00
>
> 570
>
> 44.000
>
> 10,5
>
> 50.000,00
>
> 5.190
>
> 150.000
>
> 11,5
>
> 200.000,00
>
> 22.440
>
> En adelante
>
> 13,00
>
> 2.º La cuantía resultante se minorará en el importe derivado de aplicar a la parte de la base liquidable del ahorro correspondiente al mínimo personal y familiar que resulte de los incrementos o disminuciones a que se refiere el artículo 56.3 de esta Ley, la escala prevista en el número 1.º anterior.
>
> Se modifica, con efectos desde 1 de enero de 2021, por el art. 59.2 de la Ley 11/2020, de 30 de diciembre. Ref. BOE-A-2020-17339
>
> Se modifica por el art. 1.51 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Se modifica, con efectos desde 1 de enero de 2010, por el art. 63.2 de la Ley 39/2010, de 22 de diciembre. Ref. BOE-A-2010-19703.
>
> Se modifica, con efectos desde el 1 de enero de 2010 por el art. 69.2 de la Ley 26/2009, de 23 de diciembre. Ref. BOE-A-2009-20765
>
> Redactado conforme a la corrección de errores pubicada en BOE núm. 96, de 21 de abril de 2010. Ref. BOE-A-2010-6285

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2021, 2022. 3 construct(s); 12 formula(s); 2 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-02`.

### 39. `ley-35-2006:art-76-2023`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-76-2023.html#a76`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2023-01-01
- `required_text`:
  - "Tipo de gravamen del ahorro."
  - "150.000"
  - "200.000,00"
  - "22.440"
  - "100.000"
  - "13,5"
- `notes` (verbatim): "LIRPF art 76, redaction selected by BOE at 2022-12-24 (art. 63.2 Ley 31/2022, BOE-A-2022-22128), in force 2023-01-01 to 2024-12-21: five-bracket autonómica savings scale adding the 13,5/14 percent tranches above 200.000/300.000 euros, before the 2024-12-22 redaction. Grounds the 2023 Modelo 100 base liquidable del ahorro autonómica scale casillas and formulas."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 76. Tipo de gravamen del ahorro.
>
> La parte de base liquidable del ahorro que exceda, en su caso, del importe del mínimo personal y familiar que resulte de los incrementos o disminuciones a que se refiere el artículo 56.3 de esta ley, será gravada de la siguiente forma:
>
> 1.º A la base liquidable del ahorro se le aplicarán los tipos que se indican en la siguiente escala:
>
> Base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Cuota íntegra
>
> –
>
> Euros
>
> Resto base liquidable del ahorro
>
> –
>
> Hasta euros
>
> Tipo aplicable
>
> –
>
> Porcentaje
>
> 0
>
> 0
>
> 6.000
>
> 9,5
>
> 6.000,00
>
> 570
>
> 44.000
>
> 10,5
>
> 50.000,00
>
> 5.190
>
> 150.000
>
> 11,5
>
> 200.000,00
>
> 22.440
>
> 100.000
>
> 13,5
>
> 300.000,00
>
> 35.940
>
> En adelante
>
> 14
>
> 2.º La cuantía resultante se minorará en el importe derivado de aplicar a la parte de la base liquidable del ahorro correspondiente al mínimo personal y familiar que resulte de los incrementos o disminuciones a que se refiere el artículo 56.3 de esta ley, la escala prevista en el número 1.º anterior.
>
> Se modifica por el art. 63.2 de la Ley 31/2022, de 23 de diciembre. Ref. BOE-A-2022-22128
>
> Se modifica, con efectos desde 1 de enero de 2021, por el art. 59.2 de la Ley 11/2020, de 30 de diciembre. Ref. BOE-A-2020-17339
>
> Se modifica por el art. 1.51 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Se modifica, con efectos desde 1 de enero de 2010, por el art. 63.2 de la Ley 39/2010, de 22 de diciembre. Ref. BOE-A-2010-19703.
>
> Se modifica, con efectos desde el 1 de enero de 2010 por el art. 69.2 de la Ley 26/2009, de 23 de diciembre. Ref. BOE-A-2009-20765
>
> Redactado conforme a la corrección de errores pubicada en BOE núm. 96, de 21 de abril de 2010. Ref. BOE-A-2010-6285

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2023. 2 construct(s); 6 formula(s); 1 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-02`.

### 40. `ley-35-2006:da-56`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#da-12`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2023-01-01
- `required_text`:
  - "Gastos de difícil justificación en estimación directa simplificada durante el período impositivo 2023"
  - "durante el período impositivo 2023"
  - "del 7 por ciento"
- `notes` (verbatim): "LIRPF disposición adicional 56ª: eleva exclusivamente para el periodo impositivo 2023 al 7 por ciento el porcentaje de deducción para el conjunto de provisiones deducibles y gastos de difícil justificación de la estimación directa simplificada, manteniendo el límite anual de 2.000 EUR fijado por el art. 30 LIRPF/RIRPF."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Disposición adicional quincuagésima sexta. Gastos de difícil justificación en estimación directa simplificada durante el período impositivo 2023.
>
> 1. El porcentaje de deducción para el conjunto de las provisiones deducibles y los gastos de difícil justificación a que se refiere el artículo 30 del Reglamento del Impuesto sobre la Renta de las Personas Físicas será, durante el período impositivo 2023, del 7 por ciento.
>
> 2. El porcentaje establecido en el apartado 1 anterior podrá ser modificado reglamentariamente.
>
> Se añade por el art. 60.2 de la Ley 31/2022, de 23 de diciembre. Ref. BOE-A-2022-22128
>
> Redactado conforme a la corrección de errores publicada en BOE núm. 52, de 2 de marzo de 2023. Ref. BOE-A-2023-5478

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2023. 1 construct(s); 1 formula(s); 1 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-29`.

### 41. `real-decreto-ley-7-2024:art-11`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/real-decreto-ley-7-2024.html#a1-3`
- `document_id`: `BOE-A-2024-23422`; `effective_from`: 2024-11-13
- `required_text`:
  - "Artículo 11"
  - "rendimiento neto de módulos de 2024"
  - "pago fraccionado correspondiente al último trimestre de 2024"
- `notes` (verbatim): "Reduccion DANA 2024 para actividades economicas en estimacion objetiva en municipios afectados; fundamenta el APARTADO 1 del articulo, que opera sobre el rendimiento neto de modulos del IRPF. El apartado 2 del mismo articulo reduce la cuota devengada por operaciones corrientes del regimen simplificado del IVA y tiene su propia entrada, real-decreto-ley-7-2024:art-11.2. CAMBIO DE CORPUS. corpus_ref apuntaba a un extracto recortado a mano del articulo que perdia su ultima frase (la que declara que la reduccion se computa sobre la cuota ANUAL del regimen simplificado); apunta ahora al documento consolidado integro ya empaquetado, cuyo bloque a1-3 es el mismo articulo completo. Ninguna de las tres frases de required_text cambia de resultado: se verificaron contra el bloque nuevo antes del cambio. FECHA DE CONSOLIDACION. consolidated_as_of pasa de 2025-10-29 a 2026-08-13. El 2025-10-29 fechaba el extracto recortado que se retiro y no viajo con el cambio de puntero; las bytes que ahora se citan son las del documento consolidado empaquetado (sha256 13615f1354c9644aeccd62170c60a147e2b18a3d8211bea33c7d387bd63e6eb6), cotejadas contra el texto en vigor servido por boe.es el 2026-08-13. La entrada real-decreto-ley-7-2024:art-11.2 del catalogo del IVA cita esas mismas bytes: una sola fecha para unas mismas bytes. PROVENANCIA DE LA REVISION. El operador reviso esta entrada el 2026-05-05, pero reviso el extracto recortado y una nota de una linea; ni el puntero de evidencia actual ni esta prosa pasaron por sus manos. reviewed_by lo declara asi y queda pendiente de re-sello por operador."
- `reviewed_by` (verbatim): "agent-prepared-pending-operator"

#### Bundled corpus text

> Artículo 11. Reducción en 2024 del rendimiento neto calculado por el método de estimación objetiva en el Impuesto sobre la Renta de las Personas Físicas y de la cuota devengada por operaciones corrientes del régimen simplificado del Impuesto sobre el Valor Añadido.
>
> 1. Los contribuyentes del Impuesto sobre la Renta de las Personas Físicas que desarrollen actividades económicas en los términos municipales citados en el anexo del Real Decreto-ley 6/2024, de 5 de noviembre, por el que se adoptan medidas urgentes de respuesta ante los daños causados por la Depresión Aislada en Niveles Altos (DANA) en diferentes municipios entre el 28 de octubre y el 4 de noviembre de 2024, y determinen el rendimiento neto por el método de estimación objetiva, podrán reducir el rendimiento neto de módulos de 2024 correspondiente a tales actividades en un 25 por ciento.
>
> La reducción prevista en el párrafo anterior se aplicará sobre el rendimiento neto de módulos resultante después de aplicar la reducción prevista en el apartado 1 de la disposición adicional primera de la Orden HFP/1359/2023, de 19 de diciembre, por la que se desarrollan para el año 2024 el método de estimación objetiva del Impuesto sobre la Renta de las Personas Físicas y el régimen especial simplificado del Impuesto sobre el Valor Añadido.
>
> Para la determinación de la cuantía del pago fraccionado correspondiente al último trimestre de 2024, el rendimiento neto a efectos del pago fraccionado se reducirá en la parte proporcional del mismo que corresponda a las actividades económicas desarrolladas en los términos municipales afectados por la Depresión Aislada en Niveles Altos (DANA) a que se refiere el primer párrafo de este apartado.
>
> 2. Los sujetos pasivos del Impuesto sobre el Valor Añadido que desarrollen actividades empresariales o profesionales en los términos municipales citados en el anexo del Real Decreto-ley 6/2024, de 5 de noviembre, por el que se adoptan medidas urgentes de respuesta ante los daños causados por la Depresión Aislada en Niveles Altos (DANA) en diferentes municipios entre el 28 de octubre y el 4 de noviembre de 2024, y estén acogidos al régimen especial simplificado, podrán reducir en un 25 por ciento el importe de las cuotas devengadas por operaciones corrientes correspondiente a tales actividades en el año 2024.
>
> Esta reducción se tendrá en cuenta para el cálculo de la cuota anual del régimen especial simplificado correspondiente al año 2024.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2024. 1 construct(s); 1 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-13`.

Also cited by modelo(s): 131.
