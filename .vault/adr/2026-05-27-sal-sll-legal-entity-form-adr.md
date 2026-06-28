---
tags:
  - '#adr'
  - '#sal-sll-legal-entity-form'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-21-corporate-entity-calculation-adr]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]"
  - "[[2026-04-13-modelo-inventory-adr]]"
  - '[[2026-06-04-sal-sll-legal-entity-form-research]]'
---


# `sal-sll-legal-entity-form` adr: SAL/SLL legal entity form + reserva especial Ley 44/2015 | (**status:** `accepted`)

## D1 — Context

Aitor (round-20) is the sole administrator of a Sociedad Anónima Laboral
(SAL) with a workforce of 12 employee-shareholders. SALs and Sociedades de
Responsabilidad Limitada Laborales (SLLs) are labour companies regulated by
Ley 44/2015 de Empresas Sociales. They are required to maintain a `reserva
especial` (special reserve) under Art. 14 of that law: each financial year,
at least 10% of net profit must be allocated to this reserve until the reserve
reaches 50% of the company's share capital.

Prior to this ADR, the `LegalEntityForm` enum had no `sal` or `sll` members.
The M200 Impuesto sobre Sociedades calculation engine had no formula chain for
the reserva especial dotation. Aitor's entity was forced to use `sa` as a
proxy, which produced incorrect M200 output and gave no advisory on the Art.
14 obligation.

There are approximately 3,700 SALs and SLLs operating in Spain. The reserva
especial is a mandatory annual allocation; incorrectly excluding it from the
M200 filing understates the deductible provision and may overstate taxable
income.

Legal grounding: Ley 44/2015 arts. 1, 2, 13, and 14; Real Decreto 1112/2015
(SAL/SLL registro); IS regulations on reserva especial deductibility.

## D2 — Decision

### D2.1 — Extend `LegalEntityForm` enum with `sal` and `sll`

Add `sal` and `sll` members to the `LegalEntityForm` enum. The existing
members (`sa`, `sl`, `autonomo`, `cb`, `sc`, `coop`, `fundacion`, `asociacion`,
`otros`) remain unchanged.

### D2.2 — Add three `TaxpayerProfile` fields for SAL/SLL data

Add to `TaxpayerProfile`:
- `sal_socios_trabajadores_count: int | None = None` — number of
  employee-shareholders (used for advisory: Ley 44/2015 Art. 1 requires at
  least 51% of share capital held by worker-shareholders for SAL, 100% for
  SLL).
- `sal_reserva_especial_dotada: Decimal | None = None` — cumulative amount
  already in the reserva especial fund (prior years' allocations).
- `sal_capital_social: Decimal | None = None` — registered share capital
  (used to determine when the 50% cap is reached).

### D2.3 — M200 casilla `SAL_RESERVA_DOTACION`

Add an M200 casilla carrying `semantic_role = "is_sal_reserva_especial_dotacion"`
to the registry. This casilla carries the current-year dotation amount
computed by the formula in D2.4.

### D2.4 — Pure helper `_compute_sal_reserva_especial_dotacion`

Add a pure helper function
`_compute_sal_reserva_especial_dotacion(beneficio_neto, reserva_dotada,
capital_social) -> Decimal`:

  `dotacion = min(Decimal("0.10") * beneficio_neto,
                  max(0, Decimal("0.50") * capital_social - reserva_dotada))`

Rounding: `ROUND_HALF_UP` to 2 decimal places. The formula saturates to zero
once the reserve reaches 50% of capital (the cap condition from Ley 44/2015
Art. 14.3).

### D2.5 — M200 bindings for SAL profile fields

Add two M200 bindings to the registry:
- `sal_reserva_especial_dotada` — bound to the profile field.
- `sal_capital_social` — bound to the profile field.

Extend all five existing M200 cuota/tipo dispatch tables to include `sal` and
`sll` keys mapped to the régimen general 25% rate (SALs and SLLs are taxed at
the general IS rate under RDLeg 4/2004).

### D2.6 — CLI flags `--sal-beneficio-neto`, `--sal-reserva-dotada`, `--sal-capital-social`

Add three co-required CLI flags on `work calculate`. An all-or-nothing guard
raises `BadParameter` if any subset is supplied without the others.

## D3 — Alternatives considered

**Alternative A: treat SAL/SLL as `sa` with a separate advisory.** Reuse the
`sa` legal form and add a boolean `es_laboral: bool` flag. Rejected: `sa` and
`sal` are distinct legal forms with distinct regulatory obligations; conflating
them in the enum produces incorrect dispatch for any future rule that
differentiates on legal form (e.g., certain co-operative tax incentives that
extend to SLLs but not SAs).

**Alternative B: derive beneficio neto from the IS calculation output.**
Rather than asking the operator for `beneficio_neto`, derive it from the
M200 base imponible. Rejected for this ADR: the M200 base imponible is the
output of the calculation engine; using it as an input to the reserva formula
creates a circular dependency. The operator-supplied beneficio neto from the
P&L is the correct grounding document per Ley 44/2015 Art. 14.1.

**Alternative C: separate CLI subcommand for SAL/SLL.** A dedicated `work
calculate-sal` surface was considered. Rejected: the CLI surface rule limits
the root to `config` and `app`; the `work calculate` path with typed flags
is the established pattern for entity-form-specific inputs.

## D4 — Trade-offs

- **Cap saturation.** The formula produces zero dotation once the reserve
  equals 50% of capital. This is correct under Ley 44/2015 Art. 14.3 but
  requires the operator to supply an accurate `sal_reserva_especial_dotada`
  balance; an understated balance produces an overstated dotation. An advisory
  is emitted when `sal_reserva_especial_dotada >= 0.50 * sal_capital_social`
  to confirm the cap has been reached.
- **25% régimen general rate for SAL/SLL.** The decision to apply the 25%
  general IS rate is grounded in RDLeg 4/2004 art. 28. SALs may qualify for
  the 15% new-entity rate in their first two profitable years, but this is a
  future feature; the 25% general rate is the conservative default.
- **Approximately 3,700 entities.** The affected population is small in
  absolute terms but the reserva especial is a mandatory obligation; mis-
  computing M200 for a SAL/SLL constitutes a material filing error.

## D5 — Consequences

- `LegalEntityForm` gains `sal` and `sll` members. All five M200 cuota/tipo
  dispatch tables are extended to include both forms at the 25% régimen
  general rate.
- `TaxpayerProfile` gains three optional SAL/SLL-specific fields defaulting
  to `None`.
- The `_compute_sal_reserva_especial_dotacion` pure helper is the canonical
  implementation with oracle tests for year-1 dotation (€12,000), year-2
  partial cap (€8,000), cap-reached (€0), above-cap (€0), and input guard
  cases.
- Ley 44/2015 Art. 1, 2, 13, 14 legal authority entries are added to
  `legal/is.toml`.
- Approximately 3,700 SALs and SLLs in Spain are correctly served by the
  application's M200 calculation path.
