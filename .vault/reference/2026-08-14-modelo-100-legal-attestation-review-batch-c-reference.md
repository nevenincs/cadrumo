---
tags:
  - '#reference'
  - '#modelo-100-legal-attestation-review-batch-c'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:4ccd37c5e082617ff92b6d6e9c517b4441f621d8b1bee1497c57cb2420893618'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-14-registry-campaign-sequencing-operator-attestation-ledger-audit]]"
  - "[[2026-08-14-legal-attestation-packet-methodology-audit]]"
---

# `modelo-100-legal-attestation-review-batch-c` reference: `Modelo 100 legal-reference attestation review packet, Batch C (concept-clustered remainder)`

This is **Batch C**, the last of three batches covering Modelo 100's 119
remaining legal references (74% of the entire remaining attestation burden
across the seven layout-capable modelos). Batch A (49 references,
self-flagged as agent-transcribed and awaiting re-stamp) and Batch B (41
references, each stating a rate, bracket, threshold or amount) were written
and accepted first. Batch C is the 29 references that are neither: no
self-verification claim, and no numeric content anywhere in the bundled
corpus text.

**With this batch, the Modelo 100 tranche is complete at 119 references
across three batches (49 + 41 + 29), and the operator attestation review
series stands at 144 references prepared across five modelos**: Modelo 390
(10, `2026-08-14-modelo-390-legal-attestation-review-reference`), Modelo
180/145/349 combined (15,
`2026-08-14-modelo-180-145-349-legal-attestation-review-reference`), and
Modelo 100 (119, this batch plus Batches A and B). That is the whole surface
prepared by this packet series so far; recorded here so it is visible from
the most recent document rather than requiring the operator to add it up
across five separate files.

**Batch B's own count moved a second time after it was first accepted, and
that correction bears directly on how this batch was built, so it is
restated here rather than assumed known.** A phrase-adjacency numeric scan
(a number immediately followed by "por ciento", "%", or "euros") missed four
references whose rate figures are laid out as bracket TABLES rather than in
a sentence carrying an adjacent unit word: `ley-35-2006:art-63` (the state
general IRPF scale itself), `art-66` (the state savings-income scale), and
`art-76` / `art-76-2015` (the autonomous-community savings-income scale).
Those four moved from this batch's original 33-reference candidate set into
Batch B before either batch was finalized, and Batch C's actual count is 29,
not 33. A dedicated table-shape detector (co-occurrence of a table-header
marker -- "Tipo aplicable", "Porcentaje", "Base liquidable", "tipo de
gravamen" -- with two or more bare decimal-comma numbers or a
euro-thousands-shaped figure) was run against every reference in this batch
before it was written, not only against the four that moved; none of the 29
below trip it. Two references most likely to be confused for a bracket table
by their own title -- `ley-35-2006:art-62` ("Cuota íntegra estatal") and
`art-74` ("Escala autonómica del Impuesto") -- were individually read in
full and confirmed to be genuine cross-reference articles rather than
numeric ones: `art-62` sums the results art-63 and art-66 already computed
without stating a figure of its own, and `art-74` establishes that EACH
autonomous community sets its own scale under Ley 22/2009 without the LIRPF
itself stating any bracket number for it. This is the same
cites-versus-states distinction drawn on the Modelo 390 and Modelo
180/145/349 packets (`rd-1624-1992:art-80`'s cross-reference to a different
article numbered 80): a reference that points at a number elsewhere is a
different review task from one that states a number itself, and conflating
them would send the operator hunting for figures that are not in the text.
Both corrections, and the general finding that a cheap numeric-detection
method fails in the direction that costs the operator the most, are recorded
in `legal-attestation-packet-methodology-audit`.

For each reference this packet places the registry's own claim next to the
actual bundled corpus text it points at, quoted verbatim, and lists what in
Modelo 100 depends on it. It does not state whether the claim and the source
agree -- that is the operator's act, and stating it here would turn the
operator's sign-off into a rubber stamp on agent work. The one exception is a
structural discrepancy: a broken `corpus_ref`, a `required_text` phrase absent
from the quoted text, or a citation that plainly names a different subject.
**Zero of the 119 Modelo 100 references across all three batches have
triggered that exception** -- forty-nine in Batch A, forty-one in Batch B,
twenty-nine here -- and the wider series, including the ten Modelo 390 and
fifteen Modelo 180/145/349 references, has found none either. Every
`corpus_ref` below resolves and every declared `required_text` phrase is
present in the quoted text, checked against the same production normaliser
(`cadrumo.core.normalise_corpus_text`) used throughout this series.

**Standing caveat on the `notes` and `reviewed_by` fields.** Every `notes`
and `reviewed_by` value quoted below is agent-authored registry content, not
operator-verified prose -- stated once here as a standing practice across
the whole series.

**Numeric grounding flag: does not apply to any of the 29 references below.**
None state a rate, amount or threshold, verified by the phrase-adjacency scan,
the full-text pattern scan, and the dedicated table-shape detector together
-- three independent signals, not one. This mirrors the Modelo 390 packet,
where the flag also applied to none of its ten references, but is reached
here by an explicitly stronger method after Batch B's own experience showed a
weaker one misses in the dangerous direction.

**Quotation discipline, carried forward unchanged.** Every substantive
paragraph of every bundled corpus text below is quoted in full. The only
material ever omitted is the trailing BOE amendment-history citation footer
("Se modifica...", "Se añade...", "Texto añadido..."), which is pure
metadata and never carries a `required_text` phrase.

This document is read-only working material. No `operator_reviewed` stamp was
applied or could be applied through any path available to this session, and
nothing under `modelos/100/**` was touched to produce it.

## Summary

Twenty-nine sections follow, grouped into seven concept clusters: datos
identificativos y familia, rendimientos del trabajo, rendimientos de capital
inmobiliario, mínimos y base imponible / liquidable, deducciones y
regímenes especiales, cálculo del impuesto y regularización, and a single
procedural entry (an annual form-approval orden citation carrying no rate or
amount). Each section carries the same four parts in the same order: the
registry's current entry, the bundled corpus text quoted verbatim, what in
Modelo 100 depends on it, and the entry's current review status.

## Datos identificativos y familia

### 1. `ley-35-2006:art-74`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a74`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2011-01-12
- `required_text`:
  - "Escala autonómica del Impuesto."
  - "base liquidable general que exceda del importe del mínimo personal y familiar"
  - "escala autonómica del Impuesto"
  - "aprobadas por la Comunidad Autónoma"
  - "tipo medio de gravamen general autonómico"
- `notes` (verbatim): "LIRPF art 74: current autonomic general-scale rule for the part of the base liquidable general exceeding the personal and family minimum adjusted under art 56.3. The article delegates the scale to the Comunidad Autonoma under Ley 22/2009 and defines the autonomic average general tax rate. Base legal para Modelo 100 casillas 0529 and 0531."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 74. Escala autonómica del Impuesto.
>
> 1. La parte de la base liquidable general que exceda del importe del mínimo personal y familiar que resulte de los incrementos o disminuciones a que se refiere el artículo 56.3 de esta Ley, será gravada de la siguiente forma:
>
> 1.º A la base liquidable general se le aplicarán los tipos de la escala autonómica del Impuesto que, conforme a lo previsto en la Ley 22/2009, por el que se regula el sistema de financiación de las Comunidades Autónomas de régimen común y Ciudades con Estatuto de Autonomía, hayan sido aprobadas por la Comunidad Autónoma.
>
> 2.º La cuantía resultante se minorará en el importe derivado de aplicar a la parte de la base liquidable general correspondiente al mínimo personal y familiar que resulte de los incrementos o disminuciones a que se refiere el artículo 56.3 de esta Ley, la escala prevista en el número 1.º anterior.
>
> 2. Se entenderá por tipo medio de gravamen general autonómico, el derivado de multiplicar por 100 el cociente resultante de dividir la cuota obtenida por la aplicación de lo previsto en el apartado anterior por la base liquidable general. El tipo medio de gravamen general autonómico se expresará con dos decimales.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 5 binding(s); 5 casilla(s); 8 construct(s); 36 formula(s); 90 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 714.

### 2. `ley-35-2006:art-82`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a82`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Tributación conjunta."
  - "modalidades de unidad familiar"
  - "cónyuges no separados legalmente"
  - "Los hijos menores"
  - "Nadie podrá formar parte de dos unidades familiares"
  - "31 de diciembre de cada año"
- `notes` (verbatim): "LIRPF art 82: defines the family-unit modalities that may file jointly: legally non-separated spouses with qualifying children, and single-parent units in legal separation or no-marriage cases. Grounds M100 joint-taxation eligibility, family-unit profile bindings, and wizard family-situation checks."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 82. Tributación conjunta.
>
> 1. Podrán tributar conjuntamente las personas que formen parte de alguna de las siguientes modalidades de unidad familiar:
>
> 1.ª La integrada por los cónyuges no separados legalmente y, si los hubiera:
>
> a) Los hijos menores, con excepción de los que, con el consentimiento de los padres, vivan independientes de éstos.
>
> b) Los hijos mayores de edad incapacitados judicialmente sujetos a patria potestad prorrogada o rehabilitada.
>
> 2.ª En los casos de separación legal, o cuando no existiera vínculo matrimonial, la formada por el padre o la madre y todos los hijos que convivan con uno u otro y que reúnan los requisitos a que se refiere la regla 1.ª de este artículo.
>
> 2. Nadie podrá formar parte de dos unidades familiares al mismo tiempo.
>
> 3. La determinación de los miembros de la unidad familiar se realizará atendiendo a la situación existente a 31 de diciembre de cada año.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 7 binding(s); 2 casilla(s); 10 construct(s); 14 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 3. `ley-35-2006:art-83`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a83`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Opción por la tributación conjunta."
  - "podrán optar, en cualquier período impositivo"
  - "no vinculará para períodos sucesivos"
  - "deberá abarcar a la totalidad de los miembros"
  - "Si uno de ellos presenta declaración individual"
- `notes` (verbatim): "LIRPF art 83: governs the option for joint taxation by people integrated in a family unit, including the whole-unit election requirement, non-binding nature for later periods, individual-return override, and post-deadline immutability."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 83. Opción por la tributación conjunta.
>
> 1. Las personas físicas integradas en una unidad familiar podrán optar, en cualquier período impositivo, por tributar conjuntamente en el Impuesto sobre la Renta de las Personas Físicas, con arreglo a las normas generales del impuesto y las disposiciones de este título, siempre que todos sus miembros sean contribuyentes por este impuesto.
>
> La opción por la tributación conjunta no vinculará para períodos sucesivos.
>
> 2. La opción por la tributación conjunta deberá abarcar a la totalidad de los miembros de la unidad familiar. Si uno de ellos presenta declaración individual, los restantes deberán utilizar el mismo régimen.
>
> La opción ejercitada para un período impositivo no podrá ser modificada con posterioridad respecto del mismo una vez finalizado el plazo reglamentario de declaración.
>
> En caso de falta de declaración, los contribuyentes tributarán individualmente, salvo que manifiesten expresamente su opción en el plazo de 10 días a partir del requerimiento de la Administración tributaria.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 1 binding(s); 2 casilla(s); 8 construct(s); 8 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

## Rendimientos del trabajo

### 4. `ley-35-2006:art-14.2.m`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a14`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2023-01-01
- `required_text`:
  - "rendimientos del trabajo en especie derivados de la entrega de acciones"
  - "artículo 42 de esta ley no estén exentos por superar la cuantía"
  - "plazo de diez años"
- `notes` (verbatim): "LIRPF art 14.2.m: imputacion temporal de rendimientos del trabajo en especie por entrega de acciones o participaciones de empresa emergente que cumplen art 42.3.f pero no estan exentos por superar la cuantia prevista. Se imputan al admitirse a negociacion, salir del patrimonio del contribuyente, o cumplirse el plazo de diez anos."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 14. Imputación temporal.
>
> 1. Regla general.
>
> Los ingresos y gastos que determinan la renta a incluir en la base del impuesto se imputarán al período impositivo que corresponda, de acuerdo con los siguientes criterios:
>
> a) Los rendimientos del trabajo y del capital se imputarán al período impositivo en que sean exigibles por su perceptor.
>
> b) Los rendimientos de actividades económicas se imputarán conforme a lo dispuesto en la normativa reguladora del Impuesto sobre Sociedades, sin perjuicio de las especialidades que reglamentariamente puedan establecerse.
>
> No obstante, las ayudas públicas para la primera instalación de jóvenes agricultores previstas en el Marco Nacional de Desarrollo Rural de España podrán imputarse por cuartas partes, en el período impositivo en el que se obtengan y en los tres siguientes.
>
> c) Las ganancias y pérdidas patrimoniales se imputarán al período impositivo en que tenga lugar la alteración patrimonial.
>
> 2. Reglas especiales.
>
> a) Cuando no se hubiera satisfecho la totalidad o parte de una renta, por encontrarse pendiente de resolución judicial la determinación del derecho a su percepción o su cuantía, los importes no satisfechos se imputarán al período impositivo en que aquélla adquiera firmeza.
>
> b) Cuando por circunstancias justificadas no imputables al contribuyente, los rendimientos derivados del trabajo se perciban en períodos impositivos distintos a aquéllos en que fueron exigibles, se imputarán a éstos, practicándose, en su caso, autoliquidación complementaria, sin sanción ni intereses de demora ni recargo alguno. Cuando concurran las circunstancias previstas en el párrafo a) anterior, los rendimientos se considerarán exigibles en el período impositivo en que la resolución judicial adquiera firmeza.
>
> La autoliquidación se presentará en el plazo que media entre la fecha en que se perciban y el final del inmediato siguiente plazo de declaraciones por el impuesto.
>
> c) Las ganancias patrimoniales derivadas de ayudas públicas se imputarán al período impositivo en que tenga lugar su cobro, sin perjuicio de las opciones previstas en las letras g), i), j) y l) de este apartado.
>
> d) En el caso de operaciones a plazos o con precio aplazado, el contribuyente podrá optar por imputar proporcionalmente las rentas obtenidas en tales operaciones, a medida que se hagan exigibles los cobros correspondientes. Se considerarán operaciones a plazos o con precio aplazado aquellas cuyo precio se perciba, total o parcialmente, mediante pagos sucesivos, siempre que el período transcurrido entre la entrega o la puesta a disposición y el vencimiento del último plazo sea superior al año.
>
> Cuando el pago de una operación a plazos o con precio aplazado se hubiese instrumentado, en todo o en parte, mediante la emisión de efectos cambiarios y éstos fuesen transmitidos en firme antes de su vencimiento, la renta se imputará al período impositivo de su transmisión.
>
> En ningún caso tendrán este tratamiento, para el transmitente, las operaciones derivadas de contratos de rentas vitalicias o temporales. Cuando se transmitan bienes y derechos a cambio de una renta vitalicia o temporal, la ganancia o pérdida patrimonial para el rentista se imputará al período impositivo en que se constituya la renta.
>
> e) Las diferencias positivas o negativas que se produzcan en las cuentas representativas de saldos en divisas o en moneda extranjera, como consecuencia de la modificación experimentada en sus cotizaciones, se imputarán en el momento del cobro o del pago respectivo.
>
> f) Las rentas estimadas a que se refiere el artículo 6.5 de esta Ley se imputarán al período impositivo en que se entiendan producidas.
>
> g) Las ayudas públicas percibidas como compensación por los defectos estructurales de construcción de la vivienda habitual y destinadas a su reparación podrán imputarse por cuartas partes, en el periodo impositivo en el que se obtengan y en los tres siguientes.
>
> h) Se imputará como rendimiento de capital mobiliario a que se refiere el artículo 25.3 de esta Ley, de cada período impositivo, la diferencia entre el valor liquidativo de los activos afectos a la póliza al final y al comienzo del período impositivo en aquellos contratos de seguros de vida en los que el tomador asuma el riesgo de la inversión. El importe imputado minorará el rendimiento derivado de la percepción de cantidades en estos contratos.
>
> No resultará de aplicación esta regla especial de imputación temporal en aquellos contratos en los que concurra alguna de las siguientes circunstancias:
>
> A) No se otorgue al tomador la facultad de modificar las inversiones afectas a la póliza.
>
> B) Las provisiones matemáticas se encuentren invertidas en:
>
> a) Acciones o participaciones de instituciones de inversión colectiva, predeterminadas en los contratos, siempre que se trate de instituciones de inversión colectiva adaptadas a la Ley 35/2003, de 4 de noviembre, de instituciones de inversión colectiva, o amparadas por la Directiva 2009/65/CEE del Parlamento Europeo y del Consejo, de 13 de julio de 2009.
>
> b) Conjuntos de activos reflejados de forma separada en el balance de la entidad aseguradora, siempre que se cumplan los siguientes requisitos:
>
> La determinación de los activos integrantes de cada uno de los distintos conjuntos de activos separados deberá corresponder, en todo momento, a la entidad aseguradora quien, a estos efectos, gozará de plena libertad para elegir los activos con sujeción, únicamente, a criterios generales predeterminados relativos al perfil de riesgo del conjunto de activos o a otras circunstancias objetivas.
>
> La inversión de las provisiones de cada conjunto de activos deberá efectuarse en activos que cumplan las normas establecidas en el artículo 89 del Real Decreto 1060/2015, de 20 de noviembre, de ordenación, supervisión y solvencia de las entidades aseguradoras y reaseguradoras. En ningún caso podrá tratarse de bienes inmuebles o derechos reales inmobiliarios.
>
> No obstante, se entenderá que cumplen tales requisitos aquellos conjuntos de activos que traten de desarrollar una política de inversión caracterizada por reproducir un determinado índice bursátil o de renta fija representativo de algunos de los mercados secundarios oficiales de valores de la Unión Europea.
>
> El tomador únicamente tendrá la facultad de elegir, entre los distintos conjuntos separados de activos, en cuáles debe invertir la entidad aseguradora la provisión matemática del seguro, pero en ningún caso podrá intervenir en la determinación de los activos concretos en los que, dentro de cada conjunto separado, se invierten tales provisiones.
>
> En estos contratos, el tomador o el asegurado podrán elegir, de acuerdo con las especificaciones de la póliza, entre las distintas instituciones de inversión colectiva o conjuntos separados de activos, expresamente designados en los contratos, sin que puedan producirse especificaciones singulares para cada tomador o asegurado.
>
> Las condiciones a que se refiere esta letra h) deberán cumplirse durante toda la vigencia del contrato.
>
> i) Las ayudas incluidas en el ámbito de los planes estatales para el acceso por primera vez a la vivienda en propiedad, percibidas por los contribuyentes mediante pago único en concepto de Ayuda Estatal Directa a la Entrada (AEDE), podrán imputarse por cuartas partes en el período impositivo en el que se obtengan y en los tres siguientes.
>
> j) Las ayudas públicas otorgadas por las Administraciones competentes a los titulares de bienes integrantes del Patrimonio Histórico Español inscritos en el Registro general de bienes de interés cultural a que se refiere la Ley 16/1985, de 25 de junio, del Patrimonio Histórico Español, y destinadas exclusivamente a su conservación o rehabilitación, podrán imputarse por cuartas partes en el período impositivo en que se obtengan y en los tres siguientes, siempre que se cumplan las exigencias establecidas en dicha ley, en particular respecto de los deberes de visita y exposición pública de dichos bienes.
>
> k) Las pérdidas patrimoniales derivadas de créditos vencidos y no cobrados podrán imputarse al período impositivo en que concurra alguna de las siguientes circunstancias:
>
> 1.º Que adquiera eficacia una quita establecida en un acuerdo de refinanciación judicialmente homologable a los que se refiere el artículo 71 bis y la disposición adicional cuarta de la Ley 22/2003, de 9 de julio, Concursal, o en un acuerdo extrajudicial de pagos a los cuales se refiere el Título X de la misma Ley.
>
> 2.º Que, encontrándose el deudor en situación de concurso, adquiera eficacia el convenio en el que se acuerde una quita en el importe del crédito conforme a lo dispuesto en el artículo 133 de la Ley 22/2003, de 9 de julio, Concursal, en cuyo caso la pérdida se computará por la cuantía de la quita.
>
> En otro caso, que concluya el procedimiento concursal sin que se hubiera satisfecho el crédito salvo cuando se acuerde la conclusión del concurso por las causas a las que se refieren los apartados 1.º, 4.º y 5.º del artículo 176 de la Ley 22/2003, de 9 de julio, Concursal.
>
> 3.º Que se cumpla el plazo de un año desde el inicio del procedimiento judicial distinto de los de concurso que tenga por objeto la ejecución del crédito sin que este haya sido satisfecho.
>
> Cuando el crédito fuera cobrado con posterioridad al cómputo de la pérdida patrimonial a que se refiere esta letra k), se imputará una ganancia patrimonial por el importe cobrado en el período impositivo en que se produzca dicho cobro.
>
> l) Las ayudas públicas para la primera instalación de jóvenes agricultores previstas en el Marco Nacional de Desarrollo Rural de España que se destinen a la adquisición de una participación en el capital de empresas agrícolas societarias podrán imputarse por cuartas partes, en el período impositivo en el que se obtengan y en los tres siguientes.
>
> m) Los rendimientos del trabajo en especie derivados de la entrega de acciones o participaciones de una empresa emergente a las que se refiere la Ley 28/2022, de 21 de diciembre, de fomento del ecosistema de las empresas emergentes, que, cumpliendo los requisitos establecidos en la letra f) del apartado 3 del artículo 42 de esta ley no estén exentos por superar la cuantía prevista en dicho artículo, se imputarán en el período impositivo en el que concurra alguna de las siguientes circunstancias:
>
> – Que el capital de la sociedad sea objeto de admisión a negociación en bolsa de valores o en cualquier sistema multilateral de negociación, español o extranjero.
>
> – Que se produzca la salida del patrimonio del contribuyente de la acción o participación correspondiente.
>
> No obstante, transcurrido el plazo de diez años a contar desde la entrega de las acciones o participaciones sin que se haya producido alguna de las circunstancias señaladas anteriormente, el contribuyente deberá imputar los rendimientos del trabajo a que se refiere esta letra correspondientes a tales acciones o participaciones, en el período impositivo en el que se haya cumplido el referido plazo de diez años.
>
> 3. En el supuesto de que el contribuyente pierda su condición por cambio de residencia, todas las rentas pendientes de imputación deberán integrarse en la base imponible correspondiente al último período impositivo que deba declararse por este impuesto, en las condiciones que se fijen reglamentariamente, practicándose, en su caso, autoliquidación complementaria, sin sanción ni intereses de demora ni recargo alguno.
>
> Cuando el traslado de residencia se produzca a otro Estado miembro de la Unión Europea, el contribuyente podrá optar por imputar las rentas pendientes conforme a lo dispuesto en el párrafo anterior, o por presentar a medida en que se vayan obteniendo cada una de las rentas pendientes de imputación, una autoliquidación complementaria sin sanción, ni intereses de demora ni recargo alguno, correspondiente al último período que deba declararse por este Impuesto. La autoliquidación se presentará en el plazo de declaración del período impositivo en el que hubiera correspondido imputar dichas rentas en caso de no haberse producido la pérdida de la condición de contribuyente.
>
> 4. En el caso de fallecimiento del contribuyente todas las rentas pendientes de imputación deberán integrarse en la base imponible del último período impositivo que deba declararse.
>
> Se añade la letra m) al apartado 2, con efectos de 1 de enero de 2023, por la disposición final 3.1 de la Ley 28/2022, de 21 de diciembre. Ref. BOE-A-2022-21739
>
> Se modifica la letra h) del apartado 2 por el art. 3.1 de la Ley 11/2021, de 9 de julio. Ref. BOE-A-2021-11473
>
> Se modifican los apartados 1 y 2, con efectos desde el 1 de enero de 2020, por el art. 2 de la Ley 8/2020, de 16 de diciembre. Ref. BOE-A-2020-16346
>
> Se modifican los apartados 1 y 2 por el art. 2 del Real Decreto-ley 5/2020, de 25 de febrero. Ref. BOE-A-2020-2669
>
> Esta modificación surtirá efectos desde el 1 de enero de 2020, según establece la disposición final 2 del citado Real Decreto-ley.
>
> Se modifica la letra c) y se añade la k) al apartado 2 por el art. 1.8 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Se suprime la letra c) del apartado 2, con efectos desde 1 de enero de 2013, por el art. 8.2 de la Ley 11/2013, de 26 de julio. Ref. BOE-A-2013-8187.
>
> Téngase en cuenta que la letra c) del apartado 2 ya fue suprimida por el Real Decreto-ley 4/2013, de 22 de febrero.
>
> Se suprime la letra c) del apartado 2, con efectos desde 1 de enero de 2013, por el art. 8.2 del Real Decreto-ley 4/2013, de 22 de febrero. Ref. BOE-A-2013-2030.
>
> Se modifica el apartado 3, con efectos desde el 1 de enero de 2013, por la disposición final 10.1 de la Ley 16/2012, de 27 de diciembre. Ref. BOE-A-2012-15650.
>
> TÍTULO II
>
> Determinación de la renta sometida a gravamen

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2023, 2024, 2025. 1 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-30`.

## Rendimientos de capital inmobiliario

### 5. `ley-35-2006:art-22`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a22`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Rendimientos íntegros del capital inmobiliario."
  - "bienes inmuebles rústicos y urbanos"
  - "se deriven del arrendamiento"
  - "importe que por todos los conceptos deba satisfacer"
- `notes` (verbatim): "LIRPF art 22: defines gross real-estate capital income from ownership of rural or urban immovable property or real rights over it, including lease income and consideration for use or enjoyment rights."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 22. Rendimientos íntegros del capital inmobiliario.
>
> 1. Tendrán la consideración de rendimientos íntegros procedentes de la titularidad de bienes inmuebles rústicos y urbanos o de derechos reales que recaigan sobre ellos, todos los que se deriven del arrendamiento o de la constitución o cesión de derechos o facultades de uso o disfrute sobre aquéllos, cualquiera que sea su denominación o naturaleza.
>
> 2. Se computará como rendimiento íntegro el importe que por todos los conceptos deba satisfacer el adquirente, cesionario, arrendatario o subarrendatario, incluido, en su caso, el correspondiente a todos aquellos bienes cedidos con el inmueble y excluido el Impuesto sobre el Valor Añadido o, en su caso, el Impuesto General Indirecto Canario.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 56 casilla(s); 18 construct(s); 52 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 6. `ley-35-2006:art-24`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a24`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Rendimiento en caso de parentesco."
  - "sea el cónyuge o un pariente"
  - "hasta el tercer grado inclusive"
  - "no podrá ser inferior al que resulte de las reglas del artículo 85"
- `notes` (verbatim): "LIRPF art 24: sets the minimum computable real-estate capital income when the tenant, assignee, lessee or sublessee is the taxpayer's spouse or a relative up to the third degree, tying the minimum to the art 85 imputed-rent rules."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 24. Rendimiento en caso de parentesco.
>
> Cuando el adquirente, cesionario, arrendatario o subarrendatario del bien inmueble o del derecho real que recaiga sobre el mismo sea el cónyuge o un pariente, incluidos los afines, hasta el tercer grado inclusive, del contribuyente, el rendimiento neto total no podrá ser inferior al que resulte de las reglas del artículo 85 de esta ley.
>
> Subsección 2.ª Rendimientos del capital mobiliario

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 21 casilla(s); 11 construct(s); 14 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 7. `ley-35-2006:art-27`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a27`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Rendimientos íntegros de actividades económicas"
  - "ordenación por cuenta propia de medios de producción"
  - "arrendamiento de inmuebles se realiza como actividad económica"
- `notes` (verbatim): "LIRPF art 27: define los rendimientos integros de actividades economicas por la ordenacion por cuenta propia de medios de produccion o recursos humanos y concreta el arrendamiento de inmuebles como actividad economica cuando existe al menos una persona empleada a jornada completa."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 27. Rendimientos íntegros de actividades económicas.
>
> 1. Se considerarán rendimientos íntegros de actividades económicas aquellos que, procediendo del trabajo personal y del capital conjuntamente, o de uno solo de estos factores, supongan por parte del contribuyente la ordenación por cuenta propia de medios de producción y de recursos humanos o de uno de ambos, con la finalidad de intervenir en la producción o distribución de bienes o servicios.
>
> En particular, tienen esta consideración los rendimientos de las actividades extractivas, de fabricación, comercio o prestación de servicios, incluidas las de artesanía, agrícolas, forestales, ganaderas, pesqueras, de construcción, mineras, y el ejercicio de profesiones liberales, artísticas y deportivas.
>
> No obstante, tratándose de rendimientos obtenidos por el contribuyente procedentes de una entidad en cuyo capital participe derivados de la realización de actividades incluidas en la Sección Segunda de las Tarifas del Impuesto sobre Actividades Económicas, aprobadas por el Real Decreto Legislativo 1175/1990, de 28 de septiembre, tendrán esta consideración cuando el contribuyente esté incluido, a tal efecto, en el régimen especial de la Seguridad Social de los trabajadores por cuenta propia o autónomos, o en una mutualidad de previsión social que actúe como alternativa al citado régimen especial conforme a lo previsto en la disposición adicional decimoquinta de la Ley 30/1995, de 8 de noviembre, de ordenación y supervisión de los seguros privados.
>
> 2. A efectos de lo dispuesto en el apartado anterior, se entenderá que el arrendamiento de inmuebles se realiza como actividad económica, únicamente cuando para la ordenación de esta se utilice, al menos, una persona empleada con contrato laboral y a jornada completa.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 7 application_link(s); 4 binding(s); 188 casilla(s); 16 construct(s); 31 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 130.

### 8. `ley-35-2006:art-28`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a28`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Reglas generales de cálculo del rendimiento neto"
  - "rendimiento neto de las actividades económicas"
  - "según las normas del Impuesto sobre Sociedades"
  - "ganancias o pérdidas patrimoniales derivadas de los elementos patrimoniales afectos"
- `notes` (verbatim): "LIRPF art 28: fija las reglas generales de calculo del rendimiento neto de actividades economicas, remitiendo a las normas del Impuesto sobre Sociedades y separando las ganancias o perdidas de elementos patrimoniales afectos."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 28. Reglas generales de cálculo del rendimiento neto.
>
> 1. El rendimiento neto de las actividades económicas se determinará según las normas del Impuesto sobre Sociedades, sin perjuicio de las reglas especiales contenidas en este artículo, en el artículo 30 de esta Ley para la estimación directa, y en el artículo 31 de esta Ley para la estimación objetiva.
>
> A efectos de lo dispuesto en el artículo 108 del texto refundido de la Ley del Impuesto sobre Sociedades, para determinar el importe neto de la cifra de negocios se tendrá en cuenta el conjunto de actividades económicas ejercidas por el contribuyente.
>
> 2. Para la determinación del rendimiento neto de las actividades económicas no se incluirán las ganancias o pérdidas patrimoniales derivadas de los elementos patrimoniales afectos a las mismas, que se cuantificarán conforme a lo previsto en la sección 4.ª de este capítulo.
>
> 3. La afectación de elementos patrimoniales o la desafectación de activos fijos por el contribuyente no constituirá alteración patrimonial, siempre que los bienes o derechos continúen formando parte de su patrimonio.
>
> Se entenderá que no ha existido afectación si se llevase a cabo la enajenación de los bienes o derechos antes de transcurridos tres años desde ésta.
>
> 4. Se atenderá al valor normal en el mercado de los bienes o servicios objeto de la actividad, que el contribuyente ceda o preste a terceros de forma gratuita o destine al uso o consumo propio.
>
> Asimismo, cuando medie contraprestación y ésta sea notoriamente inferior al valor normal en el mercado de los bienes y servicios, se atenderá a este último.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 7 application_link(s); 30 binding(s); 190 casilla(s); 16 construct(s); 66 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 130.

### 9. `ley-35-2006:art-33`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a33`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Concepto."
  - "Son ganancias y pérdidas patrimoniales"
  - "variaciones en el valor del patrimonio"
  - "alteración en la composición"
  - "hubiera adquirido valores homogéneos dentro de los dos meses anteriores o posteriores"
- `notes` (verbatim): "LIRPF art 33: define el concepto de ganancias y perdidas patrimoniales, identifica supuestos sin alteracion patrimonial, exenciones y perdidas no computables. Base legal de la fundacion de ganancias y perdidas patrimoniales en Modelo 100."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 33. Concepto.
>
> 1. Son ganancias y pérdidas patrimoniales las variaciones en el valor del patrimonio del contribuyente que se pongan de manifiesto con ocasión de cualquier alteración en la composición de aquél, salvo que por esta Ley se califiquen como rendimientos.
>
> 2. Se estimará que no existe alteración en la composición del patrimonio:
>
> a) En los supuestos de división de la cosa común.
>
> b) En la disolución de la sociedad de gananciales o en la extinción del régimen económico matrimonial de participación.
>
> c) En la disolución de comunidades de bienes o en los casos de separación de comuneros.
>
> Los supuestos a que se refiere este apartado no podrán dar lugar, en ningún caso, a la actualización de los valores de los bienes o derechos recibidos.
>
> 3. Se estimará que no existe ganancia o pérdida patrimonial en los siguientes supuestos:
>
> a) En reducciones del capital. Cuando la reducción de capital, cualquiera que sea su finalidad, dé lugar a la amortización de valores o participaciones, se considerarán amortizadas las adquiridas en primer lugar, y su valor de adquisición se distribuirá proporcionalmente entre los restantes valores homogéneos que permanezcan en el patrimonio del contribuyente.
>
> Cuando la reducción de capital no afecte por igual a todos los valores o participaciones propiedad del contribuyente, se entenderá referida a las adquiridas en primer lugar. Cuando la reducción de capital tenga por finalidad la devolución de aportaciones, el importe de ésta o el valor normal de mercado de los bienes o derechos percibidos minorará el valor de adquisición de los valores o participaciones afectadas, de acuerdo con las reglas del párrafo anterior, hasta su anulación. El exceso que pudiera resultar se integrará como rendimiento del capital mobiliario procedente de la participación en los fondos propios de cualquier tipo de entidad, en la forma prevista para la distribución de la prima de emisión, salvo que dicha reducción de capital proceda de beneficios no distribuidos, en cuyo caso la totalidad de las cantidades percibidas por este concepto tributará de acuerdo con lo previsto en la letra a) del artículo 25.1 de esta Ley. A estos efectos, se considerará que las reducciones de capital, cualquiera que sea su finalidad, afectan en primer lugar a la parte del capital social que no provenga de beneficios no distribuidos, hasta su anulación.
>
> No obstante lo dispuesto en el párrafo anterior, en el caso de reducción de capital que tenga por finalidad la devolución de aportaciones y no proceda de beneficios no distribuidos, correspondiente a valores no admitidos a negociación en alguno de los mercados regulados de valores definidos en la Directiva 2004/39/CE del Parlamento Europeo y del Consejo, de 21 de abril de 2004, relativa a los mercados de instrumentos financieros, y representativos de la participación en fondos propios de sociedades o entidades, cuando la diferencia entre el valor de los fondos propios de las acciones o participaciones correspondiente al último ejercicio cerrado con anterioridad a la fecha de la reducción de capital y su valor de adquisición sea positiva, el importe obtenido o el valor normal de mercado de los bienes o derechos recibidos se considerará rendimiento del capital mobiliario con el límite de la citada diferencia positiva.
>
> A estos efectos, el valor de los fondos propios a que se refiere el párrafo anterior se minorará en el importe de los beneficios repartidos con anterioridad a la fecha de la reducción de capital, procedentes de reservas incluidas en los citados fondos propios, así como en el importe de las reservas legalmente indisponibles incluidas en dichos fondos propios que se hubieran generado con posterioridad a la adquisición de las acciones o participaciones.
>
> El exceso sobre el citado límite minorará el valor de adquisición de las acciones o participaciones conforme a lo dispuesto en el segundo párrafo de esta letra a).
>
> Cuando por aplicación de lo dispuesto en el párrafo tercero de esta letra a) la reducción de capital hubiera determinado el cómputo como rendimiento del capital mobiliario de la totalidad o parte del importe obtenido o del valor normal de mercado de los bienes o derechos recibidos, y con posterioridad el contribuyente obtuviera dividendos o participaciones en beneficios conforme al artículo 25.1 a) de esta Ley procedentes de la misma entidad en relación con acciones o participaciones que hubieran permanecido en su patrimonio desde la reducción de capital, el importe obtenido de los dividendos o participaciones en beneficios minorará, con el límite de los rendimientos del capital mobiliario previamente computados que correspondan a las citadas acciones o participaciones, el valor de adquisición de las mismas conforme a lo dispuesto en el segundo párrafo de esta letra a).
>
> b) Con ocasión de transmisiones lucrativas por causa de muerte del contribuyente.
>
> c) Con ocasión de las transmisiones lucrativas de empresas o participaciones a las que se refiere el apartado 6 del artículo 20 de la Ley 29/1987, de 18 de diciembre, del Impuesto sobre Sucesiones y Donaciones.
>
> Los elementos patrimoniales que se afecten por el contribuyente a la actividad económica con posterioridad a su adquisición deberán haber estado afectos ininterrumpidamente durante, al menos, los cinco años anteriores a la fecha de la transmisión.
>
> d) En la extinción del régimen económico matrimonial de separación de bienes, cuando por imposición legal o resolución judicial se produzcan compensaciones, dinerarias o mediante la adjudicación de bienes, por causa distinta de la pensión compensatoria entre cónyuges.
>
> Las compensaciones a que se refiere esta letra d) no darán derecho a reducir la base imponible del pagador ni constituirá renta para el perceptor.
>
> El supuesto al que se refiere esta letra d) no podrá dar lugar, en ningún caso, a las actualizaciones de los valores de los bienes o derechos adjudicados.
>
> e) Con ocasión de las aportaciones a los patrimonios protegidos constituidos a favor de personas con discapacidad.
>
> 4. Estarán exentas del Impuesto las ganancias patrimoniales que se pongan de manifiesto:
>
> a) Con ocasión de las donaciones que se efectúen a las entidades citadas en el artículo 68.3 de esta Ley.
>
> b) Con ocasión de la transmisión de su vivienda habitual por mayores de 65 años o por personas en situación de dependencia severa o de gran dependencia de conformidad con la Ley de promoción de la autonomía personal y atención a las personas en situación de dependencia.
>
> c) Con ocasión del pago previsto en el artículo 97.3 de esta Ley y de las deudas tributarias a que se refiere el artículo 73 de la Ley 16/1985, de 25 de junio, del Patrimonio Histórico Español.
>
> d) Con ocasión de la dación en pago de la vivienda habitual del deudor o garante del deudor, para la cancelación de deudas garantizadas con hipoteca que recaiga sobre la misma, contraídas con entidades de crédito o de cualquier otra entidad que, de manera profesional, realice la actividad de concesión de préstamos o créditos hipotecarios.
>
> Asimismo estarán exentas las ganancias patrimoniales que se pongan de manifiesto con ocasión de la transmisión de la vivienda en que concurran los requisitos anteriores, realizada en ejecuciones hipotecarias judiciales o notariales.
>
> En todo caso será necesario que el propietario de la vivienda habitual no disponga de otros bienes o derechos en cuantía suficiente para satisfacer la totalidad de la deuda y evitar la enajenación de la vivienda.
>
> 5. No se computarán como pérdidas patrimoniales las siguientes:
>
> a) Las no justificadas.
>
> b) Las debidas al consumo.
>
> c) Las debidas a transmisiones lucrativas por actos ínter vivos o a liberalidades.
>
> d) Las debidas a pérdidas en el juego obtenidas en el período impositivo que excedan de las ganancias obtenidas en el juego en el mismo período.
>
> En ningún caso se computarán las pérdidas derivadas de la participación en los juegos a los que se refiere la disposición adicional trigésima tercera de esta Ley.
>
> e) Las derivadas de las transmisiones de elementos patrimoniales, cuando el transmitente vuelva a adquirirlos dentro del año siguiente a la fecha de dicha transmisión.
>
> Esta pérdida patrimonial se integrará cuando se produzca la posterior transmisión del elemento patrimonial.
>
> f) Las derivadas de las transmisiones de valores o participaciones admitidos a negociación en alguno de los mercados secundarios oficiales de valores definidos en la Directiva 2004/39/CE del Parlamento Europeo y del Consejo de 21 de abril de 2004 relativa a los mercados de instrumentos financieros, cuando el contribuyente hubiera adquirido valores homogéneos dentro de los dos meses anteriores o posteriores a dichas transmisiones.
>
> g) Las derivadas de las transmisiones de valores o participaciones no admitidos a negociación en alguno de los mercados secundarios oficiales de valores definidos en la Directiva 2004/39/CE del Parlamento Europeo y del Consejo de 21 de abril de 2004 relativa a los mercados de instrumentos financieros, cuando el contribuyente hubiera adquirido valores homogéneos en el año anterior o posterior a dichas transmisiones.
>
> En los casos previstos en los párrafos f) y g) anteriores, las pérdidas patrimoniales se integrarán a medida que se transmitan los valores o participaciones que permanezcan en el patrimonio del contribuyente.
>
> Se modifican las letras a) y d) del apartados 3 por el art. 1.20 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 315 casilla(s); 23 construct(s); 305 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 10. `ley-35-2006:art-34`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a34`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Importe de las ganancias o pérdidas patrimoniales. Norma general"
  - "diferencia entre los valores de adquisición y transmisión"
  - "valor de mercado de los elementos patrimoniales"
  - "mejoras en los elementos patrimoniales transmitidos"
- `notes` (verbatim): "LIRPF art 34: fija la norma general para calcular el importe de ganancias o perdidas patrimoniales por diferencia entre valores de adquisicion y transmision, o por valor de mercado en otros supuestos."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 34. Importe de las ganancias o pérdidas patrimoniales. Norma general.
>
> 1. El importe de las ganancias o pérdidas patrimoniales será:
>
> a) En el supuesto de transmisión onerosa o lucrativa, la diferencia entre los valores de adquisición y transmisión de los elementos patrimoniales.
>
> b) En los demás supuestos, el valor de mercado de los elementos patrimoniales o partes proporcionales, en su caso.
>
> 2. Si se hubiesen efectuado mejoras en los elementos patrimoniales transmitidos, se distinguirá la parte del valor de enajenación que corresponda a cada componente del mismo.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 313 casilla(s); 23 construct(s); 301 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 11. `ley-35-2006:art-99`

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
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 99. Obligación de practicar pagos a cuenta.
>
> 1. En el Impuesto sobre la Renta de las Personas Físicas, los pagos a cuenta que, en todo caso, tendrán la consideración de deuda tributaria, podrán consistir en:
>
> a) Retenciones.
>
> b) Ingresos a cuenta.
>
> c) Pagos fraccionados.
>
> 2. Las entidades y las personas jurídicas, incluidas las entidades en atribución de rentas, que satisfagan o abonen rentas sujetas a este impuesto, estarán obligadas a practicar retención e ingreso a cuenta, en concepto de pago a cuenta del Impuesto sobre la Renta de las Personas Físicas correspondiente al perceptor, en la cantidad que se determine reglamentariamente y a ingresar su importe en el Tesoro en los casos y en la forma que se establezcan. Estarán sujetos a las mismas obligaciones los contribuyentes por este impuesto que ejerzan actividades económicas respecto a las rentas que satisfagan o abonen en el ejercicio de dichas actividades, así como las personas físicas, jurídicas y demás entidades no residentes en territorio español, que operen en él mediante establecimiento permanente, o sin establecimiento permanente respecto a los rendimientos del trabajo que satisfagan, así como respecto de otros rendimientos sometidos a retención o ingreso a cuenta que constituyan gasto deducible para la obtención de las rentas a que se refiere el apartado 2 del artículo 24 del texto refundido de la Ley del Impuesto sobre la Renta de no Residentes.
>
> Cuando una entidad, residente o no residente, satisfaga o abone rendimientos del trabajo a contribuyentes que presten sus servicios a una entidad residente vinculada con aquélla en los términos previstos en el artículo 16 del texto refundido de la Ley del Impuesto sobre Sociedades o a un establecimiento permanente radicado en territorio español, la entidad o el establecimiento permanente en el que preste sus servicios el contribuyente, deberá efectuar la retención o el ingreso a cuenta.
>
> Las entidades aseguradoras domiciliadas en otro Estado miembro del Espacio Económico Europeo que operen en España en régimen de libre prestación de servicios deberán practicar retención e ingreso a cuenta en relación con las operaciones que se realicen en España.
>
> Los fondos de pensiones domiciliados en otro Estado miembro de la Unión Europea que desarrollen en España planes de pensiones de empleo sujetos a la legislación española, conforme a lo previsto en la Directiva 2003/41/CE del Parlamento Europeo y del Consejo, de 3 de junio de 2003, relativa a las actividades y la supervisión de fondos de pensiones de empleo o, en su caso, sus entidades gestoras, deberán practicar retención e ingreso a cuenta en relación con las operaciones que se realicen en España.
>
> En ningún caso estarán obligadas a practicar retención o ingreso a cuenta las misiones diplomáticas u oficinas consulares en España de Estados extranjeros.
>
> 3. No se someterán a retención los rendimientos derivados de las letras del Tesoro y de la transmisión, canje o amortización de los valores de deuda pública que con anterioridad al 1 de enero de 1999 no estuvieran sujetas a retención. Reglamentariamente podrán excepcionarse de la retención o del ingreso a cuenta determinadas rentas.
>
> Tampoco estará sujeto a retención o ingreso a cuenta el rendimiento derivado de la distribución de la prima de emisión de acciones o participaciones, o de la reducción de capital. Reglamentariamente podrá establecerse la obligación de practicar retención o ingreso a cuenta en estos supuestos.
>
> 4. En todo caso, los sujetos obligados a retener o a ingresar a cuenta asumirán la obligación de efectuar el ingreso en el Tesoro, sin que el incumplimiento de aquella obligación pueda excusarles de ésta.
>
> 5. El perceptor de rentas sobre las que deba retenerse a cuenta de este impuesto computará aquéllas por la contraprestación íntegra devengada.
>
> Cuando la retención no se hubiera practicado o lo hubiera sido por un importe inferior al debido, por causa imputable exclusivamente al retenedor u obligado a ingresar a cuenta, el perceptor deducirá de la cuota la cantidad que debió ser retenida.
>
> En el caso de retribuciones legalmente establecidas que hubieran sido satisfechas por el sector público, el perceptor sólo podrá deducir las cantidades efectivamente retenidas.
>
> Cuando no pudiera probarse la contraprestación íntegra devengada, la Administración tributaria podrá computar como importe íntegro una cantidad que, una vez restada de ella la retención procedente, arroje la efectivamente percibida. En este caso se deducirá de la cuota como retención a cuenta la diferencia entre lo realmente percibido y el importe íntegro.
>
> 6. Cuando exista obligación de ingresar a cuenta, se presumirá que dicho ingreso ha sido efectuado. El contribuyente incluirá en la base imponible la valoración de la retribución en especie, conforme a las normas previstas en esta ley, y el ingreso a cuenta, salvo que le hubiera sido repercutido.
>
> 7. Los contribuyentes que ejerzan actividades económicas estarán obligados a efectuar pagos fraccionados a cuenta del Impuesto sobre la Renta de las Personas Físicas, autoliquidando e ingresando su importe en las condiciones que reglamentariamente se determinen.
>
> Reglamentariamente se podrá exceptuar de esta obligación a aquellos contribuyentes cuyos ingresos hayan estado sujetos a retención o ingreso a cuenta en el porcentaje que se fije al efecto.
>
> El pago fraccionado correspondiente a las entidades en régimen de atribución de rentas, que ejerzan actividades económicas, se efectuará por cada uno de los socios, herederos, comuneros o partícipes, a los que proceda atribuir rentas de esta naturaleza, en proporción a su participación en el beneficio de la entidad.
>
> 8. 1.º Cuando el contribuyente adquiera su condición por cambio de residencia, tendrán la consideración de pagos a cuenta de este Impuesto las retenciones e ingresos a cuenta del Impuesto sobre la Renta de no Residentes, practicadas durante el período impositivo en que se produzca el cambio de residencia.
>
> 2.º Los trabajadores por cuenta ajena que no sean contribuyentes por este Impuesto, pero que vayan a adquirir dicha condición como consecuencia de su desplazamiento a territorio español, podrán comunicar a la Administración tributaria dicha circunstancia, dejando constancia de la fecha de entrada en dicho territorio, a los exclusivos efectos de que el pagador de los rendimientos del trabajo les considere como contribuyentes por este Impuesto.
>
> De acuerdo con el procedimiento que reglamentariamente se establezca, la Administración tributaria expedirá un documento acreditativo a los trabajadores por cuenta ajena que lo soliciten, que comunicarán al pagador de sus rendimientos del trabajo, residentes o con establecimiento permanente en España, y en el que conste la fecha a partir de la cual las retenciones e ingresos a cuenta se practicarán por este Impuesto, teniendo en cuenta para el cálculo del tipo de retención lo señalado en el apartado 1.º anterior.
>
> 9. Cuando en virtud de resolución judicial o administrativa se deba satisfacer una renta sujeta a retención o ingreso a cuenta de este impuesto, el pagador deberá practicar la misma sobre la cantidad íntegra que venga obligado a satisfacer y deberá ingresar su importe en el Tesoro, de acuerdo con lo previsto en este artículo.
>
> 10. Los contribuyentes deberán comunicar, al pagador de rendimientos sometidos a retención o ingreso a cuenta de los que sean perceptores, las circunstancias determinantes para el cálculo de la retención o ingreso a cuenta procedente, en los términos que se establezcan reglamentariamente.
>
> 11. Tendrán la consideración de pagos a cuenta de este Impuesto las retenciones a cuenta efectivamente practicadas en virtud de lo dispuesto en el artículo 11 de la Directiva 2003/48/CE del Consejo, de 3 de junio de 2003, en materia de fiscalidad de los rendimientos del ahorro en forma de pago de intereses.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 31 application_link(s); 27 binding(s); 17 casilla(s); 26 construct(s); 6 deadline_window(s); 36 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 111, 115, 117, 123, 126, 128, 130, 180, 187, 188, 190, 193, 194.

## Minimos y base imponible / liquidable

### 12. `ley-35-2006:art-50`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a50`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Base liquidable general y del ahorro."
  - "La base liquidable general estará constituida"
  - "exclusivamente y por este orden"
  - "artículos 51, 53, 54, 55 y disposición adicional undécima"
  - "sin que pueda resultar negativa"
  - "La base liquidable del ahorro será el resultado de disminuir"
  - "Si la base liquidable general resultase negativa"
  - "cuatro años siguientes"
- `notes` (verbatim): "LIRPF art 50: defines base liquidable general and base liquidable del ahorro, including the ordered reductions against base imponible general, the savings-base remnant rule for art 55, non-negative floors, and four-year compensation of negative general taxable bases. Current consolidated redaction was published 2014-11-28 and is in force from 2015-01-01. Grounds M100 base-liquidation formulas, carried negative-base compensation, and settlement completeness predicates."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 50. Base liquidable general y del ahorro.
>
> 1. La base liquidable general estará constituida por el resultado de practicar en la base imponible general, exclusivamente y por este orden, las reducciones a que se refieren los artículos 51, 53, 54, 55 y disposición adicional undécima de esta Ley, sin que pueda resultar negativa como consecuencia de dichas disminuciones.
>
> 2. La base liquidable del ahorro será el resultado de disminuir la base imponible del ahorro en el remanente, si lo hubiera, de la reducción prevista en el artículo 55, sin que pueda resultar negativa como consecuencia de tal disminución.
>
> 3. Si la base liquidable general resultase negativa, su importe podrá ser compensado con los de las bases liquidables generales positivas que se obtengan en los cuatro años siguientes.
>
> La compensación deberá efectuarse en la cuantía máxima que permita cada uno de los ejercicios siguientes y sin que pueda practicarse fuera del plazo a que se refiere el párrafo anterior mediante la acumulación a bases liquidables generales negativas de años posteriores.
>
> Se modifican los apartados 1 y 2 por el art. 1.30 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Se modifica, con efectos para los periodos impositivos finalizados con posterioridad a la entrada en vigor de la Ley Orgánica 8/2007, de 4 de julio. Ref. BOE-A-2007-13022 por la disposición final 6.1 de la Ley 51/2007, de 28 de diciembre. Ref. BOE-A-2007-22295
>
> CAPÍTULO I
>
> Reducciones por atención a situaciones de dependencia y envejecimiento

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 2 binding(s); 37 casilla(s); 30 construct(s); 99 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 13. `ley-35-2006:art-56`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a56`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2010-01-01
- `required_text`:
  - "Mínimo personal y familiar."
  - "constituye la parte de la base liquidable"
  - "necesidades básicas personales y familiares"
  - "Cuando no exista base liquidable general"
  - "artículos 57, 58, 59 y 60"
  - "gravamen autonómico"
- `notes` (verbatim): "LIRPF art 56: defines the personal and family minimum as the non-taxed part of the taxable base for basic personal and family needs, allocates it between the general and savings taxable bases, and aggregates arts 57-60 with autonomous-community increases/decreases for autonomic tax calculation. Base legal para el minimo personal y familiar in Modelo 100, casillas 0511-0524."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 56. Mínimo personal y familiar.
>
> 1. El mínimo personal y familiar constituye la parte de la base liquidable que, por destinarse a satisfacer las necesidades básicas personales y familiares del contribuyente, no se somete a tributación por este Impuesto.
>
> 2. Cuando la base liquidable general sea superior al importe del mínimo personal y familiar, éste formará parte de la base liquidable general.
>
> Cuando la base liquidable general sea inferior al importe del mínimo personal y familiar, éste formará parte de la base liquidable general por el importe de esta última y de la base liquidable del ahorro por el resto.
>
> Cuando no exista base liquidable general, el mínimo personal y familiar formará parte de la base liquidable del ahorro.
>
> 3. El mínimo personal y familiar será el resultado de sumar el mínimo del contribuyente y los mínimos por descendientes, ascendientes y discapacidad a que se refieren los artículos 57, 58, 59 y 60 de esta Ley, incrementados o disminuidos a efectos de cálculo del gravamen autonómico en los importes que, de acuerdo con lo establecido en la Ley 22/2009, por el que se regula el sistema de financiación de las Comunidades Autónomas de régimen común y Ciudades con Estatuto de Autonomía, hayan sido aprobados por la Comunidad Autónoma.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 14 casilla(s); 1 construct(s); 52 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 14. `ley-35-2006:art-73`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a73`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Cuota íntegra autonómica."
  - "La cuota íntegra autonómica del Impuesto será la suma"
  - "artículos 74 y 76"
  - "base liquidable general y del ahorro"
- `notes` (verbatim): "LIRPF art 73: defines the cuota integra autonomica as the sum of the amounts resulting from applying the autonomic general scale in art 74 and the autonomic savings scale in art 76 to the general and savings taxable bases. Base legal de la cuota integra autonomica in Modelo 100."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 73. Cuota íntegra autonómica.
>
> La cuota íntegra autonómica del Impuesto será la suma de las cuantías resultantes de aplicar los tipos de gravamen, a los que se refieren los artículos 74 y 76 de esta Ley, a la base liquidable general y del ahorro, respectivamente.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 23 casilla(s); 1 construct(s); 38 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

## Deducciones y regimenes especiales

### 15. `ley-35-2006:art-86`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a86`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Régimen de atribución de rentas."
  - "se atribuirán a los socios, herederos, comuneros o partícipes"
  - "sección 2.ª"
- `notes` (verbatim): "LIRPF art 86: general attribution-of-income rule. Income corresponding to entities under the attribution regime is attributed to partners, heirs, community members or participants according to section 2. Grounds Modelo 184 and Modelo 100 attribution surfaces."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 86. Régimen de atribución de rentas.
>
> Las rentas correspondientes a las entidades en régimen de atribución de rentas se atribuirán a los socios, herederos, comuneros o partícipes, respectivamente, de acuerdo con lo establecido en esta sección 2.ª

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 1 binding(s); 70 casilla(s); 6 construct(s); 12 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 184.

### 16. `orden-hac-242-2025:art-11`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-242-2025.html#a11`
- `document_id`: `BOE-A-2025-5049`; `effective_from`: 2025-03-15
- `required_text`:
  - "Documentación adicional que debe acompañar a la declaración del Impuesto sobre la Renta de las Personas Físicas"
  - "imputación de rentas en el régimen de transparencia fiscal internacional"
  - "datos relativos a la entidad no residente en territorio español"
  - "Nombre o razón social y lugar del domicilio social"
  - "Importe de las rentas positivas que deban ser imputadas"
  - "Justificación de los impuestos satisfechos respecto de la renta positiva"
- `notes` (verbatim): "Orden HAC/242/2025 art 11: additional documentation accompanying IRPF 2024 declarations. It requires taxpayers subject to international fiscal transparency imputation under LIRPF art 91.6 to provide non-resident entity identification, administrator, accounts, positive-income and tax-paid data."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 11. Documentación adicional que debe acompañar a la declaración del Impuesto sobre la Renta de las Personas Físicas.
>
> 1. Los contribuyentes a quienes sea de aplicación la imputación de rentas en el régimen de transparencia fiscal internacional a que se refiere el artículo 91.6 de la Ley 35/2006, de 28 de noviembre, del Impuesto sobre la Renta de las Personas Físicas, deberán presentar los siguientes datos relativos a la entidad no residente en territorio español:
>
> a) Nombre o razón social y lugar del domicilio social.
>
> b) Relación de administradores y lugar del domicilio fiscal.
>
> c) Balance, cuenta de pérdidas y ganancias y la memoria.
>
> d) Importe de las rentas positivas que deban ser imputadas.
>
> e) Justificación de los impuestos satisfechos respecto de la renta positiva que deba ser imputada.
>
> 2. Los contribuyentes que, al amparo de lo establecido en el artículo 27.11 de la Ley 19/1994, de 6 de julio, de modificación del Régimen Económico y Fiscal de Canarias, hayan efectuado en el período impositivo inversiones anticipadas de futuras dotaciones a la reserva para inversiones en Canarias, deberán presentar comunicación de la materialización de las citadas inversiones y su sistema de financiación, de acuerdo con lo dispuesto en el apartado 6 de este artículo.
>
> 3. Los contribuyentes que, al amparo de lo establecido en el número 10 del apartado Cuatro de la disposición adicional septuagésima de la Ley 31/2022, de 23 de diciembre, de Presupuestos Generales del Estado para el año 2023, hayan efectuado en el período impositivo inversiones anticipadas de futuras dotaciones a la reserva para inversiones en Illes Balears, deberán presentar comunicación de la materialización de las citadas inversiones y su sistema de financiación, de acuerdo con lo dispuesto en el apartado 6 de este artículo.
>
> 4. Los contribuyentes que soliciten la devolución mediante cheque nominativo sin cruzar del Banco de España, deberán presentar escrito conteniendo dicha solicitud, de acuerdo con lo dispuesto en el apartado 6 de este artículo.
>
> 5. De acuerdo con lo dispuesto en el artículo 89.1 de la Ley 27/2014, de 27 de noviembre, del Impuesto sobre Sociedades, tratándose de operaciones a que se refieren los artículos 76 y 87 de la mencionada ley, deberán ser objeto de comunicación a la Administración tributaria por la entidad adquirente de las operaciones, salvo que la misma no sea residente en territorio español, en cuyo caso dicha comunicación se realizará por la entidad transmitente. Esta comunicación deberá indicar el tipo de operación que se realiza y si se opta por no aplicar el régimen fiscal especial previsto en este capítulo.
>
> No obstante, en las operaciones en las cuales ni la entidad adquirente ni la transmitente sean residentes en territorio español, la comunicación deberá ser presentada por los socios que deberán indicar que la operación se ha acogido a un régimen similar al regulado en el capítulo VII del título VII de la Ley 27/2014, de 27 de noviembre, del Impuesto sobre Sociedades.
>
> Los contribuyentes que comuniquen la realización de estas operaciones deberán presentar, de acuerdo con lo dispuesto en el apartado 6 de este artículo, los siguientes documentos:
>
> a) Identificación de las entidades participantes en la operación y descripción de la misma.
>
> b) Copia de la escritura pública o documento equivalente que corresponda a la operación.
>
> c) En el caso de que las operaciones se hubieran realizado mediante una oferta pública de adquisición de acciones, también deberá aportarse copia del folleto informativo.
>
> 6. Los citados documentos o escritos y, en general, cualesquiera otros no contemplados expresamente en los propios modelos de declaración que deban acompañarse a esta, podrán presentarse a través del registro electrónico de la Agencia Estatal de Administración Tributaria, regulado mediante Resolución de 28 de diciembre de 2009, de la Presidencia de la Agencia Estatal de Administración Tributaria por la que se crea la Sede electrónica y se regulan los registros electrónicos de la Agencia Estatal de Administración Tributaria. También podrán presentarse en el registro presencial de la Agencia Estatal de Administración Tributaria. Todo ello se entenderá sin perjuicio de lo dispuesto en el artículo 16.4 de la Ley 39/2015, de 1 de octubre, del Procedimiento Administrativo Común de las Administraciones Públicas.
>
> La aportación de la documentación complementaria se realizará a través del registro electrónico de la Agencia Estatal de Administración Tributaria, en la dirección electrónica de la Agencia Estatal de Administración Tributaria, https://sede.agenciatributaria.gob.es/, accediendo al trámite de aportación de documentación complementaria correspondiente a la declaración.
>
> CAPÍTULO VI
>
> Modalidades de pago y forma de obtención de la devolución

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2024. 2 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 17. `orden-hac-248-2021:art-10`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-248-2021.html#a1-2`
- `document_id`: `BOE-A-2021-4238`; `effective_from`: 2021-03-18
- `required_text`:
  - "Documentación adicional que debe acompañar a la declaración del Impuesto sobre la Renta de las Personas Físicas"
  - "imputación de rentas en el régimen de transparencia fiscal internacional"
  - "datos relativos a la entidad no residente en territorio español"
  - "Nombre o razón social y lugar del domicilio social"
  - "Importe de las rentas positivas que deban ser imputadas"
  - "Justificación de los impuestos satisfechos respecto de la renta positiva"
- `notes` (verbatim): "Orden HAC/248/2021 art 10: additional documentation accompanying IRPF 2020 declarations. It requires taxpayers subject to international fiscal transparency imputation under LIRPF art 91 to provide non-resident entity identification, administrator, accounts, positive-income and tax-paid data."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 10. Documentación adicional que debe acompañar a la declaración del Impuesto sobre la Renta de las Personas Físicas.
>
> 1. Los contribuyentes a quienes sea de aplicación la imputación de rentas en el régimen de transparencia fiscal internacional a que se refiere el artículo 91 de la Ley 35/2006, de 28 de noviembre, reguladora del Impuesto sobre la Renta de las Personas Físicas, deberán presentar, de acuerdo con lo dispuesto en el apartado 5 de este artículo, los siguientes datos relativos a la entidad no residente en territorio español:
>
> a) Nombre o razón social y lugar del domicilio social.
>
> b) Relación de administradores y lugar del domicilio fiscal.
>
> c) Balance, cuenta de pérdidas y ganancias y la memoria.
>
> d) Importe de las rentas positivas que deban ser imputadas.
>
> e) Justificación de los impuestos satisfechos respecto de la renta positiva que deba ser imputada.
>
> 2. Los contribuyentes que, al amparo de lo establecido en el apartado 11 del artículo 27 de la Ley 19/1994, de 6 de julio, de modificación del Régimen Económico y Fiscal de Canarias, hayan efectuado en el período impositivo inversiones anticipadas de futuras dotaciones a la reserva para inversiones en Canarias, deberán presentar comunicación de la materialización de las citadas inversiones y su sistema de financiación, de acuerdo con lo dispuesto en el apartado 5 de este artículo.
>
> 3. Los contribuyentes que soliciten la devolución mediante cheque nominativo sin cruzar del Banco de España, deberán presentar escrito conteniendo dicha solicitud, de acuerdo con lo dispuesto en el apartado 5 de este artículo.
>
> 4. De acuerdo con lo dispuesto en el artículo 89.1 de la Ley 27/2014, de 27 de noviembre, del Impuesto de Sociedades, tratándose de operaciones de fusión o de escisión en las cuales ni la entidad transmitente ni la entidad adquirente tengan su residencia fiscal en España y en las que no sea de aplicación el régimen establecido en el artículo 84 de la Ley del Impuesto, por no disponer la transmitente de un establecimiento permanente situado en este país, la opción por el régimen especial corresponderá al socio residente afectado. El ejercicio de la opción se efectuará por este, cuando así lo consigne en la casilla correspondiente del modelo de declaración del Impuesto sobre la Renta de las Personas Físicas.
>
> Los contribuyentes que comuniquen la realización de estas operaciones deberán presentar, de acuerdo con lo dispuesto en el apartado 5 de este artículo, los siguientes documentos:
>
> a) Identificación de las entidades participantes en la operación y descripción de la misma.
>
> b) Copia de la escritura pública o documento equivalente que corresponda a la operación.
>
> c) En el caso de que las operaciones se hubieran realizado mediante una oferta pública de adquisición de acciones, también deberá aportarse copia del folleto informativo.
>
> 5. Los citados documentos o escritos y, en general, cualesquiera otros no contemplados expresamente en los propios modelos de declaración que deban acompañarse a esta, podrán presentarse a través del registro electrónico de la Agencia Estatal de Administración Tributaria, regulado mediante Resolución de 28 de diciembre de 2009, de la Presidencia de la Agencia Estatal de Administración Tributaria por la que se crea la Sede Electrónica y se regulan los registros electrónicos de la Agencia Estatal de Administración Tributaria. También podrán presentarse en el registro presencial de la Agencia Estatal de Administración Tributaria. Todo ello se entenderá sin perjuicio de lo dispuesto en el apartado 4 del artículo 16 de la Ley 39/2015, de 1 de octubre, del Procedimiento Administrativo Común de las Administraciones Públicas.
>
> La aportación de la documentación complementaria se realizará a través del registro electrónico de la Agencia Estatal de Administración Tributaria, en la Sede Electrónica de la Agencia Estatal de Administración Tributaria accediendo al trámite de aportación de documentación complementaria correspondiente a la declaración.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020. 2 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 18. `orden-hac-265-2024:art-11`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-265-2024.html#a1-3`
- `document_id`: `BOE-A-2024-5721`; `effective_from`: 2024-03-23
- `required_text`:
  - "Documentación adicional que debe acompañar a la declaración del Impuesto sobre la Renta de las Personas Físicas"
  - "imputación de rentas en el régimen de transparencia fiscal internacional"
  - "datos relativos a la entidad no residente en territorio español"
  - "Nombre o razón social y lugar del domicilio social"
  - "Importe de las rentas positivas que deban ser imputadas"
  - "Justificación de los impuestos satisfechos respecto de la renta positiva"
- `notes` (verbatim): "Orden HAC/265/2024 art 11: additional documentation accompanying IRPF 2023 declarations. It requires taxpayers subject to international fiscal transparency imputation under LIRPF art 91 to provide non-resident entity identification, administrator, accounts, positive-income and tax-paid data."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 11. Documentación adicional que debe acompañar a la declaración del Impuesto sobre la Renta de las Personas Físicas.
>
> 1. Los contribuyentes a quienes sea de aplicación la imputación de rentas en el régimen de transparencia fiscal internacional a que se refiere el artículo 91 de la Ley 35/2006, de 28 de noviembre, del Impuesto sobre la Renta de las Personas Físicas, deberán presentar, de acuerdo con lo dispuesto en el apartado 6 de este artículo, los siguientes datos relativos a la entidad no residente en territorio español:
>
> a) Nombre o razón social y lugar del domicilio social.
>
> b) Relación de administradores y lugar del domicilio fiscal.
>
> c) Balance, cuenta de pérdidas y ganancias y la memoria.
>
> d) Importe de las rentas positivas que deban ser imputadas.
>
> e) Justificación de los impuestos satisfechos respecto de la renta positiva que deba ser imputada.
>
> 2. Los contribuyentes que, al amparo de lo establecido en el apartado 11 del artículo 27 de la Ley 19/1994, de 6 de julio, de modificación del Régimen Económico y Fiscal de Canarias, hayan efectuado en el período impositivo inversiones anticipadas de futuras dotaciones a la reserva para inversiones en Canarias, deberán presentar comunicación de la materialización de las citadas inversiones y su sistema de financiación, de acuerdo con lo dispuesto en el apartado 6 de este artículo.
>
> 3. Los contribuyentes que, al amparo de lo establecido en el número 10 del apartado Cuatro de la disposición adicional septuagésima de la Ley 31/2022, de 23 de diciembre, de Presupuestos Generales del Estado para el año 2023, hayan efectuado en el período impositivo inversiones anticipadas de futuras dotaciones a la reserva para inversiones en Illes Balears, deberán presentar comunicación de la materialización de las citadas inversiones y su sistema de financiación, de acuerdo con lo dispuesto en el apartado 6 de este artículo.
>
> 4. Los contribuyentes que soliciten la devolución mediante cheque nominativo sin cruzar del Banco de España, deberán presentar escrito conteniendo dicha solicitud, de acuerdo con lo dispuesto en el apartado 6 de este artículo.
>
> 5. De acuerdo con lo dispuesto en el artículo 89.1 de la Ley 27/2014, de 27 de noviembre, del Impuesto sobre Sociedades, tratándose de operaciones a que se refieren los artículos 76 y 87 de la mencionada Ley, deberán ser objeto de comunicación a la Administración tributaria por la entidad adquirente de las operaciones, salvo que la misma no sea residente en territorio español, en cuyo caso dicha comunicación se realizará por la entidad transmitente. Esta comunicación deberá indicar el tipo de operación que se realiza y si se opta por no aplicar el régimen fiscal especial previsto en este capítulo.
>
> No obstante, en las operaciones en las cuales ni la entidad adquirente ni la transmitente sean residentes en territorio español, la comunicación deberá ser presentada por los socios que deberán indicar que la operación se ha acogido a un régimen similar al regulado en el Capítulo VII del Título VII de la Ley 27/2014, de 27 de noviembre, del Impuesto sobre Sociedades.
>
> Los contribuyentes que comuniquen la realización de estas operaciones deberán presentar, de acuerdo con lo dispuesto en el apartado 6 de este artículo, los siguientes documentos:
>
> a) Identificación de las entidades participantes en la operación y descripción de la misma.
>
> b) Copia de la escritura pública o documento equivalente que corresponda a la operación.
>
> c) En el caso de que las operaciones se hubieran realizado mediante una oferta pública de adquisición de acciones, también deberá aportarse copia del folleto informativo.
>
> 6. Los citados documentos o escritos y, en general, cualesquiera otros no contemplados expresamente en los propios modelos de declaración que deban acompañarse a esta, podrán presentarse a través del registro electrónico de la Agencia Estatal de Administración Tributaria, regulado mediante Resolución de 28 de diciembre de 2009, de la Presidencia de la Agencia Estatal de Administración Tributaria por la que se crea la Sede electrónica y se regulan los registros electrónicos de la Agencia Estatal de Administración Tributaria. También podrán presentarse en el registro presencial de la Agencia Estatal de Administración Tributaria. Todo ello se entenderá sin perjuicio de lo dispuesto en el apartado 4 del artículo 16 de la Ley 39/2015, de 1 de octubre, del Procedimiento Administrativo Común de las Administraciones Públicas.
>
> La aportación de la documentación complementaria se realizará a través del registro electrónico de la Agencia Estatal de Administración Tributaria, en la dirección electrónica de la Agencia Estatal de Administración Tributaria, https://sede.agenciatributaria.gob.es/, accediendo al trámite de aportación de documentación complementaria correspondiente a la declaración.
>
> CAPÍTULO VI
>
> Modalidades de pago y forma de obtención de la devolución

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2023. 2 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 19. `orden-hac-277-2026:art-10`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-277-2026.html#a10`
- `document_id`: `BOE-A-2026-7041`; `effective_from`: 2026-03-28
- `required_text`:
  - "Documentación adicional que debe acompañar a la declaración del Impuesto sobre la Renta de las Personas Físicas"
  - "imputación de rentas en el régimen de transparencia fiscal internacional"
  - "datos relativos a la entidad no residente en territorio español"
  - "Nombre o razón social y lugar del domicilio social"
  - "Importe de las rentas positivas que deban ser imputadas"
  - "Justificación de los impuestos satisfechos respecto de la renta positiva"
- `notes` (verbatim): "Orden HAC/277/2026 art 10: additional documentation accompanying IRPF 2025 declarations. It requires taxpayers subject to international fiscal transparency imputation under LIRPF art 91.6 to provide non-resident entity identification, administrator, accounts, positive-income and tax-paid data."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 10. Documentación adicional que debe acompañar a la declaración del Impuesto sobre la Renta de las Personas Físicas.
>
> 1. Los contribuyentes a quienes sea de aplicación la imputación de rentas en el régimen de transparencia fiscal internacional a que se refiere el artículo 91.6 de la Ley 35/2006, de 28 de noviembre, del Impuesto sobre la Renta de las Personas Físicas, deberán presentar los siguientes datos relativos a la entidad no residente en territorio español:
>
> a) Nombre o razón social y lugar del domicilio social.
>
> b) Relación de administradores y lugar del domicilio fiscal.
>
> c) Balance, cuenta de pérdidas y ganancias y la memoria.
>
> d) Importe de las rentas positivas que deban ser imputadas.
>
> e) Justificación de los impuestos satisfechos respecto de la renta positiva que deba ser imputada.
>
> 2. Los contribuyentes que, al amparo de lo establecido en el artículo 27.11 de la Ley 19/1994, de 6 de julio, de modificación del Régimen Económico y Fiscal de Canarias, hayan efectuado en el período impositivo inversiones anticipadas de futuras dotaciones a la reserva para inversiones en Canarias, deberán presentar comunicación de la materialización de las citadas inversiones y su sistema de financiación, de acuerdo con lo dispuesto en el apartado 6 de este artículo.
>
> 3. Los contribuyentes que, al amparo de lo establecido en el número 10 del apartado Cuatro de la disposición adicional septuagésima de la Ley 31/2022, de 23 de diciembre, de Presupuestos Generales del Estado para el año 2023, hayan efectuado en el período impositivo inversiones anticipadas de futuras dotaciones a la reserva para inversiones en Illes Balears, deberán presentar comunicación de la materialización de las citadas inversiones y su sistema de financiación, de acuerdo con lo dispuesto en el apartado 6 de este artículo.
>
> 4. Los contribuyentes que soliciten la devolución mediante cheque nominativo sin cruzar del Banco de España, deberán presentar escrito conteniendo dicha solicitud, de acuerdo con lo dispuesto en el apartado 6 de este artículo.
>
> 5. De acuerdo con lo dispuesto en el artículo 89.1 de la Ley 27/2014, de 27 de noviembre, del Impuesto sobre Sociedades, tratándose de operaciones a que se refieren los artículos 76 y 87 de la Ley 27/2014, de 27 de noviembre, deberán ser objeto de comunicación a la Administración tributaria por la entidad adquirente de las operaciones, salvo que la misma no sea residente en territorio español, en cuyo caso dicha comunicación se realizará por la entidad transmitente. Esta comunicación deberá indicar el tipo de operación que se realiza y si se opta por no aplicar el régimen fiscal especial previsto en este capítulo.
>
> No obstante, en las operaciones en las cuales ni la entidad adquirente ni la transmitente sean residentes en territorio español, la comunicación deberá ser presentada por los socios que deberán indicar que la operación se ha acogido a un régimen similar al regulado en el capítulo VII del título VII de la Ley 27/2014, de 27 de noviembre, del Impuesto sobre Sociedades.
>
> Los contribuyentes que comuniquen la realización de estas operaciones deberán presentar, de acuerdo con lo dispuesto en el apartado 6 de este artículo, los siguientes documentos:
>
> a) Identificación de las entidades participantes en la operación y descripción de la misma.
>
> b) Copia de la escritura pública o documento equivalente que corresponda a la operación.
>
> c) En el caso de que las operaciones se hubieran realizado mediante una oferta pública de adquisición de acciones, también deberá aportarse copia del folleto informativo.
>
> 6. Los citados documentos o escritos y, en general, cualesquiera otros no contemplados expresamente en los propios modelos de declaración que deban acompañarse a ésta, podrán presentarse a través del registro electrónico de la Agencia Estatal de Administración Tributaria, regulado mediante Resolución de 28 de diciembre de 2009, de la Presidencia de la Agencia Estatal de Administración Tributaria por la que se crea la Sede electrónica y se regulan los registros electrónicos de la Agencia Estatal de Administración Tributaria. También podrán presentarse en el registro presencial de la Agencia Estatal de Administración Tributaria. Todo ello se entenderá sin perjuicio de lo dispuesto en el artículo 16.4 de la Ley 39/2015, de 1 de octubre, del Procedimiento Administrativo Común de las Administraciones Públicas.
>
> La aportación de la documentación complementaria se realizará a través del registro electrónico de la Agencia Estatal de Administración Tributaria, en la dirección electrónica de la Agencia Estatal de Administración Tributaria, https://sede.agenciatributaria.gob.es/, accediendo al trámite de aportación de documentación complementaria correspondiente a la declaración.
>
> CAPÍTULO VI
>
> Modalidades de pago y forma de obtención de la devolución

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2025. 2 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 20. `orden-hfp-207-2022:art-10`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hfp-207-2022.html#a1-2`
- `document_id`: `BOE-A-2022-4296`; `effective_from`: 2022-03-18
- `required_text`:
  - "Documentación adicional que debe acompañar a la declaración del Impuesto sobre la Renta de las Personas Físicas"
  - "imputación de rentas en el régimen de transparencia fiscal internacional"
  - "datos relativos a la entidad no residente en territorio español"
  - "Nombre o razón social y lugar del domicilio social"
  - "Importe de las rentas positivas que deban ser imputadas"
  - "Justificación de los impuestos satisfechos respecto de la renta positiva"
- `notes` (verbatim): "Orden HFP/207/2022 art 10: additional documentation accompanying IRPF 2021 declarations. It requires taxpayers subject to international fiscal transparency imputation under LIRPF art 91 to provide non-resident entity identification, administrator, accounts, positive-income and tax-paid data."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 10. Documentación adicional que debe acompañar a la declaración del Impuesto sobre la Renta de las Personas Físicas.
>
> 1. Los contribuyentes a quienes sea de aplicación la imputación de rentas en el régimen de transparencia fiscal internacional a que se refiere el artículo 91 de la Ley 35/2006, de 28 de noviembre, reguladora del Impuesto sobre la Renta de las Personas Físicas, deberán presentar, de acuerdo con lo dispuesto en el apartado 5 de este artículo, los siguientes datos relativos a la entidad no residente en territorio español:
>
> a) Nombre o razón social y lugar del domicilio social.
>
> b) Relación de administradores y lugar del domicilio fiscal.
>
> c) Balance, cuenta de pérdidas y ganancias y la memoria.
>
> d) Importe de las rentas positivas que deban ser imputadas.
>
> e) Justificación de los impuestos satisfechos respecto de la renta positiva que deba ser imputada.
>
> 2. Los contribuyentes que, al amparo de lo establecido en el apartado 11 del artículo 27 de la Ley 19/1994, de 6 de julio, de modificación del Régimen Económico y Fiscal de Canarias, hayan efectuado en el período impositivo inversiones anticipadas de futuras dotaciones a la reserva para inversiones en Canarias, deberán presentar comunicación de la materialización de las citadas inversiones y su sistema de financiación, de acuerdo con lo dispuesto en el apartado 5 de este artículo.
>
> 3. Los contribuyentes que soliciten la devolución mediante cheque nominativo sin cruzar del Banco de España, deberán presentar escrito conteniendo dicha solicitud, de acuerdo con lo dispuesto en el apartado 5 de este artículo.
>
> 4. De acuerdo con lo dispuesto en el artículo 89.1 de la Ley 27/2014, de 27 de noviembre, del Impuesto de Sociedades, tratándose de operaciones de fusión o de escisión en las cuales ni la entidad transmitente ni la entidad adquirente tengan su residencia fiscal en España y en las que no sea de aplicación el régimen establecido en el artículo 84 de la Ley del Impuesto, por no disponer la transmitente de un establecimiento permanente situado en este país, la opción por el régimen especial corresponderá al socio residente afectado. El ejercicio de la opción se efectuará por este, cuando así lo consigne en la casilla correspondiente del modelo de declaración del Impuesto sobre la Renta de las Personas Físicas.
>
> Los contribuyentes que comuniquen la realización de estas operaciones deberán presentar, de acuerdo con lo dispuesto en el apartado 5 de este artículo, los siguientes documentos:
>
> a) Identificación de las entidades participantes en la operación y descripción de la misma.
>
> b) Copia de la escritura pública o documento equivalente que corresponda a la operación.
>
> c) En el caso de que las operaciones se hubieran realizado mediante una oferta pública de adquisición de acciones, también deberá aportarse copia del folleto informativo.
>
> 5. Los citados documentos o escritos y, en general, cualesquiera otros no contemplados expresamente en los propios modelos de declaración que deban acompañarse a esta, podrán presentarse a través del registro electrónico de la Agencia Estatal de Administración Tributaria, regulado mediante Resolución de 28 de diciembre de 2009, de la Presidencia de la Agencia Estatal de Administración Tributaria por la que se crea la Sede Electrónica y se regulan los registros electrónicos de la Agencia Estatal de Administración Tributaria. También podrán presentarse en el registro presencial de la Agencia Estatal de Administración Tributaria. Todo ello se entenderá sin perjuicio de lo dispuesto en el apartado 4 del artículo 16 de la Ley 39/2015, de 1 de octubre, del Procedimiento Administrativo Común de las Administraciones Públicas.
>
> La aportación de la documentación complementaria se realizará a través del registro electrónico de la Agencia Estatal de Administración Tributaria, en la dirección electrónica de la Agencia Estatal de Administración Tributaria, https://sede.agenciatributaria.gob.es/, accediendo al trámite de aportación de documentación complementaria correspondiente a la declaración.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2021. 2 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 21. `orden-hfp-310-2023:art-11`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hfp-310-2023.html#a1-3`
- `document_id`: `BOE-A-2023-8118`; `effective_from`: 2023-04-01
- `required_text`:
  - "Documentación adicional que debe acompañar a la declaración del Impuesto sobre la Renta de las Personas Físicas"
  - "imputación de rentas en el régimen de transparencia fiscal internacional"
  - "datos relativos a la entidad no residente en territorio español"
  - "Nombre o razón social y lugar del domicilio social"
  - "Importe de las rentas positivas que deban ser imputadas"
  - "Justificación de los impuestos satisfechos respecto de la renta positiva"
- `notes` (verbatim): "Orden HFP/310/2023 art 11: additional documentation accompanying IRPF 2022 declarations. It requires taxpayers subject to international fiscal transparency imputation under LIRPF art 91 to provide non-resident entity identification, administrator, accounts, positive-income and tax-paid data."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 11. Documentación adicional que debe acompañar a la declaración del Impuesto sobre la Renta de las Personas Físicas.
>
> 1. Los contribuyentes a quienes sea de aplicación la imputación de rentas en el régimen de transparencia fiscal internacional a que se refiere el artículo 91 de la Ley 35/2006, de 28 de noviembre, reguladora del Impuesto sobre la Renta de las Personas Físicas, deberán presentar, de acuerdo con lo dispuesto en el apartado 5 de este artículo, los siguientes datos relativos a la entidad no residente en territorio español:
>
> a) Nombre o razón social y lugar del domicilio social.
>
> b) Relación de administradores y lugar del domicilio fiscal.
>
> c) Balance, cuenta de pérdidas y ganancias y la memoria.
>
> d) Importe de las rentas positivas que deban ser imputadas.
>
> e) Justificación de los impuestos satisfechos respecto de la renta positiva que deba ser imputada.
>
> 2. Los contribuyentes que, al amparo de lo establecido en el apartado 11 del artículo 27 de la Ley 19/1994, de 6 de julio, de modificación del Régimen Económico y Fiscal de Canarias, hayan efectuado en el período impositivo inversiones anticipadas de futuras dotaciones a la reserva para inversiones en Canarias, deberán presentar comunicación de la materialización de las citadas inversiones y su sistema de financiación, de acuerdo con lo dispuesto en el apartado 5 de este artículo.
>
> 3. Los contribuyentes que soliciten la devolución mediante cheque nominativo sin cruzar del Banco de España, deberán presentar escrito conteniendo dicha solicitud, de acuerdo con lo dispuesto en el apartado 5 de este artículo.
>
> 4. De acuerdo con lo dispuesto en el artículo 89.1 de la Ley 27/2014, de 27 de noviembre, del Impuesto de Sociedades, tratándose de operaciones de fusión o de escisión en las cuales ni la entidad transmitente ni la entidad adquirente tengan su residencia fiscal en España y en las que no sea de aplicación el régimen establecido en el artículo 84 de la Ley del Impuesto, por no disponer la transmitente de un establecimiento permanente situado en este país, la opción por el régimen especial corresponderá al socio residente afectado. El ejercicio de la opción se efectuará por este, cuando así lo consigne en la casilla correspondiente del modelo de declaración del Impuesto sobre la Renta de las Personas Físicas.
>
> Los contribuyentes que comuniquen la realización de estas operaciones deberán presentar, de acuerdo con lo dispuesto en el apartado 5 de este artículo, los siguientes documentos:
>
> a) Identificación de las entidades participantes en la operación y descripción de la misma.
>
> b) Copia de la escritura pública o documento equivalente que corresponda a la operación.
>
> c) En el caso de que las operaciones se hubieran realizado mediante una oferta pública de adquisición de acciones, también deberá aportarse copia del folleto informativo.
>
> 5. Los citados documentos o escritos y, en general, cualesquiera otros no contemplados expresamente en los propios modelos de declaración que deban acompañarse a esta, podrán presentarse a través del registro electrónico de la Agencia Estatal de Administración Tributaria, regulado mediante Resolución de 28 de diciembre de 2009, de la Presidencia de la Agencia Estatal de Administración Tributaria por la que se crea la sede electrónica y se regulan los registros electrónicos de la Agencia Estatal de Administración Tributaria. También podrán presentarse en el registro presencial de la Agencia Estatal de Administración Tributaria. Todo ello se entenderá sin perjuicio de lo dispuesto en el apartado 4 del artículo 16 de la Ley 39/2015, de 1 de octubre, del Procedimiento Administrativo Común de las Administraciones Públicas.
>
> La aportación de la documentación complementaria se realizará a través del registro electrónico de la Agencia Estatal de Administración Tributaria, en la dirección electrónica de la Agencia Estatal de Administración Tributaria, https://sede.agenciatributaria.gob.es/, accediendo al trámite de aportación de documentación complementaria correspondiente a la declaración.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2022. 2 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 22. `rd-439-2007:art-39`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/rd-439-2007-art-39.html#a39`
- `document_id`: `BOE-A-2007-6820`; `effective_from`: 2007-04-01
- `required_text`:
  - "El método de estimación objetiva"
  - "todos sus socios, herederos, comuneros o partícipes sean personas físicas"
  - "definición del ámbito de aplicación"
  - "se atribuirá por partes iguales"
- `notes` (verbatim): "RIRPF art 39: entidades en regimen de atribucion. Establece la aplicacion del metodo de estimacion objetiva a actividades economicas desarrolladas por entidades de atribucion de rentas, con independencia de las circunstancias individuales de sus miembros y con reglas de computo del ambito de aplicacion."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 39. Entidades en régimen de atribución.
>
> 1. El método de estimación objetiva será aplicable para la determinación del rendimiento neto de las actividades económicas desarrolladas por las entidades a que se refiere el artículo 87 de la Ley del Impuesto, siempre que todos sus socios, herederos, comuneros o partícipes sean personas físicas contribuyentes por este Impuesto.
>
> 2. La renuncia al método, que deberá efectuarse de acuerdo a lo dispuesto en el artículo 33 de este Reglamento, se formulará por todos los socios, herederos, comuneros o partícipes.
>
> 3. La aplicación de este método de estimación objetiva deberá efectuarse con independencia de las circunstancias que concurran individualmente en los socios, herederos, comuneros o partícipes.
>
> No obstante, para la definición del ámbito de aplicación deberán computarse no sólo las operaciones correspondientes a las actividades económicas desarrolladas por la propia entidad en régimen de atribución, sino también las correspondientes a las desarrolladas por sus socios, herederos, comuneros o partícipes; los cónyuges, descendientes y ascendientes de éstos; así como por otras entidades en régimen de atribución de rentas en las que participen cualquiera de las personas anteriores, en las que concurran las circunstancias señaladas en el artículo 32.2.a) de este Reglamento.
>
> 4. El rendimiento neto se atribuirá a los socios, herederos, comuneros o partícipes, según las normas o pactos aplicables en cada caso y, si éstos no constaran a la Administración en forma fehaciente, se atribuirá por partes iguales.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2025. 1 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-27`.

## Calculo del impuesto y regularizacion

### 23. `ley-35-2006:art-62`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a62`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Cuota íntegra estatal."
  - "La cuota íntegra estatal será la suma"
  - "artículos 63 y 66"
  - "bases liquidables general y del ahorro"
- `notes` (verbatim): "LIRPF art 62: defines the cuota integra estatal as the sum of the amounts resulting from applying the state general scale in art 63 and the state savings scale in art 66 to the general and savings taxable bases. Base legal de la cuota integra estatal in Modelo 100."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 62. Cuota íntegra estatal.
>
> La cuota íntegra estatal será la suma de las cantidades resultantes de aplicar los tipos de gravamen, a los que se refieren los artículos 63 y 66 de esta Ley, a las bases liquidables general y del ahorro, respectivamente.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 22 casilla(s); 7 construct(s); 30 formula(s); 6 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 24. `ley-35-2006:art-80`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a80`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Deducción por doble imposición internacional"
  - "rendimientos o ganancias patrimoniales obtenidos y gravados en el extranjero"
  - "impuesto de naturaleza idéntica o análoga"
  - "resultado de aplicar el tipo medio efectivo de gravamen"
  - "cuota líquida total por la base liquidable"
- `notes` (verbatim): "LIRPF art 80: deduccion por doble imposicion internacional para rendimientos o ganancias patrimoniales obtenidos y gravados en el extranjero. The current consolidated text, effective from 2015-01-01 after Ley 26/2014, limits the deduction to the lesser of the foreign tax paid for an identical or analogous tax and the effective average tax rate applied to the foreign-taxed base. Base legal para Modelo 100 casillas 1124, 1127, 1128."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 80. Deducción por doble imposición internacional.
>
> 1. Cuando entre las rentas del contribuyente figuren rendimientos o ganancias patrimoniales obtenidos y gravados en el extranjero, se deducirá la menor de las cantidades siguientes:
>
> a) El importe efectivo de lo satisfecho en el extranjero por razón de un impuesto de naturaleza idéntica o análoga a este impuesto o al Impuesto sobre la Renta de no Residentes sobre dichos rendimientos o ganancias patrimoniales.
>
> b) El resultado de aplicar el tipo medio efectivo de gravamen a la parte de base liquidable gravada en el extranjero.
>
> 2. A estos efectos, el tipo medio efectivo de gravamen será el resultado de multiplicar por 100 el cociente obtenido de dividir la cuota líquida total por la base liquidable. A tal fin, se deberá diferenciar el tipo de gravamen que corresponda a las rentas generales y del ahorro, según proceda. El tipo de gravamen se expresará con dos decimales.
>
> 3. Cuando se obtengan rentas en el extranjero a través de un establecimiento permanente se practicará la deducción por doble imposición internacional prevista en este artículo, y en ningún caso resultará de aplicación lo dispuesto en el artículo 22 de la Ley del Impuesto sobre Sociedades.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 3 casilla(s); 8 construct(s); 6 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 25. `ley-35-2006:art-87`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a87`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2022-10-20
- `required_text`:
  - "Entidades en régimen de atribución de rentas."
  - "artículo 8.3 de esta Ley"
  - "entidades constituidas en el extranjero"
  - "no estarán sujetas al Impuesto sobre Sociedades"
  - "apartado 12 del artículo 15 bis"
- `notes` (verbatim): "LIRPF art 87: defines entities under the attribution-of-income regime, including entities referenced in art 8.3, analogous foreign entities, the exclusion for sociedades agrarias de transformación, and the non-IS-subject rule except LIS art 15 bis.12. Current consolidated redaction was published 2022-10-19 and is in force from 2022-10-20."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 87. Entidades en régimen de atribución de rentas.
>
> 1. Tendrán la consideración de entidades en régimen de atribución de rentas aquellas a las que se refiere el artículo 8.3 de esta Ley y, en particular, las entidades constituidas en el extranjero cuya naturaleza jurídica sea idéntica o análoga a la de las entidades en atribución de rentas constituidas de acuerdo con las leyes españolas.
>
> 2. El régimen de atribución de rentas no será aplicable a las sociedades agrarias de transformación que tributarán por el Impuesto sobre Sociedades.
>
> 3. Las entidades en régimen de atribución de rentas no estarán sujetas al Impuesto sobre Sociedades, a excepción de lo dispuesto en el apartado 12 del artículo 15 bis de la Ley del Impuesto sobre Sociedades.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

#### Modelo 100 dependents

Cited in revisions 2022, 2023, 2024, 2025. 1 binding(s); 2 casilla(s); 6 construct(s); 12 formula(s); 1 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 184.

### 26. `ley-35-2006:art-87-2007`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-87-2007.html#a87`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Entidades en régimen de atribución de rentas."
  - "artículo 8.3 de esta Ley"
  - "entidades constituidas en el extranjero"
  - "no estarán sujetas al Impuesto sobre Sociedades"
- `notes` (verbatim): "LIRPF art 87, original 2006-11-29 text, in force 2007-01-01 to 2022-10-19: defines entities under the attribution-of-income regime (art. 8.3 entities, analogous foreign entities, the sociedades agrarias de transformación exclusion, the non-IS-subject rule), before Ley 31/2022 art. 62.5 added the LIS art. 15 bis.12 exception clause with effect from 2022-10-20. Grounds the 2020 and 2021 Modelo 100 régimen de atribución de rentas casillas."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 87. Entidades en régimen de atribución de rentas.
>
> 1. Tendrán la consideración de entidades en régimen de atribución de rentas aquellas a las que se refiere el artículo 8.3 de esta Ley y, en particular, las entidades constituidas en el extranjero cuya naturaleza jurídica sea idéntica o análoga a la de las entidades en atribución de rentas constituidas de acuerdo con las leyes españolas.
>
> 2. El régimen de atribución de rentas no será aplicable a las sociedades agrarias de transformación que tributarán por el Impuesto sobre Sociedades.
>
> 3. Las entidades en régimen de atribución de rentas no estarán sujetas al Impuesto sobre Sociedades.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021. 2 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-02`.

### 27. `ley-35-2006:art-88`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a88`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Calificación de la renta atribuida."
  - "tendrán la naturaleza derivada de la actividad o fuente"
  - "para cada uno de ellos"
- `notes` (verbatim): "LIRPF art 88: classifies attributed income by preserving the nature derived from the underlying activity or source for each partner, heir, community member or participant."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 88. Calificación de la renta atribuida.
>
> Las rentas de las entidades en régimen de atribución de rentas atribuidas a los socios, herederos, comuneros o partícipes tendrán la naturaleza derivada de la actividad o fuente de donde procedan para cada uno de ellos.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 1 binding(s); 2 casilla(s); 6 construct(s); 12 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 184.

### 28. `ley-35-2006:art-89`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a89`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Cálculo de la renta atribuible y pagos a cuenta."
  - "Para el cálculo de las rentas a atribuir"
  - "se determinarán con arreglo a las normas de este Impuesto"
  - "no serán aplicables las reducciones previstas en los artículos 23.2, 23.3, 26.2 y 32"
  - "estarán sujetas a retención o ingreso a cuenta"
  - "se atribuirán por partes iguales"
  - "podrán practicar en su declaración las reducciones previstas"
- `notes` (verbatim): "LIRPF art 89: calculation of attributable income and payments on account. It determines attributed income under IRPF rules, excludes listed reductions during entity-level attribution, subjects paid income to withholding/on-account rules, attributes income by applicable rules or equal shares if not proven, and lets IRPF members apply listed reductions on their own returns."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 89. Cálculo de la renta atribuible y pagos a cuenta.
>
> 1. Para el cálculo de las rentas a atribuir a cada uno de los socios, herederos, comuneros o partícipes, se aplicarán las siguientes reglas:
>
> 1.ª Las rentas se determinarán con arreglo a las normas de este Impuesto, y no serán aplicables las reducciones previstas en los artículos 23.2, 23.3, 26.2 y 32 de esta Ley, con las siguientes especialidades:
>
> a) La renta atribuible se determinará de acuerdo con lo previsto en la normativa del Impuesto sobre Sociedades cuando todos los miembros de la entidad en régimen de atribución de rentas sean sujetos pasivos de dicho Impuesto o contribuyentes por el Impuesto sobre la Renta de no Residentes con establecimiento permanente.
>
> b) La determinación de la renta atribuible a los contribuyentes del Impuesto sobre la Renta de no Residentes sin establecimiento permanente se efectuará de acuerdo con lo previsto en el capítulo IV del texto refundido de la Ley del Impuesto sobre la Renta de no Residentes, aprobado por el Real Decreto Legislativo 5/2004, de 5 de marzo.
>
> c) Para el cálculo de la renta atribuible a los miembros de la entidad en régimen de atribución de rentas, que sean sujetos pasivos del Impuesto sobre Sociedades o contribuyentes por el Impuesto sobre la Renta de no Residentes con establecimiento permanente o sin establecimiento permanente que no sean personas físicas, procedente de ganancias patrimoniales derivadas de la transmisión de elementos no afectos al desarrollo de actividades económicas, no resultará de aplicación lo establecido en la disposición transitoria novena de esta Ley.
>
> 2.ª La parte de renta atribuible a los socios, herederos, comuneros o partícipes, contribuyentes por este Impuesto o por el Impuesto sobre Sociedades, que formen parte de una entidad en régimen de atribución de rentas constituida en el extranjero, se determinará de acuerdo con lo señalado en la regla 1.ª anterior.
>
> 3.ª Cuando la entidad en régimen de atribución de rentas obtenga rentas de fuente extranjera que procedan de un país con el que España no tenga suscrito un convenio para evitar la doble imposición con cláusula de intercambio de información, no se computarán las rentas negativas que excedan de las positivas obtenidas en el mismo país y procedan de la misma fuente. El exceso se computará en los cuatro años siguientes de acuerdo con lo señalado en esta regla 3.ª
>
> 2. Estarán sujetas a retención o ingreso a cuenta, con arreglo a las normas de este Impuesto, las rentas que se satisfagan o abonen a las entidades en régimen de atribución de rentas, con independencia de que todos o alguno de sus miembros sea contribuyente por este Impuesto, sujeto pasivo del Impuesto sobre Sociedades o contribuyente por el Impuesto sobre la Renta de no Residentes. Dicha retención o ingreso a cuenta se deducirá en la imposición personal del socio, heredero, comunero o partícipe, en la misma proporción en que se atribuyan las rentas.
>
> 3. Las rentas se atribuirán a los socios, herederos, comuneros o partícipes según las normas o pactos aplicables en cada caso y, si éstos no constaran a la Administración tributaria en forma fehaciente, se atribuirán por partes iguales.
>
> 4. Los miembros de la entidad en régimen de atribución de rentas que sean contribuyentes por este Impuesto podrán practicar en su declaración las reducciones previstas en los artículos 23.2, 23.3, 26.2 y 32.1 de esta Ley.
>
> 5. Los sujetos pasivos del Impuesto sobre Sociedades y los contribuyentes por el Impuesto sobre la Renta de no Residentes con establecimiento permanente, que sean miembros de una entidad en régimen de atribución de rentas que adquiera acciones o participaciones en instituciones de inversión colectiva, integrarán en su base imponible el importe de las rentas contabilizadas o que deban contabilizarse procedentes de las citadas acciones o participaciones. Asimismo, integrarán en su base imponible el importe de los rendimientos del capital mobiliario derivados de la cesión a terceros de capitales propios que se hubieran devengado a favor de la entidad en régimen de atribución de rentas.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 1 binding(s); 2 casilla(s); 6 construct(s); 12 formula(s); 1 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 184.

## Procedural (aprobacion anual del modelo / plazos)

### 29. `ley-19-1994:art-27`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-19-1994-art-27.html#a27`
- `document_id`: `BOE-A-1994-15794`; `effective_from`: 1994-07-08
- `required_text`:
  - "Reserva para inversiones en Canarias"
  - "plazo máximo de tres años"
  - "cinco años como mínimo"
  - "rendimientos netos mediante el método de estimación directa"
  - "rendimientos netos de explotación"
  - "ochenta por ciento"
- `notes` (verbatim): "Ley 19/1994 art 27: Reserva para inversiones en Canarias (RIC). Grounds Modelo 100 RIC parameters for materialisation within three years, minimum five-year maintenance, and the IRPF direct-estimation deduction limit over net operating income assigned to the reserve."
- `reviewed_by` (verbatim): "agent-review"

#### Bundled corpus text

> Artículo 27. Reserva para inversiones en Canarias.
>
> 1. Las entidades sujetas al Impuesto sobre Sociedades tendrán derecho a la reducción en la base imponible de las cantidades que, con relación a sus establecimientos situados en Canarias, destinen de sus beneficios a la reserva para inversiones de acuerdo con lo dispuesto en este artículo.
>
> 4. Las cantidades destinadas a la reserva para inversiones en Canarias deberán materializarse en el plazo máximo de tres años, contados desde la fecha del devengo del impuesto correspondiente al ejercicio en que se ha dotado la misma, en la realización de alguna de las siguientes inversiones:
>
> Los elementos patrimoniales en que se materialice la inversión deberán permanecer en funcionamiento en la empresa del adquirente durante cinco años como mínimo, sin ser objeto de transmisión, arrendamiento o cesión a terceros para su uso.
>
> 15. Los contribuyentes del Impuesto sobre la Renta de las Personas Físicas que determinen sus rendimientos netos mediante el método de estimación directa tendrán derecho a una deducción en la cuota íntegra por los rendimientos netos de explotación que se destinen a la reserva para inversiones, siempre y cuando éstos provengan de actividades económicas realizadas mediante establecimientos situados en Canarias.
>
> La deducción se calculará aplicando el tipo medio de gravamen a las dotaciones anuales a la reserva y tendrá como límite el ochenta por ciento de la parte de la cuota íntegra que proporcionalmente corresponda a la cuantía de los rendimientos netos de explotación que provengan de establecimientos situados en Canarias.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2025. 3 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.
