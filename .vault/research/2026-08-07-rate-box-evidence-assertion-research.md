---
tags:
  - '#research'
  - '#rate-box-evidence-assertion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a2b57162e64205c6594e0f2da465be6c06f7ac728107441fbe95f2f9c6640dc7'
related: []
---

# `rate-box-evidence-assertion` research: `what a rate-keyed official box may assert when the evidence underdetermines it`

A Modelo 390 casilla that is exported to a rate-specific AEAT box currently
merges several rates into one box, so a filed artefact declares a false rate
breakdown. The obvious repair — narrowing the binding to the box's rate —
silently deletes money from the return, because the rate discriminator is
optional on the underlying ledger row. This document establishes the measured
picture: how the merge reaches an official box, why the narrowing repair
under-declares, what the existing code already decided about the underdetermined
case, and which option space remains. It records no decision.

The question generalises past Modelo 390. Every rate-keyed box on every modelo
faces it, including the four unmodelled régimen blocks of this same form.

## Findings

### The merge reaches an official AEAT box through the export layer, not through a casilla number

Modelo 390's casillas were believed to carry no official-box identity, which
would have made the merge a harmless internal aggregation. That is false in two
independent ways.

Five casillas already carry real box numbers in
`src/cadrumo/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/casillas/`:
`522` (regularización prorrata), `63` (regularización bienes de inversión), `97`
and `662` (compensación), and `79` (régimen simplificado). Three more carry a
`form_number`: `47` (cuota devengada total), `64` (cuota deducible total) and
`65` (resultado régimen general). The numeric surface is partial, not absent.

More decisively, the semantic tier casillas reach official boxes by **export
offset** rather than by casilla number. The export record `modelo-390-page-02`
writes `iva.anual.repercutido.super-reducido` at offset 98,
`iva.anual.repercutido.reducido` at offset 200 and
`iva.anual.repercutido.general` at offset 234. The bundled AEAT record design
`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/files/16-390-ejercicio-2024-actualizado-18-12-24-544-kb-xlsx.xlsx.extracted.md`
labels those positions, in the Reg. ordinario rows, `Tipo 4% - Cuota [02]`,
`Tipo 10% - Cuota [04]` and `Tipo 21% - Cuota [06]`.

The offset match alone would be ambiguous and would have looked conclusive:
every position in that design appears twice, once under Reg. ordinario and once
under Recargo de equivalencia, whose twins are `[36]`, `[600]` and `[602]`. The
recargo values are written by a separate record, `modelo-390-page-02b`, at the
same offsets 98/200/234. The records are distinguished by `record_type`
(`page_02` versus `page_02b`), so the segment — not the offset — resolves which
box a value lands in. The mapping above holds for the ordinario segment.

### The tier merge is reproducible and mis-allocates across boxes

On 2024-11-15 the rate lookup in `src/cadrumo/domain/iva/_lookup.py` returns
`REDUCED` for both `0.10` and `0.075`, and `SUPER_REDUCED` for both `0.04` and
`0.02` — the RDL 4/2024 temporary food rates share their tier with the ordinary
rate. Driving a 10 % sale (cuota 10.00) and a 7,5 % sale (cuota 7.50) through
the real `ledger_iva_aggregation` resolver against the committed revision yields
`modelo-390-iva-repercutido-reducido-cuota = 17.50`, which the export writes to
box `[04]` while box `[670]` (7,5 % cuota) stays empty.

The total cuota devengada is correct, so the amount payable is correct and the
Modelo 390 to Modelo 303 reconciliation holds. The error is confined to the
breakdown: `[04]` overstates by 7.50 and `[670]` understates by the same. AEAT
reconciles the rate boxes of this return, and a human files the artefact
outside the application, so the false breakdown reaches the filing surface.

### Narrowing the binding deletes rows whose rate was never recorded

The selector carries an `applied_rates` axis
(`src/cadrumo/domain/calculations/registry/_ledger_bindings.py:488`) and it
works: narrowing `modelo-390-iva-repercutido-reducido-cuota` to
`applied_rates=[0.10]` returns 10.00 instead of 17.50.

It also deletes money. `IvaLedgerObservation.applied_rate` is `Decimal | None`
(`_ledger_bindings.py:395`), populated directly from the transaction as
`applied_rate=transaction.iva_rate`
(`src/cadrumo/application/aggregation/_iva_ledger.py:1336`), and
`RawTransaction.iva_rate` is itself `Decimal | None`
(`src/cadrumo/domain/transactions/_models.py:803`). The match at
`_ledger_bindings.py:725` tests `observation.applied_rate not in
set(selector.applied_rates)`, and `None` is never a member, so a narrowed
binding drops the row.

Measured on the committed revision with two `DOMESTIC_REDUCED` repercutido rows
of cuota 10.00 each, one carrying `applied_rate=0.10` and one carrying `None`:
the rate-blind binding returns 20.00; narrowed to `[0.10]` it returns 10.00. The
dropped 10.00 does not move to a sibling casilla. It reaches no casilla, so it
also leaves `iva.anual.cuota-devengada-total`.

This converts a wrong breakdown into a wrong total, which is the more dangerous
direction and the one `no-silent-under-declaration` exists to prevent.

### Atomicity does not resolve it, because the conflict is inside one casilla

The natural repair is a single atomic commit adding rate-specific casillas so
the 7,5 % and 2 % money has somewhere to go, while narrowing the existing
bindings. That handles rows whose rate is recorded and does nothing for rows
whose rate is absent, because every new binding is keyed on the same optional
field and none claims them.

The underlying reason is that `iva.anual.repercutido.reducido` serves two roles
at once: it feeds `iva.anual.cuota-devengada-total` through the devengada
formula, and it is exported to box `[04]`. The total role wants a rate-blind
binding that catches every row; the box role wants a rate-specific binding that
admits only 10 %. Narrowing satisfies the box role and breaks the total role.
The conflict is between two roles of a single casilla, so no commit boundary can
separate them.

### The underdetermined case was already decided in code, against admitting it

The drop is not an oversight. The `applied_rates` docstring
(`_ledger_bindings.py:488-503`) states that an observation whose `applied_rate`
is `None` matches no rate-specific binding, and that this is deliberate because
admitting it "would put an unmeasured line in a box that asserts a specific
rate, and the annual return is where that assertion is read". The same docstring
records that `applied_rates = None` "is the shape every quarterly binding uses".

Read together, those two sentences describe an intended architecture in which
rate-blind bindings serve totals and rate-specific bindings serve per-rate
boxes, as complements rather than substitutes. The defect is that Modelo 390's
tier casillas were never split along that line.

### The Modelo 390 to Modelo 303 reconciliation detects the narrowing defect

`modelo-390-cuota-devengada-total-equals-reconciliacion-303` is a
`BLOCKING_RULE` comparing the annual total against the sum of the four filed
quarters. The quarterly bindings are rate-blind and therefore retain
rate-unrecorded rows, so a narrowed annual would fall short of the summed
quarters and the rule would fire as a shortfall rather than pass silently.

The instrument was designed to catch annual-versus-quarterly drift, not
optional-discriminator loss, so its coverage here is incidental. It is
nonetheless a real net, and it means the narrowing repair would have blocked the
resumen anual of any taxpayer holding a rate-unrecorded row.

### The option space

Three shapes resolve the underdetermined row, with materially different costs.

Admitting `None` into the tier's ordinary-rate binding is the cheapest change
and requires no new casillas. It writes into an official box an assertion the
operator never made, since the evidence records that a cuota exists but not the
rate it was charged at. The existing docstring already rejects this shape on
that ground, so adopting it would reverse a recorded decision rather than fill a
gap. It is also undetectable downstream, because the box appears correctly
populated.

Splitting the roles — rate-specific casillas carrying `export_refs` for the
boxes, alongside a rate-blind casilla without `export_refs` feeding the total —
keeps every row in the total, populates each box only from evidence that
determines it, and matches the architecture the docstring describes. Its
consequence is that the rate boxes can sum to less than the declared total
whenever rate-unrecorded rows exist, which raises a second question this
research does not settle: what a return may assert when its parts underdetermine
its whole.

Making `iva_rate` mandatory wherever a cuota exists removes the underdetermined
case at source. It is a data-model change over existing ledger rows and carries
a backfill-or-refuse question, so it is separable from the first two and does
not resolve rows already recorded.

### What was not investigated

The registry rate catalogue resolves only 2024: `lookup_rate` raises for
`GENERAL`, `REDUCED` and `SUPER_REDUCED` on 2011-06-01, 2013-06-01 and
2023-06-01, and `rate_kinds_for_declared_rate` returns no tier for `0.18`,
`0.08`, `0.05` or `0.00` on those dates, while the revision declares
`2010-y-siguientes`. Whether that is deliberate scoping or a gap was not
determined and is tracked separately.

The régimen simplificado, deducciones-diferenciadas and prorratas blocks were
not examined. The four unmodelled régimen blocks — intragrupo, criterio de caja,
bienes usados, agencias de viajes — each carry their own rate breakdown and face
the same question, but were not measured.

Whether rate-unrecorded rows are common in practice was not measured; the
argument here rests on their being representable, not on their frequency.

## Sources

- `src/cadrumo/domain/calculations/registry/_ledger_bindings.py:395`
- `src/cadrumo/domain/calculations/registry/_ledger_bindings.py:488-503`
- `src/cadrumo/domain/calculations/registry/_ledger_bindings.py:725`
- `src/cadrumo/application/aggregation/_iva_ledger.py:1336`
- `src/cadrumo/domain/transactions/_models.py:803`
- `src/cadrumo/domain/iva/_lookup.py:119`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/export_layouts/0001-export_layouts.toml`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/casillas/civa.anual.repercutido.general__civa.anual.resultado-regimen-general.toml`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/files/16-390-ejercicio-2024-actualizado-18-12-24-544-kb-xlsx.xlsx.extracted.md`
