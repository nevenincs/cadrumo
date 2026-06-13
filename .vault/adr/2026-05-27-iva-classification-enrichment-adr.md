---
tags:
  - '#adr'
  - '#iva-classification-enrichment'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-04-13-r1-vat-enumeration-adr]]"
  - "[[2026-04-12-modelo-303-390-adr]]"
  - "[[2026-04-17-modelo-303-formulas-adr]]"
  - "[[2026-04-27-modelo-303-calc-verify-adr]]"
  - "[[2026-04-14-transaction-catalogue-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-adr]]"
  - "[[2026-05-21-sii-digital-iva-ledger-adr]]"
  - '[[2026-06-04-iva-classification-enrichment-research]]'
---


# `iva-classification-enrichment` adr: IVA category + counterparty enrichment on Transaction | (**status:** `accepted`)

## Problem Statement

The IVA ledger aggregation pipeline currently handles only domestic
VAT transactions. The M303 filing requires two additional casilla
clusters:

- Casilla 59 ("Entregas intracomunitarias bienes y servicios"): base
  imponible of EU intra-community supplies and qualifying services, cited
  in Ley 37/1992 arts. 88 and 92.
- Casilla 60 ("Exportaciones y operaciones asimiladas"): base imponible
  of third-country zero-rated exports, cited in Ley 37/1992 art. 21.

Neither casilla has a formula binding in the registry today; both carry
`input_kind = "manual"`. Wiring them to the ledger pipeline requires:

1. A typed IVA category enrichment field on `Transaction` so an operator
   can tag a row as intra-community supply or third-country export.
2. A counterparty EU member-state field on `Transaction` so the
   aggregation engine can verify that intra-community transactions name
   a real EU member state.
3. A deliberate decision about `BusinessClassification` scope to prevent
   the two enumerations from conflating independent semantic axes.
4. A deliberate decision about casilla 62 (criterio de caja) to keep it
   out of the scope of this ADR.

## Considerations

**Semantic-axis separation.** `BusinessClassification` already has a stable
seven-member closed set (`BUSINESS`, `PERSONAL`, `MIXED`,
`NOT_YET_PROCESSED`, `PROCESSED_UNCLASSIFIED`, `SKIPPED_BY_RULE`,
`FAILED_VALIDATION`). It answers "is this row a business transaction?".
`IvaCategory` answers "what VAT treatment applies to this row?". These are
orthogonal axes. Extending `BusinessClassification` with IVA-category
values would conflate the two, make the pipeline gate logic wrong (the gate
already uses `BusinessClassification` as an entry filter), and force every
downstream consumer that reads one axis to absorb the other.

**Existing `IvaCategory` catalogue.** The `IvaCategory` enum in
`src/aeat/domain/iva/_schema.py` already carries the authoritative 17-member
closed set including `INTRA_COMMUNITY_SUPPLY`,
`INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE`,
`INTRA_COMMUNITY_TRIANGULATION`, and `EXPORT_THIRD_COUNTRY_ZERO_RATED` with
legal citations. Adding new members would require BOE grounding.

**R12 vs R10 place-of-supply ruling for services.** Ley 37/1992 art. 69
(transposing Directive 2006/112/EC art. 44) places B2B service supplies at
the customer's territory when the customer is a taxable person established
in another EU member state. This means:
- Goods sold to an EU buyer → `INTRA_COMMUNITY_SUPPLY` (R10 casilla 59).
- B2B services billed to an EU buyer → `DOMESTIC_NOT_SUBJECT` (R12:
  the supply is outside Spain's VAT territory). Casilla 59 DOES include
  qualifying services per Ley 37/1992 art. 25 — those for which the
  fiscal adjustment point is Spain. In practice, the vast majority of
  digital / consultancy services to EU B2B clients fall under R12 and
  land in casilla 61 (other operations not subject), NOT casilla 59.
  The casilla 59 binding for the ledger must therefore accept both
  `INTRA_COMMUNITY_SUPPLY` (goods and qualifying services with Spanish
  fiscal adjustment point) and be explicitly documented to exclude plain
  R12 B2B-service transactions.

**Casilla 62.** Casilla 62 ("Entregas criterio caja devengado art 75 LIVA —
Base imponible") is the criterio de caja (cash-accounting VAT) base for
supplies under Ley 37/1992 arts. 163 quinquies-undecies. It has no
relationship to intra-community supply or third-country export. Grouping it
with casillas 59 and 60 in the same implementation step would introduce
incorrect logic and confusion for operators.

**`EUMemberState` enum.** `src/aeat/domain/iva/_schema.py` already defines
a closed 27-member `EUMemberState` enum (ISO 3166-1 alpha-2, lowercase).
Spain (`es`) is a member of the enum because it is an EU member state;
however, a domestic-to-domestic transaction with `counterparty_eu_member_state
= EUMemberState.ES` is an invalid combination — the aggregation engine
must reject it.

**`_classify_iva_transaction` current behaviour.** Today the function
hard-codes `_RATE_KIND_TO_DOMESTIC_CATEGORY[rate_kind]` as the IVA category
on every observation. When `iva_category` is set on the `Transaction`, the
function must use it directly instead. The domestic lookup remains the
fallback for rows without an explicit category.

## Constraints

- `Transaction` is an immutable pydantic-v2 model with a deterministic
  content-addressed `transaction_id`. The new fields must be `Optional`
  and default to `None` so all existing serialised records remain valid.
- The `Transaction._enforce_derived_transaction_id` model validator re-
  derives `transaction_id` from `raw` only; the new enrichment fields do
  not affect the content-addressed id (they post-date initial import).
- `BusinessClassification` is a closed enum used as a gate in both the
  IVA and RENTA ledger pipelines. Adding members to it is in-scope only
  for pipeline-state semantics, not VAT treatment. Do not add members.
- The registry casillas 59 and 60 carry `input_kind = "manual"` today.
  The S94 implementation replaces this with a `ledger` binding that sums
  `IvaLedgerObservation` rows tagged with the appropriate `IvaCategory`
  values. No TOML structure changes are required until the binding type is
  confirmed by the registry-formula team.
- The criterio de caja implementation (casilla 62) is a separate campaign
  step and must not be started in the same commit as casillas 59/60.

## Decisions

### D1 — Add `iva_category: IvaCategory | None` to `Transaction`

Add `iva_category: IvaCategory | None = None` as an optional enrichment
field on `Transaction`. This field carries the operator's explicit VAT
treatment override. It is independent of `business_classification`.

When `iva_category` is set, `_classify_iva_transaction` uses it as the
observation category directly rather than deriving from `_RATE_KIND_TO_DOMESTIC_CATEGORY`.
The `iva_rate` / `taxable_base` / `iva_amount` pre-gates still apply.
For categories that imply a zero VAT rate (`INTRA_COMMUNITY_SUPPLY`,
`EXPORT_THIRD_COUNTRY_ZERO_RATED`, `DOMESTIC_NOT_SUBJECT`), the engine
must accept `iva_rate = 0` and `iva_amount = 0` without rejecting on the
missing-tax-fact gate.

Serialisation: the field is persisted alongside the other optional
`Transaction` fields, defaulting to `None` on all existing records.
`IvaCategory` is a `StrEnum` so JSON round-trip is the string value.

### D2 — Do NOT extend `BusinessClassification`

`BusinessClassification` remains a seven-member closed enum answering only
the question "did this row originate as a business transaction?". No IVA-
category values are added. The `CLASSIFIED_STATES` frozenset and
`is_classified` helper remain unchanged.

Rationale: adding IVA-category values to `BusinessClassification` would
break every consumer that uses it as an entry-eligibility gate, would
conflate two independent semantic dimensions, and would force a migration
of all persisted records carrying the new members. The correct surface is
`iva_category` on `Transaction` (D1).

### D3 — Casilla 62 is out of scope for W05.P24.S91-S95

Casilla 62 ("Entregas criterio caja devengado art 75 LIVA") covers the
criterio de caja VAT regime under Ley 37/1992 arts. 163 quinquies-undecies.
This regime is structurally independent of intra-community supply and
third-country export. W05.P24.S94 implements casillas 59 and 60 only.
Casilla 62 is tracked as a separate plan step (S281) and must not be
touched in the same commit.

### D4 — R12 vs R10 routing: `DOMESTIC_NOT_SUBJECT` does NOT feed casilla 59

The casilla 59 ledger binding sums `IvaLedgerObservation` rows whose
`category` is `INTRA_COMMUNITY_SUPPLY`. B2B services supplied to EU-
established taxable persons under Ley 37/1992 art. 69 are
`DOMESTIC_NOT_SUBJECT` (R12) and do not flow into casilla 59. The
aggregation engine does not reclassify `DOMESTIC_NOT_SUBJECT` rows as
intra-community.

An operator classifying Marc's IT-services invoice to a German GmbH must
use `DOMESTIC_NOT_SUBJECT` — the supply lands outside Spain's VAT
territory. If the operator believes a qualifying exception applies (e.g.,
art. 25 intermediate services with Spanish adjustment point), they set
`INTRA_COMMUNITY_SUPPLY` explicitly. The CLI `work ledger tag` command
presents both options with their legal citations.

### D5 — Add `counterparty_eu_member_state: EUMemberState | None` to `Transaction`

Add `counterparty_eu_member_state: EUMemberState | None = None` as an
optional enrichment field on `Transaction`. This field is required when
`iva_category` is `INTRA_COMMUNITY_SUPPLY` or
`INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE` or
`INTRA_COMMUNITY_TRIANGULATION`.

Validation rule (enforced in `_classify_iva_transaction`): if
`iva_category` is an intra-community variant and
`counterparty_eu_member_state` is `None`, the engine emits a
`MISSING_COUNTERPARTY_EU_MEMBER_STATE` gate issue rather than producing
an observation. If `counterparty_eu_member_state` is `EUMemberState.ES`
(Spain) and `iva_category` is an intra-community variant, the engine
emits a `DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION` gate issue.

For `EXPORT_THIRD_COUNTRY_ZERO_RATED`, `counterparty_eu_member_state` must
be `None` (non-EU destination); the engine emits
`EU_MEMBER_STATE_ON_EXPORT_TRANSACTION` if it is set.

## Implementation Notes for S91-S95

- **S91** — Add `iva_category: IvaCategory | None = None` and
  `counterparty_eu_member_state: EUMemberState | None = None` to
  `Transaction` in `src/aeat/domain/transactions/_models.py`. Add the two
  new `IvaLedgerAggregationIssueReason` members
  (`MISSING_COUNTERPARTY_EU_MEMBER_STATE`,
  `DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION`,
  `EU_MEMBER_STATE_ON_EXPORT_TRANSACTION`) to
  `src/aeat/application/aggregation/_iva_ledger.py`. Update
  `_classify_iva_transaction` to branch on `iva_category` before the
  `_RATE_KIND_TO_DOMESTIC_CATEGORY` lookup and apply the D5 validation.

- **S92** — Add casilla 59 ledger binding: aggregate all
  `IvaLedgerObservation` rows with `category = INTRA_COMMUNITY_SUPPLY` and
  `flow_direction = REPERCUTIDO` into the casilla 59 base-imponible
  observation. Mirror for casilla 60 (`EXPORT_THIRD_COUNTRY_ZERO_RATED`).

- **S93** — CLI surface: `work ledger tag` must present `iva_category` as an
  editable field alongside `business_classification`. The locale scaffolder
  must add translation keys for the two new `Transaction` fields.

- **S94** — Registry binding: annotate casillas 59 and 60 with a `ledger`
  binding once the registry-formula team confirms the binding type schema.
  Until then leave `input_kind = "manual"` and implement the aggregation
  layer in the application tier.

- **S95** — Persona test (Marc): a full `work → calculate → verify` run
  with one `INTRA_COMMUNITY_SUPPLY` invoice to a German counterparty and
  one `DOMESTIC_NOT_SUBJECT` IT-services invoice to the same counterparty.
  Expected: casilla 59 populated from the goods invoice; casilla 59 empty
  from the services invoice; casilla 61 (or equivalent not-subject bucket)
  populated from the services invoice.

## Consequences

- `Transaction` gains two optional nullable fields. All existing persisted
  records remain valid without migration (both default to `None`).
- `_classify_iva_transaction` gains a branch for explicit `iva_category`
  enrichment, plus three new gate issue reasons. The domestic path remains
  the default when `iva_category` is `None`.
- `BusinessClassification` stays frozen. No downstream consumer needs to
  handle new members.
- Casilla 62 (criterio de caja) is deferred to S281 with a separate ADR
  entry point. The two code paths must not be co-mingled.
- Operators will be required to set `iva_category` explicitly for intra-
  community and export rows; the engine does not auto-classify these from
  `iva_rate` alone. This is consistent with the R12/R10 ambiguity: the
  engine cannot determine place-of-supply without operator intent.
