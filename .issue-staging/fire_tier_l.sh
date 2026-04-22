#!/usr/bin/env bash
set -euo pipefail

# Per-modelo Tier-L data
declare -A SCOPE
declare -A CURRENT

SCOPE[100]='Modelo 100 — IRPF anual (RENTA). Within THIS issue the scope is the **summary block** (27 casillas) already wired into the ruleset. The full multi-anexo RENTA deep-dive is deferred to the RENTA hardening umbrella (separate issue).'
CURRENT[100]='Ruleset exists for summary 2025 only (`modelo_100_summary_2025.py`, 12 computed casillas). Declaración extractor exists with summary MVP. No 2024 / 2026 rulesets. No integration test in `test_kent_workflows.py`. L1 anchor directory empty.'

SCOPE[111]='Modelo 111 — IRPF retenciones sobre rendimientos del trabajo y actividades económicas (trimestral). All liquidación casillas (21 printed, 9 currently modelled).'
CURRENT[111]='Ruleset exists for 2024 + 2025 (`modelo_111_2024.py`, `modelo_111_2025.py`). Extractor MVP (21 casillas, all liquidación; per-perceptor detail is in Modelo 190). No 2026 ruleset. No integration test.'

SCOPE[115]='Modelo 115 — retenciones sobre rendimientos de capital inmobiliario (alquileres, trimestral). 6 casillas.'
CURRENT[115]='Ruleset exists for 2024 + 2025 (`modelo_115_2024.py`, `modelo_115_2025.py`). Extractor MVP (all 6 casillas). No 2026 ruleset. No integration test.'

SCOPE[123]='Modelo 123 — retenciones sobre rendimientos del capital mobiliario (trimestral). 11 casillas.'
CURRENT[123]='Ruleset exists for 2024 + 2025 (`modelo_123_2024.py`, `modelo_123_2025.py`). Extractor MVP (11 casillas). No 2026 ruleset. No integration test.'

SCOPE[130]='Modelo 130 — pago fraccionado IRPF para autónomos en estimación directa (trimestral). All 19 casillas (9 computed, 10 user-supplied).'
CURRENT[130]='Ruleset exists for 2024 + 2025. Declaración extractor FULL (7 casillas liquidación). Integration test `test_kent_workflows.py::TestKentImportsModelo130Declaracion` wired (3 cases). **This modelo is the reference implementation** — gaps: no 2026 ruleset, no L1 anchor, no rule-delta manifest.'

SCOPE[131]='Modelo 131 — pago fraccionado IRPF para autónomos en estimación objetiva (módulos, trimestral). 15 casillas.'
CURRENT[131]='Ruleset exists for 2024 + 2025. Extractor MVP (15 casillas). No 2026 ruleset. No integration test. Módulos rates change per annum (Orden HFP anual) — year-specific rates are critical.'

SCOPE[180]='Modelo 180 — resumen anual de retenciones por rendimientos del capital inmobiliario (anual). 4 resumen casillas.'
CURRENT[180]='Ruleset exists for 2024 + 2025. Extractor MVP (4 summary totals; per-arrendador detail deferred — borderline Tier-S but classified L because resumen casillas are computed). No 2026 ruleset. No integration test.'

SCOPE[200]='Modelo 200 — Impuesto sobre Sociedades (anual). **In-scope: liquidación block of page 14 (16 casillas).** The full form has ~2000 casillas spread over multiple anexos — the complete-form coverage is out of scope for this issue and should be filed separately if needed.'
CURRENT[200]='Ruleset exists for 2024 only (`modelo_200_2024.py`). Extractor MVP page-14 only. No 2025 ruleset, no 2026 ruleset. No integration test. Ejercicio 2025 filings would return UNVERIFIABLE from the registry — this is a live gap.'

SCOPE[202]='Modelo 202 — Impuesto sobre Sociedades, pago fraccionado (trimestral). 9 casillas.'
CURRENT[202]='Ruleset exists for 2025 only (`modelo_202_2025.py`). Extractor MVP (9 casillas). No 2024 ruleset, no 2026 ruleset. No integration test.'

SCOPE[303]='Modelo 303 — IVA autoliquidación (trimestral). All 33 printed casillas in the declaración block.'
CURRENT[303]='Ruleset exists for 2024 + 2025. Declaración extractor FULL (33 casillas). Extraction round-trip test exists but **NO integration test in `test_kent_workflows.py`** for the CLI verify path. No 2026 ruleset. No L1 anchor. Tier-L reference implementation alongside 130 — expected to be the most complete after this issue closes. **IVA complexity deep-dive is the IVA umbrella issue — this issue covers the formula-ruleset and extractor completeness only.**'

SCOPE[390]='Modelo 390 — IVA resumen anual (anual). **In-scope: resultado / resumen block (15 casillas currently extracted).** The full form has ~680 casillas — subset coverage must be documented in the rule-delta manifest.'
CURRENT[390]='Ruleset exists for 2025 only (`modelo_390_2025.py`). Extractor MVP (resultado subset). No 2024 ruleset, no 2026 ruleset. No integration test.'

for MODELO in 100 111 115 123 130 131 180 200 202 303 390; do
  BODY_FILE=".issue-staging/tier_l_${MODELO}.md"
  sed -e "s|{MODELO}|${MODELO}|g" \
      -e "s|{SCOPE}|${SCOPE[$MODELO]}|g" \
      -e "s|{CURRENT_STATE}|${CURRENT[$MODELO]}|g" \
      .issue-staging/_tier_l_template.md > "${BODY_FILE}"
  printf "\n---\n\n**Parent EPIC:** #316\n" >> "${BODY_FILE}"
  printf "\n**Labels:** \`type:feature\`, \`area:submission\`, \`health:coverage\`, \`priority:P2-medium\`, \`effort:L\`, \`parallel-safe\`, \`kent-journey\`\n" >> "${BODY_FILE}"

  TITLE="Kent can calc-verify-roundtrip Modelo ${MODELO} for 2024/2025/2026 (Tier-L)"
  URL=$(gh issue create \
    --title "${TITLE}" \
    --body-file "${BODY_FILE}" \
    --label "type:feature" \
    --label "area:submission" \
    --label "health:coverage" \
    --label "priority:P2-medium" \
    --label "effort:L" \
    --label "parallel-safe" \
    --label "kent-journey")
  echo "modelo ${MODELO} → ${URL}"
done
