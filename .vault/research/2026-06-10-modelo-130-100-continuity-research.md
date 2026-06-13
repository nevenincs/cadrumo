---
tags:
  - '#research'
  - '#modelo-130-100-continuity'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - "[[2026-06-10-modelo-130-100-continuity-plan]]"
---



# `modelo-130-100-continuity` research: `M100 annual fold-in of M130 pagos fraccionados: grounding`

Grounding for plan step P01.S01: how the annual Modelo 100 (Renta/IRPF) credits the four
quarterly Modelo 130 pagos fraccionados, and whether the cross-period carry infrastructure
landed in the `modelo-iva-routing-carry` Wave C is the mechanism. Read-only investigation
against HEAD; every claim anchored in the in-repo registry TOML, the AEAT M100 corpus, or
application code, with honest not-grounded / version-skew flags. This report is the basis
for the P01.S02 ADR.

## Findings

### 1. M130 result casilla — casilla 19 "Resultado final"

The quarterly amount paid is M130 casilla 19 (`semantic_role = irpf_pf_resultado_final`,
`input_kind = computed`, formula `modelo-130-resultado-final = subtract(17, 18)`, grounded
`ley-35-2006:art-99` + `rd-439-2007:art-110`) in
`130/revisions/2019-y-siguientes/casillas/0001-casillas.toml` + `formulas/0001-formulas.toml`.
Casilla 19 is net of casilla 18 (autoliquidaciones anteriores / complementarias); for a clean
Q1–Q4 sequence with no complementarias, casilla 18 = 0 and casilla 19 == the amount actually
paid. The existing 2024/2025 fold-in sums `source_output = 19`, so the repo's own precedent
treats casilla 19 as the credited amount.

### 2. M100 target casilla — casilla 0604 "Pagos fraccionados ingresados (actividades económicas)"

M100 casilla 0604 (`semantic_role = irpf_pago_fraccionado_actividades_economicas`) is where the
M130 pagos fraccionados are credited (registry `100/revisions/2020/casillas/0537-0604.toml`;
corpus diccionario `RET9=[...][0604][Pagos fraccionados ingresados (actividades económicas)]`).
The credit is established by `ley-35-2006:art-99` (pagos fraccionados como pagos a cuenta del
IRPF) + `rd-439-2007:art-109` (deducción de pagos fraccionados). `art-99` is grounded in the
legal catalogue (`legal/irpf.toml`, resolvable `corpus_ref`); `art-109`'s catalogue presence
must be re-confirmed before citing.

### 3. The fold-in already exists — in M100 2024/2025, NOT in 2020 (the key version-skew finding)

The M130→M100 fold-in is already modelled in the M100 **2024 and 2025** revisions via a
`relation` (`cross_model_output`) → formula, but is **absent from the 2020 revision** the
plan's multiyear-enrollment tests target. In 2025: casilla 0604 is `computed` via formula
`renta-2025-pagos-fraccionados-ingresados = sum(rel-130-pagos-fraccionados,
rel-131-pagos-fraccionados)`; the relation is `kind = cross_model_output, source_modelo = 130,
source_output = 19, source_periods = [1T,2T,3T,4T], target_period = 0A, aggregation.op = sum`,
grounded `rd-439-2007:art-109` + `orden-hac-277-2026:art-3`. 2024 mirrors it. In the 2020
revision, casilla 0604 is a bare MANUAL casilla referenced nowhere; only M111/M115/M123
retenciones relations exist. KEY: the fold-in vehicle is the `relation` entity, not the Wave-C
`previous_filing` binding.

### 4. Does the Wave-C carry infra serve it? — schema YES; but the live mesh runs a different resolver

The `_PreviousModeloSelector` schema fully supports the shape: (a) cross-modelo
(`source_modelo` free; proven by M390←M303 and M130←M100); (b) multi-period sum
(`source_periods` tuple + `aggregation.op = sum`; canonical M390 `[1T..4T] → 0A` precedent);
(c) `source_period_offset_from_target` is single-period only and cannot interpret the annual
`0A` token, so the four-quarter fan-in must use the explicit `source_periods` list (as M390
does). HOWEVER the repo models THIS fold-in via the `relation` → `RelationPrefillSourceResolver`
path, and **that resolver is NOT enrolled in the live calculate mesh** — `_calculation_actions.py`
merges only the ledger-IVA, ledger-renta, and `PreviousFilingSourceResolver` resolvers. So the
registry models the 2024/2025 fold-in but the calculate path never fires it (it is exercised
only in isolated continuity tests via direct `resolve_relations_from_local_store`). Wave-C
persistence IS in place: `persist_filed_revision_observation` stamps filed observations
`source_kind = app_filing` (non-official), and the relation resolver reads the same
`CalculationObservationRepository`, so the four filed M130 observations ARE available. A
dedicated new resolver is NOT required.

Two mechanism options for the ADR:
- **Option A (relation-reuse):** enroll `RelationPrefillSourceResolver` in the live mesh + use
  the existing 2024/2025 relation+formula shape (back-porting to 2020 if that revision is
  targeted). Aligns with the registry's established modelling + the M180/M190/M193
  reconciliation precedent; requires a mesh change.
- **Option B (previous_filing-direct):** model casilla 0604 as a `bound` casilla with a direct
  `previous_filing` binding (`source_modelo = 130, source_periods = [1T..4T],
  source_casillas = [19], op = sum`) — the M390←M303 shape — consumed by the already-enrolled
  `PreviousFilingSourceResolver` with NO mesh change; diverges from the registry's relation
  modelling of this fold-in. (The 2024/2025 `previous_filing` binding has no period spec and is
  not a direct binding, so it is not the live carry path today.)

### 5. Expected value, reconciliation, no-silent

Structurally: M100 casilla 0604 == sum over {1T,2T,3T,4T} of M130 casilla 19 (+ M131 if
present). It flows into cuota diferencial (M100 casilla 0610) which subtracts pagos a cuenta
from cuota líquida (0595). FLAGS: in the 2020 revision both 0610 and the 0595→0610 cuota chain
are unmodelled (bare manual casillas), so populating 0604 alone does not carry into 0610 there;
and no numeric AEAT oracle for 0604 was located (parity replays are employee-default cases), so
the expected value must be asserted structurally (sum of filed casilla-19 observations) per
`no-tautological-calculation-tests`, not against a hand-computed figure. A non-silent
reconciliation belongs as an M100 `verification_predicate` comparing 0604 against the filed
M130 casilla-19 sum (precedent: M130 `cap_le_when_positive` BLOCKING_RULE, M200 `implies_nonzero`
advisory) per `no-silent-under-declaration`.

### 6. Decisions for the P01.S02 ADR + grounding gaps

- **Mechanism:** Option A (relation-reuse, mesh enrollment) vs Option B (direct previous_filing
  binding, no mesh change). Neither needs a new resolver.
- **Target revision:** 2024/2025 (fold-in already present) vs back-port to 2020.
- **Target casilla:** 0604 (confirmed). **Provenance:** carried 0604 is non-official
  (`app_filing`, ruling D1 of `modelo-iva-routing-carry` ADR) and must not satisfy the
  cross-period clean-state filing gate.
- **No-silent:** add the M100 reconciliation `verification_predicate`.
- **Grounding gaps (registry-calculation-legal-grounding):** 2020 casilla 0604 cites the
  rendimiento articles, not the credit article — if 2020 is targeted, add `ley-35-2006:art-99`
  (grounded) + `rd-439-2007:art-109` (re-confirm catalogue presence) to 0604's `legal_refs`;
  and decide whether scope includes modelling the unmodelled 2020 cuota chain (0595→0610) or
  stops at populating 0604.

