---
tags:
  - '#exec'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-05-01-corpus-data-hydration-plan]]"
---

# `corpus-data-hydration` phase-1 task-3: Modelo 100 (IRPF Anual)

Manual semantic extraction and hydration of Modelo 100 (IRPF Anual) for the period 2023-2025.

## Sourcing
Official AEAT documentation sourced:
- URL: `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025.html`

## Casilla Semantic Mapping (Critical MVP Set)

| Casilla | Label (ES) | Help (ES) |
| :--- | :--- | :--- |
| 0001 | Retribuciones en dinero | Importe íntegro de las retribuciones dinerarias del trabajo. |
| 0003 | Retenciones (Trabajo) | Retenciones e ingresos a cuenta por rendimientos del trabajo. |
| 0435 | Base imponible general | Suma de los rendimientos y ganancias que integran la base general. |
| 0460 | Base imponible del ahorro | Suma de los rendimientos y ganancias que integran la base del ahorro. |
| 0500 | Base liquidable general | Resultado de aplicar las reducciones a la base imponible general. |
| 0550 | Cuota íntegra estatal | Gravamen estatal sobre la base liquidable general y del ahorro. |
| 0611 | Cuota líquida estatal | Diferencia entre la cuota íntegra y las deducciones estatales. |
| 0612 | Cuota líquida autonómica | Diferencia entre la cuota íntegra y las deducciones autonómicas. |
| 0670 | Cuota resultante de la autoliquidación | Resultado final antes de pagos a cuenta. |

## Tasks
- [ ] Update `corpus/casillas/modelo_100/*.json` for 2023-2026.
- [ ] Hydrate at least the top 50 critical casillas for calculation verification.
