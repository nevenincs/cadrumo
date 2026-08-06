---
tags:
  - '#audit'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:11786ff8556139301e606d5e6337291244dde0dc9aa5ea7997fcb243ef08b67f'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-adr]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-research]]"
---

# `modelo-verify-nonzero-guards` audit: `M714 deferred edges grounded non-guard decision`

## Scope

Wave `W02` Phase `P06` (`W02.P06.S18`, `W02.P06.S19`) of the
`modelo-verify-nonzero-guards` plan requires a grounded, documented decision on
the two Modelo 714 (Impuesto sobre el Patrimonio) edges the research and ADR
deliberately scoped out of Wave `W01`'s SAFE `cuota-integra -> total-cuota-integra`
ADVISORY guard: `patrimonio.base-imponible -> patrimonio.base-liquidable` and
`patrimonio.total-cuota-integra -> patrimonio.cuota-a-ingresar`. This audit
re-verifies the research's rejection of both edges against the live registry
tree at HEAD (`src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/`),
the bundled authoritative corpus for Ley 19/1991 arts. 28/30/31, and the closed
operator set in `KNOWN_VERIFICATION_PREDICATE_OPERATORS`
(`src/aeat/domain/calculations/registry/_schema.py:1011`), and records why
neither edge can be authored as a false-positive-free `implies_nonzero`
ADVISORY without further calculation-modelling work that is out of scope for a
registry-authoring-only plan. Per `no-silent-under-declaration` and the
advisory-must-distinguish discipline (`ledger-iva-advisory-only-on-cuota-bearing-categories`),
an advisory that fires on a routinely-legitimate zero trains operators to
ignore it; both edges fail that bar today.

## Findings

### m714-base-imponible-base-liquidable-no-safe-guard | medium | minimo exento makes the zero-consequent the common case, and the registry has no formula or parameter to gate it

`patrimonio.base-imponible` and `patrimonio.base-liquidable` are both
`input_kind = "manual"` casillas (`casillas/0001-casillas.toml:36-57`) with no
formula linking them. Ley 19/1991 art. 28 (`legal/patrimonio.toml:11-28`,
`corpus_ref = corpus/normatives/html/ley-19-1991-art-28.html#art-28`, reviewed
2026-06-02) states the base liquidable equals the base imponible reduced by the
"minimo exento" -- "con caracter general 700.000 euros" per the bundled corpus
text. The Modelo 714 filing threshold (art. 28's cross-reference plus the
registry's own catalogue header note) obligates filing at gross assets >=
EUR 2,000,000, which is well above the EUR 700,000 default exemption. A filer
with, for example, EUR 2,000,000 gross assets and ordinary debt has a positive
`base-imponible` and a `base-liquidable` floored at EUR 1,300,000 -- still
positive -- but a filer closer to the threshold, or one whose comunidad
autonoma sets a materially higher umbral (the catalogue note records the
Comunitat Valenciana at EUR 600,000 and other CCAA variants up to
EUR 1,000,000), can legitimately resolve `base-liquidable` to exactly zero
while still being obligated to file. This is not an edge case; it is the
ordinary outcome for any filer within one minimo-exento band of the threshold.
The registry carries no formula, no parameter, and no casilla encoding the
minimo exento amount for this revision (`grep`-confirmed against every
`parameters/*.toml` and `formulas/*.toml` file under the revision: the only
parameter is `patrimonio-escala-estatal`, the art. 30 cuota tariff, and the
only formulas are the art. 30 escala and the art. 31 80%-suelo reference). The
`implies_nonzero` operator only compares two casilla values
(`_schema.py:1068-1079`); it has no subtraction-against-a-parameter or
threshold-comparison capability, so there is no way to express "base-imponible
minus the minimo exento is still positive" inside the existing predicate DSL.
Authoring `implies_nonzero(["patrimonio.base-imponible", "patrimonio.base-liquidable"])`
as proposed in the research's rejected-candidate list would fire on every
near-threshold filer who correctly applied the exemption -- a guard with a
structurally guaranteed false-positive rate, not an edge case the advisory
exists to flag. **Decision: documented non-guard (wontfix-for-now).**

### m714-total-cuota-integra-cuota-a-ingresar-no-safe-guard | medium | limite conjunto floor plus two unmodelled deduction mechanisms leave legitimate full-offset paths the registry cannot distinguish from omission

`patrimonio.total-cuota-integra` (casilla 40) and `patrimonio.cuota-a-ingresar`
(casilla 55) are both `input_kind = "manual"` with no formula linkage
(`casillas/0001-casillas.toml:97-131`), and the intermediate
`patrimonio.cuota-minorada` (casilla 45) between them is manual too. Ley
19/1991 art. 31 (`legal/patrimonio.toml:50-70`, reviewed 2026-06-02) sets the
limite conjunto: when the combined IP+IRPF cuota exceeds 60% of IRPF bases
imponibles, the IP cuota is reduced toward that limit, but "sin que la
reduccion pueda exceder del 80 por 100" -- a 20% floor on the cuota integra,
not a path to zero. The registry already computes that floor reference as
`patrimonio.reduccion-limite-80` (casilla 39, `formulas/0002-...toml`), so the
limite-conjunto mechanism alone cannot legitimately zero `cuota-a-ingresar`.
However, two further deduction mechanisms genuinely can: Ley 19/1991 art. 32
(deduccion por impuestos satisfechos en el extranjero, for IP-liable taxpayers
who paid an equivalent wealth tax abroad) and art. 33 (bonificacion del 75% de
la cuota for bienes/derechos situados or ejercidos en Ceuta o Melilla). Neither
article is present anywhere in this codebase: `grep` across
`legal/patrimonio.toml` finds only arts. 4.Nueve, 28, 30, and 31 grounded; `ls`
of `corpus/normatives/html/ley-19-1991-*` confirms no `art-32` or `art-33`
bundled corpus file exists; and the M714 casilla set
(`casillas/0001-casillas.toml`, 12 casillas total) has no casilla recording
either deduction having been applied. A taxpayer who legitimately zeroes their
`cuota-a-ingresar` via either mechanism leaves no registry-visible signal that
distinguishes their filing from an operator who simply forgot to populate
casilla 55 -- the exact ambiguity the false-positive-risk framing in the ADR
and research warned against, now confirmed by the absence of the grounding
data itself (not merely the absence of a formula). Authoring
`implies_nonzero(["patrimonio.total-cuota-integra", "patrimonio.cuota-a-ingresar"])`
today would fire on every Ceuta/Melilla-bonificada or foreign-tax-credited
filing alongside every genuine omission. **Decision: documented non-guard
(wontfix-for-now).**

## Recommendations

- **Prerequisite for the base-imponible -> base-liquidable edge.** Model the
  minimo exento as a registry parameter (state default EUR 700,000 plus the
  documented CCAA variants) and a formula computing
  `patrimonio.base-liquidable = max(0, patrimonio.base-imponible - minimo_exento)`
  for this revision. Once `base-liquidable` is formula-derived rather than
  manual, the existing `implies_nonzero` shape becomes safe to apply one step
  earlier in the chain (`base-imponible` vs. the *formula's own computed
  zero*, which is no longer ambiguous), or a dedicated floor-aware predicate
  becomes possible. This is calculation-modelling work, not registry-authoring
  work, and is out of scope for this plan; track it as a follow-up Modelo 714
  calc-engine feature.
- **Prerequisite for the total-cuota-integra -> cuota-a-ingresar edge.** Author
  the art. 32 (deduccion impuestos extranjero) and art. 33 (bonificacion
  Ceuta/Melilla) legal-catalogue entries against the bundled BOE corpus, add
  their corresponding casillas to the M714 2021-y-siguientes revision, and wire
  them into the cuota-minorada / cuota-a-ingresar chain. Once those deductions
  are registry-visible facts rather than invisible operator knowledge, a
  predicate can legitimately exclude "deduction casilla is populated" before
  firing, closing the false-positive gap. Until then, no `implies_nonzero`
  variant over the existing casilla set can distinguish a legitimate full
  offset from a silent omission.
- **No engine change recommended now.** Per `aeat-schema-central-config` and
  `registry-calculation-legal-grounding`, neither prerequisite is a small
  registry-authoring addition: each requires new legal-catalogue entries backed
  by freshly-bundled corpus text, new casillas, and (for the first edge) a new
  formula -- properly scoped as its own research/ADR/plan cycle, not folded
  into this plan's registry-authoring-only Wave `W02`.
- The Wave `W01` `cuota-integra -> total-cuota-integra` ADVISORY
  (`modelo-714-cuota-integra-implica-total-cuota-integra`) and the
  `test_modelo_714_riskier_edges_remain_unguarded` regression in
  `src/aeat/domain/calculations/registry/tests/test_modelo_714_registry.py`
  remain the enforcement surface: the test asserts the absence of
  `modelo-714-base-imponible-implica-base-liquidable` and
  `modelo-714-total-cuota-integra-implica-cuota-a-ingresar` predicate ids and
  now cites this audit document in its docstring, so a future naive addition
  of either guard fails the test and points the author back here.
