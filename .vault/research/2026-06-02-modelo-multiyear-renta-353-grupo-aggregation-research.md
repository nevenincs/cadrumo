---
tags:
  - '#research'
  - '#modelo-multiyear-renta-353-grupo-aggregation'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-modelo-multiyear-renta-adr]]"
---



# `modelo-multiyear-renta-353-grupo-aggregation` research: `353 grupo-entidades monthly aggregation mechanism`

This research grounds the cross-modelo mechanism that lets Modelo 353 (the IVA
*grupo de entidades* aggregated monthly autoliquidación, filed by the entidad
dominante) pull and sum the result casillas of the individual Modelo 322 filings
(one per group member, also monthly). It exists because the foundational
authorization-gate ADR mandates a ≥2-renta end-to-end enrollment test for every
modelo, and the 353/322 pair cannot be authorized until the aggregation that
defines their relationship actually runs. The pair is the **monthly,
cross-member** analogue of the already-shipped 390←303 reconciliation (which is
**annual, cross-period, single-filer**), and unlike every other mechanism in
this campaign it is the ONE design that needs a (small) registry-schema
extension. Every claim below was re-verified against the live registry and the
in-repo legal corpus rather than taken from the coordinator scratch.

## Findings

### F1. The two modelos share an identical result-casilla shape

Verified in `src/aeat/_data/registry/aeat/modelos/322/.../casillas/0001-casillas.toml`
and the matching `353` file. Both revisions (`322` → `2008-y-siguientes`,
`353` → `2008-y-siguientes`) declare the same three computed result casillas with
identical ids and semantic roles:

- `iva.cuota-devengada-total` (`semantic_role = iva_cuota_devengada_total`)
- `iva.cuota-deducible-total` (`semantic_role = iva_cuota_deducible_total`)
- `iva.resultado-regimen-general` (`semantic_role = iva_resultado_regimen_general`)

The only difference is the human label: 322 reads "Total cuota IVA devengada
(repercutido + autorepercutido)" while 353 reads "Total cuota IVA devengada
(agregado del grupo)". Because the source and target casilla ids match exactly,
the aggregation is a same-shape sum — structurally the same move as 390 summing
the four 303 quarters into one annual total.

### F2. 353 has NO cross-member binding today — this is the gap

`src/aeat/_data/registry/aeat/modelos/353/.../bindings/0001-bindings.toml`
declares only `source = "ledger_iva_aggregation"` bindings (repercutido by rate,
soportado interiores, autorepercutido intracomunitaria). It models the entidad
dominante computing its OWN aggregate from its OWN ledger. It has **zero**
`source = "previous_filing"` bindings, so nothing pulls the member 322 results.
The precedent it should clone — `390`'s prev-303 bindings — lives at
`src/aeat/_data/registry/aeat/modelos/390/.../bindings/0001-bindings.toml`
lines ~68-126: `modelo-390-prev-303-cuota-devengada-total` /
`-cuota-deducible-total` / `-resultado-regimen-general`, each
`source = "previous_filing"`, `selector = { source_modelo = "303",
filing_year_delta = 0, source_periods = [...], source_casillas = [...] }`,
`aggregation = { op = "sum" }`.

### F3. The previous_filing selector has NO member/declarant axis

The selector model is `_PreviousModeloSelector` in
`src/aeat/domain/calculations/registry/_bindings.py` (around line 326). Its
config is `ConfigDict(strict=True, frozen=True, extra="forbid")` — so any new
matching axis MUST be added as an explicit declared field; a TOML author cannot
smuggle one in. Its fields are exactly: `source_modelo`, `filing_year_delta`,
`period`, `source_periods`, `source_period_offset_from_target`,
`source_casillas`, `source_output`, `max_year_delta`. There is **no** axis that
selects WHICH filer's observation to read. The resolver
(`resolve_previous_filing_binding_values`) assumes a single-filer store.

### F4. The resolver hard-rejects multiple matching observations

In the same module the resolver matches observations purely on
`observation.modelo == selector.source_modelo and observation.filing_year ==
expected_year and observation.period == required_period`, then enforces
`if len(matches) != 1: raise RegistryValidationError(... expected one observed
filing ... found {len(matches)})`. Two group members filing 322 for the same
month therefore produce two matches and the resolver raises **before** it can
sum them. This `!= 1` guard is the second structural blocker, independent of the
selector gap.

### F5. The observation envelope itself carries no member identity

`RegistryModeloObservation` (`_bindings.py` ~line 123) is also
`strict / frozen / extra="forbid"` and its fields are only `modelo`,
`filing_year`, `period`, `observations` (a tuple of `CasillaObservation`). There
is no NIF / declarant / member field, so even if the resolver were relaxed, two
member 322s for the same modelo+year+period would be **indistinguishable
duplicates**. Cross-member aggregation needs a way to (a) distinguish member
observations and (b) tell the resolver to sum across them. Both the selector
(F3) and either the resolver-or-observation must change together.

### F6. The per-member precedent already exists for 184

`src/aeat/_data/registry/aeat/modelos/184/.../bindings/*.toml` declares
`source = "atribucion_member"` bindings whose selector reads
`{ fact = "row_field", row_field = "member_tax_id", grouping =
"per_atribucion_member", record = "miembro" }`. Crucially, `per_atribucion_member`
is a **free-form selector string**, NOT a `RowSetGroupingKind` enum value:
`RowSetGroupingKind` (in `src/aeat/core/aggregation.py`) only declares
`WITHHOLDING`, `RELATED_PARTY`, `FOREIGN_ASSET`, `ATRIBUCION`, `REFUND`. The
`grouping` axis lives inside the typed `_AtributionSelector` and drives
per-member row expansion via `AtributionMemberObservation` (which DOES carry
`member_tax_id`). This is the exact shape to mirror: a `grouping =
"per_grupo_member"` axis on the previous_filing selector, paired with a
member-keyed observation so the resolver can enumerate-then-sum instead of
demanding exactly one.

### F7. The cross-renta month-boundary carry already works and is tested

`_derive_offset_source_anchor` in `_bindings.py` (~line 487) handles two-digit
numeric monthly periods: for `target_period = "01"` with
`source_period_offset_from_target = -1` it returns `(-1, "12")` — i.e. month 01
of year N pulls month 12 of year N-1. This is exercised by
`test_relation_offset.py::test_monthly_offset_wraps_across_year_boundary`
(asserts `(-1, "12")`) and `test_monthly_offset_resolves_previous_month`. The
group's saldo a compensar carry from mes 12/N to mes 01/N+1 therefore reuses an
already-tested mechanism with **no new code** — the carry belongs on the 353
aggregate, not on any individual member 322.

### F8. Legal grounding — corpus reality vs the scratch

The coordinator scratch cited `ley-37-1992:art-163-sexies` /
`-quinquies` / `-nonies` for the grupo-de-entidades régimen. Those article files
do **not** exist in the in-repo corpus: enumerating
`src/aeat/_data/registry/aeat/legal/iva.toml` shows the only `art-163-*` entries
are the `-octiesdecies` … `-octovicies` (REDEME / régimen-especial) cluster, not
the grupo-de-entidades articles. The refs that DO resolve, and that the 322/353
casillas already cite, are:

- `orden-eha-3434-2007:art-1` — approves Modelo 322 (modelo individual mensual);
  its corpus note names "Grupo de entidades. Modelo individual" and ties it to
  art. 163 quinquies.Uno of the LIVA.
- `orden-eha-3434-2007:art-2` — approves Modelo 353 (modelo agregado mensual),
  presented by the entidad dominante.
- `orden-eha-3434-2007:art-8` — the monthly cadence.
- `ley-37-1992:art-88` (repercusión), `art-92` (deducción), `art-84` (inversión
  del sujeto pasivo), `rd-1624-1992:art-71` (autoliquidaciones) — the standard
  IVA articles already on the result casillas of both modelos.

The ADR MUST cite from this resolvable set. Citing `art-163-sexies` would be a
dangling legal ref that the corpus cannot back.

### F9. Two distinct axes, kept separate

The mechanism has two independent axes that must not be conflated:

- **Cross-MEMBER (same month):** `353[M] = Σ member-322[M]`. This is the PRIMARY
  gap and the only part needing the schema extension (F3-F6).
- **Cross-RENTA (month boundary):** group saldo a compensar at mes 12/N carries
  to mes 01/N+1. This reuses the tested monthly wrap (F7) and needs no new code.

The ≥2-renta enrollment test the foundational gate requires is satisfied by
driving both members across mes 12/N and mes 01/N+1 (two distinct renta years),
asserting the cross-member sum each month AND the cross-renta carry across the
boundary. No public AEAT grupo workbook exists, so the oracle is
structure / wiring / provenance, not a numeric figure (consistent with the
no-tautological-calculation-tests discipline).

### Open decision carried to the ADR

The load-bearing decision is HOW to express cross-member selection given F3-F5:
either (a) extend the previous_filing selector with a `grouping =
"per_grupo_member"` axis plus a member-keyed observation (mirroring 184's
per_atribucion_member), relaxing the `!= 1` guard to enumerate-then-sum when the
grouping axis is present; or (b) model the whole group as a single observation
bucket whose `observations` already carry every member, keyed internally by NIF,
so the resolver sums within one bucket and the `!= 1` guard still holds. The ADR
weighs both and recommends (a).

