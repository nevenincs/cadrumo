---
tags:
  - '#audit'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:4ef291ee70e3ae146c754f28772f43d194a4c873164c4fbf1b6ff3ba861b793c'
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

### FIXED -- the seguro de enfermedad cap encodes one limb of a two-limb provision

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

### FIXED -- the rehabilitation lookback approximates a calendar rule and loses a day to leap years

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

### FIXED -- the Art. 109 denominator ignores an exclusion the statute states twice

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

## Disposition

All four confirmed defects are fixed. Each landed with real-behaviour tests and a gate
proven to bite by mutating the shipped data or code from outside the tracked tree.

| defect | direction | what shipped |
|---|---|---|
| mutualidad cap frozen at 15000 | over-payment | five grounded dated rows, 2022-2026 |
| seguro de enfermedad, 1.500 limb absent | over-payment | both limbs as annual per-person variants |
| rehabilitation lookback as 730 days | over-payment | calendar-relative window, days parameter retired |
| Art. 109 denominator not net of subvenciones | over-compliance | art. 109's own concept set and activity gate |

**All four now reach production.** The seguro fix was the one that did not, and it was
closed in Step P05.S21: `aggregate_renta_ledger_expenses` now populates
`statutory_cap_variant_person_counts` from the bucket's profile record, so a married
couple deducts the 1.000 euros the article grants instead of the 500 that shipped, and a
declared grado at or above the RIRPF art. 72 threshold selects the 1.500 limb. Six
real-path tests drive stored facts through the domain count, the context and the
registry cap variants; three bite proofs confirm the gates fail when the wiring is
removed, when the wiring names a variant the corpus does not declare, and when a count
is inflated.

Reaching production cost two relocations, both recorded in the Step. The count moved off
the `RentaFamilyProfile` assembler onto a plain descendant sequence, because routing it
through `application/modelo` hit the existing modelo-imports-aggregation cycle; and
`profile_fact_index` moved from `application/modelo/profile_binding.py` to
`application/user_profile/projections.py`, where both application packages can read it
without either importing the other. Neither left an alias behind.

The lesson worth carrying is that the distance between "expressible" and "reachable" was
not evidence or law -- every figure and every signal was already present and correct. It
was one unsupplied argument at one construction site, invisible to every test that
called the resolver directly. A rule proved only at its own resolver is not proved to
run.

The Art. 109 fix has the same shape in reverse: it IS reachable, because the activity
class and income concept are already carried on the ledger row itself.

### What the fixes changed about the class, beyond the four cases

Two of the four were fixed by widening a concept the codebase already had rather than
adding a second one. `StatutoryCapVariant` already meant "a cap selected by a legally
relevant condition" and only its UNIT was daily; the seguro limbs are the same concept
in annual per-person form. `add_prescription_years` already did calendar-year
arithmetic with a leap clamp, and the rehabilitation window is the same arithmetic
under a different provision -- so it moved to `core.calendar_shift.shift_by_calendar_years`
and both domains now read one primitive with a name that says what it does rather than
which law first needed it.

That is the durable lesson under the four findings. In every case the codebase already
held the distinction the statute draws; what was missing was the recognition that a
second provision needed the same one. A hunt for this class should therefore look for
provisions the code half-implements, not for values that look stale.

## Recommendations

- The insured-person counts are wired (Step P05.S21) and the higher limb is now
  selected in production. The residual recommendation is narrower: any future rule
  whose behaviour depends on a caller-supplied argument needs a test that reaches it
  through the shipped entry point, because a resolver-level test cannot tell a
  supplied argument from an omitted one.
- The rehabilitation parameter question is settled: the days declaration was
  retired across all six revisions that carried it and re-declared in years, so no
  parameter describes a unit the code no longer uses. A gate reds if any revision
  re-declares it in days.
- Widen the hunt beyond values to UNIT and BOUNDARY approximations. The
  rehabilitation finding is not a wrong number -- every number involved is right.
  It is a calendar rule re-expressed in days, and the loss only appears at the
  boundary. Any constant whose docstring says the project "picks", "interprets"
  or "approximates" a statutory phrase is a candidate on the same footing as a
  frozen constant.
- Operator re-stamp on the one tax review these fixes rest on: the art. 109
  profesional selector groups A04 (artisticas y deportivas) with A05, following the
  art. 95 partition this registry already grounds. It is marked agent_reviewed in
  the parameter's own reviewed_by field.
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

## Citation grounding: the corpus carried pointers, not evidence

Closed in Step P05.S22. All eighty-three category citations set `quote` to a dotted
locale key, no `categories.registry.` key exists in any of the four catalogues, and
the loader resolved each through the translation fallback to the literal word "Quote".
The check that should have caught it asserted the translatable was non-empty AFTER
that resolution, so it inspected "Quote", found it non-empty, and passed eighty-three
times. The maintenance tooling documented the opposite intent the whole time: citation
quotes are "verbatim AEAT excerpts and are authored as Spanish text in the registry
TOML, never translated".

Forty-five statutory citations now carry verbatim Spanish transcribed from the bundled
consolidated corpus, covering LIRPF arts. 28, 29 and 30 and RIRPF arts. 9 and 22 across
thirteen distinct excerpts. Each is read back through `legal_reference_quotes_corpus`,
the same containment mechanism the IVA catalogue adopted for the identical defect, so
the invariant is containment rather than non-emptiness -- what a paraphrase fails and a
length check cannot.

### CONFIRMED -- the seguro citation pointed at the wrong letter of its own rule

`seguros_salud_autonomo` cited LIRPF "art. 30.2.5.c regla 1.a". Letter c of that rule
is *gastos de manutencion del propio contribuyente*; regla 1.a is *aportaciones a
mutualidades de prevision social*. The premium deduction is letter a:

> a) Las primas de seguro de enfermedad satisfechas por el contribuyente en la parte
> correspondiente a su propia cobertura y a la de su conyuge e hijos menores de
> veinticinco anos que convivan con el.

Direction of error: none reached the taxpayer -- the cap amounts were read from the
registry, not from the locator, so no figure was wrong. The loss was auditability. An
operator following the citation landed on a rule about restaurant meals, and the
locale key is precisely why it survived: a citation that renders as "Quote" cannot be
read against the article it names, so the two are never compared.

### The state of the absent evidence is now declared, not assumed

Forty-one citations name AEAT *Manual practico* editions and portal help pages. None
is in the bundled corpus, so no verbatim excerpt can be transcribed from anything this
repository holds. They carry `source_not_bundled` with a stated reason rather than
invented text, and the model refuses a quotation parked in that state -- the
containment gate skips it by design, so parked text would read as evidence to anyone
printing it while never being checked against anything.

`SOURCE_NOT_BUNDLED` is deliberately a third state rather than a reuse of the IVA
catalogue's `UNRESOLVED`. Unresolved asserts the provision was read and found not to
support the rule; these were not read at all. Collapsing them would assert a reading
nobody performed. The shared enum was relocated to `core.citation_grounding` in the
same change, since a symbol gaining a second domain gets a neutral canonical home
rather than an alias.

### Two of my own earlier defects, found by this pass

The mutualidad rule's `notes` key sat AFTER its cap-schedule array-of-tables, so TOML
bound it to the final schedule row and the rule itself declared none. The locale
scanner stringified that absence into the literal key `"None"` -- unauthorable in any
catalogue, and so a permanently red parity gate with no fix available inside the
locale tooling. Introduced by the dated cap-schedule work earlier in this campaign.
The lesson generalises past this file: in TOML an array-of-tables header ENDS the
parent table, so a scalar written after one silently changes owner, and no validator
sees a missing optional field.

The two statutory-cap variant labels added with the seguro fix were also never authored
in the four catalogues. Both are closed, and the `"None"` shape is now gated.

## Defect hunt, round two: four candidates, four verdicts

### CONFIRMED -- the home-office suministros deduction supplied its own second factor

LIRPF art. 30.2.5.b, verbatim from the bundled consolidated corpus:

> b) En los casos en que el contribuyente afecte parcialmente su vivienda habitual al
> desarrollo de la actividad economica, los gastos de suministros de dicha vivienda,
> tales como agua, gas, electricidad, telefonia e Internet, en el porcentaje resultante
> de aplicar el 30 por ciento a la proporcion existente entre los metros cuadrados de
> la vivienda destinados a la actividad respecto a su superficie total, salvo que se
> pruebe un porcentaje superior o inferior.

The deductible share is a PRODUCT: the statutory 30 per cent times the taxpayer's own
measured area proportion. The article supplies the first factor and nothing supplies
the second, which is why the sentence ends inviting proof of a different figure rather
than naming a fallback.

Five categories shipped `default_ratio = "0.30"` beside `statutory_multiplier = "0.30"`.
The evaluator reads `default_ratio` in the same slot as a STORED ratio, and stored
ratios are already effective -- `derive_home_office_ratios_from_censo` multiplies the
raw proportion by the statutory factor before saving. The default therefore asserted an
EFFECTIVE thirty per cent, reachable only at a raw afectacion of 1.00.

**Direction of error: OVER-deduction, so under-declared tax.** A 15 m2 room in a 90 m2
flat is a 16.7 per cent proportion, so the lawful figure is about 5 per cent of the
utility bill against the 30 per cent that shipped -- roughly six times over, silently,
on a return the taxpayer signs. This is the first finding in this campaign pointing
that way; the previous four all cost the taxpayer money rather than exposing them.

Fixed in Step P05.S23 by removing the fabricated factor, which is the ruling this
codebase had already made once: the same stray `default_ratio` was dropped from the
HOME_OFFICE_OWNERSHIP siblings in `2026-08-05-ledger-invoice-decomposition` P06.S61 as
"not a legally established default, just an arbitrary guess". The suministros family
was left behind by that pass, where the guess was harder to see because 0.30 is also
the statutory multiplier's own value.

### CONFIRMED, NOT FIXED -- the escape clause has no channel

The same sentence ends "salvo que se pruebe un porcentaje superior o inferior". A
taxpayer who can prove a different percentage is entitled to it.
`load_usage_ratios_with_censo_guard` compares a persisted home-office ratio against the
censo-derived one by EXACT equality and raises `CensoRatioMismatchError` on any
difference, and refuses outright when no censo is bound. There is no representation for
a proven percentage, so the second half of the provision cannot be exercised at all.

Direction of error: over-payment for a taxpayer who can prove a HIGHER percentage, who
is forced down to 30 per cent of area.

Not fixed here, and deliberately so. The guard is doing a legitimate job -- it exists to
stop a stale stored ratio silently disagreeing with the bound censo, per the
modelo-036-037 foundation contract amendment. What it lacks is the ability to tell
"stale" from "deliberately different because proven", and giving it that means adding a
proven-percentage field with its evidence and deciding how the censo guard treats it.
That is a schema and contract change against an existing amendment, so it needs a
decision rather than a tick. **Blocked on an operator/ADR decision, recorded rather
than smoothed over.**

### CLEARED -- gastos de dificil justificacion carries both its clauses

LIRPF art. 30.2.4a caps the difficult-to-justify provision at 5 per cent of net income
AND at 2.000 euros annually. Both ship as separate registry parameters
(`...gastos-dificil-justificacion-rate` value 5 percent,
`...-cap` value 2000 EUR) and the formula for casilla 0222 is
`min(max(...), cap)`, so both clauses are applied. No defect.

### SCOPED OUT -- the art. 28.3 three-year clawback is unmodelled, not half-modelled

Art. 28.3 provides that afectacion or desafectacion is not an alteracion patrimonial
while the asset stays in the taxpayer's patrimony, and that no afectacion is deemed to
have occurred if the asset is sold within three years. Nothing in the tree implements
either clause, because asset disposal of elementos afectos is not modelled at all. That
is an absent feature and a scope question, not a provision the code half-implements, so
it is recorded here without a CONFIRMED verdict rather than being counted as a defect
of this class.

### What round two adds to the class

The restated class held: three of the first four defects were lost qualifiers. This
round's confirmed defect is the same shape seen from the other side -- not a qualifier
dropped from a value, but a MISSING factor supplied with a plausible number. The tell
was that the invented factor and the real one carried the same digits, so the data read
as consistent. A product of two factors where one is a taxpayer measurement is worth
checking wherever it appears: the code cannot know the second factor, so any value
sitting in its place was authored, and an authored figure in that slot is a defect
whatever its magnitude.

## The censo-to-deduction chain, and what carrying it revealed

The operator asked whether the 036-declared dwelling area is actually connected to the
deduction. It was not. Every link existed and one join was missing:
`bound_raw_afectacion_ratio` computed office_m2/total_m2 from the profile facts,
`derive_home_office_ratios_from_censo` applied the art. 30.2.5.b thirty per cent, the
censo guard compared a stored ratio against the derived one, and a mismatch blocked
calculation. But nothing DERIVED and used the ratio: the operator had to retype it
through `ledger ratios set`, and the guard returns early when no override is persisted,
so a filer who declared their m2 and never retyped them deducted nothing on utilities,
with no preflight reason for that case.

**This is the shape the previous finding left behind, and it is worth stating plainly.**
Step P05.S23 removed the fabricated `default_ratio`, which was right -- it invented the
taxpayer's second factor. But it moved the failure from over-deduction (a flat thirty
per cent) to under-deduction (zero), when the correct figure was computable from data
already on the profile. Under this project's own "watch the unwatched direction"
mandate, a silent zero is the over-payment direction and nothing was watching it.
Removing an invented number is only half a fix when a real one is derivable.

Closed in Step P05.S24. Deriving is not new policy: because the guard demands the
stored ratio equal the derived one exactly, the stored value carried no information the
censo did not already have, so filling an absent one produces the number the guard
would have insisted on. The escape clause finding above is the reason that equality is
itself contestable, and the two interlock: today a proven percentage is unrepresentable,
which is what makes the stored value redundant.

### The duplication the same question exposed

Asked to integrate rather than invent, a semantic sweep found the home-office family
grouping declared FOUR times across `domain/usage_ratios`, `adapters/persistence`,
`application/ledger/ratios` and `application/ledger/preflight` -- two as tuples, two as
frozensets -- with two of those modules also each carrying their own function unioning
the pair's members. A fifth copy was written and removed inside the same Step, which is
the strongest evidence that the grouping was easy to re-derive locally and nothing
objected.

That is not cosmetic here. Art. 30.2.5.b applies the statutory thirty per cent to the
SUMINISTROS family only, while the OWNERSHIP costs deduct at the raw proportion under
art. 29.2. A copy that drifts by one member moves a category across that line and
changes what a taxpayer deducts. The grouping now lives once beside the membership
table it derives from, and a gate reds on any module referencing both members in code.

The gate's first version read raw source text and flagged two docstrings that
legitimately explain the difference between the families. Reading the AST instead
separates prose about a rule from a copy of it -- a distinction worth keeping in any
duplication gate, because the text-level version would have taught its readers to
delete accurate documentation to go green.
