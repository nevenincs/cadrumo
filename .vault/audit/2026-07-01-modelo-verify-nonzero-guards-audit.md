---
tags:
  - '#audit'
  - '#modelo-verify-nonzero-guards'
date: '2026-07-01'
modified: '2026-07-01'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-adr]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-research]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-audit]]"
---

# `modelo-verify-nonzero-guards` audit: `M123 exoneration grounding re-verification`

## Scope

An independent code review of the `modelo-verify-nonzero-guards` campaign
raised a MEDIUM finding against the shipped M123 (retenciones capital
mobiliario) ADVISORY guard `modelo-123-2024-base-total-implica-retenciones-total`
(`implies_nonzero(["06", "09"])`, `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/verification_expectations/0002-verification_predicates.toml`):
the guard's false-positive-freedom claim was corroborated only against the
`rd-439-2007:art-90` 19 percent base rate and its 60 percent capital-semilla
reduction, not against RD 439/2007's retention-exoneration list (the
provision commonly cited as RIRPF art. 75, "rentas exceptuadas de la
obligacion de retener e ingresar a cuenta") or any other cuantia-based
partial-exemption mechanism. This audit re-verifies the guard against the
live registry tree at HEAD
(`src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/`), the
bundled RD 439/2007 corpus, and the M193 annual-informativa mirror of M123,
modelling its rigor on the `2026-06-30-modelo-verify-nonzero-guards-audit`
M714 grounded non-guard decision. Per
`legal-grounding-verifies-bundled-authoritative-corpus` and
`ledger-iva-advisory-only-on-cuota-bearing-categories`, an ADVISORY that fires
on a routinely-legitimate zero trains operators to ignore it; this audit
determines whether the M123 `06->09` guard clears that bar.

## Findings

### m123-base-rate-never-reaches-zero | low | the only bundled capital-mobiliario retention-rate provision reduces, never exempts

`rd-439-2007:art-90` (`legal/irpf.toml:177-195`, `corpus_ref =
corpus/normatives/html/rd-439-2007-art-90.html#a90`, reviewed 2026-05-15) is
read in full: paragraph 1 sets a flat 19 percent rate on the base de
retencion; paragraph 2 reduces that rate by 60 percent (to 7.6 percent) only
for income covered by the `ley-35-2006:art-68.4.h` capital-semilla
deduction. Both paragraphs of the bundled corpus text were read verbatim;
neither states nor implies a rate of zero, and no cuantia (minimum-amount)
floor is present anywhere in the article, unlike the rendimientos-del-trabajo
retention scheme. Every euro of base entered into M123 casillas `04`/`05`
therefore carries a strictly positive statutory rate (19 percent or 7.6
percent) under the bundled corpus. **No guard change required.**

### m123-declaracion-negativa-mechanism-does-not-apply | low | the general cuantia-based zero-retention clause in RD 439/2007 art. 108 has no capital-mobiliario application under the bundled corpus

`rd-439-2007:art-108` (`legal/irpf.toml:217-235`, bundled and reviewed)
paragraph 1 confirms RD 439/2007 anticipates a "declaracion negativa"
scenario: a retenedor who paid rentas sometidas a retencion but practised no
retention "por razon de su cuantia" (by reason of amount) must still file a
zero-value declaration. This is a real general reglamento mechanism, but it
is driven by a per-income-type cuantia threshold declared elsewhere (the
rendimientos-del-trabajo retention tables, RIRPF art. 81.1). RIRPF art. 81
itself is not bundled as its own corpus file, but the bundled
`ley-35-2006.html` (disposicion adicional cuadragesima septima, apartado 2)
independently confirms the scope: it names "el cuadro con los limites
cuantitativos excluyentes de la obligacion de retener a que se refiere el
articulo 81.1 del Reglamento del Impuesto sobre la Renta de las Personas
Fisicas" and ties that table explicitly to rendimientos del trabajo, pensiones,
and prestaciones por desempleo -- not to rendimientos del capital mobiliario.
Because the bundled `art-90` -- the only capital-mobiliario retention-rate
provision in the registry -- carries no cuantia floor of its own, this general
mechanism has no confirmed application to the income categories M123 covers
(dividendos y participaciones, resto de rentas del capital mobiliario).
**No guard change required; the mechanism is real but inapplicable under the
bundled corpus.**

### m123-art-75-exoneration-list-not-bundled | medium | the type-based retention-exoneration provision (commonly RIRPF art. 75) is absent from both the corpus and the legal catalogue

RD 439/2007 arts. 74-76 (the article range containing the type-based
"rentas exceptuadas de la obligacion de retener e ingresar a cuenta" list --
e.g. Letras del Tesoro interest, primas de conversion de obligaciones en
acciones, and other named exclusions) is not present anywhere in this
codebase: `grep` across the full `src/aeat/_data/registry` tree for
`rd-439-2007:art-74`, `art-75`, and `art-76` returns zero matches, and `ls`
of `corpus/normatives/html/rd-439-2007-*` confirms no `art-74`, `art-75`, or
`art-76` file is bundled (thirteen other RD 439/2007 articles are bundled;
this range is the gap). Per
`legal-grounding-verifies-bundled-authoritative-corpus`, this absence is
itself a finding: the claim "no capital-mobiliario income category is
type-exonerated from retention" cannot be verified against verbatim BOE text
in this codebase today. Two structural cross-checks partially substitute for
the missing text: (1) M123 casillas `04`/`05`/`06` are declared with
`semantic_role = "base_rentas_dividendos"` / `"base_rentas_resto"` /
`"base_rentas_total"` under `section = ["base_retenciones", ...]` -- the base
casillas are defined as the base **on which retention was computed**, sourced
from `rd-439-2007:art-90`'s "base de retencion," not as gross income paid
regardless of retention status; a rendimiento with no retention obligation
has no "base de retencion" to enter. (2) M193 (`decl.base-total` /
`decl.retenciones-total`, the annual informativa mirror of M123's quarterly
series) carries the identical two-casilla base/retenciones-total structure
with no parallel channel for reporting type-exonerated amounts, consistent
with such income falling outside this modelo family's declared scope entirely
rather than being reported at a legitimate zero rate inside it. Neither
cross-check is a substitute for reading the actual exoneration list verbatim.
**Decision: keep the guard (ADVISORY, aggregate `06->09`) unchanged; the
structural argument plus the confirmed absence of any capital-mobiliario
cuantia floor (finding above) together give reasonable, but not
corpus-verbatim, confidence that no category M123 declares resolves to a
legitimate zero. Track bundling RD 439/2007 arts. 74-76 as a follow-up to
close this gap with verbatim text.**

## Recommendations

- **No guard change.** The M123 `06->09` ADVISORY
  (`modelo-123-2024-base-total-implica-retenciones-total`) and its two-tier
  test pair (`test_modelo_123_registry.py`,
  `test_verification_m123_advisory.py`) remain sound under the corroboration
  performed here; do not narrow, widen, or convert it to `BLOCKING_RULE`.
- **Follow-up: bundle RD 439/2007 arts. 74-76.** Fetch and bundle the
  type-based retention-exoneration article range against the official BOE
  consolidated text (`BOE-A-2007-6820`), author the corresponding
  `legal.*` catalogue entries with `corpus_ref` and `required_text`, and
  cross-check each listed exoneration category against M123's own income
  scope (dividendos y participaciones, resto de rentas del capital
  mobiliario) to confirm none intersects. This closes the residual gap this
  audit records with verbatim BOE text instead of the structural argument.
- **No engine change recommended now.** Per `aeat-schema-central-config` and
  `registry-calculation-legal-grounding`, the follow-up is legal-catalogue
  authoring work, not a registry-authoring addition to this campaign's guard;
  scope it as its own small research/authoring pass rather than folding it
  into this plan's closeout.
- This audit and its exec record
  (`.vault/exec/2026-07-01-modelo-verify-nonzero-guards-exec.md`) are the
  input `W03.P09.S29` should cite when converting this code-review finding
  into either a closed item or a tracked follow-up Step.
