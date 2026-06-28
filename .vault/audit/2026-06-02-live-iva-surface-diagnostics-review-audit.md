---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-28-live-iva-read-only-auth-success-surface-failures-audit]]'
---

# `live-iva-compensation-wallet` Code Review

S56-20260602-001 | INFO | Redacted diagnostics improve live-surface evidence
Reviewed the live-surface diagnostics slice. The declarations driver now emits
structured page-shape context on navigation/form/search failures, and the
combined acquisition path carries timeout progress into CLI output and persisted
manifest surfaces. The context is structural: phase, model/year/period, URL with
query stripped, booleans, counts, bounded button/header labels, and raw HTML
hash. It does not persist raw HTML, filed values, wallet amounts, expediente
ids, or taxpayer identifiers.

S56-20260602-002 | INFO | Locale gap addressed
The touched declarations error for unavailable modelos now uses
`adapters.sede.errors.modelo_unavailable`, populated through `aeat.locales` for
`es`, `en`, `ca`, and `hu`. The live IVA surface-timeout error also now carries
the registered `errors.error.error_application_live_iva_surface_timeout`
translation key instead of relying on the hardcoded debug message for
operator-facing rendering. The diagnostic phase values remain stable machine
identifiers in `failure_context`, not operator-facing translated copy.

S56-20260602-003 | LOW | Wallet/cartera still blocks production readiness
The live smoke evidence improved materially but remains partial. One 2026
Modelo 303 declaration-query run reached the authenticated surface and returned
a successful zero-row filed-history result, but wallet/cartera still timed out.
The feature remains provisional until wallet/cartera either yields parseable
read-only evidence or a legally grounded no-wallet route is documented and
implemented.

S56-20260602-004 | LOW | Multi-year filed-history remains open
The successful filed-history run covered only Modelo 303 / 2026 and captured no
rows. It proves the production route can be reached for that query, not that
multi-year filing history or submitted-file download works end to end.
