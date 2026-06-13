---
tags: ['#research', '#live-iva-compensation-wallet']
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-02-live-iva-persistent-failure-team-brief-audit]]'
---

# `live-iva-compensation-wallet` research: `AEAT IVA compensation consultation`

This research re-grounds the failed live IVA feature around the required
product outcome: read-only AEAT consultation for the authenticated declarante's
IVA compensation state, without filing or mutating AEAT state.

## Findings

1. AEAT exposes "Consulta de la cartera de cuotas de IVA a compensar" as an
   IVA / Modelo 303 management action. Therefore the driver must not treat the
   cartera as speculative; it is an official consultation target.

2. AEAT's Pre303 FAQ states that the contributor can access the cartera from
   casilla 110 of Modelo 303, and that the cartera contains available
   compensation information for the contributor. It identifies casilla 110 as
   pending quotas from previous periods, casilla 78 as previous-period quotas
   applied in the current self-assessment period, and casilla 87 as previous
   quotas pending for later periods.

3. The same AEAT Pre303 FAQ says the cartera provides a breakdown table showing
   generation exercises/periods, applied amounts, and pending amounts. This
   confirms the required live evidence is a read-only consultation/extraction
   target, not a filing workflow.

4. AEAT's Modelo 303 instructions separately describe casillas 110, 78, and 87.
   They confirm the compensation-state fields needed by local Modelo 303
   grounding and reconciliation.

5. AEAT help for "Consulta de declaraciones presentadas" remains relevant
   because Modelo 303 declarations with certain outcomes may not appear in "Mis
   expedientes"; declaration-query extraction must be implemented as a
   first-class read-only consultation path. It is not sufficient by itself until
   it yields multiyear compensation-relevant extracted state.

6. Implementation implication: the live driver should not rely only on a
   hardcoded direct wallet URL. It must first use authenticated Pre303/Modelo
   pages to discover the official cartera entrypoint, and fall back to the
   configured route only when the authenticated page does not expose one. Any
   discovered URL must be constrained to the centralized AEAT wallet path and
   allowed AEAT hosts.

## Official Sources

- AEAT Pre303 FAQ, "Cuestiones específicas sobre el servicio Pre303":
  `https://sede.agenciatributaria.gob.es/Sede/iva/pre-303/preguntas-frecuentes/cuestiones-especificas-sobre-servicio-pre303_.html`
- AEAT Modelo 303 instructions 2025:
  `https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/iva/modelo-303-iva-autoliquidacion_/instrucciones-2025.html`
- AEAT IVA management actions page:
  `https://sede.agenciatributaria.gob.es/Sede/iva/gestiones-iva.html`
- AEAT declaration-query help:
  `https://sede.agenciatributaria.gob.es/Sede/eu_es/ayuda/consultas-informaticas/otros-servicios-ayuda-tecnica/consulta-declaraciones-presentadas.html`

