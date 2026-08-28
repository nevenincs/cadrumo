---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:b53ce8deef0e66cafa087a60d3d43f333f9338f5cc7a7e268d77ea3b45d14a5e'
related: []
---

# `tui-architecture` audit: `M210 IRNR: the art 25.1.a EU/EEA reduced rate is unreachable for canones and inmobiliaria`

## Finding

The TRLIRNR art. 25.1.a reduced rate of 19 % for EU/EEA residents is unreachable
for a filer who declares `canones` or `inmobiliaria`, and reachable for a filer
declaring general rendimientos only by discarding the income category. The
domestic baseline is charged at 24 % instead. The error direction is
**over-payment**, and nothing in the engine watches it.

### The provision has two axes; the registry key has one

The bundled consolidated text at
`src/cadrumo/_data/corpus/normatives/html/trlirnr-rdleg-5-2004.html` states
art. 25.1.a verbatim:

> a) Con caracter general, el 24 por ciento. No obstante, el tipo de gravamen
> sera el 19 por ciento cuando se trate de contribuyentes residentes en otro
> Estado miembro de la Union Europea o del Espacio Economico Europeo con el que
> exista un efectivo intercambio de informacion tributaria.

The 19 % is a proviso *to letter a)*. Its condition is the contributor's
**residence**, not the income type, so it reaches every income letter a) taxes —
general rendimientos, and (per the registry's own reasoning) canones and
inmobiliaria, neither of which has a specific letter in the consolidated art. 25.1.

The registry collapses both axes into one lookup key. In
`src/cadrumo/_data/registry/aeat/modelos/210/revisions/2025/parameters/0001-m210-tipo-gravamen-2025.toml`
(and byte-identically in `2026-y-siguientes/`), residence appears as a *value* of
the income-type table:

| key | value |
|---|---|
| `general` | 0.24 |
| `ue_residente` | 0.19 |
| `canones` | 0.24 |
| `inmobiliaria` | 0.24 |

The file states the consequence in its own comment, for `canones`:

> La reduccion al 19% para residentes UE/EEE del art 25.1.a se alcanza por el
> concepto `ue_residente`

That is the defect, written down as the design: the reduction is reachable only
by electing a *different* value of the same enum, which erases the income
classification the box exists to record. A filer cannot be both `canones` and
`ue_residente`.

### The rate resolver never consults residence

`src/cadrumo/domain/calculations/registry/_formula_runtime_irnr.py:92`
(`evaluate_irnr_resolve_tipo_gravamen`) resolves the domestic baseline as:

```python
baseline_rate = _resolve_keyed_bracket(baseline_param, key=tipo_renta, filing_year=ctx.filing_year)
country = ctx.enum_binding_values.get(args.country_binding) or ""
override = _resolve_convenio_override(ctx, country=country, tipo_renta=tipo_renta)
```

`country` enters only through `_resolve_convenio_override` — the bilateral treaty
(CDI) mechanism, which is a different rule from the domestic art. 25.1.a
proviso. The domestic baseline is keyed on `tipo_renta` alone.

A treaty does not repair this. The `ceiling` override computes
`min(domestic, treaty)`; with the domestic side pinned at 0.24 rather than 0.19,
an EU/EEA resident whose treaty rate sits between the two (or who has no matching
override row) is charged the higher figure.

The residence signal is not missing from the engine. The same module already
reads it for a different purpose at
`_formula_runtime_irnr.py:472`:

```python
def _m210_allows_art_24_6_expenses(*, tipo_renta: str, country_code: str) -> bool:
    return tipo_renta == "ue_residente" or country_code in UE_EEA_COUNTRY_CODES
```

So the art. 24.6 **expense** path honours a country code independently of
`tipo_renta`, while the art. 25.1.a **rate** path does not.

### The guard that exists watches only the other direction

`src/cadrumo/domain/calculations/registry/schema_verification.py:626` documents
the `casilla_equals_implies_profile_flag` operator, authored for this very axis:

> Authored for the M210 IRNR `tipo_renta="ue_residente"` reduced-rate election
> (TRLIRNR Art 25.1.a): the categorical rate choice was not cross-checked against
> the declared `country_of_fiscal_residence`, so a non-EU/EEA filer could
> self-declare the reduced 19% rate reserved for EU/EEE residents.

That is the under-declaration direction — a filer claiming 19 % without
entitlement. The symmetric case, an EU/EEA resident charged 24 % on `canones` or
`inmobiliaria` when art. 25.1.a entitles them to 19 %, has no predicate, no
advisory and no finding. `ue_eee_status` is already a derived `TaxpayerProfile`
property and is already enrolled in `KNOWN_PROFILE_FLAG_ADVISORY_FIELDS`
(`schema_verification.py:560`), so the signal needed to detect the over-payment is
present and consumed — on one side only.

This is the structural tell named in `no-silent-under-declaration`: a restrictive
provision (the 24 % general rate) used as a default, producing valid output, no
refusal and no signal, in the direction nothing watches.

## Scope

Both live M210 revisions (`2025`, `2026-y-siguientes`); the two revisions'
parameter files are byte-identical modulo the revision token, which is correct —
art. 25 is year-stable — so the finding applies equally to both.

Not affected: `pension` (art. 25.1.b progressive tariff, resolved through
`m210-pension-tarifa-2025`), `ganancia_patrimonial`, `interest` and `dividend`
(art. 25.1.f, 19 % unconditionally for every non-resident, correctly modelled and
documented as such in the parameter file).

## Remediation — owner's decision, not taken here

The reduction is a second axis, so the fix is a schema question rather than a
value correction, and it is not adjudicated in this audit. The two shapes:

- **Split the axes.** Resolve the domestic baseline from
  `(tipo_renta, ue_eee_status)` rather than `tipo_renta` alone, so letter a)'s
  proviso applies to every income it governs. This is the faithful model of the
  provision and it retires the `ue_residente` enum value, whose only job today is
  to smuggle residence through the income key. It touches
  `evaluate_irnr_resolve_tipo_gravamen`, the keyed-bracket parameter shape, and
  the `ue_residente` verification predicate.
- **Watch the direction.** Leave the rate model and add an ADVISORY predicate
  firing when `tipo_renta` is a letter-a) category, `ue_eee_status` is true, and
  the resolved rate is 0.24 — the mirror of the existing
  `casilla_equals_implies_profile_flag`. Cheaper, and it makes the over-payment
  visible to the operator rather than silent, but it leaves the engine computing
  a figure the operator must then correct outside the application.

Note that art. 25.1.a's condition is narrower than EU/EEA membership alone: it
also requires "un efectivo intercambio de informacion tributaria". Any fix must
honour that qualifier rather than treating every EEA code as eligible;
`UE_EEA_COUNTRY_CODES` should be checked against it before being reused for the
rate axis.

No production code, registry data or test was changed by this audit.
