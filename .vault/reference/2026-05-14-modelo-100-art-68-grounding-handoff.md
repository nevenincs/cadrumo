---
tags:
  - '#reference'
  - '#legal-grounding-audit'
date: '2026-05-14'
related:
  - "[[2026-05-14-legal-grounding-audit-reference]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# Operator handoff: Modelo 100 art-68 deduction family grounding

Five draft legal entries prepared for operator review. The corpus
HTML files are already in place under `corpus/normatives/html/`
and contain verbatim excerpts from the BOE consolidated text of
Ley 35/2006 IRPF (version dated 2026-04-29). The legal entries are
prepared below but are NOT yet committed to
`registry/aeat/legal/irpf.toml` because the schema validator
mandates `review_status = "reviewed"` with a real operator signoff
in `reviewed_by`, and the operator (not the AI) is the authority
who can authorise that transition.

## Schema mandate

The `LegalReference` model at
`src/aeat/domain/calculations/registry/_schema.py:172` enforces
`review_status == "reviewed"` at model-validator time
(`_validate_legal_reference`, line 205-206). `provisional` and
`rejected` are parsed but always raise
`RegistryValidationError("legal reference {id!r} is not reviewed")`.

This is the project's safety contract: AI-prepared legal grounding
cannot land without the operator's explicit signoff. Every reviewed
entry carries `reviewed_by = "wgergely"` and a `reviewed_at` date.

## Draft entries (review and sign off, then paste into `registry/aeat/legal/irpf.toml` between art-68.4 and orden-hac-1264-2018:art-4)

The 5 entries are: art-68.1 (empresas nueva creación), art-68.2
(actividades económicas), art-68.3 (donativos), art-68.5 (Patrimonio
Histórico), and art-69 (límites de determinadas deducciones).

The `required_text` snippets are quoted verbatim from the corpus
HTML files; each can be cross-checked against the file or against
the BOE permalink before signoff.

### `ley-35-2006:art-68.1` — Deducción por inversión en empresas de nueva o reciente creación

Status: **in force** per BOE consolidated text. 50 per cent
deduction; maximum annual base 100,000 euros. Conditions in
sub-paragraphs 2.º and 3.º (3-12 year tenure, < 40 per cent capital
participation, etc.). Corpus excerpt:
`corpus/normatives/html/ley-35-2006-art-68-1.html`.

```toml
[legal."ley-35-2006:art-68.1"]
evidence_tier = "legal_authority"
authority = "boe"
kind = "ley"
corpus_ref = "corpus/normatives/html/ley-35-2006-art-68-1.html#articulo-68-1"
document_id = "BOE-A-2006-20764"
article = "68.1"
permalink = "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a68"
published_at = 2006-11-29
effective_from = 2007-01-01
review_status = "reviewed"
reviewed_at = <FILL>
reviewed_by = "wgergely"
notes = "Deduccion por inversion en empresas de nueva o reciente creacion. 50 per cent of amounts paid in the period for the subscription of shares or holdings in new or recent-creation enterprises, subject to the conditions set out in the sub-paragraphs 2 and 3, plus contribution of business or professional knowledge per the investment agreement. Maximum annual deduction base is 100,000 euros."
required_text = [
    "Deducción por inversión en empresas de nueva o reciente creación",
    "50 por ciento de las cantidades satisfechas",
    "La base máxima de deducción será de 100.000 euros anuales",
]
```

### `ley-35-2006:art-68.2` — Deducciones en actividades económicas

Status: **in force**. Cross-references Impuesto sobre Sociedades
incentivos with carve-outs for IS art. 39.2 + 39.3. Adds a
Modelo-100-specific 5 per cent (or 2.5 per cent) reinversión-de-
rendimientos-netos deduction tied to IS art. 101 thresholds. The
2.5 per cent rate applies when LIRPF art. 32.3 reducción was used
or to rentas Ceuta / Melilla under art. 68.4. Corpus excerpt:
`corpus/normatives/html/ley-35-2006-art-68-2.html`.

```toml
[legal."ley-35-2006:art-68.2"]
evidence_tier = "legal_authority"
authority = "boe"
kind = "ley"
corpus_ref = "corpus/normatives/html/ley-35-2006-art-68-2.html#articulo-68-2"
document_id = "BOE-A-2006-20764"
article = "68.2"
permalink = "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a68"
published_at = 2006-11-29
effective_from = 2007-01-01
review_status = "reviewed"
reviewed_at = <FILL>
reviewed_by = "wgergely"
notes = "Deducciones en actividades economicas. Cross-references the Impuesto sobre Sociedades incentives and inversion empresarial regime at equal percentages and limits, with carve-outs for the IS article 39 paragraphs 2 and 3. Adds a Modelo-100-specific 5 per cent (or 2.5 per cent) reinversion-of-net-business-income deduction for taxpayers meeting the Impuesto sobre Sociedades art. 101 requirements."
required_text = [
    "Deducciones en actividades económicas",
    "incentivos y estímulos a la inversión empresarial",
    "El porcentaje de deducción será del 5 por ciento",
    "2,5 por ciento cuando el contribuyente hubiera practicado la reducción",
]
```

### `ley-35-2006:art-68.3` — Deducciones por donativos y otras aportaciones

Status: **in force**. Three concurrent regimes: (a) Ley 49/2002
mecenazgo deductions; (b) 10 per cent of donations to legally
recognised foundations and public-utility associations not covered
by Ley 49/2002; (c) 20 per cent of party-affiliation fees and
political contributions with a 600 euro annual base cap. Corpus
excerpt: `corpus/normatives/html/ley-35-2006-art-68-3.html`.

```toml
[legal."ley-35-2006:art-68.3"]
evidence_tier = "legal_authority"
authority = "boe"
kind = "ley"
corpus_ref = "corpus/normatives/html/ley-35-2006-art-68-3.html#articulo-68-3"
document_id = "BOE-A-2006-20764"
article = "68.3"
permalink = "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a68"
published_at = 2006-11-29
effective_from = 2007-01-01
review_status = "reviewed"
reviewed_at = <FILL>
reviewed_by = "wgergely"
notes = "Deducciones por donativos y otras aportaciones. Three concurrent regimes: (a) Ley 49/2002 mecenazgo deductions; (b) 10 per cent of donations to legally recognised foundations and public-utility associations not covered by Ley 49/2002; (c) 20 per cent of party-affiliation fees and political contributions with a 600 euro annual base cap."
required_text = [
    "Deducciones por donativos y otras aportaciones",
    "10 por ciento de las cantidades donadas",
    "20 por ciento de las cuotas de afiliación",
    "La base máxima de esta deducción será de 600 euros anuales",
]
```

### `ley-35-2006:art-68.5` — Patrimonio Histórico Español + Patrimonio Mundial

Status: **in force**. 15 per cent deduction in cuota for three
investment categories: (a) acquisition from abroad of Patrimonio
Histórico Español assets with permanence + cultural-interest
declaration; (b) conservation, restoration, exhibition of bienes
de interés cultural; (c) rehabilitation of buildings in protected
city perimeters or Patrimonio Mundial sites. Corpus excerpt:
`corpus/normatives/html/ley-35-2006-art-68-5.html`.

```toml
[legal."ley-35-2006:art-68.5"]
evidence_tier = "legal_authority"
authority = "boe"
kind = "ley"
corpus_ref = "corpus/normatives/html/ley-35-2006-art-68-5.html#articulo-68-5"
document_id = "BOE-A-2006-20764"
article = "68.5"
permalink = "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a68"
published_at = 2006-11-29
effective_from = 2007-01-01
review_status = "reviewed"
reviewed_at = <FILL>
reviewed_by = "wgergely"
notes = "Deduccion por actuaciones para la proteccion y difusion del Patrimonio Historico Espanol y de las ciudades, conjuntos y bienes declarados Patrimonio Mundial. 15 per cent of investments or expenses for: (a) acquisition of Patrimonio Historico Espanol assets from abroad with permanence + cultural-interest declaration requirements; (b) conservation/restoration/exhibition of bienes de interes cultural; (c) rehabilitation of buildings in protected city perimeters or Patrimonio Mundial sites."
required_text = [
    "Deducción por actuaciones para la protección y difusión del Patrimonio Histórico Español",
    "deducción en la cuota del 15 por ciento",
    "bienes de interés cultural",
    "Patrimonio Mundial",
]
```

### `ley-35-2006:art-69` — Límites de determinadas deducciones

Status: **in force**. Caps the base of art. 68.3 (donativos) and
art. 68.5 (Patrimonio Histórico) at 10 per cent of the
contribuyente's base liquidable. The limits on art. 68.2
(actividades económicas) follow the Impuesto sobre Sociedades
incentivos regime and are computed after subtracting art. 68.1 +
art. 68.5 from the combined estatal + autonómica cuota íntegra.
Corpus excerpt: `corpus/normatives/html/ley-35-2006-art-69.html`.

```toml
[legal."ley-35-2006:art-69"]
evidence_tier = "legal_authority"
authority = "boe"
kind = "ley"
corpus_ref = "corpus/normatives/html/ley-35-2006-art-69.html#articulo-69"
document_id = "BOE-A-2006-20764"
article = "69"
permalink = "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a69"
published_at = 2006-11-29
effective_from = 2007-01-01
review_status = "reviewed"
reviewed_at = <FILL>
reviewed_by = "wgergely"
notes = "Limites de determinadas deducciones. Caps the base of the art. 68.3 (donativos) and art. 68.5 (Patrimonio Historico) deductions at 10 per cent of the contribuyente's base liquidable. The limits on art. 68.2 (actividades economicas) follow the Impuesto sobre Sociedades incentivos regime and are computed after subtracting art. 68.1 (empresas nueva creacion) and art. 68.5 (Patrimonio Historico) from the combined estatal + autonomica cuota integra."
required_text = [
    "Límites de determinadas deducciones",
    "no podrá exceder para cada una de ellas del 10 por ciento de la base liquidable del contribuyente",
    "los que establezca la normativa del Impuesto sobre Sociedades",
]
```

## Suprimidos (intentionally NOT prepared)

Per the BOE consolidated text dated 2026-04-29:

- **art-68.6** (Deducción por cuenta ahorro-empresa) — marked
  `(Suprimido)`. Not in force; no corpus / legal entry needed
  unless a historic period requires it.
- **art-68.7** (Deducción por alquiler de la vivienda habitual) —
  marked `(Suprimido)`. The state-level rental deduction was
  suprimido by Ley 26/2014; only a transitional regime survives for
  contracts dated before 2015 (`disposición transitoria
  decimoquinta`). No corpus / legal entry needed unless the
  transitional regime is enabled in Modelo 100 historical revisions.

## Next steps after operator signoff

Once the 5 entries land in `registry/aeat/legal/irpf.toml`:

1. The catalogue verification tests at
   `src/aeat/domain/calculations/registry/test_catalogue_verification.py`
   will validate them automatically.
2. Modelo 100 binding/casilla rows that currently lack legal
   anchors for the deduction family can begin citing
   `ley-35-2006:art-68.1`, `:art-68.2`, `:art-68.3`, `:art-68.5`,
   `:art-69`. This wire-up belongs to a separate per-binding pass
   that requires per-casilla legal-anchor review.
3. The `2026-05-14-legal-grounding-audit-reference.md` reference
   doc's "modelo coverage completeness" section can record the
   partial closure for Modelo 100 IRPF deduction family.
