**Kent success moment:** Kent has the declaración PDF of his Modelo 303 filing for any supported ejercicio (2024/2025/2026). He runs `aeat filing import --from-declaracion <pdf>`. The tool parses every printed casilla, re-derives every `computed=True` casilla via the formula engine against the extracted inputs, and returns `Extraction status: COMPLETE`, `Verification status: VERIFIED` with zero discrepancies. If a discrepancy appears, the classifier tells Kent exactly which casilla drifted and the suggested cause (extraction / formula / un-modelled rule / rounding).

## Tier — L (Liquidation)

Full calc + round-trip + per-annum rule coverage applies. This modelo has `computed=True` casillas derived via the formula DSL.

## Scope

Modelo 303 — IVA autoliquidación (trimestral). All 33 printed casillas in the declaración block.

## Current state (2026-04-22 audit)

Ruleset exists for 2024 + 2025. Declaración extractor FULL (33 casillas). Extraction round-trip test exists but **NO integration test in `test_kent_workflows.py`** for the CLI verify path. No 2026 ruleset. No L1 anchor. Tier-L reference implementation alongside 130 — expected to be the most complete after this issue closes. **IVA complexity deep-dive is the IVA umbrella issue — this issue covers the formula-ruleset and extractor completeness only.**

## Definition of Done — cent-exact pass criteria

### Correctness (quantitative)

- [ ] Every `computed=True` casilla printed on the BOE template is implemented as a `FormulaDefinition` in the ruleset (enumerate the full inventory in the PR body; justify any subset with a `.vault/reference/` waiver)
- [ ] ≥ 3 parametrized worked examples per computed casilla: zero-boundary / typical / threshold-edge
- [ ] Every expected value **externally anchored** to BOE, AEAT simulator output, or a real filing — no internally-computed expected values. Follow the pattern of `src/aeat/formulas/_rulesets/test_modelo_130_2025.py::test_external_worked_example_rirpf_art_110`
- [ ] Rounding semantics declared per rule (default: terminal `RoundFormula(digits=2, HALF_UP)`); boundary tests at 0.01 € detection floor
- [ ] Threshold tests for every legal boundary relevant to this modelo (retenciones mínimas, umbrales de exención, etc.)

### Mutation coverage

- [ ] Operand-swap mutation harness (`test_operand_swap_mutation.py`) covers every `sub_op` chain in this modelo
- [ ] **Depends on** issue (mutation-harness extension chore): `percent`-rate and `brackets`-threshold mutations must flag ≥ 90% of mutants once the harness is extended

### Legal citation completeness

- [ ] Every `CasillaDefinition.legal_basis` is non-empty and passes the blocklist validator (`src/aeat/models/_citation_registry.py`)
- [ ] **Depends on** issue (mandatory LegalCitation enforcement): once `model_post_init` enforces non-empty `legal_basis`, this modelo imports clean

### Per-year legal completeness

- [ ] Year-scoped rulesets registered for **2024, 2025, 2026** (separate files, non-overlapping `effective_from/to`)
- [ ] `.vault/reference/2026-303-rule-delta.md` manifest listing every numeric/structural change per year with BOE citations
- [ ] Any worked example in BOE/AEAT docs is reproduced to the cent in the colocated test file
- [ ] For 2026: BOE references checked from primary sources (not training data); implementer flags any unresolved ambiguity in the PR body

### PDF round-trip

- [ ] Declaración extractor (`src/aeat/declaracion/_extractors/modelo_303_v2025.py`) is casilla-complete for the liquidación block (not just MVP — enumerate full inventory)
- [ ] Synthetic generator via `QuarterlyGenParams` scaffold (or bespoke if the form cannot fit); round-trip `generator(params) → PDF → extractor == params`
- [ ] L1 public-anchor real PDF hash-pinned in `tests/fixtures/pdf_corpus/l1_public_anchors/modelo_303/` **OR** explicit `.vault/reference/` waiver explaining why none is available
- [ ] Integration test in `tests/integration/test_kent_workflows.py::TestKentImportsModelo303Declaracion` asserting full CLI path returns `VERIFIED` on happy path + classified discrepancies on tampered fixture (ES + EN + partial-extraction cases — follow the 130 template)

### Verification wiring

- [ ] `verify_declaracion(filing, ruleset)` returns `VERIFIED` on the synthetic happy path
- [ ] Tampered fixture produces correctly-classified `ClassifiedDiscrepancy` (extraction / formula / un-modelled / rounding)
- [ ] Coverage ≥ 30% of ruleset casillas supplied by extraction (verdict threshold)

### Test discipline (project mandates)

- [ ] `pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]`
- [ ] No mocks / fakes / stubs / skips / freezegun / pytest-mock (project-wide ban)
- [ ] Tests colocated Rust-style under `src/aeat/formulas/_rulesets/` and `src/aeat/declaracion/`
- [ ] 100% of named formula rows covered by at least one parametrized test

### Closure evidence

- [ ] `.vault/exec/YYYY-MM-DD-modelo-303-calc-verify/…-summary.md` with mutation-harness % + coverage delta
- [ ] `docs/coverage/modelos.md` row flipped to ✅ in every applicable column with provenance line
- [ ] PR body cites BOE article numbers for every rate, threshold, and deduction cap

---

**Parent EPIC:** #316

**Labels:** `type:feature`, `area:submission`, `health:coverage`, `priority:P2-medium`, `effort:L`, `parallel-safe`, `kent-journey`
