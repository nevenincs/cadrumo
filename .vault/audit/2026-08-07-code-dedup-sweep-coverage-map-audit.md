---
tags:
  - '#audit'
  - '#code-dedup-sweep'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a70892afdae07321da76a99bde21a1e9c1fc77078c64d915a90643098672f0a3'
related: []
---

# `code-dedup-sweep` audit: `Sweep coverage map: what was swept, what was not, and why fifteen near-neighbours are not gaps`

## Scope

A RAG-led semantic dedup sweep under the standing canonicalisation directive: no
shims, no re-exports, no duplicated functionality, no redeclarations. Concepts
were located by MEANING first, pinned with a targeted grep, and the relation
between candidate sites established by MEASUREMENT rather than inspection.

This note exists because the sweep's most reusable output is not the defects it
found but the judgements it settled. A cleared near-neighbour recorded without
its discriminator is indistinguishable from an unexamined one, so the next sweep
re-derives every judgement from scratch and may answer some of them differently.

### Swept

IVA / aggregation / registry spine; identity and tax-id validation; money
rounding and the decimal grammar; period boundary and pre-activity suppression;
content addressing and digests; casilla routing; Modelo 349 claves; retencion
derivation; mechanical import hygiene including dynamic-import targets; CLI
entrypoints (result emission, single-subject id resolution, diagnostic channels,
direct prints); MCP (transport and native tools); inbound financial parsers
(direction, per-format normalisation, decimal parsers); wizard and flows (answer
validation and coercion, profile-field writes, sequencing and gates, prompt
surface); renta (income measures, business eligibility, gate composition).

### NOT swept

Adapters outbound beyond the AEAT auth tax-id path; persistence and storage
internals beyond content addressing; the borrador, declaracion and censo inbound
families beyond their decimal parsers; core observability; the llm package; the
entire test tree.

## Findings

### renta-measures-cannot-collapse | low | Three measures of income are distinct typed facts, and the model prevents the collapse a future sweep will be tempted to make

`RentaIncomeObservation` in
`src/cadrumo/application/aggregation/_renta_income_ledger.py` carries
`gross_amount`, `taxable_base_amount` and `withheld_amount` as three separate
facts. `gross_amount` is the cash magnitude times the business proportion;
`taxable_base_amount` is `None` when the operator declared no base, rather than
defaulting to gross; a model validator then asserts the `grounding` enum agrees
with whether a base was declared.

Recorded because the pull to canonicalise them is real and this auditor felt it:
they look like one quantity measured three ways. In renta,
same-quantity-by-two-rules is legally required rather than accidental, and base,
rendimiento neto and ingreso integro are not copies of one another. The model is
what prevented the mistake, not the auditor. A future sweep will feel the same
pull and should read the validator before acting.

### absence-is-not-always-a-gap | low | Business proportion missing from the income ledgers is correct, not a hole

`_renta_business_eligibility` exports `relies_on_activity_marker` and
`renta_expense_business_proportion`, consumed by the two expense-side ledgers and
by neither income ledger. That is correct: business PROPORTION asks what fraction
of a cost is business, an expense question with no income counterpart.

Stated explicitly because an auditor counting consumers finds two of five and
files a gap. The discriminator is what the quantity is FOR, not how many callers
it has.

### gate-ordering-divergence-already-recorded | low | The three ledger classifiers compose shared gate primitives in differing order, and that is documented elsewhere

`_iva_ledger`, `_renta_income_ledger` and `_renta_gasto_ledger` all import
`_shared_issue_reasons` for `OUTSIDE_PERIOD`, `UNSUPPORTED_CURRENCY` and
`UNSUPPORTED_DIRECTION`, and all import `is_non_eur_without_conversion` from
`_currency_predicates`. One set of gate primitives composed per regime, not a
duplication finding.

The ORDER each composes them in still differs. That is a behaviour-consistency
finding already recorded in the accepted ledger-latency-budget ADR dated
2026-07-05. The pointer is written here so it survives and so a later sweep does
not re-report it as new.

### near-neighbours-cleared-with-discriminators | low | Fifteen candidate duplications examined and cleared, each with the fact that settled it

Recorded so none is re-derived. Tax-id validation: three DNI-shaped regexes with
differing digit counts are shape PRE-FILTERS over one checksum authority, and the
sole input they disagree on is refused by that authority anyway, so the
divergence is outcome-neutral. Money rounding: `round_to_cents` is canonical, and
the one production cent-quantise bypassing it computes a display percentage never
persisted or filed. Content addressing: one protocol, one implementation, while
the secret store hashes a lookup key rather than content. sha256 across twelve
packages is a primitive serving different purposes. The deadline engine's
activity-start check uses a different operand from the period-end comparison,
answering a related but distinct question. Decimal parsing: four apparent money
parsers all route into one `core.decimal` home exposing two deliberately
separated grammars. Direction: one sign-based derivation, at the parse boundary,
called once, zero downstream consumers. Per-format bank modules carry zero
parsers of their own; all four live in the shared base. CLI result emission:
every emit helper delegates to the one envelope builder. CLI id resolution: one
resolver, injected once, threaded by dependency injection. MCP: duplication is
structurally impossible rather than merely absent, because the in-process host
invokes the real command. The one MCP-native tool has no CLI counterpart at all.
Wizard answer projection: two functions look like one job but differ in keyspace,
source, absent-handling and validation posture, both routing through one parser.
Wizard profile writes duplicate a trivial three-line rule while the substantive
descendant handling is already shared. The live-auth preflight emitting outside
the notice channel is correct-by-design per its own governing audit.

## Recommendations

Persist the discriminator, not merely the verdict, whenever a near-neighbour is
cleared. A verdict alone is unfalsifiable by the next reader.

Before consolidating two measures of one domain quantity, find the validator or
gate that keeps them apart and read what it asserts. In a regulated domain the
separation is frequently the requirement rather than an accident.

When a finding already lives in an accepted decision record, cite where it lives
rather than restating it. A restated finding competes with its original.
