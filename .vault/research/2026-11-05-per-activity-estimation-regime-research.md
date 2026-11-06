---
tags:
  - '#research'
  - '#per-activity-estimation-regime'
date: '2026-11-05'
modified: '2026-11-05'
body_schema: 'body-v2'
body_hash: 'sha256:a4c56787c06bde64aae66d5f3e9acaa900e495135d88f7fda1d72c586a6f4cfb'
related: []
---

# `per-activity-estimation-regime` research: `RIRPF art. 35: per-activity estimation regime in the year a new activity starts`

The question is whether the IRPF estimation method (estimación directa normal, directa simplificada, objetiva) is a fact about the taxpayer or about each economic activity, and when two methods can stand together in one ejercicio. It matters because the profile holds one taxpayer-wide dated `irpf.estimation_regime`, so a lawful mixed year cannot be stated. Today the 2025 Modelo 100 Anexo D inventory resolver refuses that year rather than misattributing a row. The evidence shows that the method is selected per activity, that the law then forces a single method across all activities, and that it tolerates a mixed state only in the year a new activity starts, for the activities already in progress. The mixed state ends from the following year.

## Findings

### Objective estimation is applied per activity, but excludes direct estimation for the whole taxpayer

- RIRPF art. 32.1: objetiva "se aplicará a cada una de las actividades económicas, aisladamente consideradas, que determine el Ministro", unless the taxpayer renounces or is excluded under arts. 33 and 34. Eligibility is therefore per activity (the Orden de módulos lists activities by IAE epígrafe).
- LIRPF art. 31.1.3ª.a): objetiva cannot be applied when the taxpayer "determine[n] el rendimiento neto de alguna actividad económica por el método de estimación directa".
- RIRPF art. 35 (title "Incompatibilidad de la estimación objetiva con la estimación directa"), first paragraph: a taxpayer using estimación directa in either modality for any activity uses it for all activities, "en la modalidad correspondiente".
- Consequence: in a steady-state year every activity has the same method. That is why a taxpayer-wide field was a sound first model.

### The start-of-activity exception: two methods in one ejercicio

- RIRPF art. 35, second paragraph: when an activity is started during the year that is not included in objetiva, or for which objetiva is renounced, the incompatibility "no surtirá efectos para ese año respecto a las actividades que se venían realizando con anterioridad". In that year the new activity is in directa and the earlier activities stay in objetiva.
- RIRPF art. 28.3 has the same structure between the two direct modalities. Normal for one activity means normal for all, except that an activity started during the year with a renunciation of simplificada does not move the earlier activities that year. AEAT Manual Renta 2025, cap. 7, "Incompatibilidad entre métodos y modalidades", Ejemplo 2: a new activity started 5 May with renunciation is in normal while the existing one stays in simplificada. "No surtirá efectos hasta el año siguiente", when both are in normal.
- The exception shields only the activities that were already running. The new activity carries its own method from its start.
- Counter-example in the same manual, Ejemplo 1: a lawyer in directa simplificada starts a módulos-eligible agricultural activity. That activity goes into simplificada at once, because the existing activity's directa drags the new one. The exception does not apply in that direction. Only a new activity outside objetiva, or renouncing it, while earlier activities are in objetiva (art. 35), or a new activity renouncing simplificada while earlier ones are in simplificada (art. 28.3), produces a mixed year.
- AEAT leaflet "Actividades económicas", 3.1 "Incompatibilidad de regímenes" (updated 26/03/2026), repeats both exceptions. It says the incompatibility takes effect "a partir del año siguiente".

### What happens the next year

- RIRPF art. 34.2: the art. 35 incompatibility is a cause of exclusion from objetiva. Art. 34.1 says exclusion takes effect from the start of the following year. Art. 34.3 says exclusion places the taxpayer in directa simplificada for the following three years, in the terms of art. 28.1.
- Renunciation of objetiva (art. 33) is made in December, at the censal alta of a new activity, or by filing the first-quarter pago fraccionado in direct form. It binds for three years (art. 33.3). LIRPF art. 30.1 sets the three-year consequence of renouncing simplificada.
- Mixed state is therefore bounded to one ejercicio per start event. From 1 January of the next year a single method is again taxpayer-wide.

### The form already models activities by method

- Modelo 100 records activities in separate occurrences by method: `ActividadEstDirecta` and `ActividadEstObj` appear in every authored revision (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/revision.toml` and its siblings for 2021, 2023 and 2024). A mixed year fills both. The return carries the method per activity, not per taxpayer.

### Pagos fraccionados in a mixed year: Modelo 130 and Modelo 131 are both due (closed 2026-11-05)

- RIRPF art. 110.1 computes the instalment by method, in separate letters for one taxpayer: a) "Por las actividades que estuvieran en el método de estimación directa" (20 % of the year-to-date net yield), b) "Por las actividades que estuvieran en el método de estimación objetiva" (4/3/2 % of the módulos yield, from the data at 1 January "o, en caso de inicio de actividades, del día en que éstas hubiesen comenzado"). Art. 110.3 likewise deducts withholdings separately for direct-estimation professional activities (year to date) and objetiva activities (the quarter). Art. 111 sets the same quarterly deadlines for both.
- Orden EHA/672/2007 attaches each form to a method, not to a taxpayer. Art. 2 says Modelo 130 is used by taxpayers who "determinen su rendimiento neto con arreglo al método de estimación directa". Art. 4 says Modelo 131 is used by those who do so "con arreglo al método de estimación objetiva". Neither excludes the other.
- Conclusion: in a lawful mixed year the taxpayer files Modelo 130 for the direct-estimation activities and Modelo 131 for the objetiva activities, for the same quarters. A secondary source states the same: https://palenciaasesores.es/modelo-131-pago-fraccionado-modulos/. No AEAT page found states the mixed case in words; the conclusion rests on the BOE texts above.
- The art. 109.2–109.4 exemptions are per activity ("en relación con las mismas"). The 70 % test is applied per activity, independent of the method mix.
- Consequence for the ADR's "any activity in the period" readers: the 131 window applies when any activity in force in the quarter is in objetiva, and the 130 window when any is in directa. In a mixed year both apply.

### Modelo 036 records the mixed year per activity (closed 2026-11-05)

- Modelo 036 states the method's inclusion taxpayer-wide: casilla 604 for objetiva, 608 for directa normal, 609 for directa simplificada; renuncia 605/610, revocación 606/611, exclusión 607/612, baja 617.
- The start-year exception is recorded per activity. Casilla 613 (objetiva) is filled in a modification declaration when a new activity outside módulos, or renouncing them, starts while another was in objetiva. "La actividad que estaba en módulos lo seguirá estando hasta el final del período impositivo, pero hay que identificar de qué actividad se trata a través de su código IAE o en su caso el código de actividad". Casilla 614 is the same for simplificada when the new activity renounces it: "consignará el grupo o epígrafe/sección del IAE o el código de aquellas actividades a las que continuará aplicando la modalidad simplificada hasta el final del período impositivo".
- AEAT's own exclusion example (a DGT consulta) has epígrafe 663.9 in objetiva and, from 2009, 619.2 and 614.1 in directa in the same year. The earlier activity is excluded from objetiva the following year even though the new activities were deregistered at the end of the start year.
- Consequence: the censal record identifies the activities in a mixed year by IAE epígrafe, which matches the per-activity row with `iae_epigraph`. A later censal cotejo could adopt casillas 613/614 onto `activities.<n>.estimation_regime`, keyed by epígrafe. That adoption is a separate decision under the censo-regimen record, blocked on a real specimen.
- Modelo 037 was not examined separately. The guide pages read cover Modelo 036 only.

### Not investigated

- Agrarian módulos specifics (art. 32.2.b' thresholds, IVA REAGP coupling under LIRPF art. 31.1.2ª) were not examined. They do not change whether the method is per activity.
- No BOE text was found that lets a taxpayer hold different methods for continuing activities outside the start year. The search covered RIRPF arts. 28 and 32–36 and LIRPF arts. 30–31.

## Sources

- RIRPF (RD 439/2007), consolidated text: https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820 (anchors `#a28`, `#a32`, `#a33`, `#a34`, `#a35`), retrieved 2026-11-05
- LIRPF (Ley 35/2006), consolidated text: https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764 (anchors `#a28`, `#a30`, `#a31`), retrieved 2026-11-05
- AEAT Manual práctico Renta 2025, cap. 7, incompatibilidad: https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c07-rendimientos-actividades-economicas-estimacion-directa/concepto-ambito-aplicacion-metodo-estimacion-directa/incompatibilidad-metodos-modalidades.html
- AEAT Manual práctico Renta 2025, cap. 7, ejemplos: https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c07-rendimientos-actividades-economicas-estimacion-directa/concepto-ambito-aplicacion-metodo-estimacion-directa/ejemplos.html
- AEAT leaflet Actividades económicas, 3.1: https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/folleto-actividades-economicas/3-impuesto-sobre-renta-personas-fisicas/3_1-incompatibilidad-regimenes.html
- RIRPF arts. 109–111: https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820 (anchors `#a109`, `#a110`, `#a111`), retrieved 2026-11-05
- Orden EHA/672/2007 (Modelos 130 and 131), consolidated: https://www.boe.es/buscar/act.php?id=BOE-A-2007-6032 (arts. 2 and 4), retrieved 2026-11-05
- AEAT Guía práctica modelo censal 036, cap. 7, método de estimación: https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/guia-practica-cumplimentacion-modelo-censal-036/capitulo-07-irpf-is-irnr/irpf-modelo-036/metodo-estimacion-irpf.html and its subpages `estimacion-objetiva/casilla-613.html`, `estimacion-directa-simplificada/casilla-614.html`, `estimacion-objetiva/exclusion-metodo-estimacion-objetiva.html`
- Secondary (not authority): https://palenciaasesores.es/modelo-131-pago-fraccionado-modulos/
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/revision.toml` (ActividadEstDirecta / ActividadEstObj occurrences)
- The AEAT manual pages were read through a summarising fetch. Short quotations are verbatim; the rest is paraphrase and should be re-read before code.
