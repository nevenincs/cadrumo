---
tags:
  - '#adr'
  - '#ledger-renta-pipeline'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-ledger-renta-pipeline-research]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
---



# `ledger-renta-pipeline` adr: `canonical-ledger-observations-for-renta-bindings` | (**status:** `accepted`)

## Problem Statement

The codebase has a real ledger backend, purchase invoice evidence association model,
category/proportionality catalogue, calculation registry, and Renta
formula surface, but these pieces are not connected into a persisted
ledger-to-Renta calculation path.

The current calculation runtime accepts explicit casilla inputs,
binding values, and relation values. It does not load financial
repositories, classify expenses, apply proportionality, or derive Renta
deductible amounts. The declaration CLI has a deliberate aggregation
seam, but the observed implementation still returns no aggregated
filing inputs for the ledger/Renta case.

This feature therefore must be treated as new architecture, not a
minor wiring task or an extension of speculative autonomous work.

## Decision

Ledger-to-Renta integration will be implemented as a pre-calculation
observation and binding pipeline.

The ledger financial transaction catalogue is the canonical classified ledger state for
calculation purposes. User CLI review overlays remain non-canonical
until an explicit reconciliation path writes their classification and
split choices into the ledger financial transaction catalogue or into a reviewed,
typed, auditable bridge record.

Renta calculations will consume strongly typed Renta ledger
observations derived before registry calculation. These observations
will be built from persisted ledger financial transaction and purchase invoice evidence catalogue state,
validated category identifiers, category profile/proportionality rules,
usage ratios where applicable, and filing-period filters.

The calculation registry remains pure. `calculate_registry_snapshot`
will continue to consume explicit `inputs`, `binding_values`, and
`relation_values`; it will not gain repository access.

Registry bindings for the covered Renta surfaces will use explicit
binding definitions with legal references and source references. The
binding resolver layer will convert Renta ledger observations into
binding values using the same side-effect-free pattern already used by
IVA and OSS/IOSS ledger aggregation.

The first executable slice will target a narrow Modelo 100
direct-estimation expense path. Broader cases such as purchase invoice evidence
precedence, refunds, retentions, payments, rental-specific bindings,
and review-state reconciliation must either be decided in this ADR's
plan or deferred explicitly.

## Considerations

The research identified a mature precedent for ledger-shaped
calculation data: `IvaLedgerObservation`,
`OssIossLedgerObservation`, and purchase invoice evidence observations are typed,
side-effect-free records consumed by binding resolvers. They do not
load repositories directly.

The Renta surface differs from IVA because deductible amount is not
always the transaction amount. Category proportionality, statutory
caps, user usage ratios, exclusive-use gates, business classification,
and purchase invoice evidence may all change or block the deductible result.

The category registry is already the strongest legal substrate for
deductibility because it carries citation-backed proportionality rules.
It is not currently an evaluator and it does not project categories to
Renta casillas. That evaluation and projection must be new typed
domain behavior.

Modelo 100 already contains direct-estimation formulas for economic
activity income, deductible expenses, difficult-to-justify expenses,
and net yield. Existing tests drive these formulas with manual or
synthetic values. They do not prove persisted ledger integration.

The existing schema already admits generic `ledger` and `category`
source values, but the implemented resolver precedent is a narrower
source contract such as `ledger_iva_aggregation` or
`ledger_oss_aggregation`. The plan must decide whether Renta uses a
generic source or introduces an explicit Renta ledger aggregation
source before registry bindings land.

## Constraints

Every new boundary record must be strict and typed. Persisted category
strings must be normalized to closed `SpendingCategory` members before
they become calculation facts.

Every deductible result must carry provenance back to source
transaction, purchase invoice evidence when applicable, category, proportionality rule,
binding definition, and legal/source references.

The aggregation path must prevent duplicate counting between linked
purchase invoice evidence and ledger financial transaction facts.

Date, period, sign, refund, reversal, and partial-payment semantics
must be explicit before those cases are enabled.

The legal category catalogue currently in the repository is usable
local grounding, but any claim to an updated legally current deductible
category list requires a fresh official-source pass against AEAT and
BOE material before implementation is marked complete.

Tests must be real-behavior tests. They may not use fakes, mocks,
stubs, monkeypatches, skips, or xfails as shortcuts, and they may not
restate the implementation formula as the expected value.

## Implementation

The implementation will land through a staged VaultSpec plan.

The first stage creates the formal feature pipeline and removes the
temporary kickoff notes. This does not implement feature code, but it
establishes the research, ADR, plan, and execution trail required for
subsequent code work.

The second stage inventories modeller inputs that require ledger data,
starting with Modelo 100 and Modelo 130, then confirming how existing
IVA and OSS/IOSS aggregation paths fit into the same filing input
aggregation layer.

The third stage defines and tests the Renta observation and
deductibility models. These models will represent gross amount,
business-use amount, deductible amount, non-deductible amount,
category, proportionality result, legal citations, and source
provenance.

The fourth stage implements repository-backed aggregation before
calculation. This layer loads the ledger financial transaction and purchase invoice evidence catalogues,
applies period filters, reconciles facts, resolves category profiles,
evaluates proportionality, and emits binding values and filing inputs.

The fifth stage adds registry bindings and resolver support for the
covered Renta slice, then runs the real Modelo 100 calculation
snapshot with explicit binding values.

The final stage hardens legal grounding and verification, including
official-source refresh for any updated legally current deductible
category list.

## Rationale

Keeping repository loading outside the formula runtime preserves the
registry architecture already used throughout the calculation backend.
It also keeps calculation snapshots deterministic and testable.

Using canonical ledger financial transaction catalogue state prevents UI review overlays
from silently changing legal results without an auditable domain
transition. If review-state reconciliation is needed, it becomes an
explicit feature rather than hidden coupling.

Typed observations provide a reusable bridge between persisted
financial facts and model-specific registry bindings. The same pattern
already works for IVA and OSS/IOSS and is safer than embedding ledger
filters directly in formulas.

Proportionality belongs before calculation because it is legal and
factual classification, not arithmetic over already-established
casilla values. The registry should own binding IDs, formula targets,
legal references, and source references; the category registry should
own category-specific proportionality citations.

## Consequences

The first implementation slices will add new domain and registry
surface area rather than only wiring an existing module.

The plan must resolve source-kind naming, observation shape,
purchase invoice evidence-versus-ledger financial transaction precedence, review-state reconciliation,
period filtering, sign/refund handling, and legal-source refresh before
the broader feature can claim completion.

Existing Renta tests will remain valid but insufficient. New tests must
prove the persisted path from classified ledger facts through
observation, binding resolution, filing input aggregation, and
calculation snapshot.

The feature will likely expose inconsistencies between ledger review
state and ledger financial transaction catalogue state. Those inconsistencies must fail
loudly or remain outside calculation until reconciled.
