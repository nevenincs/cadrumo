---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:97d7bdea260e6144bfe7ca9c832f93da656b4f0fb1ccd6ab80a9242d042923e1'
step_id: 'S251'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Resolve Cataluna 2024 autonomic tariff discrepancy

## Scope

- `reviewer reconstruction gives 4522.78 EUR for base 35400 but S115/S249 oracle values use 4650.03`
- `either the bracket table is wrong in S115 or there is a complementary tariff source from Orden HAC 2024 Cataluña not yet ingested`
- `ground against AEAT oracle replay before adjusting`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/`

## Description

- Re-ran vault and code discovery for the FU-S115-CAT discrepancy.
- Checked the live AEAT Renta 2024 manual page for Comunidad Autonoma de Cataluna:
  `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2024/c15-calculo-impuesto-determinacion-cuotas-integras/gravamen-base-liquidable-general/gravamen-autonomico/comunidad-autonoma-cataluna.html`.
- Compared the official 2024 Cataluna autonomic scale with
  `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/parameters/0009-renta-2024-escala-autonomica-cataluna-base-general.toml`.
- Verified the focused real-behaviour regression
  `src/aeat/domain/calculations/registry/tests/test_modelo_100_tarifa_real.py::test_m100_2024_cuota_integra_autonomica_cataluna_matches_lirpf_tables`.

## Outcome

No code change was required. The current Modelo 100 2024 Cataluna bracket table
matches AEAT's published Renta 2024 manual and the bundled extracted manual
corpus.

The disputed base 35,400 EUR value is:

- official bracket floor: 33,007.20 EUR;
- official fixed addition at that floor: 4,200.18 EUR;
- excess base: 2,392.80 EUR;
- official marginal rate: 18.80%;
- excess cuota: 449.85 EUR after money rounding;
- tariff result: 4,200.18 + 449.85 = 4,650.03 EUR.

Therefore the S115/S249 oracle value 4,650.03 EUR is correct. The older
4,522.78 EUR reviewer reconstruction is the stale wrong edge. S251 is closed as
grounded, not implemented.

Verification:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/tests/test_modelo_100_tarifa_real.py::test_m100_2024_cuota_integra_autonomica_cataluna_matches_lirpf_tables`
  passed: 1 test.

## Notes

No fallback, re-export, or alternate source path was introduced. The registry
continues to source the scale from the AEAT Renta 2024 manual authority already
declared on the parameter.
