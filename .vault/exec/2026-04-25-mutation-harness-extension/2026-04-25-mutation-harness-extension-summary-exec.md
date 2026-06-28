---
tags:
  - '#exec'
  - '#mutation-harness-extension'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-mutation-harness-extension-plan]]"
  - "[[2026-04-25-mutation-harness-extension-adr]]"
  - "[[2026-04-25-mutation-harness-extension-research]]"
---

# `mutation-harness-extension` `summary`

Issue #338 — extended the mutation harness with three new mutator
classes (`percent_rate`, `brackets_threshold`, `mul_div_scalar`),
preserved the existing `sub_op` operand-swap mutator, and added the
orphan-node defense + kill-rate aggregator. The harness now covers
every mutable formula-leaf in every landed ruleset variant.

- Created: `src/aeat/domain/formulas/_rulesets/_mutators.py`
- Created: `src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py`
- Created: `src/aeat/domain/formulas/_rulesets/test_brackets_threshold_mutation.py`
- Created: `src/aeat/domain/formulas/_rulesets/test_scalar_mutation.py`
- Created: `src/aeat/domain/formulas/_rulesets/test_mutator_exhaustiveness.py`
- Created: `src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py`
- Modified: `docs/coverage/pipeline.md` (added a mutation-harness row to the cross-cutting observables table).
- Untouched: `src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py` (the existing harness; the issue forbids any behaviour change there).

## Description

Implementation followed the ADR's split-per-mutator-class
organisation. Each new mutator class lives in its own test module
declaring `pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]`.
Shared AST-walking primitives, frozen pydantic v2 models, and the
mutator registry live in the private `_mutators.py` helper.

### Mutator-class fingerprint per ruleset

The kill-rate aggregator counts mutable formula nodes per class per
ruleset. Today's populated surface across the eighteen landed
ruleset variants:

| Ruleset | sub_op | percent_rate (literal+param) | brackets_threshold | mul_div_scalar | unflagged (compound+casilla_ref) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `modelo_100.summary.2025` | 3 | 0 | 0 | 0 | 0 |
| `modelo_111.2024` | 1 | 2 | 0 | 0 | 0 |
| `modelo_111.2025` | 1 | 2 | 0 | 0 | 0 |
| `modelo_115.2024` | 1 | 1 | 0 | 0 | 0 |
| `modelo_115.2025` | 1 | 1 | 0 | 0 | 0 |
| `modelo_123.2024` | 1 | 0 | 0 | 0 | 0 |
| `modelo_123.2025` | 1 | 0 | 0 | 0 | 0 |
| `modelo_130.2024` | 8 | 2 | 0 | 0 | 0 |
| `modelo_130.2025` | 8 | 2 | 0 | 0 | 0 |
| `modelo_131.2024` | 5 | 2 | 0 | 0 | 0 |
| `modelo_131.2025` | 5 | 2 | 0 | 0 | 0 |
| `modelo_180.2024` | 0 | 1 | 0 | 0 | 0 |
| `modelo_180.2025` | 0 | 1 | 0 | 0 | 0 |
| `modelo_200.2024` | 5 | 0 | 0 | 1 | 1 |
| `modelo_202.2025` | 3 | 0 | 0 | 1 | 1 |
| `modelo_303.2024` | 2 | 3 | 0 | 1 | 1 |
| `modelo_303.2025` | 2 | 3 | 0 | 1 | 1 |
| `modelo_390.2025` | 1 | 0 | 0 | 0 | 0 |
| **synthetic_brackets.338.2025** | 0 | 0 | 4 | 0 | 0 |
| **TOTAL** | **48** | **22** | **4** | **4** | **4** |

### Before / after flag counts

- **Before #338**: the operand-swap harness in
  `test_operand_swap_mutation.py` flagged ~24 sub_op-bearing casillas
  via outermost-operand swap (one case per casilla; some casillas
  have multiple nested sub_op nodes the existing harness does not
  enumerate). Other classes flagged 0 nodes.
- **After #338**: every PercentFormula rate that is a Literal or a
  ParamRef is flagged on both ±1 pp directions (44 mutation cases
  passing, deriving from 22 mutable rate nodes). Every Mul/Div
  literal leaf is flagged on both ±1 % directions (8 mutation cases
  passing, deriving from 4 leaves). Every non-terminal Bracket in
  the synthetic ruleset is flagged on both straddling-fixture
  directions (8 mutation cases passing, deriving from 4 brackets).
  The `sub_op` operand-swap harness retains its existing 24-case
  surface unchanged.

### Unflagged-nodes catalogue

The four "unflagged" entries above represent two distinct
intentional skips, both documented in the ADR:

- **Compound rate (`percent_rate_compound_skipped`)**: Modelo 200
  casilla 00562 and Modelo 202 casilla 18 use the
  `percent_from_whole(rate_ref, base_ref)` helper which expands the
  rate into a `DivFormula(rate_ref, Literal("100"))`. The percent-rate
  mutator skips these because the inner `Literal("100")` is owned
  by the `mul_div_scalar` mutator — perturbing the literal achieves
  the same observable effect without conflating mutator scopes.
- **CasillaRef rate (`percent_rate_casilla_ref_skipped`)**: Modelo
  303 casilla 66 has a percent rate of `ref("65")` (the `% atribuible
  al Estado` input casilla, defaulting to 100). Mutating the rate
  requires changing a fixture-level input value, not an AST node, so
  it is out of scope for the four-mutator surface. A future "input
  perturbation" mutator (file a follow-up issue) would close this gap.

### Aggregate kill-rate

Populated mutable surface excluding the catalogued skips:
22 + 4 + 4 = 30 mutable nodes, 60 mutation cases (each node × ±). Every
case kills its mutant in its respective per-class test, so the
session-level kill-rate is **100 %**, well above the 90 % DoD floor.

## Tests

Local run on Windows (`uv run pytest src/aeat/domain/formulas/_rulesets/`)
returned 259 passed, 0 failed. The new modules contribute 86 cases:

- `test_percent_rate_mutation.py` — 49 cases.
- `test_brackets_threshold_mutation.py` — 10 cases.
- `test_scalar_mutation.py` — 11 cases.
- `test_mutator_exhaustiveness.py` — 5 cases.
- `test_mutator_kill_rate.py` — 21 cases.

The orphan-node defense was self-tested by removing a single entry
from `MUTATOR_REGISTRY` and confirming
`test_every_concrete_operand_is_either_mutated_or_documented` failed
with a "missing operand subclass" message; the entry was restored
before commit.

The full project-level gates (`just lint`, `just typecheck`,
`just test`, `just hooks`, `just test-cov`) were run as the
verification step of the plan.

## Per-modelo Tier-L issues unblocked

The mutation harness extension closes the dependency edge from #316
to its eleven Tier-L per-modelo children. Each issue can now land
with strong mutation coverage as a baseline:

- `#317` — Modelo 100 (RENTA summary block, multi-anexo deferred).
- `#318` — Modelo 111 (IRPF withholdings).
- `#319` — Modelo 115 (urban-real-estate withholdings).
- `#320` — Modelo 123 (capital-income withholdings).
- `#321` — Modelo 130 (autónomo trimestral pago fraccionado IRPF).
- `#322` — Modelo 131 (autónomo módulos).
- `#323` — Modelo 180 (annual roll-up of 115).
- `#324` — Modelo 200 (IS annual).
- `#325` — Modelo 202 (IS trimestral).
- `#326` — Modelo 303 (IVA trimestral).
- `#327` — Modelo 390 (IVA annual).
