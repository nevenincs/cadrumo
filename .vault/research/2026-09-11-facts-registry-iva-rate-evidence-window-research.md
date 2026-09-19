---
tags:
  - '#research'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:1b481076620e7a55135c93b34f60f6d9109d0e3536b849c935faabe36478e743'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` research: `iva-rate-evidence-window`

The enforced source-window invariant exposed no M347 or Article 161 defect. It exposed 53 IVA schedule citations that were newer guidance than the variants they supported. The current `0062-iva-rate-schedule.toml` edit removes only those inapplicable citations, which is consistent with strict temporal evidence rather than a date relaxation. The remaining question is whether filing-grade foreign VAT rates require a national-law evidence package beyond the present guidance-backed corpus.

## Findings

### m347-and-recargo-have-exact-temporal-grounding

The two M347 facts begin on 2008-01-01, the same date as their BOE source and legal reference. The bundled excerpt at `src/cadrumo/_data/registry/aeat/legal/iva-rates.toml:33-119` and `src/cadrumo/_data/corpus/normatives/html/rd-1065-2007.html:3265` supports the statutory thresholds. The historic Article 161 recargo variants align with source windows beginning 1993-01-01, 1997-01-01, and 2012-09-01. The 2012 effect date is corroborated by https://www.boe.es/eli/es/rdl/2012/07/13/20 and is already covered by `2026-09-10-facts-registry-s72-effect-date-repair-review-audit.md`.

### iva-guidance-citations-must-not-extend-applicability

The prior 53 violations were all `iva-rate-schedule` variants in `src/cadrumo/_data/registry/aeat/facts/0062-iva-rate-schedule.toml`. Forty-nine cited `eu-your-europe-iva-rates-2026-07-13` before its 2026-07-13 applicability date; four January 2025 variants cited `eu-eprs-iva-rates-2025-07-01` before 2025-07-01. The current authored edit removes those citations while retaining sources that cover the historical variants. Two future variants beginning 2026-07-13 retain the former source and remain temporally conformant. Narrowing legally applicable fact windows would make the authority less true; a non-applicability evidence lane would conceal unsupported values.

### filing-grade-foreign-rate-evidence-remains-a-separate-decision

Current generic EU guidance is classified as `official_source_guidance` and pending review. The European Commission explains that Member States set VAT rate levels at https://taxation-customs.ec.europa.eu/taxation/vat/vat-directive/vat-rates_en. A future evidence-authoring package can capture pinned national tax-authority or statutory sources per state and rate change, with exact effect windows, then remove generic guidance as operative rate evidence. This research does not determine whether that stronger standard is required for the current filing-grade authority.

## Sources

- `dev/registry/compiler/fact_validation.py:64`
- `src/cadrumo/_data/registry/aeat/facts/0062-iva-rate-schedule.toml`
- `src/cadrumo/_data/registry/aeat/legal/iva-rates.toml:33`
- `src/cadrumo/_data/corpus/normatives/html/rd-1065-2007.html:3265`
- `2026-09-10-facts-registry-s72-effect-date-repair-review-audit.md`
- https://www.boe.es/eli/es/rdl/2012/07/13/20
- https://www.boe.es/eli/es/rd/2007/07/27/1065/con/20081227
- https://taxation-customs.ec.europa.eu/taxation/vat/vat-directive/vat-rates_en
