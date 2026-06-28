---
tags:
  - '#research'
  - '#live-iva-compensation-wallet'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - '[[2026-05-19-iva-compensation-chain-audit-research]]'
  - '[[2026-05-19-iva-compensation-chain-adr]]'
  - '[[2026-05-19-iva-compensation-chain-plan]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-19-modelo-130-relation-regression-research]]'
  - '[[2026-05-19-modelo-130-relation-regression-plan]]'
---

# `live-iva-compensation-wallet` research: `AEAT-held IVA compensation wallet read`

This research checks whether the prior-period IVA compensation balance used
by Modelo 303 must be obtained from AEAT state, whether AEAT exposes that state,
and where the existing backend can host a read-only driver. The conclusion is
that the live AEAT wallet read is the lead backend requirement; local recurrence
is reconciliation and fallback evidence only.

## Findings

AEAT exposes the relevant state as the `Cartera de Cuotas a Compensar`, not only
as a value derivable from local filed declarations. The Modelo 303 procedure
page contains a dedicated consultation action named `Modelo 303. Consulta de la
cartera de cuotas de IVA a compensar`. The target path observed from the public
procedure page is `https://www1.agenciatributaria.gob.es/wlpl/DAI3-RUTI/CarteraCuotas`.
Unauthenticated access returns the AEAT certificate-identification error page,
which confirms this is an authenticated read surface.

AEAT's Pre303 documentation describes the wallet as available to all Modelo 303
filers through the result section and as an independent Sede service. AEAT says
casilla `110` is prefilled when the administration has the information, and the
wallet shows the balance split by generation year and period, applied amounts,
and pending amounts. This is stronger than a simple previous-filing recurrence:
the taxpayer can see the AEAT-held portfolio, including the generation-period
breakdown used to monitor expiry.

The value is still legally a declaration value, not an uneditable oracle. AEAT
states that the taxpayer may modify the prefilled casilla `110`; if modified,
the breakdown table is disabled, while casilla `87` still reflects the resulting
declared balance. Implementation should therefore treat the live wallet as the
highest-priority AEAT observation and reconciliation anchor, not as a silent
write-back or unchallengeable mutation of user data.

Local reconstruction from prior filings is insufficient as the primary authority.
It misses or can mis-handle late/autoliquidaciones extemporaneas, rectificativas,
administrative settlements, requested/refunded balances, foral-state splits,
four-year expiry tracking, and any AEAT-side adjustments reflected in the wallet.
It remains useful as a consistency check against AEAT's wallet and as a fallback
when the user has no live authenticated session.

SII is not the correct primary driver for this value. SII and Pre303/LLAA can
populate liquidation data for eligible taxpayers from IVA books, but AEAT exposes
the compensation wallet separately and makes it generally available. SII drivers
should remain book/liquidation evidence drivers, not the authoritative wallet
driver.

The codebase already has the right outer machinery:

- Certificate and Cl@ve Móvil session support under the AEAT outbound auth
  adapters.
- A read-only Sede module with structural `mode = "read"` schemas.
- A declarations-presented driver for `SCEJ-MANT/CONSUL`.
- Local encrypted observation persistence for filed declaration observations.
- A central live-read access gate and permanent live-write refusal.

The internal-state audit shows that the missing piece is broader than a parser.
The codebase already has two evidence stores:

- `CalculationObservationRepository` stores normalized filed casilla observations
  used by previous-filing and relation prefills.
- `FiledDeclarationObservationStore` stores live AEAT filed-declaration evidence
  and artefacts captured through the Sede adapter.

Neither store currently represents an AEAT-side account state that is not itself
a filed declaration. The wallet is exactly that: an external state observation
with its own capture time, authenticated identity, breakdown rows, and source
locator. It must not be flattened into a synthetic previous filing because that
would erase why the value is authoritative and make divergence impossible to
review.

The behavioral model should therefore be:

- Wallet observation: external AEAT state captured read-only from the Sede.
- Local recurrence: internal reconstruction from filed Modelo 303 observations.
- Taxpayer override: explicit operator-entered value with reason and evidence.
- Reconciliation decision: deterministic record choosing the effective binding
  value for `modelo-303-compensacion-pendiente-anteriores`.

The effective binding value must be derived from a persisted reconciliation
decision, not by whichever prefill source happens to run last.

The missing implementation pieces are a dedicated read-only wallet driver,
observation schema, evidence persistence, and reconciliation layer:

- Add external constants for `www1` path `/wlpl/DAI3-RUTI/CarteraCuotas`.
- Add a Sede adapter such as `fetch_iva_compensation_wallet`.
- Model a strict `IvaCompensationWalletObservation` with balance rows keyed by
  generation exercise and period, original/generated amount, applied amount,
  pending amount, captured timestamp, authenticated identity, and raw evidence
  locator.
- Persist wallet observations as calculation evidence, with provenance distinct
  from filed-declaration observations.
- Resolve Modelo 303 binding `modelo-303-compensacion-pendiente-anteriores`
  from a reconciliation decision whose authority ladder is wallet first,
  explicit taxpayer override second, and local reconstruction third.
- Reconcile wallet-derived total against locally reconstructed chain and fail
  closed, or at least warn/block automatic filing output, on material mismatch.

Divergence scenarios must be explicit:

- Wallet and local recurrence match: use wallet as primary evidence and retain
  recurrence as corroboration.
- Wallet is higher than local recurrence: block automatic output until missing
  prior filings, rectifications, administrative adjustments, or stale local
  evidence are reviewed.
- Wallet is lower than local recurrence: block automatic output until refunds,
  prior applications, expired balances, rectifications, or AEAT-side adjustments
  are reviewed.
- Wallet is stale or cannot be fetched: allow lower-confidence local recurrence
  only with a visible provenance warning.
- Taxpayer overrides casilla `110`: require explicit reason and evidence, then
  retain wallet and recurrence values as reconciliation context.

The reconciliation decision should be stored separately from raw evidence so
state remains explainable:

- Raw wallet evidence remains immutable for audit.
- Local recurrence remains reproducible from filed observations.
- Override remains an explicit taxpayer assertion.
- The effective binding decision records selected authority, selected amount,
  compared amounts, divergence class, blocking status, reason, and timestamps.

This prevents the calculation engine from silently mutating internal state when
new AEAT evidence arrives. A new wallet pull creates new evidence and a new
reconciliation decision; it does not rewrite past calculations.

## Source Notes

Official AEAT sources checked:

- `https://sede.agenciatributaria.gob.es/Sede/tramitacion/G414.shtml`
- `https://sede.agenciatributaria.gob.es/Sede/iva/pre-303/que-servicios-funcionalidades-tiene-nuevo-pre303.html`
- `https://sede.agenciatributaria.gob.es/Sede/iva/pre-303/preguntas-frecuentes/cuestiones-generales-sobre-servicio-pre303_.html`
- `https://sede.agenciatributaria.gob.es/Sede/iva/pre-303/preguntas-frecuentes/cuestiones-especificas-sobre-servicio-pre303_.html`
- `https://sede.agenciatributaria.gob.es/Sede/notas-prensa/notas-prensa/2021/febrero/12/comienza-segunda-fase-borrador-iva-contribuyentes.html`
- `https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/iva/modelo-303-iva-autoliquidacion_/instrucciones-2025.html`
- `https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G417.shtml`
- `https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/otros-servicios-ayuda-tecnica/consulta-declaraciones-presentadas.html`

## Follow-up Backlog

The non-IVA relation-contract failures discovered during the previous verification
pass are now explicitly slated for a separate review/fix pass:

- Modelo 130 same-model previous-period relation contract failure.
- Modelo 130 formula-bearing revision relation-consumption failure.
- Modelo 130 edge-year observation-copy aggregation failure.

These should not be folded into the IVA wallet work because their source model,
legal grounding, and regression surface differ from the Modelo 303/390 IVA
compensation chain.

They are now tracked by the dedicated Modelo 130 relation-regression research,
ADR, and plan. The relationship is implementation-level: both Modelo 303 IVA
and Modelo 130 IRPF depend on previous-period evidence being resolved into a
current-period binding, but the AEAT-held IVA wallet is not the authority for
Modelo 130.
