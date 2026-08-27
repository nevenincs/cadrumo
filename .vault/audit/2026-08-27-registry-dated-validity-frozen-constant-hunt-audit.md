---
tags:
  - '#audit'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:aa1131382028adf5dd8908ab0a74b9b962f2f459550e1dab74b91db870e0a3dc'
related: []
---

# `registry-dated-validity` audit: `regulatory values that do not match the provision that governs them`

## Scope

A standing hunt for the bug class the mutualidad-alternativa defect belongs to,
opened after that defect showed the class exists and is invisible to every gate
this repository has.

In scope: any regulatory value -- cap, rate, threshold, coefficient, bracket,
window, reduction -- encoded in the registry or as a literal in domain or
application code, measured against the verbatim text of the provision that
governs it.

Out of scope: values whose provision is not in the bundled corpus, which are
recorded as unmeasurable rather than cleared.

## Findings

### The method, because the method is the transferable part

The mutualidad defect was not found by reading code, by diffing files, or by a
gate. Every one of those had already passed over it. It was found by reading the
statute and asking a single question of it:

> Does this provision fix A NUMBER, or does it fix A REFERENCE to a number
> somebody else re-fixes?

LIRPF art. 30.2.1.a fixes a reference -- "la cuota maxima por contingencias
comunes que este establecida, en cada ejercicio economico" -- and the registry
had frozen it as a constant. Phrases that mean a value moves and must never be a
constant: `en cada ejercicio economico`, `que este establecida`,
`reglamentariamente se establezcan`, `con los limites cuantitativos establecidos
reglamentariamente`, `el que se fije en la Ley de Presupuestos`, `vigente en cada
momento`.

Two traps nearly hid it, and both must be checked on every candidate.

**Byte-identical is not evidence of invariance.** Two per-year copies agreeing
may mean the law is stable, or may mean one was mirrored from the other. Only the
statute settles which. This was got wrong once in this campaign: the two profile
years were byte-identical on the mutualidad cap and that was reported as evidence
the surface was not year-variable. It was evidence of the mirror. The measurement
was of the copy; the conclusion was about the law.

**Check the direction of the error.** A cap set too LOW makes the taxpayer deduct
less than the law allows and OVER-pay. That produces a valid return, no refusal
and no signal. `no-silent-under-declaration` names this as the unwatched axis,
and both defects found so far run that way.

### CONFIRMED -- the seguro de enfermedad cap encodes one limb of a two-limb provision

LIRPF art. 30.2.5.a, verbatim from the bundled consolidated corpus:

> a) Las primas de seguro de enfermedad satisfechas por el contribuyente en la
> parte correspondiente a su propia cobertura y a la de su conyuge e hijos
> menores de veinticinco anos que convivan con el. El limite maximo de deduccion
> sera de 500 euros por cada una de las personas senaladas anteriormente **o de
> 1.500 euros por cada una de ellas con discapacidad**.

The registry encodes `statutory_cap_eur = 500`, `statutory_cap_period =
year_per_person`, and no variants at all. The second limb is absent.

**Direction: over-payment.** A taxpayer insuring a spouse or a child under
twenty-five with discapacidad is entitled to 1.500 euros for that person and is
held to 500. The shortfall is 1.000 euros of allowance per disabled person per
year, and it lands on exactly the population the higher limit exists to protect.
Nothing refuses, nothing warns, and the return is valid.

This is not the frozen-constant shape: both figures are literal numbers in the
statute, so neither is stale. It is the adjacent shape, and it is the one
`no-silent-under-declaration` predicts in as many words -- **a restrictive
provision used as a default**, silently capturing the population the limiting
article does not govern. The hunt found it on its first tick because the method
reads the whole provision rather than the part the code already models.

**Fixing it needs a model change, not just data.** `StatutoryCapVariant` carries
only `statutory_cap_eur_per_day`, which is the dietas shape; it cannot express
two ANNUAL per-person amounts selected by a condition. It also needs a
discapacidad signal to select on, which is taxpayer data rather than registry
data, so the selector question has to be settled before the value can be applied.
Until then the registry understates the allowance for that population.

### CLEARED -- the four dietas manutencion caps are genuinely law-fixed

RIRPF art. 9.A.3.a states the amounts as literal numbers in the article text:
`53,34` and `91,35` euros per day con pernocta, `26,67` and `48,08` sin
pernocta. No deferral clause governs them. The registry's
`statutory_cap_variants` carry exactly those four figures.

The amounts were last amended with effect from 2008-01-01 by the disposicion
final 3.1 of RD 1804/2008. The later Orden HFP/792/2023 does carry a `revisa la
cuantia` clause, which is the phrase this hunt watches for -- but the corpus note
scopes it to apartados A.2.b and B.1.a, which are LOCOMOCION, not the A.3
manutencion amounts. Checked and excluded rather than assumed.

Direction: not applicable, the values match the statute.

### CLEARED -- every LIRPF art. 23.2 rental reduccion tier is a literal in the article

Art. 23.2, verbatim from the bundled consolidated corpus, states each tier as a
number in the article text: `En un 90 por ciento` (zona tensionada with the rent
reduced `en mas de un 5 por ciento`), `En un 70 por ciento` (first letting to a
tenant `entre 18 y 35 anos` in a zona tensionada, or an Administracion Publica /
entidad sin fines lucrativos tenant), `En un 60 por ciento` (rehabilitation
finished in the two preceding years), and `En un 50 por ciento, en cualquier otro
caso`.

No deferral clause governs any of them. The shipped tier rates, the 5 per cent
threshold with its strict `>` comparison, and the inclusive 18-35 age range all
match the statute. The resolver reads each from a registry parameter per
ejercicio rather than from the code constants, which are parity anchors pinned by
a test.

Direction: not applicable, the values match the statute.

### CONFIRMED -- the rehabilitation lookback approximates a calendar rule and loses a day to leap years

Art. 23.2.c grants the 60 per cent tier when the rehabilitation `hubiera
finalizado en los dos anos anteriores a la fecha de la celebracion del contrato`.
That is a CALENDAR-relative rule. The implementation converts it to a day count:

    REHAB_LOOKBACK_DAYS: int = 730
    """``2 anos anteriores`` interpreted as 730 calendar days (2 * 365)."""

and `_qualifies_for_tier_60_rehab` in
`src/cadrumo/domain/fincas/_tier_resolver.py:390` decides with
`0 <= delta_days <= rehab_lookback_days`.

Two calendar years are 731 days whenever the span contains a 29 February, so the
730-day cutoff falls one day short. Probed through the production helper itself:

| contract | rehabilitation finished | delta | tier 60? |
|---|---|---|---|
| 2024-03-01 | 2022-03-01 | 731 d | **denied** |
| 2023-06-01 | 2021-06-01 | 730 d | granted |
| 2024-03-01 | 2022-03-02 | 730 d | granted |

The first and second rows are the SAME statutory situation -- a rehabilitation
finished exactly two calendar years before the contract -- and they resolve
differently on nothing but the presence of a leap day.

**Direction: over-payment.** A denied tier 60 falls through to tier d), so the
reduccion drops from 60 per cent to 50 per cent of the rendimiento neto positivo.
The taxpayer is refused a reduction the statute grants them, the return is valid,
and nothing warns. Same direction as the mutualidad defect and the seguro limb.

The docstring is candid that this is a choice -- "the project picks 730-day
lookback as the deterministic boundary" -- so this is an approximation that was
adopted deliberately and whose cost was not measured, rather than a mistake. The
cost is the boundary day in roughly one contract date in four.

**Remediation has a fork, which is why this is recorded rather than changed
here.** The correct comparison is calendar-relative -- the rehabilitation
qualifies when `rehabilitation_finished_date >= contract_celebration_date` minus
two calendar years, computed on the date rather than in days. Making that change
leaves `renta-<year>-rental-rehab-lookback-days` describing nothing, so the
registry parameter has to be retired across every revision that declares it or
redefined as an explicit override. That is a decision about the registry surface,
not a figure to be fetched, and no official source is missing.

### CLEARED -- every LIRPF DT 12.4 transitional boundary is a literal in the disposition

The disposition, verbatim from the bundled consolidated corpus:

> 4. El regimen transitorio previsto en esta disposicion unicamente podra ser de
> aplicacion, en su caso, a las prestaciones percibidas en el ejercicio en el que
> acaezca la contingencia correspondiente, **o en los dos ejercicios siguientes**.
>
> No obstante, en el caso de contingencias acaecidas en **los ejercicios 2011 a
> 2014**, el regimen transitorio solo podra ser de aplicacion, en su caso, a las
> prestaciones percibidas **hasta la finalizacion del octavo ejercicio siguiente**
> a aquel en el que acaecio la contingencia correspondiente. En el caso de
> contingencias acaecidas en **los ejercicios 2010 o anteriores**, el regimen
> transitorio solo podra ser de aplicacion, en su caso, a las prestaciones
> percibidas **hasta el 31 de diciembre de 2018**.

Every boundary is stated as a literal: the years 2010, 2011, 2014 and 2018, and
the two window lengths of two and eight ejercicios. There is no deferral clause.
This is a closed transitional regime the legislator fixed once, when Ley 26/2014
art. 1.86 added the apartado; it has no mechanism to move.

The shipped constants carry exactly those values -- `DT12_CLIFF_LAST_YEAR` 2018,
`DT12_TRANSITIONAL_CONTINGENCIA_FIRST_YEAR` 2011,
`DT12_TRANSITIONAL_CONTINGENCIA_LAST_YEAR` 2014,
`DT12_TRANSITIONAL_WINDOW_FOLLOWING_YEARS` 8,
`DT12_GENERAL_WINDOW_FOLLOWING_YEARS` 2 -- and the resolver was probed at every
branch boundary rather than read:

| contingencia | rescate | eligible | through | branch |
|---|---|---|---|---|
| 2009 | 2018 | yes | 2018 | cliff |
| 2009 | 2019 | no | 2018 | cliff |
| 2010 | 2018 | yes | 2018 | cliff (upper edge of the branch) |
| 2011 | 2019 | yes | 2019 | transitional (first year of the branch) |
| 2012 | 2020 | yes | 2020 | transitional (octavo ejercicio siguiente) |
| 2012 | 2021 | no | 2020 | transitional |
| 2016 | 2018 | yes | 2018 | general (segundo ejercicio siguiente) |
| 2016 | 2019 | no | 2018 | general |

The two ordinal readings were checked rather than assumed, because they are the
same shape as the rehabilitation lookback that failed: "los dos ejercicios
siguientes" from 2016 means through 2018, and "el octavo ejercicio siguiente"
from 2012 means through 2020. Both are correct. Unlike the rehabilitation case
these windows are counted in EJERCICIOS, not converted into days, so there is no
unit to approximate and no boundary for a leap year to move.

Direction: not applicable, every value matches the statute.

### CLEARED -- the Modelo 720 and 721 foreign-asset thresholds are literals in the reglamento

`application/_foreign_asset_thresholds.py` holds no literal at all: it resolves
`modelo-72x-asset-declaration-threshold-eur` and
`modelo-72x-redeclaration-increment-threshold-eur` from registry parameters. The
candidate is therefore the parameter values, which are already dated rows.

RD 1065/2007 art. 42 bis.4.e, verbatim, for the cuentas obligation behind Modelo
720:

> e) No existira obligacion de informar sobre ninguna cuenta cuando los saldos a
> 31 de diciembre a los que se refiere el apartado 2.d) no superen, conjuntamente,
> **los 50.000 euros** [...] La presentacion de la declaracion en los anos
> sucesivos solo sera obligatoria cuando cualquiera de los saldos conjuntos [...]
> hubiese experimentado un **incremento superior a 20.000 euros** respecto de los
> que determinaron la presentacion de la ultima declaracion.

Art. 42 quater states the same two figures for the moneda virtual obligation
behind Modelo 721. All six shipped values match to the cent: `50000.00` and
`20000.00` on M720 from 2013-01-01, and on M721 revisions 2023 and 2024 from
2023-01-01.

Direction: not applicable, the values match the reglamento.

### The trigger phrase was too blunt, and this candidate is what proved it

`ley-58-2003:da-18` -- the enabling disposition these parameters cite -- contains
the words **"en los terminos que reglamentariamente"**, which is on the phrase
list this hunt was given. Applied mechanically, the list flags Modelo 720 as a
defect. It is not one, and the reason matters more than the clearance.

**The trigger is not the phrase. It is where the phrase POINTS.** Follow the
reference exactly one hop and read the destination:

- **Delegation.** A law says the reglamento will set the terms, and the reglamento
  then states a literal. The value is stable until that reglamento is amended,
  which is ordinary legal drift and is exactly what `effective_from` and
  `effective_to` on the legal-catalogue entry exist to carry. Not a defect.
- **Periodic re-fixing.** A law points at an instrument that is REISSUED on a
  cycle -- an annual cotizacion orden, the Ley de Presupuestos, a tariff table.
  The value moves by design, and freezing it is the defect.

The mutualidad case is the second kind: LIRPF art. 30.2.1.a points at the cuota
maxima por contingencias comunes of the RETA, which a new orden re-fixes every
January. Modelo 720 is the first kind: DA 18 points at RD 1065/2007, which fixes
50.000 as a number.

A phrase match is therefore a reason to open the destination text, never a
verdict on its own. Recorded because a hunt that produced false positives at this
rate would be abandoned, and because the sharpened test is cheap: one hop, one
read.

### CLEARED -- the Art. 109 exemption ratio itself is a literal stated three times

RIRPF art. 109, verbatim, apartados 2, 3 and 4:

> 2. Los contribuyentes que desarrollen actividades profesionales no estaran
> obligados a efectuar pago fraccionado [...] si, en el ano natural anterior, **al
> menos el 70 por ciento de los ingresos de la actividad** fueron objeto de
> retencion o ingreso a cuenta.
>
> 3. Los contribuyentes que desarrollen actividades agricolas o ganaderas [...] si
> [...] **al menos el 70 por ciento de los ingresos procedentes de la explotacion,
> con excepcion de las subvenciones corrientes y de capital y de las
> indemnizaciones**, fueron objeto de retencion o ingreso a cuenta.
>
> 4. [...] actividades forestales [...] con la misma excepcion.

The ratio is a literal, repeated in all three apartados, with no deferral clause.
The registry carries `irpf.art_109_retained_income_exemption_ratio = 0.70` from
2019-01-01, which matches. The ratio is not the defect.

### CONFIRMED -- the Art. 109 denominator ignores an exclusion the statute states twice

Reading past the ratio to the rest of the provision is what this hunt is for, and
apartados 3 and 4 do not measure the 70 per cent over the same base as apartado
2. They exclude **las subvenciones corrientes y de capital y las
indemnizaciones**. The implementation excludes neither, and does not distinguish
the activity classes at all:

    denominator += computable_income   # every ACTIVITY_INCOME row in the period

`derive_art109_activity_income_coverage` in
`src/cadrumo/application/modelo/_art109_activity_income.py:142` sums every
active, incoming, non-personal, non-trabajo row. A sweep of the module for
`profesional`, `agricola`, `ganadera`, `forestal`, `subvenc` or `indemniz`
returns nothing.

**Direction: over-compliance, and it is not a corner case.** Subvenciones are not
subject to retencion, so they enter the denominator and never the numerator.
Every euro of subsidy therefore pushes the computed ratio DOWN, below the lawful
one, making the 70 per cent threshold harder to reach. The coverage fact feeds
`art109_activity_income_withholding_ge_70pct`, which the Modelo 130 deadline
window consumes as `equals false` to decide whether the obligation appears. A
farmer whose lawful ratio clears 70 per cent but whose computed ratio does not is
shown a Modelo 130 obligation and pays a pago fraccionado the reglamento exempts
them from. PAC subsidies are near-universal and substantial for that population.

The registry already knows the scope. The deadline window's own explanation reads
"salvo la excepcion Art. 109 por cobertura de retencion o ingreso a cuenta en
actividades **profesionales, agricolas, ganaderas o forestales**". The scope is
written into the data and dropped in the computation.

**The mirror risk, recorded for completeness.** With no activity-class gate, an
empresario -- who gets no art. 109 exemption at all -- would have the flag
computed for them like anyone else, and a true result would REMOVE a Modelo 130
obligation they owe. That runs in the under-declaration direction. Exposure is
low in practice because retencion on actividades economicas reaches profesionales
(RIRPF art. 95) and certain agrarian activities, not general empresarios, so an
empresario's numerator is normally zero. Low is not none, and the gate is absent
either way.

**The remedy already exists in this codebase, unused by this consumer.**
`src/cadrumo/domain/transactions/_volumen_ingresos.py` exists precisely to
distinguish `SUBVENCION_CORRIENTE` from `SUBVENCION_CAPITAL`, and the profile
schema carries `taxpayer_type` and `iae_epigraph`. So this is not blocked on a
model that does not exist; it is one sibling calculation applying a distinction
its neighbour ignores.

Note the two provisions need DIFFERENT exclusions and must not share one helper
unexamined: art. 110 excludes "las subvenciones de capital y las indemnizaciones"
and keeps subvenciones corrientes in, while art. 109.3 and 109.4 exclude
subvenciones corrientes AND de capital AND indemnizaciones. The existing module's
docstring already notes that "the distinction runs INSIDE subsidies" -- it got
art. 110 right. Art. 109 needs the broader exclusion.

### OUT OF CLASS -- core/external_constants carries no regulatory value

`core/external_constants.toml` holds 140 declarations across twelve sections, and
every one is an externally-defined IDENTIFIER rather than a regulatory quantity:
AEAT hostnames, sede paths, clave endpoints, help-page URLs, oracle locations,
portal paths and Google OAuth scopes. A scan for a non-string value returns
exactly one hit in the whole file.

That hit is `aeat.notifications_query.lookback_years = 10`, and it is not a
regulatory value either. It sets how far back the AEAT notifications search sets
its `fecha desde` filter, because the portal defaults to one month and was
answering a narrower question than the reader intended. It computes no tax, gates
no obligation and caps no deduction.

Its own comment already performs this hunt's adjacency check and gets it right:
"Four years is la LGT art-66 prescription period, so this deliberately reaches
further: a notification older than prescription is still part of the record an
operator needs to see". The constant is deliberately WIDER than the legal period.

Direction: a lookback set too short would hide notifications from the operator.
At ten years against a four-year prescription period it errs toward showing more
of the record, so there is no taxpayer-detriment direction to report.

### The class, restated now that every lead carries a verdict

Seven leads produced four confirmed defects, and calling the class "a regulatory
value frozen as a constant where the provision makes it move" turned out to
describe only the first of them. The mutualidad cap was the only frozen value.
The other three are:

- a two-limb provision encoded as one limb (seguro de enfermedad, 500 without
  1.500);
- a calendar rule re-expressed in a different unit (the rehabilitation lookback,
  two years as 730 days);
- a provision whose ratio was copied and whose DENOMINATOR was not (Art. 109,
  subvenciones and indemnizaciones left in the base).

What unites all four is not staleness. **The numbers were always right and always
available in the statute; what the code lost was WHO each number applies to, and
OVER WHAT.** The mutualidad figure applied per ejercicio, the 1.500 applied to
persons with discapacidad, the two years applied on a calendar, the 70 per cent
applied to a base net of subsidies. Every defect is a lost qualifier, not a lost
digit.

That is the sharper statement of the class, and it changes where to look next: not
at numbers that might be stale, but at provisions where the code implements one
clause and the statute has two.

### NOTED -- the locomocion per-kilometre exencion is absent, not wrong

The same Orden HFP/792/2023 raised the locomocion allowance to `0,26 euros` per
kilometre with effect from 2023-07-17, from `0,19`. That is a value that really
did move, mid-year, and would be a textbook instance of this bug class if it were
encoded.

It is not encoded anywhere: a sweep of the registry, domain, application and core
trees for the rate found only unrelated matches (address kilometre fields on
Modelo 840, treaty withholding ceilings, a docstring timing figure). This is an
absence in product coverage, not a defect in a stored value, and it is recorded
here so a later reader does not re-derive the same negative.

Worth noting for whoever models it: the 2023 change lands mid-ejercicio, so that
year carries two rates and the value is dated from birth.

## Recommendations

- Settle the seguro de enfermedad discapacidad limb. Two decisions are needed
  before data: whether `StatutoryCapVariant` gains an annual amount alongside its
  per-day one, and where the discapacidad signal for the insured person comes
  from. Neither is a figure that has to be fetched -- both numbers are in the
  statute -- so this is blocked on design, not on evidence.
- Settle the rehabilitation lookback. Replace the 730-day count with
  calendar-relative arithmetic and decide what becomes of the
  `renta-<year>-rental-rehab-lookback-days` parameter it makes vacuous. Blocked on
  that decision, not on evidence.
- Widen the hunt beyond values to UNIT and BOUNDARY approximations. The
  rehabilitation finding is not a wrong number -- every number involved is right.
  It is a calendar rule re-expressed in days, and the loss only appears at the
  boundary. Any constant whose docstring says the project "picks", "interprets"
  or "approximates" a statutory phrase is a candidate on the same footing as a
  frozen constant.
- Fix the Art. 109 denominator for agricultural, livestock and forestry
  activities, and add the activity-class gate. Both building blocks already ship:
  the subvencion-kind distinction in `domain/transactions/_volumen_ingresos.py`
  and `taxpayer_type` / `iae_epigraph` on the profile schema. Use a BROADER
  exclusion than art. 110's, which is deliberately narrower.
- None of the three open findings is blocked on a figure. Each needs a SCOPING
  decision -- which population a rule applies to, or which signal selects between
  two lawful values -- and every number involved is already in the statute or
  already in this repository.
- When the hunt resumes, aim it at the restated class rather than the original
  one: look for provisions where the code implements ONE clause and the statute
  has TWO. Reading past the figure the code already uses, to the rest of the
  sentence it sits in, found three of the four defects.
- When a value is cleared, quote the provision that clears it. A clearance
  without the text is the same unverified assertion the hunt exists to find.
