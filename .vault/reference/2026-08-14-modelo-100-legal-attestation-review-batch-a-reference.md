---
tags:
  - '#reference'
  - '#modelo-100-legal-attestation-review-batch-a'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:d9e95ec85deebf7d5793dedb806d097464950a4895964d32aea745cb6cb8118f'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-14-registry-campaign-sequencing-operator-attestation-ledger-audit]]"
---

# `modelo-100-legal-attestation-review-batch-a` reference: `Modelo 100 legal-reference attestation review packet, Batch A (restamp-ready tranche)`

Modelo 100 carries 119 of the 161 legal references still remaining across the
seven layout-capable modelos -- 74% of the entire remaining attestation
burden on one modelo. Building that as one undifferentiated document would
produce something nobody could work through in a sitting, so it is split into
three batches by a real shared property rather than by a round number: this
is **Batch A**, the 49 references whose `reviewed_by` field already carries a
self-verification claim -- most commonly "agent-authored... operator to
re-stamp", the same shape as the Modelo 390 packet's `art-104`/`art-105`, just
far more prevalent here. Batch B (31 references, all bearing a rate, bracket,
threshold or amount) and Batch C (39 references, the concept-clustered
remainder) follow separately.

Worklist confirmed at exactly 119 via `_collect_snapshot_ref_ids` across all
six Modelo 100 revisions (2020-2025); Batch A's 49 are the subset whose
`reviewed_by` or `notes` field states, in the agent's own words, that the
citation was already checked against the bundled or live text. That claim is
what makes this batch cheapest to re-stamp -- the transcription work is
already done -- and it is exactly why the caveat below is not a footnote here.

For each reference this packet places the registry's own claim next to the
actual bundled corpus text it points at, quoted verbatim, and lists what in
Modelo 100 depends on it. It does not state whether the claim and the source
agree -- that is the operator's act, and stating it here would turn the
operator's sign-off into a rubber stamp on agent work. The one exception is a
structural discrepancy: a broken `corpus_ref`, a `required_text` phrase absent
from the quoted text, or a citation that plainly names a different subject.
**Zero of the 119 references across all three planned batches triggered that
exception** -- stated here, up front, once, so the operator knows the whole
119-reference sweep found nothing structurally broken rather than that nobody
checked. Within Batch A specifically, all 49 `corpus_ref`s resolve and every
declared `required_text` phrase is present in the quoted text, verified
against the production check (`cadrumo.core.normalise_corpus_text`, which
folds case, diacritics and whitespace before comparing -- the same normaliser
the registry build itself uses, not a bespoke one built for this packet).

**Standing caveat on the `notes` and `reviewed_by` fields -- the norm in this
batch, not the exception.** Every `notes` and `reviewed_by` value quoted below
is agent-authored registry content, not operator-verified prose. On the
Modelo 390 packet this caveat applied to two references out of ten; here it
applies to **all 49 of 49**, because Batch A is defined by exactly this
property -- every entry in it carries some form of "already checked" language.
Where a note or `reviewed_by` field asserts that the bundled text was already
checked against a live BOE source, cross-checked against an AEAT manual, or
independently verified, that assertion is itself an unverified agent claim,
carrying exactly the same weight as any other agent claim in this packet -- it
is not independent confirmation, and it may have been written by the same
agent that authored the entry it purports to validate. That is the same shape
as a `required_text` cross-check that passes because one author wrote both the
excerpt and the phrase validating it: self-attesting and unfalsifiable from
inside the packet. A reader who met this caveat as a one-time footnote on an
earlier packet should read it as the operating condition of this entire batch
instead: every claim below is agent work awaiting the operator's own act, not
a shortcut past it.

Two of the 49 carry a self-verification claim of particular weight, because
they sit on numeric content rather than procedural or definitional text.
`ley-35-2006:art-63-2015` is the pre-2021 state general IRPF scale itself
(the five-bracket table, before Ley 11/2020 added a sixth), and its `notes`
field states that "the stored 2020 bracket values were independently verified
against this redaction" -- a self-attested check sitting directly on the
bracket table is the single worst place for an unexamined claim to go
unnoticed, and it is flagged here rather than left to be found mid-read.
`orden-hac-1347-2024:anexo-i-instruccion-2-1`'s `notes` similarly states it
was "cross-checked byte-identical against the AEAT Manual practico de Renta
2025" worked example, carrying a full monetary example (18.030,00 x 0,37 =
6.671,10 euros). Both are also numeric-flagged below, for the same reason
stated in the next paragraph.

**Numeric grounding flag.** Per project rule, the bundled corpus text is
preferred evidence but not infallible on numbers: for any reference
establishing a rate, amount or threshold, a live BOE or AEAT consolidated-text
cross-check is the operator's to make -- no such fetch was performed here.
Unlike the Modelo 390 packet, where this flag applied to none of ten
references, it applies to **34 of Batch A's 49** -- IRPF is rate- and
bracket-heavy by nature, and a self-verification claim sitting on a numeric
provision (the two above) is flagged doubly: once for the unverified claim,
once for the number itself. Each affected section below carries its own
`**Numeric flag**` line rather than leaving the reader to notice it while
reading the quoted text.

Batch A also carries a short, distinct procedural cluster: five references
(`orden-hac-242-2025:art-8`, `orden-hac-248-2021:art-3`,
`orden-hac-265-2024:art-3`, `orden-hfp-207-2022:art-3`,
`orden-hfp-310-2023:art-3`) are the annual órdenes approving that year's
Modelo 100/D-100 form and its filing-deadline window, one per revision year.
Four of the five have no casilla, binding, formula or construct dependent at
all in Modelo 100 -- they ground the form's approval and the filing calendar,
not any declared data field -- while the fifth
(`orden-hac-242-2025:art-8`) grounds a `deadline_window`/`application_link`
pair rather than a casilla. This is a genuinely distinct cluster, not a data
gap, and is sequenced last in this batch for that reason.

This document is read-only working material. No `operator_reviewed` stamp was
applied or could be applied through any path available to this session, and
nothing under `modelos/100/**` was touched to produce it.

## Summary

Forty-nine sections follow, one per legal reference, in the order gathered
with the five procedural deadline-órdenes moved to the end as their own short
cluster. Each section carries the same four parts in the same order: the
registry's current entry, the bundled corpus text quoted verbatim (the
trailing BOE amendment-history citation footer -- "Se modifica...", "Se
añade..." -- is omitted where present; the substantive body is never
abridged), what in Modelo 100 depends on it, and the entry's current review
status. A `**Numeric flag**` line appears wherever the text states a rate,
bracket, threshold or amount.

### 1. `ley-31-2022:da-70`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-31-2022-da-70.html#da-70`
- `document_id`: `BOE-A-2022-22128`; `effective_from`: 2023-01-01
- `required_text`:
  - "Reserva para inversiones en las Illes Balears"
  - "El importe de la reserva pendiente de materialización"
  - "Los contribuyentes del Impuesto sobre la Renta de las Personas Físicas"
  - "tendrán derecho a una deducción en la cuota íntegra"
- `notes` (verbatim): "Ley 31/2022 (Presupuestos Generales del Estado para 2023) disposición adicional 70ª: Régimen fiscal especial de las Illes Balears. DA-70.Cuatro grounds the Reserva para Inversiones en las Illes Balears (RIB), including the reserve/materialisation tracking fields and the IRPF estimación-directa cuota deduction for Modelo 100 RIB casillas. Corpus excerpt bundled from the official BOE consolidated text."
- `reviewed_by` (verbatim): "verified against official BOE-A-2022-22128 consolidated DA-70; corpus excerpt bundled"

#### Bundled corpus text

> Disposición adicional septuagésima. Régimen fiscal especial de las Illes Balears.
>
> Con efectos para los períodos impositivos que se inicien entre el 1 de enero de 2023 y el 31 de diciembre de 2028 se introduce el Régimen fiscal especial de las Illes Balears, que queda redactado de la siguiente forma:
>
> Cuatro. Reserva para inversiones en las Illes Balears.
>
> 1. Los contribuyentes del Impuesto sobre Sociedades y del Impuesto sobre la Renta de no Residentes tendrán derecho a la reducción en la base imponible de las cantidades que, con relación a sus establecimientos situados en las Illes Balears, destinen de sus beneficios a la reserva para inversiones de acuerdo con lo dispuesto en este apartado.
>
> 2. La reducción a que se refiere el número anterior se aplicará a las dotaciones que en cada período impositivo se hagan a la reserva para inversiones hasta el límite del 90 por ciento de la parte de beneficio obtenido en el mismo período que no sea objeto de distribución, en cuanto proceda de establecimientos situados en las Illes Balears.
>
> En ningún caso la aplicación de la reducción podrá determinar que la base imponible sea negativa.
>
> 3. La reserva para inversiones deberá figurar en los balances con absoluta separación y título apropiado y será indisponible en tanto que los bienes en que se materializó deban permanecer en la empresa.
>
> 4. Las cantidades destinadas a la reserva para inversiones en las Illes Balears deberán materializarse en el plazo máximo de tres años, contados desde la fecha del devengo del impuesto correspondiente al ejercicio en que se ha dotado la misma, en la realización de alguna de las siguientes inversiones:
>
> A. La adquisición de elementos patrimoniales del inmovilizado material o intangible, de elementos patrimoniales que contribuyan a la mejora y protección del medio ambiente en el territorio de las Illes Balears, en los términos que reglamentariamente se determinen, así como los gastos de investigación y desarrollo derivados de actividades de investigación, desarrollo e innovación tecnológica a que se refiere el artículo 35.1 y 2 de la Ley 27/2014, de 27 de noviembre, del Impuesto sobre Sociedades.
>
> B. La creación de puestos de trabajo relacionada de forma directa con las inversiones previstas en la letra A, que se produzca dentro de un período de seis meses a contar desde la fecha de entrada en funcionamiento de dicha inversión.
>
> C. La suscripción de acciones o participaciones en el capital emitidas por sociedades como consecuencia de su constitución o ampliación de capital que desarrollen en el archipiélago su actividad, siempre que se cumplan los requisitos establecidos en este apartado.
>
> 10. Los contribuyentes a que se refiere este apartado podrán llevar a cabo inversiones anticipadas, que se considerarán como materialización de la reserva para inversiones que se dote con cargo a beneficios obtenidos en el período impositivo en el que se realiza la inversión o en los tres posteriores, siempre que se cumplan los restantes requisitos exigidos en el mismo.
>
> La materialización y su sistema de financiación se comunicarán conjuntamente con la declaración del Impuesto sobre Sociedades, el Impuesto sobre la Renta de no Residentes o el Impuesto sobre la Renta de las Personas Físicas del período impositivo en que se realicen las inversiones anticipadas.
>
> 12. Mientras no se cumpla el plazo de mantenimiento a que se refiere el número 8 de este apartado, los contribuyentes harán constar en la memoria de las cuentas anuales la siguiente información:
>
> a) El importe de las dotaciones efectuadas a la reserva con indicación del ejercicio en que se efectuaron.
>
> b) El importe de la reserva pendiente de materialización, con indicación del ejercicio en que se hubiera dotado.
>
> c) El importe y la fecha de las inversiones, con indicación del ejercicio en que se produjo la dotación de la reserva, así como la identificación de los elementos patrimoniales en que se materializa.
>
> d) El importe y la fecha de las inversiones anticipadas a la dotación, previstas en el número 10 de este apartado, lo que se hará constar a partir de la memoria correspondiente al ejercicio en que las mismas se materializaron.
>
> Los contribuyentes que no tengan obligación de llevar cuentas anuales llevarán un libro registro de bienes de inversión, en el que figurará la información requerida en las letras a) a g) anteriores.
>
> 13. Los contribuyentes del Impuesto sobre la Renta de las Personas Físicas que determinen sus rendimientos netos mediante el método de estimación directa, tendrán derecho a una deducción en la cuota íntegra por los rendimientos netos de explotación que se destinen a la reserva para inversiones, siempre y cuando estos provengan de actividades económicas realizadas mediante establecimientos situados en las Illes Balears.
>
> Para poder disfrutar de la reserva para inversiones en las Illes Balears, las personas físicas deberán llevar la contabilidad en la forma exigida por el Código de Comercio y su normativa de desarrollo desde el ejercicio en que se han obtenido los beneficios que se destinan a dotar la reserva para inversiones en las Illes Balears hasta aquel en que deban permanecer en funcionamiento los bienes objeto de la materialización de la inversión.
>
> La deducción se calculará aplicando el tipo medio de gravamen a las dotaciones anuales a la reserva y tendrá como límite el 80 por ciento de la parte de la cuota íntegra que proporcionalmente corresponda a la cuantía de los rendimientos netos de explotación que provengan de establecimientos situados en las Illes Balears, siempre que no se superen los límites establecidos en el Ordenamiento comunitario que, en cada caso, resulten de aplicación.
>
> Este beneficio fiscal se aplicará de acuerdo con lo dispuesto en los números 3 a 12 de este apartado, en los mismos términos que los exigidos a las sociedades y demás entidades jurídicas.
>
> 14. La disposición de la reserva para inversiones con anterioridad a la finalización del plazo de mantenimiento de la inversión o para inversiones diferentes a las previstas en el número 4 de este apartado, así como el incumplimiento de cualquier otro de los requisitos establecidos en este apartado, salvo los contenidos en sus números 3 y 12, dará lugar a que el contribuyente proceda a la integración, en la base imponible del Impuesto sobre Sociedades o del Impuesto sobre la Renta de no Residentes o en la cuota íntegra del Impuesto sobre la Renta de las Personas Físicas del ejercicio en que ocurrieran estas circunstancias, de las cantidades que en su día dieron lugar a la reducción de aquella o a la deducción de esta, sin perjuicio de las sanciones que resulten procedentes.
>
> 16. Reglamentariamente se determinará la información que deban suministrar los contribuyentes que practiquen la reducción prevista en este apartado junto con la declaración por el Impuesto sobre Sociedades, del Impuesto sobre la Renta de las Personas Físicas o del Impuesto sobre la Renta de no Residentes, con el objeto de verificar que el importe de las ayudas y beneficios obtenidos en relación con una misma inversión no excede de los límites establecidos en el Ordenamiento comunitario que, en cada caso, resulten de aplicación.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2023, 2024, 2025. 17 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 2. `ley-35-2006:art-11`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a11`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Individualización de rentas"
- `notes` (verbatim): "LIRPF art 11: individualización de rentas — la renta se entiende obtenida por los contribuyentes en función del origen o fuente (rendimientos del trabajo por quien genera el derecho, del capital por los titulares de los elementos, de actividades por quien las realiza, ganancias por los titulares). Base legal de las casillas 'Contribuyente que obtiene los rendimientos / a quien corresponde la imputación / titular' del Modelo 100 (toma de datos ampliada). AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#a11; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a11; operator to re-stamp"

#### Bundled corpus text

> Artículo 11. Individualización de rentas.
>
> 1. La renta se entenderá obtenida por los contribuyentes en función del origen o fuente de aquélla, cualquiera que sea, en su caso, el régimen económico del matrimonio.
>
> 2. Los rendimientos del trabajo se atribuirán exclusivamente a quien haya generado el derecho a su percepción.
>
> No obstante, las prestaciones a que se refiere el artículo 17.2 a) de esta Ley se atribuirán a las personas físicas en cuyo favor estén reconocidas.
>
> 3. Los rendimientos del capital se atribuirán a los contribuyentes que sean titulares de los elementos patrimoniales, bienes o derechos, de que provengan dichos rendimientos según las normas sobre titularidad jurídica aplicables en cada caso y en función de las pruebas aportadas por aquéllos o de las descubiertas por la Administración.
>
> En su caso, serán de aplicación las normas sobre titularidad jurídica de los bienes y derechos contenidas en las disposiciones reguladoras del régimen económico del matrimonio, así como en los preceptos de la legislación civil aplicables en cada caso a las relaciones patrimoniales entre los miembros de la familia.
>
> La titularidad de los bienes y derechos que conforme a las disposiciones o pactos reguladores del correspondiente régimen económico matrimonial, sean comunes a ambos cónyuges, se atribuirá por mitad a cada uno de ellos, salvo que se justifique otra cuota de participación.
>
> Cuando no resulte debidamente acreditada la titularidad de los bienes o derechos, la Administración tributaria tendrá derecho a considerar como titular a quien figure como tal en un registro fiscal u otros de carácter público.
>
> 4. Los rendimientos de las actividades económicas se considerarán obtenidos por quienes realicen de forma habitual, personal y directa la ordenación por cuenta propia de los medios de producción y los recursos humanos afectos a las actividades.
>
> Se presumirá, salvo prueba en contrario, que dichos requisitos concurren en quienes figuren como titulares de las actividades económicas.
>
> 5. Las ganancias y pérdidas patrimoniales se considerarán obtenidas por los contribuyentes que sean titulares de los bienes, derechos y demás elementos patrimoniales de que provengan según las normas sobre titularidad jurídica establecidas para los rendimientos del capital en el apartado 3 anterior.
>
> Las ganancias patrimoniales no justificadas se atribuirán en función de la titularidad de los bienes o derechos en que se manifiesten.
>
> Las adquisiciones de bienes y derechos que no se deriven de una transmisión previa, como las ganancias en el juego, se considerarán ganancias patrimoniales de la persona a quien corresponda el derecho a su obtención o que las haya ganado directamente.
>
> Se modifican los apartados 3 y 5 por el art. 1.7 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> CAPÍTULO III
>
> Período impositivo, devengo del Impuesto e imputación temporal

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 45 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 3. `ley-35-2006:art-38`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a38`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Ganancias excluidas de gravamen en supuestos de reinversión"
- `notes` (verbatim): "LIRPF art 38: ganancias excluidas de gravamen en supuestos de reinversión — exención de la ganancia por transmisión de la vivienda habitual reinvertida en otra vivienda habitual, y de acciones/participaciones de entidades de nueva o reciente creación. Base legal de las casillas de exención por reinversión en Modelo 100. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#a38; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a38; operator to re-stamp"

#### Bundled corpus text

> Artículo 38. Ganancias excluidas de gravamen en supuestos de reinversión.
>
> 1. Podrán excluirse de gravamen las ganancias patrimoniales obtenidas por la transmisión de la vivienda habitual del contribuyente, siempre que el importe total obtenido por la transmisión se reinvierta en la adquisición de una nueva vivienda habitual en las condiciones que reglamentariamente se determinen.
>
> Cuando el importe reinvertido sea inferior al total de lo percibido en la transmisión, únicamente se excluirá de tributación la parte proporcional de la ganancia patrimonial obtenida que corresponda a la cantidad reinvertida.
>
> 2. Podrán excluirse de gravamen las ganancias patrimoniales que se pongan de manifiesto con ocasión de la transmisión de acciones o participaciones por las que se hubiera practicado la deducción prevista en el artículo 68.1 de esta Ley, siempre que el importe total obtenido por la transmisión de las mismas se reinvierta en la adquisición de acciones o participaciones de las citadas entidades en las condiciones que reglamentariamente se determinen.
>
> Cuando el importe reinvertido sea inferior al total percibido en la transmisión, únicamente se excluirá de tributación la parte proporcional de la ganancia patrimonial obtenida que corresponda a la cantidad reinvertida.
>
> No resultará de aplicación lo dispuesto en este apartado en los siguientes supuestos:
>
> a) Cuando el contribuyente hubiera adquirido valores homogéneos en el año anterior o posterior a la transmisión de las acciones o participaciones. En este caso, la exención no procederá respecto de los valores que como consecuencia de dicha adquisición permanezcan en el patrimonio del contribuyente.
>
> b) Cuando las acciones o participaciones se transmitan a su cónyuge, a cualquier persona unida al contribuyente por parentesco, en línea recta o colateral, por consanguinidad o afinidad, hasta el segundo grado incluido, a una entidad respecto de la que se produzca, con el contribuyente o con cualquiera de las personas anteriormente citadas, alguna de las circunstancias establecidas en el artículo 42 del Código de Comercio, con independencia de la residencia y de la obligación de formular cuentas anuales consolidadas, distinta de la propia entidad cuyas participaciones se transmiten.
>
> 3. Podrán excluirse de gravamen las ganancias patrimoniales que se pongan de manifiesto con ocasión de la transmisión de elementos patrimoniales por contribuyentes mayores de 65 años, siempre que el importe total obtenido por la transmisión se destine en el plazo de seis meses a constituir una renta vitalicia asegurada a su favor, en las condiciones que reglamentariamente se determinen. La cantidad máxima total que a tal efecto podrá destinarse a constituir rentas vitalicias será de 240.000 euros.
>
> Cuando el importe reinvertido sea inferior al total de lo percibido en la transmisión, únicamente se excluirá de tributación la parte proporcional de la ganancia patrimonial obtenida que corresponda a la cantidad reinvertida.
>
> La anticipación, total o parcial, de los derechos económicos derivados de la renta vitalicia constituida, determinará el sometimiento a gravamen de la ganancia patrimonial correspondiente.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 13 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 4. `ley-35-2006:art-51`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a51`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Reducciones por aportaciones y contribuciones a sistemas de previsión social"
  - "deberá reponer las reducciones en la base imponible indebidamente practicadas"
- `notes` (verbatim): "LIRPF art 51: reducciones de la base imponible general por aportaciones y contribuciones a sistemas de previsión social (planes de pensiones, mutualidades de previsión social, planes de previsión asegurados, planes de previsión social empresarial, seguros de dependencia, y sistemas a favor de personas con discapacidad). Base legal de las casillas de reducción/exceso por previsión social en Modelo 100; el límite conjunto lo fija el art. 52. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#a51; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a51; operator to re-stamp"

#### Bundled corpus text

> Artículo 51. Reducciones por aportaciones y contribuciones a sistemas de previsión social.
>
> Podrán reducirse en la base imponible general las siguientes aportaciones y contribuciones a sistemas de previsión social:
>
> 1. Aportaciones y contribuciones a planes de pensiones.
>
> 1.º Las aportaciones realizadas por los partícipes a planes de pensiones, incluyendo las contribuciones del promotor que le hubiesen sido imputadas en concepto de rendimiento del trabajo.
>
> 2.º Las aportaciones realizadas por los partícipes a los planes de pensiones regulados en la Directiva 2003/41/CE del Parlamento Europeo y del Consejo, de 3 de junio de 2003, relativa a las actividades y la supervisión de fondos de pensiones de empleo, incluidas las contribuciones efectuadas por las empresas promotoras, siempre que se cumplan los siguientes requisitos:
>
> a) Que las contribuciones se imputen fiscalmente al partícipe a quien se vincula la prestación.
>
> b) Que se transmita al partícipe de forma irrevocable el derecho a la percepción de la prestación futura.
>
> c) Que se transmita al partícipe la titularidad de los recursos en que consista dicha contribución.
>
> d) Las contingencias cubiertas deberán ser las previstas en el artículo 8.6 del texto refundido de la Ley de regulación de los planes y fondos de pensiones, aprobado por el Real Decreto Legislativo 1/2002, de 29 de noviembre.
>
> 2. Las aportaciones y contribuciones a mutualidades de previsión social que cumplan los siguientes requisitos:
>
> a) Requisitos subjetivos:
>
> 1.º Las cantidades abonadas en virtud de contratos de seguro concertados con mutualidades de previsión social por profesionales no integrados en alguno de los regímenes de la Seguridad Social, por sus cónyuges y familiares consanguíneos en primer grado, así como por los trabajadores de las citadas mutualidades, en la parte que tenga por objeto la cobertura de las contingencias previstas en el artículo 8.6 del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones siempre que no hayan tenido la consideración de gasto deducible para los rendimientos netos de actividades económicas, en los términos que prevé el segundo párrafo de la regla 1.ª del artículo 30.2 de esta Ley.
>
> 2.º Las cantidades abonadas en virtud de contratos de seguro concertados con mutualidades de previsión social por profesionales o empresarios individuales integrados en cualquiera de los regímenes de la Seguridad Social, por sus cónyuges y familiares consanguíneos en primer grado, así como por los trabajadores de las citadas mutualidades, en la parte que tenga por objeto la cobertura de las contingencias previstas en el artículo 8.6 del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones.
>
> 3.º Las cantidades abonadas en virtud de contratos de seguro concertados con mutualidades de previsión social por trabajadores por cuenta ajena o socios trabajadores, incluidas las contribuciones del promotor que les hubiesen sido imputadas en concepto de rendimientos del trabajo, cuando se efectúen de acuerdo con lo previsto en la disposición adicional primera del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones, con inclusión del desempleo para los citados socios trabajadores.
>
> b) Los derechos consolidados de los mutualistas sólo podrán hacerse efectivos en los supuestos previstos, para los planes de pensiones, por el artículo 8.8 del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones.
>
> 3. Las primas satisfechas a los planes de previsión asegurados. Los planes de previsión asegurados se definen como contratos de seguro que deben cumplir los siguientes requisitos:
>
> a) El contribuyente deberá ser el tomador, asegurado y beneficiario. No obstante, en el caso de fallecimiento, podrá generar derecho a prestaciones en los términos previstos en el texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones, aprobado por el Real Decreto Legislativo 1/2002, de 29 de noviembre.
>
> b) Las contingencias cubiertas deberán ser, únicamente, las previstas en el artículo 8.6 del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones, aprobado por el Real Decreto Legislativo 1/2002, de 29 de noviembre, y deberán tener como cobertura principal la de jubilación. Sólo se permitirá la disposición anticipada, total o parcial, en estos contratos en los supuestos previstos en el artículo 8.8 del citado texto refundido. En dichos contratos no será de aplicación lo dispuesto en los artículos 97 y 99 de la Ley 50/1980, de 8 de octubre, de Contrato de Seguro.
>
> c) Este tipo de seguros tendrá obligatoriamente que ofrecer una garantía de interés y utilizar técnicas actuariales.
>
> d) En el condicionado de la póliza se hará constar de forma expresa y destacada que se trata de un plan de previsión asegurado. La denominación Plan de Previsión Asegurado y sus siglas quedan reservadas a los contratos de seguro que cumplan los requisitos previstos en esta Ley.
>
> e) Reglamentariamente se establecerán los requisitos y condiciones para la movilización de la provisión matemática a otro plan de previsión asegurado.
>
> En los aspectos no específicamente regulados en los párrafos anteriores y sus normas de desarrollo, el régimen financiero y fiscal de las aportaciones, contingencias y prestaciones de estos contratos se regirá por la normativa de los planes de pensiones, salvo los aspectos financiero-actuariales de las provisiones técnicas correspondientes. En particular, los derechos en un plan de previsión asegurado no podrán ser objeto de embargo, traba judicial o administrativa hasta el momento en que se cause el derecho a la prestación o en que sean disponibles en los supuestos de enfermedad grave, desempleo de larga duración o por corresponder a primas abonadas con al menos diez años de antigüedad.
>
> 4. Las aportaciones realizadas por los trabajadores a los planes de previsión social empresarial regulados en la disposición adicional primera del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones, incluyendo las contribuciones del tomador. En todo caso los planes de previsión social empresarial deberán cumplir los siguientes requisitos:
>
> a) Serán de aplicación a este tipo de contratos de seguro los principios de no discriminación, capitalización, irrevocabilidad de aportaciones y atribución de derechos establecidos en el número 1 del artículo 5 del Texto Refundido de la Ley de Regulación de los Planes y Fondos de Pensiones, aprobado por Real Decreto Legislativo 1/2002, de 29 de noviembre.
>
> b) La póliza dispondrá las primas que, en cumplimiento del plan de previsión social, deberá satisfacer el tomador, las cuales serán objeto de imputación a los asegurados.
>
> c) En el condicionado de la póliza se hará constar de forma expresa y destacada que se trata de un plan de previsión social empresarial. La denominación Plan de Previsión Social Empresarial y sus siglas quedan reservadas a los contratos de seguro que cumplan los requisitos previstos en esta Ley.
>
> d) Reglamentariamente se establecerán los requisitos y condiciones para la movilización de la provisión matemática a otro plan de previsión social empresarial.
>
> e) Lo dispuesto en las letras b) y c) del apartado 3 anterior.
>
> En los aspectos no específicamente regulados en los párrafos anteriores y sus normas de desarrollo, resultará de aplicación lo dispuesto en el último párrafo del apartado 3 anterior.
>
> 5. Las primas satisfechas a los seguros privados que cubran exclusivamente el riesgo de dependencia severa o de gran dependencia conforme a lo dispuesto en la Ley de promoción de la autonomía personal y atención a las personas en situación de dependencia.
>
> Igualmente, las personas que tengan con el contribuyente una relación de parentesco en línea directa o colateral hasta el tercer grado inclusive, o por su cónyuge, o por aquellas personas que tuviesen al contribuyente a su cargo en régimen de tutela o acogimiento, podrán reducir en su base imponible las primas satisfechas a estos seguros privados, teniendo en cuenta el límite de reducción previsto en el artículo 52 de esta Ley.
>
> El conjunto de las reducciones practicadas por todas las personas que satisfagan primas a favor de un mismo contribuyente, incluidas las del propio contribuyente, no podrán exceder de 1.500 euros anuales.
>
> Estas primas no estarán sujetas al Impuesto sobre Sucesiones y Donaciones.
>
> El contrato de seguro deberá cumplir en todo caso lo dispuesto en las letras a) y c) del apartado 3 anterior.
>
> En los aspectos no específicamente regulados en los párrafos anteriores y sus normas de desarrollo, resultará de aplicación lo dispuesto en el último párrafo del apartado 3 anterior.
>
> Tratándose de seguros colectivos de dependencia efectuados de acuerdo con lo previsto en la disposición adicional primera del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones, aprobado por el Real Decreto Legislativo 1/2002, de 29 de noviembre, como tomador del seguro figurará exclusivamente la empresa y la condición de asegurado y beneficiario corresponderá al trabajador. Las primas satisfechas por la empresa en virtud de estos contratos de seguro e imputadas al trabajador tendrán un límite de reducción propio e independiente de 5.000 euros anuales.
>
> Reglamentariamente se desarrollará lo previsto en este apartado.
>
> 6. El conjunto de las aportaciones anuales máximas que pueden dar derecho a reducir la base imponible realizadas a los sistemas de previsión social previstos en los apartados 1, 2, 3, 4 y 5 anteriores, incluyendo, en su caso, las que hubiesen sido imputadas por los promotores, no podrá exceder de las cantidades previstas en el artículo 5.3 del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones.
>
> Las prestaciones percibidas tributarán en su integridad sin que en ningún caso puedan minorarse en las cuantías correspondientes a los excesos de las aportaciones y contribuciones.
>
> 7. Además de las reducciones realizadas con los límites previstos en el artículo siguiente, los contribuyentes cuyo cónyuge no obtenga rendimientos netos del trabajo ni de actividades económicas, o los obtenga en cuantía inferior a 8.000 euros anuales, podrán reducir en la base imponible las aportaciones realizadas a los sistemas de previsión social previstos en este artículo de los que sea partícipe, mutualista o titular dicho cónyuge, con el límite máximo de 1.000 euros anuales.
>
> Estas aportaciones no estarán sujetas al Impuesto sobre Sucesiones y Donaciones.
>
> 8. Si el contribuyente dispusiera de los derechos consolidados así como los derechos económicos que se derivan de los diferentes sistemas de previsión social previstos en este artículo, total o parcialmente, en supuestos distintos de los previstos en la normativa de planes y fondos de pensiones, deberá reponer las reducciones en la base imponible indebidamente practicadas, mediante las oportunas autoliquidaciones complementarias, con inclusión de los intereses de demora. Las cantidades percibidas que excedan del importe de las aportaciones realizadas, incluyendo, en su caso, las contribuciones imputadas por el promotor, tributarán como rendimiento del trabajo en el período impositivo en que se perciban.
>
> 9. La reducción prevista en este artículo resultará de aplicación cualquiera que sea la forma en que se perciba la prestación. En el caso de que la misma se perciba en forma de renta vitalicia asegurada, se podrán establecer mecanismos de reversión o períodos ciertos de prestación o fórmulas de contraseguro en caso de fallecimiento una vez constituida la renta vitalicia.
>
> Se modifica el apartado 5, con efectos desde 1 de enero de 2022, por el art. 59.1 de la Ley 22/2021, de 28 de diciembre. Ref. BOE-A-2021-21653
>
> Se modifican los apartados 5 y 7, con efectos desde 1 de enero de 2021, por el art. 62.1 de la Ley 11/2020, de 30 de diciembre. Ref. BOE-A-2020-17339
>
> Se modifican los apartados 3, 5 y 7 por el art. 1.31 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 107 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 5. `ley-35-2006:art-53`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a53`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Reducciones por aportaciones y contribuciones a sistemas de previsión social constituidos a favor de personas con discapacidad"
- `notes` (verbatim): "LIRPF art 53: reducciones de la base imponible general por aportaciones y contribuciones a sistemas de previsión social constituidos a favor de personas con discapacidad. Base legal de las casillas de reducción/exceso por previsión social de personas con discapacidad en Modelo 100 (distinto del patrimonio protegido del art. 54). AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#a53; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a53; operator to re-stamp"

#### Bundled corpus text

> Artículo 53. Reducciones por aportaciones y contribuciones a sistemas de previsión social constituidos a favor de personas con discapacidad.
>
> 1. Las aportaciones realizadas a planes de pensiones a favor de personas con discapacidad con un grado de minusvalía física o sensorial igual o superior al 65 por ciento, psíquica igual o superior al 33 por 100, así como de personas que tengan una incapacidad declarada judicialmente con independencia de su grado, de acuerdo con lo previsto en la disposición adicional décima de esta Ley, podrán ser objeto de reducción en la base imponible con los siguientes límites máximos:
>
> a) Las aportaciones anuales realizadas a planes de pensiones a favor de personas con discapacidad con las que exista relación de parentesco o tutoría, con el límite de 10.000 euros anuales.
>
> Ello sin perjuicio de las aportaciones que puedan realizar a sus propios planes de pensiones, de acuerdo con los límites establecidos en el artículo 52 de esta ley.
>
> b) Las aportaciones anuales realizadas por las personas con discapacidad partícipes, con el límite de 24.250 euros anuales.
>
> El conjunto de las reducciones practicadas por todas las personas que realicen aportaciones a favor de una misma persona con discapacidad, incluidas las de la propia persona con discapacidad, no podrá exceder de 24.250 euros anuales. A estos efectos, cuando concurran varias aportaciones a favor de la persona con discapacidad, habrán de ser objeto de reducción, en primer lugar, las aportaciones realizadas por la propia persona con discapacidad, y sólo si las mismas no alcanzaran el límite de 24.250 euros señalado, podrán ser objeto de reducción las aportaciones realizadas por otras personas a su favor en la base imponible de éstas, de forma proporcional, sin que, en ningún caso, el conjunto de las reducciones practicadas por todas las personas que realizan aportaciones a favor de una misma persona con discapacidad pueda exceder de 24.250 euros.
>
> c) Las aportaciones que no hubieran podido ser objeto de reducción en la base imponible por insuficiencia de la misma podrán reducirse en los cinco ejercicios siguientes. Esta regla no resultará de aplicación a las aportaciones y contribuciones que excedan de los límites previstos en este apartado 1.
>
> 2. El régimen regulado en este artículo también será de aplicación a las aportaciones a mutualidades de previsión social, a las primas satisfechas a los planes de previsión asegurados, a los planes de previsión social empresarial y a los seguros de dependencia que cumplan los requisitos previstos en el artículo 51 y en la disposición adicional décima de esta ley. En tal caso, los límites establecidos en el apartado 1 anterior serán conjuntos para todos los sistemas de previsión social constituidos a favor de personas con discapacidad.
>
> 3. Las aportaciones a estos sistemas de previsión social constituidos a favor de personas con discapacidad, realizadas por las personas a las que se refiere el apartado 1 de la disposición adicional décima de esta ley, no estarán sujetas al Impuesto sobre Sucesiones y Donaciones.
>
> 4. A los efectos de la percepción de las prestaciones y de la disposición anticipada de derechos consolidados o económicos en supuestos distintos de los previstos en la disposición adicional décima de esta Ley, se aplicará lo dispuesto en los apartados 8 y 9 del artículo 51 de esta Ley.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 8 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 6. `ley-35-2006:art-54`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a54`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Reducciones por aportaciones a patrimonios protegidos de las personas con discapacidad"
  - "en caso de fallecimiento del titular del patrimonio protegido, del aportante o de los trabajadores"
- `notes` (verbatim): "LIRPF art 54: reducciones de la base imponible general por aportaciones a patrimonios protegidos de las personas con discapacidad (límite 10.000 € por aportante, 24.250 € conjunto). Base legal de las casillas de reducción/exceso por patrimonio protegido en Modelo 100. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#a54; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a54; operator to re-stamp"

#### Bundled corpus text

> Artículo 54. Reducciones por aportaciones a patrimonios protegidos de las personas con discapacidad.
>
> 1. Las aportaciones al patrimonio protegido de la persona con discapacidad efectuadas por las personas que tengan con el mismo una relación de parentesco en línea directa o colateral hasta el tercer grado inclusive, así como por el cónyuge de la persona con discapacidad o por aquellos que lo tuviesen a su cargo en régimen de tutela o acogimiento, darán derecho a reducir la base imponible del aportante, con el límite máximo de 10.000 euros anuales.
>
> El conjunto de las reducciones practicadas por todas las personas que efectúen aportaciones a favor de un mismo patrimonio protegido no podrá exceder de 24.250 euros anuales.
>
> A estos efectos, cuando concurran varias aportaciones a favor de un mismo patrimonio protegido, las reducciones correspondientes a dichas aportaciones habrán de ser minoradas de forma proporcional sin que, en ningún caso, el conjunto de las reducciones practicadas por todas las personas físicas que realicen aportaciones a favor de un mismo patrimonio protegido pueda exceder de 24.250 euros anuales.
>
> 2. Las aportaciones que excedan de los límites previstos en el apartado anterior darán derecho a reducir la base imponible de los cuatro períodos impositivos siguientes, hasta agotar, en su caso, en cada uno de ellos los importes máximos de reducción.
>
> Lo dispuesto en el párrafo anterior también resultará aplicable en los supuestos en que no proceda la reducción por insuficiencia de base imponible.
>
> Cuando concurran en un mismo período impositivo reducciones de la base imponible por aportaciones efectuadas en el ejercicio con reducciones de ejercicios anteriores pendientes de aplicar, se practicarán en primer lugar las reducciones procedentes de los ejercicios anteriores, hasta agotar los importes máximos de reducción.
>
> 3. Tratándose de aportaciones no dinerarias se tomará como importe de la aportación el que resulte de lo previsto en el artículo 18 de la Ley 49/2002, de 23 de diciembre, de régimen fiscal de las entidades sin fines lucrativos y de los incentivos fiscales al mecenazgo.
>
> 4. No generarán el derecho a reducción las aportaciones de elementos afectos a la actividad que efectúen los contribuyentes de este Impuesto que realicen actividades económicas.
>
> En ningún caso darán derecho a reducción las aportaciones efectuadas por la propia persona con discapacidad titular del patrimonio protegido.
>
> 5. La disposición de cualquier bien o derecho aportado al patrimonio protegido de la persona con discapacidad efectuada en el período impositivo en que se realiza la aportación o en los cuatro siguientes tendrá las siguientes consecuencias fiscales:
>
> a) Si el aportante fue un contribuyente por este Impuesto, deberá reponer las reducciones en la base imponible indebidamente practicadas mediante la presentación de la oportuna autoliquidación complementaria con inclusión de los intereses de demora que procedan, en el plazo que medie entre la fecha en que se produzca la disposición y la finalización del plazo reglamentario de declaración correspondiente al período impositivo en que se realice dicha disposición.
>
> b) El titular del patrimonio protegido que recibió la aportación deberá integrar en la base imponible la parte de la aportación recibida que hubiera dejado de integrar en el período impositivo en que recibió la aportación como consecuencia de la aplicación de lo dispuesto en la letra w) del artículo 7 de esta Ley, mediante la presentación de la oportuna autoliquidación complementaria con inclusión de los intereses de demora que procedan, en el plazo que medie entre la fecha en que se produzca la disposición y la finalización del plazo reglamentario de declaración correspondiente al período impositivo en que se realice dicha disposición.
>
> En los casos en que la aportación se hubiera realizado al patrimonio protegido de los parientes, cónyuges o personas a cargo de los trabajadores en régimen de tutela o acogimiento, a que se refiere el apartado 1 de este artículo, por un sujeto pasivo del Impuesto sobre Sociedades, la obligación descrita en el párrafo anterior deberá ser cumplida por dicho trabajador.
>
> c) A los efectos de lo dispuesto en el apartado 5 del artículo 43 del texto refundido de la Ley del Impuesto sobre Sociedades, el trabajador titular del patrimonio protegido deberá comunicar al empleador que efectuó las aportaciones, las disposiciones que se hayan realizado en el período impositivo.
>
> En los casos en que la disposición se hubiera efectuado en el patrimonio protegido de los parientes, cónyuges o personas a cargo de los trabajadores en régimen de tutela o acogimiento, la comunicación a que se refiere el párrafo anterior también deberá efectuarla dicho trabajador.
>
> La falta de comunicación o la realización de comunicaciones falsas, incorrectas o inexactas constituirá infracción tributaria leve. Esta infracción se sancionará con multa pecuniaria fija de 400 euros.
>
> La sanción impuesta de acuerdo con lo previsto en este apartado se reducirá conforme a lo dispuesto en el apartado 3 del artículo 188 de la Ley 58/2003, de 17 de diciembre, General Tributaria.
>
> A los efectos previstos en este apartado, tratándose de bienes o derechos homogéneos se entenderá que fueron dispuestos los aportados en primer lugar.
>
> No se aplicará lo dispuesto en este apartado en caso de fallecimiento del titular del patrimonio protegido, del aportante o de los trabajadores a los que se refiere el apartado 2 del artículo 43 del texto refundido de la Ley del Impuesto sobre Sociedades.
>
> CAPÍTULO II
>
> Reducción por pensiones compensatorias

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 24 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 7. `ley-35-2006:art-55`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a55`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Reducciones por pensiones compensatorias"
- `notes` (verbatim): "LIRPF art 55: reducciones de la base imponible por pensiones compensatorias satisfechas al cónyuge y anualidades por alimentos (salvo las fijadas a favor de los hijos) por decisión judicial. Base legal de las casillas de reducción por pensiones compensatorias y anualidades por alimentos en Modelo 100. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#a55; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a55; operator to re-stamp"

#### Bundled corpus text

> Artículo 55. Reducciones por pensiones compensatorias.
>
> Las pensiones compensatorias a favor del cónyuge y las anualidades por alimentos, con excepción de las fijadas en favor de los hijos del contribuyente, satisfechas ambas por decisión judicial, podrán ser objeto de reducción en la base imponible.
>
> TÍTULO V
>
> Adecuación del impuesto a las circunstancias personales y familiares del contribuyente

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 3 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 8. `ley-35-2006:art-58-1`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a58`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "no tenga rentas anuales, excluidas las exentas, superiores a 8.000 euros, de:"
- `notes` (verbatim): "LIRPF art 58.1: the rentas ceiling conditioning the minimo por descendientes. A descendant generates the minimo only when, besides being under 25 (or carrying any discapacidad) and cohabiting, the descendant does not hold rentas anuales, excluidas las exentas, superiores a 8.000 euros. This entry grounds the 8.000-euro CEILING specifically, which the parent ley-35-2006:art-58 entry does not pin (its required_text covers only the tranche amounts). The required_text ends at the ', de:' that introduces the tranche list, which is what separates this clause from art 61 norma 1a's grado-de-parentesco tie-break -- that clause carries the SAME 8.000-euro figure but applies it to the CLAIMANT rather than the descendant, and reads 'no tengan ... en cuyo caso'. Confirmed present in the art-58 unit and absent from the art-61 unit. AGENT-AUTHORED, grounded in the bundled authoritative consolidated ley-35-2006.html#a58 (redaccion Ley 26/2014, en vigor 01/01/2015, unamended since); operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a58; operator to re-stamp"

#### Bundled corpus text

> Artículo 58. Mínimo por descendientes.
>
> 1. El mínimo por descendientes será, por cada uno de ellos menor de veinticinco años o con discapacidad cualquiera que sea su edad, siempre que conviva con el contribuyente y no tenga rentas anuales, excluidas las exentas, superiores a 8.000 euros, de:
>
> 2.400 euros anuales por el primero.
>
> 2.700 euros anuales por el segundo.
>
> 4.000 euros anuales por el tercero.
>
> 4.500 euros anuales por el cuarto y siguientes.
>
> A estos efectos, se asimilarán a los descendientes aquellas personas vinculadas al contribuyente por razón de tutela y acogimiento, en los términos previstos en la legislación civil aplicable. Asimismo, se asimilará a la convivencia con el contribuyente, la dependencia respecto de este último salvo cuando resulte de aplicación lo dispuesto en los artículos 64 y 75 de esta Ley.
>
> 2. Cuando el descendiente sea menor de tres años, el mínimo a que se refiere el apartado 1 anterior se aumentará en 2.800 euros anuales.
>
> En los supuestos de adopción o acogimiento, tanto preadoptivo como permanente, dicho aumento se producirá, con independencia de la edad del menor, en el período impositivo en que se inscriba en el Registro Civil y en los dos siguientes. Cuando la inscripción no sea necesaria, el aumento se podrá practicar en el período impositivo en que se produzca la resolución judicial o administrativa correspondiente y en los dos siguientes.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 6 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-04`.

### 9. `ley-35-2006:art-60`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a60`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Mínimo por discapacidad"
  - "3.000 euros anuales cuando sea una persona con discapacidad"
  - "9.000 euros anuales"
- `notes` (verbatim): "LIRPF art 60: minimo por discapacidad. Del contribuyente: 3.000 euros (discapacidad grado >=33%<65%), 9.000 euros (grado >=65%); +3.000 euros en concepto de gastos de asistencia (ayuda de terceras personas, movilidad reducida, o grado >=65%). De ascendientes o descendientes con discapacidad: 3.000 euros por cada uno (>=33%), 9.000 euros (>=65%); +3.000 euros gastos de asistencia. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#a60; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a60; operator to re-stamp"

#### Bundled corpus text

> Artículo 60. Mínimo por discapacidad.
>
> El mínimo por discapacidad será la suma del mínimo por discapacidad del contribuyente y del mínimo por discapacidad de ascendientes y descendientes.
>
> 1. El mínimo por discapacidad del contribuyente será de 3.000 euros anuales cuando sea una persona con discapacidad y 9.000 euros anuales cuando sea una persona con discapacidad y acredite un grado de discapacidad igual o superior al 65 por ciento.
>
> Dicho mínimo se aumentará, en concepto de gastos de asistencia, en 3.000 euros anuales cuando acredite necesitar ayuda de terceras personas o movilidad reducida, o un grado de discapacidad igual o superior al 65 por ciento.
>
> 2. El mínimo por discapacidad de ascendientes o descendientes será de 3.000 euros anuales por cada uno de los descendientes o ascendientes que generen derecho a la aplicación del mínimo a que se refieren los artículos 58 y 59 de esta Ley, que sean personas con discapacidad, cualquiera que sea su edad. El mínimo será de 9.000 euros anuales, por cada uno de ellos que acrediten un grado de discapacidad igual o superior al 65 por ciento.
>
> Dicho mínimo se aumentará, en concepto de gastos de asistencia, en 3.000 euros anuales por cada ascendiente o descendiente que acredite necesitar ayuda de terceras personas o movilidad reducida, o un grado de discapacidad igual o superior al 65 por ciento.
>
> 3. A los efectos de este Impuesto, tendrán la consideración de personas con discapacidad los contribuyentes que acrediten, en las condiciones que reglamentariamente se establezcan, un grado de discapacidad igual o superior al 33 por ciento.
>
> En particular, se considerará acreditado un grado de discapacidad igual o superior al 33 por ciento en el caso de los pensionistas de la Seguridad Social que tengan reconocida una pensión de incapacidad permanente total, absoluta o gran invalidez y en el caso de los pensionistas de clases pasivas que tengan reconocida una pensión de jubilación o retiro por incapacidad permanente para el servicio o inutilidad. Igualmente, se considerará acreditado un grado de discapacidad igual o superior al 65 por ciento, cuando se trate de personas cuya incapacidad sea declarada judicialmente, aunque no alcance dicho grado.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 2 binding(s); 2 casilla(s); 1 construct(s); 18 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-14`.

### 10. `ley-35-2006:art-61`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-61.html#a61`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "su importe se prorrateará entre ellos por partes iguales"
- `notes` (verbatim): "LIRPF art 61: normas comunes para la aplicacion del minimo del contribuyente y por descendientes, ascendientes y discapacidad. Norma 1a: cuando dos o mas contribuyentes tengan derecho al minimo por descendientes, ascendientes o discapacidad respecto de los mismos ascendientes o descendientes, su importe se prorrateara entre ellos por partes iguales -- the custodia-compartida 50% prorrata applied to Modelo 100 casillas 0513/0514. Norma 4a fixes a reduced amount on a mid-year death (unrelated to entry timing); norma 5a's half-period residency rule is scoped to ascendientes only. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#a61 (en vigor 01/01/2015); operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a61; operator to re-stamp"

#### Bundled corpus text

> Artículo 61. Normas comunes para la aplicación del mínimo del contribuyente y por descendientes, ascendientes y discapacidad.
>
> Para la determinación del importe de los mínimos a que se refieren los artículos 57, 58, 59 y 60 de esta Ley, se tendrán en cuenta las siguientes normas:
>
> 1.ª Cuando dos o más contribuyentes tengan derecho a la aplicación del mínimo por descendientes, ascendientes o discapacidad, respecto de los mismos ascendientes o descendientes, su importe se prorrateará entre ellos por partes iguales.
>
> No obstante, cuando los contribuyentes tengan distinto grado de parentesco con el ascendiente o descendiente, la aplicación del mínimo corresponderá a los de grado más cercano, salvo que éstos no tengan rentas anuales, excluidas las exentas, superiores a 8.000 euros, en cuyo caso corresponderá a los del siguiente grado.
>
> 2.ª No procederá la aplicación del mínimo por descendientes, ascendientes o discapacidad, cuando los ascendientes o descendientes que generen el derecho a los mismos presenten declaración por este Impuesto con rentas superiores a 1.800 euros.
>
> 3.ª La determinación de las circunstancias personales y familiares que deban tenerse en cuenta a efectos de lo establecido en los artículos 57, 58, 59 y 60 de esta Ley, se realizará atendiendo a la situación existente en la fecha de devengo del Impuesto.
>
> 4.ª No obstante lo dispuesto en el apartado anterior, en caso de fallecimiento de un descendiente o ascendiente que genere el derecho al mínimo por descendientes o ascendientes, la cuantía será de 2.400 euros anuales o 1.150 euros anuales por ese descendiente o ascendiente, respectivamente.
>
> 5.ª Para la aplicación del mínimo por ascendientes, será necesario que éstos convivan con el contribuyente, al menos, la mitad del período impositivo o, en el caso de fallecimiento del ascendiente antes de la finalización de este, la mitad del período transcurrido entre el inicio del período impositivo y la fecha de fallecimiento.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 12 binding(s); 2 casilla(s); 1 construct(s); 12 formula(s); 12 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-02`.

### 11. `ley-35-2006:art-61-norma-2`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a61`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "presenten declaración por este Impuesto con rentas superiores a 1.800 euros"
- `notes` (verbatim): "LIRPF art 61 norma 2a: the own-return exclusion. The minimo does not apply at all when the ascendiente or descendiente who generates the entitlement files their own declaracion for this Impuesto with rentas superiores a 1.800 euros. This is an exclusion threshold on the DEPENDANT's own filing, distinct from art 58.1's 8.000-euro rentas ceiling, and distinct from norma 1a's prorrateo which the parent ley-35-2006:art-61 entry already pins. The 1.800-euro figure is pinned verbatim here because the parent entry's required_text covers only the norma 1a prorrateo clause. SCOPE, and read this before authoring anything adjacent: the clause governs THREE minimos in one sentence -- 'No procedera la aplicacion del minimo por descendientes, ascendientes o discapacidad' -- so this entry is the single authority for all three, not a descendientes-only entry. Only the descendientes predicate consumes it today, and the per-year parameters are named 'minimo-descendientes-declaracion-propia-rentas-limite' after that first consumer rather than after the clause's reach; ascendientes and discapacidad are currently bare manual inputs with no formula and no binding, so nothing is incomplete. Whoever builds an ascendientes or discapacidad predicate MUST cite this entry and reuse the existing 1.800 parameter rather than minting a second legal entry and a second parameter for the same clause and the same figure -- one clause, one authority, one figure. AGENT-AUTHORED, grounded in the bundled authoritative consolidated ley-35-2006.html#a61 (redaccion Ley 26/2014, en vigor 01/01/2015, unamended since); operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a61; operator to re-stamp"

#### Bundled corpus text

> Artículo 61. Normas comunes para la aplicación del mínimo del contribuyente y por descendientes, ascendientes y discapacidad.
>
> Para la determinación del importe de los mínimos a que se refieren los artículos 57, 58, 59 y 60 de esta Ley, se tendrán en cuenta las siguientes normas:
>
> 1.ª Cuando dos o más contribuyentes tengan derecho a la aplicación del mínimo por descendientes, ascendientes o discapacidad, respecto de los mismos ascendientes o descendientes, su importe se prorrateará entre ellos por partes iguales.
>
> No obstante, cuando los contribuyentes tengan distinto grado de parentesco con el ascendiente o descendiente, la aplicación del mínimo corresponderá a los de grado más cercano, salvo que éstos no tengan rentas anuales, excluidas las exentas, superiores a 8.000 euros, en cuyo caso corresponderá a los del siguiente grado.
>
> 2.ª No procederá la aplicación del mínimo por descendientes, ascendientes o discapacidad, cuando los ascendientes o descendientes que generen el derecho a los mismos presenten declaración por este Impuesto con rentas superiores a 1.800 euros.
>
> 3.ª La determinación de las circunstancias personales y familiares que deban tenerse en cuenta a efectos de lo establecido en los artículos 57, 58, 59 y 60 de esta Ley, se realizará atendiendo a la situación existente en la fecha de devengo del Impuesto.
>
> 4.ª No obstante lo dispuesto en el apartado anterior, en caso de fallecimiento de un descendiente o ascendiente que genere el derecho al mínimo por descendientes o ascendientes, la cuantía será de 2.400 euros anuales o 1.150 euros anuales por ese descendiente o ascendiente, respectivamente.
>
> 5.ª Para la aplicación del mínimo por ascendientes, será necesario que éstos convivan con el contribuyente, al menos, la mitad del período impositivo o, en el caso de fallecimiento del ascendiente antes de la finalización de este, la mitad del período transcurrido entre el inicio del período impositivo y la fecha de fallecimiento.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 6 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-04`.

### 12. `ley-35-2006:art-61-norma-4`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a61`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "en caso de fallecimiento de un descendiente o ascendiente que genere el derecho al mínimo"
  - "la cuantía será de 2.400 euros anuales o 1.150 euros anuales"
- `notes` (verbatim): "LIRPF art 61 norma 4a: the death-in-period flat cuantia. Displacing norma 3a's devengo-date rule, a descendiente or ascendiente who dies during the periodo impositivo and generates the entitlement takes a FLAT 2.400 euros (descendiente) or 1.150 euros (ascendiente) instead of the amount that would otherwise correspond. SCOPE, read this before authoring anything adjacent: one clause fixes BOTH figures, so this entry is the single authority for the descendientes AND the ascendientes death amount, not a descendientes-only entry. Only the descendientes figure is parameterised today (renta-{year}-minimo-descendientes-fallecimiento-{year}); whoever wires the ascendientes minimo MUST cite this same entry and mint a SIBLING parameter under an ascendientes stem for the 1.150 figure -- NOT a second value on the descendientes parameter, whose id is descendientes-specific -- rather than authoring a second legal entry for the same clause. One clause, one legal authority, two parameters. The 2.400 descendientes figure COINCIDES with art 58.1's first-child tranche but is a legally DISTINCT figure: it is fixed here, applies at any birth order, and would not move if a reform moved the tranche, so the two must never share a parameter. CAUTION, the clause is only half the rule as the AEAT Renta manual applies it: the manual's 'Minimo por descendientes / Cuantias aplicables' section restates this flat amount AND adds the ordering limb -- the number of orden is assigned by age 'sin computar a estos efectos aquellos descendientes que, en su caso, hubieran fallecido en el ejercicio con anterioridad a la fecha de devengo del impuesto' -- which has no counterpart in the statutory text of norma 4a and is grounded on the manual source instead. Omitting that second limb over-grants every younger sibling by leaving them at a rank the deceased should have vacated. AGENT-AUTHORED, grounded in the bundled authoritative consolidated ley-35-2006.html#a61 (redaccion Ley 26/2014, en vigor 01/01/2015, unamended since; norma 4a last modified by Ley 39/2010 art 61.5 with effect 01/01/2011 and then by Ley 26/2014); operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a61; operator to re-stamp"

#### Bundled corpus text

> Artículo 61. Normas comunes para la aplicación del mínimo del contribuyente y por descendientes, ascendientes y discapacidad.
>
> Para la determinación del importe de los mínimos a que se refieren los artículos 57, 58, 59 y 60 de esta Ley, se tendrán en cuenta las siguientes normas:
>
> 1.ª Cuando dos o más contribuyentes tengan derecho a la aplicación del mínimo por descendientes, ascendientes o discapacidad, respecto de los mismos ascendientes o descendientes, su importe se prorrateará entre ellos por partes iguales.
>
> No obstante, cuando los contribuyentes tengan distinto grado de parentesco con el ascendiente o descendiente, la aplicación del mínimo corresponderá a los de grado más cercano, salvo que éstos no tengan rentas anuales, excluidas las exentas, superiores a 8.000 euros, en cuyo caso corresponderá a los del siguiente grado.
>
> 2.ª No procederá la aplicación del mínimo por descendientes, ascendientes o discapacidad, cuando los ascendientes o descendientes que generen el derecho a los mismos presenten declaración por este Impuesto con rentas superiores a 1.800 euros.
>
> 3.ª La determinación de las circunstancias personales y familiares que deban tenerse en cuenta a efectos de lo establecido en los artículos 57, 58, 59 y 60 de esta Ley, se realizará atendiendo a la situación existente en la fecha de devengo del Impuesto.
>
> 4.ª No obstante lo dispuesto en el apartado anterior, en caso de fallecimiento de un descendiente o ascendiente que genere el derecho al mínimo por descendientes o ascendientes, la cuantía será de 2.400 euros anuales o 1.150 euros anuales por ese descendiente o ascendiente, respectivamente.
>
> 5.ª Para la aplicación del mínimo por ascendientes, será necesario que éstos convivan con el contribuyente, al menos, la mitad del período impositivo o, en el caso de fallecimiento del ascendiente antes de la finalización de este, la mitad del período transcurrido entre el inicio del período impositivo y la fecha de fallecimiento.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 6 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-05`.

### 13. `ley-35-2006:art-63-2015`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006-art-63-2015.html#a63`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Escala general del Impuesto."
  - "base liquidable general que exceda del importe del mínimo personal y familiar"
  - "A la base liquidable general se le aplicarán los tipos"
  - "se minorará en el importe derivado de aplicar"
  - "tipo medio de gravamen general estatal"
- `notes` (verbatim): "LIRPF art 63, redaction selected by BOE at 2014-11-28 (art. 1.39 Ley 26/2014, BOE-A-2014-12327), in force 2015-01-01 to 2020-12-31: five-bracket state general scale (9,50/12,00/15,00/18,50/22,50 percent up to 12.450/20.200/35.200/60.000/en adelante euros), before Ley 11/2020 art. 58 added a sixth bracket (24,50 percent above 300.000 euros) with effect from 2021-01-01; brackets below 300.000 euros are numerically unchanged by that amendment. Grounds the 2020 Modelo 100 escala general estatal parameter (renta-2020-escala-estatal-base-general) and its dependent cuota-íntegra-estatal formulas — the stored 2020 bracket values were independently verified against this redaction and are unaffected by the citation correction."
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
> En adelante
>
> 22,50
>
> 2.º La cuantía resultante se minorará en el importe derivado de aplicar a la parte de la base liquidable general correspondiente al mínimo personal y familiar, la escala prevista en el número 1.º anterior.
>
> 2. Se entenderá por tipo medio de gravamen general estatal el derivado de multiplicar por 100 el cociente resultante de dividir la cuota obtenida por la aplicación de lo previsto en el apartado anterior por la base liquidable general. El tipo medio de gravamen general estatal se expresará con dos decimales.
>
> Se modifica el apartado 1 por el art. 1.39 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Se modifica el apartado 1, con efectos desde 1 de enero de 2011, por el art. 62.1 de la Ley 39/2010, de 22 de diciembre. Ref. BOE-A-2010-19703.
>
> Se modifica el apartado 1, con vigencia exclusiva para el ejercicio 2010 por el art. 68.1 de la Ley 26/2009, de 23 de diciembre. Ref. BOE-A-2009-20765
>
> Se modifica por la disposición final 2.4 de la Ley 22/2009, de 18 de diciembre. Ref. BOE-A-2009-20375
>
> Esta modificación entra en vigor y surte efectos desde el 1 de enero de 2010, según establece la disposición final 5.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020. 15 casilla(s); 2 construct(s); 7 formula(s); 1 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-02`.

### 14. `ley-35-2006:art-64`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a64`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "anualidades por alimentos a favor de los hijos"
- `notes` (verbatim): "LIRPF art 64: especialidades aplicables en los supuestos de anualidades por alimentos a favor de los hijos satisfechas por decisión judicial — la escala se aplica separadamente al importe de las anualidades y al resto de la base liquidable general. Base legal de las casillas de anualidades por alimentos en Modelo 100 (junto con el art. 75 para la parte autonómica). AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#a64; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a64; operator to re-stamp"

#### Bundled corpus text

> Artículo 64. Especialidades aplicables en los supuestos de anualidades por alimentos a favor de los hijos.
>
> Los contribuyentes que satisfagan las anualidades por alimentos a sus hijos previstas en la letra k) del artículo 7 sin derecho a la aplicación por estos últimos del mínimo por descendientes previsto en el artículo 58, cuando el importe de aquellas sea inferior a la base liquidable general, aplicarán la escala prevista en el número 1.º del apartado 1 del artículo 63 separadamente al importe de las anualidades por alimentos y al resto de la base liquidable general. La cuantía total resultante se minorará en el importe derivado de aplicar la escala prevista en el número 1.º del apartado 1 del artículo 63, a la parte de la base liquidable general correspondiente al mínimo personal y familiar incrementado en 1.980 euros anuales, sin que pueda resultar negativa como consecuencia de tal minoración.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 7 binding(s); 34 casilla(s); 8 construct(s); 22 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 15. `ley-35-2006:art-7`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a7`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Rentas exentas"
  - "trabajos efectivamente realizados en el extranjero"
  - "límite máximo de 60.100 euros anuales"
- `notes` (verbatim): "LIRPF art 7: rentas exentas, including art 7.p foreign-work exemption and its 60.100 EUR annual cap. Base legal de las casillas informativas de rentas exentas (importes que no se integran en la base imponible) del Modelo 100 and the maritime worker Art. 7.p exemption. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#a7; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a7; operator to re-stamp"

#### Bundled corpus text

> Artículo 7. Rentas exentas.
>
> Estarán exentas las siguientes rentas:
>
> a) Las prestaciones públicas extraordinarias por actos de terrorismo y las pensiones derivadas de medallas y condecoraciones concedidas por actos de terrorismo.
>
> b) Las ayudas de cualquier clase percibidas por los afectados por el virus de inmunodeficiencia humana, reguladas en el Real Decreto-Ley 9/1993, de 28 de mayo.
>
> c) Las pensiones reconocidas en favor de aquellas personas que sufrieron lesiones o mutilaciones con ocasión o como consecuencia de la Guerra Civil, 1936/1939, ya sea por el régimen de clases pasivas del Estado o al amparo de la legislación especial dictada al efecto.
>
> d) Las indemnizaciones como consecuencia de responsabilidad civil por daños personales, en la cuantía legal o judicialmente reconocida.
>
> Asimismo, las indemnizaciones como consecuencia de responsabilidad civil por daños físicos o psíquicos, satisfechos por la entidad aseguradora del causante del daño no previstas en el párrafo anterior, cuando deriven de un acuerdo de mediación o de cualquier otro medio adecuado de solución de controversias legalmente establecido, siempre que en la obtención del acuerdo por ese medio haya intervenido un tercero neutral y el acuerdo se haya elevado a escritura pública, hasta la cuantía que resulte de aplicar, para el daño sufrido, el sistema para la valoración de los daños y perjuicios causados a las personas en accidentes de circulación, incorporado como anexo en el texto refundido de la Ley sobre responsabilidad civil y seguro en la circulación de vehículos a motor, aprobado por el Real Decreto Legislativo 8/2004, de 29 de octubre.
>
> Igualmente estarán exentas las indemnizaciones por daños personales derivadas de contratos de seguro de accidentes, salvo aquellos cuyas primas hubieran podido reducir la base imponible o ser consideradas gasto deducible por aplicación de la regla 1.ª del apartado 2 del artículo 30 de esta ley, hasta la cuantía que resulte de aplicar, para el daño sufrido, el sistema para la valoración de los daños y perjuicios causados a las personas en accidentes de circulación, incorporado como anexo en el texto refundido de la Ley sobre responsabilidad civil y seguro en la circulación de vehículos a motor, aprobado por el Real Decreto Legislativo 8/2004, de 29 de octubre.
>
> e) Las indemnizaciones por despido o cese del trabajador, en la cuantía establecida con carácter obligatorio en el texto refundido de la Ley del Estatuto de los Trabajadores, aprobado por el Real Decreto Legislativo 2/2015, de 23 de octubre, en su normativa de desarrollo o, en su caso, en la normativa reguladora de la ejecución de sentencias, sin que pueda considerarse como tal la establecida en virtud de convenio, pacto o contrato.
>
> Sin perjuicio de lo dispuesto en el párrafo anterior, en los supuestos de despidos colectivos realizados, o cuando se extinga el contrato en el supuesto de la letra c) del artículo 52 del mismo texto, siempre que, en ambos casos, se deban a causas económicas, técnicas, organizativas, de producción o por fuerza mayor, quedará exenta la parte de indemnización percibida que no supere los límites establecidos con carácter obligatorio en el mencionado Estatuto para el despido improcedente.
>
> No tendrán la consideración de indemnizaciones establecidas en virtud de convenio, pacto o contrato, las acordadas en el acto de conciliación ante el Servicio administrativo al que se refiere el artículo 63 de la Ley 36/2011, de 10 de octubre, reguladora de la jurisdicción social.
>
> El importe de la indemnización exenta a que se refiere esta letra tendrá como límite la cantidad de 180.000 euros.
>
> f) Las prestaciones reconocidas al contribuyente por la Seguridad Social o por las entidades que la sustituyan como consecuencia de incapacidad permanente absoluta o gran invalidez.
>
> Asimismo, las prestaciones reconocidas a los profesionales no integrados en el régimen especial de la Seguridad Social de los trabajadores por cuenta propia o autónomos por las mutualidades de previsión social que actúen como alternativas al régimen especial de la Seguridad Social mencionado, siempre que se trate de prestaciones en situaciones idénticas a las previstas para la incapacidad permanente absoluta o gran invalidez de la Seguridad Social. La cuantía exenta tendrá como límite el importe de la prestación máxima que reconozca la Seguridad Social por el concepto que corresponda. El exceso tributará como rendimiento del trabajo, entendiéndose producido, en caso de concurrencia de prestaciones de la Seguridad Social y de las mutualidades antes citadas, en las prestaciones de estas últimas.
>
> g) Las pensiones por inutilidad o incapacidad permanente del régimen de clases pasivas, siempre que la lesión o enfermedad que hubiera sido causa de aquéllas inhabilitara por completo al perceptor de la pensión para toda profesión u oficio.
>
> h) Las prestaciones por maternidad o paternidad y las familiares no contributivas reguladas, respectivamente, en los Capítulos VI y VII del Título II y en el Capítulo I del título VI del texto refundido de la Ley General de la Seguridad Social, aprobado por el Real Decreto Legislativo 8/2015, de 30 de octubre y las pensiones y los haberes pasivos de orfandad y a favor de nietos y hermanos, menores de veintidós años o incapacitados para todo trabajo, percibidos de los regímenes públicos de la Seguridad Social y clases pasivas.
>
> Asimismo, las prestaciones reconocidas a los profesionales no integrados en el régimen especial de la Seguridad Social de los trabajadores por cuenta propia o autónomos por las mutualidades de previsión social que actúen como alternativas al régimen especial de la Seguridad Social mencionado, siempre que se trate de prestaciones en situaciones idénticas a las previstas en el párrafo anterior por la Seguridad Social para los profesionales integrados en dicho régimen especial. La cuantía exenta tendrá como límite el importe de la prestación máxima que reconozca la Seguridad Social por el concepto que corresponda. El exceso tributará como rendimiento del trabajo, entendiéndose producido, en caso de concurrencia de prestaciones de la Seguridad Social y de las mutualidades antes citadas, en las prestaciones de estas últimas.
>
> En el caso de los empleados públicos encuadrados en un régimen de Seguridad Social que no de derecho a percibir la prestación por maternidad o paternidad a que se refiere el primer párrafo de esta letra, estará exenta la retribución percibida durante los permisos por parto, adopción o guarda y paternidad a que se refieren las letras a), b) y c) del artículo 49 del texto refundido de la Ley del Estatuto Básico del Empleado Público, aprobado por el Real Decreto Legislativo 5/2015, de 30 de octubre o la reconocida por la legislación específica que le resulte de aplicación por situaciones idénticas a las previstas anteriormente. La cuantía exenta de las retribuciones o prestaciones referidas en este párrafo tendrá como límite el importe de la prestación máxima que reconozca la Seguridad Social por el concepto que corresponda. El exceso tributará como rendimiento del trabajo.
>
> Igualmente estarán exentas las demás prestaciones públicas por nacimiento, parto o adopción múltiple, adopción, maternidad o paternidad, hijos a cargo y orfandad.
>
> i) Las prestaciones económicas percibidas de instituciones públicas con motivo del acogimiento de personas con discapacidad, mayores de 65 años o menores, sea en la modalidad simple, permanente o preadoptivo o las equivalentes previstas en los ordenamientos de las Comunidades Autónomas, incluido el acogimiento en la ejecución de la medida judicial de convivencia del menor con persona o familia previsto en la Ley Orgánica 5/2000, de 12 de enero, reguladora de la responsabilidad penal de los menores.
>
> Igualmente estarán exentas las ayudas económicas otorgadas por instituciones públicas a personas con discapacidad con un grado de minusvalía igual o superior al 65 por ciento o mayores de 65 años para financiar su estancia en residencias o centros de día, siempre que el resto de sus rentas no excedan del doble del indicador público de renta de efectos múltiples.
>
> j) Las becas públicas, las becas concedidas por las entidades sin fines lucrativos a las que sea de aplicación el régimen especial regulado en el Título II de la Ley 49/2002, de 23 de diciembre, de régimen fiscal de las entidades sin fines lucrativos y de los incentivos fiscales al mecenazgo, y las becas concedidas por las fundaciones bancarias reguladas en el Título II de la Ley 26/2013, de 27 de diciembre, de cajas de ahorros y fundaciones bancarias en el desarrollo de su actividad de obra social, percibidas para cursar estudios reglados, tanto en España como en el extranjero, en todos los niveles y grados del sistema educativo, en los términos que reglamentariamente se establezcan.
>
> Asimismo estarán exentas, en los términos que reglamentariamente se establezcan, las becas públicas y las concedidas por las entidades sin fines lucrativos y fundaciones bancarias mencionadas anteriormente para investigación en el ámbito descrito por el Real Decreto 63/2006, de 27 de enero, por el que se aprueba el Estatuto del personal investigador en formación, así como las otorgadas por aquellas con fines de investigación a los funcionarios y demás personal al servicio de las Administraciones públicas y al personal docente e investigador de las universidades.
>
> k) Las anualidades por alimentos percibidas de los padres en virtud del convenio regulador a que se refiere el artículo 90 del Código Civil, o del convenio equivalente previsto en los ordenamientos de las Comunidades Autónomas, aprobado por la autoridad judicial o formalizado ante el letrado o letrada de la Administración de Justicia, o en escritura pública ante notario, con independencia de que dicho convenio derive o no de cualquier medio adecuado de solución de controversias legalmente previsto.
>
> Igualmente estarán exentas las anualidades por alimentos percibidas de los padres en virtud de decisión judicial en supuestos distintos a los establecidos en el párrafo anterior.
>
> l) Los premios literarios, artísticos o científicos relevantes, con las condiciones que reglamentariamente se determinen, así como los premios «Príncipe de Asturias», en sus distintas modalidades, otorgados por la Fundación Príncipe de Asturias.
>
> m) Las ayudas de contenido económico a los deportistas de alto nivel ajustadas a los programas de preparación establecidos por el Consejo Superior de Deportes con las federaciones deportivas españolas o con el Comité Olímpico Español, en las condiciones que se determinen reglamentariamente.
>
> n) Las prestaciones por desempleo reconocidas por la respectiva entidad gestora cuando se perciban en la modalidad de pago único establecida en el Real Decreto 1044/1985, de 19 de junio, por el que se regula el abono de la prestación por desempleo en su modalidad de pago único, siempre que las cantidades percibidas se destinen a las finalidades y en los casos previstos en la citada norma.
>
> Esta exención estará condicionada al mantenimiento de la acción o participación durante el plazo de cinco años, en el supuesto de que el contribuyente se hubiera integrado en sociedades laborales o cooperativas de trabajo asociado o hubiera realizado una aportación al capital social de una entidad mercantil, o al mantenimiento, durante idéntico plazo, de la actividad, en el caso del trabajador autónomo.
>
> ñ) Los rendimientos positivos del capital mobiliario procedentes de los seguros de vida, depósitos y contratos financieros a través de los cuales se instrumenten los Planes de Ahorro a Largo Plazo a que se refiere la disposición adicional vigésima sexta de esta Ley, siempre que el contribuyente no efectúe disposición alguna del capital resultante del Plan antes de finalizar el plazo de cinco años desde su apertura.
>
> Cualquier disposición del citado capital o el incumplimiento de cualquier otro requisito de los previstos en la disposición adicional vigésima sexta de esta Ley antes de la finalización de dicho plazo, determinará la obligación de integrar los rendimientos a que se refiere el párrafo anterior generados durante la vigencia del Plan en el período impositivo en el que se produzca tal incumplimiento.
>
> o) Las gratificaciones extraordinarias satisfechas por el Estado español por la participación en misiones internacionales de paz o humanitarias, en los términos que reglamentariamente se establezcan.
>
> p) Los rendimientos del trabajo percibidos por trabajos efectivamente realizados en el extranjero, con los siguientes requisitos:
>
> 1.º Que dichos trabajos se realicen para una empresa o entidad no residente en España o un establecimiento permanente radicado en el extranjero en las condiciones que reglamentariamente se establezcan. En particular, cuando la entidad destinataria de los trabajos esté vinculada con la entidad empleadora del trabajador o con aquella en la que preste sus servicios, deberán cumplirse los requisitos previstos en el apartado 5 del artículo 16 del texto refundido de la Ley del Impuesto sobre Sociedades, aprobado por el Real Decreto Legislativo 4/2004, de 5 de marzo.
>
> 2.º Que en el territorio en que se realicen los trabajos se aplique un impuesto de naturaleza idéntica o análoga a la de este impuesto y no se trate de un país o territorio considerado como paraíso fiscal. Se considerará cumplido este requisito cuando el país o territorio en el que se realicen los trabajos tenga suscrito con España un convenio para evitar la doble imposición internacional que contenga cláusula de intercambio de información.
>
> La exención se aplicará a las retribuciones devengadas durante los días de estancia en el extranjero, con el límite máximo de 60.100 euros anuales. Reglamentariamente podrá establecerse el procedimiento para calcular el importe diario exento.
>
> Esta exención será incompatible, para los contribuyentes destinados en el extranjero, con el régimen de excesos excluidos de tributación previsto en el reglamento de este impuesto, cualquiera que sea su importe. El contribuyente podrá optar por la aplicación del régimen de excesos en sustitución de esta exención.
>
> q) Las indemnizaciones satisfechas por las Administraciones públicas por daños personales como consecuencia del funcionamiento de los servicios públicos, cuando vengan establecidas de acuerdo con los procedimientos previstos en el Real Decreto 429/1993, de 26 de marzo, por el que se regula el Reglamento de los procedimientos de las Administraciones públicas en materia de responsabilidad patrimonial.
>
> r) Las prestaciones percibidas por entierro o sepelio, con el límite del importe total de los gastos incurridos.
>
> s) Las ayudas económicas reguladas en el artículo 2 de la Ley 14/2002, de 5 de junio.
>
> t) Las derivadas de la aplicación de los instrumentos de cobertura cuando cubran exclusivamente el riesgo de incremento del tipo de interés variable de los préstamos hipotecarios destinados a la adquisición de la vivienda habitual, regulados en el artículo decimonoveno de la Ley 36/2003, de 11 de noviembre, de medidas de reforma económica.
>
> u) Las indemnizaciones previstas en la legislación del Estado y de las Comunidades Autónomas para compensar la privación de libertad en establecimientos penitenciarios como consecuencia de los supuestos contemplados en la Ley 46/1977, de 15 de octubre, de Amnistía, y las establecidas en la disposición adicional vigésima de la Ley 20/2022, de 19 de octubre, de Memoria Democrática.
>
> v) Las rentas que se pongan de manifiesto en el momento de la constitución de rentas vitalicias aseguradas resultantes de los planes individuales de ahorro sistemático a que se refiere la disposición adicional tercera de esta Ley.
>
> w) Los rendimientos del trabajo derivados de las prestaciones obtenidas en forma de renta por las personas con discapacidad correspondientes a las aportaciones a las que se refiere el artículo 53 de esta Ley, hasta un importe máximo anual de tres veces el indicador público de renta de efectos múltiples.
>
> Igualmente estarán exentos, con el mismo límite que el señalado en el párrafo anterior, los rendimientos del trabajo derivados de las aportaciones a patrimonios protegidos a que se refiere la disposición adicional decimoctava de esta Ley.
>
> x) Las prestaciones económicas públicas vinculadas al servicio, para cuidados en el entorno familiar y de asistencia personalizada que se derivan de la Ley de promoción de la autonomía personal y atención a las personas en situación de dependencia.
>
> y) La prestación de la Seguridad Social del Ingreso Mínimo Vital, las prestaciones económicas establecidas por las Comunidades Autónomas en concepto de renta mínima de inserción para garantizar recursos económicos de subsistencia a las personas que carezcan de ellos, así como las demás ayudas establecidas por estas o por entidades locales para atender, con arreglo a su normativa, a colectivos en riesgo de exclusión social, situaciones de emergencia social, necesidades habitacionales de personas sin recursos o necesidades de alimentación, escolarización y demás necesidades básicas de menores o personas con discapacidad cuando ellos y las personas a su cargo, carezcan de medios económicos suficientes, hasta un importe máximo anual conjunto de 1,5 veces el indicador público de rentas de efectos múltiples.
>
> Asimismo, estarán exentas las ayudas concedidas a las víctimas de delitos violentos a que se refiere la Ley 35/1995, de 11 de diciembre, de ayudas y asistencia a las víctimas de delitos violentos y contra la libertad sexual, y las ayudas previstas en la Ley Orgánica 1/2004, de 28 de diciembre, de Medidas de Protección Integral contra la Violencia de Género, y demás ayudas públicas satisfechas a víctimas de violencia de género por tal condición.
>
> z) Las prestaciones y ayudas familiares percibidas de cualquiera de las Administraciones Públicas, ya sean vinculadas a nacimiento, adopción, acogimiento o cuidado de hijos menores.
>
> Se modifica la letra u) por la disposición final 2.1 del Real Decreto-ley 6/2026, de 3 de marzo. Ref. BOE-A-2026-5060
>
> Redactado conforme a la correccion de errores publicada en BOE núm. 66, de 16 de marzo de 2026. Ref. BOE-A-2026-6092
>
> Se modifican las letras d), e) y k), con efectos de 3 de abril de 2025, por la diposición final 14.1 de la Ley Orgánica 1/2025, de 2 de enero. Ref. BOE-A-2025-76
>
> Se modifica la letra y), con efectos desde el 1 de junio de 2020, por el art. 1 de la Ley 2/2022, de 24 de febrero. Ref. BOE-A-2022-2977
>
> Se modifica la letra y), con efectos desde el 1 de junio de 2020, por el art. 1 del Real Decreto-ley 39/2020, de 29 de diciembre. Ref. BOE-A-2020-17267
>
> Se modifica la letra h), con efectos desde 30 de diciembre de 2018 y ejercicios anteriores no prescritos, por el art. 1.1 del Real Decreto-ley 27/2018, de 28 de diciembre. Ref. BOE-A-2018-17991
>
> Se añade la letra y), con efectos desde 1 de enero de 2015, por el art. 1.1 del Real Decreto-ley 9/2015, de 10 de julio. Ref. BOE-A-2015-7765.
>
> Se modifica, con efectos desde 29 de noviembre de 2014, la letra e) y, con efectos desde 1 de enero de 2015, se modifican las letras j) y w), se añade la ñ) y se suprime la y), por el art. 1.1 a 5 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Se modifica la letra n), con efectos desde 1 de enero de 2013, por el art. 8.1 de la Ley 11/2013, de 26 de julio. Ref. BOE-A-2013-8187.
>
> Se modifica la letra n), con efectos desde 1 de enero de 2013, por el art. 8.1 del Real Decreto-ley 4/2013, de 22 de febrero. Ref. BOE-A-2013-2030.
>
> Se suprime la letra ñ), con efectos desde el 1 de enero de 2013, por el art. 2.1 de la Ley 16/2012, de 27 de diciembre. Ref. BOE-A-2012-15650.
>
> Se modifica la letra e), con efectos desde el 12 de febrero de 2012, por la disposición final 11.1 de la Ley 3/2012, de 6 de julio. Ref. BOE-A-2012-9110.
>
> Se modifica la letra ñ) por el art. 6 de la Ley 2/2010, de 1 de marzo. Ref. BOE-A-2010-3366
>
> Esta modificación surte efectos desde el 1 de enero de 2009, según establece la disposición final 4.d).
>
> Redactada la disposición final 4.d) conforme a la corrección de errores publicada en BOE núm. 128, de 26 de mayo de 2010. Ref. BOE-A-2010-8384
>
> Se modifica la letra e) por la disposición adicional 13 de la Ley 27/2009, de 30 de diciembre. Ref. BOE-A-2009-21160
>
> Se modifica la letra n), con efectos desde el 1 de enero de 2010 por el art. 65 de la Ley 26/2009, de 23 de diciembre. Ref. BOE-A-2009-20765
>
> Se añade la letra z) por la disposición final 1.1 de la Ley 35/2007, de 15 de noviembre. Ref. BOE-A-2007-19745
>
> CAPÍTULO II
>
> Contribuyentes

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 2 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 16. `ley-35-2006:art-81-2`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a81`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2018-01-01
- `required_text`:
  - "se podrá incrementar hasta en 1.000 euros adicionales"
  - "siempre que se hayan producido por meses completos"
- `notes` (verbatim): "LIRPF art 81.2: the guarderia increment's ANNUAL CAP. The deduccion por maternidad of apartado 1 may be increased 'hasta en 1.000 euros adicionales' where the contribuyente paid gastos de custodia for a child under three at an authorised guarderia or centro de educacion infantil. This entry grounds the 1.000-euro FIGURE specifically, which the parent ley-35-2006:art-81 entry does not pin -- that entry's required_text covers the 1.200-euro maternidad cap of apartado 1, a different figure for a different concept. CORPUS CHOICE, deliberate: this cites the bundled CONSOLIDATED ley-35-2006.html, not the per-article ley-35-2006-art-81.html excerpt the parent entry uses. That excerpt is a two-vintage hybrid and is tracked as its own open defect; grounding a new figure on it would inherit the problem. The apartado also fixes the turning-three extension ('los gastos incurridos con posterioridad al cumplimiento de dicha edad hasta el mes anterior a aquel en el que pueda comenzar el segundo ciclo de educacion infantil') and the complete-months condition on qualifying spend. AGENT-AUTHORED, grounded in the bundled authoritative consolidated ley-35-2006.html#a81; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a81; operator to re-stamp"

#### Bundled corpus text

> Artículo 81. Deducción por maternidad.
>
> 1. Las mujeres con hijos menores de tres años con derecho a la aplicación del mínimo por descendientes previsto en el artículo 58 de esta ley, que en el momento del nacimiento del menor perciban prestaciones contributivas o asistenciales del sistema de protección de desempleo, o que en dicho momento o en cualquier momento posterior estén dadas de alta en el régimen correspondiente de la Seguridad Social o mutualidad con un período mínimo, en este último caso, de 30 días cotizados, podrán minorar la cuota diferencial de este Impuesto hasta en 1.200 euros anuales por cada hijo menor de tres años hasta que el menor alcance los tres años de edad. En los supuestos de adopción o acogimiento, tanto preadoptivo como permanente, la deducción se podrá practicar, con independencia de la edad del menor, durante los tres años siguientes a la fecha de la inscripción en el Registro Civil.
>
> Cuando la inscripción no sea necesaria, la deducción se podrá practicar durante los tres años posteriores a la fecha de la resolución judicial o administrativa que la declare.
>
> En caso de fallecimiento de la madre, o cuando la guarda y custodia se atribuya de forma exclusiva al padre o, en su caso, a un tutor, siempre que cumpla los requisitos previstos en este artículo, este tendrá derecho a la práctica de la deducción pendiente.
>
> 2. El importe de la deducción a que se refiere el apartado 1 anterior se podrá incrementar hasta en 1.000 euros adicionales cuando el contribuyente que tenga derecho a la misma hubiera satisfecho en el período impositivo gastos de custodia del hijo menor de tres años en guarderías o centros de educación infantil autorizados.
>
> En el período impositivo en que el hijo menor cumpla tres años, el incremento previsto en este apartado podrá resultar de aplicación respecto de los gastos incurridos con posterioridad al cumplimiento de dicha edad hasta el mes anterior a aquel en el que pueda comenzar el segundo ciclo de educación infantil.
>
> A estos efectos se entenderán por gastos de custodia las cantidades satisfechas a guarderías y centros de educación infantil por la preinscripción y matrícula de dichos menores, la asistencia, en horario general y ampliado, y la alimentación, siempre que se hayan producido por meses completos y no tuvieran la consideración de rendimientos del trabajo en especie exentos por aplicación de lo dispuesto en las letras b) o d) del apartado 3 del artículo 42 de esta ley.
>
> 3. La deducción prevista en el apartado 1 anterior se calculará de forma proporcional al número de meses del periodo impositivo posteriores al momento en el que se cumplen los requisitos señalados en el apartado 1 anterior, en los que la mujer tenga derecho al mínimo por descendientes por ese menor de tres años, siempre que durante dichos meses no se perciba por ninguno de los progenitores en relación con dicho descendiente el complemento de ayuda para la infancia previsto en la Ley 19/2021, de 20 de diciembre, por la que se establece el ingreso mínimo vital.
>
> Cuando tenga derecho a la deducción en relación con ese descendiente por haberse dado de alta en la Seguridad Social o mutualidad con posterioridad al nacimiento del menor, la deducción correspondiente al mes en el que se cumpla el período de cotización de 30 días al que se refiere el apartado 1 anterior, se incrementará en 150 euros.
>
> El incremento de la deducción previsto en el apartado 2 anterior se calculará de forma proporcional al número de meses en que se cumplan de forma simultánea los requisitos de los apartados 1 y 2 anteriores, salvo el relativo a que sea menor de tres años en los meses a los que se refiere el segundo párrafo del apartado 2 anterior, y tendrá como límite el importe total del gasto efectivo no subvencionado satisfecho en dicho período a la guardería o centro educativo en relación con ese hijo.
>
> 4. Se podrá solicitar a la Agencia Estatal de Administración Tributaria el abono del importe de la deducción previsto en el apartado 1 anterior de forma anticipada. En estos supuestos, no se minorará la cuota diferencial del impuesto.
>
> 5. Reglamentariamente se regularán el procedimiento y las condiciones para tener derecho a la práctica de esta deducción, los supuestos en que se pueda solicitar de forma anticipada su abono y las obligaciones de información a cumplir por las guarderías o centros infantiles.
>
> Se modifica por el art. 64 de la Ley 31/2022, de 23 de diciembre. Ref. BOE-A-2022-22128
>
> Redactado conforme a la corrección de errores publicada en BOE núm. 52, de 2 de marzo de 2023. Ref. BOE-A-2023-5478

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2024. 1 binding(s); 1 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-05`.

### 17. `ley-35-2006:art-81-3`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a81`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2018-01-01
- `required_text`:
  - "El incremento de la deducción previsto en el apartado 2 anterior se calculará de forma proporcional al número de meses en que se cumplan de forma simultánea"
  - "tendrá como límite el importe total del gasto efectivo no subvencionado"
- `notes` (verbatim): "LIRPF art 81.3 third paragraph: how the apartado 2 increment is PRORATED and BOUNDED. Read this before assuming the proration is a manual gloss -- it is statutory, and an earlier reading of this campaign wrongly attributed it to the AEAT manual alone. The clause states three things the calculation depends on. It is proportional to 'el numero de meses en que se cumplan de forma simultanea los requisitos de los apartados 1 y 2', so the month basis is an INTERSECTION of the two apartados rather than either alone. It carves out the under-three condition for the turning-three extension months ('salvo el relativo a que sea menor de tres anios en los meses a los que se refiere el segundo parrafo del apartado 2'). And it caps the result at 'el importe total del gasto efectivo no subvencionado satisfecho en dicho periodo a la guarderia o centro educativo EN RELACION CON ESE HIJO' -- per child by its own words, which is the authority for bounding the increment per descendant rather than over the household. The apartado's FIRST paragraph prorates the apartado 1 deduccion and is a different rule for a different figure; do not conflate them. AGENT-AUTHORED, grounded in the bundled authoritative consolidated ley-35-2006.html#a81; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a81; operator to re-stamp"

#### Bundled corpus text

> Artículo 81. Deducción por maternidad.
>
> 1. Las mujeres con hijos menores de tres años con derecho a la aplicación del mínimo por descendientes previsto en el artículo 58 de esta ley, que en el momento del nacimiento del menor perciban prestaciones contributivas o asistenciales del sistema de protección de desempleo, o que en dicho momento o en cualquier momento posterior estén dadas de alta en el régimen correspondiente de la Seguridad Social o mutualidad con un período mínimo, en este último caso, de 30 días cotizados, podrán minorar la cuota diferencial de este Impuesto hasta en 1.200 euros anuales por cada hijo menor de tres años hasta que el menor alcance los tres años de edad. En los supuestos de adopción o acogimiento, tanto preadoptivo como permanente, la deducción se podrá practicar, con independencia de la edad del menor, durante los tres años siguientes a la fecha de la inscripción en el Registro Civil.
>
> Cuando la inscripción no sea necesaria, la deducción se podrá practicar durante los tres años posteriores a la fecha de la resolución judicial o administrativa que la declare.
>
> En caso de fallecimiento de la madre, o cuando la guarda y custodia se atribuya de forma exclusiva al padre o, en su caso, a un tutor, siempre que cumpla los requisitos previstos en este artículo, este tendrá derecho a la práctica de la deducción pendiente.
>
> 2. El importe de la deducción a que se refiere el apartado 1 anterior se podrá incrementar hasta en 1.000 euros adicionales cuando el contribuyente que tenga derecho a la misma hubiera satisfecho en el período impositivo gastos de custodia del hijo menor de tres años en guarderías o centros de educación infantil autorizados.
>
> En el período impositivo en que el hijo menor cumpla tres años, el incremento previsto en este apartado podrá resultar de aplicación respecto de los gastos incurridos con posterioridad al cumplimiento de dicha edad hasta el mes anterior a aquel en el que pueda comenzar el segundo ciclo de educación infantil.
>
> A estos efectos se entenderán por gastos de custodia las cantidades satisfechas a guarderías y centros de educación infantil por la preinscripción y matrícula de dichos menores, la asistencia, en horario general y ampliado, y la alimentación, siempre que se hayan producido por meses completos y no tuvieran la consideración de rendimientos del trabajo en especie exentos por aplicación de lo dispuesto en las letras b) o d) del apartado 3 del artículo 42 de esta ley.
>
> 3. La deducción prevista en el apartado 1 anterior se calculará de forma proporcional al número de meses del periodo impositivo posteriores al momento en el que se cumplen los requisitos señalados en el apartado 1 anterior, en los que la mujer tenga derecho al mínimo por descendientes por ese menor de tres años, siempre que durante dichos meses no se perciba por ninguno de los progenitores en relación con dicho descendiente el complemento de ayuda para la infancia previsto en la Ley 19/2021, de 20 de diciembre, por la que se establece el ingreso mínimo vital.
>
> Cuando tenga derecho a la deducción en relación con ese descendiente por haberse dado de alta en la Seguridad Social o mutualidad con posterioridad al nacimiento del menor, la deducción correspondiente al mes en el que se cumpla el período de cotización de 30 días al que se refiere el apartado 1 anterior, se incrementará en 150 euros.
>
> El incremento de la deducción previsto en el apartado 2 anterior se calculará de forma proporcional al número de meses en que se cumplan de forma simultánea los requisitos de los apartados 1 y 2 anteriores, salvo el relativo a que sea menor de tres años en los meses a los que se refiere el segundo párrafo del apartado 2 anterior, y tendrá como límite el importe total del gasto efectivo no subvencionado satisfecho en dicho período a la guardería o centro educativo en relación con ese hijo.
>
> 4. Se podrá solicitar a la Agencia Estatal de Administración Tributaria el abono del importe de la deducción previsto en el apartado 1 anterior de forma anticipada. En estos supuestos, no se minorará la cuota diferencial del impuesto.
>
> 5. Reglamentariamente se regularán el procedimiento y las condiciones para tener derecho a la práctica de esta deducción, los supuestos en que se pueda solicitar de forma anticipada su abono y las obligaciones de información a cumplir por las guarderías o centros infantiles.
>
> Se modifica por el art. 64 de la Ley 31/2022, de 23 de diciembre. Ref. BOE-A-2022-22128
>
> Redactado conforme a la corrección de errores publicada en BOE núm. 52, de 2 de marzo de 2023. Ref. BOE-A-2023-5478

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2024. 1 binding(s); 1 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-08-05`.

### 18. `ley-35-2006:art-92`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a92`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Imputación de rentas por la cesión de derechos de imagen"
  - "al tiempo de presentar la declaración deberá determinar su importe y efectuar su ingreso en el Tesoro"
- `notes` (verbatim): "LIRPF art 92: imputación de rentas por la cesión de derechos de imagen. Base legal de las casillas del régimen especial de imputación por cesión de derechos de imagen en Modelo 100. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#a92; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a92; operator to re-stamp"

#### Bundled corpus text

> Artículo 92. Imputación de rentas por la cesión de derechos de imagen.
>
> 1. Los contribuyentes imputarán en su base imponible del Impuesto sobre la Renta de las Personas Físicas la cantidad a que se refiere el apartado 3 cuando concurran las circunstancias siguientes:
>
> a) Que hubieran cedido el derecho a la explotación de su imagen o hubiesen consentido o autorizado su utilización a otra persona o entidad, residente o no residente. A efectos de lo dispuesto en este párrafo, será indiferente que la cesión, consentimiento o autorización hubiese tenido lugar cuando la persona física no fuese contribuyente.
>
> b) Que presten sus servicios a una persona o entidad en el ámbito de una relación laboral.
>
> c) Que la persona o entidad con la que el contribuyente mantenga la relación laboral, o cualquier otra persona o entidad vinculada con ellas en los términos del artículo 16 del texto refundido de la Ley del Impuesto sobre Sociedades, haya obtenido, mediante actos concertados con personas o entidades residentes o no residentes la cesión del derecho a la explotación o el consentimiento o autorización para la utilización de la imagen de la persona física.
>
> 2. La imputación a que se refiere el apartado anterior no procederá cuando los rendimientos del trabajo obtenidos en el período impositivo por la persona física a que se refiere el párrafo primero del apartado anterior en virtud de la relación laboral no sean inferiores al 85 por ciento de la suma de los citados rendimientos más la total contraprestación a cargo de la persona o entidad a que se refiere el párrafo c) del apartado anterior por los actos allí señalados.
>
> 3. La cantidad a imputar será el valor de la contraprestación que haya satisfecho con anterioridad a la contratación de los servicios laborales de la persona física o que deba satisfacer la persona o entidad a que se refiere el párrafo c) del apartado 1 por los actos allí señalados. Dicha cantidad se incrementará en el importe del ingreso a cuenta a que se refiere el apartado 8 y se minorará en el valor de la contraprestación obtenida por la persona física como consecuencia de la cesión, consentimiento o autorización a que se refiere el párrafo a) del apartado 1, siempre que la misma se hubiera obtenido en un período impositivo en el que la persona física titular de la imagen sea contribuyente por este impuesto.
>
> 4. 1.º Cuando proceda la imputación, será deducible de la cuota líquida del Impuesto sobre la Renta de las Personas Físicas correspondiente a la persona a que se refiere el párrafo primero del apartado 1:
>
> a) El impuesto o impuestos de naturaleza idéntica o similar al Impuesto sobre la Renta de las Personas Físicas o sobre Sociedades que, satisfecho en el extranjero por la persona o entidad no residente primera cesionaria, corresponda a la parte de la renta neta derivada de la cuantía que debe incluir en su base imponible.
>
> b) El Impuesto sobre la Renta de las Personas Físicas o sobre Sociedades que, satisfecho en España por la persona o entidad residente primera cesionaria, corresponda a la parte de la renta neta derivada de la cuantía que debe incluir en su base imponible.
>
> c) El impuesto o gravamen efectivamente satisfecho en el extranjero por razón de la distribución de los dividendos o participaciones en beneficios distribuidos por la primera cesionaria, sea conforme a un convenio para evitar la doble imposición o de acuerdo con la legislación interna del país o territorio de que se trate, en la parte que corresponda a la cuantía incluida en la base imponible.
>
> d) El impuesto satisfecho en España, cuando la persona física no sea residente, que corresponda a la contraprestación obtenida por la persona física como consecuencia de la primera cesión del derecho a la explotación de su imagen o del consentimiento o autorización para su utilización.
>
> e) El impuesto o impuestos de naturaleza idéntica o similar al Impuesto sobre la Renta de las Personas Físicas satisfecho en el extranjero, que corresponda a la contraprestación obtenida por la persona física como consecuencia de la primera cesión del derecho a la explotación de su imagen o del consentimiento o autorización para su utilización.
>
> 2.º Estas deducciones se practicarán aun cuando los impuestos correspondan a períodos impositivos distintos a aquél en el que se realizó la imputación.
>
> En ningún caso se deducirán los impuestos satisfechos en países o territorios considerados como paraísos fiscales.
>
> Estas deducciones no podrán exceder, en su conjunto, de la cuota íntegra que corresponda satisfacer en España por la renta imputada en la base imponible.
>
> 5. 1.º La imputación se realizará por la persona física en el período impositivo que corresponda a la fecha en que la persona o entidad a que se refiere el párrafo c) del apartado 1 efectúe el pago o satisfaga la contraprestación acordada, salvo que por dicho período impositivo la persona física no fuese contribuyente por este impuesto, en cuyo caso la inclusión deberá efectuarse en el primero o en el último período impositivo por el que deba tributar por este impuesto, según los casos.
>
> 2.º La imputación se efectuará en la base imponible, de acuerdo con lo previsto en el artículo 45 de esta Ley.
>
> 3.º A estos efectos se utilizará el tipo de cambio vigente al día de pago o satisfacción de la contraprestación acordada por parte de la persona o entidad a que se refiere el párrafo c) del apartado 1.
>
> 6. 1.º No se imputarán en el impuesto personal de los socios de la primera cesionaria los dividendos o participaciones en beneficios distribuidos por ésta en la parte que corresponda a la cuantía que haya sido imputada por la persona física a que se refiere el primer párrafo del apartado 1. El mismo tratamiento se aplicará a los dividendos a cuenta.
>
> En caso de distribución de reservas se atenderá a la designación contenida en el acuerdo social, entendiéndose aplicadas las últimas cantidades abonadas a dichas reservas.
>
> 2.º Los dividendos o participaciones a que se refiere el ordinal 1.º anterior no darán derecho a la deducción por doble imposición internacional.
>
> 3.º Una misma cuantía sólo podrá ser objeto de imputación por una sola vez, cualquiera que sea la forma y la persona o entidad en que se manifieste.
>
> 7. Lo previsto en los apartados anteriores de este artículo se entenderá sin perjuicio de lo dispuesto en los tratados y convenios internacionales que hayan pasado a formar parte del ordenamiento interno y en el artículo 4 de esta ley.
>
> 8. Cuando proceda la imputación a que se refiere el apartado 1, la persona o entidad a que se refiere el párrafo c) del mismo deberá efectuar un ingreso a cuenta de las contraprestaciones satisfechas en metálico o en especie a personas o entidades no residentes por los actos allí señalados.
>
> Si la contraprestación fuese en especie, su valoración se efectuará de acuerdo con lo previsto en el artículo 43 de esta ley, y se practicará el ingreso a cuenta sobre dicho valor.
>
> La persona o entidad a que se refiere el párrafo c) del apartado 1 deberá presentar declaración del ingreso a cuenta en la forma, plazos e impresos que establezca el Ministro de Economía y Hacienda. Al tiempo de presentar la declaración deberá determinar su importe y efectuar su ingreso en el Tesoro.
>
> Reglamentariamente se regulará el tipo de ingreso a cuenta.
>
> Sección 5.ª Régimen especial para trabajadores desplazados

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 4 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 19. `ley-35-2006:art-95`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a95`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "instituciones de inversión colectiva constituidas en países o territorios considerados como paraísos fiscales"
- `notes` (verbatim): "LIRPF art 95: tributación de los socios o partícipes de las instituciones de inversión colectiva constituidas en países o territorios considerados como paraísos fiscales. Base legal de las casillas del régimen especial de imputación por IIC en paraísos fiscales en Modelo 100. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#a95; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a95; operator to re-stamp"

#### Bundled corpus text

> Artículo 95. Tributación de los socios o partícipes de las instituciones de inversión colectiva constituidas en países o territorios considerados como paraísos fiscales.
>
> 1. Los contribuyentes que participen en instituciones de inversión colectiva constituidas en países o territorios considerados como paraísos fiscales, imputarán en la base imponible, de acuerdo con lo previsto en el artículo 45 de esta ley, la diferencia positiva entre el valor liquidativo de la participación al día de cierre del período impositivo y su valor de adquisición.
>
> La cantidad imputada se considerará mayor valor de adquisición.
>
> 2. Los beneficios distribuidos por la institución de inversión colectiva no se imputarán y minorarán el valor de adquisición de la participación.
>
> 3. Se presumirá, salvo prueba en contrario, que la diferencia a que se refiere el apartado 1 es el 15 por ciento del valor de adquisición de la acción o participación.
>
> 4. La renta derivada de la transmisión o reembolso de las acciones o participaciones se determinará conforme a lo previsto en la letra c) del apartado 1 del artículo 37 de esta Ley, debiendo tomarse a estos efectos como valor de adquisición el que resulte de la aplicación de lo previsto en los apartados anteriores.
>
> Sección 7.ª Ganancias patrimoniales por cambio de residencia

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 3 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 20. `ley-35-2006:art-97`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#a97`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Autoliquidación"
  - "no existe transmisión lucrativa a efectos fiscales entre los cónyuges por la renuncia a la devolución"
- `notes` (verbatim): "LIRPF art 97: autoliquidación. Incluye en su apartado 6 la compensación entre cónyuges cuando, en tributación individual, el resultado de una declaración es a ingresar y el de la otra a devolver. Base legal de las casillas de resultado de la autoliquidación, compensación entre cónyuges (datos de la cuenta SEPA) y autoliquidación rectificativa en Modelo 100. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#a97; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#a97; operator to re-stamp"

#### Bundled corpus text

> Artículo 97. Autoliquidación.
>
> 1. Los contribuyentes, al tiempo de presentar su declaración, deberán determinar la deuda tributaria correspondiente e ingresarla en el lugar, forma y plazos determinados por el Ministro de Economía y Hacienda.
>
> 2. El ingreso del importe resultante de la autoliquidación sólo se podrá fraccionar en la forma que se determine en el reglamento de desarrollo de esta Ley.
>
> 3. El pago de la deuda tributaria podrá realizarse mediante entrega de bienes integrantes del Patrimonio Histórico Español que estén inscritos en el Inventario General de Bienes Muebles o en el Registro General de Bienes de Interés Cultural, de acuerdo con lo dispuesto en el artículo 73 de la Ley 16/1985, de 25 de junio, del Patrimonio Histórico Español.
>
> 4. Los sucesores del causante quedarán obligados a cumplir las obligaciones tributarias pendientes por este impuesto, con exclusión de las sanciones, de conformidad con el artículo 39.1 de la Ley 58/2003, de 17 de diciembre, General Tributaria.
>
> 5. En el supuesto previsto en el artículo 14.4 de esta ley, los sucesores del causante podrán solicitar a la Administración tributaria el fraccionamiento de la parte de deuda tributaria correspondiente a las rentas a que se refiere dicho precepto, calculada aplicando el tipo regulado en el artículo 80.2 de esta ley.
>
> La solicitud se formulará dentro del plazo reglamentario de declaración relativo al período impositivo del fallecimiento y se concederá en función de los períodos impositivos a los que correspondería imputar dichas rentas en caso de que aquél no se hubiese producido con el límite máximo de cuatro años en las condiciones que se determinen reglamentariamente.
>
> 6. El contribuyente casado y no separado legalmente que esté obligado a presentar declaración por este Impuesto y cuya autoliquidación resulte a ingresar podrá, al tiempo de presentar su declaración, solicitar la suspensión del ingreso de la deuda tributaria, sin intereses de demora, en una cuantía igual o inferior a la devolución a la que tenga derecho su cónyuge por este mismo Impuesto.
>
> La solicitud de suspensión del ingreso de la deuda tributaria que cumpla todos los requisitos enumerados en este apartado determinará la suspensión cautelar del ingreso hasta tanto se reconozca por la Administración tributaria el derecho a la devolución a favor del otro cónyuge. El resto de la deuda tributaria podrá fraccionarse de acuerdo con lo establecido en el apartado 2 de este artículo.
>
> Los requisitos para obtener la suspensión cautelar serán los siguientes:
>
> a) El cónyuge cuya autoliquidación resulte a devolver deberá renunciar al cobro de la devolución hasta el importe de la deuda cuya suspensión haya sido solicitada. Asimismo, deberá aceptar que la cantidad a la que renuncia se aplique al pago de dicha deuda.
>
> b) La deuda cuya suspensión se solicita y la devolución pretendida deberán corresponder al mismo período impositivo.
>
> c) Ambas autoliquidaciones deberán presentarse de forma simultánea dentro del plazo que establezca el Ministro de Economía y Hacienda.
>
> d) Los cónyuges no podrán estar acogidos al sistema de cuenta corriente tributaria regulado en el Real Decreto 1108/1999, de 25 de junio.
>
> e) Los cónyuges deberán estar al corriente en el pago de sus obligaciones tributarias en los términos previstos en la Orden de 28 de abril de 1986, sobre justificación del cumplimiento de obligaciones tributarias.
>
> La Administración notificará a ambos cónyuges, dentro del plazo previsto en el apartado 1 del artículo 103 de esta Ley, el acuerdo que se adopte con expresión, en su caso, de la deuda extinguida y de las devoluciones o ingresos adicionales que procedan.
>
> Cuando no proceda la suspensión por no reunirse los requisitos anteriormente señalados, la Administración practicará liquidación provisional al contribuyente que solicitó la suspensión por importe de la deuda objeto de la solicitud junto con el interés de demora calculado desde el día siguiente a la fecha de vencimiento del plazo establecido para presentar la autoliquidación hasta la fecha de la liquidación.
>
> Los efectos del reconocimiento del derecho a la devolución respecto a la deuda cuya suspensión se hubiera solicitado son los siguientes:
>
> a) Si la devolución reconocida fuese igual a la deuda, ésta quedará extinguida, al igual que el derecho a la devolución.
>
> b) Si la devolución reconocida fuese superior a la deuda, ésta se declarará extinguida y la Administración procederá a devolver la diferencia entre ambos importes de acuerdo con lo previsto en el artículo 103 de esta Ley.
>
> c) Si la devolución reconocida fuese inferior a la deuda, ésta se declarará extinguida en la parte concurrente, practicando la Administración tributaria liquidación provisional al contribuyente que solicitó la suspensión por importe de la diferencia, exigiéndole igualmente el interés de demora calculado desde el día siguiente a la fecha de vencimiento del plazo establecido para presentar la autoliquidación hasta la fecha de la liquidación.
>
> Se considerará que no existe transmisión lucrativa a efectos fiscales entre los cónyuges por la renuncia a la devolución de uno de ellos para su aplicación al pago de la deuda del otro.
>
> Reglamentariamente podrá regularse el procedimiento a que se refiere este apartado

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 34 casilla(s); 1 construct(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 21. `ley-35-2006:da-11`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#daundecima`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Mutualidad de previsión social de deportistas profesionales"
  - "a los efectos de la percepción de las prestaciones se aplicará lo dispuesto en los apartados 8 y 9"
- `notes` (verbatim): "LIRPF disposición adicional 11ª: mutualidad de previsión social de deportistas profesionales y de alto nivel — aportaciones reducibles de la base imponible general con su propio límite (la menor de 24.250 € o la suma de rendimientos netos de trabajo y actividades económicas). Base legal de las casillas de reducción/exceso por mutualidad de deportistas en Modelo 100. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#daundecima; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#daundecima; operator to re-stamp"

#### Bundled corpus text

> Disposición adicional undécima. Mutualidad de previsión social de deportistas profesionales.
>
> Uno. Los deportistas profesionales y de alto nivel podrán realizar aportaciones a la mutualidad de previsión social a prima fija de deportistas profesionales, con las siguientes especialidades:
>
> 1. Ámbito subjetivo. Se considerarán deportistas profesionales los incluidos en el ámbito de aplicación del Real Decreto 1006/1985, de 26 de junio, por el que se regula la relación laboral especial de los deportistas profesionales. Se considerarán deportistas de alto nivel los incluidos en el ámbito de aplicación del Real Decreto 1467/1997, de 19 de septiembre, sobre deportistas de alto nivel.
>
> La condición de mutualista y asegurado recaerá, en todo caso, en el deportista profesional o de alto nivel.
>
> 2. Aportaciones. No podrán rebasar las aportaciones anuales la cantidad máxima que se establezca para los sistemas de previsión social constituidos a favor de personas con discapacidad, incluyendo las que hubiesen sido imputadas por los promotores en concepto de rendimientos del trabajo cuando se efectúen estas últimas de acuerdo con lo previsto en la disposición adicional primera del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones.
>
> No se admitirán aportaciones una vez que finalice la vida laboral como deportista profesional o se produzca la pérdida de la condición de deportista de alto nivel en los términos y condiciones que se establezcan reglamentariamente.
>
> 3. Contingencias. Las contingencias que pueden ser objeto de cobertura son las previstas para los planes de pensiones en el artículo 8.6 del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones.
>
> 4. Disposición de derechos consolidados. Los derechos consolidados de los mutualistas sólo podrán hacerse efectivos en los supuestos previstos en el artículo 8.8 del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones, y, adicionalmente, una vez transcurrido un año desde que finalice la vida laboral de los deportistas profesionales o desde que se pierda la condición de deportistas de alto nivel.
>
> 5. Régimen fiscal:
>
> a) Las aportaciones, directas o imputadas, que cumplan los requisitos anteriores podrán ser objeto de reducción en la base imponible general del Impuesto sobre la Renta de las Personas Físicas, con el límite de la suma de los rendimientos netos del trabajo y de actividades económicas percibidos individualmente en el ejercicio y hasta un importe máximo de 24.250 euros.
>
> b) Las aportaciones que no hubieran podido ser objeto de reducción en la base imponible por insuficiencia de la misma o por aplicación del límite establecido en la letra a) podrán reducirse en los cinco ejercicios siguientes. Esta regla no resultará de aplicación a las aportaciones que excedan del límite máximo previsto en el número 2 de este apartado uno.
>
> c) La disposición de los derechos consolidados en supuestos distintos a los mencionados en el apartado 4 anterior determinará la obligación para el contribuyente de reponer en la base imponible las reducciones indebidamente realizadas, con la práctica de las autoliquidaciones complementarias, que incluirán los intereses de demora. Las cantidades percibidas que excedan del importe de las aportaciones realizadas, incluyendo, en su caso, las contribuciones imputadas por el promotor, tributarán como rendimiento del trabajo en el período impositivo en que se perciban.
>
> d) Las prestaciones percibidas, así como la percepción de los derechos consolidados en los supuestos previstos en el apartado 4 anterior, tributarán en su integridad como rendimientos del trabajo.
>
> e) A los efectos de la percepción de las prestaciones se aplicará lo dispuesto en los apartados 8 y 9 del artículo 51 de esta Ley.
>
> Dos. Con independencia del régimen previsto en el apartado anterior, los deportistas profesionales y de alto nivel, aunque hayan finalizado su vida laboral como tales o hayan perdido esta condición, podrán realizar aportaciones a la mutualidad de previsión social de deportistas profesionales.
>
> Tales aportaciones podrán ser objeto de reducción en la base imponible del Impuesto sobre la Renta de las Personas Físicas en la parte que tenga por objeto la cobertura de las contingencias previstas en el artículo 8.6 del texto refundido de la Ley de Regulación de los Planes y Fondos de Pensiones.
>
> Los derechos consolidados de los mutualistas sólo podrán hacerse efectivos en los supuestos previstos, para los planes de pensiones, por el artículo 8.8 del texto refundido de la ley de Regulación de los Planes y Fondos de Pensiones.
>
> Como límite máximo conjunto de reducción de estas aportaciones se aplicará el que establece el artículo 51.6 de esta ley.
>
> A los efectos de la percepción de las prestaciones se aplicará lo dispuesto en los apartados 8 y 9 del artículo 51 de esta Ley.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 23 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 22. `ley-35-2006:da-45`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#dacuadragesimaquinta`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2017-01-21
- `required_text`:
  - "Tratamiento fiscal de las cantidades percibidas por la devolución de las cláusulas de limitación de tipos de interés"
  - "se perderá el derecho a practicar la deducción"
  - "debiendo sumar a la cuota líquida estatal y autonómica"
  - "sin inclusión de intereses de demora"
- `notes` (verbatim): "LIRPF disposición adicional 45ª: tratamiento fiscal de la devolución de cláusulas suelo. Cuando las cantidades devueltas formaron parte de la base de deducciones previas, se pierde el derecho a esas deducciones y deben sumarse las cantidades indebidamente deducidas a la cuota líquida estatal y autonómica, sin intereses de demora. Base legal específica de las casillas Modelo 100 que marcan la regularización motivada por DA 45ª.2.a) o DA 45ª.3. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#dacuadragesimaquinta; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#dacuadragesimaquinta; operator to re-stamp"

#### Bundled corpus text

> Disposición adicional cuadragésima quinta. Tratamiento fiscal de las cantidades percibidas por la devolución de las cláusulas de limitación de tipos de interés de préstamos derivadas de acuerdos celebrados con las entidades financieras o del cumplimiento de sentencias o laudos arbitrales.
>
> 1. No se integrará en la base imponible de este Impuesto la devolución derivada de acuerdos celebrados con entidades financieras, en efectivo o a través de otras medidas de compensación, junto con sus correspondientes intereses indemnizatorios, de las cantidades previamente satisfechas a aquellas en concepto de intereses por la aplicación de cláusulas de limitación de tipos de interés de préstamos.
>
> 2. Las cantidades previamente satisfechas por el contribuyente objeto de la devolución prevista en el apartado 1 anterior, tendrán el siguiente tratamiento fiscal:
>
> a) Cuando tales cantidades, en ejercicios anteriores, hubieran formado parte de la base de la deducción por inversión en vivienda habitual o de deducciones establecidas por la Comunidad Autónoma, se perderá el derecho a practicar la deducción en relación con las mismas, debiendo sumar a la cuota líquida estatal y autonómica, devengada en el ejercicio en el que se hubiera celebrado el acuerdo con la entidad financiera, exclusivamente las cantidades indebidamente deducidas en los ejercicios respecto de los que no hubiera prescrito el derecho de la Administración para determinar la deuda tributaria mediante la oportuna liquidación, en los términos previstos en el artículo 59 del Reglamento del Impuesto sobre la Renta de las Personas Físicas, aprobado por el Real Decreto 439/2007, de 30 de marzo, sin inclusión de intereses de demora.
>
> No resultará de aplicación la adición prevista en el párrafo anterior respecto de la parte de las cantidades que se destine directamente por la entidad financiera, tras el acuerdo con el contribuyente afectado, a minorar el principal del préstamo.
>
> b) Cuando tales cantidades hubieran tenido la consideración de gasto deducible en ejercicios anteriores respecto de los que no hubiera prescrito el derecho de la Administración para determinar la deuda tributaria mediante la oportuna liquidación, se perderá tal consideración, debiendo practicarse autoliquidación complementaria correspondiente a tales ejercicios, sin sanción, ni intereses de demora, ni recargo alguno en el plazo comprendido entre la fecha del acuerdo y la finalización del siguiente plazo de presentación de autoliquidación por este Impuesto.
>
> c) Cuando tales cantidades hubieran sido satisfechas por el contribuyente en ejercicios cuyo plazo de presentación de autoliquidación por este Impuesto no hubiera finalizado con anterioridad al acuerdo de devolución de las mismas celebrado con la entidad financiera, así como las cantidades a que se refiere el segundo párrafo de la letra a anterior, no formarán parte de la base de deducción por inversión en vivienda habitual ni de deducción autonómica alguna ni tendrán la consideración de gasto deducible.
>
> 3. Lo dispuesto en los apartados anteriores será igualmente de aplicación cuando la devolución de cantidades a que se refiere el apartado 1 anterior hubiera sido consecuencia de la ejecución o cumplimiento de sentencias judiciales o laudos arbitrales.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 2 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 23. `ley-35-2006:da-48`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#da-cuadragesima-octava-deduccion-aplicable`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2018-01-01
- `required_text`:
  - "Deducción aplicable a las unidades familiares formadas por residentes fiscales en Estados miembros de la Unión Europea"
- `notes` (verbatim): "LIRPF disposición adicional 48ª: deducción aplicable a las unidades familiares formadas por residentes fiscales en Estados miembros de la Unión Europea o del Espacio Económico Europeo, que equipara el tratamiento al de la tributación conjunta cuando uno de los miembros no es residente en España. Base legal de las casillas de la deducción por unidad familiar de residentes en la UE/EEE en Modelo 100. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html (DA cuadragésima octava); operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html (DA cuadragésima octava); operator to re-stamp"

#### Bundled corpus text

> Disposición adicional cuadragésima octava. Deducción aplicable a las unidades familiares formadas por residentes fiscales en Estados miembros de la Unión Europea o del Espacio Económico Europeo.
>
> 1. Cuando la unidad familiar a que se refiere el artículo 82.1 de esta Ley esté formada por contribuyentes de este Impuesto y por residentes en otro Estado miembro de la Unión Europea o del Espacio Económico Europeo con el que exista un efectivo intercambio de información tributaria, en los términos previstos en el apartado 4 de la disposición adicional primera de la Ley 36/2006, de 29 de noviembre, de medidas para la prevención del fraude fiscal, los contribuyentes por este Impuesto podrán deducir de la cuota íntegra que corresponde a su declaración individual, en su caso, el resultado de las siguientes operaciones:
>
> 1.º Se sumarán las cuotas íntegras estatal y autonómica minoradas en las deducciones previstas en los artículos 67 y 77 de esta Ley, de los miembros de la unidad familiar contribuyentes por este Impuesto junto con las cuotas del Impuesto sobre la Renta de no Residentes correspondientes a las rentas obtenidas en territorio español en ese mismo período impositivo por el resto de miembros de la unidad familiar.
>
> 2.º Se determinará la cuota líquida total de este Impuesto que hubiera resultado de haber podido optar por tributar conjuntamente con el resto de miembros de la unidad familiar, entendiéndose, a estos exclusivos efectos, que todos los miembros de la unidad familiar son contribuyentes por este Impuesto. Para dicho cálculo solamente se tendrán en cuenta, para cada fuente de renta, la parte de las rentas positivas de los miembros no residentes integrados en la unidad familiar que excedan de las rentas negativas obtenidas por estos últimos.
>
> 3.º Se restará a la cuantía prevista en el número 1.º anterior, la cuota a la que se refiere el número 2.º anterior. Cuando dicha diferencia sea negativa, la cantidad a computar será cero.
>
> 4.º Se deducirá de la cuota íntegra estatal y autonómica, una vez efectuadas las deducciones previstas en los artículos 67 y 77 de esta Ley, la cuantía prevista en el número 3.º anterior. A estos efectos, se minorará la cuota íntegra estatal del Impuesto en la proporción que representen las cuotas del Impuesto sobre la Renta de no Residentes respecto de la cuantía total prevista en el número 1.º del apartado 1 anterior, y el resto minorará la cuota íntegra estatal y autonómica por partes iguales.
>
> Cuando sean varios los contribuyentes de este Impuesto integrados en la unidad familiar, esta minoración se efectuará de forma proporcional a las respectivas cuotas íntegras, una vez efectuadas las deducciones previstas en los artículos 67 y 77 de esta Ley, de cada uno de ellos.
>
> 2. Lo dispuesto en el apartado 1 anterior no resultará de aplicación cuando alguno de los miembros integrados en la unidad familiar hubiera optado por tributar con arreglo a lo dispuesto en el artículo 93 de esta Ley o en el artículo 46 del Texto Refundido de la Ley del Impuesto sobre la Renta de no Residentes o no disponga del número de identificación fiscal.
>
> 3. La Administración podrá requerir del contribuyente cuantos documentos justificativos juzgue necesarios para acreditar el cumplimiento de las condiciones que determinan la aplicación de esta deducción.
>
> Cuando la documentación que se aporte para justificar la aplicación del régimen o las circunstancias personales o familiares que deban ser tenidas en cuenta, esté redactada en una lengua no oficial en territorio español, se presentará acompañada de su correspondiente traducción.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 5 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 24. `ley-35-2006:da-50`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#da-quincuagesima-deduccion-por-obras`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2021-10-06
- `required_text`:
  - "Deducción por obras de mejora de la eficiencia energética de viviendas"
  - "se restará de la cuota íntegra estatal después de las deducciones previstas en los apartados"
- `notes` (verbatim): "LIRPF disposición adicional 50ª: deducción por obras de mejora de la eficiencia energética de viviendas (20%/40%/60% según el tipo de obra y la reducción de demanda/consumo acreditada por certificado energético). Base legal de las casillas de deducción y exceso por mejoras energéticas de vivienda en Modelo 100. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#da-4 (DA quincuagésima); operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#da-4; operator to re-stamp"

#### Bundled corpus text

> Disposición adicional quincuagésima. Deducción por obras de mejora de la eficiencia energética de viviendas.
>
> 1. Los contribuyentes podrán deducirse el 20 por ciento de las cantidades satisfechas desde la entrada en vigor del Real Decreto-ley 19/2021, de 5 de octubre, de medidas urgentes para impulsar la actividad de rehabilitación edificatoria en el contexto del Plan de Recuperación, Transformación y Resiliencia, hasta el 31 de diciembre de 2026 por las obras realizadas durante dicho período para la reducción de la demanda de calefacción y refrigeración de su vivienda habitual o de cualquier otra de su titularidad que tuviera arrendada para su uso como vivienda en ese momento o en expectativa de alquiler, siempre que en este último caso, la vivienda se alquile antes de 31 de diciembre de 2027.
>
> A estos efectos, únicamente se entenderá que se ha reducido la demanda de calefacción y refrigeración de la vivienda cuando se reduzca en al menos un 7 por ciento la suma de los indicadores de demanda de calefacción y refrigeración del certificado de eficiencia energética de la vivienda expedido por el técnico competente después de la realización de las obras, respecto del expedido antes del inicio de las mismas.
>
> La deducción se practicará en el período impositivo en el que se expida el certificado de eficiencia energética emitido después de la realización de las obras. Cuando el certificado se expida en un período impositivo posterior a aquél en el que se abonaron cantidades por tales obras, la deducción se practicará en este último tomando en consideración las cantidades satisfechas desde la entrada en vigor del Real Decreto-ley 19/2021, de 5 de octubre, de medidas urgentes para impulsar la actividad de rehabilitación edificatoria en el contexto del Plan de Recuperación, Transformación y Resiliencia, hasta el 31 de diciembre de dicho período impositivo. En todo caso, dicho certificado deberá ser expedido antes de 1 de enero de 2027.
>
> La base máxima anual de esta deducción será de 5.000 euros anuales.
>
> 2. Los contribuyentes podrán deducirse el 40 por ciento de las cantidades satisfechas desde la entrada en vigor del Real Decreto-ley 19/2021, de 5 de octubre, de medidas urgentes para impulsar la actividad de rehabilitación edificatoria en el contexto del Plan de Recuperación, Transformación y Resiliencia, hasta el 31 de diciembre de 2026 por las obras realizadas durante dicho período para la mejora en el consumo de energía primaria no renovable de su vivienda habitual o de cualquier otra de su titularidad que tuviera arrendada para su uso como vivienda en ese momento o en expectativa de alquiler, siempre que, en este último caso, la vivienda se alquile antes de 31 de diciembre de 2027.
>
> A estos efectos, únicamente se entenderá que se ha mejorado el consumo de energía primaria no renovable en la vivienda en la que se hubieran realizado tales obras cuando se reduzca en al menos un 30 por ciento el indicador de consumo de energía primaria no renovable, o bien, se consiga una mejora de la calificación energética de la vivienda para obtener una clase energética "A" o "B", en la misma escala de calificación, acreditado mediante certificado de eficiencia energética expedido por el técnico competente después de la realización de aquéllas, respecto del expedido antes del inicio de las mismas.
>
> La deducción se practicará en el período impositivo en el que se expida el certificado de eficiencia energética emitido después de la realización de las obras. Cuando el certificado se expida en un período impositivo posterior a aquél en el que se abonaron cantidades por tales obras, la deducción se practicará en este último tomando en consideración las cantidades satisfechas desde la entrada en vigor del Real Decreto-ley 19/2021, de 5 de octubre, de medidas urgentes para impulsar la actividad de rehabilitación edificatoria en el contexto del Plan de Recuperación, Transformación y Resiliencia, hasta el 31 de diciembre de dicho período impositivo. En todo caso, dicho certificado deberá ser expedido antes de 1 de enero de 2027.
>
> La base máxima anual de esta deducción será de 7.500 euros anuales.
>
> 3. Los contribuyentes propietarios de viviendas ubicadas en edificios de uso predominante residencial en el que se hayan llevado a cabo desde la entrada en vigor del Real Decreto-ley 19/2021, de 5 de octubre, de medidas urgentes para impulsar la actividad de rehabilitación edificatoria en el contexto del Plan de Recuperación, Transformación y Resiliencia, hasta el 31 de diciembre de 2027 obras de rehabilitación energética, podrán deducirse el 60 por ciento de las cantidades satisfechas durante dicho período por tales obras. A estos efectos, tendrán la consideración de obras de rehabilitación energética del edificio aquéllas en las que se obtenga una mejora de la eficiencia energética del edificio en el que se ubica la vivienda, debiendo acreditarse con el certificado de eficiencia energética del edificio expedido por el técnico competente después de la realización de aquéllas una reducción del consumo de energía primaria no renovable, referida a la certificación energética, de un treinta por ciento como mínimo, o bien, la mejora de la calificación energética del edificio para obtener una clase energética «A» o «B», en la misma escala de calificación, respecto del expedido antes del inicio de las mismas.
>
> Se asimilarán a viviendas las plazas de garaje y trasteros que se hubieran adquirido con estas.
>
> No darán derecho a practicar esta deducción por las obras realizadas en la parte de la vivienda que se encuentre afecta a una actividad económica.
>
> La deducción se practicará en los períodos impositivos 2021, 2022, 2023, 2024, 2025, 2026 y 2027 en relación con las cantidades satisfechas en cada uno de ellos, siempre que se hubiera expedido, antes de la finalización del período impositivo en el que se vaya a practicar la deducción, el citado certificado de eficiencia energética. Cuando el certificado se expida en un período impositivo posterior a aquél en el que se abonaron cantidades por tales obras, la deducción se practicará en este último tomando en consideración las cantidades satisfechas desde la entrada en vigor del Real Decreto-ley 19/2021, de 5 de octubre, de medidas urgentes para impulsar la actividad de rehabilitación edificatoria en el contexto del Plan de Recuperación, Transformación y Resiliencia, hasta el 31 de diciembre de dicho período impositivo. En todo caso, dicho certificado deberá ser expedido antes de 1 de enero de 2028.
>
> La base máxima anual de esta deducción será de 5.000 euros anuales.
>
> Las cantidades satisfechas no deducidas por exceder de la base máxima anual de deducción podrán deducirse, con el mismo límite, en los cuatro ejercicios siguientes, sin que en ningún caso la base acumulada de la deducción pueda exceder de 15.000 euros.
>
> 4. No darán derecho a practicar las deducciones previstas en los apartados 1 y 2 anteriores, cuando la obra se realice en las partes de las viviendas afectas a una actividad económica, plazas de garaje, trasteros, jardines, parques, piscinas e instalaciones deportivas y otros elementos análogos.
>
> En ningún caso, una misma obra realizada en una vivienda dará derecho a las deducciones previstas en los apartados 1 y 2 anteriores. Tampoco tales deducciones resultarán de aplicación en aquellos casos en los que la mejora acreditada y las cuantías satisfechas correspondan a actuaciones realizadas en el conjunto del edificio y proceda la aplicación de la deducción recogida en el apartado 3 de esta disposición.
>
> La base de las deducciones previstas en los apartados 1, 2 y 3 anteriores estará constituida por las cantidades satisfechas, mediante tarjeta de crédito o débito, transferencia bancaria, cheque nominativo o ingreso en cuentas en entidades de crédito, a las personas o entidades que realicen tales obras, así como a las personas o entidades que expidan los citados certificados, debiendo descontar aquellas cuantías que, en su caso, hubieran sido subvencionadas a través de un programa de ayudas públicas o fueran a serlo en virtud de resolución definitiva de la concesión de tales ayudas. En ningún caso, darán derecho a practicar deducción las cantidades satisfechas mediante entregas de dinero de curso legal.
>
> A estos efectos, se considerarán como cantidades satisfechas por las obras realizadas aquellas necesarias para su ejecución, incluyendo los honorarios profesionales, costes de redacción de proyectos técnicos, dirección de obras, coste de ejecución de obras o instalaciones, inversión en equipos y materiales y otros gastos necesarios para su desarrollo, así como la emisión de los correspondientes certificados de eficiencia energética. En todo caso, no se considerarán en dichas cantidades los costes relativos a la instalación o sustitución de equipos que utilicen combustibles de origen fósil.
>
> Tratándose de obras llevadas a cabo por una comunidad de propietarios la cuantía susceptible de formar la base de la deducción de cada contribuyente a que se refiere el apartado 3 anterior vendrá determinada por el resultado de aplicar a las cantidades satisfechas por la comunidad de propietarios, a las que se refiere el párrafo anterior, el coeficiente de participación que tuviese en la misma.
>
> 5. Los certificados de eficiencia energética previstos en los apartados anteriores deberán haber sido expedidos y registrados con arreglo a lo dispuesto en el Real Decreto 390/2021, de 1 de junio, por el que se aprueba el procedimiento básico para la certificación de la eficiencia energética de los edificios.
>
> A los efectos de acreditar el cumplimiento de los requisitos exigidos para la práctica de estas deducciones serán válidos los certificados expedidos antes del inicio de las obras siempre que no hubiera transcurrido un plazo de dos años entre la fecha de su expedición y la del inicio de estas.
>
> 6. El importe de estas deducciones se restará de la cuota íntegra estatal después de las deducciones previstas en los apartados 1, 2, 3, 4, y 5 del artículo 68 de esta ley.
>
> Se modifica, con efectos desde el 1 de enero de 2025, por el art. 36.1 del Real Decreto-ley 7/2026, de 20 de marzo. Ref. BOE-A-2026-6544
>
> Se deja sin efecto la modificación por Resolución de 26 de febrero de 2026, que publica el Acuerdo del Congreso de los Diputados por el que se deroga el Real Decreto-ley 2/2026, de 3 de febrero. Ref. BOE-A-2026-4667
>
> Se modifica, con efectos de 1 de enero de 2025, por el art. 10.1 del Real Decreto-ley 2/2026, de 3 de febrero. Ref. BOE-A-2026-2547
>
> Se deja sin efecto la modificación de esta disposición por Resolución de 27 de enero de 2026, que publica el Acuerdo del Congreso de los Diputados por el que se deroga el Real Decreto-ley 16/2025 de 23 de diciembre. Ref. BOE-A-2026-2024
>
> Se modifica, con efectos de 1 de enero de 2025, por el art. 14.1 del Real Decreto-ley 16/2025, de 23 de diciembre. Ref. BOE-A-2025-26458
>
> Se deja sin efecto la modificación de esta disposición por Resolución de 22 de enero de 2025, que publica el Acuerdo del Congreso de los Diputados por el que se deroga el Real Decreto-ley 9/2024, de 23 de diciembre. Ref. BOE-A-2025-1136

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2021, 2022, 2023, 2024, 2025. 57 casilla(s); 5 construct(s); 5 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 25. `ley-35-2006:da-58`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#da-11`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2023-06-30
- `required_text`:
  - "Deducción por la adquisición de vehículos eléctricos"
  - "reglamentariamente se regularán las obligaciones de información a cumplir por los concesionarios"
- `notes` (verbatim): "LIRPF disposición adicional 58ª: deducción por la adquisición de vehículos eléctricos enchufables y de pila de combustible y por la instalación de puntos de recarga (15% sobre el valor de adquisición, con límites). Base legal de las casillas de deducción por vehículos eléctricos y puntos de recarga en Modelo 100. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#da-11 (DA quincuagésima octava); operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#da-11; operator to re-stamp"

#### Bundled corpus text

> Disposición adicional quincuagésima octava. Deducción por la adquisición de vehículos eléctricos "enchufables" y de pila de combustible y puntos de recarga.
>
> 1. Los contribuyentes podrán deducir el 15 por ciento del valor de adquisición de un vehículo eléctrico nuevo, en cualquiera de las siguientes circunstancias:
>
> a) Cuando el vehículo se adquiera desde la entrada en vigor del Real Decreto-ley 5/2023, de 28 de junio, por el que se adoptan y prorrogan determinadas medidas de respuesta a las consecuencias económicas y sociales de la Guerra de Ucrania, de apoyo a la reconstrucción de la isla de La Palma y a otras situaciones de vulnerabilidad; de transposición de Directivas de la Unión Europea en materia de modificaciones estructurales de sociedades mercantiles y conciliación de la vida familiar y la vida profesional de los progenitores y los cuidadores; y de ejecución y cumplimiento del Derecho de la Unión Europea, hasta el 31 de diciembre de 2026. En este caso, la deducción se practicará en el periodo impositivo en el que el vehículo sea matriculado.
>
> b) Cuando se abone al vendedor desde la entrada en vigor del Real Decreto-ley 5/2023, de 28 de junio, por el que se adoptan y prorrogan determinadas medidas de respuesta a las consecuencias económicas y sociales de la Guerra de Ucrania, de apoyo a la reconstrucción de la isla de La Palma y a otras situaciones de vulnerabilidad; de transposición de Directivas de la Unión Europea en materia de modificaciones estructurales de sociedades mercantiles y conciliación de la vida familiar y la vida profesional de los progenitores y los cuidadores; y de ejecución y cumplimiento del Derecho de la Unión Europea, hasta el 31 de diciembre de 2026, una cantidad a cuenta para la futura adquisición del vehículo que represente, al menos, el 25 por ciento del valor de adquisición del mismo. En este caso, la deducción se practicará en el periodo impositivo en el que se abone tal cantidad, debiendo abonarse el resto y adquirirse el vehículo antes de que finalice el segundo período impositivo inmediato posterior a aquel en el que se produjo el pago de tal cantidad.
>
> En ambos casos, la base máxima de la deducción será 20.000 euros y estará constituida por el valor de adquisición del vehículo, incluidos los gastos y tributos inherentes a la adquisición, debiendo descontar aquellas cuantías que, en su caso, hubieran sido subvencionadas o fueran a serlo a través de un programa de ayudas públicas. El contribuyente podrá aplicar la deducción prevista en este apartado por una única compra de alguno de los vehículos referidos en el apartado 2, debiendo optar en relación a la misma por la aplicación de lo dispuesto en la letra a) o b) anterior.
>
> 2. Solamente darán derecho a la práctica de esta deducción los vehículos que cumplan los siguientes requisitos:
>
> a) Los vehículos deberán pertenecer a alguna de las categorías siguientes: turismos M1, cuadriciclos ligeros L6e, cuadriciclos pesados L7e o motocicletas L3e, L4e o L5e.
>
> b) Los modelos de los vehículos deberán ser subvencionables conforme a la normativa estatal reguladora del programa de ayudas públicas a la movilidad eléctrica aplicable en el momento de la matriculación en el caso de la letra a) del apartado 1 anterior, o en el que momento en el que se produjo el pago de la cantidad a cuenta, en el caso de la letra b) del apartado 1 anterior.
>
> c) Los vehículos no podrán estar afectos a una actividad económica.
>
> d) Deberán estar matriculados por primera vez en España a nombre del contribuyente antes de 31 de diciembre de 2026, en el caso de la letra a) del apartado 1 anterior, o antes de que finalice el segundo período impositivo inmediato posterior a aquel en el que se produjo el pago de la cantidad a cuenta, en el caso de la letra b) del apartado 1 anterior.
>
> e) El precio de venta del vehículo adquirido no podrá superar el importe máximo establecido, en su caso, para cada tipo de vehículo por la normativa estatal reguladora de los programas de ayudas públicas a la movilidad eléctrica aplicable en el momento de la matriculación, en el caso de la letra a) del apartado 1 anterior, o en el momento en el que se produjo el pago de la cantidad a cuenta, en el caso de la letra b) del apartado 1 anterior, calculado en ambos supuestos en los términos establecidos en dicha normativa.
>
> 3. Los contribuyentes podrán deducir el 15 por ciento de las cantidades satisfechas desde la entrada en vigor del Real Decreto-ley 5/2023, de 28 de junio, por el que se adoptan y prorrogan determinadas medidas de respuesta a las consecuencias económicas y sociales de la Guerra de Ucrania, de apoyo a la reconstrucción de la isla de La Palma y a otras situaciones de vulnerabilidad; de transposición de Directivas de la Unión Europea en materia de modificaciones estructurales de sociedades mercantiles y conciliación de la vida familiar y la vida profesional de los progenitores y los cuidadores; y de ejecución y cumplimiento del Derecho de la Unión Europea, hasta el 31 de diciembre de 2026, para la instalación durante dicho período en un inmueble de su propiedad de sistemas de recarga de baterías para vehículos eléctricos no afectas a una actividad económica.
>
> La base máxima anual de esta deducción será de 4.000 euros anuales y estará constituida por las cantidades satisfechas, mediante tarjeta de crédito o débito, transferencia bancaria, cheque nominativo o ingreso en cuentas en entidades de crédito, a las personas o entidades que realicen la instalación, debiendo descontar aquellas cuantías que, en su caso, hubieran sido subvencionadas a través de un programa de ayudas públicas. En ningún caso, darán derecho a practicar deducción las cantidades satisfechas mediante entregas de dinero de curso legal.
>
> A estos efectos, se considerarán como cantidades satisfechas para la instalación de los sistemas de recarga las necesarias para llevarla a cabo, tales como, la inversión en equipos y materiales, gastos de instalación de los mismos y las obras necesarias para su desarrollo.
>
> La deducción se practicará en el periodo impositivo en el que finalice la instalación, que no podrá ser posterior a 2026. Cuando la instalación finalice en un período impositivo posterior a aquél en el que se abonaron cantidades por tal instalación, la deducción se practicará en este último tomando en consideración las cantidades satisfechas desde la entrada en vigor del Real Decreto-ley 5/2023, de 28 de junio, por el que se adoptan y prorrogan determinadas medidas de respuesta a las consecuencias económicas y sociales de la Guerra de Ucrania, de apoyo a la reconstrucción de la isla de La Palma y a otras situaciones de vulnerabilidad; de transposición de Directivas de la Unión Europea en materia de modificaciones estructurales de sociedades mercantiles y conciliación de la vida familiar y la vida profesional de los progenitores y los cuidadores; y de ejecución y cumplimiento del Derecho de la Unión Europea, hasta el 31 de diciembre de dicho período impositivo. Para la aplicación de la deducción deberá contarse con las autorizaciones y permisos establecidos en la legislación vigente.
>
> 4. En caso de que con posterioridad a su adquisición o instalación se afectaran a una actividad económica los vehículos o los sistemas de recarga de baterías a que se refieren los apartados anteriores, se perderá el derecho a la deducción practicada.
>
> 5. El importe de estas deducciones se restará de la cuota íntegra estatal después de las deducciones previstas en los apartados 1, 2, 3, 4, y 5 del artículo 68 de esta ley.
>
> 6. Reglamentariamente se regularán las obligaciones de información a cumplir por los concesionarios o vendedores de los vehículos.
>
> Se modifica, con efectos desde el 1 de enero de 2026, por el art. 36.2 del Real Decreto-ley 7/2026, de 20 de marzo. Ref. BOE-A-2026-6544
>
> Se deja sin efecto la modificación por Resolución de 26 de febrero de 2026, que publica el Acuerdo del Congreso de los Diputados por el que se deroga el Real Decreto-ley 2/2026, de 3 de febrero. Ref. BOE-A-2026-4667
>
> Se modifica, con efectos de 1 de enero de 2026, por el art. 10.3 del Real Decreto-ley 2/2026, de 3 de febrero. Ref. BOE-A-2026-2547
>
> Se deja sin efecto la modificación de esta disposición por Resolución de 27 de enero de 2026, que publica el Acuerdo del Congreso de los Diputados por el que se deroga el Real Decreto-ley 16/2025 de 23 de diciembre. Ref. BOE-A-2026-2024
>
> Se modifica, con efectos de 1 de enero de 2026, por el art. 14.3 del Real Decreto-ley 16/2025, de 23 de diciembre. Ref. BOE-A-2025-26458
>
> Se modifica, con efectos desde 1 de enero de 2025, por la disposición final 1 del Real Decreto-ley 3/2025, de 1 de abril. Ref. BOE-A-2025-6596
>
> Redactada conforme a la corrección de errores publicada en BOE núm. 86, de 9 de abril de 2025. Ref. BOE-A-2025-7094
>
> Se deja sin efecto la modificación de esta disposición por Resolución de 22 de enero de 2025, que publica el Acuerdo del Congreso de los Diputados por el que se deroga el Real Decreto-ley 9/2024, de 23 de diciembre. Ref. BOE-A-2025-1136

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2023, 2024, 2025. 21 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 26. `ley-35-2006:da-6`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#da-sexta-beneficios-fiscales-especiales`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "Beneficios fiscales especiales aplicables en actividades agrarias"
  - "podrán reducir el correspondiente a su actividad agraria en un 25 por ciento"
  - "primera instalación como titulares de una explotación prioritaria"
- `notes` (verbatim): "LIRPF disposición adicional sexta: beneficios fiscales especiales aplicables en actividades agrarias — los agricultores jóvenes o asalariados agrarios que determinen el rendimiento neto de su actividad agraria mediante estimación objetiva podrán reducir el correspondiente a dicha actividad en un 25 por ciento durante los períodos impositivos cerrados durante los cinco años siguientes a su primera instalación como titulares de una explotación prioritaria (Ley 19/1995, capítulo IV, título I), siempre que acrediten la realización de un plan de mejora de la explotación; la reducción se tiene en cuenta también para los pagos fraccionados. Base legal de la reducción agricultores jóvenes (casilla 1551 del Modelo 100 2025, Anexo I Orden HAC/1347/2024, instrucción 3). AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#dasexta; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#dasexta; operator to re-stamp"

#### Bundled corpus text

> Disposición adicional sexta. Beneficios fiscales especiales aplicables en actividades agrarias.
>
> Los agricultores jóvenes o asalariados agrarios que determinen el rendimiento neto de su actividad mediante el régimen de estimación objetiva, podrán reducir el correspondiente a su actividad agraria en un 25 por ciento durante los períodos impositivos cerrados durante los cinco años siguientes a su primera instalación como titulares de una explotación prioritaria, realizada al amparo de lo previsto en el capítulo IV del título I de la Ley 19/1995, de 4 de julio, de modernización de las explotaciones agrarias, siempre que acrediten la realización de un plan de mejora de la explotación.
>
> El rendimiento neto a que se refiere el párrafo anterior será el resultante exclusivamente de la aplicación de las normas que regulan el régimen de estimación objetiva.
>
> Esta reducción se tendrá en cuenta a efectos de determinar la cuantía de los pagos fraccionados que deban efectuarse.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2025. 3 casilla(s); 1 construct(s); 2 formula(s); 1 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-03`.

### 27. `ley-35-2006:da-60`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#da-14`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2025-01-01
- `required_text`:
  - "Rendimientos de actividades artísticas obtenidos de manera excepcional"
  - "se reducirá en un 30 por ciento"
  - "La cuantía sobre la que se aplicará esta reducción no podrá superar los 150.000 euros anuales"
- `notes` (verbatim): "LIRPF disposición adicional 60ª: reducción del 30% sobre rendimientos de actividades artísticas obtenidos de manera excepcional, con base máxima anual de 150.000 euros, para rendimientos del trabajo artísticos y rendimientos netos de actividades económicas artísticas que excedan del 130% de la media de los tres periodos impositivos anteriores. Base legal de las casillas Modelo 100 2025 de reducción por rendimientos artísticos excepcionales. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#da-14 (DA sexagésima); operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#da-14; operator to re-stamp"

#### Bundled corpus text

> Disposición adicional sexagésima. Rendimientos de actividades artísticas obtenidos de manera excepcional.
>
> 1. Cuando los rendimientos íntegros del trabajo obtenidos en el período impositivo a los que no les resulte de aplicación la reducción prevista en el artículo 18.2 de esta ley derivados de elaboración de obras literarias, artísticas o científicas a los que se refiere el artículo 17.2 d) de esta ley y de la relación laboral especial de las personas artistas que desarrollan su actividad en las artes escénicas, audiovisuales y musicales, así como de las personas que realizan actividades técnicas o auxiliares necesarias para el desarrollo de dicha actividad, excedan del 130 por ciento de la cuantía media de los referidos rendimientos imputados en los tres períodos impositivos anteriores, se reducirá en un 30 por ciento el citado exceso.
>
> La cuantía sobre la que se aplicará esta reducción no podrá superar los 150.000 euros anuales.
>
> 2. Cuando los rendimientos netos de actividades económicas obtenidos en el período impositivo a los que no les resulte de aplicación la reducción prevista en el artículo 32.1 de esta ley derivados de actividades incluidas en los grupos 851, 852, 853, 861, 862, 864 y 869 de la sección segunda y en las agrupaciones 01, 02, 03 y 05 de la sección tercera, de las Tarifas del Impuesto sobre Actividades Económicas, aprobadas junto con la Instrucción para su aplicación por el Real Decreto Legislativo 1175/1990, de 28 de septiembre, o de la prestación de servicios profesionales que por su naturaleza, si se realizase por cuenta ajena, quedaría incluida en el ámbito de aplicación de la relación laboral especial de las personas artistas que desarrollan su actividad en las artes escénicas, audiovisuales y musicales, así como de las personas que realizan actividades técnicas o auxiliares necesarias para el desarrollo de dicha actividad, excedan del 130 por ciento de la cuantía media de los referidos rendimientos netos imputados en los tres períodos impositivos anteriores, se reducirá en un 30 por ciento el citado exceso.
>
> A efectos del cálculo de los rendimientos netos de actividades económicas a los que les sea de aplicación esta reducción, así como los de los tres períodos impositivos anteriores, se tendrán en cuenta las siguientes reglas:
>
> 1.°) Los gastos deducibles que sean comunes a otros rendimientos de actividades económicas se prorratearán los mismos de forma proporcional en función de la cuantía de los distintos rendimientos íntegros de actividades económicas computadas en dicho ejercicio.
>
> 2.°) En caso de que, en alguno de los tres ejercicios anteriores el rendimiento neto fuera negativo se computará como 0 a efectos del cálculo de dicha media.
>
> La cuantía sobre la que se aplicará esta reducción no podrá superar los 150.000 euros anuales.
>
> La reducción será de aplicación con posterioridad, en su caso, a las reducciones previstas en los apartados 2 y 3 del artículo 32 de esta ley.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2025. 3 casilla(s); 2 construct(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-27`.

### 28. `ley-35-2006:dt-15`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#dtdecimoquinta`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2015-01-01
- `required_text`:
  - "Deducción por alquiler de la vivienda habitual"
- `notes` (verbatim): "LIRPF disposición transitoria 15ª: régimen transitorio de la deducción por alquiler de la vivienda habitual — aplicable a contribuyentes con contrato de arrendamiento anterior al 01-01-2015 que venían deduciéndose (10,05% con base máxima según base imponible). Base legal de las casillas informativas y de cálculo de la deducción por alquiler en Modelo 100. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#dtdecimoquinta; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#dtdecimoquinta; operator to re-stamp"

#### Bundled corpus text

> Disposición transitoria decimoquinta. Deducción por alquiler de la vivienda habitual.
>
> 1. Podrán aplicar la deducción por alquiler de la vivienda habitual en los términos previstos en el apartado 2 de esta disposición, los contribuyentes que hubieran celebrado un contrato de arrendamiento con anterioridad a 1 de enero de 2015 por el que hubieran satisfecho, con anterioridad a dicha fecha, cantidades por el alquiler de su vivienda habitual.
>
> En todo caso, resultará necesario que el contribuyente hubiera tenido derecho a la deducción por alquiler de la vivienda habitual en relación con las cantidades satisfechas por el alquiler de dicha vivienda en un período impositivo devengado con anterioridad a 1 de enero de 2015.
>
> 2. La deducción por alquiler de la vivienda habitual se aplicará conforme a lo dispuesto en los artículos 67.1, 68.7 y 77.1 de la Ley del Impuesto, en su redacción en vigor a 31 de diciembre de 2014.
>
> Se modifica por el art. 1.89 de la Ley 26/2014, de 27 de noviembre. Ref. BOE-A-2014-12327.
>
> Se añade por la disposición final 2.15 de la Ley 22/2009, de 18 de diciembre. Ref. BOE-A-2009-20375
>
> La incorporación de esta disposición entra en vigor y surte efectos desde el 1 de enero de 2010, según establece la disposición final 5.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 12 casilla(s); 6 construct(s); 12 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 29. `ley-35-2006:dt-18`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#dtdecimoctava`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2013-01-01
- `required_text`:
  - "Deducción por inversión en vivienda habitual"
- `notes` (verbatim): "LIRPF disposición transitoria 18ª: régimen transitorio de la deducción por inversión en vivienda habitual — aplicable a contribuyentes que adquirieron su vivienda habitual (o satisficieron cantidades para su construcción) antes del 01-01-2013 y venían deduciéndose. Base legal de las casillas de deducción por vivienda habitual en Modelo 100. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#dtdecimoctava; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#dtdecimoctava; operator to re-stamp"

#### Bundled corpus text

> Disposición transitoria decimoctava. Deducción por inversión en vivienda habitual.
>
> 1. Podrán aplicar la deducción por inversión en vivienda habitual en los términos previstos en el apartado 2 de esta disposición:
>
> a) Los contribuyentes que hubieran adquirido su vivienda habitual con anterioridad a 1 de enero de 2013 o satisfecho cantidades con anterioridad a dicha fecha para la construcción de la misma.
>
> b) Los contribuyentes que hubieran satisfecho cantidades con anterioridad a 1 de enero de 2013 por obras de rehabilitación o ampliación de la vivienda habitual, siempre que las citadas obras estén terminadas antes de 1 de enero de 2017.
>
> c) Los contribuyentes que hubieran satisfecho cantidades para la realización de obras e instalaciones de adecuación de la vivienda habitual de las personas con discapacidad con anterioridad a 1 de enero de 2013 siempre y cuando las citadas obras o instalaciones estén concluidas antes de 1 de enero de 2017.
>
> En todo caso, resultará necesario que el contribuyente hubiera practicado la deducción por inversión en vivienda habitual en relación con las cantidades satisfechas para la adquisición o construcción de dicha vivienda en un período impositivo devengado con anterioridad a 1 de enero de 2013, salvo que hubiera resultado de aplicación lo dispuesto en el artículo 68.1.2.ª de esta Ley en su redacción vigente a 31 de diciembre de 2012.
>
> 2. La deducción por inversión en vivienda habitual se aplicará conforme a lo dispuesto en los artículos 67.1, 68.1, 70.1, 77.1, y 78 de la Ley del Impuesto, en su redacción en vigor a 31 de diciembre de 2012, sin perjuicio de los porcentajes de deducción que conforme a lo dispuesto en la Ley 22/2009 hayan sido aprobados por la Comunidad Autónoma.
>
> 3. Los contribuyentes que por aplicación de lo establecido en esta disposición ejerciten el derecho a la deducción estarán obligados, en todo caso, a presentar declaración por este Impuesto y el importe de la deducción así calculada minorará el importe de la suma de la cuota íntegra estatal y autonómica del Impuesto a los efectos previstos en el apartado 2 del artículo 69 de esta Ley.
>
> 4. Los contribuyentes que con anterioridad a 1 de enero de 2013 hubieran depositado cantidades en cuentas vivienda destinadas a la primera adquisición o rehabilitación de la vivienda habitual, siempre que en dicha fecha no hubiera transcurrido el plazo de cuatro años desde la apertura de la cuenta, podrán sumar a la cuota líquida estatal y a la cuota líquida autonómica devengadas en el ejercicio 2012 las deducciones practicadas hasta el ejercicio 2011, sin intereses de demora.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 20 casilla(s); 6 construct(s); 12 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 30. `ley-35-2006:dt-9`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-35-2006.html#dtnovena`
- `document_id`: `BOE-A-2006-20764`; `effective_from`: 2007-01-01
- `required_text`:
  - "adquiridos con anterioridad a 31 de diciembre de 1994"
  - "la desafectación de estas actividades se haya producido con más de tres años"
- `notes` (verbatim): "LIRPF disposición transitoria 9ª: régimen transitorio (coeficientes de abatimiento) de las ganancias patrimoniales derivadas de elementos patrimoniales adquiridos antes del 31-12-1994, con el límite acumulado de 400.000 € de valor de transmisión. Base legal de la reducción DT-9ª en las casillas de ganancia patrimonial por transmisión de inmuebles en Modelo 100. AGENT-AUTHORED, grounded in the bundled authoritative ley-35-2006.html#dtnovena; operator to confirm and re-stamp."
- `reviewed_by` (verbatim): "agent-authored from bundled ley-35-2006.html#dtnovena; operator to re-stamp"

#### Bundled corpus text

> Disposición transitoria novena. Régimen transitorio aplicable a las ganancias patrimoniales derivadas de elementos patrimoniales adquiridos con anterioridad a 31 de diciembre de 1994.
>
> 1. El importe de las ganancias patrimoniales correspondientes a transmisiones de elementos patrimoniales no afectos a actividades económicas que hubieran sido adquiridos con anterioridad a 31 de diciembre de 1994, se determinará con arreglo a las siguientes reglas:
>
> 1.ª) En general, se calcularán, para cada elemento patrimonial, con arreglo a lo establecido en la Sección 4.ª, del Capítulo II, del Título III de esta Ley. De la ganancia patrimonial así calculada se distinguirá la parte de la misma que se haya generado con anterioridad a 20 de enero de 2006, entendiendo como tal la parte de la ganancia patrimonial que proporcionalmente corresponda al número de días transcurridos entre la fecha de adquisición y el 19 de enero de 2006, ambos inclusive, respecto del número total de días que hubiera permanecido en el patrimonio del contribuyente.
>
> La parte de la ganancia patrimonial generada con anterioridad a 20 de enero de 2006, se reducirá, en su caso, de la siguiente manera:
>
> a) Se calculará el período de permanencia en el patrimonio del contribuyente anterior a 31 de diciembre de 1996 del elemento patrimonial.
>
> A estos efectos, se tomará como período de permanencia en el patrimonio del contribuyente el número de años que medie entre la fecha de adquisición del elemento y el 31 de diciembre de 1996, redondeado por exceso.
>
> En el caso de derechos de suscripción se tomará como período de permanencia el que corresponda a los valores de los cuales procedan. Cuando no se hubieran transmitido la totalidad de los derechos de suscripción, se entenderá que los transmitidos correspondieron a los valores adquiridos en primer lugar.
>
> Si se hubiesen efectuado mejoras en los elementos patrimoniales transmitidos se tomará como período de permanencia de éstas en el patrimonio del contribuyente el número de años que medie entre la fecha en que se hubiesen realizado y el 31 de diciembre de 1996, redondeado por exceso.
>
> b) Se calculará el valor de transmisión de todos los elementos patrimoniales a cuya ganancia patrimonial le hubiera resultado de aplicación lo señalado en esta disposición, transmitidos desde 1 de enero de 2015 hasta la fecha de transmisión del elemento patrimonial.
>
> c) Cuando sea inferior a 400.000 euros la suma del valor de transmisión del elemento patrimonial y la cuantía a que se refiere la letra b) anterior, la parte de la ganancia patrimonial generada con anterioridad a 20 de enero de 2006 se reducirá en el importe resultante de aplicar los siguientes porcentajes por cada año de permanencia de los señalados en la letra a) anterior que exceda de dos:
>
> 1.º Si los elementos patrimoniales transmitidos fuesen bienes inmuebles, derechos sobre los mismos o valores de las entidades comprendidas en el artículo 108 de la Ley 24/1988, de 28 de julio, del Mercado de Valores, con excepción de las acciones o participaciones representativas del capital social o patrimonio de las Sociedades o Fondos de Inversión Inmobiliaria, un 11,11 por ciento.
>
> 2.º Si los elementos patrimoniales transmitidos fuesen acciones admitidas a negociación en alguno de los mercados secundarios oficiales de valores definidos en la Directiva 2004/39/CE del Parlamento Europeo y del Consejo, de 21 de abril de 2004, relativa a los mercados de instrumentos financieros, y representativos de la participación en fondos propios de sociedades o entidades, con excepción de las acciones representativas del capital social de Sociedades de Inversión Mobiliaria e Inmobiliaria, un 25 por ciento.
>
> 3.º Para las restantes ganancias patrimoniales generadas con anterioridad a 20 de enero de 2006, un 14,28 por ciento.
>
> Estará no sujeta la parte de la ganancia patrimonial generada con anterioridad a 20 de enero de 2006 derivada de elementos patrimoniales que a 31 de diciembre de 1996 y en función de lo señalado en esta letra c) tuviesen un período de permanencia, tal y como éste se define en la letra a), superior a diez, cinco y ocho años, respectivamente.
>
> d) Cuando sea superior a 400.000 euros la suma del valor de transmisión del elemento patrimonial y la cuantía a que se refiere la letra b) anterior, pero el resultado de lo dispuesto en la letra b) anterior sea inferior a 400.000 euros, se practicará la reducción señalada en la letra c) anterior a la parte de la ganancia patrimonial generada con anterioridad a 20 de enero de 2006 que proporcionalmente corresponda a la parte del valor de transmisión que sumado a la cuantía de la letra b) anterior no supere 400.000 euros.
>
> e) Cuando el resultado de lo dispuesto en la letra b) anterior sea superior a 400.000 euros, no se practicará reducción alguna a la parte de la ganancia patrimonial generada con anterioridad a 20 de enero de 2006.
>
> 2.ª) En los casos de valores admitidos a negociación en alguno de los mercados regulados y de acciones o participaciones en instituciones de inversión colectiva a las que resulte aplicable el régimen previsto en las letras a) y c) del apartado 1 del artículo 37 de esta Ley, las ganancias y pérdidas patrimoniales se calcularán para cada valor, acción o participación de acuerdo con lo establecido en la Sección 4.ª, del Capítulo II del Título III de esta Ley.
>
> Si, como consecuencia de lo dispuesto en el párrafo anterior, se obtuviera como resultado una ganancia patrimonial, se efectuará la reducción que proceda de las siguientes:
>
> a) Si el valor de transmisión fuera igual o superior al que corresponda a los valores, acciones o participaciones a efectos del Impuesto sobre el Patrimonio del año 2005, la parte de la ganancia patrimonial que se hubiera generado con anterioridad a 20 de enero de 2006 se reducirá, en su caso, de acuerdo con lo previsto en la regla 1.ª) anterior. A estos efectos, la ganancia patrimonial generada con anterioridad a 20 de enero de 2006 será la parte de la ganancia patrimonial resultante de tomar como valor de transmisión el que corresponda a los valores, acciones o participaciones a efectos del Impuesto sobre el Patrimonio del año 2005.
>
> b) Si el valor de transmisión fuera inferior al que corresponda a los valores, acciones o participaciones a efectos del Impuesto sobre el Patrimonio del año 2005, se entenderá que toda la ganancia patrimonial se ha generado con anterioridad a 20 de enero de 2006 y se reducirá, en su caso, de acuerdo con lo previsto en la regla 1.ª) anterior.
>
> 3.ª) Si se hubieran efectuado mejoras en los elementos patrimoniales transmitidos, se distinguirá la parte del valor de enajenación que corresponda a cada componente del mismo a efectos de la aplicación de lo dispuesto en este apartado 1.
>
> 2. A los efectos de lo establecido en esta disposición, se considerarán elementos patrimoniales no afectos a actividades económicas aquellos en los que la desafectación de estas actividades se haya producido con más de tres años de antelación a la fecha de transmisión.

The trailing BOE amendment-history footer ("Se modifica..."/"Se añade..." citation lines) is omitted; the substantive body above is quoted in full, unabridged. `corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 1 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-15`.

### 31. `ley-58-2003:art-26`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-58-2003-art-26.html#a26`
- `document_id`: `BOE-A-2003-23186`; `effective_from`: 2004-07-01
- `required_text`:
  - "Interés de demora"
  - "prestación accesoria"
  - "se calculará sobre el importe no ingresado en plazo"
  - "interés legal del dinero vigente"
  - "incrementado en un 25 por ciento"
- `notes` (verbatim): "LGT art 26: interes de demora. Define the accessory tax interest charge, the cases in which it is due, calculation over unpaid or improperly refunded amounts, and the art 26.6 legal-interest-plus-25-percent rule cited by RIRPF art 59 for lost deduction regularization."
- `reviewed_by` (verbatim): "agent-authored from official BOE-A-2003-23186#a26 and bundled ley-58-2003-art-26.html; operator to re-stamp"

#### Bundled corpus text

> Artículo 26. Interés de demora.
>
> 1. El interés de demora es una prestación accesoria que se exigirá a los obligados tributarios y a los sujetos infractores como consecuencia de la realización de un pago fuera de plazo o de la presentación de una autoliquidación o declaración de la que resulte una cantidad a ingresar una vez finalizado el plazo establecido al efecto en la normativa tributaria, del cobro de una devolución improcedente o en el resto de casos previstos en la normativa tributaria.
>
> La exigencia del interés de demora tributario no requiere la previa intimación de la Administración ni la concurrencia de un retraso culpable en el obligado.
>
> 2. El interés de demora se exigirá, entre otros, en los siguientes supuestos:
>
> a) Cuando finalice el plazo establecido para el pago en período voluntario de una deuda resultante de una liquidación practicada por la Administración o del importe de una sanción, sin que el ingreso se hubiera efectuado.
>
> b) Cuando finalice el plazo establecido para la presentación de una autoliquidación o declaración sin que hubiera sido presentada o hubiera sido presentada incorrectamente, salvo lo dispuesto en el apartado 2 del artículo 27 de esta ley relativo a la presentación de declaraciones extemporáneas sin requerimiento previo.
>
> c) Cuando se suspenda la ejecución del acto, salvo en el supuesto de recursos y reclamaciones contra sanciones durante el tiempo que transcurra hasta la finalización del plazo de pago en período voluntario abierto por la notificación de la resolución que ponga fin a la vía administrativa.
>
> d) Cuando se inicie el período ejecutivo, salvo lo dispuesto en el apartado 5 del artículo 28 de esta ley respecto a los intereses de demora cuando sea exigible el recargo ejecutivo o el recargo de apremio reducido.
>
> e) Cuando se reciba una petición de cobro de deudas de titularidad de otros Estados o de entidades internacionales o supranacionales conforme a la normativa sobre asistencia mutua, salvo que dicha normativa establezca otra cosa.
>
> f) Cuando el obligado tributario haya obtenido una devolución improcedente, salvo que voluntariamente regularice su situación tributaria sin perjuicio de lo dispuesto en el apartado 2 del artículo 27 de esta Ley relativo a la presentación de declaraciones extemporáneas sin requerimiento previo.
>
> 3. El interés de demora se calculará sobre el importe no ingresado en plazo o sobre la cuantía de la devolución cobrada improcedentemente, y resultará exigible durante el tiempo al que se extienda el retraso del obligado, salvo lo dispuesto en el apartado siguiente.
>
> 4. No se exigirán intereses de demora desde el momento en que la Administración tributaria incumpla por causa imputable a la misma alguno de los plazos fijados en esta ley para resolver hasta que se dicte dicha resolución o se interponga recurso contra la resolución presunta. Entre otros supuestos, no se exigirán intereses de demora a partir del momento en que se incumplan los plazos máximos para notificar la resolución de las solicitudes de compensación, el acto de liquidación o la resolución de los recursos administrativos, siempre que, en este último caso, se haya acordado la suspensión del acto recurrido.
>
> Lo dispuesto en este apartado no se aplicará al incumplimiento del plazo para resolver las solicitudes de aplazamiento o fraccionamiento del pago.
>
> 5. En los casos en que resulte necesaria la práctica de una nueva liquidación como consecuencia de haber sido anulada otra liquidación por una resolución administrativa o judicial, se conservarán íntegramente los actos y trámites no afectados por la causa de anulación, con mantenimiento íntegro de su contenido, y exigencia del interés de demora sobre el importe de la nueva liquidación. En estos casos, la fecha de inicio del cómputo del interés de demora será la misma que, de acuerdo con lo establecido en el apartado 2 de este artículo, hubiera correspondido a la liquidación anulada y el interés se devengará hasta el momento en que se haya dictado la nueva liquidación, sin que el final del cómputo pueda ser posterior al plazo máximo para ejecutar la resolución.
>
> 6. El interés de demora será el interés legal del dinero vigente a lo largo del período en el que aquél resulte exigible, incrementado en un 25 por ciento, salvo que la Ley de Presupuestos Generales del Estado establezca otro diferente.
>
> No obstante, en los supuestos de aplazamiento, fraccionamiento o suspensión de deudas garantizadas en su totalidad mediante aval solidario de entidad de crédito o sociedad de garantía recíproca o mediante certificado de seguro de caución, el interés de demora exigible será el interés legal.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 6 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 32. `madrid-dl-1-2010:art-18`

#### Registry entry

- `corpus_ref`: `corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf.extracted.md#madrid-nacimiento-adopcion-limites`
- `document_id`: `BOCM-m-2010-90050`; `effective_from`: 2023-01-01
- `required_text`:
  - "30.930 euros en tributación individual"
  - "37.322,20 euros en tributación conjunta"
  - "61.860 euros"
  - "suma de las casillas [0435] y [0460]"
- `notes` (verbatim): "DL 1/2010 art. 18.1 (Comunidad de Madrid): doble límite de la suma de las bases imponibles general y del ahorro (casillas 0435 + 0460) para aplicar las deducciones autonómicas. Límite del contribuyente: 30.930 euros en tributación individual, 37.322,20 euros en tributación conjunta. Límite de la unidad familiar: 61.860 euros (agregado de las bases imponibles de todos los miembros de la unidad familiar)."
- `reviewed_by` (verbatim): "agent-authored from the bundled AEAT Renta manual; operator to re-stamp and confirm the BOCM/BOE consolidated id"

#### Bundled corpus text

> Comunidad de Madrid: límites de la deducción por nacimiento o adopción
>
> Comunidad de Madrid
>
> • Límites de la suma de las bases imponibles general y del ahorro (suma de las casillas [0435] y [0460] de la declaración) para poder aplicar la deducción.
>
> Se exige un doble límite: uno general, que ha de cumplir el contribuyente que pretenda aplicar la deducción, y otro especifico que ha de cumplir la unidad familiar de la que forme parte:
>
> a. Contribuyente: la suma de las bases imponibles general y del ahorro del contribuyente no podrá superar:
>
> - 30.930 euros en tributación individual.
>
> - 37.322,20 euros en tributación conjunta.
>
> b. Unidad familiar: la suma de las bases imponibles general y del ahorro de todos los miembros de la unidad familiar de la que el contribuyente pueda formar parte no podrá ser superior a 61.860 euros.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2025. 1 binding(s); 1 casilla(s); 1 construct(s); 1 formula(s); 3 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-01`.

### 33. `madrid-dl-1-2010:art-2`

#### Registry entry

- `corpus_ref`: `corpus/manuals/renta/2025/part1/source.pdf.extracted.md#madrid-minimo-descendientes`
- `document_id`: `BOCM-m-2010-90050`; `effective_from`: 2020-01-01
- `required_text`:
  - "Comunidad de Madrid"
  - "mínimo por descendientes"
  - "4.400 euros anuales por el tercero"
  - "4.950 euros anuales por el cuarto y siguientes"
- `notes` (verbatim): "DL 1/2010 art. 2 (Comunidad de Madrid): importes propios del mínimo por descendientes para el cálculo del gravamen autonómico (Ley 22/2009 art. 46.1.a). Para 2020-2021 solo divergen el tercer descendiente (4.400 €) y el cuarto y siguientes (4.950 €); el primero, segundo y el suplemento por descendiente menor de tres años coinciden con los importes generales del art. 58 LIRPF. Desde 2022 (Ley 8/2022, con efectos 1-1-2022) Madrid regula también el primero, segundo y el suplemento menor-de-tres-años con cuantías propias, que se han revisado en ejercicios posteriores (Ley 13/2023, con efectos 1-1-2023)."
- `reviewed_by` (verbatim): "agent-authored from the bundled AEAT Renta manual; operator to re-stamp and confirm the BOCM/BOE consolidated id"

#### Bundled corpus text

> Comunidad de Madrid: Importes del mínimo personal y familiar
>
> Comunidad de Madrid: Importes del mínimo personal y familiar
>
> Normativa: Arts. 2, 2 bis, 2 ter y 2 quater Texto Refundido de las disposiciones legales de la Comunidad de Madrid en materia de tributos cedidos por el Estado, aprobado por Decreto Legislativo 1/2010, de 21 octubre
>
> Se establecen los siguientes importes de los mínimos del contribuyente, por descendientes, por ascendientes y por discapacidad, que deben aplicar los contribuyentes residentes en el territorio de la Comunidad Autónoma de Madrid para el cálculo del gravamen autonómico:
>
> Mínimo por descendientes
>
> • 2.575,85 euros anuales por el primer descendiente.
>
> • 2.897,83 euros anuales por el segundo.
>
> • 4.400 euros anuales por el tercero.
>
> • 4.950 euros anuales por el cuarto y siguientes.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 6 binding(s); 1 casilla(s); 1 construct(s); 6 formula(s); 24 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-03`.

### 34. `madrid-dl-1-2010:art-4`

#### Registry entry

- `corpus_ref`: `corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf.extracted.md#madrid-nacimiento-adopcion`
- `document_id`: `BOCM-m-2010-90050`; `effective_from`: 2023-01-01
- `required_text`:
  - "Por nacimiento o adopción de hijos"
  - "Decreto Legislativo 1/2010, de 21 octubre"
  - "721,70 euros por cada hijo nacido o adoptado"
  - "los padres que convivan con los hijos"
  - "en cada uno de los dos períodos impositivos"
- `notes` (verbatim): "DL 1/2010 art. 4 (Comunidad de Madrid): deducción por nacimiento o adopción de hijos. Cuantía 721,70 euros por cada hijo nacido o adoptado en la regulación vigente desde el 1 de enero de 2023 (600 euros para nacimientos/adopciones anteriores a esa fecha). La deducción se aplica en el período de nacimiento/adopción y en cada uno de los dos períodos siguientes; sólo para padres que convivan con los hijos; se prorratea por partes iguales cuando el hijo convive con ambos padres y estos tributan de forma individual."
- `reviewed_by` (verbatim): "agent-authored from the bundled AEAT Renta manual; operator to re-stamp and confirm the BOCM/BOE consolidated id"

#### Bundled corpus text

> Comunidad de Madrid: Por nacimiento o adopción de hijos
>
> Comunidad de Madrid
>
> Por nacimiento o adopción de hijos
>
> Normativa: Arts. 4 y 18.1 Texto Refundido de las disposiciones legales de la Comunidad de Madrid en materia de tributos cedidos por el Estado, aprobado por Decreto Legislativo 1/2010, de 21 octubre
>
> Cuantías de la deducción y periodos de aplicación
>
> • 721,70 euros por cada hijo nacido o adoptado.
>
> Ámbito temporal de aplicación de la deducción
>
> La deducción se aplica tanto en el período impositivo en el que se produzca el nacimiento o la adopción como en cada uno de los dos períodos impositivos siguientes.
>
> Requisitos y otras condiciones para la aplicación de la deducción
>
> • Solo tendrán derecho a practicar la deducción los padres que convivan con los hijos nacidos o adoptados.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2025. 1 binding(s); 1 casilla(s); 1 construct(s); 1 formula(s); 1 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-01`.

### 35. `orden-eha-672-2007:art-1`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-eha-672-2007.html#a1`
- `document_id`: `BOE-A-2007-6032`; `effective_from`: 2007-04-01
- `required_text`:
  - "Aprobación del modelo 130"
  - "Actividades económicas en estimación directa"
  - "código 130"
- `notes` (verbatim): "Orden EHA/672/2007 art 1: aprobacion del Modelo 130 para pagos fraccionados IRPF de actividades economicas en estimacion directa. Article 3 is the separate Modelo 131 approval authority."
- `reviewed_by` (verbatim): "verified against bundled orden-eha-672-2007.html#a1 and official BOE-A-2007-6032#a1; operator to re-stamp"

#### Bundled corpus text

> Artículo 1. Aprobación del modelo 130.
>
> Se aprueba el modelo 130. Impuesto sobre la Renta de las Personas Físicas. Actividades económicas en estimación directa. Pago fraccionado. Autoliquidación.
>
> Dicho modelo, que figura como anexo I de la presente orden, consta de los dos ejemplares siguientes:
>
> Ejemplar para el declarante.
>
> Ejemplar para la Entidad colaboradora-AEAT.
>
> El número de justificante que habrá de figurar en este modelo será un número secuencial cuyos tres primeros dígitos se corresponderán con el código 130. No obstante, en el supuesto a que se refiere el artículo 4 de la Orden HAP/2194/2013, de 22 de noviembre, por la que se regulan los procedimientos y las condiciones generales para la presentación de determinadas autoliquidaciones y declaraciones informativas de naturaleza tributaria, el número de justificante comenzará con el código 134.
>
> Se modifica por el art. único.1 de la Orden HAP/258/2015, de 17 de febrero. Ref. BOE-A-2015-1656
>
> Esta modificación surtirá efectos respecto de la presentación de las declaraciones formuladas que correspondan a la primera autoliquidación trimestral del ejercicio 2015 y siguientes, según establece la disposición final 3 de la citada Orden.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 6 binding(s); 8 construct(s); 5 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 130.

### 36. `orden-eha-672-2007:art-3`

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

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 6 binding(s); 9 construct(s); 6 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 131.

### 37. `orden-hac-1347-2024:anexo-i-instruccion-2-1`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1347-2024.html#anexo-i-instruccion-2-1`
- `document_id`: `BOE-A-2024-24949`; `effective_from`: 2025-01-01
- `required_text`:
  - "2.1 Fase 1: Rendimiento neto previo."
  - "se obtendrá multiplicando el volumen total de ingresos"
  - "por el «índice de rendimiento neto» que corresponda a cada uno de ellos"
- `notes` (verbatim): "Fase 1a agraria: rendimiento neto previo. Para cada actividad agricola, ganadera o forestal independiente, el rendimiento neto previo se obtiene multiplicando el volumen total de ingresos (incluidas subvenciones e indemnizaciones) del cultivo o explotacion por el indice de rendimiento neto que corresponda a ese producto o servicio, por el cuadro codigo-producto de indices aprobado en este mismo Anexo I. Cross-checked byte-identical against the AEAT Manual practico de Renta 2025, Parte 1, Capitulo 9, worked example "Determinacion del rendimiento neto previo de la actividad" (Dona M.J.I., manzanas / frutos no citricos, codigo 12: ingresos 18.030,00 euros x indice 0,37 = rendimiento neto previo 6.671,10 euros)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1347-2024.html; operator to re-stamp"

#### Bundled corpus text

> 2.1 Fase 1: Rendimiento neto previo.
>
> El rendimiento neto previo en el supuesto de actividades en que se realice la entrega de los productos naturales o los trabajos, servicios y actividades accesorios, se obtendrá multiplicando el volumen total de ingresos, incluidas las subvenciones corrientes o de capital y las indemnizaciones, de cada uno de los cultivos o explotaciones por el «índice de rendimiento neto» que corresponda a cada uno de ellos.
>
> Las ayudas directas desacopladas de la Política Agraria Común (ayuda básica a la renta para la sostenibilidad, ayuda redistributiva complementaria a la renta o ayuda complementaria para jóvenes agricultores) se acumularán a los ingresos procedentes de los cultivos o explotaciones del perceptor en proporción a sus respectivos importes. No obstante, cuando el perceptor de la ayuda directa hubiera obtenido ingresos por actividades agrícolas y ganaderas, distintos de la ayuda directa, por cuantía inferior al 25 por ciento del importe del total de los ingresos de tales actividades, el índice de rendimiento neto a aplicar sobre las ayudas directas será el 0,56.
>
> El rendimiento neto previo en el supuesto de actividades en las que se sometan los productos naturales a transformación, elaboración o manufactura se obtendrá multiplicando el valor de los productos naturales utilizados en el proceso, a precio de mercado, por el «índice de rendimiento neto» previsto para estos supuestos. El rendimiento neto previo se determinará en el momento de incorporación de los productos naturales a los procesos de transformación elaboración o manufactura.
>
> El procedimiento de cálculo previsto en el párrafo anterior se aplicará también a los productos sometidos a procesos de transformación, elaboración o manufactura en los años anteriores a 1998 que sean transmitidos a partir del 1 de enero del 2025. En estos casos, la determinación del rendimiento neto previo se producirá en el momento en que sean transmitidos los productos.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2025. 1 construct(s); 18 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-03`.

### 38. `orden-hac-1347-2024:anexo-i-instruccion-2-2`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1347-2024.html#anexo-i-instruccion-2-2`
- `document_id`: `BOE-A-2024-24949`; `effective_from`: 2025-01-01
- `required_text`:
  - "2.2 Fase 2: Rendimiento neto minorado."
  - "El rendimiento neto minorado se obtiene deduciendo del anterior las cantidades que, en concepto de amortización del inmovilizado material e intangible correspondan a la depreciación efectiva"
  - "No obstante, los elementos patrimoniales del inmovilizado descritos a continuación, se amortizarán conforme a la siguiente tabla"
- `notes` (verbatim): "Fase 2a agraria: rendimiento neto minorado. El rendimiento neto minorado se obtiene deduciendo del rendimiento neto previo (fase 1a) las cantidades que, en concepto de amortizacion del inmovilizado material e intangible (excluidas las actividades forestales), correspondan a la depreciacion efectiva que sufran los distintos elementos afectos por funcionamiento, uso, disfrute u obsolescencia, calculada elemento por elemento conforme a la tabla de amortizacion de este mismo Anexo I (para grupos no tabulados en el Anexo I, la orden remite a la letra b) del punto 2.2 del Anexo II). El primer slice del motor no modela un registro de bienes de inversion por elemento (valor de adquisicion, coeficiente, periodo transcurrido por bien); la amortizacion se recoge como un importe declarado por el operador, grounded en esta instruccion, y se resta del rendimiento neto previo (casilla 1538 del Modelo 100, minorando la casilla 1537 para obtener la casilla 1539). Mismo patron honesto-escalar que la minoracion por incentivos a la inversion del motor de modulos del Anexo II (instruccion 2.2.b), ver orden-hac-1347-2024:instruccion-2-2-b."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1347-2024.html; operator to re-stamp"

#### Bundled corpus text

> 2.2 Fase 2: Rendimiento neto minorado.
>
> El rendimiento neto minorado se obtiene deduciendo del anterior las cantidades que, en concepto de amortización del inmovilizado material e intangible correspondan a la depreciación efectiva que sufran los distintos elementos por funcionamiento, uso, disfrute u obsolescencia.
>
> A estos efectos, la amortización se calculará de acuerdo con lo establecido en la letra b) del punto 2.2. de las instrucciones para la aplicación de los signos, índices o módulos en el Impuesto sobre la Renta de las Personas Físicas del anexo II de esta orden.
>
> No obstante, los elementos patrimoniales del inmovilizado descritos a continuación, se amortizarán conforme a la siguiente tabla:
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
> 5
>
> Batea.
>
> 10
>
> 12 años
>
> 6
>
> Barco.
>
> 10
>
> 25 años
>
> 7
>
> Vacuno, porcino, ovino y caprino.
>
> 22
>
> 8 años
>
> 8
>
> Equino y frutales no cítricos.
>
> 10
>
> 17 años
>
> 9
>
> Frutales cítricos y viñedos.
>
> 5
>
> 45 años
>
> 10
>
> Olivar.
>
> 3
>
> 80 años
>
> Cuando se trate de actividades forestales, para el cálculo del rendimiento neto minorado no se deducirán las amortizaciones.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2025. 1 construct(s); 1 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-03`.

### 39. `orden-hac-1347-2024:anexo-i-instruccion-2-3`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1347-2024.html#anexo-i-instruccion-2-3`
- `document_id`: `BOE-A-2024-24949`; `effective_from`: 2025-01-01
- `required_text`:
  - "Rendimiento neto de módulos."
  - "Sobre el rendimiento neto minorado se aplicarán, cuando correspondan, los índices correctores que se establecen a continuación"
  - "según las circunstancias, cuantía, orden e incompatibilidad que se indica a continuación, sobre el rendimiento neto minorado o, en su caso, sobre el rectificado por aplicación de los mismos"
- `notes` (verbatim): "Fase 3a agraria: rendimiento neto de modulos. Sobre el rendimiento neto minorado (fase 2a) se aplican, cuando corresponda, los indices correctores letras a) a i) de esta instruccion, cada uno sobre el rendimiento minorado o, en su caso, sobre el ya rectificado por los indices anteriores (aplicacion secuencial, no simultanea, siguiendo el orden de letras del Anexo). El motor implementa las letras a) a h) (indices 1 a 8, casillas 1540-1547 del Modelo 100: medios de produccion ajenos 0,75; personal asalariado 0,90/0,85/0,80/0,75 por tramos; tierras arrendadas 0,90; piensos de terceros 0,50; agricultura ecologica 0,95; regadio electrico 0,75; pequena empresa (rendimiento minorado <= 9.447,91 euros) 0,90; forestales 0,80) sobre la casilla 1539 para obtener la casilla 1548 (rendimiento neto de modulos); el indice 9 (mejillon en batea, letra i) se aplica en un producto separado (casilla 0160) fuera de esta cascada. Cada indice es un valor P012 declarado por el operador/preparador segun el Diseno de Registros AEAT (aeat-dr-100-2025-dictionary, campos E5AI1-E5AI8); una casilla en blanco no aplica ningun indice (factor neutro), nunca fabrica una reduccion no declarada. Si el rendimiento neto minorado no es positivo, no se aplica ningun indice corrector (principio general de estimacion objetiva, ver el paralelo Anexo II instruccion 2.3 aplicado por el motor de modulos M131)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1347-2024.html; operator to re-stamp"

#### Bundled corpus text

> 2.3 Fase 3: Rendimiento neto de módulos.
>
> Sobre el rendimiento neto minorado se aplicarán, cuando correspondan, los índices correctores que se establecen a continuación, obteniendo el rendimiento neto de módulos.
>
> Los índices correctores se aplicarán en aquellas actividades que los tengan asignados expresamente y según las circunstancias, cuantía, orden e incompatibilidad que se indica a continuación, sobre el rendimiento neto minorado o, en su caso, sobre el rectificado por aplicación de los mismos:
>
> a) Utilización de medios de producción ajenos en actividades agrícolas.
>
> Cuando en el desarrollo de actividades agrícolas se utilicen exclusivamente medios de producción ajenos, sin tener en cuenta el suelo, y salvo en los casos de aparcería y figuras similares.
>
> Índice: 0,75.
>
> b) Utilización de personal asalariado.
>
> Cuando el coste del personal asalariado supere el porcentaje del volumen total de ingresos que se expresa, será aplicable el índice corrector que se indica.
>
> Porcentaje
>
> Índice
>
> Más del 10 por 100.
>
> 0,90
>
> Más del 20 por 100.
>
> 0,85
>
> Más del 30 por 100.
>
> 0,80
>
> Más del 40 por 100.
>
> 0,75
>
> Cuando resulte aplicable el índice corrector de la letra a) anterior no podrá aplicarse el contenido en esta letra b).
>
> c) Cultivos realizados en tierras arrendadas.
>
> Cuando los cultivos se realicen, en todo o en parte, en tierras arrendadas.
>
> Índice: 0,90 sobre los rendimientos procedentes de cultivos en tierras arrendadas.
>
> Cuando no sea posible delimitar dichos rendimientos, se prorrateará en función del porcentaje que supongan las tierras arrendadas dedicadas a cada cultivo respecto a la superficie total, propia y arrendada, dedicada a ese cultivo.
>
> d) Piensos adquiridos a terceros.
>
> Cuando en las actividades ganaderas se alimente el ganado con piensos y otros productos para la alimentación adquiridos a terceros que representen más del 50 por 100 del importe de los consumidos.
>
> Índice: 0,50.
>
> A efectos de este índice, la valoración del importe de los piensos y otros productos propios se efectuará según su valor de mercado.
>
> e) Agricultura ecológica.
>
> Cuando la producción cumpla los requisitos establecidos en el Reglamento (CE) 834/2007, del Consejo de 28 de junio de 2007 sobre producción y etiquetado de los productos ecológicos y por el que se deroga el Reglamento (CEE) N.º 2092/1991, en su normativa específica de desarrollo y en la normativa legal vigente de las correspondientes Comunidades Autónomas sobre producción ecológica y quede correspondientemente acreditado por su certificado de operador ecológico.
>
> Índice: 0,95.
>
> f) Cultivos en tierras de regadío que utilicen, a tal efecto, energía eléctrica.
>
> Cuando los cultivos se realicen, en todo o en parte, en tierras de regadío, siempre que el contribuyente, o la comunidad de regantes en la que participe, estén inscritos en el registro territorial correspondiente a la oficina gestora de impuestos especiales a que se refiere el artículo 102.2 de la Ley 38/1992, de 28 de diciembre, de Impuestos Especiales.
>
> Índice: 0,75 sobre el rendimiento procedente de los cultivos realizados en tierras de regadío por energía eléctrica.
>
> Cuando no sea posible delimitar dicho rendimiento, este índice se aplicará sobre el resultado de multiplicar el rendimiento procedente de todos los cultivos por el porcentaje que suponga la superficie de los cultivos en tierras de regadío que utilicen, a tal fin, energía eléctrica sobre la superficie total de la explotación agrícola.
>
> g) Empresas cuyo rendimiento neto minorado no supere 9.447,91 euros.
>
> Cuando el rendimiento neto minorado no supere 9.447,91 euros anuales y no se tenga derecho a la reducción regulada en el punto 3 siguiente.
>
> Índice: 0,90.
>
> h) Índice aplicable a las actividades forestales.
>
> Cuando se exploten fincas forestales gestionadas de acuerdo con planes técnicos de gestión forestal, ordenación de montes, planes dasocráticos o planes de repoblación forestal aprobados por la Administración forestal competente, siempre que el período de producción medio, según la especie de que se trate, determinado en cada caso por la Administración forestal competente, sea igual o superior a veinte años.
>
> Índice: 0,80.
>
> A las actividades forestales únicamente le será aplicable el índice señalado en la letra h) anterior.
>
> i) Índice aplicable a la actividad de producción de mejillón en batea.
>
> Se aplicará el índice 0,90 cuando la actividad se desarrolle con 3 o 4 bateas.
>
> Se aplicará el índice 0,85 cuando la actividad se desarrolle con 5 bateas.
>
> A la actividad de producción de mejillón en batea únicamente le será aplicable el índice señalado en esta letra i).

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2025. 1 construct(s); 1 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-03`.

### 40. `orden-hac-1347-2024:anexo-i-instruccion-3`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1347-2024.html#anexo-i-instruccion-3`
- `document_id`: `BOE-A-2024-24949`; `effective_from`: 2025-01-01
- `required_text`:
  - "Los agricultores jóvenes o asalariados agrarios podrán reducir el rendimiento neto de módulos correspondiente a su actividad agraria en un 25 por ciento"
  - "primera instalación como titulares de una explotación prioritaria"
- `notes` (verbatim): "Fase 4a agraria: reduccion agricultores jovenes. Los agricultores jovenes o asalariados agrarios podran reducir el rendimiento neto de modulos correspondiente a su actividad agraria en un 25 por ciento durante los periodos impositivos cerrados durante los cinco anos siguientes a su primera instalacion como titulares de una explotacion prioritaria (capitulo IV, titulo I, Ley 19/1995), siempre que acrediten un plan de mejora de la explotacion. Desarrolla, para el ejercicio 2025, la disposicion adicional sexta de la Ley del IRPF (ley-35-2006:da-6). Base legal de la casilla 1551 del Modelo 100 2025 (motor: percent(1550, 25) cuando la casilla informativa AJ del Diseno de Registros AEAT declara la elegibilidad; en blanco/No no se fabrica ninguna reduccion)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1347-2024.html; operator to re-stamp"

#### Bundled corpus text

> 3. Los agricultores jóvenes o asalariados agrarios podrán reducir el rendimiento neto de módulos correspondiente a su actividad agraria en un 25 por ciento durante los períodos impositivos cerrados durante los cinco años siguientes a su primera instalación como titulares de una explotación prioritaria, realizada al amparo de lo previsto en el capítulo IV del título I de la Ley 19/1995, de 4 de julio, de Modernización de las Explotaciones Agrarias, siempre que acrediten la realización de un plan de mejora de la explotación.
>
> La reducción prevista en este punto se tendrá en cuenta a efectos de determinar la cuantía de los pagos fraccionados que deban efectuarse.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2025. 3 casilla(s); 1 construct(s); 2 formula(s); 1 parameter(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-03`.

### 41. `orden-hac-1347-2024:da-1`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-1347-2024.html#da-primera`
- `document_id`: `BOE-A-2024-24949`; `effective_from`: 2025-01-01
- `required_text`:
  - "Reducción en 2025 del rendimiento neto calculado por el método de estimación objetiva"
  - "podrán reducir el rendimiento neto de módulos obtenido en 2025 en un 5 por ciento"
  - "Esta reducción se tendrá en cuenta para cuantificar el rendimiento neto a efectos de los pagos fraccionados correspondientes a 2025"
- `notes` (verbatim): "Reduccion general del 5 por ciento del rendimiento neto de modulos para 2025, aplicable tambien para cuantificar el rendimiento neto a efectos de los pagos fraccionados (M131) de 2025 (apartado 3)."
- `reviewed_by` (verbatim): "agent-authored from bundled orden-hac-1347-2024.html; operator to re-stamp"

#### Bundled corpus text

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

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2025. 2 casilla(s); 1 construct(s); 2 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-02`.

Also cited by modelo(s): 131.

### 42. `orden-hac-242-2025:art-3`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-242-2025.html#a3`
- `document_id`: `BOE-A-2025-5049`; `effective_from`: 2025-03-15
- `required_text`:
  - "Artículo 3"
  - "modelo D-100"
  - "Modelo 100. Documento de ingreso o devolución"
- `notes` (verbatim): "Orden HAC/242/2025 art 3: aprobacion del Modelo D-100 y documentos de ingreso o devolucion del IRPF ejercicio 2024."
- `reviewed_by` (verbatim): "verified against bundled orden-hac-242-2025.html; operator to re-stamp"

#### Bundled corpus text

> Artículo 3. Aprobación del modelo de declaración del Impuesto sobre la Renta de las Personas Físicas.
>
> Se aprueba el modelo de declaración del Impuesto sobre la Renta de las Personas Físicas y los documentos de ingreso o devolución, consistentes en:
>
> a) Declaración del Impuesto sobre la Renta de las Personas Físicas, modelo D-100, que se reproduce en el anexo I de la presente orden.
>
> b) Documento de ingreso o devolución, que se reproducen en el anexo II de la presente orden, con el siguiente detalle:
>
> 1.º Modelo 100. Documento de ingreso o devolución de la declaración del Impuesto sobre la Renta de las Personas Físicas, que consta de dos ejemplares, un documento de ingreso o devolución (ejemplar para el contribuyente) y un documento de ingreso (ejemplar para la entidad colaboradora), en su caso, para efectuar el ingreso en dicha entidad.
>
> 2.º Modelo 102. Documento de ingreso del segundo plazo de la declaración del Impuesto sobre la Renta de las Personas Físicas que consta de dos ejemplares, uno para el contribuyente y otro para la entidad colaboradora-AEAT. El número de justificante que habrá de figurar en este documento, será un número secuencial cuyos tres primeros dígitos se corresponderán con el código 102.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2024. 29 binding(s); 30 casilla(s); 1 construct(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-29`.

### 43. `rd-439-2007:art-110`

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

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 11 binding(s); 1 casilla(s); 9 construct(s); 11 formula(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

Also cited by modelo(s): 130, 131.

### 44. `rd-439-2007:art-59`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/rd-439-2007-art-59.html#a59`
- `document_id`: `BOE-A-2007-6820`; `effective_from`: 2015-07-12
- `required_text`:
  - "Pérdida del derecho a deducir"
  - "sumar a la cuota líquida estatal y a la cuota líquida autonómica"
  - "las cantidades indebidamente deducidas"
  - "más los intereses de demora"
- `notes` (verbatim): "RIRPF art 59: perdida del derecho a deducir. Obliga a sumar a la cuota liquida estatal y autonomica las deducciones indebidamente practicadas cuando se incumplen requisitos en periodos posteriores, mas intereses de demora del art 26.6 LGT. Base reglamentaria de las casillas M100 0572/0574/0577/0579 y de sus intereses 0573/0576/0578/0581."
- `reviewed_by` (verbatim): "agent-authored from official BOE-A-2007-6820#a59 and bundled rd-439-2007-art-59.html; operator to re-stamp"

#### Bundled corpus text

> Artículo 59. Pérdida del derecho a deducir.
>
> 1. Cuando, en períodos impositivos posteriores al de su aplicación se pierda el derecho, en todo o en parte, a las deducciones practicadas, el contribuyente estará obligado a sumar a la cuota líquida estatal y a la cuota líquida autonómica o complementaria devengadas en el ejercicio en que se hayan incumplido los requisitos, las cantidades indebidamente deducidas, más los intereses de demora a que se refiere el artículo 26.6 de la Ley 58/2003, de 17 de diciembre, General Tributaria.
>
> 2. Esta adición se aplicará de la siguiente forma:
>
> a) Cuando se trate de la deducción por inversión en vivienda habitual aplicable a la cuota íntegra estatal o la deducción por inversión en empresas de nueva o reciente creación, se añadirá a la cuota líquida estatal la totalidad de las deducciones indebidamente practicadas.
>
> b) Cuando se trate de las deducciones previstas en los apartados 2, 3 y 5 del artículo 68 de la Ley del Impuesto, se añadirá a la cuota líquida estatal el 50 por ciento de las deducciones indebidamente practicadas y a la cuota líquida autonómica o complementaria el 50 por ciento restante.
>
> c) Cuando se trate de deducciones establecidas por la Comunidad Autónoma en el ejercicio de las competencias normativas previstas en el artículo 46.1 de la Ley 22/2009, de 18 de diciembre, por la que se regula el sistema de financiación de las Comunidades Autónomas de régimen común y Ciudades con Estatuto de Autonomía y se modifican determinadas normas tributarias, y del tramo autonómico de la deducción por inversión en vivienda habitual, se añadirá a la cuota líquida autonómica la totalidad de las deducciones indebidamente practicadas.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

**Numeric flag**: this reference states a rate, bracket, threshold or amount -- the bundled corpus is preferred evidence but not infallible on numbers; a live BOE cross-check is the operator's to make.

#### Modelo 100 dependents

Cited in revisions 2020, 2021, 2022, 2023, 2024, 2025. 8 casilla(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 45. `orden-hac-242-2025:art-8`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-242-2025.html#a8`
- `document_id`: `BOE-A-2025-5049`; `effective_from`: 2025-03-15
- `required_text`:
  - "Plazo de presentación del borrador de declaración"
  - "2 de abril y 30 de junio de 2025"
  - "plazo específicamente establecido en el artículo 13.3"
- `notes` (verbatim): "Articulo 8 de la Orden HAC/242/2025: plazo de presentacion de la declaracion del IRPF ejercicio 2024. El plazo general comprende del 2 de abril al 30 de junio de 2025. La domiciliacion bancaria del pago puede realizarse desde el 2 de abril hasta el 25 de junio de 2025, por remision al articulo 13.3."
- `reviewed_by` (verbatim): "verified against official BOE-A-2025-5049#a8 and bundled orden-hac-242-2025.html; operator to re-stamp"

#### Bundled corpus text

> Artículo 8. Plazo de presentación del borrador de declaración y de las declaraciones del Impuesto sobre la Renta de las Personas Físicas y del Impuesto sobre el Patrimonio.
>
> 1. El plazo de presentación del borrador de declaración y de las declaraciones del Impuesto sobre la Renta de las Personas Físicas, cualquiera que sea su resultado, será el comprendido entre los días 2 de abril y 30 de junio de 2025, ambos inclusive.
>
> Lo dispuesto en este apartado se entenderá sin perjuicio del plazo específicamente establecido en el artículo 13.3 para la domiciliación bancaria del pago de las deudas tributarias resultantes de las mismas, salvo que se opte por domiciliar únicamente el segundo plazo, en cuyo caso la confirmación y presentación podrá realizarse hasta el 30 de junio de 2025.
>
> 2. El plazo de presentación de las declaraciones del Impuesto sobre el Patrimonio será el comprendido entre los días 2 de abril y 30 de junio de 2025, ambos inclusive, sin perjuicio del plazo específicamente establecido en el artículo 13.3, para la domiciliación bancaria del pago de las deudas tributarias resultantes de las mismas.
>
> CAPÍTULO V
>
> Forma, habilitación, condiciones y procedimiento para la presentación de las declaraciones

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

Cited in revisions 2024. 1 application_link(s); 1 deadline_window(s).

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-28`.

### 46. `orden-hac-248-2021:art-3`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-248-2021.html#a3`
- `document_id`: `BOE-A-2021-4238`; `effective_from`: 2021-03-18
- `required_text`:
  - "Artículo 3"
  - "modelo D-100"
  - "Modelo 100. Documento de ingreso o devolución"
- `notes` (verbatim): "Orden HAC/248/2021 art 3: aprobacion del Modelo D-100 y documentos de ingreso o devolucion del IRPF ejercicio 2020."
- `reviewed_by` (verbatim): "verified against bundled orden-hac-248-2021.html; operator to re-stamp"

#### Bundled corpus text

> Artículo 3. Aprobación del modelo de declaración del Impuesto sobre la Renta de las Personas Físicas.
>
> Se aprueba el modelo de declaración del Impuesto sobre la Renta de las Personas Físicas y los documentos de ingreso o devolución, consistentes en:
>
> a) Declaración del Impuesto sobre la Renta de las Personas Físicas, modelo D-100, que se reproduce en el anexo I de la presente orden.
>
> b) Documento de ingreso o devolución, que se reproducen en el anexo II de la presente orden, con el siguiente detalle:
>
> 1.º Modelo 100. Documento de ingreso o devolución de la declaración del Impuesto sobre la Renta de las Personas Físicas, que consta de dos ejemplares, uno para el contribuyente y otro para la entidad colaboradora-AEAT.
>
> El número de justificante que habrá de figurar en este documento será un número secuencial cuyos tres primeros dígitos se corresponderán con el código 100.
>
> 2.º Modelo 102. Documento de ingreso del segundo plazo de la declaración del Impuesto sobre la Renta de las Personas Físicas que consta de dos ejemplares, uno para el contribuyente y otro para la entidad colaboradora-AEAT. El número de justificante que habrá de figurar en este documento será un número secuencial cuyos tres primeros dígitos se corresponderán con el código 102.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

No casilla, binding, formula, construct, parameter, deadline-window or application-link entry in any M100 revision carries this citation directly -- traced by walking the revision fragments, not inferred from the snapshot ref-id sweep alone.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-29`.

### 47. `orden-hac-265-2024:art-3`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hac-265-2024.html#a3`
- `document_id`: `BOE-A-2024-5721`; `effective_from`: 2024-03-23
- `required_text`:
  - "Artículo 3"
  - "modelo D-100"
  - "Modelo 100. Documento de ingreso o devolución"
- `notes` (verbatim): "Orden HAC/265/2024 art 3: aprobacion del Modelo D-100 y documentos de ingreso o devolucion del IRPF ejercicio 2023."
- `reviewed_by` (verbatim): "verified against bundled orden-hac-265-2024.html; operator to re-stamp"

#### Bundled corpus text

> Artículo 3. Aprobación del modelo de declaración del Impuesto sobre la Renta de las Personas Físicas.
>
> Se aprueba el modelo de declaración del Impuesto sobre la Renta de las Personas Físicas y los documentos de ingreso o devolución, consistentes en:
>
> a) Declaración del Impuesto sobre la Renta de las Personas Físicas, modelo D-100, que se reproduce en el anexo I de la presente orden.
>
> b) Documento de ingreso o devolución, que se reproducen en el anexo II de la presente orden, con el siguiente detalle:
>
> 1.º Modelo 100. Documento de ingreso o devolución de la declaración del Impuesto sobre la Renta de las Personas Físicas, que consta de dos ejemplares, un documento de ingreso o devolución (ejemplar para el contribuyente) y un documento de ingreso (ejemplar para la entidad colaboradora), en su caso, para efectuar el ingreso en dicha entidad.
>
> 2.º Modelo 102. Documento de ingreso del segundo plazo de la declaración del Impuesto sobre la Renta de las Personas Físicas que consta de dos ejemplares, uno para el contribuyente y otro para la entidad colaboradora-AEAT. El número de justificante que habrá de figurar en este documento, será un número secuencial cuyos tres primeros dígitos se corresponderán con el código 102.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

No casilla, binding, formula, construct, parameter, deadline-window or application-link entry in any M100 revision carries this citation directly -- traced by walking the revision fragments, not inferred from the snapshot ref-id sweep alone.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-29`.

### 48. `orden-hfp-207-2022:art-3`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hfp-207-2022.html#a3`
- `document_id`: `BOE-A-2022-4296`; `effective_from`: 2022-03-18
- `required_text`:
  - "Artículo 3"
  - "modelo D-100"
  - "Modelo 100. Documento de ingreso o devolución"
- `notes` (verbatim): "Orden HFP/207/2022 art 3: aprobacion del Modelo D-100 y documentos de ingreso o devolucion del IRPF ejercicio 2021."
- `reviewed_by` (verbatim): "verified against bundled orden-hfp-207-2022.html; operator to re-stamp"

#### Bundled corpus text

> Artículo 3. Aprobación del modelo de declaración del Impuesto sobre la Renta de las Personas Físicas.
>
> Se aprueba el modelo de declaración del Impuesto sobre la Renta de las Personas Físicas y los documentos de ingreso o devolución, consistentes en:
>
> a) Declaración del Impuesto sobre la Renta de las Personas Físicas, modelo D-100, que se reproduce en el anexo I de la presente orden.
>
> b) Documento de ingreso o devolución, que se reproducen en el anexo II de la presente orden, con el siguiente detalle:
>
> 1.º Modelo 100. Documento de ingreso o devolución de la declaración del Impuesto sobre la Renta de las Personas Físicas, que consta de dos ejemplares, un documento de ingreso o devolución (ejemplar para el contribuyente) y un documento de ingreso (ejemplar para la entidad colaboradora), en su caso, para efectuar el ingreso en dicha entidad.
>
> 2.º Modelo 102. Documento de ingreso del segundo plazo de la declaración del Impuesto sobre la Renta de las Personas Físicas que consta de dos ejemplares, uno para el contribuyente y otro para la entidad colaboradora-AEAT. El número de justificante que habrá de figurar en este documento, será un número secuencial cuyos tres primeros dígitos se corresponderán con el código 102.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

No casilla, binding, formula, construct, parameter, deadline-window or application-link entry in any M100 revision carries this citation directly -- traced by walking the revision fragments, not inferred from the snapshot ref-id sweep alone.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-29`.

### 49. `orden-hfp-310-2023:art-3`

#### Registry entry

- `corpus_ref`: `corpus/normatives/html/orden-hfp-310-2023.html#a3`
- `document_id`: `BOE-A-2023-8118`; `effective_from`: 2023-04-01
- `required_text`:
  - "Artículo 3"
  - "modelo D-100"
  - "Modelo 100. Documento de ingreso o devolución"
- `notes` (verbatim): "Orden HFP/310/2023 art 3: aprobacion del Modelo D-100 y documentos de ingreso o devolucion del IRPF ejercicio 2022."
- `reviewed_by` (verbatim): "verified against bundled orden-hfp-310-2023.html; operator to re-stamp"

#### Bundled corpus text

> Artículo 3. Aprobación del modelo de declaración del Impuesto sobre la Renta de las Personas Físicas.
>
> Se aprueba el modelo de declaración del Impuesto sobre la Renta de las Personas Físicas y los documentos de ingreso o devolución, consistentes en:
>
> a) Declaración del Impuesto sobre la Renta de las Personas Físicas, modelo D-100, que se reproduce en el anexo I de la presente orden.
>
> b) Documento de ingreso o devolución, que se reproducen en el anexo II de la presente orden, con el siguiente detalle:
>
> 1.º Modelo 100. Documento de ingreso o devolución de la declaración del Impuesto sobre la Renta de las Personas Físicas, que consta de dos ejemplares, un documento de ingreso o devolución (ejemplar para el contribuyente) y un documento de ingreso (ejemplar para la entidad colaboradora), en su caso, para efectuar el ingreso en dicha entidad.
>
> 2.º Modelo 102. Documento de ingreso del segundo plazo de la declaración del Impuesto sobre la Renta de las Personas Físicas que consta de dos ejemplares, uno para el contribuyente y otro para la entidad colaboradora-AEAT. El número de justificante que habrá de figurar en este documento, será un número secuencial cuyos tres primeros dígitos se corresponderán con el código 102.

`corpus_ref` resolves; every declared `required_text` phrase is present verbatim in the text above. Nothing is elided.

#### Modelo 100 dependents

No casilla, binding, formula, construct, parameter, deadline-window or application-link entry in any M100 revision carries this citation directly -- traced by walking the revision fragments, not inferred from the snapshot ref-id sweep alone.

#### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-06-29`.
