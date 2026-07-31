---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:38b2b370b39aa260cf2684b15bcbad8c927c333f442af9c51d734f9fec7119cb'
step_id: 'S312'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# FU-W05-D add hu.yml locale key-path fallbacks for the two new W05.P24 IVA classification reject reasons (DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION + EU_MEMBER_STATE_ON_EXPORT_TRANSACTION)

## Scope

- `architect non-blocking follow-up from Task #115 review`
- `src/aeat/locales/hu.yml`

## Description

- Ground S312 with RAG against the cross-domain plan row, the W05.P24 IVA D5 reject reasons, and the current ledger preflight/calculation-readiness path.
- Reject the initial Hungarian-only locale approach because scaffold/audit parity correctly treated the two new leaves as extra keys with no live code reference.
- Promote the D5 counterparty/category validator in the IVA aggregation module as the single application authority for ledger transactions.
- Route the two D5 invalid-counterparty reasons through ledger preflight so ledger-backed calculations see them as readiness blockers before aggregation can drop the rows.
- Add English, Spanish, Catalan, and Hungarian locale leaves for the two operator-facing details under the existing IVA ledger error namespace.
- Add real preflight tests for domestic counterparties on intra-community supplies, EU member states on exports, and Hungarian rendering of the domestic-counterparty detail.
- Run a scoped code review after implementation; the reviewer reported no findings.

## Outcome

S312 is closed as a production readiness/localisation fix. The two W05.P24 D5 reject reasons are no longer Hungarian-only catalogue extras: they are now live through ledger preflight, participate in the same blocking readiness surface consumed by ledger-backed calculations, and render from the supported locale catalogues.

The implementation imports from the real IVA aggregation module rather than adding a top-level facade reexport. The preflight layer reuses the aggregation validator and maps its typed reasons to first-class `LedgerPreflightIssueReason` members.

## Notes

Validation:

- `uv run --no-sync pytest src/aeat/application/ledger/tests/test_preflight.py -q` passed with 9 tests.
- `uv run --no-sync pytest src/aeat/application/aggregation/tests/test_intracom_export.py -q` passed with 10 tests.
- `uv run --no-sync python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run --no-sync python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run --no-sync pytest src/aeat/core/i18n/tests/test_placeholder_parity.py -q` passed with 3 tests.
- `uv run --no-sync ruff check src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/ledger/_preflight.py src/aeat/application/ledger/tests/_preflight_test_support.py src/aeat/application/ledger/tests/test_preflight.py` passed.
- `git diff --check` passed for the S312 path set, with only existing CRLF normalisation warnings on touched YAML/test files.

Notes:

- The first worker attempt added Hungarian locale leaves before the code path was live; scaffold/audit rejected that as `missing=0 extra=2`. The final implementation added the live path and all-locale leaves together.
- Review agent Aquinas reported no findings and did not edit files.
