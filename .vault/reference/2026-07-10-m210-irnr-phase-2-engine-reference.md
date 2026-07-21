---
tags:
  - '#reference'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-17'
related:
  - "[[2026-07-10-m210-irnr-phase-2-engine-research]]"
---

# `m210-irnr-phase-2-engine` reference: `M210 aggregation and grouped-row implementation blueprint`

## Summary

`W01.P02.S06` and `W02.P05.S10`–`S12` need two deliberately separate
contracts. Grouped M210 rentas are declared filing rows used only to validate
the Orden HAC/56/2024 grouping conditions; they must not become a second
calculation or aggregation path. M210 source scope is a ledger-source
contract: it needs an approved registry binding family, a classifier, and
provenance-bearing observations before it can derive or filter a base.

## Live analogues and constraint differences

- M151 supplies the source-scope pattern. Its classifier emits a typed issue
  before any foreign or undeclared-source row can become an observation
  (`src/aeat/application/aggregation/_impatriado_income_ledger.py:294`),
  retains the rejected jurisdiction on the issue
  (`src/aeat/application/aggregation/_impatriado_income_ledger.py:105`), and
  constructs the casilla total and transaction provenance only from admitted
  observations (`src/aeat/application/aggregation/_impatriado_income_ledger.py:433`).
  Its source resolver converts issues into calculate-time diagnostics and
  admitted rows into source provenance
  (`src/aeat/application/aggregation/_modelo_bindings.py:461`). M210 should
  copy that topology, not its annual-only period rule or its single M151 base
  casilla.
- M353's `per_grupo_member` is a different kind of grouping. It enumerates
  several already-persisted Modelo 322 observations for a cross-filer
  `previous_filing` fan-in
  (`src/aeat/application/calculations/_binding_prefill.py:265`,
  `src/aeat/application/calculations/_binding_prefill.py:400`). It has no
  operator-declared row set, no same-payer/rate/right validation, and no
  applicability to M210 rentas. Do not generalise it as the S06 solution.
- The generic row persistence seam is deliberately a tagged union
  (`src/aeat/domain/modelos/_row_models.py:627`) that
  `CalculationRevision` canonicalises before persistence
  (`src/aeat/domain/modelos/_calculation_revision.py:138`) and stores as
  `detail_rows` (`src/aeat/domain/modelos/_calculation_revision.py:477`). It
  can carry a new strict M210 row type, but its current input validator only
  knows M184 and M347 rules
  (`src/aeat/application/modelo/_calculate_input.py:427`); it supplies no
  M210 grouping semantics by itself.
- The current M210 engine is manual-input based. Its calculation bundle keeps
  decimal casillas, text casillas, bindings, relations, and detail rows
  separate (`src/aeat/application/modelo/_calculate_input.py:126`), while
  `tipo_renta` specifically remains a text casilla
  (`src/aeat/application/modelo/_calculate_input.py:307`). The verification
  expression runtime evaluates values, text values, profile state, and
  unresolved outcomes, not detail-row collections
  (`src/aeat/application/modelo/_verification_predicates.py:337`). Thus a
  row-set operator needs an explicit typed input into verification; adding a
  regex over existing scalar casillas would be ungrounded.

## Minimal viable blueprint

### S06 — grouped-renta contract and verification

1. First accept an ADR defining one strict, frozen
   `Modelo210AgrupacionRentaRow` domain record and its legal meaning. It must
   carry the official tipo-de-renta code, payer identity, applicable tax rate,
   the identified good/right, and a non-negative individual renta/base amount.
   The row needs an explicit representation for the code-35
   arrendamiento multi-payer exception; do not encode the exception as a
   missing payer. It belongs in `ModeloDetailRow` and therefore persists in the
   existing calculation revision rather than in an untyped side mapping.
2. Extend the M210 detail-row input boundary to accept only that validated row
   shape for an M210 work unit. The application validator must reject mixed
   M210/non-M210 row sets, empty grouped declarations, negative/off-setting
   component amounts, and rows whose declared official code disagrees with the
   work unit's M210 type input. Preserve the normal manual casilla path: rows
   establish grouping validity and provenance, not an alternative arithmetic
   path.
3. Add one registry-authorable row-set predicate operator to the verification
   runtime and pass the persisted M210 detail rows into it explicitly. Its
   implementation must prove: one code, one rate, one good/right, and one
   payer except for the explicit code-35 rule; each component is non-negative;
   and at least one row is present when the grouping/`0A` mode is asserted.
   Registry predicates then select which conditions apply to each M210 period
   and outcome. It must return ordinary typed verification findings with the
   registry legal/source references, not free-text application refusals.
4. Pin real calculate-then-verify tests through the persisted
   `CalculationRevision`: a valid group, each incompatible grouping key, the
   code-35 exception, and an attempted positive/negative offset. Assert both
   the computed manual-engine result and the saved row-set findings so the
   test cannot merely duplicate the predicate implementation.

### S10–S12 — M210 ledger source scope

1. Before implementation, accept a separate M210 ledger-base-ingestion ADR.
   It must declare the legal base fields that ledger observations may supply,
   the valid M210 periods, the source-to-casilla mapping, manual-versus-ledger
   ownership, and treatment of unresolved jurisdiction. This is necessary
   because the existing M210 input channel is manual and because M151's annual
   single-casilla selector is not a valid M210 contract.
2. Add one new typed `BindingSourceKind` and registry binding selector family
   for M210 IRNR ledger income. Restrict its selector to M210 casillas and
   explicitly supported facts; require `sum` and validate all of that at
   snapshot build. Add the family to the canonical ledger-source taxonomy and
   implement one registry resolver over an observation protocol. A manual value
   for a casilla owned by this binding must be refused or routed through the
   existing source-authority resolution—not silently merged.
3. Implement an application classifier analogous to M151 but with M210's
   ADR-approved period and casilla mapping. It loads the real bucket catalogue,
   partitions it by the calculated filing period, classifies an eligible
   Spanish-source row into a typed M210 observation, and creates
   `FOREIGN_SOURCE_OUT_OF_SCOPE` issues for every non-`ES` row. An unresolved
   jurisdiction must also fail loud rather than defaulting to Spain. Each issue
   preserves transaction id and original jurisdiction; only admitted rows form
   binding values, source transaction ids, and casilla provenance.
4. Register a source resolver that translates classifier issues into existing
   calculate-time diagnostics, emits unrouted-observation diagnostics for
   non-zero admitted rows no binding consumes, and retains the single
   registry-driven calculation path. Do not add a second M210 calculation
   service or filter manual `base_imponible` after the formula runs.
5. Add real secure-store tests: an ES row and a DE row in the same M210 window
   must produce the ES-only binding/base, an issue carrying `DE`, provenance
   for the ES transaction only, and a result distinguishable from the combined
   amount. Cover a missing jurisdiction, unsupported period/currency or
   classification as the ADR specifies, binding-definition rejection, and the
   calculate-to-verification persistence path. These are behavioural oracle
   tests over real catalogue and registry surfaces; they must not use fakes,
   patches, or a duplicate business-logic oracle.

## Delivery order

Land the accepted grouped-renta ADR and S06 first as a row-validation slice;
it has no dependency on ledger ingestion. Land the accepted M210 ledger-source
ADR, typed source kind/registry validation, classifier/resolver, and S10–S12
as one source-authority slice. Only after the latter exists can S17 choose a
consistent localized issue-label contract and S18 close task #62. The current
proposed Phase-2 ADR establishes the legal grouping rules, but it does not yet
approve either missing data contract.
