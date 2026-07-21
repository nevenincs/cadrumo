---
tags:
  - '#research'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-10'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# `m210-irnr-phase-2-engine` research: `M210 grouped-rentas and ledger aggregation contract`

## Findings

### Current boundary

`W01.P02.S06` cannot be implemented as another aggregate-casilla predicate.
The binding M210 design declares `tipo_renta`, `rendimientos_integros`,
`gastos_deducibles`, and the inmobiliaria facts as `input_kind = "manual"`;
its formula resolves one scalar `base_imponible`.  There is no M210 detail-row
variant in `ModeloDetailRow`, no M210 ledger binding, and verification consumes
aggregate casilla/text mappings rather than a declared renta row set.  Sources:
`src/aeat/_data/registry/aeat/modelos/210/revisions/2025/casillas/0001-casillas.toml`,
`src/aeat/domain/modelos/_row_models.py`, and
`src/aeat/application/modelo/_verification_predicates.py`.

The statutory grouping facts are genuinely row-relative.  The bundled
consolidated Orden EHA/3316/2010 says that grouped rentas must belong to one
contributor and have the same tipo-de-renta code, payer, tax rate and, when
arising from a bien/derecho, the same bien/derecho; the payer requirement is
waived only for unwithheld rented/sublet property using code 35; grouped rentas
never offset each other.  It also fixes the result-dependent quarterly/annual
grouping windows.  Source:
`src/aeat/_data/corpus/normatives/html/orden-eha-3316-2010.html:680-685`.
Those facts cannot be reconstructed honestly from the existing scalar inputs.

The accepted multi-row and 353 designs give useful but non-substitutable
precedents.  `ModeloDetailRow` is the strict persisted operator-row boundary;
the M353 `per_grupo_member` exception is instead an opt-in fan-in of filed
observations across filers.  It must not be repurposed for M210 rentas: M210
needs one declaration's source records and legality checks before its base is
summed.  Sources: `2026-05-27-multi-row-modelo-declaration-adr`, D2; and
`2026-06-02-modelo-multiyear-renta-353-grupo-aggregation-adr`, Implementation
and Rationale.

`W02.P05` has the same missing primitive.  The current source mesh already
enrols the Modelo 151 `ledger_impatriado_income_aggregation` classifier, which
emits only ES-source observations and reports foreign or unresolved rows as a
typed issue containing the transaction id and rejected jurisdiction.  M210 has
no counterpart in `BindingSourceKind` or the 2025 registry bindings, so its
manual base cannot receive a provenance-preserving source-scope filter.  Sources:
`src/aeat/application/aggregation/_impatriado_income_ledger.py`,
`src/aeat/application/aggregation/_modelo_bindings.py`,
`src/aeat/application/modelo/_calculation_actions.py:520-681`, and
`src/aeat/core/aggregation.py:213-272`.

The accepted source-jurisdiction decision and S16's classifier verdict remain
sound: a per-row classifier, not a verification predicate, retains the source
record and its jurisdiction in an operator-visible issue.  Existing predicates
operate on aggregate casilla values; extending them to produce row evidence
would create a second classifier pathway.  Sources:
`2026-05-27-source-jurisdiction-axis-adr`, Consequences;
`2026-05-28-source-jurisdiction-axis-research`, Recommendation; and
`2026-06-10-calculation-aggregation-taxonomy-adr`, canonical mechanism table.

### Legal and corpus boundary

The grouping rule is already bundled and sufficient for the row-shape decision.
The generic IRNR source-scope rule must be grounded on the consolidated TRLIRNR
Article 13 (rentas obtenidas en territorio español), with Articles 24 and 25
then governing base and rate.  The present M210 catalogue snippet contains only
Article 13.1.h's inmobiliaria example, while Article 25.1 is a rate rule, not a
generic source-scope rule.  The M210 aggregation ADR therefore needs a bundled,
authoritative Article 13 source before it defines generic ledger classification;
it must not treat Article 25.1 as that authority.  Sources:
`src/aeat/_data/corpus/normatives/html/trlirnr-rdleg-5-2004.html#a13-1-h`,
`#a24`, and `#a25`; see also the corpus-grounding rule
`legal-grounding-verifies-bundled-authoritative-corpus`.

### Options and recommendation

- **Scalar manual inputs plus a grouping predicate.** Reject.  No row set or
  grouping attributes reaches the evaluator, so any predicate would either be
  tautological or invent facts.
- **A generic per-row predicate pipeline.** Reject.  It duplicates the existing
  classifier role, loses typed transaction evidence, and contradicts the
  accepted classifier decision.
- **A ledger-only M210 source copied from Modelo 151.** Defer.  It addresses
  source jurisdiction but cannot establish the legally required renta, payer,
  rate, and bien/derecho grouping attributes from the current M210 contract.
- **Row-first M210 base-ingestion contract with one classifier-backed ledger
  projection.** Recommend.  Record this as a new ADR before reopening S06 or
  S10-S12.

The ADR should introduce one strict, persisted `Modelo210RentaRow`/IRNR
observation contract, with a stable row/source id, non-negative declared amount,
official tipo-de-renta code, payer identity (or the explicit code-35 exception),
applicable rate identity, and conditional bien/derecho identity.  Its row-set
evaluator owns the EHA/3316 grouping checks and rejects any attempted offset.
The ledger adapter may emit the same observation only when it has every required
attribute; it must issue a typed unresolved/enrichment finding rather than infer
missing payer, rate, or asset facts.

On that single observation channel, add a distinct
`ledger_irnr_income_aggregation` binding source and a Modelo-151-shaped M210
classifier.  It admits only `source_jurisdiction == "ES"` into the M210 base;
foreign and unresolved rows produce
`IrnrAggregationIssueReason.FOREIGN_SOURCE_OUT_OF_SCOPE` with their source id
and original jurisdiction, remain in provenance, and do not contribute a value.
The source mesh must be its sole base writer: caller scalar overrides of a
ledger-owned M210 base are refused, and manual-row and ledger modes must be
explicitly mutually exclusive or be normalised into that same observation set.
This follows the taxonomy's ledger-projection row and its exclusive mesh
ownership rule, rather than adding a parallel calculation path.

The implementation proof should use real persisted transaction/catalogue
behaviour: one ES row and one foreign row in the same filing window, asserting
that only the ES observation reaches the bound M210 base and that the issue
preserves the foreign source id and code.  A jurisdiction mutation must change
the admitted base and clear/create the issue, without reimplementing aggregation
arithmetic in the test.  A separate row-set test must demonstrate a valid group,
the code-35 payer exception, and rejection of a mismatched code, rate, or
bien/derecho / offset attempt.  This is the evidence needed to close S06 and
S10-S12; S17 and S18 follow only after the new issue surface is settled.
