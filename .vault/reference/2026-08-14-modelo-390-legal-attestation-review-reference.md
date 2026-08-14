---
tags:
  - '#reference'
  - '#modelo-390-legal-attestation-review'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:475c85077bba130f55bfad63d62278d0099d2f66238ccefc5423afa5adddaff5'
related:
  - '[[2026-08-10-aeat-export-fragment-generator-authority-plan]]'
  - '[[2026-08-14-registry-campaign-sequencing-operator-attestation-ledger-audit]]'
---

# `modelo-390-legal-attestation-review` reference: `Modelo 390 2025 legal-reference attestation review packet`

This packet exists to make ten personal legal attestations a bounded,
reviewable act instead of ten bare identifiers. Modelo 390 revision 2025
already carries a verified export layout and is blocked purely on attestation:
one revision stamp plus these ten legal references, currently at
`agent_reviewed`, all shared with revisions 2022-2024 so attesting each once
clears it everywhere it is cited.

For each reference this packet places the registry's own claim next to the
actual bundled corpus text it points at, quoted verbatim, and lists what in
the 2025 revision depends on it. It does not state whether the claim and the
source agree -- that is the operator's act, and stating it here would turn the
operator's sign-off into a rubber stamp on agent work. The one exception is a
structural discrepancy: a broken `corpus_ref`, a `required_text` phrase absent
from the quoted text, or a citation that plainly names a different subject.
None of the ten references below triggered that exception; each `corpus_ref`
resolved and each declared `required_text` phrase is present verbatim in the
quoted text. That is reported as a mechanical fact -- text is present or
absent -- and is not a judgement that the provision legally supports what the
casilla, binding or formula claims about it.

**Standing caveat on the `notes` field.** Every `notes` value quoted in this
packet is agent-authored registry content, not operator-verified prose. Where
a note asserts that the bundled text was already checked against a live BOE
or AEAT source, that assertion is itself an unverified agent claim, carrying
exactly the same weight as any other agent claim in this packet -- it is not
independent confirmation, and it may have been written by the same agent that
authored the entry it purports to validate. That is the same shape as a
`required_text` cross-check that passes because one author wrote both the
excerpt and the phrase validating it: self-attesting and unfalsifiable from
inside the packet. Two of the ten entries below carry this kind of
self-verification claim in their `notes`: `art-69` ("Bundled text checked
against the live BOE consolidated text on 2026-08-05...") and `art-70`
(the same sentence, dated the same day, against a different redaction). The
other eight `notes` values are explanatory only and make no verification
claim about themselves. This caveat is not a statement that either claim is
false -- it is stated once here, rather than adjudicated, so it is not
mistaken for independent confirmation while reading either section. These
same two entries are also two of the three sections below whose quoted
corpus text is elided for length rather than reproduced in full (`art-69`
and `art-70`; the third elided section, `art-104`, carries no such claim):
on those two sections the reader faces both a self-verification claim and a
quoted block that is not the complete article, which is exactly where the
least raw primary source sits next to the strongest reassurance that it was
already checked -- worth reading with more care than the other eight
sections, not less.

Two references (`art-104`, `art-105`) carry a `reviewed_by` value that
explicitly names itself as unstamped agent work awaiting operator re-stamp;
that text is quoted verbatim in its own section.

Where a reference establishes a rate, amount or threshold, this packet flags
that the bundled corpus text is preferred evidence but not infallible on
numbers, and that a live BOE or AEAT consolidated-text cross-check is the
operator's to make -- no such fetch was performed here. None of the ten
references below state a numeric rate, amount or threshold, so this flag does
not apply to any of them; noted for completeness rather than omitted silently.

This document is read-only working material. No `operator_reviewed` stamp was
applied or could be applied through any path available to this session, and
nothing under `modelos/390/**` was touched to produce it.

## Summary

Ten sections follow, one per legal reference: `ley-37-1992:art-69`,
`art-70`, `art-85`, `art-104`, `art-105`, `art-115`, `art-116`, `art-121`, and
`rd-1624-1992:art-29`, `art-30`. Each section carries the same four parts in
the same order: the registry's current entry, the bundled corpus text quoted
verbatim, what in the 2025 revision depends on it, and the entry's current
review status.

## 1. `ley-37-1992:art-69` -- Lugar de realización de las prestaciones de servicios. Reglas generales

### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-37-1992.html#a69`
- `document_id`: `BOE-A-1992-28740`; `effective_from`: 2010-01-01
- `required_text`:
  - "Lugar de realización de las prestaciones de servicios. Reglas generales"
  - "Cuando el destinatario sea un empresario o profesional que actúe como tal"
- `notes` (verbatim): "LIVA art 69: general place-of-supply rules for services. Grounds M349 intracommunity service prestation/acquisition keys S and I together with the RIVA recapitulativa obligation. With arts. 68 and 70 it is also the rule set that decides WHICH IVA category a cross-border service belongs to; that selection is a declared judgement made by the operator, never derived by the system from the counterparty's country alone. Bundled text checked against the live BOE consolidated text on 2026-08-05: the anchored #a69 unit of the bundled ley-37-1992.html is character-identical to the current redaction BOE-A-2014-12329 (in force 2015-01-01), apart from the BOE amendment-history footnotes the consolidated page appends after the article body."

### Bundled corpus text (verbatim, from the anchored `#a69` unit)

> Artículo 69. Lugar de realización de las prestaciones de servicios. Reglas generales.
>
> Uno. Las prestaciones de servicios se entenderán realizadas en el territorio de aplicación del Impuesto, sin perjuicio de lo dispuesto en el apartado siguiente de este artículo y en los artículos 70 y 72 de esta Ley, en los siguientes casos:
>
> 1.º Cuando el destinatario sea un empresario o profesional que actúe como tal y radique en el citado territorio la sede de su actividad económica, o tenga en el mismo un establecimiento permanente o, en su defecto, el lugar de su domicilio o residencia habitual, siempre que se trate de servicios que tengan por destinatarios a dicha sede, establecimiento permanente, domicilio o residencia habitual, con independencia de dónde se encuentre establecido el prestador de los servicios y del lugar desde el que los preste.
>
> 2.º Cuando el destinatario no sea un empresario o profesional actuando como tal, siempre que los servicios se presten por un empresario o profesional y la sede de su actividad económica o establecimiento permanente desde el que los preste o, en su defecto, el lugar de su domicilio o residencia habitual, se encuentre en el territorio de aplicación del Impuesto.
>
> Dos. Por excepción de lo dispuesto en el número 2.º del apartado Uno del presente artículo, no se entenderán realizados en el territorio de aplicación del Impuesto los servicios que se enumeran a continuación cuando el destinatario de los mismos no sea un empresario o profesional actuando como tal y esté establecido o tenga su domicilio o residencia habitual fuera de la Comunidad, salvo en el caso de que dicho destinatario esté establecido o tenga su domicilio o residencia habitual en las Islas Canarias, Ceuta o Melilla [enumerates: propiedad intelectual/industrial; cesión de fondos de comercio; publicidad; asesoramiento/auditoría/ingeniería/abogacía; tratamiento de datos; traducción; seguros/servicios financieros; cesión de personal; doblaje de películas; arrendamiento de bienes muebles corporales (salvo transporte); acceso a redes de gas/electricidad/calefacción; obligaciones de no prestar los anteriores].
>
> Tres. A efectos de esta Ley, se entenderá por: 1.º Sede de la actividad económica [...]; 2.º Establecimiento permanente [...]; 3.º Servicios de telecomunicación [...]; 4.º Servicios prestados por vía electrónica [...]; 5.º Servicios de radiodifusión y televisión [...].
>
> [Followed by BOE amendment-history footnotes: Ley 28/2014 art. 1.12/13, Ley 39/2010 art. 79.8, Ley 2/2010 art. 1.6 with effects from 2010-01-01.]

The apartado Dos enumeration and apartado Tres definitions are elided above
(`[...]`) for length; both are present in full in the bundled file and neither
elision touches a `required_text` phrase. `corpus_ref` resolves; both
declared `required_text` phrases are present verbatim in the text above.

### Modelo 390 (2025) dependents

Cited on every AIC (adquisiciones intracomunitarias) rate-box casilla and its
binding, across both "bienes" and "servicios" categories and all seven rate
rungs (0%, 2%, 4%, 5%, 7.5%, 10%, 21%), plus the rate-blind AIC total
casillas/bindings, the `iva.anual.autorepercutido.intracomunitaria` casilla
and binding, the `iva.anual.total-bases-cuotas-iva` casilla (box 34), and the
formula `modelo-390-iva-anual-total-bases-cuotas-iva` that sums the devengada
total. 38 casillas and 36 bindings cite this reference in the 2025 revision;
representative examples: `iva.anual.aic.bienes.tipo-21.base` /
`iva.anual.aic.bienes.tipo-21.cuota` (binding
`modelo-390-iva-aic-bienes-tipo-21-base` /
`modelo-390-iva-aic-bienes-tipo-21-cuota`),
`iva.anual.autorepercutido.intracomunitaria`.

### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-06-27`.

## 2. `ley-37-1992:art-70` -- Lugar de realización de las prestaciones de servicios. Reglas especiales

### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-37-1992.html#a70`
- `document_id`: `BOE-A-1992-28740`; `effective_from`: 2010-01-01
- `required_text`:
  - "Lugar de realización de las prestaciones de servicios. Reglas especiales"
  - "Los relacionados con bienes inmuebles que radiquen en el citado territorio"
- `notes` (verbatim): "LIVA art 70: special place-of-supply rules for services. Complements art 69 for M349 service keys S and I where official instructions distinguish services localized in or outside the TAI. Its apartado Uno reglas (inmuebles, transporte, acceso a manifestaciones, servicios electronicos, restauracion, mediacion, trabajos sobre bienes muebles, arrendamiento de medios de transporte) override the art. 69 general rule, so category selection for a cross-border service must be read here before art. 69 is applied; the selection stays a declared operator judgement. Bundled text checked against the live BOE consolidated text on 2026-08-05: the anchored #a70 unit of the bundled ley-37-1992.html is character-identical to the current redaction BOE-A-2023-12204 (in force 2023-05-26), apart from the BOE amendment-history footnotes the consolidated page appends after the article body."

### Bundled corpus text (verbatim, from the anchored `#a70` unit)

> Artículo 70. Lugar de realización de las prestaciones de servicios. Reglas especiales.
>
> Uno. Se entenderán prestados en el territorio de aplicación del Impuesto los siguientes servicios:
>
> 1.º Los relacionados con bienes inmuebles que radiquen en el citado territorio. Se considerarán relacionados con bienes inmuebles, entre otros, los siguientes servicios: a) El arrendamiento o cesión de uso [...]; b) los relativos a ejecuciones de obra inmobiliarias; c) los de carácter técnico sobre dichas obras; d) los de gestión relativos a bienes inmuebles; e) los de vigilancia o seguridad; f) los de alquiler de cajas de seguridad; g) la utilización de vías de peaje; h) los de alojamiento hostelero.
>
> 2.º Los de transporte [...], por la parte de trayecto que discurra por el territorio de aplicación del Impuesto tal y como éste se define en el artículo 3 de esta Ley: a) transporte de pasajeros; b) transporte de bienes distintos de los del artículo 72 cuyo destinatario no actúe como empresario o profesional.
>
> 3.º El acceso a manifestaciones culturales, artísticas, deportivas, científicas, educativas, recreativas o similares [...] siempre que su destinatario sea un empresario o profesional actuando como tal y dichas manifestaciones tengan lugar efectivamente en el citado territorio.
>
> 4.º-9.º [Servicios electrónicos/telecomunicaciones/radiodifusión; restauración y catering; mediación; servicios accesorios a transportes y ejecuciones de obra sobre bienes muebles; arrendamiento de medios de transporte -- full enumerations with sub-conditions present in the bundled file.]
>
> Dos. Asimismo, se considerarán prestados en el territorio de aplicación del Impuesto los servicios que se enumeran a continuación cuando [...] no se entiendan realizados en la Comunidad, Islas Canarias, Ceuta o Melilla, pero su utilización o explotación efectivas se realicen en dicho territorio: 1.º Los enunciados en el apartado dos del artículo 69 [...]; 2.º Los de arrendamiento de medios de transporte.
>
> [Followed by an extensive BOE amendment-history footnote list running from Ley 13/2023 back to Real Decreto-Ley 12/1995, present in full in the bundled file.]

Apartados 4.º through 9.º are elided above (`[...]`) for length; present in
full in the bundled file, and no elision touches a `required_text` phrase.
`corpus_ref` resolves; both declared `required_text` phrases are present
verbatim in the text above.

### Modelo 390 (2025) dependents

Same dependent population as `art-69` above (cited jointly on every AIC
rate-box casilla/binding, the rate-blind AIC totals, the ISP casilla, box 34,
and its formula) -- 38 casillas, 36 bindings, 1 formula
(`modelo-390-iva-anual-total-bases-cuotas-iva`).

### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-06-27`.

## 3. `ley-37-1992:art-85` -- Sujetos pasivos (adquisiciones intracomunitarias de bienes)

### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-37-1992.html#a85`
- `document_id`: `BOE-A-1992-28740`; `effective_from`: 1993-01-01
- `required_text`:
  - "Sujetos pasivos"
  - "En las adquisiciones intracomunitarias de bienes los sujetos pasivos del impuesto serán quienes las realicen"
- `notes` (verbatim): "LIVA art 85: sujetos pasivos de las adquisiciones intracomunitarias de bienes. Distinto de art. 84, que gobierna la inversion del sujeto pasivo para servicios/entregas de no establecidos; el sujeto pasivo de una AIB de bienes es quien realiza la adquisicion, por remision al art. 71."

### Bundled corpus text (verbatim, from the anchored `#a85` unit)

> Artículo 85. Sujetos pasivos.
>
> En las adquisiciones intracomunitarias de bienes los sujetos pasivos del impuesto serán quienes las realicen, de conformidad con lo previsto en el artículo 71 de esta Ley.
>
> CAPÍTULO III
> Importaciones

`corpus_ref` resolves; both declared `required_text` phrases are present
verbatim in the text above. The article is one paragraph; nothing is elided.

### Modelo 390 (2025) dependents

Same AIC-bienes/servicios casilla and binding population as `art-69`/`art-70`
above (38 casillas, 36 bindings) -- this reference is cited specifically as
the sujeto-pasivo grounding shared across the AIC rate-box layer.

### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-08-06`.

## 4. `ley-37-1992:art-104` -- La prorrata general

### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-37-1992-art-104.html#a104` (a
  standalone excerpt file, not the consolidated `ley-37-1992.html`)
- `document_id`: `BOE-A-1992-28740`; `effective_from`: 1993-01-01
- `required_text` (10 phrases, listing the rounding rule and all six art.
  104.Tres exclusions):
  - "La prorrata de deducción resultante de la aplicación de los criterios anteriores se redondeará en la unidad superior."
  - "Tres. Para la determinación del porcentaje de deducción no se computarán en ninguno de los términos de la relación:"
  - "Las operaciones realizadas desde establecimientos permanentes situados fuera del territorio de aplicación del Impuesto."
  - "Las cuotas del Impuesto sobre el Valor Añadido que hayan gravado directamente las operaciones a que se refiere el apartado anterior."
  - "El importe de las entregas y exportaciones de los bienes de inversión que el sujeto pasivo haya utilizado en su actividad empresarial o profesional."
  - "El importe de las operaciones inmobiliarias o financieras que no constituyan actividad empresarial o profesional habitual del sujeto pasivo."
  - "En todo caso se reputará actividad empresarial o profesional habitual del sujeto pasivo la de arrendamiento."
  - "Tendrán la consideración de operaciones financieras a estos efectos las descritas en el artículo 20, apartado uno, número 18.º de esta Ley, incluidas las que no gocen de exención."
  - "Las operaciones no sujetas al impuesto según lo dispuesto en el artículo 7 de esta Ley."
  - "Las operaciones a que se refiere el artículo 9, número 1.º, letra d) de esta Ley."
- `notes` (verbatim): "Articulo 104 LIVA: la prorrata general. Define el calculo del porcentaje de deduccion como cociente entre el importe total de las operaciones que originan el derecho a la deduccion (numerador) y el importe total de todas las operaciones realizadas en el ejercicio (denominador), redondeado por exceso a la unidad superior. El apartado Tres enumera las seis operaciones excluidas de ambos terminos de la relacion (art 104.Tres reglas 1a a 6a): (1) operaciones desde establecimientos permanentes fuera del TAI; (2) las cuotas de IVA que gravaron directamente esas operaciones; (3) entregas y exportaciones de bienes de inversion utilizados en la actividad; (4) operaciones inmobiliarias o financieras que no constituyan actividad habitual (arrendamiento siempre habitual; operaciones financieras del art 20.Uno.18); (5) operaciones no sujetas del art 7; (6) operaciones del art 9, numero 1.o, letra d) (autoconsumo del promotor). Las subvenciones no vinculadas al precio NO son una exclusion del art 104.Tres: fueron suprimidas del denominador de la prorrata por la Ley 3/2006 (BOE-A-2006-5691), por lo que no se computan en absoluto en lugar de excluirse de un volumen computado."

### Bundled corpus text (verbatim, from the standalone excerpt)

> Artículo 104. La prorrata general.
>
> Uno. En los casos de aplicación de la regla de prorrata general, sólo será deducible el impuesto soportado en cada período de liquidación en el porcentaje que resulte de lo dispuesto en el apartado dos siguiente. Para la aplicación de lo dispuesto en el párrafo anterior no se computarán en el impuesto soportado las cuotas que no sean deducibles en virtud de lo dispuesto en los artículos 95 y 96 de esta Ley.
>
> Dos. El porcentaje de deducción a que se refiere el apartado anterior se determinará multiplicando por 100 el resultante de una fracción en la que figuren: 1.º En el numerador, el importe total [...] de las entregas de bienes y prestaciones de servicios que originen el derecho a la deducción [...]. 2.º En el denominador, el importe total [...] de las entregas de bienes y prestaciones de servicios realizadas por el sujeto pasivo [...], incluidas aquellas que no originen el derecho a deducir. [Special rules for cesión de divisas/pagarés/valores follow in full in the excerpt.] La prorrata de deducción resultante de la aplicación de los criterios anteriores se redondeará en la unidad superior.
>
> Tres. Para la determinación del porcentaje de deducción no se computarán en ninguno de los términos de la relación: 1.º Las operaciones realizadas desde establecimientos permanentes situados fuera del territorio de aplicación del Impuesto. 2.º Las cuotas del Impuesto sobre el Valor Añadido que hayan gravado directamente las operaciones a que se refiere el apartado anterior. 3.º El importe de las entregas y exportaciones de los bienes de inversión que el sujeto pasivo haya utilizado en su actividad empresarial o profesional. 4.º El importe de las operaciones inmobiliarias o financieras que no constituyan actividad empresarial o profesional habitual del sujeto pasivo. En todo caso se reputará actividad empresarial o profesional habitual del sujeto pasivo la de arrendamiento. Tendrán la consideración de operaciones financieras a estos efectos las descritas en el artículo 20, apartado uno, número 18.º de esta Ley, incluidas las que no gocen de exención. 5.º Las operaciones no sujetas al impuesto según lo dispuesto en el artículo 7 de esta Ley. 6.º Las operaciones a que se refiere el artículo 9, número 1.º, letra d) de esta Ley.
>
> Cuatro. A los efectos del cálculo de la prorrata, se entenderá por importe total de las operaciones la suma de las contraprestaciones correspondientes a las mismas [...]. Cinco. [regla del coste soportado en TAI para ejecuciones de obras/servicios fuera del territorio]. Seis. [normas de imputación temporal, remisión al Título IV].
>
> [Followed by BOE amendment-history footnotes: Ley 22/2013 art. 78, Ley 3/2006 art. único.3, Ley 6/2000 art. 6.1, Ley 55/1999 art. 6.10, Ley 9/1998 art. único.9, Ley 66/1997 art. 6.16.]

Portions of apartado Dos (the cesión de divisas/pagarés/valores special
rules) and apartados Cuatro through Seis are elided above (`[...]`) for
length; present in full in the bundled excerpt, and no elision touches a
`required_text` phrase. `corpus_ref` resolves; all ten declared
`required_text` phrases are present verbatim in the text above.

### Modelo 390 (2025) dependents

Casilla `iva.anual.regularizacion-prorrata-definitiva` (feeds the annual
prorrata-regularization figure), binding
`modelo-390-prorrata-regularizacion-anual`, and the formula
`modelo-390-iva-anual-cuota-deducible-total`.

### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-07`. `reviewed_by`
(verbatim, quoted in full because it is a flag, not a name): **"agent-authored
verbatim from the bundled corpus text; operator to re-stamp"**.

## 5. `ley-37-1992:art-105` -- Procedimiento de la prorrata general

### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-37-1992.html#a105`
- `document_id`: `BOE-A-1992-28740`; `effective_from`: 1993-01-01
- `required_text`:
  - "el porcentaje de deducción provisionalmente aplicable cada año natural será el fijado como definitivo para el año precedente"
  - "En la última declaración-liquidación del impuesto correspondiente a cada año natural el sujeto pasivo calculará la prorrata de deducción definitiva"
  - "practicará la consiguiente regularización de las deducciones provisionales"
  - "En los supuestos de interrupción durante uno o más años naturales de la actividad empresarial o profesional"
  - "el que globalmente corresponda al conjunto de los tres últimos años naturales en que se hubiesen realizado operaciones"
- `notes` (verbatim): "Articulo 105 LIVA: procedimiento de la prorrata general. Apartado Uno: el porcentaje de deduccion provisionalmente aplicable cada ano natural sera el fijado como definitivo para el ano precedente. Apartado Cuatro: en la ultima declaracion-liquidacion de cada ano natural el sujeto pasivo calcula la prorrata definitiva en funcion de las operaciones del ano y practica la consiguiente regularizacion de las deducciones provisionales - la cuota de esa regularizacion se consigna en la casilla 44 del Modelo 303 y en el campo de regularizacion anual del Modelo 390. Base legal de la regularizacion prorrata por porcentaje definitivo. Apartado Cinco: en los supuestos de interrupcion durante uno o mas anos naturales de la actividad (o de un sector diferenciado), el porcentaje definitivamente aplicable durante cada uno de esos anos es el que globalmente corresponda al conjunto de los tres ULTIMOS anos naturales en que se hubiesen realizado operaciones (porcentaje global sobre los volumenes agregados de los tres anos activos, saltando la interrupcion; no la media de los tres porcentajes ni los tres anos de calendario). Base legal de la siembra del ejercicio que reanuda tras una interrupcion."

### Bundled corpus text (verbatim, from the anchored `#a105` unit)

> Artículo 105. Procedimiento de la prorrata general.
>
> Uno. Salvo lo dispuesto en los apartados dos y tres de este artículo, el porcentaje de deducción provisionalmente aplicable cada año natural será el fijado como definitivo para el año precedente.
>
> Dos. Podrá solicitarse la aplicación de un porcentaje provisional distinto del establecido en el apartado anterior cuando se produzcan circunstancias susceptibles de alterarlo significativamente.
>
> Tres. En los supuestos de inicio de actividades empresariales o profesionales, y en los de inicio de actividades que vayan a constituir un sector diferenciado respecto de las que se viniesen desarrollando con anterioridad, el porcentaje provisional de deducción aplicable durante el año en que se comience la realización de las entregas de bienes y prestaciones de servicios correspondientes a la actividad de que se trate será el que se hubiese determinado según lo previsto en el apartado dos del artículo 111 de esta Ley. En los casos en que no se hubiese determinado un porcentaje provisional de deducción según lo dispuesto en el apartado dos del artículo 111 de esta Ley, el porcentaje provisional a que se refiere el párrafo anterior se fijará de forma análoga a lo previsto en dicho precepto.
>
> Cuatro. En la última declaración-liquidación del impuesto correspondiente a cada año natural el sujeto pasivo calculará la prorrata de deducción definitiva en función de las operaciones realizadas en dicho año natural y practicará la consiguiente regularización de las deducciones provisionales.
>
> Cinco. En los supuestos de interrupción durante uno o más años naturales de la actividad empresarial o profesional o, en su caso, de un sector diferenciado de la misma, el porcentaje de deducción definitivamente aplicable durante cada uno de los mencionados años será el que globalmente corresponda al conjunto de los tres últimos años naturales en que se hubiesen realizado operaciones.
>
> Seis. El porcentaje de deducción, determinado con arreglo a lo dispuesto en los apartados anteriores de este artículo, se aplicará a la suma de las cuotas soportadas por el sujeto pasivo durante el año natural correspondiente, excluidas las que no sean deducibles en virtud de lo establecido en los artículos 95 y 96 de esta Ley.
>
> Se modifica el apartado 3 por el art. 5.5 de la Ley 14/2000, de 29 de diciembre. Ref. BOE-A-2000-24357.

`corpus_ref` resolves; all five declared `required_text` phrases are present
verbatim in the text above. Nothing is elided -- the full article is quoted.

### Modelo 390 (2025) dependents

Same as `art-104`: casilla `iva.anual.regularizacion-prorrata-definitiva`,
binding `modelo-390-prorrata-regularizacion-anual`, formula
`modelo-390-iva-anual-cuota-deducible-total`.

### Review status

`review_status = "agent_reviewed"`; `reviewed_at = 2026-07-07`. `reviewed_by`
(verbatim, quoted in full because it is a flag, not a name): **"agent-authored
from bundled ley-37-1992.html#a105 arts. 105.Uno/.Cuatro/.Cinco procedimiento
de la prorrata general; operator to re-stamp"**.

## 6. `ley-37-1992:art-115` -- Supuestos generales de devolución

### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-37-1992.html#a115`
- `document_id`: `BOE-A-1992-28740`; `effective_from`: 1993-01-01
- `required_text`:
  - "Supuestos generales de devolución"
  - "Los sujetos pasivos que no hayan podido hacer efectivas las deducciones originadas en un período de liquidación por el procedimiento previsto en el artículo 99"
  - "solicitar la devolución del saldo a su favor existente a 31 de diciembre de cada año"
- `notes` (verbatim): "Articulo 115 LIVA: supuestos generales de devolucion. Conecta el saldo a favor no hecho efectivo por compensacion del articulo 99 con la solicitud de devolucion al cierre del ultimo periodo de liquidacion del ano natural."

### Bundled corpus text (verbatim, from the anchored `#a115` unit)

> Artículo 115. Supuestos generales de devolución.
>
> Uno. Los sujetos pasivos que no hayan podido hacer efectivas las deducciones originadas en un período de liquidación por el procedimiento previsto en el artículo 99 de esta Ley, por exceder la cuantía de las mismas de la de las cuotas devengadas, tendrán derecho a solicitar la devolución del saldo a su favor existente a 31 de diciembre de cada año en la autoliquidación correspondiente al último período de liquidación de dicho año.
>
> Dos. No obstante, tendrán derecho a solicitar la devolución del saldo a su favor existente al término de cada período de liquidación los sujetos pasivos a que se refiere el artículo 116 de esta Ley.
>
> Tres. En los supuestos a que se refieren este artículo y el siguiente, la Administración procederá, en su caso, a practicar liquidación provisional dentro de los seis meses siguientes al término del plazo previsto para la presentación de la autoliquidación en que se solicite la devolución del Impuesto [...]. El procedimiento de devolución será el previsto en los artículos 124 a 127, ambos inclusive, de la Ley 58/2003, de 17 de diciembre, General Tributaria, y en su normativa de desarrollo. [Further paragraphs on the six-month provisional-liquidation deadline and late interest under LGT art. 26.6 follow in full in the bundled file.]
>
> [Followed by BOE amendment-history footnotes: Ley 4/2008 art. 5.9 (effective for periods from 2009-01-01), Ley 53/2002 art. 4.16, Ley 66/1997 art. 6.19.]

The later paragraphs of apartado Tres (provisional-liquidation timing and
late-interest mechanics) are elided above (`[...]`) for length; present in
full in the bundled file, and no elision touches a `required_text` phrase.
`corpus_ref` resolves; all three declared `required_text` phrases are present
verbatim in the text above.

### Modelo 390 (2025) dependents

Casillas `iva.anual.compensacion-ultimo-periodo-97` (box 97) and
`iva.anual.compensacion-generada-ejercicio-no-97` (box 662), bindings
`modelo-390-prev-303-compensacion-ultimo-periodo` and
`modelo-390-prev-303-compensacion-generada-ejercicio-no-97`.

### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-05-19`.

## 7. `ley-37-1992:art-116` -- Solicitud de devoluciones al fin de cada período de liquidación

### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-37-1992.html#a116`
- `document_id`: `BOE-A-1992-28740`; `effective_from`: 1993-01-01
- `required_text`:
  - "Solicitud de devoluciones al fin de cada período de liquidación"
  - "podrán optar por solicitar la devolución del saldo a su favor existente al término de cada período de liquidación"
  - "El período de liquidación de los sujetos pasivos que opten por este procedimiento coincidirá con el mes natural"
- `notes` (verbatim): "Articulo 116 LIVA: solicitud de devoluciones al fin de cada periodo de liquidacion. Base legal de la devolucion periodica para sujetos pasivos que optan por el procedimiento reglamentario."

### Bundled corpus text (verbatim, from the anchored `#a116` unit)

> Artículo 116. Solicitud de devoluciones al fin de cada período de liquidación.
>
> Uno. Los sujetos pasivos podrán optar por solicitar la devolución del saldo a su favor existente al término de cada período de liquidación conforme a las condiciones, términos, requisitos y procedimiento que se establezcan reglamentariamente. El período de liquidación de los sujetos pasivos que opten por este procedimiento coincidirá con el mes natural, con independencia de su volumen de operaciones.
>
> Dos. En los supuestos a que se refiere el artículo 15, apartado dos de esta Ley, la persona jurídica que importe los bienes en el territorio de aplicación del Impuesto podrá recuperar la cuota correspondiente a la importación cuando acredite la expedición o transporte de los bienes a otro Estado miembro y el pago del Impuesto en dicho Estado.
>
> Se modifica por el art. 5.10 de la Ley 4/2008, de 23 de diciembre. Ref. BOE-A-2008-20802. Aplicable a los periodos de liquidación que se inicien desde el 1 de enero de 2009, según establece la disposición final 5.d). Se modifica el apartado 2 por el art. 10.14 de la Ley 13/1996, de 30 de diciembre. Ref. BOE-A-1996-29117.

`corpus_ref` resolves; all three declared `required_text` phrases are present
verbatim in the text above. Nothing is elided -- the full article is quoted.

### Modelo 390 (2025) dependents

Same as `art-115`: casillas `iva.anual.compensacion-ultimo-periodo-97` and
`iva.anual.compensacion-generada-ejercicio-no-97`, bindings
`modelo-390-prev-303-compensacion-ultimo-periodo` and
`modelo-390-prev-303-compensacion-generada-ejercicio-no-97`.

### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-05-19`.

## 8. `ley-37-1992:art-121` -- Determinación del volumen de operaciones

### Registry entry

- `corpus_ref`: `corpus/normatives/html/ley-37-1992.html#a121`
- `document_id`: `BOE-A-1992-28740`; `effective_from`: 1993-01-01
- `required_text`:
  - "Determinación del volumen de operaciones"
  - "se entenderá por volumen de operaciones"
  - "año natural anterior"
- `notes` (verbatim): "LIVA art 121: determinacion del volumen de operaciones. Defines the operation-volume calculation used by regulated thresholds, including the RIVA art 71 large-company monthly liquidation threshold."

### Bundled corpus text (verbatim, from the anchored `#a121` unit)

> Artículo 121. Determinación del volumen de operaciones.
>
> Uno. A efectos de lo dispuesto en esta Ley, se entenderá por volumen de operaciones el importe total, excluido el propio impuesto sobre el Valor Añadido y, en su caso, el recargo de equivalencia y la compensación a tanto alzado, de las entregas de bienes y prestaciones de servicios efectuadas por el sujeto pasivo durante el año natural anterior, incluidas las exentas del Impuesto. En los supuestos de transmisión de la totalidad o parte de un patrimonio empresarial o profesional, el volumen de operaciones a computar por el sujeto pasivo adquirente será el resultado de añadir al realizado, en su caso, por este último durante el año natural anterior, el volumen de operaciones realizadas durante el mismo período por el transmitente en relación a la parte de su patrimonio transmitida.
>
> Dos. Las operaciones se entenderán realizadas cuando se produzca o, en su caso, se hubiera producido el devengo del Impuesto sobre el Valor Añadido.
>
> Tres. Para la determinación del volumen de operaciones no se tomarán en consideración las siguientes: 1.º Las entregas ocasionales de bienes inmuebles. 2.º Las entregas de bienes calificados como de inversión respecto del transmitente, de acuerdo con lo dispuesto en el artículo 108 de esta Ley. 3.º Las operaciones financieras mencionadas en el artículo 20, apartado uno, número 18.º de esta Ley, incluidas las que no gocen de exención, así como las operaciones exentas relativas al oro de inversión comprendidas en el artículo 140 bis de esta Ley, cuando unas y otras no sean habituales de la actividad empresarial o profesional del sujeto pasivo.
>
> Se modifica por el art. 6.12 de la Ley 55/1999, de 29 de diciembre. Ref. BOE-A-1999-24786. Se modifica por el art. 6.20 de la Ley 66/1997, de 30 de diciembre. Ref. BOE-A-1997-28053.

`corpus_ref` resolves; all three declared `required_text` phrases are present
verbatim in the text above. Nothing is elided -- the full article is quoted.

### Modelo 390 (2025) dependents

Casillas `iva.anual.volumen.entregas-intracomunitarias` (box 103) and
`iva.anual.volumen.exportaciones-exentas` (box 104), bindings
`modelo-390-volumen-entregas-intracomunitarias-base` and
`modelo-390-volumen-exportaciones-exentas-base`.

### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-06-29`.

## 9. `rd-1624-1992:art-29` -- Devoluciones de oficio

### Registry entry

- `corpus_ref`: `corpus/normatives/html/rd-1624-1992-art-29.html#a29` (a
  standalone excerpt file)
- `document_id`: `BOE-A-1992-28925`; `effective_from`: 1993-01-01
- `required_text`:
  - "Devoluciones de oficio"
  - "se realizarán por transferencia bancaria"
  - "artículo 115 de la Ley del Impuesto"
- `notes` (verbatim): "Reglamento del IVA art 29: forma de las devoluciones de oficio vinculadas al articulo 115 LIVA."

### Bundled corpus text (verbatim, from the standalone excerpt)

> Artículo 29. Devoluciones de oficio.
>
> Las devoluciones de oficio a que se refiere el artículo 115 de la Ley del Impuesto, se realizarán por transferencia bancaria.
>
> El Ministro de Economía y Hacienda podrá autorizar la devolución por cheque cruzado cuando concurran circunstancias que lo justifiquen.

`corpus_ref` resolves; all three declared `required_text` phrases are present
verbatim in the text above. Nothing is elided -- the full excerpt is quoted.

### Modelo 390 (2025) dependents

Same as `art-115`/`art-116`: casillas
`iva.anual.compensacion-ultimo-periodo-97` and
`iva.anual.compensacion-generada-ejercicio-no-97`, bindings
`modelo-390-prev-303-compensacion-ultimo-periodo` and
`modelo-390-prev-303-compensacion-generada-ejercicio-no-97`.

### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-05-19`.

## 10. `rd-1624-1992:art-30` -- Devoluciones al término de cada período de liquidación

### Registry entry

- `corpus_ref`: `corpus/normatives/html/rd-1624-1992-art-30.html#a30` (a
  standalone excerpt file)
- `document_id`: `BOE-A-1992-28925`; `effective_from`: 1993-01-01
- `required_text`:
  - "Devoluciones al término de cada período de liquidación"
  - "deberán estar inscritos en el registro de devolución mensual"
  - "no iniciarán el procedimiento de devolución"
- `notes` (verbatim): "Reglamento del IVA art 30: registro de devolucion mensual y limites para solicitar devolucion en periodos distintos del ultimo periodo anual."

### Bundled corpus text (verbatim, from the standalone excerpt)

> Artículo 30. Devoluciones al término de cada período de liquidación.
>
> Para poder ejercitar el derecho a la devolución establecido en los artículos 116 y 163 nonies de la Ley del Impuesto, los sujetos pasivos deberán estar inscritos en el registro de devolución mensual regulado en este artículo.
>
> En otro caso, sólo podrán solicitar la devolución del saldo que tengan a su favor al término del último período de liquidación de cada año natural de acuerdo con lo dispuesto en el artículo 115.uno de la Ley del Impuesto.
>
> Las solicitudes de devolución consignadas en declaraciones-liquidaciones que correspondan a períodos de liquidación distintos del último del año natural presentadas por sujetos pasivos no inscritos en el registro de devolución mensual, no iniciarán el procedimiento de devolución a que se refiere este artículo.

`corpus_ref` resolves; all three declared `required_text` phrases are present
verbatim in the text above. Nothing is elided -- the full excerpt is quoted.

### Modelo 390 (2025) dependents

Same as `art-29`/`art-115`/`art-116`: casillas
`iva.anual.compensacion-ultimo-periodo-97` and
`iva.anual.compensacion-generada-ejercicio-no-97`, bindings
`modelo-390-prev-303-compensacion-ultimo-periodo` and
`modelo-390-prev-303-compensacion-generada-ejercicio-no-97`.

### Review status

`review_status = "agent_reviewed"`; `reviewed_by = "agent-review"`;
`reviewed_at = 2026-05-19`.
