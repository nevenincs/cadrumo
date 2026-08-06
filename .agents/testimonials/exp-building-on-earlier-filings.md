# Testimonial — `docs/explanation/building-on-earlier-filings.md`

- **Doc path:** `docs/explanation/building-on-earlier-filings.md`
- **Persona:** A curious user reading the EXPLANATION page on how filings build on
  earlier periods (cross-period dependencies, carry-forward, the IVA wallet,
  previous_filing / relation bindings). Not running a command tutorial — verifying
  every factual claim against the real CLI and source, and judging whether the
  narrative matches how the app actually behaves.
- **Date:** 2026-06-18

This is an explanation page with **no commands to run literally** — so the
"Walkthrough" is a claim-by-claim verification against source and the live CLI,
rather than a command transcript.

## Claim-by-claim verification

### Claim 1 — "Annual summaries gather the year. Modelo 390 summarises the year's Modelo 303 IVA filings; Modelo 100 (RENTA) pulls together instalments and withholdings."
- **Expected:** M390 derives from M303; M100 derives from instalment/withholding filings.
- **Actual:** Confirmed. M390←M303 fold-in is a real, live-tested relation:
  `src/aeat/application/modelo/tests/test_modelo_390_303_fold_in_live.py`. RENTA
  fold-in: `test_renta_annual_reconciliations_fold_in_live.py`,
  `test_relation_fold_in_live.py`, `test_modelo_202_sociedades_fold_in_live.py`.
  `IvaCompensationAnnualSummary` is explicitly described as the "Filed Modelo 390
  annual IVA compensation summary for cross-checking" against the M303 carry-forward
  lots (`_iva_compensation_history.py:45-63`).
- **Verdict:** OK.

### Claim 2 — "Unused IVA carries into the next period as a credit you keep until a later return can use it."
- **Expected:** A running carry-forward of unused IVA credit across M303 periods.
- **Actual:** Confirmed. `query_iva_wallet_balance` builds an
  `IvaWalletBalanceReport` summarising "carry-forward lots and the available
  compensation balance" (`_iva_wallet_balance.py`). Live CLI: `aeat app modelo
  iva-wallet balance` — "Muestra el saldo acumulado del crédito IVA por
  compensación calculado a partir del historial local del Modelo 303."
- **Verdict:** OK.

### Claim 3 — "Earlier figures must be backed by evidence; a figure should come from a filing you completed and marked as filed, ideally backed by the agency's receipt."
- **Expected:** The carry-forward path is gated on official/filed evidence, not
  unconfirmed data.
- **Actual:** Confirmed. The cross-period clean-state gate
  (`_cross_period_clean_state.py`) reads filed `ModeloRecord` rows and proves a
  dependent period's upstream filings "carry official evidence". `_OFFICIAL_SOURCE_KINDS`
  = {`aeat_sede_justificante`, `aeat_sede_live_capture`, `aeat_csv_register`}.
  Blocker codes include `MISSING_EXTERNAL_EVIDENCE`,
  `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`, `MISSING_AEAT_ACCEPTANCE`,
  `MISSING_JUSTIFICANTE_VERIFICATION`. The gate is wired into the real filing,
  verification, and calculation paths (`_filing_actions.py`,
  `_verification_actions.py`, `_calculation_actions.py`) via
  `_require_cross_period_clean_state` → `ModeloCrossPeriodCleanStateError`. This
  exactly matches the brief's known finding that "verify blocks on unevidenced
  prior periods."
- **Verdict:** OK — and notably accurate, not overstated.

### Claim 4 — "It carries forward what it HAS on record for the matching modelo/year/period; it does not invent a missing prior; if you ask for four quarters and only two are on record, it brings in the two."
- **Expected:** No fabrication of absent priors; a missing prior surfaces as a gap.
- **Actual:** Confirmed. The requirement model is keyed by
  `(source_modelo, filing_year, period)` (`CrossPeriodDependencyRequirement`), a
  missing upstream yields `MISSING_OBSERVATION` / `MISSING_CURRENT_FILING_RECORD`
  blockers rather than a silent zero, and pre-activity periods are *explicitly*
  scoped out with an auditable `NoPriorObligationProvenance` marker
  (`no-silent-under-declaration`). Nothing fabricates an absent period.
- **Verdict:** OK.

### Claim 5 — "The running IVA credit needs a true starting point; you set the opening balance once (the credit you were already carrying when you started); from there each period updates the balance on its own."
- **Expected:** A one-time opening-balance seed for pre-history credit.
- **Actual:** Confirmed. `seed_iva_compensation_period` writes a `status='seeded'`
  state for "a period that pre-dates local history" and **refuses if a record
  already exists** (`IvaCompensationSeedConflictError`). Live CLI: `aeat app modelo
  iva-wallet seed` — "Declaración de un saldo inicial ... para un período anterior
  al historial local. Se rechaza si ya existe un registro para el período."
- **Verdict:** OK.

### Claim 6 — "You can fix a wrong opening balance after the fact, but the tool refuses to change the basis of a period you've already completed and marked as filed; the correction is refused and NAMES the filing in the way."
- **Expected:** A correction path that is blocked by an already-filed (sealed) M303,
  with the blocking filing identified.
- **Actual:** Confirmed precisely. `correct_iva_compensation_period` is the
  deliberate re-write path (refuses on a missing period — "seed, not a correction").
  The sealed-period guard lives one layer up in
  `_iva_wallet_seed.py`: `_sealed_modelo_303_blocker_for_period` finds the first
  sealed (`VERIFICADO_COMPLETO` / `PRESENTADO`) M303 at or after the seeded period
  and raises `ModeloIvaWalletCorrectionSealedError` with context carrying
  `blocking_filing_year` (so it literally "names the filing that's in the way").
  Live CLI confirms: `aeat app modelo iva-wallet correct` — "se rechaza ... si un
  Modelo 303 ya presentado ha consumido la base sembrada (corregirla cambiaría una
  declaración presentada)." This is a strong, accurate match to the prose.
- **Verdict:** OK.

### Claim 7 — "RENTA settles on the instalments and withholdings the tool has on record from filings you completed; you review those before trusting the result."
- **Expected:** RENTA depends on prior instalment/withholding filings, gated as above.
- **Actual:** Confirmed (same cross-period gate + RENTA fold-in tests as Claims 1/3).
- **Verdict:** OK.

### Claim 8 — "What the tool checks vs what it leaves to you: it does not silently treat unconfirmed/out-of-date agency data as final, does not invent a prior period, does not sweep up every figure and assume it's correct."
- **Expected:** Conservative carry-forward; human keeps confirmation.
- **Actual:** Consistent with the blocker taxonomy
  (`OBSERVATION_REVISION_VALUE_DIVERGENCE`, `MISMATCHED_EXTERNAL_EVIDENCE_RECORD`,
  `REGISTRY_REVISION_DIVERGENCE`) and the stamped-revision re-confirmation
  (`stamped_revision_id` on the observation payload; divergence → blocked carry per
  ADR 2026-06-10-period-revision-resolution-adr). The narrative matches behavior.
- **Verdict:** OK.

### Naming note — previous_filing vs relation_prefill (brief's flagged concern)
- The brief asked to verify the binding-naming claim. **The page never uses the
  internal terms `previous_filing` or `relation_prefill`** — it stays at the
  taxpayer-facing "carries figures forward" level. That is the *correct* editorial
  choice for an explanation page (per the source-hygiene / taxpayer-facing rules).
  Under the hood both source kinds are real and distinct: `previous_filing` (direct
  same-modelo carry) and `relation_prefill` (cross-modelo fold-in slot), with a
  registry collision gate in
  `domain/calculations/registry/_validate_relation_sources.py` and the documented
  M303 iva-wallet carve-out
  (`_IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS`). The page's omission of these
  internal names is appropriate, not an inaccuracy.
- **Verdict:** OK (the abstraction is honest).

### Cross-links and glossary terms
- `{term}` roles `modelo 100`, `casilla`, `justificante`, `AEAT` — **all resolve**
  to real entries in `docs/_generated/glossary.rst` (and the concept TOMLs exist).
- The glossary `{doc}` target `/_generated/glossary` exists
  (`docs/_generated/glossary.rst`).
- Internal markdown links all resolve to existing files:
  `from-records-to-figures.md`, `index.md`, `reviewing-and-exporting.md`,
  `../how-to/review-calculation-values.md`, `../how-to/modelo-390.md`.
- IVA / IRPF / RENTA are referenced as **plain prose** (not `{term}` roles) in the
  same sentence that tells the reader to look terms up; all three nonetheless exist
  in the glossary (`IVA`, `IRPF`, `renta`). Minor inconsistency only — see Finding 1.
- **Verdict:** OK (one NIT).

### Passphrase note (brief's standing finding)
- This page documents no commands, so it correctly does not mention the master-key
  passphrase. Not applicable as a finding for this page (the iva-wallet/verify
  commands that DO require it belong to the how-to pages).

## Findings

1. **[NIT] [DOC]** Inconsistent term-role usage. The sentence lists
   "`modelo 100`, `casilla`, `justificante`, `AEAT`, IVA, IRPF, or RENTA" but only
   the first four are `{term}` roles; IVA / IRPF / RENTA are bare text even though
   they have real glossary entries (`IVA`, `IRPF`, `renta`). A reader gets a hover
   card / link for four of seven terms and nothing for the other three in the same
   breath. *Fix:* either make IVA/IRPF/RENTA `{term}` roles too, or move them out of
   the "look it up" list — keep one convention.

2. **[NIT] [DOC]** Slight understatement of the carry-forward guards. The page frames
   the safety story as "evidence-backed" and "doesn't invent a prior", which is
   accurate, but the app actually enforces *more*: it also blocks a carry when the
   prior was filed under a now-superseded registry revision
   (`REGISTRY_REVISION_DIVERGENCE` / stamped-revision re-confirmation) and when the
   stored figure diverges from the recomputed one
   (`OBSERVATION_REVISION_VALUE_DIVERGENCE`). This is the rare case where the app is
   *stronger* than the doc claims. *Fix (optional):* one sentence noting that a
   figure filed under an out-of-date rule set is also refused, not just a missing
   one — it would reassure the careful reader the page is written for.

No DOC-ISSUE, no APP-ISSUE, no BLOCKER, no MAJOR, no MINOR.

## Testimonial

I came in skeptical — explanation pages love to promise tidy guarantees the code
quietly breaks — but this one held up under every probe. Each claim I traced
landed on a real, tested surface: the M390←M303 fold-in, the seed-once /
correct-later IVA wallet, and especially the "we refuse to rewrite a figure a filed
return already used, and we'll tell you which filing is blocking" promise, which
maps one-to-one onto `ModeloIvaWalletCorrectionSealedError` carrying the blocking
filing year. The page wisely stays at the taxpayer's altitude and never leaks the
`previous_filing` / `relation_prefill` internals, yet nothing it says is loose. The
only things I'd touch are cosmetic: a half-applied glossary-term convention and a
chance to mention that out-of-date *rule sets* (not just missing periods) are
refused too. The app delivered exactly what the page promised.

## Scorecard

- **Doc clarity:** 5 / 5
- **App capability:** 5 / 5
- **Findings by severity:** BLOCKER 0 · MAJOR 0 · MINOR 0 · NIT 2
