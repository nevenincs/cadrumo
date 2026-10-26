---
tags:
  - '#research'
  - '#iva-workflow'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:17af6723f7c054a3b4222399cfa4cce37c4b70e91f133709c28043d9dc9f9926'
related: []
---

# `iva-workflow` research: `IVA settlement wallet and export identity`

Two findings the IVA work depends on (researched 2026-09-21 and 2026-09-22): what AEAT's carry-forward wallet actually is and how it is reached, and why the official Modelo 303 export cannot be produced without two developer-supplied header values.

## Findings

### The wallet is carry-forward credit, not a tax account

AEAT offers the "Cartera de cuotas a compensar" inside Pre303 and as a standalone consultation. It shows carry-forward credit by origin year and period and relates it to Modelo 303 casillas 110, 78 and 87. It is not the taxpayer's full record of debts, payments and refunds, and it is not an SII invoice book. The product's row schema records available balance per origin period; `generated_amount` and `applied_amount` may be absent and must not be inferred from `pending_amount`, and one snapshot does not give movement history. A snapshot's capture time and its origin periods are separate coordinates.

### Authentication routes are distinct providers

AEAT's Cl@ve Móvil routes include QR and non-QR DNI/NIE with contrast data. The NIE support number is contrast data; the taxpayer still approves the request in the app, with an SMS alternative. Cl@ve Permanente is a separate provider, not another name for Móvil. Having the identity inputs is not an authenticated session.

### The official Modelo 303 export needs two developer values

The 2025 Modelo 303 record design (DP30300) requires "Versión del Programa" (positions 93–96, exactly four characters) and "NIF del desarrollador" (positions 101–109, a valid nine-character Spanish NIF). Note 1 of the design says the development entity completes these fields; AEAT does not assign them. They identify the software's developer, not the taxpayer or the presenter. As of 2026-09-22 Cadrumo had no approved values, and commit `a27d7962e3` makes the official export refuse with `REFUSED_MODELO_EXPORT_PRODUCT_IDENTITY_UNAVAILABLE`, naming both fields and their positions. The refusal can only be lifted by genuine reviewed values with provenance, or by official evidence of a valid export path without them.

## Sources

- https://sede.agenciatributaria.gob.es/Sede/iva/pre-303/preguntas-frecuentes/cuestiones-especificas-sobre-servicio-pre303_.html
- https://sede.agenciatributaria.gob.es/Sede/iva/regimenes-tributacion-iva/gestiones.html
- https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/iva/modelo-303-iva-autoliquidacion_/instrucciones-2026.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/firma-digital-sistema-clave-pin-tecnica/obtencion-clave-pin.html
- https://clave.gob.es/clave-permanente/como-funciona
- https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/ejercicios-anteriores-modelos-300-399.html (2025 Modelo 303 DP30300 workbook, Note 1)
- commit `a27d7962e3`
