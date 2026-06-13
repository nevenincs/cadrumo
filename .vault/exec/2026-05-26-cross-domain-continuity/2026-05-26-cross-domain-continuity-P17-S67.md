---
step_id: S67
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-P17-S66]]"
---

# cross-domain-continuity P17.S67 — External oracle values backfill

## Oracle citations

### Modelo 200 — cuota-integra micro-empresa 2024

Source: AEAT Manual Practico de Sociedades 2024, Capitulo III, "Tipo de
gravamen reducido para empresas de reducida dimension", section "Entidades
de reducida dimension - Articulo 29 LIS".

Authority: Ley 27/2014 Art. 29 (BOE-A-2014-12328) as in force for
ejercicios iniciados en 2024.

Inputs:
- Base imponible: 100.000,00 EUR
- SL, no new-entity override, INCN < 1.000.000 EUR (micro-empresa lane)
- Tipo gravamen pyme 2024: 23 % flat (pre-2025 regime)

Expected: cuota integra (DP200014:00562) = 23.000,00 EUR

---

### Modelo 202 — Art. 40.2 cuota

Source: AEAT Declaracion 202 Instrucciones (DR 202, Agencia Tributaria
2025), Clave [03] "Base del pago fraccionado (modalidad articulo 40.2
LIS), porcentaje del 18 %".

Authority: Ley 27/2014 Art. 40.2 (BOE-A-2014-12328):
"el pago fraccionado consistira en el 18 por ciento de la cuota integra
del ultimo periodo impositivo cuyo plazo de declaracion estuviese vencido".

Inputs:
- Clave [01] (base): 10.000,00 EUR
- Clave [02] (pagos fraccionados anteriores): 0,00 EUR
- INCN: 500.000 EUR (below 6M threshold; Art. 40.2 lane)

Expected: casilla 03 = 18 % x 10.000 - 0 = 1.800,00 EUR

---

### Modelo 130 — resultado apartado I (estimacion directa)

Source: AEAT DR 130 Instrucciones (Orden EHA/672/2007 y sucesivas),
Casilla 07 "Resultado parcial del apartado I".

Authority: Ley 35/2006 Art. 99; RD 439/2007 Art. 110.
AEAT DR 130 Instrucciones: Casilla 04 "20 por 100 del importe de la
casilla 03 cuando este sea positivo, y cero en caso contrario".

Inputs:
- Casilla 01 (ingresos): 12.000,00 EUR
- Casilla 02 (gastos): 4.000,00 EUR
- Casilla 05 (pagos anteriores): 0,00 EUR
- Casilla 06 (retenciones): 0,00 EUR
- Prior-year economic activity net income: 13.000 EUR (above 12.000
  threshold -> minoracion casilla 13 = 0)

Formula chain:
- 03 = 01 - 02 = 12.000 - 4.000 = 8.000
- 04 = max(0, 20 % x 03) = 1.600
- 07 = 04 - 05 - 06 = 1.600 - 0 - 0 = 1.600

Expected: casilla 07 = 1.600,00 EUR

---

### Modelo 303 and Modelo 100 — structural surface tests only

Numeric oracle for M303 requires ledger-sourced IVA devengado and
deducible bindings (full transaction ingestion pipeline; out of scope).

Numeric oracle for M100 requires full escala general and autonomica
tables applied to base liquidable general and del ahorro (exercised in
registry-level IRPF escala tests).

Both are tested structurally: no traceback, well-formed JSON, key
casillas present in output.
