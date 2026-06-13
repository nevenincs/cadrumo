---
tags:
  - "#audit"
  - "#real-pdf-import"
date: 2026-04-22
modified: '2026-04-22'
related:
  - "[[2026-04-22-real-pdf-import-wave-48-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-53-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-58-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-60-exhaustive-audit]]"
---

# real-pdf-import — wave 62 exhaustive audit

## Scope

Fifth cycle of the exhaustive-audit pattern. Four parallel streams
verify waves 61a–f remediations and flag residuals that waves 61
did NOT address.

Commit range audited: `c36f9b0..HEAD` (wave 61 sub-waves) —
specifically `d30c530`, `a12342c`, `c08ad18`, `40c45df`.

| Stream | Verdict | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| 1 wave 61 remediation verification | PASS | 0 | 0 | 2* |
| 2 mutation-harness + external-anchor rigor | REVISION REQUIRED | 4 | 0 | 1 |
| 3 extractor + primitive regression | PASS | 0 | 0 | 3 |
| 4 audit-trail + ADR consistency | REVISION REQUIRED | 1 | 1 | 1 |

*Stream 1 surfaced two out-of-scope residuals (L1 390 docstring
imprecision, L3 missing exec records) that fell outside the wave
61 remediation plan. L3 is re-cited as HIGH in stream 4.

**Total open: 5 HIGH, 1 MEDIUM, 7 LOW.**

## Closure status (updated 2026-04-22, wave 68)

| Finding | Status | Closing wave |
|---|---|---|
| H1 mutation harness ≤1 sub_op per modelo | CLOSED | wave 63b (`65e5643`) |
| H2 Modelo 200 absent from harness | CLOSED | wave 63b (`65e5643`) |
| H3 LIRPF art. 103 miscite for cuota diferencial | CLOSED | wave 63a (`65e5643`); further refined wave 67a (`29a537e`) — arts. 62/67/73/77/79/99 disambiguated |
| H4 RIRPF art. 110.1.b subsection inverted | CLOSED | wave 63a (`65e5643`); wave 65a (`ab808d2`) clarified b/c assignment; wave 67g (`HEAD`) fixed ruleset _CITATIONS + 115/180 100.3.a cross-cutting |
| H5 exec records missing | PARTIAL | re-cited as wave 64 H7 → wave 66 H1; ADR deferral section added wave 65d (`ab808d2`); GH issue tracked wave 68d |
| M1 wave 48 audit-doc H3 row stale | CLOSED | wave 63c (`65e5643`); further refreshed wave 67a |
| L1 390 docstring imprecision | CLOSED | wave 63d (`65e5643`) |
| L2 202 operand-swap docstring | CLOSED | wave 63d (`65e5643`) |
| L3 thousands_sep pattern too permissive | CLOSED | wave 63d (`65e5643`) |
| L4 test_thousands_sep_reaches name misleading | CLOSED | wave 63d (`65e5643`) |
| L5 y-ordering invariant undocumented | CLOSED | wave 63d (`65e5643`) |
| L6 modelos.md row 15 drift | CLOSED | wave 63c (`65e5643`) |
| L7 escalated to HIGH H5 | See H5 | — |

## HIGH findings

### H1 (stream 2) — Mutation harness covers ≤1 sub_op per target modelo

`test_operand_swap_mutation.py` ships a parametrized harness for
Modelos 130/131/202/303 but covers only ONE sub_op formula per
modelo:

| Modelo | sub_op-bearing casillas | Harness-covered |
|---|---|---|
| 130_2025 | 03, 07, 11, 14, 17, 19 | 03 only |
| 131_2025 | 13, 15, 17 | 15 only |
| 303_2025 | 64, 69 | 69 only |
| 202_2025 | 32 (4-deep nest) | 32 outer swap only |

The uncovered chains include Modelo 130's `sub_op(sub_op(04,05),06)`
at casilla 07 and 131's `sub_op(sub_op(07,08),09)` at casilla 13 —
exactly the Kent-visible cuota-chain formulas the harness is named
to protect.

**Fix**: expand parametrization so every sub_op-bearing casilla
across 130/131/303 is tested, not just one exemplar per modelo.

### H2 (stream 2) — Modelo 200 entirely absent from mutation harness

`modelo_200_2024.py` line 141 carries a 4-level `sub_op` nest
`sub_op(sub_op(sub_op(sub_op(00592,00599),...),...),...)` — strictly
deeper than Modelo 202's chain. Modelo 200 is IS annual (larger Kent
liability than 202 trimestral) and is the most swap-sensitive surface
in the codebase. Harness docstring names "four highest-Kent-harm
modelos" but 200 was swapped out for 202 silently.

**Fix**: add Modelo 200 casilla 00611 to the harness parametrization.

### H3 (stream 2) — LIRPF art. 103 wrongly cited for cuota diferencial

`test_modelo_100_summary_2025.py::test_external_worked_example_lirpf_art_67_and_77`
cites `LIRPF art. 103` as the source of
`0720 = 0698 - 0699 - 0700` (cuota diferencial subtracting
retenciones and pagos a cuenta). LIRPF (Ley 35/2006) art. 103 is
titled "Liquidaciones provisionales" — AEAT's administrative
liquidation power, NOT the cuota diferencial formula. The correct
statutory source is **art. 79** (cuota líquida total) combined with
**art. 99** (pagos a cuenta). Arts. 67 and 77 (cuota íntegra
estatal / autonómica) ARE correctly cited.

Same wrong-attribution pattern as the wave 59c Modelo 202 23% error.

**Fix**: replace `art. 103` references with `arts. 79 + 99` and
re-verify the cited article's plain text supports the scenario.

### H4 (stream 2) — RIRPF art. 110.1.b subsection misattribution

`test_modelo_130_2025.py::test_external_worked_example_rirpf_art_110`
docstring cites `art. 110.1.b` for the 20% pago-fraccionado rate.
In RD 439/2007 (RIRPF) art. 110:

- **110.1.a** → 20% (estimación directa)
- **110.1.b** → 2% (actividades agrarias)
- **110.1.c** → módulos

The parent article (110) is correct; the arithmetic checks out;
only the subsection pointer is inverted. Low blast radius but
indistinguishable from the 202/100 citation-accuracy failure
mode unless explicitly fixed.

**Fix**: `110.1.b` → `110.1.a` in the docstring.

### H5 (stream 4) — Exec records missing for waves 59a/b/c + 61a–f

`.vault/exec/2026-04-20-pdf-import/` contains phase-1..6 summaries
but no per-wave step records for 59a/59b/59c or 61a/61b/61c/61d/
61e/61f. Wave 60 stream 3 L3 flagged this; wave 61 did not close
it. The vaultspec pipeline contract (`.vault/exec/{feature}/
{step}.md`) is violated for nine consecutive waves.

**Fix**: ship a consolidated wave-59/61 step-record bundle OR
explicitly document the per-wave-step deferral in the ADR with
a rationale and a catch-up commitment.

## MEDIUM findings

- **M1 (stream 4)**: Wave 48 audit doc H3 status row still reads
  `DEFERRED | wave 57+ (partial mitigation ...)` despite
  waves 57a/b and 59c anchoring 11/14 rulesets. Wave 61b updated
  the ADR but did not refresh the wave-48 audit-doc row.
  **Fix**: update row 50 of wave-48 doc to `PARTIAL — wave 59c
  (c36f9b0) anchored 11/14 rulesets; 130_2025 + 100_summary_2025
  closed in wave 61c (d30c530); 303_2024 remains (wave 63+)`.

## LOW findings

- **L1 (stream 1)**: Modelo 390 docstring at
  `test_modelo_390_2025.py:96` still reads "96 cuotas repercutidas
  = 42 000 (sum of quarterly 03+06+09)" — imprecise, since 96
  aggregates Modelo 390's OWN sub-totals. Carried from wave 60 L1.
- **L2 (stream 2)**: `test_operand_swap_mutation.py` 202 docstring
  describes the outer swap as "a sign flip of the innermost chain" —
  the swap actually negates the OUTER subtraction only. Assertion
  is correct; prose is imprecise.
- **L3 (stream 3)**: `QuarterlyGenParams.thousands_sep` accepts any
  single char (`Field(min_length=1, max_length=1)`). A digit or
  comma would break rendering. Tighten with
  `pattern=r"^[.  ]$"`.
- **L4 (stream 3)**: `test_thousands_sep_reaches_draw_casilla_box`
  is misleadingly named — never calls `draw_casilla_box` or
  `generate`, only tests `format_amount`. Either rename or thread
  through `generate()`.
- **L5 (stream 3)**: Hyphenated-label test relies on implicit
  pdfplumber top-to-bottom ordering (drawn at `y-30mm` then
  `y-35mm`). Add a one-line comment documenting the y-ordering
  invariant.
- **L6 (stream 4)**: `docs/coverage/modelos.md` row 15 Modelo 130
  `declaración import` cell reads `✅ (2025 MVP)` despite both
  130_2024 + 130_2025 shipping. Should read `✅ (2024 + 2025 MVP)`.
- **L7 (stream 1)**: No exec records for waves 59a/b/c per the
  vaultspec pipeline contract — escalated to HIGH H5 in stream 4.

## Remediation plan — wave 63

- **Wave 63a** (citation accuracy — HIGH H3 + H4):
  `art. 103` → `arts. 79 + 99` in Modelo 100 summary test;
  `110.1.b` → `110.1.a` in Modelo 130 test. Verify each new
  citation's plain text supports the scenario arithmetic.
- **Wave 63b** (mutation harness breadth — HIGH H1 + H2):
  extend parametrization to every sub_op-bearing casilla across
  Modelos 130/131/200/303. Target: ~12 additional parametrized
  cases.
- **Wave 63c** (audit-trail refresh — MEDIUM M1):
  update wave-48 doc H3 row; fix `modelos.md` row-15 column drift.
- **Wave 63d** (LOW cleanups — L1/L2/L3/L4/L5):
  390 docstring; 202 operand-swap docstring; `thousands_sep`
  pattern validator; rename string-layer threading test;
  y-ordering comment.
- **Wave 63e** (exec records — HIGH H5):
  either consolidated wave-59/61 exec-record bundle OR explicit
  ADR-documented deferral with rationale. Decide in the wave 63e
  opening commit.

Each sub-wave ships with its own audit-loop per the established
exhaustive-audit contract. Wave 64 audit loop follows.
