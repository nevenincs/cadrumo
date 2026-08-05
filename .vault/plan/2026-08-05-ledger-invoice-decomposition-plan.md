---
tags:
  - '#plan'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_hash: 'sha256:40d26281bf86933cccd28a5685ad8acc6b0d6cc9cf24f82086ba7f9b4dde46b4'
tier: L2
related:
  - '[[2026-08-05-ledger-invoice-decomposition-adr]]'
  - '[[2026-08-05-ledger-invoice-decomposition-reference]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `ledger-invoice-decomposition` plan

## Steps

### Phase `P01` - Income measure grounding

Make the renta income measure explicit and its gaps visible. The fact selector stops defaulting to a legal claim, the honest name replaces the misleading one, and every row that reaches a filed casilla without invoice substrate surfaces an advisory instead of folding bank cash in silently.


<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

- [x] `P01.S01` - Remove the fact default from the renta ledger income selector so an omitting binding fails registry validation loudly; `src/cadrumo/domain/calculations/registry/_ledger_bindings.py`.
- [x] `P01.S02` - Remove the divergent fact default from the impatriado income selector so both siblings are required; `src/cadrumo/domain/calculations/registry/_ledger_impatriado_bindings.py`.
- [x] `P01.S03` - Rename the renta and impatriado fact gross_income_sum to cash_received_sum, leaving the accurately-named Modelo 210 member untouched; `src/cadrumo/domain/calculations/registry/_ledger_bindings.py`.
- [x] `P01.S04` - Add the income-side missing-substrate issue reason mirroring the gasto pipeline, with an explicit observation grounding marker; `src/cadrumo/application/aggregation/_renta_income_ledger.py`.
- [x] `P01.S05` - Surface the missing-substrate advisory on both the preflight and calculate paths through the typed notice channel; `src/cadrumo/application/modelo/_calculation_actions.py`.
- [x] `P01.S06` - Stop taxable_base_sum coercing a missing base to zero, routing base-less rows into the ungrounded class; `src/cadrumo/domain/calculations/registry/_ledger_bindings.py`.

### Phase `P02` - Component axis and legal grounding

Declare which components an invoice of each IVA category actually has, as registry-grounded data derived from the existing category frozensets rather than a parallel list that can disagree with them. Land the legal catalogue entries and retencion rate parameters the table cites.

- [ ] `P02.S07` - Declare the per-category component-expectation table as registry-grounded data derived from the existing cuota-less frozensets, never a parallel list; `src/cadrumo/domain/iva/_schema.py`.
- [ ] `P02.S08` - Gate the table for completeness across every IvaCategory member and for non-divergence from the frozensets it derives from; `src/cadrumo/domain/iva/tests`.
- [ ] `P02.S09` - Land the legal catalogue entries every component-expectation row cites, each resolving to bundled authoritative corpus text; `src/cadrumo/_data/registry/aeat/legal`.
- [ ] `P02.S10` - Land the RIRPF article 95 retencion rate parameters as registry data rather than feature-module literals; `src/cadrumo/_data/registry/aeat/legal`.

### Phase `P03` - Retencion derivation and invoice contracts

Let exempt invoices recover their retencion by relaxing the inference precondition to category-determinable cuota, keeping the registry max-rate bound and never inverting a rate from cash. Give the invoice record its decomposition contract so a partial declaration is excluded but visible.

- [ ] `P03.S11` - Relax the withheld-inference precondition to category-determinable cuota so exempt invoices recover their retencion, keeping the registry max-rate bound; `src/cadrumo/application/aggregation/_renta_income_ledger.py`.
- [ ] `P03.S12` - Add the invoice retencion consistency validator, holding retencion outside the grand total; `src/cadrumo/domain/transactions`.
- [ ] `P03.S13` - Add the partial-invoice decomposition contract so an ungrounded record is excluded but visible rather than silently dropped; `src/cadrumo/domain/transactions`.

### Phase `P04` - Verify severity escalation

Escalate the missing-substrate advisory to a verify-stage refusal only where the under-declaration direction is certain, on operator ratification.

- [ ] `P04.S14` - Escalate the advisory to a verify-stage refusal only for a row declaring a cuota-less category with no taxable base, pending operator ratification; `src/cadrumo/application/modelo`.

### Phase `P05` - Oracle grounding and roundtrip coverage

Prove the chain against external AEAT authority rather than against itself, anchored on a worked example carrying retencion and an exempt-services example, with roundtrip coverage for every new persisted field.

- [ ] `P05.S15` - Ground the chain on an AEAT worked example carrying retencion, asserting against the published figure and never against the formula under test; `src/cadrumo/domain/calculations/registry/tests`.
- [ ] `P05.S16` - Ground the chain on an exempt-services example proving the under-declaration direction is closed; `src/cadrumo/domain/calculations/registry/tests`.
- [ ] `P05.S17` - Add strict roundtrip coverage for every new persisted field, with an anti-tautology proof that a deleted field is refused on load; `src/cadrumo/application/calculations/tests`.
