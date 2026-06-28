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
  - "[[2026-04-22-real-pdf-import-wave-62-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-64-exhaustive-audit]]"
---

# real-pdf-import — wave 66 exhaustive audit

## Scope

Seventh cycle of the exhaustive-audit pattern. Four parallel streams
verify wave 65a–d remediations.

Commit audited: `ab808d2` (wave 65a+b+c+d).

| Stream | Verdict | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| 1 wave 65 remediation verification | PASS | 0 | 0 | 0 |
| 2 deep citation re-audit (12 anchors) | REVISION REQUIRED | **4** | 0 | 1 |
| 3 ADR + deferral + audit-trail rigor | REVISION REQUIRED | 3 | 1 | 1 |
| 4 test suite + coverage gaps | PASS (+ notes) | 0 | 1 | 2 |

Stream 2 delivered 4 additional citation-accuracy HIGHs (wave 65a
itself introduced regressions in test_modelo_100_summary_2025 by
confusing cuota íntegra vs cuota líquida articles; pre-existing
errors in test_modelo_111_2025, test_modelo_200_2024; and a
ruleset-level cross-cutting concern for the 100.3.a citation in
modelo_115/180 production code).

**Total open: 7 HIGH, 2 MEDIUM, 4 LOW.**

## Closure status (updated 2026-04-22, wave 70)

| Finding | Status | Closing wave |
|---|---|---|
| H1 exec-record deferral structurally soft | CLOSED | wave 68c (`fe8fa85`) filed issue #313 |
| H2 wave 64 audit doc missing closure table | CLOSED | wave 67a (`29a537e`) |
| H3 checklist bullet 5 not falsifiable | CLOSED | wave 67c (`29a537e`) rewrote grep-checkable |
| H_S2_1 100_summary cuota íntegra/líquida miscite | CLOSED | wave 67a (`29a537e`) arts. 62/67/73/77/79/99 |
| H_S2_2 111 RIRPF 105.1 + 100.3.c miscite | CLOSED | wave 67a (test) + wave 69a (`4fa75da`) production |
| H_S2_3 200 LIS art. 125 miscite | PARTIAL | wave 67a (test) + wave 71c production |
| H_S2_4 RIRPF 100.3.a cross-cutting | CLOSED | wave 67g (`fe8fa85`) |
| M1 checklist silent on statute-drift | CLOSED | wave 67c (`29a537e`) added bullet 6 |
| M2 wave 64 L2 untracked | CLOSED | wave 68c (`fe8fa85`) filed issue #314 |
| L1 390 docstring imprecision | CLOSED | wave 63d (prior) |
| L2 202 operand-swap docstring | CLOSED | wave 63d (prior) |
| L3 wave 48 H3 vague | CLOSED | wave 63c + 67a |
| L4 wave 63 commit dropped 65e plan | CLOSED-by-rewording | wave 66 + 70 retrospectives |

## HIGH findings

### H1 (stream 3) — Exec-record deferral still structurally soft

Wave 65d re-worded the "vaultspec pipeline contract violation"
deferral into an ADR section naming a concrete artefact path
(`.vault/exec/2026-04-20-pdf-import/2026-04-22-pdf-import-audit-loop-summary.md`)
and gate-anchored deadline ("before EPIC #305 close-out PR").
Stream 3 ruled this PARTIAL:

- No GitHub issue number.
- No calendar date.
- "before EPIC close-out" is unfalsifiable until close-out itself.

This is the same anti-pattern wave 64 H7 flagged — re-worded,
not structurally fixed.

**Fix**: create a concrete `gh` issue under EPIC #305 titled
`chore: back-fill pdf-import exec records for waves 59a/b/c + 61a–f + 63a–d + 65a–d + 67a–f`,
reference it from the ADR, and keep the gate-anchored deadline
as a secondary constraint.

### H2 (stream 3) — Wave 64 audit doc missing wave-66 closure-status table

Wave 63c refreshed the wave 48 audit doc's H3 row from
`DEFERRED` → `PARTIAL` when later waves closed findings. The same
contract applies to the wave 64 doc — stream 1 confirmed waves 65a–d
closed H1–H7 + M1–M2 of wave 64, yet the wave-64 doc has no
closure-status section or row annotations to that effect. A reader
opening `.vault/audit/2026-04-22-real-pdf-import-wave-64-exhaustive-audit.md`
still sees 7 open HIGHs.

Since the exec-record deferral rationale rests on "audit docs are
the load-bearing pipeline artefact", this gap is load-bearing too.

**Fix**: add a `## Closure status (updated 2026-04-22, wave 66)`
table to the wave 64 doc, one row per finding (H1..L5) with the
closing wave + SHA.

### Stream 2 findings — 4 more citation-accuracy errors

#### H_S2_1 — test_modelo_100_summary_2025 art. 67/79 roles wrong (wave 65a regression)

Wave 65a "fixed" the Modelo 100 summary citation but introduced TWO
new errors:
- `art. 67` was cited for "Cuota íntegra estatal". Per BOE-A-2006-20764,
  art. 67 is **"Cuota líquida estatal"** (post-deduction); cuota íntegra
  estatal lives in **art. 62**.
- `art. 79` was cited for "Cuota líquida total". Per BOE, art. 79 is
  **"Cuota diferencial"**; cuota líquida estatal is art. 67 and cuota
  líquida autonómica is art. 77.

Closed in **wave 67a** (`HEAD`): docstring rewritten with correct
article-to-role mapping and the full citation-accuracy history
across waves 61c / 63a / 65a / 67a preserved for auditability.

#### H_S2_2 — test_modelo_111_2025 RIRPF art. 105.1 + 100.3.c wrong

- RIRPF art. 105 covers transmisiones de IIC, NOT premios en
  metálico. The 19% rate on premios derives from **LIRPF art. 101.7**
  implemented via **RIRPF art. 99** (threshold at art. 75.2.c).
- RIRPF art. 100 has **no sub-letters** in the consolidated text; the
  19% rate on arrendamientos lives in art. 100 para. 1.

Closed in **wave 67a**: test renamed from
`test_external_worked_example_rirpf_105` to
`test_external_worked_example_rirpf_99`; citations corrected to
LIRPF arts. 99/101.2/101.7 + RIRPF arts. 99/100.

#### H_S2_3 — test_modelo_200_2024 LIS art. 125 wrong

Wave 59c cited `art. 125` for the cuota-líquida arithmetic
`00621 = 00611 + 00619 - 00615`. Art. 125 is **"Autoliquidación e
ingreso de la deuda tributaria"** (procedural, not definitional).
Correct source: **LIS art. 30** ("Cuota íntegra" / cuota líquida).

Closed in **wave 67a**.

#### H_S2_4 — RIRPF art. 100.3.a cited across 115/180 ruleset + tests

Stream 2 flagged that RIRPF art. 100 has no sub-letter structure
in the consolidated text; the 19% rate lives in art. 100 para. 1
only. Current citations `100.3.a` in `modelo_115_2025.py:62-63`,
`modelo_180_2025.py:10/33/64-65`, `modelo_115_2024.py:3`, plus the
corresponding tests `test_modelo_115_2025.py:70/76/85/93` and
`test_modelo_180_2025.py:81/89/94` are all inconsistent with the
BOE consolidated text.

**Status: OPEN — tracked as wave 67g** (cross-cutting: production
ruleset `_CITATIONS` tuples + tests + the citation-string assertion
at `test_modelo_115_2025.py:70` all need coordinated update; the
wave-29 audit's prior acceptance of `100.3.a` should be re-verified
against current BOE text before committing the change).

### H3 (stream 3) — ADR checklist bullet 5 is not grep-checkable

Bullet 5 ("Run a WebSearch for the article + role string before
landing") is a process step that leaves no artefact. Four prior
miscites (59c / 61a / 63a / 65a) all presumably received some
verification yet shipped errors. Non-falsifiable process rules
are by definition weak.

**Fix**: re-frame bullet 5 as: "The exact quoted article title
from bullet 1 MUST appear as a literal string in the test
docstring. CI can grep for it." Make the enforcement grep-able.

## MEDIUM findings

- **M1 (stream 3)**: ADR checklist does not cover statute drift
  (e.g., a rate correct at authoring time that changes via Orden
  HAC/* amendment). Add a bullet requiring the quoted article's
  BOE consolidated-text date / version identifier to appear in
  the docstring next to the citation.

- **M2 (stream 4)**: Wave 64 L2 (9 uncovered sub_op chains) was
  tagged "wave 65e+" in the wave 64 doc but wave 65 silently
  dropped the 65e slot without a replacement issue / wave
  reference. Same anti-pattern as wave 64 L4 flagged about
  wave 63e. No GitHub issue carries the backlog.

## LOW findings

- **L1 (stream 3)**: ADR "External-anchoring convention" narrative
  (lines 164-166) still reads "11 of 14 in-scope rulesets have
  external anchors. The residual (130_2025, 100_summary_2025
  plus 303_2024) is tracked for wave 61c." Reality post-wave-65a:
  12 of 14 anchored; 130_2025 + 100_summary_2025 both shipped;
  only 303_2024 remains. Stale.

- **L2 (stream 4)**: Mutation-harness invariant "delta ≥ 0.02"
  is prose-only. The parametrized test body does not assert
  `abs(correct - swapped) >= 0.02`. A future author could add a
  case with delta=0.005 that clears the 0.01 audit tolerance but
  still detects — yet a 0.015 delta could silently regress past
  a loosened tolerance. Recommend adding a mechanical assertion.

- **L3 (stream 4)**: Wave 62 audit doc line 73 still references
  the pre-rename method name `test_external_worked_example_lirpf_art_67_and_77`.
  Historical record — correct to leave as-is for audit-trail
  integrity. Flagging for awareness only; no action.

## Remediation plan — wave 67

- **Wave 67a** (closure-status refresh — HIGH H2):
  add `## Closure status` table to wave 64 audit doc.
- **Wave 67b** (ADR narrative refresh — LOW L1):
  update the "11 of 14" line to "12 of 14 post-wave-65a; only
  303_2024 remains".
- **Wave 67c** (ADR checklist hardening — HIGH H3, MEDIUM M1):
  reframe bullet 5 as grep-checkable; add bullet 6 for BOE
  consolidated-text date.
- **Wave 67d** (exec-record issue — HIGH H1):
  `gh issue create` under EPIC #305 referencing the consolidated
  exec-record back-fill; link the issue in the ADR.
- **Wave 67e** (mutation-harness mechanical assertion — LOW L2):
  add `assert abs(baseline_value - mutated_value) >= Decimal("0.02")`
  inside the parametrized test body.
- **Wave 67f** (uncovered sub_op chains issue — MEDIUM M2):
  `gh issue create` under EPIC #305 listing the 9 chains.
- **Wave 67g** (RIRPF 100.3.a cross-cutting concern — stream 2 H_S2_4):
  re-verify art. 100 structure against BOE consolidated text; if
  `100.3.a` is confirmed invalid, coordinate a ruleset + tests
  update across modelo_115/180. Scope requires verification before
  action to avoid a sixth citation-error iteration.

Wave 67a shipped inline (100_summary, 111_2025, 200_2024 citation
fixes + mutation-harness delta assertion). Wave 67b–g queued.
Wave 68 audit loop follows.
