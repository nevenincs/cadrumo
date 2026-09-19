---
tags:
  - '#reference'
  - '#modelo-131-legal-attestation-review'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:ddcb553453799d0ddaabed3230ef0c6723821999c93f4ed4af59d4fed534c941'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-14-registry-campaign-sequencing-operator-attestation-ledger-audit]]"
  - "[[2026-08-14-legal-attestation-packet-methodology-audit]]"
---

# `modelo-131-legal-attestation-review` reference: `Modelo 131 legal-reference attestation review packet`

Modelo 131 (Impuesto sobre la Renta de las Personas Físicas -- actividades
económicas en estimación objetiva -- pago fraccionado) carries the last 25
legal references remaining across the seven modelos that already declare
export layouts. With this packet, every currently layout-capable modelo has
a prepared operator-attestation packet: Modelo 390 (10 references), Modelo
180/145/349 combined (15), Modelo 100 (119, across three batches), and now
Modelo 131 (25) -- **169 references prepared across six modelos**. The
seventh, Modelo 720, needs no legal-reference attestation at all: zero
remaining references, one revision stamp. Worklist confirmed at exactly 25
via `collect_snapshot_ref_ids` across all four Modelo 131 revisions
(2019-2023, 2024, 2025, 2026) -- the same authoritative mechanism used
throughout this series, not a grep.

**The numeric flag bites harder here than anywhere else in the series, as
expected going in.** Modelo 131 is módulos -- estimación objetiva -- and its
governing instrucciones print índices correctores and coeficientes as
tables, not as prose sentences. **24 of the 25 references state a rate,
coefficient, bracket or threshold.** The single non-numeric reference,
`orden-eha-672-2007:art-3`, approves the Modelo 131 form itself and states
no figure. The full-text-plus-table-shape numeric detection method --
catalogue fields, full-text phrase-adjacency, AND a dedicated table-shape
signal (table-header markers such as "tramo", "coeficiente", "índice",
"módulo" co-occurring with three or more bare decimal-comma numbers or a
euro-thousands-shaped figure) -- was applied from the FIRST pass on this
packet, not retrofitted after a miss, per the recommendation in
`legal-attestation-packet-methodology-audit` written after Modelo 100's
Batch B/C correction. That audit's finding that a cheap method undercounts,
and undercounts specifically the references most worth catching, is exactly
what this packet was built to not repeat.

**23 of the 25 also carry a self-verification claim** in `reviewed_by` or
`notes` -- overwhelmingly "agent-authored... operator to re-stamp", the same
shape as Modelo 100's Batch A, plus several instances of "cross-checked
byte-identical against the AEAT Manual práctico de Renta" worked examples
(the coefficient-table entries specifically). Unlike Modelo 100, where this
property defined one batch and the numeric property defined another, here
the two properties overlap almost completely -- the same 22 references carry
both -- so this packet is not split into batches. Twenty-five references in
one sitting is comparable in size to the Modelo 180/145/349 packet (fifteen)
and well inside a single review session.

For each reference this packet places the registry's own claim next to the
actual bundled corpus text it points at, quoted verbatim, and lists what in
Modelo 131 depends on it. It does not state whether the claim and the source
agree -- that is the operator's act, and stating it here would turn the
operator's sign-off into a rubber stamp on agent work. The one exception is a
structural discrepancy: a broken `corpus_ref`, a `required_text` phrase absent
from the quoted text, or a citation that plainly names a different subject.
**Zero of the 25 references below triggered that exception**, and the wider
series -- Modelo 390's 10, Modelo 180/145/349's 15, Modelo 100's 119 -- has
found none either, so the full 169-reference sweep across six modelos closes
with zero structural discrepancies found anywhere. Every `corpus_ref` below
resolves and every declared `required_text` phrase is present in the quoted
text, checked against the same production normaliser
(`cadrumo.core.normalise_corpus_text`) used throughout.

**Standing caveat on the `notes` and `reviewed_by` fields.** Every `notes`
and `reviewed_by` value quoted below is agent-authored registry content, not
operator-verified prose. As on Modelo 100's Batch A, this is the norm in
this packet rather than the exception -- 23 of 25 entries carry some form of
"already checked" language. Where a note asserts that a coefficient table
was cross-checked against an AEAT manual worked example (several entries
below), that assertion is itself an unverified agent claim carrying exactly
the same weight as any other claim in this packet.

**Cross-modelo sharing.** Five of the 25 are also cited elsewhere, and all
five are also part of the Modelo 100 tranche this series already wrote up:
`ley-35-2006:art-31`, `orden-eha-672-2007:art-3`, `orden-hac-1347-2024:da-1`
and `real-decreto-ley-7-2024:art-11` were each covered in one of Modelo
100's three batches, and `rd-439-2007:art-110` is cited by both Modelo 100
and Modelo 130. Each still gets its own full section here rather than a
cross-reference, because Modelo 131's own dependent casillas differ from
Modelo 100's and the operator attesting for Modelo 131 needs the claim and
source in front of them regardless of having reviewed the same citation
under a different modelo already.

This document is read-only working material. No `operator_reviewed` stamp was
applied or could be applied through any path available to this session, and
nothing under `modelos/131/**` was touched to produce it.

## Summary

Twenty-five sections follow in three groups. **Fundamento y aprobación del
modelo** (2 references) grounds the estimación objetiva regime itself and
the form's approval. **Anexo II: módulos, índices correctores e
incompatibilidades** (21 references) is organised by INSTRUCTION TOPIC
rather than alphabetically or by orden: each of the eight instrucción
sub-provisions Modelo 131 depends on is grouped with its citation from every
one of the three yearly órdenes (2023, 2024, 2025) that carries it, so an
operator reviewing "the employment-incentive coefficient table" sees all
three years' versions together rather than scattered across the document.
**Otras referencias** (2 references) covers the retention-percentage
reglamento article and the RDL 7/2024 módulos reduction. Each section
carries the same four parts in the same order: the registry's current
entry, the bundled corpus text quoted verbatim (the trailing BOE
amendment-history citation footer is omitted where present; the substantive
body -- including every coefficient table -- is never abridged), what in
Modelo 131 depends on it, and the entry's current review status, plus the
`**Numeric flag**` line the 24 numeric entries each carry.

## Fundamento y aprobacion del modelo

### 1. `ley-35-2006:art-31`

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

**Numeric flag**: this reference states a rate, coefficient, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

#### Modelo 131 dependents

Cited in revisions 2024, 2025, 2026. 17 casilla(s); 3 construct(s); 12 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 100.

### 2. `orden-eha-672-2007:art-3`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-eha-672-2007.html#a3`
- `document_id`: `BOE-A-2007-6032`; `effective_from`: 2007-04-01
- `required_text`:
  - "Aprobación del modelo 131"
  - "Actividades económicas en estimación objetiva"
  - "código 131"
- `notes` (verbatim): "Orden EHA/672/2007 art 3: aprobacion del Modelo 131 para pagos fraccionados IRPF de actividades economicas en estimacion objetiva."
- `reviewed_by` (verbatim): "verified against bundled orden-eha-672-2007.html#a3 and official BOE-A-2007-6032#a3; operator to re-stamp"

#### Bundled corpus text

> Artículo 3. Aprobación del modelo 131.
>
> Se aprueba el modelo 131. Impuesto sobre la Renta de las Personas Físicas. Actividades económicas en estimación objetiva. Pago fraccionado. Autoliquidación.
>
> Dicho modelo, que figura como anexo II de la presente orden, consta de los dos ejemplares siguientes:
>
> Ejemplar para el declarante.
>
> Ejemplar para la Entidad colaboradora-AEAT.
>
> El número de justificante que habrá de figurar en este modelo será un número secuencial cuyos tres primeros dígitos se corresponderán con el código 131. No obstante, en el supuesto a que se refiere el artículo 4 de la Orden HAP/2194/2013, de 22 de noviembre, por la que se regulan los procedimientos y las condiciones generales para la presentación de determinadas autoliquidaciones y declaraciones informativas de naturaleza tributaria, el número de justificante comenzará con el código 135.
>
> Se modifica por el art. único.2 de la Orden HAP/258/2015, de 17 de febrero. Ref. BOE-A-2015-1656
>
> Esta modificación surtirá efectos respecto de la presentación de las declaraciones formuladas que correspondan a la primera autoliquidación trimestral del ejercicio 2015 y siguientes, según establece la disposición final 3 de la citada Orden.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 131 dependents

Cited in revisions 2019-2023, 2024, 2025, 2026. 35 application_link(s); 298 binding(s); 4 construct(s); 4 deadline_window(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 100.

## Anexo II: modulos, indices correctores e incompatibilidades (ordenes 2023, 2024, 2025)

### Fase 2, minoracion por incentivos al empleo (instruccion 2.2.a)

#### 3. `orden-hac-1347-2024:instruccion-2-2-a`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1347-2024.html#anexo-ii-instruccion-2-2-a`
- `document_id`: `BOE-A-2024-24949`; `effective_from`: 2025-01-01
- `required_text`:
  - "2.2 Fase 2: Rendimiento neto minorado."
  - "El rendimiento neto previo se minorará en el importe de los incentivos al empleo y la inversión"
  - "a) Minoración por incentivos al empleo."
  - "Si la diferencia resultase positiva, a ésta se aplicará el coeficiente 0,40"
- `notes` (verbatim): "Fase 2a: minoracion por incentivos al empleo. El rendimiento neto previo se minora en el coeficiente de minoracion (incremento del modulo personal asalariado x 0,40, mas el coeficiente por tramos del numero de unidades restante) multiplicado por el rendimiento anual por unidad del modulo personal asalariado. Cross-checked byte-identical against the AEAT Manual practico de Renta 2025, Parte 1, worked example epigrafe 673.1."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1347-2024.html; operator to re-stamp"

##### Bundled corpus text

> 2.2 Fase 2: Rendimiento neto minorado.
>
> El rendimiento neto previo se minorará en el importe de los incentivos al empleo y la inversión, en la forma que se establece a continuación, dando lugar al rendimiento neto minorado.
>
> a) Minoración por incentivos al empleo.
>
> Para practicar la minoración por incentivos al empleo se tendrá en cuenta lo siguiente:
>
> 1.º Si en el año que se liquida hubiese tenido lugar un incremento del número de personas asalariadas, por comparación al año inmediato anterior, se calculará, en primer lugar, la diferencia entre el número de unidades del módulo «personal asalariado» correspondientes al año y el número de unidades de ese mismo módulo correspondientes al año inmediato anterior. A estos efectos, se tendrán en cuenta exclusivamente las personas asalariadas que se hayan computado en la Fase 1.ª, de acuerdo con lo establecido en la regla 2.ª
>
> Si en el año anterior no se hubiese estado acogido al régimen de estimación objetiva, se tomará como número de unidades correspondientes a dicho año el que hubiese debido tomarse, de acuerdo a las normas contenidas en la regla 2.ª de la Fase anterior.
>
> Si la diferencia resultase positiva, a ésta se aplicará el coeficiente 0,40. El resultado es el coeficiente por incremento del número de personas asalariadas.
>
> Si la diferencia hubiese resultado positiva y, por tanto, hubiese procedido la aplicación del coeficiente 0,40, a dicha diferencia no se le aplicará la tabla de coeficientes por tramos que se señala a continuación.
>
> 2.º Además, a cada uno de los tramos del número de unidades del módulo que a continuación se indica se le aplicarán los coeficientes que se expresan en la siguiente tabla:
>
> Tramo
>
> Coeficiente
>
> Hasta 1,00.
>
> 0,10
>
> Entre 1,01 a 3,00.
>
> 0,15
>
> Entre 3,01 a 5,00.
>
> 0,20
>
> Entre 5,01 a 8,00.
>
> 0,25
>
> Más de 8,00.
>
> 0,30
>
> Para cuantificar la minoración por incentivos al empleo, se procede de la siguiente forma:
>
> – Se suma el coeficiente por incremento del número de personas asalariadas, si procede, y el de la tabla anterior, obteniéndose el coeficiente de minoración.
>
> – Este coeficiente de minoración se multiplica por el «Rendimiento anual por unidad antes de amortización» correspondiente al módulo «personal asalariado». La cantidad anterior se minora del rendimiento neto previo.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a coefficient/rate table (tramos and their corresponding coefficients laid out as table rows rather than in a sentence carrying "por ciento" or "euros" adjacent to the figure) -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2025. 2 casilla(s); 1 construct(s); 1 formula(s); 2 parameter(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-03`.

#### 4. `orden-hac-1425-2025:instruccion-2-2-a`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1425-2025.html#anexo-ii-instruccion-2-2-a`
- `document_id`: `BOE-A-2025-25272`; `effective_from`: 2026-01-01
- `required_text`:
  - "2.2 Fase 2: Rendimiento neto minorado."
  - "El rendimiento neto previo se minorará en el importe de los incentivos al empleo y la inversión"
  - "a) Minoración por incentivos al empleo."
  - "Si la diferencia resultase positiva, a ésta se aplicará el coeficiente 0,40"
- `notes` (verbatim): "Fase 2a: minoracion por incentivos al empleo. El rendimiento neto previo se minora en el coeficiente de minoracion (incremento del modulo personal asalariado x 0,40, mas el coeficiente por tramos del numero de unidades restante) multiplicado por el rendimiento anual por unidad del modulo personal asalariado. Cross-checked byte-identical against the 2025 instruccion (orden-hac-1347-2024:instruccion-2-2-a): same coeficiente 0,40 and tramos schedule (0,10/0,15/0,20/0,25/0,30)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1425-2025.html; operator to re-stamp"

##### Bundled corpus text

> 2.2 Fase 2: Rendimiento neto minorado.
>
> El rendimiento neto previo se minorará en el importe de los incentivos al empleo y la inversión, en la forma que se establece a continuación, dando lugar al rendimiento neto minorado.
>
> a) Minoración por incentivos al empleo.
>
> Para practicar la minoración por incentivos al empleo se tendrá en cuenta lo siguiente:
>
> 1.º Si en el año que se liquida hubiese tenido lugar un incremento del número de personas asalariadas, por comparación al año inmediato anterior, se calculará, en primer lugar, la diferencia entre el número de unidades del módulo «personal asalariado» correspondientes al año y el número de unidades de ese mismo módulo correspondientes al año inmediato anterior. A estos efectos, se tendrán en cuenta exclusivamente las personas asalariadas que se hayan computado en la Fase 1.ª, de acuerdo con lo establecido en la regla 2.ª
>
> Si en el año anterior no se hubiese estado acogido al régimen de estimación objetiva, se tomará como número de unidades correspondientes a dicho año el que hubiese debido tomarse, de acuerdo a las normas contenidas en la regla 2.ª de la Fase anterior.
>
> Si la diferencia resultase positiva, a ésta se aplicará el coeficiente 0,40. El resultado es el coeficiente por incremento del número de personas asalariadas.
>
> Si la diferencia hubiese resultado positiva y, por tanto, hubiese procedido la aplicación del coeficiente 0,40, a dicha diferencia no se le aplicará la tabla de coeficientes por tramos que se señala a continuación.
>
> 2.º Además, a cada uno de los tramos del número de unidades del módulo que a continuación se indica se le aplicarán los coeficientes que se expresan en la siguiente tabla:
>
> Tramo
>
> Coeficiente
>
> Hasta 1,00.
>
> 0,10
>
> Entre 1,01 a 3,00.
>
> 0,15
>
> Entre 3,01 a 5,00.
>
> 0,20
>
> Entre 5,01 a 8,00.
>
> 0,25
>
> Más de 8,00.
>
> 0,30
>
> Para cuantificar la minoración por incentivos al empleo, se procede de la siguiente forma:
>
> – Se suma el coeficiente por incremento del número de personas asalariadas, si procede, y el de la tabla anterior, obteniéndose el coeficiente de minoración.
>
> – Este coeficiente de minoración se multiplica por el «Rendimiento anual por unidad antes de amortización» correspondiente al módulo «personal asalariado». La cantidad anterior se minora del rendimiento neto previo.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a coefficient/rate table (tramos and their corresponding coefficients laid out as table rows rather than in a sentence carrying "por ciento" or "euros" adjacent to the figure) -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2026. 2 casilla(s); 1 construct(s); 1 formula(s); 2 parameter(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-04`.

#### 5. `orden-hfp-1359-2023:instruccion-2-2-a`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hfp-1359-2023.html#anexo-ii-instruccion-2-2-a`
- `document_id`: `BOE-A-2023-25882`; `effective_from`: 2024-01-01
- `required_text`:
  - "2.2 Fase 2: Rendimiento neto minorado."
  - "El rendimiento neto previo se minorará en el importe de los incentivos al empleo y la inversión"
  - "a) Minoración por incentivos al empleo."
  - "Si la diferencia resultase positiva, a ésta se aplicará el coeficiente 0,40"
- `notes` (verbatim): "Fase 2a: minoracion por incentivos al empleo. El rendimiento neto previo se minora en el coeficiente de minoracion (incremento del modulo personal asalariado x 0,40, mas el coeficiente por tramos del numero de unidades restante) multiplicado por el rendimiento anual por unidad del modulo personal asalariado. Cross-checked byte-identical against the AEAT Manual practico de Renta 2024, Parte 1."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hfp-1359-2023.html; operator to re-stamp"

##### Bundled corpus text

> 2.2 Fase 2: Rendimiento neto minorado.
>
> El rendimiento neto previo se minorará en el importe de los incentivos al empleo y la inversión, en la forma que se establece a continuación, dando lugar al rendimiento neto minorado.
>
> a) Minoración por incentivos al empleo.
>
> Para practicar la minoración por incentivos al empleo se tendrá en cuenta lo siguiente:
>
> 1.º Si en el año que se liquida hubiese tenido lugar un incremento del número de personas asalariadas, por comparación al año inmediato anterior, se calculará, en primer lugar, la diferencia entre el número de unidades del módulo «personal asalariado» correspondientes al año y el número de unidades de ese mismo módulo correspondientes al año inmediato anterior. A estos efectos, se tendrán en cuenta exclusivamente las personas asalariadas que se hayan computado en la Fase 1.ª, de acuerdo con lo establecido en la regla 2.ª
>
> Si en el año anterior no se hubiese estado acogido al régimen de estimación objetiva, se tomará como número de unidades correspondientes a dicho año el que hubiese debido tomarse, de acuerdo a las normas contenidas en la regla 2.ª de la Fase anterior.
>
> Si la diferencia resultase positiva, a ésta se aplicará el coeficiente 0,40. El resultado es el coeficiente por incremento del número de personas asalariadas.
>
> Si la diferencia hubiese resultado positiva y, por tanto, hubiese procedido la aplicación del coeficiente 0,40, a dicha diferencia no se le aplicará la tabla de coeficientes por tramos que se señala a continuación.
>
> 2.º Además, a cada uno de los tramos del número de unidades del módulo que a continuación se indica se le aplicarán los coeficientes que se expresan en la siguiente tabla:
>
> Tramo
>
> Coeficiente
>
> Hasta 1,00.
>
> 0,10
>
> Entre 1,01 a 3,00.
>
> 0,15
>
> Entre 3,01 a 5,00.
>
> 0,20
>
> Entre 5,01 a 8,00.
>
> 0,25
>
> Más de 8,00.
>
> 0,30
>
> Para cuantificar la minoración por incentivos al empleo, se procede de la siguiente forma:
>
> – Se suma el coeficiente por incremento del número de personas asalariadas, si procede, y el de la tabla anterior, obteniéndose el coeficiente de minoración.
>
> – Este coeficiente de minoración se multiplica por el «Rendimiento anual por unidad antes de amortización» correspondiente al módulo «personal asalariado». La cantidad anterior se minora del rendimiento neto previo.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a coefficient/rate table (tramos and their corresponding coefficients laid out as table rows rather than in a sentence carrying "por ciento" or "euros" adjacent to the figure) -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2024. 2 casilla(s); 1 construct(s); 1 formula(s); 2 parameter(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-15`.

### Fase 2, minoracion por incentivos a la inversion (instruccion 2.2.b)

#### 6. `orden-hac-1347-2024:instruccion-2-2-b`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1347-2024.html#anexo-ii-instruccion-2-2-b`
- `document_id`: `BOE-A-2024-24949`; `effective_from`: 2025-01-01
- `required_text`:
  - "b) Minoración por incentivos a la inversión."
  - "Serán deducibles las cantidades que, en concepto de amortización del inmovilizado, material o intangible, correspondan a la depreciación efectiva"
  - "El coeficiente de amortización lineal máximo."
- `notes` (verbatim): "Fase 2a: minoracion por incentivos a la inversion. Son deducibles las cantidades que, en concepto de amortizacion del inmovilizado material o intangible afecto a la actividad, correspondan a la depreciacion efectiva, calculada segun la tabla de amortizacion de la propia orden (coeficiente lineal maximo, minimo derivado del periodo maximo, o cualquier coeficiente intermedio). El primer slice del motor no modela un registro de bienes de inversion por elemento; la minoracion se recoge como un importe declarado por el operador, grounded en esta instruccion, y se resta del rendimiento neto previo junto con la minoracion por incentivos al empleo. Cross-checked byte-identical against the AEAT Manual practico de Renta 2025, Parte 1, worked example epigrafe 673.1 (minoracion por incentivos a la inversion 6.050,00 euros, libro registro de bienes de inversion)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1347-2024.html; operator to re-stamp"

##### Bundled corpus text

> b) Minoración por incentivos a la inversión.
>
> Serán deducibles las cantidades que, en concepto de amortización del inmovilizado, material o intangible, correspondan a la depreciación efectiva que sufran los distintos elementos por funcionamiento, uso, disfrute u obsolescencia.
>
> Se considerará que la depreciación es efectiva cuando sea el resultado de aplicar al precio de adquisición o coste de producción del elemento patrimonial del inmovilizado alguno de los siguientes coeficientes:
>
> 1.º El coeficiente de amortización lineal máximo.
>
> 2.º El coeficiente de amortización lineal mínimo que se deriva del período máximo de amortización.
>
> 3.º Cualquier otro coeficiente de amortización lineal comprendido entre los dos anteriormente mencionados.
>
> La tabla de amortización es la siguiente:
>
> Grupo
>
> Descripción
>
> Coeficiente lineal máximo
>
> –
>
> Porcentaje
>
> Período máximo
>
> 1
>
> Edificios y otras construcciones.
>
> 5
>
> 40 años
>
> 2
>
> Útiles, herramientas, equipos para el tratamiento de la información y sistemas y programas informáticos.
>
> 40
>
> 5 años
>
> 3
>
> Elementos de transporte y resto de inmovilizado material.
>
> 25
>
> 8 años
>
> 4
>
> Inmovilizado intangible.
>
> 15
>
> 10 años
>
> Será amortizable el precio de adquisición o coste de producción excluido, en su caso el valor residual.
>
> En las edificaciones, no será amortizable la parte del precio de adquisición correspondiente al valor del suelo el cual, cuando no se conozca, se calculará prorrateando el precio de adquisición entre los valores catastrales del suelo y de la construcción en el año de adquisición.
>
> La amortización se practicará elemento por elemento, si bien cuando se trate de elementos patrimoniales integrados en el mismo Grupo de la Tabla de Amortización, la amortización podrá practicarse sobre el conjunto de ellos, siempre que en todo momento pueda conocerse la parte de la amortización correspondiente a cada elemento patrimonial.
>
> Los elementos patrimoniales de inmovilizado material empezarán a amortizarse desde su puesta en condiciones de funcionamiento y los de inmovilizado intangible desde el momento en que estén en condiciones de producir ingresos.
>
> La vida útil no podrá exceder del período máximo de amortización establecido en la Tabla de Amortización.
>
> En el supuesto de elementos patrimoniales del inmovilizado material que se adquieran usados, el cálculo de la amortización se efectuará sobre el precio de adquisición, hasta el límite resultante de multiplicar por dos la cantidad derivada de aplicar el coeficiente de amortización lineal máximo.
>
> En el supuesto de cesión de uso de bienes con opción de compra o renovación, cuando por las condiciones económicas de la operación no existan dudas razonables de que se ejercitará una u otra opción, será deducible para el cesionario, en concepto de amortización, un importe equivalente a las cuotas de amortización que corresponderían a los citados bienes, aplicando los coeficientes previstos en la Tabla de Amortización, sobre el precio de adquisición o coste de producción del bien.
>
> Los elementos de inmovilizado material nuevos, puestos a disposición del contribuyente en el ejercicio, cuyo valor unitario no exceda de 601,01 euros, podrán amortizarse libremente, hasta el límite de 3.005,06 euros anuales.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, coefficient, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2025. 2 casilla(s); 1 construct(s); 1 formula(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-03`.

#### 7. `orden-hac-1425-2025:instruccion-2-2-b`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1425-2025.html#anexo-ii-instruccion-2-2-b`
- `document_id`: `BOE-A-2025-25272`; `effective_from`: 2026-01-01
- `required_text`:
  - "b) Minoración por incentivos a la inversión."
  - "Serán deducibles las cantidades que, en concepto de amortización del inmovilizado, material o intangible, correspondan a la depreciación efectiva"
  - "El coeficiente de amortización lineal máximo."
- `notes` (verbatim): "Fase 2a: minoracion por incentivos a la inversion. Son deducibles las cantidades que, en concepto de amortizacion del inmovilizado material o intangible afecto a la actividad, correspondan a la depreciacion efectiva, calculada segun la tabla de amortizacion de la propia orden (coeficiente lineal maximo, minimo derivado del periodo maximo, o cualquier coeficiente intermedio). El primer slice del motor no modela un registro de bienes de inversion por elemento; la minoracion se recoge como un importe declarado por el operador, grounded en esta instruccion, y se resta del rendimiento neto previo junto con la minoracion por incentivos al empleo."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1425-2025.html; operator to re-stamp"

##### Bundled corpus text

> b) Minoración por incentivos a la inversión.
>
> Serán deducibles las cantidades que, en concepto de amortización del inmovilizado, material o intangible, correspondan a la depreciación efectiva que sufran los distintos elementos por funcionamiento, uso, disfrute u obsolescencia.
>
> Se considerará que la depreciación es efectiva cuando sea el resultado de aplicar al precio de adquisición o coste de producción del elemento patrimonial del inmovilizado alguno de los siguientes coeficientes:
>
> 1.º El coeficiente de amortización lineal máximo.
>
> 2.º El coeficiente de amortización lineal mínimo que se deriva del período máximo de amortización.
>
> 3.º Cualquier otro coeficiente de amortización lineal comprendido entre los dos anteriormente mencionados.
>
> La tabla de amortización es la siguiente:
>
> Grupo
>
> Descripción
>
> Coeficiente lineal máximo
>
> –
>
> Porcentaje
>
> Período máximo
>
> 1
>
> Edificios y otras construcciones.
>
> 5
>
> 40 años
>
> 2
>
> Útiles, herramientas, equipos para el tratamiento de la información y sistemas y programas informáticos.
>
> 40
>
> 5 años
>
> 3
>
> Elementos de transporte y resto de inmovilizado material.
>
> 25
>
> 8 años
>
> 4
>
> Inmovilizado intangible.
>
> 15
>
> 10 años
>
> Será amortizable el precio de adquisición o coste de producción excluido, en su caso el valor residual.
>
> En las edificaciones, no será amortizable la parte del precio de adquisición correspondiente al valor del suelo el cual, cuando no se conozca, se calculará prorrateando el precio de adquisición entre los valores catastrales del suelo y de la construcción en el año de adquisición.
>
> La amortización se practicará elemento por elemento, si bien cuando se trate de elementos patrimoniales integrados en el mismo Grupo de la Tabla de Amortización, la amortización podrá practicarse sobre el conjunto de ellos, siempre que en todo momento pueda conocerse la parte de la amortización correspondiente a cada elemento patrimonial.
>
> Los elementos patrimoniales de inmovilizado material empezarán a amortizarse desde su puesta en condiciones de funcionamiento y los de inmovilizado intangible desde el momento en que estén en condiciones de producir ingresos.
>
> La vida útil no podrá exceder del período máximo de amortización establecido en la Tabla de Amortización.
>
> En el supuesto de elementos patrimoniales del inmovilizado material que se adquieran usados, el cálculo de la amortización se efectuará sobre el precio de adquisición, hasta el límite resultante de multiplicar por dos la cantidad derivada de aplicar el coeficiente de amortización lineal máximo.
>
> En el supuesto de cesión de uso de bienes con opción de compra o renovación, cuando por las condiciones económicas de la operación no existan dudas razonables de que se ejercitará una u otra opción, será deducible para el cesionario, en concepto de amortización, un importe equivalente a las cuotas de amortización que corresponderían a los citados bienes, aplicando los coeficientes previstos en la Tabla de Amortización, sobre el precio de adquisición o coste de producción del bien.
>
> Los elementos de inmovilizado material nuevos, puestos a disposición del contribuyente en el ejercicio, cuyo valor unitario no exceda de 601,01 euros, podrán amortizarse libremente, hasta el límite de 3.005,06 euros anuales.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, coefficient, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2026. 2 casilla(s); 1 construct(s); 1 formula(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-04`.

#### 8. `orden-hfp-1359-2023:instruccion-2-2-b`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hfp-1359-2023.html#anexo-ii-instruccion-2-2-b`
- `document_id`: `BOE-A-2023-25882`; `effective_from`: 2024-01-01
- `required_text`:
  - "b) Minoración por incentivos a la inversión."
  - "Serán deducibles las cantidades que, en concepto de amortización del inmovilizado, material o intangible, correspondan a la depreciación efectiva"
  - "El coeficiente de amortización lineal máximo."
- `notes` (verbatim): "Fase 2a: minoracion por incentivos a la inversion. Son deducibles las cantidades que, en concepto de amortizacion del inmovilizado material o intangible afecto a la actividad, correspondan a la depreciacion efectiva, calculada segun la tabla de amortizacion de la propia orden (coeficiente lineal maximo, minimo derivado del periodo maximo, o cualquier coeficiente intermedio). El primer slice del motor no modela un registro de bienes de inversion por elemento; la minoracion se recoge como un importe declarado por el operador, grounded en esta instruccion, y se resta del rendimiento neto previo junto con la minoracion por incentivos al empleo."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hfp-1359-2023.html; operator to re-stamp"

##### Bundled corpus text

> b) Minoración por incentivos a la inversión.
>
> Serán deducibles las cantidades que, en concepto de amortización del inmovilizado, material o intangible, correspondan a la depreciación efectiva que sufran los distintos elementos por funcionamiento, uso, disfrute u obsolescencia.
>
> Se considerará que la depreciación es efectiva cuando sea el resultado de aplicar al precio de adquisición o coste de producción del elemento patrimonial del inmovilizado alguno de los siguientes coeficientes:
>
> 1.º El coeficiente de amortización lineal máximo.
>
> 2.º El coeficiente de amortización lineal mínimo que se deriva del período máximo de amortización.
>
> 3.º Cualquier otro coeficiente de amortización lineal comprendido entre los dos anteriormente mencionados.
>
> La tabla de amortización es la siguiente:
>
> Grupo
>
> Descripción
>
> Coeficiente lineal máximo
>
> Período máximo
>
> 1
>
> Edificios y otras construcciones.
>
> 5 %
>
> 40 años
>
> 2
>
> Útiles, herramientas, equipos para el tratamiento de la información y sistemas y programas informáticos.
>
> 40 %
>
> 5 años
>
> 3
>
> Batea.
>
> 10 %
>
> 12 años
>
> 4
>
> Barco.
>
> 10 %
>
> 25 años
>
> 5
>
> Elementos de transporte y resto de inmovilizado material.
>
> 25 %
>
> 8 años
>
> 6
>
> Inmovilizado intangible.
>
> 15 %
>
> 10 años
>
> Será amortizable el precio de adquisición o coste de producción excluido, en su caso el valor residual.
>
> En las edificaciones, no será amortizable la parte del precio de adquisición correspondiente al valor del suelo el cual, cuando no se conozca, se calculará prorrateando el precio de adquisición entre los valores catastrales del suelo y de la construcción en el año de adquisición.
>
> La amortización se practicará elemento por elemento, si bien cuando se trate de elementos patrimoniales integrados en el mismo Grupo de la Tabla de Amortización, la amortización podrá practicarse sobre el conjunto de ellos, siempre que en todo momento pueda conocerse la parte de la amortización correspondiente a cada elemento patrimonial.
>
> Los elementos patrimoniales de inmovilizado material empezarán a amortizarse desde su puesta en condiciones de funcionamiento y los de inmovilizado intangible desde el momento en que estén en condiciones de producir ingresos.
>
> La vida útil no podrá exceder del período máximo de amortización establecido en la Tabla de Amortización.
>
> En el supuesto de elementos patrimoniales del inmovilizado material que se adquieran usados, el cálculo de la amortización se efectuará sobre el precio de adquisición, hasta el límite resultante de multiplicar por dos la cantidad derivada de aplicar el coeficiente de amortización lineal máximo.
>
> En el supuesto de cesión de uso de bienes con opción de compra o renovación, cuando por las condiciones económicas de la operación no existan dudas razonables de que se ejercitará una u otra opción, será deducible para el cesionario, en concepto de amortización, un importe equivalente a las cuotas de amortización que corresponderían a los citados bienes, aplicando los coeficientes previstos en la Tabla de Amortización, sobre el precio de adquisición o coste de producción del bien.
>
> Los elementos de inmovilizado material nuevos, puestos a disposición del contribuyente en el ejercicio, cuyo valor unitario no exceda de 601,01 euros, podrán amortizarse libremente, hasta el límite de 3.005,06 euros anuales.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, coefficient, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2024. 2 casilla(s); 1 construct(s); 1 formula(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-15`.

### Fase 3, indice corrector aplicable (instruccion 2.3.b.1)

#### 9. `orden-hac-1347-2024:anexo-ii-instruccion-2-3-b-1`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1347-2024.html#anexo-ii-instruccion-2-3-b-1`
- `document_id`: `BOE-A-2024-24949`; `effective_from`: 2025-01-01
- `required_text`:
  - "b.1) Índice corrector para empresas de pequeña dimensión:"
  - "Titular persona física."
  - "Sin personal asalariado."
- `notes` (verbatim): "Fase 3a: indice corrector para empresas de pequena dimension. Se aplica el indice que corresponda (0,70/0,75/0,80 segun la poblacion del municipio, o 0,90 si ademas hay personal asalariado hasta 2 trabajadores) cuando concurren todas las circunstancias: titular persona fisica, un solo local, no mas de un vehiculo afecto de hasta 1.000 kg, y sin personal asalariado (salvo el supuesto de hasta 2 trabajadores del indice 0,90). Cross-checked byte-identical against the bundled orden-hac-1347-2024.html (Anexo II, instruccion 2.3.b.1)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1347-2024.html; operator to re-stamp"

##### Bundled corpus text

> b.1) Índice corrector para empresas de pequeña dimensión:
>
> Se aplicará el índice que corresponda, en función de la población en que se desarrolle la actividad, cuando concurran todas y cada una de las circunstancias siguientes:
>
> 1.º Titular persona física.
>
> 2.º Ejercer la actividad en un solo local.
>
> 3.º No disponer de más de un vehículo afecto a la actividad y que éste no supere los 1.000 kilogramos de capacidad de carga.
>
> 4.º Sin personal asalariado.
>
> Población del municipio
>
> Índice
>
> Hasta 2.000 habitantes.
>
> 0,70
>
> De 2.001 hasta 5.000 habitantes.
>
> 0,75
>
> Más de 5.000 habitantes.
>
> 0,80
>
> Cuando, por ejercerse la actividad en varios municipios, exista la posibilidad de aplicar más de uno de los índices anteriores, se aplicará un único índice: el correspondiente al municipio de mayor población.
>
> Cuando concurran las circunstancias señaladas en los números 1.º, 2.º y 3.º del primer párrafo y, además, se ejerza la actividad con personal asalariado, hasta 2 trabajadores, se aplicará el índice 0,90, cualquiera que sea la población del municipio en el que se desarrolla la actividad.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a coefficient/rate table (tramos and their corresponding coefficients laid out as table rows rather than in a sentence carrying "por ciento" or "euros" adjacent to the figure) -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2025. 2 casilla(s); 1 construct(s); 1 formula(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-04`.

#### 10. `orden-hfp-1359-2023:anexo-ii-instruccion-2-3-b-1`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hfp-1359-2023.html#anexo-ii-instruccion-2-3-b-1`
- `document_id`: `BOE-A-2023-25882`; `effective_from`: 2024-01-01
- `required_text`:
  - "b.1) Índice corrector para empresas de pequeña dimensión:"
  - "Titular persona física."
  - "Sin personal asalariado."
- `notes` (verbatim): "Fase 3a: indice corrector para empresas de pequena dimension. Se aplica el indice que corresponda (0,70/0,75/0,80 segun la poblacion del municipio, o 0,90 si ademas hay personal asalariado hasta 2 trabajadores) cuando concurren todas las circunstancias: titular persona fisica, un solo local, no mas de un vehiculo afecto de hasta 1.000 kg, y sin personal asalariado (salvo el supuesto de hasta 2 trabajadores del indice 0,90). Cross-checked byte-identical against the bundled orden-hfp-1359-2023.html (Anexo II, instruccion 2.3.b.1)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hfp-1359-2023.html; operator to re-stamp"

##### Bundled corpus text

> b.1) Índice corrector para empresas de pequeña dimensión:
>
> Se aplicará el índice que corresponda, en función de la población en que se desarrolle la actividad, cuando concurran todas y cada una de las circunstancias siguientes:
>
> 1.º Titular persona física.
>
> 2.º Ejercer la actividad en un solo local.
>
> 3.º No disponer de más de un vehículo afecto a la actividad y que éste no supere los 1.000 kilogramos de capacidad de carga.
>
> 4.º Sin personal asalariado.
>
> Población del municipio
>
> Índice
>
> Hasta 2.000 habitantes.
>
> 0,70
>
> De 2.001 hasta 5.000 habitantes.
>
> 0,75
>
> Más de 5.000 habitantes.
>
> 0,80
>
> Cuando, por ejercerse la actividad en varios municipios, exista la posibilidad de aplicar más de uno de los índices anteriores, se aplicará un único índice: el correspondiente al municipio de mayor población.
>
> Cuando concurran las circunstancias señaladas en los números 1.º, 2.º y 3.º del primer párrafo y, además, se ejerza la actividad con personal asalariado, hasta 2 trabajadores, se aplicará el índice 0,90, cualquiera que sea la población del municipio en el que se desarrolla la actividad.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a coefficient/rate table (tramos and their corresponding coefficients laid out as table rows rather than in a sentence carrying "por ciento" or "euros" adjacent to the figure) -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2024. 2 casilla(s); 1 construct(s); 1 formula(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-15`.

### Fase 3, indice corrector aplicable (instruccion 2.3.b.2)

#### 11. `orden-hac-1347-2024:anexo-ii-instruccion-2-3-b-2`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1347-2024.html#anexo-ii-instruccion-2-3-b-2`
- `document_id`: `BOE-A-2024-24949`; `effective_from`: 2025-01-01
- `required_text`:
  - "b.2) Índice corrector de temporada:"
  - "Tendrán la consideración de actividades de temporada las que habitualmente sólo se desarrollen durante ciertos días del año"
- `notes` (verbatim): "Fase 3a: indice corrector de temporada. Cuando la actividad tenga la consideracion de actividad de temporada (se desarrolla habitualmente solo ciertos dias del ano, continuos o alternos, sin exceder de 180 dias por ano) se aplica el indice 1,50 (hasta 60 dias), 1,35 (de 61 a 120 dias) o 1,25 (de 121 a 180 dias). Incompatible con el indice corrector por inicio de nuevas actividades (b.4). Cross-checked byte-identical against the bundled orden-hac-1347-2024.html (Anexo II, instruccion 2.3.b.2)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1347-2024.html; operator to re-stamp"

##### Bundled corpus text

> b.2) Índice corrector de temporada:
>
> Cuando la actividad tenga la consideración de actividad de temporada, se aplicará el índice de la tabla adjunta que corresponda en función de la duración de la temporada.
>
> Tendrán la consideración de actividades de temporada las que habitualmente sólo se desarrollen durante ciertos días del año, continuos o alternos, siempre que el total no exceda de 180 días por año.
>
> Duración de la temporada
>
> Índice
>
> Hasta 60 días.
>
> 1,50
>
> De 61 a 120 días.
>
> 1,35
>
> De 121 a 180 días.
>
> 1,25

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a coefficient/rate table (tramos and their corresponding coefficients laid out as table rows rather than in a sentence carrying "por ciento" or "euros" adjacent to the figure) -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2025. 2 casilla(s); 1 construct(s); 1 formula(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-04`.

#### 12. `orden-hfp-1359-2023:anexo-ii-instruccion-2-3-b-2`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hfp-1359-2023.html#anexo-ii-instruccion-2-3-b-2`
- `document_id`: `BOE-A-2023-25882`; `effective_from`: 2024-01-01
- `required_text`:
  - "b.2) Índice corrector de temporada:"
  - "Tendrán la consideración de actividades de temporada las que habitualmente sólo se desarrollen durante ciertos días del año"
- `notes` (verbatim): "Fase 3a: indice corrector de temporada. Cuando la actividad tenga la consideracion de actividad de temporada (se desarrolla habitualmente solo ciertos dias del ano, continuos o alternos, sin exceder de 180 dias por ano) se aplica el indice 1,50 (hasta 60 dias), 1,35 (de 61 a 120 dias) o 1,25 (de 121 a 180 dias). Incompatible con el indice corrector por inicio de nuevas actividades (b.4). Cross-checked byte-identical against the bundled orden-hfp-1359-2023.html (Anexo II, instruccion 2.3.b.2)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hfp-1359-2023.html; operator to re-stamp"

##### Bundled corpus text

> b.2) Índice corrector de temporada:
>
> Cuando la actividad tenga la consideración de actividad de temporada, se aplicará el índice de la tabla adjunta que corresponda en función de la duración de la temporada.
>
> Tendrán la consideración de actividades de temporada las que habitualmente sólo se desarrollen durante ciertos días del año, continuos o alternos, siempre que el total no exceda de 180 días por año.
>
> Duración de la temporada
>
> Índice
>
> Hasta 60 días.
>
> 1,50
>
> De 61 a 120 días.
>
> 1,35
>
> De 121 a 180 días.
>
> 1,25

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a coefficient/rate table (tramos and their corresponding coefficients laid out as table rows rather than in a sentence carrying "por ciento" or "euros" adjacent to the figure) -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2024. 2 casilla(s); 1 construct(s); 1 formula(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-15`.

### Fase 3, indice corrector aplicable (instruccion 2.3.b.3)

#### 13. `orden-hac-1347-2024:instruccion-2-3-b-3`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1347-2024.html#anexo-ii-instruccion-2-3-b-3`
- `document_id`: `BOE-A-2024-24949`; `effective_from`: 2025-01-01
- `required_text`:
  - "b.3) Índice corrector de exceso:"
  - "al exceso sobre dichas cuantías se le aplicará el índice 1,30"
- `notes` (verbatim): "Fase 3a: indice corrector de exceso. Cuando el rendimiento neto minorado supera la cuantia tabulada para la actividad, al exceso sobre dicha cuantia se le aplica el indice 1,30. Cross-checked byte-identical against the AEAT Manual practico de Renta 2025, Parte 1, worked example epigrafe 673.1 (cuantia 30.586,03 euros)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1347-2024.html; operator to re-stamp"

##### Bundled corpus text

> b.3) Índice corrector de exceso:
>
> Cuando el rendimiento neto minorado, o en su caso, rectificado por aplicación de los índices anteriores de las actividades que a continuación se mencionan resulte superior a las cuantías que se señalan en cada caso, al exceso sobre dichas cuantías se le aplicará el índice 1,30.
>
> Actividad económica
>
> Cuantía
>
> –
>
> Euros
>
> Industrias del pan y de la bollería.
>
> 41.602,30
>
> Industrias de bollería, pastelería y galletas.
>
> 33.760,53
>
> Industrias de elaboración de masas fritas.
>
> 19.670,55
>
> Elaboración de patatas fritas, palomitas de maíz y similares.
>
> 19.670,55
>
> Comercio al por menor de frutas, verduras, hortalizas y tubérculos.
>
> 16.867,67
>
> Comercio al por menor de carne, despojos, de productos y derivados cárnicos elaborados.
>
> 21.635,71
>
> Comercio al por menor de huevos, aves, conejos de granja, caza; y de productos derivados de los mismos.
>
> 20.136,65
>
> Comercio al por menor en casquerías, de vísceras y despojos procedentes de animales de abasto, frescos y congelados.
>
> 16.237,81
>
> Comercio al por menor de pescados y otros productos de la pesca y de la acuicultura y de caracoles.
>
> 24.551,97
>
> Comercio al por menor de pan, pastelería, confitería y similares y de leche y productos lácteos.
>
> 43.605,26
>
> Despachos de pan, panes especiales y bollería.
>
> 42.925,01
>
> Comercio al por menor de productos de pastelería, bollería y confitería.
>
> 33.760,53
>
> Comercio al por menor de masas fritas, con o sin coberturas o rellenos, patatas fritas, productos de aperitivo, frutos secos, golosinas, preparados de chocolate y bebidas refrescantes.
>
> 19.670,55
>
> Comercio al por menor de cualquier clase de productos alimenticios y de bebidas en establecimientos con vendedor.
>
> 15.822,10
>
> Comercio al por menor de cualquier clase de productos alimenticios y de bebidas en régimen de autoservicio o mixto en establecimientos cuya sala de ventas tenga una superficie inferior a 400 metros cuadrados.
>
> 25.219,62
>
> Comercio al por menor de productos textiles, confecciones para el hogar, alfombras y similares y artículos de tapicería.
>
> 23.638,67
>
> Comercio al por menor de toda clase de prendas para el vestido y tocado.
>
> 24.848,00
>
> Comercio al por menor de lencería, corsetería y prendas especiales.
>
> 19.626,46
>
> Comercio al por menor de artículos de mercería y paquetería.
>
> 14.862,05
>
> Comercio al por menor de calzado, artículos de piel e imitación o productos sustitutivos, cinturones, carteras, bolsos, maletas y artículos de viaje en general.
>
> 24.306,32
>
> Comercio al por menor de productos de droguería, perfumería y cosmética, limpieza, pinturas, barnices, disolventes, papeles y otros productos para la decoración y de productos químicos, y de artículos para la higiene y el aseo personal.
>
> 25.333,00
>
> Comercio al por menor de muebles.
>
> 30.718,31
>
> Comercio al por menor de material y aparatos eléctricos, electrónicos, electrodomésticos y otros aparatos de uso doméstico accionados por otro tipo de energía distinta de la eléctrica, así como muebles de cocina.
>
> 26.189,61
>
> Comercio al por menor de artículos de menaje, ferretería, adorno, regalo, o reclamo (incluyendo bisutería y pequeños electrodomésticos).
>
> 24.470,09
>
> Comercio al por menor de materiales de construcción, artículos y mobiliario de saneamiento, puertas, ventanas, persianas, etc.
>
> 26.454,15
>
> Comercio al por menor de otros artículos para el equipamiento del hogar n.c.o.p.
>
> 32.765,35
>
> Comercio al por menor de accesorios y piezas de recambio para vehículos terrestres.
>
> 32.815,74
>
> Comercio al por menor de toda clase de maquinaria (excepto aparatos del hogar, de oficina, médicos, ortopédicos, ópticos y fotográficos).
>
> 31.367,06
>
> Comercio al por menor de cubiertas, bandas o bandajes y cámaras de aire para toda clase de vehículos.
>
> 26.970,63
>
> Comercio al por menor de muebles de oficina y de máquinas y equipos de oficina.
>
> 30.718,31
>
> Comercio al por menor de aparatos e instrumentos médicos, ortopédicos, ópticos y fotográficos.
>
> 35.524,14
>
> Comercio al por menor de libros, periódicos, artículos de papelería y escritorio y artículos de dibujo y bellas artes, excepto en quioscos situados en la vía pública.
>
> 25.207,02
>
> Comercio al por menor de prensa, revistas y libros en quioscos situados en la vía pública.
>
> 28.860,22
>
> Comercio al por menor de juguetes, artículos de deporte, prendas deportivas de vestido, calzado y tocado, armas, cartuchería y artículos de pirotecnia.
>
> 24.948,78
>
> Comercio al por menor de semillas, abonos, flores y plantas y pequeños animales.
>
> 23.978,80
>
> Comercio al por menor de toda clase de artículos, incluyendo alimentación y bebidas, en establecimientos distintos de los especificados en el grupo 661 y en el epígrafe 662.1.
>
> 16.395,27
>
> Comercio al por menor fuera de un establecimiento comercial permanente de productos alimenticios, incluso bebidas y helados.
>
> 14.379,72
>
> Comercio al por menor fuera de un establecimiento comercial permanente de artículos textiles y de confección.
>
> 19.059,58
>
> Comercio al por menor fuera de un establecimiento comercial permanente de calzado, pieles y artículos de cuero.
>
> 17.081,82
>
> Comercio al por menor fuera de un establecimiento comercial permanente de artículos de droguería y cosméticos y de productos químicos en general.
>
> 16.886,56
>
> Comercio al por menor fuera de un establecimiento comercial permanente de otras clases de mercancías n.c.o.p.
>
> 18.354,14
>
> Restaurantes de dos tenedores.
>
> 51.617,08
>
> Restaurantes de un tenedor.
>
> 38.081,38
>
> Cafeterías.
>
> 39.070,26
>
> Cafés y bares de categoría especial.
>
> 30.586,03
>
> Otros cafés y bares.
>
> 19.084,78
>
> Servicios en quioscos, cajones, barracas u otros locales análogos.
>
> 16.596,83
>
> Servicios en chocolaterías, heladerías y horchaterías.
>
> 25.528,25
>
> Servicio de hospedaje en hoteles y moteles de una y dos estrellas.
>
> 61.512,19
>
> Servicio de hospedaje en hostales y pensiones.
>
> 32.840,94
>
> Servicio de hospedaje en fondas y casas de huéspedes.
>
> 16.256,70
>
> Reparación de artículos eléctricos para el hogar.
>
> 21.585,33
>
> Reparación de vehículos automóviles, bicicletas y otros vehículos.
>
> 33.729,04
>
> Reparación de calzado.
>
> 16.552,74
>
> Reparación de otros bienes de consumo n.c.o.p. (excepto reparación de calzado, restauración de obras de arte, muebles antigüedades e instrumentos musicales).
>
> 24.803,91
>
> Reparación de maquinaria industrial.
>
> 30.352,99
>
> Otras reparaciones n.c.o.p.
>
> 23.607,18
>
> Transporte urbano colectivo y de viajeros por carretera.
>
> 35.196,62
>
> Transporte de mercancías por carretera.
>
> 33.640,86
>
> Engrase y lavado de vehículos.
>
> 28.280,74
>
> Servicios de mudanzas.
>
> 33.640,86
>
> Transporte de mensajería y recadería, cuando la actividad se realice exclusivamente con medios de transporte propios.
>
> 33.640,86
>
> Enseñanza de conducción de vehículos terrestres, acuáticos, aeronáuticos, etc.
>
> 47.233,25
>
> Otras actividades de enseñanza, tales como idiomas, corte y confección, mecanografía, taquigrafía, preparación de exámenes y oposiciones y similares n.c.o.p.
>
> 33.697,55
>
> Escuelas y servicios de perfeccionamiento del deporte.
>
> 37.067,30
>
> Tinte, limpieza en seco, lavado y planchado de ropas hechas y de prendas y artículos del hogar usados.
>
> 37.224,77
>
> Servicios de peluquería de señora y caballero.
>
> 18.051,81
>
> Salones e institutos de belleza.
>
> 26.945,44
>
> Servicios de copias de documentos con máquinas fotocopiadoras.
>
> 24.192,95

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, coefficient, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2025. 1 casilla(s); 1 construct(s); 1 formula(s); 2 parameter(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-03`.

#### 14. `orden-hac-1425-2025:instruccion-2-3-b-3`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1425-2025.html#anexo-ii-instruccion-2-3-b-3`
- `document_id`: `BOE-A-2025-25272`; `effective_from`: 2026-01-01
- `required_text`:
  - "b.3) Índice corrector de exceso:"
  - "al exceso sobre dichas cuantías se le aplicará el índice 1,30"
- `notes` (verbatim): "Fase 3a: indice corrector de exceso. Cuando el rendimiento neto minorado supera la cuantia tabulada para la actividad, al exceso sobre dicha cuantia se le aplica el indice 1,30. Cross-checked byte-identical against the 2025 instruccion (orden-hac-1347-2024:instruccion-2-3-b-3): same indice 1,30 and per-actividad cuantias for every currently tabled epigrafe (972.1, 721.2, 722, 671.4, 671.5, 672.1, 673.1, 673.2)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1425-2025.html; operator to re-stamp"

##### Bundled corpus text

> b.3) Índice corrector de exceso:
>
> Cuando el rendimiento neto minorado, o en su caso, rectificado por aplicación de los índices anteriores de las actividades que a continuación se mencionan resulte superior a las cuantías que se señalan en cada caso, al exceso sobre dichas cuantías se le aplicará el índice 1,30.
>
> Actividad económica
>
> Cuantía
>
> –
>
> Euros
>
> Industrias del pan y de la bollería.
>
> 41.602,30
>
> Industrias de bollería, pastelería y galletas.
>
> 33.760,53
>
> Industrias de elaboración de masas fritas.
>
> 19.670,55
>
> Elaboración de patatas fritas, palomitas de maíz y similares.
>
> 19.670,55
>
> Comercio al por menor de frutas, verduras, hortalizas y tubérculos.
>
> 16.867,67
>
> Comercio al por menor de carne, despojos, de productos y derivados cárnicos elaborados.
>
> 21.635,71
>
> Comercio al por menor de huevos, aves, conejos de granja, caza; y de productos derivados de los mismos.
>
> 20.136,65
>
> Comercio al por menor en casquerías, de vísceras y despojos procedentes de animales de abasto, frescos y congelados.
>
> 16.237,81
>
> Comercio al por menor de pescados y otros productos de la pesca y de la acuicultura y de caracoles.
>
> 24.551,97
>
> Comercio al por menor de pan, pastelería, confitería y similares y de leche y productos lácteos.
>
> 43.605,26
>
> Despachos de pan, panes especiales y bollería.
>
> 42.925,01
>
> Comercio al por menor de productos de pastelería, bollería y confitería.
>
> 33.760,53
>
> Comercio al por menor de masas fritas, con o sin coberturas o rellenos, patatas fritas, productos de aperitivo, frutos secos, golosinas, preparados de chocolate y bebidas refrescantes.
>
> 19.670,55
>
> Comercio al por menor de cualquier clase de productos alimenticios y de bebidas en establecimientos con vendedor.
>
> 15.822,10
>
> Comercio al por menor de cualquier clase de productos alimenticios y de bebidas en régimen de autoservicio o mixto en establecimientos cuya sala de ventas tenga una superficie inferior a 400 metros cuadrados.
>
> 25.219,62
>
> Comercio al por menor de productos textiles, confecciones para el hogar, alfombras y similares y artículos de tapicería.
>
> 23.638,67
>
> Comercio al por menor de toda clase de prendas para el vestido y tocado.
>
> 24.848,00
>
> Comercio al por menor de lencería, corsetería y prendas especiales.
>
> 19.626,46
>
> Comercio al por menor de artículos de mercería y paquetería.
>
> 14.862,05
>
> Comercio al por menor de calzado, artículos de piel e imitación o productos sustitutivos, cinturones, carteras, bolsos, maletas y artículos de viaje en general.
>
> 24.306,32
>
> Comercio al por menor de productos de droguería, perfumería y cosmética, limpieza, pinturas, barnices, disolventes, papeles y otros productos para la decoración y de productos químicos, y de artículos para la higiene y el aseo personal.
>
> 25.333,00
>
> Comercio al por menor de muebles.
>
> 30.718,31
>
> Comercio al por menor de material y aparatos eléctricos, electrónicos, electrodomésticos y otros aparatos de uso doméstico accionados por otro tipo de energía distinta de la eléctrica, así como muebles de cocina.
>
> 26.189,61
>
> Comercio al por menor de artículos de menaje, ferretería, adorno, regalo, o reclamo (incluyendo bisutería y pequeños electrodomésticos).
>
> 24.470,09
>
> Comercio al por menor de materiales de construcción, artículos y mobiliario de saneamiento, puertas, ventanas, persianas, etc.
>
> 26.454,15
>
> Comercio al por menor de otros artículos para el equipamiento del hogar n.c.o.p.
>
> 32.765,35
>
> Comercio al por menor de accesorios y piezas de recambio para vehículos terrestres.
>
> 32.815,74
>
> Comercio al por menor de toda clase de maquinaria (excepto aparatos del hogar, de oficina, médicos, ortopédicos, ópticos y fotográficos).
>
> 31.367,06
>
> Comercio al por menor de cubiertas, bandas o bandajes y cámaras de aire para toda clase de vehículos.
>
> 26.970,63
>
> Comercio al por menor de muebles de oficina y de máquinas y equipos de oficina.
>
> 30.718,31
>
> Comercio al por menor de aparatos e instrumentos médicos, ortopédicos, ópticos y fotográficos.
>
> 35.524,14
>
> Comercio al por menor de libros, periódicos, artículos de papelería y escritorio y artículos de dibujo y bellas artes, excepto en quioscos situados en la vía pública.
>
> 25.207,02
>
> Comercio al por menor de prensa, revistas y libros en quioscos situados en la vía pública.
>
> 28.860,22
>
> Comercio al por menor de juguetes, artículos de deporte, prendas deportivas de vestido, calzado y tocado, armas, cartuchería y artículos de pirotecnia.
>
> 24.948,78
>
> Comercio al por menor de semillas, abonos, flores y plantas y pequeños animales.
>
> 23.978,80
>
> Comercio al por menor de toda clase de artículos, incluyendo alimentación y bebidas, en establecimientos distintos de los especificados en el grupo 661 y en el epígrafe 662.1.
>
> 16.395,27
>
> Comercio al por menor fuera de un establecimiento comercial permanente de productos alimenticios, incluso bebidas y helados.
>
> 14.379,72
>
> Comercio al por menor fuera de un establecimiento comercial permanente de artículos textiles y de confección.
>
> 19.059,58
>
> Comercio al por menor fuera de un establecimiento comercial permanente de calzado, pieles y artículos de cuero.
>
> 17.081,82
>
> Comercio al por menor fuera de un establecimiento comercial permanente de artículos de droguería y cosméticos y de productos químicos en general.
>
> 16.886,56
>
> Comercio al por menor fuera de un establecimiento comercial permanente de otras clases de mercancías n.c.o.p.
>
> 18.354,14
>
> Restaurantes de dos tenedores.
>
> 51.617,08
>
> Restaurantes de un tenedor.
>
> 38.081,38
>
> Cafeterías.
>
> 39.070,26
>
> Cafés y bares de categoría especial.
>
> 30.586,03
>
> Otros cafés y bares.
>
> 19.084,78
>
> Servicios en quioscos, cajones, barracas u otros locales análogos.
>
> 16.596,83
>
> Servicios en chocolaterías, heladerías y horchaterías.
>
> 25.528,25
>
> Servicio de hospedaje en hoteles y moteles de una y dos estrellas.
>
> 61.512,19
>
> Servicio de hospedaje en hostales y pensiones.
>
> 32.840,94
>
> Servicio de hospedaje en fondas y casas de huéspedes.
>
> 16.256,70
>
> Reparación de artículos eléctricos para el hogar.
>
> 21.585,33
>
> Reparación de vehículos automóviles, bicicletas y otros vehículos.
>
> 33.729,04
>
> Reparación de calzado.
>
> 16.552,74
>
> Reparación de otros bienes de consumo n.c.o.p. (excepto reparación de calzado, restauración de obras de arte, muebles antigüedades e instrumentos musicales).
>
> 24.803,91
>
> Reparación de maquinaria industrial.
>
> 30.352,99
>
> Otras reparaciones n.c.o.p.
>
> 23.607,18
>
> Transporte urbano colectivo y de viajeros por carretera.
>
> 35.196,62
>
> Transporte de mercancías por carretera.
>
> 33.640,86
>
> Engrase y lavado de vehículos.
>
> 28.280,74
>
> Servicios de mudanzas.
>
> 33.640,86
>
> Transporte de mensajería y recadería, cuando la actividad se realice exclusivamente con medios de transporte propios.
>
> 33.640,86
>
> Enseñanza de conducción de vehículos terrestres, acuáticos, aeronáuticos, etc.
>
> 47.233,25
>
> Otras actividades de enseñanza, tales como idiomas, corte y confección, mecanografía, taquigrafía, preparación de exámenes y oposiciones y similares n.c.o.p.
>
> 33.697,55
>
> Escuelas y servicios de perfeccionamiento del deporte.
>
> 37.067,30
>
> Tinte, limpieza en seco, lavado y planchado de ropas hechas y de prendas y artículos del hogar usados.
>
> 37.224,77
>
> Servicios de peluquería de señora y caballero.
>
> 18.051,81
>
> Salones e institutos de belleza.
>
> 26.945,44
>
> Servicios de copias de documentos con máquinas fotocopiadoras.
>
> 24.192,95

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a coefficient/rate table (tramos and their corresponding coefficients laid out as table rows rather than in a sentence carrying "por ciento" or "euros" adjacent to the figure) -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2026. 1 casilla(s); 1 construct(s); 1 formula(s); 2 parameter(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-04`.

#### 15. `orden-hfp-1359-2023:instruccion-2-3-b-3`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hfp-1359-2023.html#anexo-ii-instruccion-2-3-b-3`
- `document_id`: `BOE-A-2023-25882`; `effective_from`: 2024-01-01
- `required_text`:
  - "b.3) Índice corrector de exceso:"
  - "al exceso sobre dichas cuantías se le aplicará el índice 1,30"
- `notes` (verbatim): "Fase 3a: indice corrector de exceso. Cuando el rendimiento neto minorado supera la cuantia tabulada para la actividad, al exceso sobre dicha cuantia se le aplica el indice 1,30. Cross-checked byte-identical against the AEAT Manual practico de Renta 2024, Parte 1 (cuantia 30.586,03 euros, epigrafe 673.1)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hfp-1359-2023.html; operator to re-stamp"

##### Bundled corpus text

> b.3) Índice corrector de exceso:
>
> Cuando el rendimiento neto minorado, o en su caso, rectificado por aplicación de los índices anteriores de las actividades que a continuación se mencionan resulte superior a las cuantías que se señalan en cada caso, al exceso sobre dichas cuantías se le aplicará el índice 1,30.
>
> Actividad económica
>
> Cuantía
>
> Euros
>
> Producción de mejillón en batea.
>
> 40.000,00
>
> Industrias del pan y de la bollería.
>
> 41.602,30
>
> Industrias de bollería, pastelería y galletas.
>
> 33.760,53
>
> Industrias de elaboración de masas fritas.
>
> 19.670,55
>
> Elaboración de patatas fritas, palomitas de maíz y similares.
>
> 19.670,55
>
> Comercio al por menor de frutas, verduras, hortalizas y tubérculos.
>
> 16.867,67
>
> Comercio al por menor de carne, despojos, de productos y derivados cárnicos elaborados.
>
> 21.635,71
>
> Comercio al por menor de huevos, aves, conejos de granja, caza; y de productos derivados de los mismos.
>
> 20.136,65
>
> Comercio al por menor en casquerías, de vísceras y despojos procedentes de animales de abasto, frescos y congelados.
>
> 16.237,81
>
> Comercio al por menor de pescados y otros productos de la pesca y de la acuicultura y de caracoles.
>
> 24.551,97
>
> Comercio al por menor de pan, pastelería, confitería y similares y de leche y productos lácteos.
>
> 43.605,26
>
> Despachos de pan, panes especiales y bollería.
>
> 42.925,01
>
> Comercio al por menor de productos de pastelería, bollería y confitería.
>
> 33.760,53
>
> Comercio al por menor de masas fritas, con o sin coberturas o rellenos, patatas fritas, productos de aperitivo, frutos secos, golosinas, preparados de chocolate y bebidas refrescantes.
>
> 19.670,55
>
> Comercio al por menor de cualquier clase de productos alimenticios y de bebidas en establecimientos con vendedor.
>
> 15.822,10
>
> Comercio al por menor de cualquier clase de productos alimenticios y de bebidas en régimen de autoservicio o mixto en establecimientos cuya sala de ventas tenga una superficie inferior a 400 metros cuadrados.
>
> 25.219,62
>
> Comercio al por menor de productos textiles, confecciones para el hogar, alfombras y similares y artículos de tapicería.
>
> 23.638,67
>
> Comercio al por menor de toda clase de prendas para el vestido y tocado.
>
> 24.848,00
>
> Comercio al por menor de lencería, corsetería y prendas especiales.
>
> 19.626,46
>
> Comercio al por menor de artículos de mercería y paquetería.
>
> 14.862,05
>
> Comercio al por menor de calzado, artículos de piel e imitación o productos sustitutivos, cinturones, carteras, bolsos, maletas y artículos de viaje en general.
>
> 24.306,32
>
> Comercio al por menor de productos de droguería, perfumería y cosmética, limpieza, pinturas, barnices, disolventes, papeles y otros productos para la decoración y de productos químicos, y de artículos para la higiene y el aseo personal.
>
> 25.333,00
>
> Comercio al por menor de muebles.
>
> 30.718,31
>
> Comercio al por menor de material y aparatos eléctricos, electrónicos, electrodomésticos y otros aparatos de uso doméstico accionados por otro tipo de energía distinta de la eléctrica, así como muebles de cocina.
>
> 26.189,61
>
> Comercio al por menor de artículos de menaje, ferretería, adorno, regalo, o reclamo (incluyendo bisutería y pequeños electrodomésticos).
>
> 24.470,09
>
> Comercio al por menor de materiales de construcción, artículos y mobiliario de saneamiento, puertas, ventanas, persianas, etc.
>
> 26.454,15
>
> Comercio al por menor de otros artículos para el equipamiento del hogar n.c.o.p.
>
> 32.765,35
>
> Comercio al por menor de accesorios y piezas de recambio para vehículos terrestres.
>
> 32.815,74
>
> Comercio al por menor de toda clase de maquinaria (excepto aparatos del hogar, de oficina, médicos, ortopédicos, ópticos y fotográficos).
>
> 31.367,06
>
> Comercio al por menor de cubiertas, bandas o bandajes y cámaras de aire para toda clase de vehículos.
>
> 26.970,63
>
> Comercio al por menor de muebles de oficina y de máquinas y equipos de oficina.
>
> 30.718,31
>
> Comercio al por menor de aparatos e instrumentos médicos, ortopédicos, ópticos y fotográficos.
>
> 35.524,14
>
> Comercio al por menor de libros, periódicos, artículos de papelería y escritorio y artículos de dibujo y bellas artes, excepto en quioscos situados en la vía pública.
>
> 25.207,02
>
> Comercio al por menor de prensa, revistas y libros en quioscos situados en la vía pública.
>
> 28.860,22
>
> Comercio al por menor de juguetes, artículos de deporte, prendas deportivas de vestido, calzado y tocado, armas, cartuchería y artículos de pirotecnia.
>
> 24.948,78
>
> Comercio al por menor de semillas, abonos, flores y plantas y pequeños animales.
>
> 23.978,80
>
> Comercio al por menor de toda clase de artículos, incluyendo alimentación y bebidas, en establecimientos distintos de los especificados en el grupo 661 y en el epígrafe 662.1.
>
> 16.395,27
>
> Comercio al por menor fuera de un establecimiento comercial permanente de productos alimenticios, incluso bebidas y helados.
>
> 14.379,72
>
> Comercio al por menor fuera de un establecimiento comercial permanente de artículos textiles y de confección.
>
> 19.059,58
>
> Comercio al por menor fuera de un establecimiento comercial permanente de calzado, pieles y artículos de cuero.
>
> 17.081,82
>
> Comercio al por menor fuera de un establecimiento comercial permanente de artículos de droguería y cosméticos y de productos químicos en general.
>
> 16.886,56
>
> Comercio al por menor fuera de un establecimiento comercial permanente de otras clases de mercancías n.c.o.p.
>
> 18.354,14
>
> Restaurantes de dos tenedores.
>
> 51.617,08
>
> Restaurantes de un tenedor.
>
> 38.081,38
>
> Cafeterías.
>
> 39.070,26
>
> Cafés y bares de categoría especial.
>
> 30.586,03
>
> Otros cafés y bares.
>
> 19.084,78
>
> Servicios en quioscos, cajones, barracas u otros locales análogos.
>
> 16.596,83
>
> Servicios en chocolaterías, heladerías y horchaterías.
>
> 25.528,25
>
> Servicio de hospedaje en hoteles y moteles de una y dos estrellas.
>
> 61.512,19
>
> Servicio de hospedaje en hostales y pensiones.
>
> 32.840,94
>
> Servicio de hospedaje en fondas y casas de huéspedes.
>
> 16.256,70
>
> Reparación de artículos eléctricos para el hogar.
>
> 21.585,33
>
> Reparación de vehículos automóviles, bicicletas y otros vehículos.
>
> 33.729,04
>
> Reparación de calzado.
>
> 16.552,74
>
> Reparación de otros bienes de consumo n.c.o.p. (excepto reparación de calzado, restauración de obras de arte, muebles antigüedades e instrumentos musicales).
>
> 24.803,91
>
> Reparación de maquinaria industrial.
>
> 30.352,99
>
> Otras reparaciones n.c.o.p.
>
> 23.607,18
>
> Transporte urbano colectivo y de viajeros por carretera.
>
> 35.196,62
>
> Transporte de mercancías por carretera.
>
> 33.640,86
>
> Engrase y lavado de vehículos.
>
> 28.280,74
>
> Servicios de mudanzas.
>
> 33.640,86
>
> Transporte de mensajería y recadería, cuando la actividad se realice exclusivamente con medios de transporte propios.
>
> 33.640,86
>
> Enseñanza de conducción de vehículos terrestres, acuáticos, aeronáuticos, etc.
>
> 47.233,25
>
> Otras actividades de enseñanza, tales como idiomas, corte y confección, mecanografía, taquigrafía, preparación de exámenes y oposiciones y similares n.c.o.p.
>
> 33.697,55
>
> Escuelas y servicios de perfeccionamiento del deporte.
>
> 37.067,30
>
> Tinte, limpieza en seco, lavado y planchado de ropas hechas y de prendas y artículos del hogar usados.
>
> 37.224,77
>
> Servicios de peluquería de señora y caballero.
>
> 18.051,81
>
> Salones e institutos de belleza.
>
> 26.945,44
>
> Servicios de copias de documentos con máquinas fotocopiadoras.
>
> 24.192,95

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, coefficient, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2024. 1 casilla(s); 1 construct(s); 1 formula(s); 2 parameter(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-15`.

### Fase 3, indice corrector aplicable (instruccion 2.3.b.4)

#### 16. `orden-hac-1347-2024:anexo-ii-instruccion-2-3-b-4`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1347-2024.html#anexo-ii-instruccion-2-3-b-4`
- `document_id`: `BOE-A-2024-24949`; `effective_from`: 2025-01-01
- `required_text`:
  - "b.4) Índice corrector por inicio de nuevas actividades."
  - "Que se trate de nuevas actividades cuyo ejercicio se inicie a partir del 1 de enero de 2024."
- `notes` (verbatim): "Fase 3a: indice corrector por inicio de nuevas actividades. El contribuyente que inicie una nueva actividad a partir del 1 de enero de 2024, que no sea de temporada, no ejercida previamente bajo otra titularidad, y realizada en local exclusivo, aplica el indice 0,80 (primer ejercicio) / 0,90 (segundo ejercicio), o 0,60 / 0,70 si el contribuyente tiene una discapacidad de grado igual o superior al 33 por ciento. Incompatible con el indice corrector de temporada (b.2). Cross-checked byte-identical against the bundled orden-hac-1347-2024.html (Anexo II, instruccion 2.3.b.4)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1347-2024.html; operator to re-stamp"

##### Bundled corpus text

> b.4) Índice corrector por inicio de nuevas actividades.
>
> El contribuyente que inicie nuevas actividades concurriendo las siguientes circunstancias:
>
> – Que se trate de nuevas actividades cuyo ejercicio se inicie a partir del 1 de enero de 2024.
>
> – Que no se trate de actividades de temporada.
>
> – Que no se hayan ejercido anteriormente bajo otra titularidad o calificación.
>
> – Que se realicen en local o establecimiento dedicados exclusivamente a dicha actividad, con total separación del resto de actividades empresariales o profesionales que, en su caso, pudiera realizar el contribuyente.
>
> Tendrá derecho a aplicar los siguientes índices correctores:
>
> Ejercicio
>
> Índice
>
> Primero.
>
> 0,80
>
> Segundo.
>
> 0,90
>
> Cuando el contribuyente sea una persona con discapacidad, con grado de discapacidad igual o superior al 33 %, los índices correctores aplicables serán:
>
> Ejercicio
>
> Índice
>
> Primero.
>
> 0,60
>
> Segundo.
>
> 0,70

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, coefficient, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2025. 2 casilla(s); 1 construct(s); 1 formula(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-04`.

#### 17. `orden-hfp-1359-2023:anexo-ii-instruccion-2-3-b-4`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hfp-1359-2023.html#anexo-ii-instruccion-2-3-b-4`
- `document_id`: `BOE-A-2023-25882`; `effective_from`: 2024-01-01
- `required_text`:
  - "b.4) Índice corrector por inicio de nuevas actividades."
  - "Que se trate de nuevas actividades cuyo ejercicio se inicie a partir del 1 de enero de 2023."
- `notes` (verbatim): "Fase 3a: indice corrector por inicio de nuevas actividades. El contribuyente que inicie una nueva actividad a partir del 1 de enero de 2023, que no sea de temporada, no ejercida previamente bajo otra titularidad, y realizada en local exclusivo, aplica el indice 0,80 (primer ejercicio) / 0,90 (segundo ejercicio), o 0,60 / 0,70 si el contribuyente tiene una discapacidad de grado igual o superior al 33 por ciento. Incompatible con el indice corrector de temporada (b.2). Cross-checked byte-identical against the bundled orden-hfp-1359-2023.html (Anexo II, instruccion 2.3.b.4)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hfp-1359-2023.html; operator to re-stamp"

##### Bundled corpus text

> b.4) Índice corrector por inicio de nuevas actividades.
>
> El contribuyente que inicie nuevas actividades concurriendo las siguientes circunstancias:
>
> – Que se trate de nuevas actividades cuyo ejercicio se inicie a partir del 1 de enero de 2023.
>
> – Que no se trate de actividades de temporada.
>
> – Que no se hayan ejercido anteriormente bajo otra titularidad o calificación.
>
> – Que se realicen en local o establecimiento dedicados exclusivamente a dicha actividad, con total separación del resto de actividades empresariales o profesionales que, en su caso, pudiera realizar el contribuyente.
>
> Tendrá derecho a aplicar los siguientes índices correctores:
>
> Ejercicio
>
> Índice
>
> Primero.
>
> 0,80
>
> Segundo.
>
> 0,90
>
> Cuando el contribuyente sea una persona con discapacidad, con grado de discapacidad igual o superior al 33 %, los índices correctores aplicables serán:
>
> Ejercicio
>
> Índice
>
> Primero.
>
> 0,60
>
> Segundo.
>
> 0,70

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, coefficient, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2024. 2 casilla(s); 1 construct(s); 1 formula(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-15`.

### Fase 3, incompatibilidad entre indices correctores (instruccion 2.3)

#### 18. `orden-hac-1347-2024:anexo-ii-instruccion-2-3-incompatibilidades`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1347-2024.html#anexo-ii-instruccion-2-3-incompatibilidades`
- `document_id`: `BOE-A-2024-24949`; `effective_from`: 2025-01-01
- `required_text`:
  - "Incompatibilidades entre los índices correctores:"
  - "En ningún caso será aplicable el índice corrector para empresas de pequeña dimensión (b.1) a las actividades para las que están previstos los índices correctores especiales enumerados en las letras a.2), a.3), a.4) y a.5)."
  - "Cuando resulte aplicable el índice corrector para empresas de pequeña dimensión (b.1) no se aplicará el índice corrector de exceso (b.3)."
- `notes` (verbatim): "Fase 3a: incompatibilidades entre los indices correctores. El indice corrector para empresas de pequena dimension (b.1) nunca se aplica a las actividades que tienen asignados los indices correctores especiales (a.2 transporte por autotaxis, a.3 transporte urbano colectivo, a.4 transporte de mercancias por carretera y servicios de mudanzas, a.5), y cuando resulte aplicable el indice b.1 tampoco se aplica el indice corrector de exceso (b.3); el indice corrector de temporada (b.2) y el de inicio de nuevas actividades (b.4) son a su vez incompatibles entre si. El motor de modulos M131 (0003-cmodulos-epigrafe__cmodulos-rendimiento-neto-actividad.toml, m131_resolve_modulos_indices_generales) aplica ahora los cuatro indices generales (b.1, b.2, b.4, b.3) en el orden de la propia Orden y hace cumplir estructuralmente las tres incompatibilidades: el indice b.1 declarado se ignora para las dos actividades tabuladas con indice especial (721.2 transporte por autotaxis, 722 transporte de mercancias); cuando b.1 se aplica, b.3 se omite; cuando ambos b.2 y b.4 se declaran, prevalece la temporada (orden de enumeracion de la Orden) y se ignora el inicio de nuevas actividades. Dos indicadores internos (modulos-pequena-dimension-ignorado-flag, modulos-temporada-inicio-actividad-conflicto-flag) fundamentan los advisories no bloqueantes que senalan al operador cuando una de sus declaraciones fue ignorada, per no-silent-under-declaration. El motor M100 (0293-...-rendimiento-base.toml) sigue modelando unicamente su propio cascade agrario (indices 1-8, Anexo I instruccion 2.3), sin relacion con este Anexo II."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1347-2024.html; operator to re-stamp"

##### Bundled corpus text

> Incompatibilidades entre los índices correctores:
>
> – En ningún caso será aplicable el índice corrector para empresas de pequeña dimensión (b.1) a las actividades para las que están previstos los índices correctores especiales enumerados en las letras a.2), a.3), a.4) y a.5).
>
> – Cuando resulte aplicable el índice corrector para empresas de pequeña dimensión (b.1) no se aplicará el índice corrector de exceso (b.3).
>
> – Cuando resulte aplicable el índice corrector de temporada (b.2) no se aplicará el índice corrector por inicio de nuevas actividades (b.4).
>
> Los índices correctores se aplicarán según el orden que aparecen enumerados a continuación, siempre que no resulten incompatibles, sobre el rendimiento neto minorado o, en su caso, sobre el rectificado por aplicación de los mismos:

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a coefficient/rate table (tramos and their corresponding coefficients laid out as table rows rather than in a sentence carrying "por ciento" or "euros" adjacent to the figure) -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2025. 3 casilla(s); 1 construct(s); 3 formula(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-03`.

#### 19. `orden-hac-1425-2025:anexo-ii-instruccion-2-3-incompatibilidades`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1425-2025.html#anexo-ii-instruccion-2-3-incompatibilidades`
- `document_id`: `BOE-A-2025-25272`; `effective_from`: 2026-01-01
- `required_text`:
  - "Incompatibilidades entre los índices correctores:"
  - "En ningún caso será aplicable el índice corrector para empresas de pequeña dimensión (b.1) a las actividades para las que están previstos los índices correctores especiales enumerados en las letras a.2), a.3), a.4) y a.5)."
  - "Cuando resulte aplicable el índice corrector para empresas de pequeña dimensión (b.1) no se aplicará el índice corrector de exceso (b.3)."
- `notes` (verbatim): "Fase 3a: incompatibilidades entre los indices correctores. El indice corrector para empresas de pequena dimension (b.1) nunca se aplica a las actividades que tienen asignados los indices correctores especiales (a.2 transporte por autotaxis, a.3 transporte urbano colectivo, a.4 transporte de mercancias por carretera y servicios de mudanzas, a.5), y cuando resulte aplicable el indice b.1 tampoco se aplica el indice corrector de exceso (b.3). El motor de modulos M131 (0003-cmodulos-epigrafe__cmodulos-rendimiento-neto-actividad.toml) modela unicamente el indice de exceso (b.3) en este primer slice para 2026, sin cruzar la incompatibilidad con los indices especiales a.2/a.4 de las actividades tabuladas que los llevan asignados (721.2 transporte por autotaxis, 722 transporte de mercancias por carretera); esta entrada fundamenta el advisory no bloqueante que senala esa brecha al operador, per orden-hac-1425-2025-Anexo-II-instruccion-2-3 y no-silent-under-declaration. Cross-checked byte-identical against the 2025 instruccion (orden-hac-1347-2024:anexo-ii-instruccion-2-3-incompatibilidades)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1425-2025.html; operator to re-stamp"

##### Bundled corpus text

> Incompatibilidades entre los índices correctores:
>
> – En ningún caso será aplicable el índice corrector para empresas de pequeña dimensión (b.1) a las actividades para las que están previstos los índices correctores especiales enumerados en las letras a.2), a.3), a.4) y a.5).
>
> – Cuando resulte aplicable el índice corrector para empresas de pequeña dimensión (b.1) no se aplicará el índice corrector de exceso (b.3).
>
> – Cuando resulte aplicable el índice corrector de temporada (b.2) no se aplicará el índice corrector por inicio de nuevas actividades (b.4).
>
> Los índices correctores se aplicarán según el orden que aparecen enumerados a continuación, siempre que no resulten incompatibles, sobre el rendimiento neto minorado o, en su caso, sobre el rectificado por aplicación de los mismos:

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a coefficient/rate table (tramos and their corresponding coefficients laid out as table rows rather than in a sentence carrying "por ciento" or "euros" adjacent to the figure) -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2026. 1 construct(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-04`.

#### 20. `orden-hfp-1359-2023:anexo-ii-instruccion-2-3-incompatibilidades`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hfp-1359-2023.html#anexo-ii-instruccion-2-3-incompatibilidades`
- `document_id`: `BOE-A-2023-25882`; `effective_from`: 2024-01-01
- `required_text`:
  - "Incompatibilidades entre los índices correctores:"
  - "En ningún caso será aplicable el índice corrector para empresas de pequeña dimensión (b.1) a las actividades para las que están previstos los índices correctores especiales enumerados en las letras a.2), a.3), a.4) y a.5)."
  - "Cuando resulte aplicable el índice corrector para empresas de pequeña dimensión (b.1) no se aplicará el índice corrector de exceso (b.3)."
- `notes` (verbatim): "Fase 3a: incompatibilidades entre los indices correctores. El indice corrector para empresas de pequena dimension (b.1) nunca se aplica a las actividades que tienen asignados los indices correctores especiales (a.2 transporte por autotaxis, a.3 transporte urbano colectivo, a.4 transporte de mercancias por carretera y servicios de mudanzas, a.5), y cuando resulte aplicable el indice b.1 tampoco se aplica el indice corrector de exceso (b.3); el indice corrector de temporada (b.2) y el de inicio de nuevas actividades (b.4) son a su vez incompatibles entre si. El motor de modulos M131 2024 (0003-cmodulos-epigrafe__cmodulos-rendimiento-neto-actividad.toml, m131_resolve_modulos_indices_generales) aplica los cuatro indices generales (b.1, b.2, b.4, b.3) en el orden de la propia Orden y hace cumplir estructuralmente las tres incompatibilidades, en paralelo al motor 2025 grounded en orden-hac-1347-2024:anexo-ii-instruccion-2-3-incompatibilidades."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hfp-1359-2023.html; operator to re-stamp"

##### Bundled corpus text

> Incompatibilidades entre los índices correctores:
>
> – En ningún caso será aplicable el índice corrector para empresas de pequeña dimensión (b.1) a las actividades para las que están previstos los índices correctores especiales enumerados en las letras a.2), a.3), a.4) y a.5).
>
> – Cuando resulte aplicable el índice corrector para empresas de pequeña dimensión (b.1) no se aplicará el índice corrector de exceso (b.3).
>
> – Cuando resulte aplicable el índice corrector de temporada (b.2) no se aplicará el índice corrector por inicio de nuevas actividades (b.4).
>
> Los índices correctores se aplicarán según el orden que aparecen enumerados a continuación, siempre que no resulten incompatibles, sobre el rendimiento neto minorado o, en su caso, sobre el rectificado por aplicación de los mismos:

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a coefficient/rate table (tramos and their corresponding coefficients laid out as table rows rather than in a sentence carrying "por ciento" or "euros" adjacent to the figure) -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2024. 3 casilla(s); 1 construct(s); 3 formula(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-15`.

### Disposicion adicional primera

#### 21. `orden-hac-1347-2024:da-1`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1347-2024.html#da-primera`
- `document_id`: `BOE-A-2024-24949`; `effective_from`: 2025-01-01
- `required_text`:
  - "Reducción en 2025 del rendimiento neto calculado por el método de estimación objetiva"
  - "podrán reducir el rendimiento neto de módulos obtenido en 2025 en un 5 por ciento"
  - "Esta reducción se tendrá en cuenta para cuantificar el rendimiento neto a efectos de los pagos fraccionados correspondientes a 2025"
- `notes` (verbatim): "Reduccion general del 5 por ciento del rendimiento neto de modulos para 2025, aplicable tambien para cuantificar el rendimiento neto a efectos de los pagos fraccionados (M131) de 2025 (apartado 3)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1347-2024.html; operator to re-stamp"

##### Bundled corpus text

> Disposición adicional primera. Reducción en 2025 del rendimiento neto calculado por el método de estimación objetiva.
>
> 1. Los contribuyentes que determinen el rendimiento neto de sus actividades económicas por el método de estimación objetiva, podrán reducir el rendimiento neto de módulos obtenido en 2025 en un 5 por ciento.
>
> 2. Cuando se trate de actividades incluidas en el anexo I de esta orden, la reducción prevista en el apartado 1 anterior se aplicará sobre el rendimiento neto de módulos a que se refiere la instrucción 2.3 para la aplicación de los signos, índices o módulos en el Impuesto sobre la Renta de las Personas Físicas del anexo I de esta orden.
>
> El rendimiento neto de módulos, así calculado, se tendrá en cuenta para la aplicación de lo dispuesto en la instrucción 3 para la aplicación de los signos, índices o módulos en el Impuesto sobre la Renta de las Personas Físicas del anexo I de esta orden.
>
> 3. Esta reducción se tendrá en cuenta para cuantificar el rendimiento neto a efectos de los pagos fraccionados correspondientes a 2025.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, coefficient, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2025. 1 casilla(s); 1 construct(s); 1 formula(s); 1 parameter(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-02`.

Also cited by modelo(s): 100.

#### 22. `orden-hac-1425-2025:da-1`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1425-2025.html#da-primera`
- `document_id`: `BOE-A-2025-25272`; `effective_from`: 2026-01-01
- `required_text`:
  - "Reducción en 2026 del rendimiento neto calculado por el método de estimación objetiva"
  - "podrán reducir el rendimiento neto de módulos obtenido en 2026 en un 5 por ciento"
  - "Esta reducción se tendrá en cuenta para cuantificar el rendimiento neto a efectos de los pagos fraccionados correspondientes a 2026"
- `notes` (verbatim): "Reduccion general del 5 por ciento del rendimiento neto de modulos para 2026, aplicable tambien para cuantificar el rendimiento neto a efectos de los pagos fraccionados (M131) de 2026 (apartado 3). Cross-checked byte-identical against the 2025 disposicion (orden-hac-1347-2024:da-1): same 5 por ciento figure."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1425-2025.html; operator to re-stamp"

##### Bundled corpus text

> Disposición adicional primera. Reducción en 2026 del rendimiento neto calculado por el método de estimación objetiva.
>
> 1. Los contribuyentes que determinen el rendimiento neto de sus actividades económicas por el método de estimación objetiva, podrán reducir el rendimiento neto de módulos obtenido en 2026 en un 5 por ciento.
>
> 2. Cuando se trate de actividades incluidas en el anexo I, la reducción prevista en el apartado 1 anterior se aplicará sobre el rendimiento neto de módulos a que se refiere la instrucción 2.3 para la aplicación de los signos, índices o módulos en el Impuesto sobre la Renta de las Personas Físicas del anexo I.
>
> El rendimiento neto de módulos, así calculado, se tendrá en cuenta para la aplicación de lo dispuesto en la instrucción 3 para la aplicación de los signos, índices o módulos en el Impuesto sobre la Renta de las Personas Físicas del anexo I.
>
> 3. Esta reducción se tendrá en cuenta para cuantificar el rendimiento neto a efectos de los pagos fraccionados correspondientes a 2026.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, coefficient, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2026. 1 casilla(s); 1 construct(s); 1 formula(s); 1 parameter(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-04`.

#### 23. `orden-hfp-1359-2023:da-1`

##### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hfp-1359-2023.html#da-primera`
- `document_id`: `BOE-A-2023-25882`; `effective_from`: 2024-01-01
- `required_text`:
  - "Reducción en 2024 del rendimiento neto calculado por el método de estimación objetiva"
  - "podrán reducir el rendimiento neto de módulos obtenido en 2024 en un 5 por ciento"
  - "Esta reducción se tendrá en cuenta para cuantificar el rendimiento neto a efectos de los pagos fraccionados correspondientes a 2024"
- `notes` (verbatim): "Reduccion general del 5 por ciento del rendimiento neto de modulos para 2024, aplicable tambien para cuantificar el rendimiento neto a efectos de los pagos fraccionados (M131) de 2024 (apartado 3)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hfp-1359-2023.html; operator to re-stamp"

##### Bundled corpus text

> Disposición adicional primera. Reducción en 2024 del rendimiento neto calculado por el método de estimación objetiva.
>
> 1. Los contribuyentes que determinen el rendimiento neto de sus actividades económicas por el método de estimación objetiva, podrán reducir el rendimiento neto de módulos obtenido en 2024 en un 5 por ciento.
>
> 2. Cuando se trate de actividades incluidas en el anexo I de esta Orden, la reducción prevista en el apartado 1 anterior se aplicará sobre el rendimiento neto de módulos a que se refiere la instrucción 2.3 para la aplicación de los signos, índices o módulos en el Impuesto sobre la Renta de las Personas Físicas del anexo I de esta orden.
>
> El rendimiento neto de módulos, así calculado, se tendrá en cuenta para la aplicación de lo dispuesto en la instrucción 3 para la aplicación de los signos, índices o módulos en el Impuesto sobre la Renta de las Personas Físicas del anexo I de esta orden.
>
> 3. Esta reducción se tendrá en cuenta para cuantificar el rendimiento neto a efectos de los pagos fraccionados correspondientes a 2024.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, coefficient, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

##### Modelo 131 dependents

Cited in revisions 2024. 1 casilla(s); 1 construct(s); 1 formula(s); 1 parameter(s).

##### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-15`.

## Otras referencias

### 24. `rd-439-2007:art-110`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/rd-439-2007-art-110.html#a110`
- `document_id`: `BOE-A-2007-6820`; `effective_from`: 2007-03-31
- `required_text`:
  - "20 por ciento del rendimiento neto"
  - "el 4 por ciento de los rendimientos netos"
  - "el porcentaje anterior será el 3 por ciento"
  - "no disponga de personal asalariado dicho porcentaje será el 2 por ciento"
  - "el pago fraccionado consistirá en el 2 por ciento del volumen de ventas o ingresos del trimestre"
  - "2 por ciento del volumen de ingresos del trimestre"
  - "se reducirán en un 60 por ciento"
  - "retenciones practicadas y los ingresos a cuenta efectuados conforme a lo dispuesto en los artículos 95 y 104"
  - "podrá deducirse dicha diferencia en cualquiera de los siguientes pagos fraccionados"
  - "33.007,2 euros"
  - "trimestres anteriores del mismo año"
- `notes` (verbatim): "Base reglamentaria del importe del pago fraccionado de actividades economicas: 20 por ciento para estimacion directa, escala 4/3/2 por ciento para estimacion objetiva con datos-base, regla sin datos-base al 2 por ciento, actividades agrarias al 2 por ciento, minoraciones y porcentajes superiores. Para la revision 2019-y-siguientes, la regla especifica de resultados negativos de trimestres anteriores del Modelo 130 se verifica contra las instrucciones AEAT del modelo; no contra un apartado 110.5 vigente."
- `reviewed_by` (verbatim): "verified against official BOE-A-2007-6820#a110 and bundled rd-439-2007-art-110.html; operator to re-stamp"

#### Bundled corpus text

> Artículo 110. Importe del fraccionamiento.
>
> 1. Los contribuyentes a que se refiere el artículo anterior ingresarán, en cada plazo, las cantidades siguientes:
>
> a) Por las actividades que estuvieran en el método de estimación directa, en cualquiera de sus modalidades, el 20 por ciento del rendimiento neto correspondiente al período de tiempo transcurrido desde el primer día del año hasta el último día del trimestre a que se refiere el pago fraccionado.
>
> De la cantidad resultante por aplicación de lo dispuesto en esta letra se deducirán los pagos fraccionados que, en relación con estas actividades, habría correspondido ingresar en los trimestres anteriores del mismo año si no se hubiera aplicado lo dispuesto en la letra c) del apartado 3 de este artículo.
>
> b) Por las actividades que estuvieran en el método de estimación objetiva, el 4 por ciento de los rendimientos netos resultantes de la aplicación de dicho método en función de los datos-base del primer día del año a que se refiere el pago fraccionado o, en caso de inicio de actividades, del día en que éstas hubiesen comenzado.
>
> No obstante, en el supuesto de actividades que tengan sólo una persona asalariada el porcentaje anterior será el 3 por ciento, y en el supuesto de que no disponga de personal asalariado dicho porcentaje será el 2 por ciento.
>
> Cuando alguno de los datos-base no pudiera determinarse el primer día del año, se tomará, a efectos del pago fraccionado, el correspondiente al año inmediato anterior. En el supuesto de que no pudiera determinarse ningún dato-base, el pago fraccionado consistirá en el 2 por ciento del volumen de ventas o ingresos del trimestre.
>
> c) Tratándose de actividades agrícolas, ganaderas, forestales o pesqueras, cualquiera que fuese el método de determinación del rendimiento neto, el 2 por ciento del volumen de ingresos del trimestre, excluidas las subvenciones de capital y las indemnizaciones.
>
> 2. Los porcentajes señalados en el apartado anterior se reducirán en un 60 por ciento para las actividades económicas que tengan derecho a la deducción en la cuota prevista en el artículo 68.4 de la Ley del Impuesto.
>
> 3. De la cantidad resultante por aplicación de lo dispuesto en los apartados anteriores, se podrán deducir, en su caso:
>
> a) Las retenciones practicadas y los ingresos a cuenta efectuados correspondientes al período de tiempo transcurrido desde el primer día del año hasta el último día del trimestre al que se refiere el pago fraccionado, cuando se trate de:
>
> 1.º Actividades profesionales que determinen su rendimiento neto por el método de estimación directa, en cualquiera de sus modalidades.
>
> 2.º Arrendamiento de inmuebles urbanos que constituya actividad económica.
>
> 3.º Cesión del derecho a la explotación de la imagen o del consentimiento o autorización para su utilización que constituya actividad económica, y demás rentas previstas en el artículo 75.2 b) del presente Reglamento.
>
> b) Las retenciones practicadas y los ingresos a cuenta efectuados conforme a lo dispuesto en los artículos 95 y 104 de este Reglamento correspondientes al trimestre, cuando se trate de:
>
> 1.º Actividades económicas que determinen su rendimiento neto por el método de estimación objetiva. No obstante, cuando el importe de las retenciones e ingresos a cuenta soportados en el trimestre sea superior a la cantidad resultante por aplicación de lo dispuesto en las letras b) y c) del apartado 1 anterior, así como, en su caso, de lo dispuesto en el apartado 2 anterior, podrá deducirse dicha diferencia en cualquiera de los siguientes pagos fraccionados correspondientes al mismo período impositivo cuyo importe positivo lo permita y hasta el límite máximo de dicho importe.
>
> 2.º Actividades agrícolas, ganaderas o forestales no incluidas en el número 1.º anterior.
>
> c) Cuando la cuantía de los rendimientos netos de actividades económicas del ejercicio anterior sea igual o inferior a 12.000 euros, el importe que resulte del siguiente cuadro:
>
> Cuantía de los rendimientos netos del ejercicio anterior
>
> -
>
> Euros
>
> Importe de la minoración
>
> -
>
> Euros
>
> Igual o inferior a 9.000
>
> 100
>
> Entre 9.000,01 y 10.000
>
> 75
>
> Entre 10.000,01 y 11.000
>
> 50
>
> Entre 11.000,01 y 12.000
>
> 25
>
> Cuando el importe de la minoración prevista en esta letra sea superior a la cantidad resultante por aplicación de lo dispuesto en los apartados anteriores y en las letras a) y b) de este apartado, la diferencia podrá deducirse en cualquiera de los siguientes pagos fraccionados correspondientes al mismo período impositivo cuyo importe positivo lo permita y hasta el límite máximo de dicho importe.
>
> d) Cuando los contribuyentes destinen cantidades para la adquisición o rehabilitación de su vivienda habitual utilizando financiación ajena, por las que vayan a tener derecho a la deducción por inversión en vivienda habitual regulada en la disposición transitoria decimoctava de la Ley del Impuesto, las cuantías que se citan a continuación:
>
> 1.º Tratándose de contribuyentes que ejerzan actividades que estuvieran en el método de estimación directa, en cualquiera de sus modalidades, cuyos rendimientos íntegros previsibles del período impositivo sean inferiores a 33.007,2 euros, se podrá deducir el 2 por ciento del rendimiento neto correspondiente al período de tiempo transcurrido desde el primer día del año hasta el último día del trimestre a que se refiere el pago fraccionado.
>
> A estos efectos se considerarán como rendimientos íntegros previsibles del período impositivo los que resulten de elevar al año los rendimientos íntegros correspondientes al primer trimestre.
>
> En ningún caso podrá practicarse una deducción por importe superior a 660,14 euros en cada trimestre.
>
> 2.º Tratándose de contribuyentes que ejerzan actividades que estuvieran en el método de estimación objetiva cuyos rendimientos netos resultantes de la aplicación de dicho método en función de los datos-base del primer día del año a que se refiere el pago fraccionado o, en caso de inicio de actividades, del día en que éstas hubiesen comenzado, sean inferiores a 33.007,2 euros, se podrá deducir el 0,5 por ciento de los citados rendimientos netos. No obstante, cuando no pudiera determinarse ningún dato base se aplicará la deducción prevista en el número 3.º de esta letra sobre el volumen de ventas o ingresos del trimestre.
>
> 3.º Tratándose de contribuyentes que ejerzan actividades agrícolas, ganaderas, forestales o pesqueras, cualquiera que fuese el método de determinación del rendimiento neto, cuyo volumen previsible de ingresos del período impositivo, excluidas las subvenciones de capital y las indemnizaciones sea inferior a 33.007,2 euros, se podrá deducir el 2 por ciento del volumen de ingresos del trimestre, excluidas las subvenciones de capital y las indemnizaciones.
>
> A estos efectos se considerará como volumen previsible de ingresos del período impositivo el resultado de elevar al año el volumen de ingresos del primer trimestre, excluidas las subvenciones de capital y las indemnizaciones.
>
> En ningún caso podrá practicarse una deducción por un importe acumulado en el período impositivo superior a 660,14 euros.
>
> Las deducciones previstas en esta letra d) no resultarán de aplicación cuando los contribuyentes ejerzan dos o más actividades comprendidas en ordinales distintos, ni cuando perciban rendimientos del trabajo y hubiesen efectuado a su pagador la comunicación a que se refiere el párrafo segundo del artículo 88.1 de este Reglamento, ni cuando las cantidades se destinen a la construcción o ampliación de la vivienda.
>
> 4. Los contribuyentes podrán aplicar en cada uno de los pagos fraccionados porcentajes superiores a los indicados.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, coefficient, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

#### Modelo 131 dependents

Cited in revisions 2019-2023, 2024, 2025, 2026. 38 application_link(s); 303 binding(s); 16 casilla(s); 4 construct(s); 28 formula(s); 2 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 100, 130.

### 25. `real-decreto-ley-7-2024:art-11`

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

**Numeric flag**: this reference states a rate, coefficient, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE/AEAT cross-check is the operator's to make.

#### Modelo 131 dependents

Cited in revisions 2024. 2 binding(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-13`.

Also cited by modelo(s): 100.
