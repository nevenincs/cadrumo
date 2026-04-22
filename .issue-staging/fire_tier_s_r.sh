#!/usr/bin/env bash
set -euo pipefail

# ==== Tier-S (Summary) ====
declare -A S_SCOPE
declare -A S_CURRENT

S_SCOPE[190]='Modelo 190 — resumen anual de retenciones IRPF sobre rendimientos del trabajo y actividades económicas (anual). Per-perceptor record lines + resumen totals.'
S_CURRENT[190]='Declaración extractor MVP (21 summary casillas only, no per-perceptor extraction). No ruleset. No integration test.'

S_SCOPE[193]='Modelo 193 — resumen anual de retenciones IRPF sobre rendimientos del capital mobiliario (anual). Per-perceptor record lines + 3 resumen casillas.'
S_CURRENT[193]='Declaración extractor MVP (3 summary casillas only). No ruleset. No integration test.'

S_SCOPE[347]='Modelo 347 — declaración anual de operaciones con terceros (>3005,06 € umbral). Per-declarado record lines + resumen totals.'
S_CURRENT[347]='Declaración extractor MVP (4 summary casillas only; no per-declarado extraction). No ruleset. No integration test. Umbral cambió históricamente — rule-delta manifest critical.'

S_SCOPE[349]='Modelo 349 — declaración recapitulativa de operaciones intracomunitarias (mensual / trimestral). Per-operador record lines with ClaveOperacion enum + resumen totals.'
S_CURRENT[349]='Declaración extractor MVP (4 summary casillas only). No ruleset. No integration test. Crítico para integración con Modelo 303 (IVA intracomunitario).'

for MODELO in 190 193 347 349; do
  BODY_FILE=".issue-staging/tier_s_${MODELO}.md"
  sed -e "s|{MODELO}|${MODELO}|g" \
      -e "s|{Modelo}|Modelo${MODELO}|g" \
      -e "s|{SCOPE}|${S_SCOPE[$MODELO]}|g" \
      -e "s|{CURRENT_STATE}|${S_CURRENT[$MODELO]}|g" \
      .issue-staging/_tier_s_template.md > "${BODY_FILE}"
  printf "\n---\n\n**Parent EPIC:** #316\n" >> "${BODY_FILE}"

  TITLE="Kent can extract + verify-totals Modelo ${MODELO} for 2024/2025/2026 (Tier-S summary return)"
  URL=$(gh issue create \
    --title "${TITLE}" \
    --body-file "${BODY_FILE}" \
    --label "type:feature" \
    --label "area:submission" \
    --label "health:coverage" \
    --label "priority:P2-medium" \
    --label "effort:M" \
    --label "parallel-safe" \
    --label "kent-journey")
  echo "tier-s modelo ${MODELO} → ${URL}"
done

# ==== Tier-R (Registration) ====
declare -A R_SCOPE
declare -A R_CURRENT

R_SCOPE[036]='Modelo 036 — declaración censal de alta, modificación o baja (IAE, IVA, IRPF regímenes). Named fields: causa, epígrafe IAE, regímenes.'
R_CURRENT[036]='Declaración extractor MVP (5 named fields). No L2 fixture — regex patterns are best-effort. No integration test. Critical for Kent autónomo onboarding.'

R_SCOPE[037]='Modelo 037 — declaración censal simplificada (subset de 036 para autónomos sin empleados sin módulos especiales). Same named-field shape as 036.'
R_CURRENT[037]='Declaración extractor MVP (5 named fields, mirror of 036). No L2 fixture. No integration test. No synthetic generator (audit flagged as the only modelo without round-trip test).'

R_SCOPE[232]='Modelo 232 — operaciones vinculadas + operaciones con paraísos fiscales (anual). Named-field summary counts per bloque.'
R_CURRENT[232]='Declaración extractor MVP (3 named fields). **Patterns explicitly speculative per `modelo_232_v2025.py:41`** — no real L2 fixture. No ruleset. No integration test.'

R_SCOPE[369]='Modelo 369 — régimen especial ventanilla única IOSS / OSS (IVA e-commerce intracomunitario). Named-field resumen totals.'
R_CURRENT[369]='Declaración extractor MVP (3 named fields). Patterns speculative without L2 fixture. No ruleset. No integration test.'

R_SCOPE[720]='Modelo 720 — declaración de bienes y derechos situados en el extranjero (anual). Named-field counts per bloque (cuentas / valores / inmuebles).'
R_CURRENT[720]='Declaración extractor MVP (3 named fields). **Patterns explicitly speculative per `modelo_720_v2025.py:38`** — no real L2 fixture. No ruleset. No integration test. Penalización por no declarar fue declarada contraria al Derecho UE — contexto legal volátil.'

R_SCOPE[840]='Modelo 840 — declaración IAE (información censal del impuesto sobre actividades económicas, anual). Text-value casillas (8 campos de texto).'
R_CURRENT[840]='Declaración extractor with text-value MVP (8 text casillas). No L2 fixture. No ruleset (text payloads — no formula-verification possible). No integration test.'

for MODELO in 036 037 232 369 720 840; do
  BODY_FILE=".issue-staging/tier_r_${MODELO}.md"
  sed -e "s|{MODELO}|${MODELO}|g" \
      -e "s|{Modelo}|Modelo${MODELO}|g" \
      -e "s|{SCOPE}|${R_SCOPE[$MODELO]}|g" \
      -e "s|{CURRENT_STATE}|${R_CURRENT[$MODELO]}|g" \
      .issue-staging/_tier_r_template.md > "${BODY_FILE}"
  printf "\n---\n\n**Parent EPIC:** #316\n" >> "${BODY_FILE}"

  TITLE="Kent can extract Modelo ${MODELO} named fields against real L2 PDF (Tier-R registration)"
  URL=$(gh issue create \
    --title "${TITLE}" \
    --body-file "${BODY_FILE}" \
    --label "type:feature" \
    --label "area:submission" \
    --label "health:coverage" \
    --label "priority:P3-low" \
    --label "effort:S" \
    --label "parallel-safe" \
    --label "kent-journey")
  echo "tier-r modelo ${MODELO} → ${URL}"
done
