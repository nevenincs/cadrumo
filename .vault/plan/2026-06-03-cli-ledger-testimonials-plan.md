---
tags:
  - '#plan'
  - '#cli-ledger-testimonials'
date: '2026-06-03'
modified: '2026-06-03'
tier: L2
related:
  - '[[2026-06-03-cli-ledger-testimonials-audit]]'
  - '[[2026-06-03-cli-ledger-testimonials-adr]]'
  - '[[2026-06-04-cli-ledger-testimonials-research]]'
---


# `cli-ledger-testimonials` `CLI ledger-operator hardening: testimonial findings to fixes` plan

### Phase `P01` - BLOCKER fixes

Resolve the round-trip, atomicity, and IVA-wallet-seed blockers that sever the operator filing path.

- [x] `P01.S01` - Fix Transaction CLI read-model to accept persisted value_in_eur/fx_rate (B1 #49); `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `P01.S02` - Verify ledger mutation atomicity: no refused-command partial writes (B2); `src/aeat/application/ledger/_actions.py`.
- [x] `P01.S03` - M303 calculate-side lazy-reconcile + casilla 110 surfacing + lot_count fix (B3 #50); `src/aeat/application/modelo/_actions.py`.

### Phase `P02` - Test-surface regression and profile-identity

Bucket-session fixture regression plus the UUID-vs-display-name in-process profile-resolution split.

- [x] `P02.S04` - Migrate ledger/modelo CLI test fixtures to bucket-session span pattern (#52); `src/aeat/entrypoints/cli/test_ledger_validation_paths.py`.
- [x] `P02.S05` - Resolve UUID-vs-display-name in-process profile identity for regime-variant tests (#53); `src/aeat/application/workflow/_errors.py`.
- [x] `P02.S06` - Journey-suite lifecycle post-state asserts + devengo-vs-caja basis test + README count (#48); `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.

### Phase `P03` - MAJOR UX fixes

File-obligation discoverability, ledger list filters, bulk classification facts, and recovery-message honesty.

- [x] `P03.S07` - file NO_PENDING_OBLIGATION discoverability + readiness reconciliation; `export as finish line (#51); `src/aeat/application/modelo/_actions.py`.
- [x] `P03.S08` - ledger list --filter via LedgerReviewFilterSpec reuse (period/year/status/classification/text) (#54); `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `P03.S09` - ledger list --filter direction + account via shared-spec extension (#55); `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `P03.S10` - config repair recovery honesty: fix or honestly disclaim the read-model failure class (M4); `src/aeat/entrypoints/cli/_config`.
- [x] `P03.S11` - Bulk classify supplies IVA facts (taxable_base/iva_rate/iva_amount), not only classification/category (m-bulk); `src/aeat/entrypoints/cli/_ledger.py`.

### Phase `P04` - MINOR and COSMETIC polish

Discoverability and consistency papercuts surfaced by the testimonials.

- [x] `P04.S12` - MINOR/COSMETIC polish: id-arg hint, describe/preflight in --help, period-token consistency, output_language honoring, percent-in-error, bindings list --missing, create --help minimal hint; `src/aeat/entrypoints/cli`.

### Phase `P05` - Post-fix persona re-run and verification

Re-run skeptic, foreign, and crossyear personas to close the still-open safety, casilla-routing, and prior-year-carry items.

- [x] `P05.S13` - Re-run skeptic/foreign/crossyear personas post-fix to close still-open: silent-under-declaration on calculated return, M303 special-IVA casilla routing, prior-year previous_filing carry across a filed period; `.vault-scratch/personas`.
- [x] `P05.S14` - Land independent-review findings for commit 4deddd89f: correct legal attribution in M131 advisory TOML comments (art. 110.1.b vs instructions vs art. 110.4), align C02 label to registry ('Pago fraccionado previo por datos-base'), fix test docstring; `add locale keys for M131 and M200 advisory finding messages (blocked by peer locale WIP); `src/aeat/_data/registry/aeat/modelos/131/revisions/*/verification_expectations/0002-verification_predicates.toml, src/aeat/application/modelo/tests/test_verification_substance.py, src/aeat/locales/*.yml`.

## Description

This plan converts the graded findings from the six-persona CLI ledger-operator
testimonial campaign (recorded in `2026-06-03-cli-ledger-testimonials-audit`)
into landed, gate-reviewed fixes. Personas operated the real `aeat` CLI against
the hand-authored ledger-corpus (Marta Ríos Velasco, autónoma, 514 transactions,
cross-year 2025 to 2026 H1) attempting end-to-end cross-period filing. The
verdict: the CLI's own signposted path (import to classify to file) was severed
by confirmed BLOCKERs, while the manual binding-to-export path worked.

Phases proceed in priority order. P01 clears the filing-path BLOCKERs (the FX
read-model round-trip, mutation atomicity, and the IVA-wallet-seed circularity).
P02 restores the bucket-session test regression and splits out the distinct
profile-identity resolution. P03 lands the MAJOR UX fixes (file-obligation
discoverability, ledger list filters, bulk classification facts, recovery
honesty). P04 sweeps the minor papercuts. P05 re-runs the personas to confirm the
still-open safety, casilla-routing, and prior-year-carry items are closed. Each
Step is one fix paired with a real-behaviour test behind the code-review gate;
every BLOCKER was re-verified against HEAD before action, and several transient
peer-churn pseudo-blockers were screened out rather than chased. Three of the
thirteen Steps were already landed and gate-passed at authoring time (B1/#49, the
B2 atomicity proof, and the #52 bucket-session migration).

## Steps







## Parallelization


## Verification
