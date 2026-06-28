---
tags:
  - "#audit"
  - "#testing-framework"
date: 2026-05-13
modified: '2026-05-13'
related:
  - "[[2026-05-13-schema-driven-wizard-ux-audit]]"
---

# testing-framework tautology audit

## scope

Stringent review of the project's test suite for tautological tests,
false-positive signals, and tests that pass without meaningfully
verifying failure conditions. Driven by the project's own rule
`.claude/rules/no-tautological-calculation-tests.md`.

## findings

### confirmed tautology (1)

`src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py`
declared `test_minimo_personal_y_familiar_aggregates_all_four_components_estatal`
which fed `0511=2775, 0513=1000, 0515=500, 0517=250` and asserted
`0519 == Decimal("4525.00")`. The registry formula declares
`0519 = sum(0511, 0513, 0515, 0517)` — author's hand-sum (4525.00) and
registry's formula compute the same value. By the rule:

> If I changed the formula's declaration to be wrong against AEAT,
> would this test fail? — No.

Fix landed in this audit: the test now asserts the formula's
expression-tree structure (`op == "sum"`, operand set ==
`{0511, 0513, 0515, 0517}`) rather than the arithmetic. Arithmetic
verification routes through the live Renta WEB Open replay parity
tests.

### borderline / accepted (under existing rule exemptions)

| file | line | pattern | category |
| --- | --- | --- | --- |
| `test_modelo_180_round_trip.py` | 52-54 | `result.values["..."] == Decimal("5"/"2149.75"/"418.00")` | identity-passthrough (op=copy) |
| `test_modelo_190_193_round_trip.py` | 67-69 | `result.values["..."] == Decimal("12"/"7000.50"/"1330.10")` | identity-passthrough (op=copy) |
| `test_filing.py` | 255-256 | `binding_values["..."] == Decimal("1200.50"/"2")` | binding threading (no formula arithmetic) |

These match the rule's allowed "Identity round-trips" exemption — they
verify runtime threading of an input value, not formula arithmetic.

### tautology candidate (escalated, not in scope of this audit)

`src/aeat/domain/calculations/registry/test_ledger_renta_expense_binding.py`
line 105: `casilla_inputs["0199"] == Decimal("200.00")` is the sum of
two synthetic observations (121 + 79). The binding's `op = "sum"`
re-sums the same observations. The test author hand-summed.

Owned by the ledger-renta-pipeline workstream; flagged here for
remediation by the test owner.

### derived asserts (7) — not replayable by detector

7 chain-behaviour expected outputs depend on bindings or parameters
that the static-replay detector cannot resolve without runtime
context. Each remains under scrutiny:

```
0519 = 2775.00   (formula reads bindings/params)
0521 = 1000.00
0522 = 0.00
0432 = 30000.00
0435 = 25000.00 / 40000.00
0500 = 35600.00
```

These are not flagged tautological today because the detector is
deliberately conservative. They warrant manual review against
.claude/rules/no-tautological-calculation-tests.md.

## suppression hygiene

```
xfail markers:            1 (strict=True, documented architectural mismatch)
xfail(strict=False):      0
@skip/@skipif markers:    0
pytest.skip() calls:     21 (all gate on env vars or filesystem state — legit)
mock.patch / Mock usage:  0 (regex false-positive resolved)
contextlib.suppress:      0 in test logic (only mentioned in docstrings)
assert True / assert 1:   0
```

The xfail in `test_renta_web_open_capture_replay.py` covers an
architectural mismatch documented inline; `strict=True` means a
future fix that lets the test pass surfaces immediately rather than
silently.

## broad-catch audit

400 `pytest.raises(...)` calls without an explicit `match=` argument.
Each broad-class catch will accept any subclass error — including
unrelated regressions. Tightening these to `match=` would surface
regressions hiding behind same-class exceptions. Not blocking but
recommended for future hardening.

17 `except Exception` clauses in test files — most are intentional
re-raises in fixture cleanup. Spot-check did not surface a swallow.

## live data ingestion + calculation verification backend

### live ingestion pipeline (operational)

`src/aeat/adapters/outbound/aeat/sede/_renta_web_open.py`
implements the Renta WEB Open driver:

- `collect_renta_web_open_observation`: navigates AEAT's open
  simulator, fills the synthetic identification profile, optionally
  applies `casilla_overrides` via the Buscar casilla dialog, scrapes
  summary labels and `scrape_casillas` form values.
- Every locator click routes through `_click_expected` →
  `assert_click_target_safe`, blocking interactions with
  forbidden-token labels (Presentar/Firmar/Pagar).
- Live captures persist as
  `corpus/parity_replays/renta_web_open/{scenario}.json`.

### calculation verification backend (operational)

`src/aeat/domain/calculations/registry/test_renta_web_open_replay_parity.py`
holds the per-scenario parity gate:

```
test_renta_web_open_replay_payload_matches_registry_via_oracle
```

For each replay payload it runs the registry calculation and asserts
`registry == AEAT`. Currently grounded on 5 captured payloads
(baseline + Madrid + Cataluña + Galicia + Canarias). The H6 hygiene
gate (`test_every_renta_chain_scenario_has_renta_web_open_replay_payload`)
enforces hard-fail mode: every declared baseline scenario must carry
a captured payload.

### regression gate added

`src/aeat/domain/calculations/registry/test_tautology_gate.py`
mechanises the rule. The gate replays each
`RegistryScenarioExpectedOutput` declared in chain-behaviour scenarios
against the registry's own formula. If the registry's declared formula
yields the same expected literal from the same test inputs, the
assertion is reported as tautological and CI fails. Conservative on
binding/parameter-dependent expressions (skips them) but strict on
pure-arithmetic compositions (sum/subtract/min/max/percent/copy over
literal casilla values).

## verdict

Three passes landed in this audit cycle:

  * **Pass 1** (chain-behaviour scope): 1 tautology removed, regression
    gate seeded.
  * **Pass 2** (codebase-wide hand-summed scope): 5 tautologies removed
    (chain-behaviour ledger expense binding, sede declarations quarter
    aggregation, IVA category-filter aggregation, modelo 349 grouping
    aggregation, OSS-IOSS routing aggregation). Gate expanded to walk
    every `src/aeat/**/test_*.py`.
  * **Pass 3** (no-failure-mode scope): 50 vacuous tests hardened with
    explicit return-value and structural assertions. The final
    truly-vacuous count is **0** (verified by AST walk that recognises
    `pytest.raises` contexts, `raise` statements, `assert_*` /
    `_assert_*` helper calls, and `pytest.fail()`).

Live ingestion (Renta WEB Open driver) and calculation verification
(replay-parity) backends are operational; 5 captured baseline payloads
ground the per-scenario parity gate. Both CI regression gates carry
explicit, documented waiver lists (one Python-primitive contract
waived; no other waivers).

The receiver round-trip tests for modelos 180, 190, and 193 are
hardened with graph-wiring preludes (formula op=copy + source relation
ids) before the runtime threading checks, so a declaration-level
regression fails before the threading assertions even run.

Rule-name references and historical-commit pointers were stripped from
test docstrings across six files in compliance with the no-transient-
meta-in-source-code mandate; the auto-memory feedback was updated to
record this incident.

Five commits landed the work:

  * `f98ae451` — pass-1 chain-behaviour fix + initial gate
  * `b0a6cd73` — pass-2 hand-summed gate + 4 tautology fixes
  * `496b91e6` — 180/190/193 graph-wiring preludes
  * `836c90a5` — pass-3 sanitizer + modelo validator hardening
  * `62645e1a` — pass-3 final 20 vacuous-test hardening sweep
