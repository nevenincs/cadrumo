---
tags:
  - '#adr'
  - '#unreachable-capability'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:4e2921cac434f436ed9a97f7757398eb4628013ff97e87b387fd2adf3ccbd921'
related:
  - "[[2026-09-02-unreachable-capability-fincas-unblock-research]]"
  - "[[2026-09-02-unreachable-capability-disconnected-capability-inventory-reference]]"
---

# `unreachable-capability` adr: `per-property titularidad and usufructo attribution for the rental engine` | (**status:** `accepted`)

## Problem Statement

The rental engine computes whole-property figures and hands them on as if the
contribuyente owned the whole property outright. `Finca` carries catastro
values, acquisition costs, dates, use type and the stressed-area flag, and
nothing about who holds title or in what proportion. Every gross rent, every
art. 23.1 gasto, every art. 23.1.f amortización and every art. 85 imputación it
produces is therefore attributed at 100 per cent, silently, including for the
two commonest arrangements in Spanish residential letting: a jointly held flat
and a property whose usufructo has been split from its bare title.

That is a silent over-declaration for a cotitular and, for a nudo propietario, a
declaration of income the taxpayer must not declare at all. The gap was
identified as a concrete modelling gap rather than an open adjudication in
`2026-09-02-unreachable-capability-fincas-unblock-research`, which located the
governing manual sections and the two casillas the declaration already
specifies. A decision is needed now because the fields change a shipped domain
record and its persistence row, and because leaving the engine to attribute the
whole property is exactly the failure `no-silent-under-declaration` forbids.

## Considerations

- The individualización rule is statutory, not presentational: Art. 11.3 Ley
  IRPF, restated in the bundled Manual práctico de Renta 2025, Parte 1,
  Capítulo 4, "Individualización de los rendimientos del capital inmobiliario"
  (págs. 292-293), and again for the art. 85 regime in Capítulo 10,
  "Individualización de las rentas inmobiliarias" (pág. 805).
- The declaration already names the facts. Capítulo 4, "Declaración bienes
  inmuebles — Datos particulares de cada inmueble" (pág. 295) carries the
  titular in casilla [0062], the porcentaje de propiedad in casilla [0063] and
  the porcentaje de usufructo in casilla [0064], the percentages "expresad[o]s
  en números enteros con dos decimales". They are per-property facts, declared
  once per inmueble per ejercicio, not per contract.
- The two regimes are not symmetric, and this is the crux. Where a usufructo
  exists, "el rendimiento íntegro debe declararlo el usufructuario y no el nudo
  propietario" (Capítulo 4, pág. 292); the art. 85 renta is imputed to the
  titular del derecho "en la misma cuantía que la que correspondería al
  propietario, sin que este último deba incluir cantidad alguna en su
  declaración" (Capítulo 10, pág. 805). Both regimes follow the derecho de
  disfrute. A nudo propietario declares neither, however large casilla [0063].
- Two percentages cannot express that on their own. A pleno propietario and a
  nudo propietario file identical casillas — a positive [0063] and an empty
  [0064] — and declare opposite amounts. The discriminating fact is which right
  is held, and it is not derivable from the numbers.
- Casilla [0062] is a closed role vocabulary within the unidad familiar
  ("Común", "Primer declarante", "Cónyuge", "Hijo 1º"), not a name or a NIF, so
  carrying it introduces no taxpayer identity into the register.
- One combination the manual permits is beyond the register's reach: pleno
  dominio over part of a property and usufructo over the rest. Capítulo 4,
  "Gastos deducibles" (pág. 281) states the amortización "se calculará de forma
  diferente" for each part, the usufructo part amortising over the cost and
  duration of the usufruct instead of at the art. 23.1.f rate. The register
  records neither that cost nor that duration.
- The `rental_fincas` table and its four siblings ship empty. They are created
  by the profile schema on every database, and nothing writes them, because the
  rental capability has no operator entry point.

## Considered options

- **Two percentages only, no regime.** Add casillas [0063] and [0064] and
  attribute by their sum or by whichever is non-zero. Rejected: it cannot tell a
  pleno propietario from a nudo propietario, which is the single most
  consequential distinction in the section, and it would attribute a nudo
  propietario the whole rental income.
- **A single attribution fraction.** Store one derived share and drop the
  casilla structure. Rejected: it discards the declaration's own shape, cannot
  be filled from the manual's fields without an undocumented derivation, and
  leaves nothing to render back into casillas [0063] and [0064].
- **Optional fields defaulting to full ownership.** Rejected outright: it is the
  present defect written down as a default, and it makes an absent fact
  indistinguishable from a declared 100 per cent.
- **A required regime plus the two declared percentages.** Chosen. Described
  under Implementation.
- **Refusing the mixed pleno-dominio-and-usufructo holding versus approximating
  it at the art. 23.1.f rate.** Approximation rejected: it would deduct an
  amortización the manual says is computed another way, on a basis the register
  does not hold, and would reach the taxpayer as a wrong figure rather than a
  visible gap.

## Constraints

- The amortización rule for a usufructo — acquisition cost over duration, or
  3 per cent if vitalicio, capped at the rendimientos íntegros of that derecho —
  needs a usufruct cost and term the register does not model. Until those exist,
  the mixed holding cannot produce a filing-grade figure.
- Attribution is applied to whole-property figures already computed. The
  art. 23.1.a) cap and the art. 23.2 reducción are linear in the underlying
  amounts, so scaling after aggregation matches the manual's own worked
  examples, which compute the property and then apportion. The art. 23.1.f
  cumulative cap is tracked on the whole property and must stay outside the
  scaled figures.
- This decision depends on no in-flight feature. It touches the rental domain
  records, the rental aggregation, the `rental_fincas` mapper row and its
  repository, and nothing else.

## Implementation

`Finca` gains one required, non-defaulted titularidad value object holding a
closed regime, the casilla [0062] titular as a closed role enum with the "Hijo"
ordinal beside it, and the two casilla percentages as `Decimal` values bounded
to the range 0 to 100 and to the two decimals the declaration accepts. The
regime is one of: not declared, pleno dominio, nuda propiedad, usufructo, and
the combined pleno-dominio-and-usufructo holding.

The value object validates its own coherence and refuses rather than
normalising: a percentage carrying a third decimal, a pair summing beyond 100, a
percentage that contradicts its regime, and a titular missing or present against
what the regime requires are all rejected at construction.

Attribution is a single derivation on that record — the porcentaje de propiedad
under pleno dominio, the porcentaje de usufructo under usufructo, and exactly
zero under nuda propiedad. The aggregation computes each finca's whole-property
figures unchanged, then reduces the five outputs and the per-contract
rendimiento and reducción by that share, and records the share it applied on the
per-finca attribution so the whole-property figure stays recoverable for audit.

Two states produce no attribution and are kept distinct from each other and from
a proven zero. A not-declared titularidad refuses because the facts were never
stated; the combined holding refuses because the amortización rule for its
usufructo part is not modelled. Each carries its own reason into the refusal,
which the aggregation raises naming the finca.

The mapper row gains five columns — regime, titular, "Hijo" ordinal, and the two
percentages — with check constraints on the two closed vocabularies. The
percentages are declared values, not money, so they take a narrower numeric
column than the monetary fields. The titular column is not encrypted, and
deliberately: unlike the address, a role within the unidad familiar identifies
nobody.

The `Finca` record schema version moves from 1 to 2. No migration, upgrader or
compatibility default is provided, and none is needed: the five rental tables
are created empty on every profile database and no code path has ever written
one, so there is no stored row for a migration to carry forward. A default would
exist solely to spare rows that do not exist, at the cost of reinstating the
silent full-ownership assumption this record removes.

## Rationale

The regime is load-bearing because the manual's own rule is stated in terms of
which right is held, not in terms of the percentages. Modelling the percentages
alone would reproduce the declaration's surface and lose its meaning, and the
loss falls precisely on the nudo propietario, whose correct figure is zero and
whose naive figure is the whole property.

Making the field required rather than optional is what closes the defect. An
optional field with a full-ownership default is the current behaviour under a
new name. Requiring it forces every construction site to state the facts, and
the explicit not-declared regime gives the honest answer when they are unknown —
a refusal at the filing boundary rather than an assumption, which is what
`no-silent-under-declaration` requires of a missing legally required input.

Refusing the mixed holding rather than approximating it follows the same rule
from the other side. The holding is legally real and the register can record it;
what the register cannot do is compute its amortización, and a figure computed
by the wrong rule is worse than a visible refusal because it reaches the
taxpayer as a filed number.

The attribution is verified against the manual's own arithmetic rather than
against this engine's output: the Capítulo 4 worked example at págs. 291-292 for
a full owner, halved for a cotitular under the pág. 292 rule, and the Capítulo
10 example at pág. 806 for the imputación.

## Consequences

- The rental engine stops producing a silently attributed total. A cotitular and
  a usufructuario now get their own figures, and a nudo propietario gets zero
  for both regimes.
- Every finca construction must state its titularidad. Twelve existing
  construction sites, all in tests and test witnesses, were updated to declare
  sole full ownership, and every prior expectation held unchanged — which is
  itself evidence that attribution at 100 per cent is a no-op.
- Two new refusal paths reach callers as aggregation errors. Any future operator
  surface for the rental register must present them as the distinct conditions
  they are, not as a zero.
- The mixed pleno-dominio-and-usufructo holding is recordable but not
  computable. Closing it needs a usufruct cost and duration on the register and
  the second amortización rule; that is follow-on work this record does not
  authorise.
- **Which blocker this closes.** It closes the ownership modelling gap the
  fincas research identified as the residual grounding question for the
  per-finca Modelo 100 semantics. It does **not** close the persistence blocker:
  the rental aggregates are still not persisted through the canonical
  secure-storage revision boundary, and the rental capability is still
  unreachable from any operator entry point. The source-connectivity census row
  for the fincas annual aggregates stays blocked, and this record does not
  change its disposition.
- The disagreement noted in the fincas research stands unresolved and is not
  adjudicated here: the census row records a grounding blocker while the
  readiness function reports the persistence one. Both remain true, the row
  still records only one, and choosing between them belongs to the owner of the
  closed disposition vocabulary.
