---
tags:
  - '#adr'
  - '#tax-domain-taxonomy-extension'
date: '2026-07-04'
modified: '2026-07-04'
related:
  - '[[2026-06-30-obligation-coverage-completeness-adr]]'
  - '[[2026-06-30-obligation-coverage-completeness-research]]'
  - '[[2026-07-01-obligation-coverage-completeness-audit]]'
  - '[[2026-06-10-modelo-enum-hardening-adr]]'
---

# `tax-domain-taxonomy-extension` adr: `per-tax Spanish-stem TaxDomain members for the new-tax modelos` | (**status:** `accepted`)

## Problem Statement

The `UNMODELED_OBLIGATIONS` burndown (driven by the obligation-coverage
completeness mandate: surface or advise, never silently drop a filing
obligation) promoted the last recognized-but-unmodeled modelos into the
registry: M490, M604, M763 (commit `7f9668cbaf`) and M592, M576, M121, M122
(commit `119898311a`, residual UNMODELED now zero). Five of those modelos
levy taxes with no existing `TaxDomain` member: the Impuesto sobre
Determinados Servicios Digitales (M490), the Impuesto sobre las
Transacciones Financieras (M604), the Impuesto sobre actividades de juego
(M763), the Impuesto especial sobre envases de plástico no reutilizables
(M592), and the IEDMT medios-de-transporte matriculation tax (M576). Since
`ModeloDefinition.tax_domain` hydrates the closed `TaxDomain` StrEnum at
registry load (`_schema.py`, `BeforeValidator`), their manifests could not
compile without extending the enum. The coordinator extended
`src/aeat/core/_tax_domain.py` with five per-tax members (`idsd`, `itf`,
`juego`, `plastico`, `iedmt`) under time pressure, in the same commits as
the registry promotion. This ADR ratifies that taxonomy decision after the
fact, records the alternatives it displaced, and fixes the extension
convention for future new-tax modelos.

## Considerations

- `TaxDomain` is a registry classification and discovery-filter axis, not a
  calculation-class switch: consumers are the loader hydration
  (`_schema.py`), the query-service domain filter (`_queries.py`), the
  discovery service (`_registry_discovery.py`), and the CLI discovery verb
  (`_modelo_discovery_cli.py`), where the Typer option is typed on the enum
  so click renders the accepted-value choice set
  (`aeat-architecture-boundaries`). No consumer performs an exhaustive
  match; all filter by equality, so adding members is strictly additive and
  triggers no consumer-reconciliation debt (the
  `retired-enum-members-need-consumer-reconciliation` rule governs removal,
  not addition).
- `aeat-architecture-boundaries`: closed value sets are StrEnum in `core`;
  the registry TOML stays free-form and the loader hydrates the typed enum
  at the boundary. Extending the enum (rather than loosening the field to
  `str`) is the only shape consistent with that rule.
- `aeat-spanish-stem-naming`: domain concepts mapping 1:1 to AEAT surfaces
  take Spanish stems. `juego` and `plastico` are Spanish stems; `idsd`,
  `itf`, and `iedmt` are the Spanish-language acronyms AEAT and the BOE use
  for those impuestos, exactly as the pre-existing members `iva`, `irpf`,
  `is`, `irnr`, `iae` are.
- Each of the five is a legally distinct impuesto with its own establishing
  law: IDSD (Ley 4/2020), ITF (Ley 5/2020), juego (Ley 13/2011), plástico
  (Ley 7/2022), IEDMT (Ley 38/1992). Only two of the five (IEDMT, plástico)
  are impuestos especiales in the excise sense; a shared "special taxes"
  bucket would be legally wrong for the other three.
- The same burndown also promoted M121/M122 WITHOUT touching the enum: they
  are IRPF deduction-transfer forms and land under the existing `IRPF`
  member. The extension convention is therefore already two-sided: reuse an
  existing family when the tax belongs to it; add a member only for a
  genuinely new impuesto.

## Considered options

- **Option A (chosen, ratified): one per-tax Spanish-stem member per new
  impuesto.** Five members, each documented with its modelo and full
  Spanish tax name. Keeps the domain filter discriminating (filtering
  `--domain plastico` returns exactly the plastic-packaging tax), matches
  the per-impuesto grain of every pre-existing member, and costs only enum
  lines.
- **Option B: one catch-all bucket (e.g. `especiales` or `otros`).**
  Rejected: legally mislabels IDSD/ITF/juego (not impuestos especiales);
  collapses the discovery filter to a junk drawer that discriminates
  nothing; and any later split back into per-tax members would be a member
  retirement with full consumer reconciliation, so the cheap choice now is
  the expensive one later.
- **Option C: classify the five under the existing `INFORMATIVE` member.**
  Rejected: all five modelos are autoliquidaciones with their own
  liquidación, which `INFORMATIVE` is documented to exclude ("no own
  liquidación"); the classification would be false on its face.
- **Option D: widen `tax_domain` to a free string for rare taxes.**
  Rejected outright by `aeat-architecture-boundaries` (closed sets are core
  enums; the loader rejects unknown values at registry-load rather than at
  a downstream branch); this would re-open the typo surface the enum exists
  to close.

## Constraints

- Member VALUES are load-bearing stored tokens: the five registry manifests
  (`modelos/{490,604,763,592,576}/manifest.toml`) already carry
  `tax_domain = "idsd" | "itf" | "juego" | "plastico" | "iedmt"`. Renaming a
  member value now would be a stored-token rename, barred by the
  behaviour-preserving-lift discipline; any future rename runs through
  `retired-enum-members-need-consumer-reconciliation`.
- The enum remains a registry taxonomy, not an applicability verdict or a
  calculation-class switch (the `_tax_domain.py` module contract). Nothing
  in this extension licenses branching calculation logic on `TaxDomain`.
- Ratification only: the code shipped in commits `7f9668cbaf` and
  `119898311a`; this ADR changes no code. If review rejects the naming, the
  correction is a follow-up campaign with consumer reconciliation, not an
  edit of this record.

## Implementation

Already landed. `TaxDomain` (`src/aeat/core/_tax_domain.py`) carries the
five new members with docstrings naming the modelo and the full Spanish tax
name; the five modelo manifests declare the matching stored tokens; loader
hydration validates them at registry load; the discovery CLI's `--domain`
choice set picked the new members up automatically from the enum typing.
Future new-tax promotions follow the two-sided convention recorded here:
hydrate into an existing member when the impuesto already has one (the
M121/M122 precedent), otherwise add one per-tax Spanish-stem member
(official AEAT/BOE acronym where the acronym is the surface name) in the
same commit as the first registry manifest that stores the token.

## Rationale

Per-tax stems are the only option that is simultaneously legally accurate
(each member names a real impuesto and only that impuesto), consistent with
the existing member grain (`iva`, `is`, `irpf`, `irnr`, `iae`, `patrimonio`
are all per-tax), compliant with the closed-set and Spanish-stem rules, and
cheap in both directions (addition is additive; nothing ever needs to be
split apart later). The catch-all alternatives optimize for fewer enum
lines at the cost of a false classification and a future retirement
campaign. The under-time-pressure choice happens to be the choice this
analysis reaches deliberately, which is why this record ratifies rather
than amends it.

## Consequences

- The registry taxonomy now covers every modeled obligation;
  `UNMODELED_OBLIGATIONS` is empty and new-tax modelos are discoverable and
  filterable by their own domain on the CLI discovery surface.
- The enum grows with the Spanish tax system (roughly one member per new
  impuesto per legislature) — accepted; members are cheap and the grain is
  stable.
- Five more stored tokens are frozen: the manifests and the enum values are
  coupled, and any rename is a reconciliation campaign.
- The two-sided extension convention (reuse family vs add per-tax member)
  is now written down, so the next promotion under time pressure has a rule
  to follow instead of a judgment call to make.
- The five new domains carry only skeletal registry content (casillas,
  deadline windows, legal grounding — no calc engines); a taxonomy member
  existing must not be read as calculation support existing. The domain
  classifies; the revision contents decide capability.
