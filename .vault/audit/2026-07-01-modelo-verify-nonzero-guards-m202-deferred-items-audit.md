---
tags:
  - '#audit'
  - '#modelo-verify-nonzero-guards'
date: '2026-07-01'
modified: '2026-07-01'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-adr]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-research]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-audit]]"
---

# `modelo-verify-nonzero-guards` audit: `M202 deferred items grounded decisions`

## Scope

A fresh-context honesty review of the `modelo-verify-nonzero-guards` campaign
found two M202 (IS pago fraccionado) silent-under-declaration candidates the
research flagged as open items but that no plan Step ever tracked to a
decision: casilla `33` ("Minimo a ingresar, CN >= 10 millones euros") and the
Mod. 40.3 LIS B2 "casos especificos" lane (casillas `19`-`26`, `61`-`66`),
which the research explicitly marked "not investigated this pass." Unlike the
Wave `W02` Phase `P06` M714 items, which were investigated and tracked by
dedicated Steps, these two M202 items were never assigned a Step and were at
risk of being silently dropped at plan close. This audit closes both,
following the rigor and structure of the `2026-06-30-modelo-verify-nonzero-guards-audit`
M714 grounded non-guard decision: re-confirm casilla ids and `input_kind`
against the live registry tree at HEAD
(`src/aeat/_data/registry/aeat/modelos/202/revisions/`), the bundled LIS art.
40 corpus, and the closed operator set in
`KNOWN_VERIFICATION_PREDICATE_OPERATORS`
(`src/aeat/domain/calculations/registry/_schema.py:1011`), and either author a
false-positive-free `implies_nonzero` ADVISORY where one exists or record a
documented non-guard with legal rationale and a concrete prerequisite. Per
`no-silent-under-declaration` and the advisory-must-distinguish discipline
(`ledger-iva-advisory-only-on-cuota-bearing-categories`), a guard that fires on
a routinely-legitimate zero trains operators to ignore it.

The B2-lane investigation surfaced a third, more severe finding beyond what
was asked: the B2 lane's own computed subtotal (casilla `26`) is never
consumed by any downstream formula in any of the three M202 revisions. This is
recorded below as a critical escalated finding, distinct from the two
"no-safe-guard-exists" wontfix decisions, because it is a suspected
formula-correctness defect rather than a legitimate-zero false-positive risk.

## Findings

### m202-minimo-cn-10m-no-safe-guard | medium | no clean antecedent casilla and the binding minimum-tax provision is ungrounded in this codebase

Casilla `33` ("Mod. 40.3 LIS -- Minimo a ingresar (CN >= 10 millones euros)")
is `input_kind = "manual"` with no formula or binding linkage in all three
revisions (`2019-2022/casillas/0042-33.toml`,
`2023-2024/casillas/0042-33.toml`,
`2025-y-siguientes/casillas/0049-33.toml` -- byte-identical label and
`legal_refs` across all three). Its declared `legal_refs`
(`ley-27-2014:art-40`, `art-29`, `art-30`, `art-105`) cover only the ordinary
modalidad 40.2/40.3 mechanics; the bundled `ley-27-2014-art-40.html` corpus
text (five numbered paragraphs, verified verbatim) contains no minimum-tax
floor for large taxpayers, and no `ley-27-2014:art-30-bis` or equivalent
disposition establishing the INCN >= EUR 10.000.000 "pago fraccionado minimo"
(the measure introduced for large groups from filing periods starting 2024) is
present anywhere in the legal catalogue or the bundled corpus (`grep` across
`legal/is.toml` finds no `art-30-bis`; `find` of
`corpus/normatives/html/ley-27-2014-*` confirms no matching file). The floor
also applies only to a cifra-de-negocios-gated subset of filers -- a
categorical fact no casilla in this chain carries, the same DSL limitation
(`implies_nonzero` takes two numeric casilla antecedents, not a categorical
gate) that blocked the M210 inmobiliaria-branch guard in Wave `W02` Phase
`P07`. The nearest candidate antecedent, casilla `04` (resultado contable), is
positive for the overwhelming majority of filers who are below the INCN
threshold and correctly leave casilla `33` blank; `implies_nonzero(["04",
"33"])` would fire on every one of them -- a structurally guaranteed
false-positive rate, the exact M714-class pattern this campaign already
established as a wontfix signal. **Decision: documented non-guard
(wontfix-for-now).**

### m202-b2-tramo-safe-guard-authored | low | the 2025-only tipo-3/tipo-4 tramo base-to-importe relationship is formula-derived and safe to declare

Casillas `61`/`62` (base/porcentaje tipo 3) and `64`/`65` (base/porcentaje
tipo 4) exist only in the 2025-y-siguientes revision
(`semantic_role_cardinality = "intentional_singleton"`, confirmed by the
already-shipped `test_committed_modelo_202_marks_2025_only_b2_rate_bands_as_intentional_singletons`).
Their corresponding importe casillas (`63`, `66`) are `input_kind =
"computed"`, each formula-derived via the `percent` operator
(`formulas/0011-modelo-202-importe-pago-fraccionado-b2-tipo-3.toml`,
`formulas/0012-modelo-202-importe-pago-fraccionado-b2-tipo-4.toml`): `63 =
percent(61, 62)`, `66 = percent(64, 65)`. This is the identical shape to the
already-shipped `modelo-202-base-imponible-previa-determinada-cuando-resultado-positivo`
(`04 -> 13`) and the M131 `01 -> 02` precedent: a positive declared base whose
computed importe resolves to zero can only happen via a genuinely-zero
percentage input, which LIS art. 29 does not establish for any tipo de
gravamen an entity filing this tramo would apply. **Decision: author as
ADVISORY (defence-in-depth, mirroring the shipped precedent).** Authored as
`modelo-202-2025-b2-base-tipo-3-implica-importe-pago-fraccionado-tipo-3`
(`implies_nonzero(["61", "63"])`) and
`modelo-202-2025-b2-base-tipo-4-implica-importe-pago-fraccionado-tipo-4`
(`implies_nonzero(["64", "66"])`), both `legal_refs = ["ley-27-2014:art-40-3",
"ley-27-2014:art-29"]`, in
`2025-y-siguientes/verification_expectations/0002-verification_predicates.toml`.
The older tipo-1/tipo-2 tramo (casillas `19`-`25`, present across all three
revisions) carries the identical mechanical invariant but is explicitly OUT OF
SCOPE for this Step -- the honesty-review item named only casillas `61`-`66`;
guarding the older tramo is a natural, low-risk follow-on left for a future
Step rather than silently expanded into this one.

### m202-b2-resultado-previo-unwired | critical | the B2 lane's own computed subtotal is never consumed by the final modalidad 40.3 result, in all three revisions

Casilla `26` ("Mod. 40.3 LIS B2 -- Resultado previo") is `input_kind =
"computed"` in every revision, formula-derived as `22 + 25 + 63 + 66 + 50 + 42
+ 51 + 52` (`formulas/0013-modelo-202-resultado-previo-b2.toml` in
2025-y-siguientes; the byte-identical shape exists in 2023-2024 and
2019-2022 under their own formula ids). A `grep` across every formula file in
all three revisions for `casilla_id = "26"` (and the equivalent recursive
walk of every formula's expression tree performed by the new
`test_committed_modelo_202_b2_resultado_previo_remains_unwired_from_modalidad_40_3_resultado`
regression) finds exactly one hit: the formula that PRODUCES casilla `26`
itself (`0013`). No formula anywhere in any M202 revision READS casilla `26`.
In particular, `modalidad-40-3-resultado` (casilla `32`, the formula whose
output feeds `cantidad-a-ingresar` via `34 = max(32, 33)`) is byte-identical
across all three revisions and reads only casilla `18` (the B1 caso general
resultado previo): `32 = percent(18 - 27 - 28, 29) - 30 - 31`. This is
corroborated by the official field ordering the `2025-y-siguientes` export
layout preserves (`18, 19..25, 61..66, 50, 42, 51, 52, 26, 27, 28, 29, 30, 31,
32, 33, 34`) and by the `modelo-202-foundation` construct, which explicitly
enrolls `modelo-202-resultado-previo-b2` immediately before
`modelo-202-modalidad-40-3-resultado` in its declared `formulas` list --
both signals consistent with casilla `26` having been INTENDED to feed casilla
`32` alongside casilla `18`, not to be a dead-end export-only figure. A
taxpayer whose modalidad 40.3 case is genuinely B2-only (multiple tipos de
gravamen applicable to different base tramos, `18 = 0`) would have their
entire B2 computation silently excluded from the final `cantidad a ingresar`
regardless of how large casilla `26` resolves. This is a suspected
formula-correctness defect, not a legitimate-zero false-positive risk, so it
is graded critical rather than treated as an ordinary wontfix. **Decision: do
NOT author an `implies_nonzero(["26", "32"])` guard in this Step.** The
correct combination semantics -- whether casilla `32` should sum `18 + 26`,
select whichever of the two is populated, or apply some other treatment, and
whether the `27`/`28` subtraction should occur before or after the
territorio-comun percentage as currently coded -- cannot be safely inferred
from the bundled corpus (the `ley-27-2014-art-40.html` text describes only the
single-tipo mechanics) or from the registry's own formula source citation,
which is suspiciously non-specific ("es un importe calculado", unlike the
verbatim-formula citations on sibling formulas such as `04 = ... clave 13 =
clave 04 + clave 38 - clave 39`). Authoring a predicate over unverified
formula semantics risks encoding a second, compounding guess on top of a
suspected defect, contrary to `aeat-safety-legal-gates` ("ground tax
semantics... do not invent legal behavior") and
`no-tautological-calculation-tests`. **Escalated as a critical follow-up**
requiring dedicated legal/workbook verification against the official AEAT
Modelo 202 instructions or DR-202 XLSX before any formula change or
predicate is authored.

## Recommendations

- **No engine change made in this Step.** Per `aeat-schema-central-config` and
  `registry-calculation-legal-grounding`, both remaining prerequisites are
  legal-catalogue and formula-correctness work, not registry-authoring
  additions in scope for this campaign; each should be scoped as its own
  research/ADR/plan cycle.
- **Prerequisite for the casilla `33` edge.** Ground the INCN >= EUR
  10.000.000 minimum-payment-on-account provision (the measure introduced for
  large groups effective from filing periods starting 2024, commonly cited
  under a new LIS disposition) against the live BOE consolidated text, bundle
  the corpus excerpt, and add a categorical CN-gating mechanism to the
  predicate DSL analogous to the M210 inmobiliaria-branch deferral (Wave `W02`
  Phase `P07`, `2026-06-30-modelo-verify-nonzero-guards-plan`). Only once both
  land does a false-positive-free guard become expressible.
- **Prerequisite for the casilla `26`-to-`32` wiring gap (urgent, critical
  priority).** Source the official AEAT Modelo 202 instructions or DR-202 XLSX
  text for the exact `modalidad-40-3-resultado` formula, confirm whether
  casilla `26` should be summed with casilla `18` (or otherwise combined) in
  the modalidad-40-3-resultado computation, fix `formulas/0006-*` in all three
  revisions accordingly, add a non-tautological regression asserting the fix
  against the sourced text, and only then consider authoring the deferred
  `implies_nonzero(["26", "32"])` (or an equivalent) advisory. Track this as
  its own follow-up campaign; do not fold a speculative formula change into
  this registry-authoring-only plan.
- **Enforcement surface.** The two new ADVISORY guards
  (`modelo-202-2025-b2-base-tipo-3-implica-importe-pago-fraccionado-tipo-3`,
  `modelo-202-2025-b2-base-tipo-4-implica-importe-pago-fraccionado-tipo-4`)
  and their two-tier test pair
  (`test_modelo_202_registry.py::test_committed_modelo_202_2025_guards_b2_tipo_3_and_tipo_4_under_declaration`,
  `test_verification_m202_advisory.py`) are the shipped, closed items from
  this audit. The two documented non-guards are locked by
  `test_committed_modelo_202_minimo_a_ingresar_cn_10m_remains_unguarded` and
  `test_committed_modelo_202_b2_resultado_previo_remains_unwired_from_modalidad_40_3_resultado`
  respectively, both citing this audit document by name in their docstrings so
  a future change that closes either prerequisite is forced to update or
  remove the corresponding assertion.
