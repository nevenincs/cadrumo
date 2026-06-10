---
tags:
  - '#exec'
  - '#cli-ledger-testimonials'
date: '2026-06-10'
step_id: P05.S14
related:
  - '[[2026-06-03-cli-ledger-testimonials-plan]]'
  - '[[2026-06-09-cli-ledger-testimonials-audit]]'
---

# `cli-ledger-testimonials` `P05.S14` step record

## Step

P05.S14 — Land independent-review findings for commit 4deddd89f (M131 under-declaration advisory): correct legal attribution in TOML comments and test docstring; align C02 label to registry label; add locale keys for advisory finding messages (locale keys blocked by peer WIP).

## Execution

### Finding (1) — Legal attribution precision (MEDIUM)

**Root cause read from corpus.** Art. 110.1.b RD 439/2007 (corpus `rd-439-2007.json#art-110`) states: "el 4 por ciento de los rendimientos netos resultantes de la aplicación de dicho método en función de los datos-base del primer día del año". It establishes the datos-base determination obligation with 4 por ciento as the headline rate — not the 4/3/2% personal-asalariado scale. The scale comes from the official M131 instructions (corpus `aeat_official/instructions/modelo_131/files/modelo-131-instrucciones.html`, Casilla 02 section, the table keyed on personal asalariado). Art. 110.4 grants operators the right to apply higher percentages; the instructions derive "no se permiten porcentajes inferiores" from that provision.

**Fix applied to all four TOML files** (`2019-2023`, `2024`, `2025`, `2026`):

- Removed the incorrect claim that art. 110.1.b establishes the 4/3/2 por 100 scale and the floor constraint.
- Replaced with a structured "Legal attribution" section naming: art. 110.1.b (datos-base determination with 4% headline), M131 instructions / aeat-modelo-131-instructions (the percentage scale), art. 110.4 (higher-percentage permission and floor constraint).
- `legal_refs = ["rd-439-2007:art-110"]` left unchanged — the catalogue entry covers the full article.

### Finding (3) — Label drift (LOW)

**Fix applied to all four TOML files and test docstring:**

- C02 renamed from "Pago fraccionado del trimestre por datos-base" to the registry label "Pago fraccionado previo por datos-base" (confirmed from `revisions/2025/casillas/0001-casillas.toml`, line 16: `label = "Pago fraccionado previo por datos-base"`).

### Test docstring fix

Section header `(RD 439/2007 art. 110.1.b)` removed from the test block heading; C02 label corrected; the non-tautology rationale updated to name the M131-instructions scale minimum (2 por 100 > 0) as the derivation source rather than the incorrectly cited art. 110.1.b minimum-rate rule.

### Finding (2) — Missing locale keys (MEDIUM) — BLOCKED

The locale keys for the M131 and M200 advisory finding messages require adding entries to `src/aeat/locales/{es,en,ca,hu}.yml`. Those files carry peer-agent WIP at the time of this Step (all four `.yml` files listed as `M` in `git status --short`). The WIP fence rule prohibits editing files carrying non-authored modifications. This finding is deferred pending locale file clearance.

**Locale keys to add when the peer WIP is cleared:**

For M131 (four per-revision keys; `tr()` constructs these via `f"application.modelo.findings.{predicate_id.replace('-', '_')}"`):
- `application.modelo.findings.modelo_131_2019_2023_pago_fraccionado_determinado_cuando_rendimientos_positivos`
- `application.modelo.findings.modelo_131_2024_pago_fraccionado_determinado_cuando_rendimientos_positivos`
- `application.modelo.findings.modelo_131_2025_pago_fraccionado_determinado_cuando_rendimientos_positivos`
- `application.modelo.findings.modelo_131_2026_pago_fraccionado_determinado_cuando_rendimientos_positivos`

For M200:
- `application.modelo.findings.modelo_200_base_imponible_determinada_cuando_resultado_positivo`

Suggested wording (to be verified against the live predicate meaning):

| locale | M131 key | M200 key |
| ------ | -------- | -------- |
| es | Los rendimientos netos de actividades en datos-base (C01) son positivos pero el pago fraccionado previo por datos-base (C02) es cero; revise la casilla 02 con el porcentaje de la Orden de módulos (mínimo 2 por 100). | El resultado contable es positivo pero la base imponible (C552) es cero; revise la determinación de la base imponible. |
| en | Net income from datos-base activities (C01) is positive but the fractional payment for datos-base (C02) is zero; check casilla 02 using the applicable Orden de módulos rate (minimum 2 per cent). | The accounting result is positive but the taxable base (C552) is zero; review the taxable base determination. |
| ca | Els rendiments nets d'activitats en dades-base (C01) són positius però el pagament fraccionat previ per dades-base (C02) és zero; reviseu la casella 02 amb el percentatge de l'Ordre de mòduls (mínim 2 per cent). | El resultat comptable és positiu però la base imposable (C552) és zero; reviseu la determinació de la base imposable. |
| hu | Az adatbázis-tevékenységek nettó jövedelme (C01) pozitív, de az adatbázis-részletfizetés (C02) nulla; ellenőrizze a 02. rubrikát a vonatkozó százalékkal (minimum 2 százalék). | A számviteli eredmény pozitív, de az adóalap (C552) nulla; ellenőrizze az adóalap meghatározását. |

## Verification

Gates run and all passing:

- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_verification_substance.py -q` — **52 passed**
- `uv run --no-sync pytest src/aeat/application/registry/tests/test_corpus.py -q` — **19 passed**
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_catalogue_verification.py -q` — **35 passed**

TOML parses cleanly (all four registry revisions load without error — confirmed by the 52 substance tests which load the registry authority).

## Commit

`b9226c586` — `docs(modelo-131): correct legal attribution and label in M131 advisory comments`

Files committed (explicit pathspecs):
- `src/aeat/_data/registry/aeat/modelos/131/revisions/2019-2023/verification_expectations/0002-verification_predicates.toml`
- `src/aeat/_data/registry/aeat/modelos/131/revisions/2024/verification_expectations/0002-verification_predicates.toml`
- `src/aeat/_data/registry/aeat/modelos/131/revisions/2025/verification_expectations/0002-verification_predicates.toml`
- `src/aeat/_data/registry/aeat/modelos/131/revisions/2026/verification_expectations/0002-verification_predicates.toml`
- `src/aeat/application/modelo/tests/test_verification_substance.py`

Locale commit: deferred (peer WIP on locale files).
