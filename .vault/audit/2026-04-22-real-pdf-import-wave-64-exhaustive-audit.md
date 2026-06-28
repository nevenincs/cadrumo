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
---

# real-pdf-import — wave 64 exhaustive audit

## Scope

Sixth cycle of the exhaustive-audit pattern. Four parallel streams
verify wave 63a–d remediations and deep-audit citation accuracy
across ALL external-anchored tests after repeated miscite patterns
(wave 59c → 61a → 63a all surfaced citation errors).

Commit audited: `65e5643` (wave 63a+b+c+d).

| Stream | Verdict | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| 1 wave 63 remediation verification | PASS | 0 | 0 | 1* |
| 2 mutation-harness rigor | REVISION REQUIRED | 0 | 1 | 1 |
| 3 citation-accuracy re-audit (all 12 anchors) | REVISION REQUIRED | **5** | 0 | 0 |
| 4 docs + audit-trail + deferred H5 | REVISION REQUIRED | 2 | 1 | 3 |

*Stream 1 noted narrative "15 cases" in commit message vs 12
parametrize + 1 standalone + 2 helper-integrity = 15 total tests.
Not a regression.

**Total open: 7 HIGH, 2 MEDIUM, 5 LOW.**

## Closure status (updated 2026-04-22, wave 66)

| Finding | Status | Closing wave |
|---|---|---|
| H1 130_2025 RIRPF 110.1 subsections inverted | CLOSED | wave 65a (`ab808d2`) |
| H2 130_2024 art. 110.2 → 110.1.c | CLOSED | wave 65a (`ab808d2`) |
| H3 131_2025 art. 110.4/110.2 → 110.1.b/.c | CLOSED | wave 65a (`ab808d2`) |
| H4 202_2025 LIS 24% → 25% + 23% narrative | CLOSED | wave 65a (`ab808d2`) |
| H5 100_summary art. 77 → 73 | CLOSED | wave 65a (`ab808d2`) |
| H6 modelos.md provenance overstated | CLOSED | wave 65b (`ab808d2`) |
| H7 wave 62 H5 exec-record deferral soft | PARTIAL | wave 65d (`ab808d2`) named artefact path + gate-anchored deadline; structural deferral (no issue/date) re-surfaced as wave 66 H1 (tracked wave 67d) |
| M1 harness "both non-zero" invariant inaccurate | CLOSED | wave 65b (`ab808d2`) |
| M2 ADR missing citation-accuracy checklist | CLOSED | wave 65c (`ab808d2`) |
| L1 commit-message count narrative | CLOSED | wave 66 audit acknowledges count is correct |
| L2 9 uncovered sub_op chains | OPEN | re-cited as wave 66 M2; tracked wave 67f |
| L3 wave 48 H3 "wave 63+" vague | OPEN | folds into wave 67d umbrella deferral tracking |
| L4 wave 63 commit dropped 65e plan | CLOSED-by-rewording | wave 66 audit re-cites planning drift; wave 67 acknowledges via concrete issues |
| L5 other citations clean reference | N/A | informational only |

## HIGH findings

### H1–H5 (stream 3) — FIVE citation errors across 5 test files

Stream 3 re-audited every `test_external_worked_example_*` method
and WebSearch-verified each cited article's plain-text role against
BOE / supercontable / iberley. Five citation errors remain after
wave 63a's two fixes:

#### H1 — `test_modelo_130_2025.py` RIRPF 110.1 subsection roles inverted

Wave 63a fixed 110.1.b → 110.1.a for the 20% rate (correct).
But the docstring parenthetical now reads:
> "art. 110.1.b is the 2% agraria rate, art. 110.1.c covers módulos"

Per BOE RD 439/2007 art. 110.1:
- **110.1.a**: 20% estimación directa ✓ (correctly cited)
- **110.1.b**: 4%/3%/2% estimación objetiva (módulos) — NOT agraria
- **110.1.c**: 2% agrícolas/ganaderas/forestales/pesqueras

**Fix**: swap the parenthetical — `110.1.b covers módulos (estimación objetiva); 110.1.c is the 2% agraria rate`.

#### H2 — `test_modelo_130_2024.py` cites "art. 110.2" for 2% agraria

Line 158/173 of the 2024 ruleset (which 2025 clones from) reads
"art. 110.2 fixes the 2% rate on agrícola/ganadera/forestal/
pesquera". Art. 110.2 is the 60% reduction clause; the 2% agraria
rate lives in **art. 110.1.c**.

**Fix**: replace `110.2` → `110.1.c` in citation strings at those line ranges.

#### H3 — `test_modelo_131_2025.py` cites "art. 110.4" and "art. 110.2"

Both wrong. Art. 110 has no `.4` subsection fixing the 2% módulos
rate. Correct mapping for Modelo 131 (módulos) is **art. 110.1.b**;
the 2% agraria is **art. 110.1.c**.

**Fix**: replace `110.4` → `110.1.b` and `110.2` → `110.1.c`.

#### H4 — `test_modelo_202_2025.py` narrative says "5/7 of 24%"

LIS art. 29.1 fixes the general tipo at **25%** (has been since
Ley 27/2014 took effect). Wave 61a narrative said "24%". The
arithmetic 5/7 × 25 rounded = 17% is correct; the "24%" narrative
is a factual error.

Additionally, lines 105–109 dismiss 23% as "not a valid rate in
any reading of art. 40.3". 23% IS in art. 40.3 LIS as the importe
mínimo threshold for large entities (not a tipo de gravamen). The
dismissal over-reaches and should be softened.

**Fix**: `24%` → `25%`; reword the 23%-dismissal to clarify it's not
a tipo de gravamen but may be an importe-mínimo floor for large
entities.

#### H5 — `test_modelo_100_summary_2025.py` art. 77 role is wrong

Lines 113–114 cite `LIRPF art. 77 ("Cuota íntegra autonómica")`.
Per BOE Ley 35/2006, LIRPF art. 77 is actually `Cuota líquida
autonómica total` (post-deduction). Cuota íntegra autonómica lives
in **art. 73** (general) / art. 74 (tarifa).

The arithmetic `0595 (LIRPF art. 67 + 77)` pairs cuota íntegra
estatal with cuota líquida autonómica — semantically incoherent.

**Fix**: `art. 77` → `art. 73` (cuota íntegra autonómica general)
or `art. 74` (tarifa autonómica).

### H6 (stream 4) — Coverage provenance overstates

`docs/coverage/modelos.md:35` claims "13 external-anchored worked
examples" and "15 parametrized cases"; repo has **12** anchor test
files + **12** `pytest.param` cases. Either bump production to
match OR correct the numbers downward.

### H7 (stream 4) — Wave 62 H5 deferral has no tracked target

Commit `65e5643` says deferral is "pending a vaultspec-pipeline
catch-up commit" but no artefact (ADR, issue, task file, step
record) carries that commitment. Wave 60 L3 → wave 62 H5 has
escalated twice with no named closing wave. `grep -r "catch-up"
.vault/` returns zero hits.

**Fix**: either ship the exec-record bundle now, or add a named
wave/issue reference and a hard deadline.

## MEDIUM findings

- **M1 (stream 2)**: Harness docstring invariant "both non-zero"
  is inaccurate for `modelo_303.2025:casilla_45` and
  `modelo_202.2025:casilla_32` — in both, the outer sub_op rhs
  is 0. Detection still succeeds because the other operand is
  large, but the invariant statement misleads future maintainers.
- **M2 (stream 4)**: ADR `External-anchoring convention` section
  does not mention the citation-accuracy failure mode (three
  independent miscites in 12 anchors). Add an author checklist:
  "quote the cited article's plain-text title; confirm subsection
  letter matches the rate/role; WebSearch-verify before landing".

## LOW findings

- **L1 (stream 1)**: Commit-message narrative says "12 parametrized
  cases" in one sentence and "15 cases total" in another. Count is
  correct (12 param + 1 standalone + 2 helpers = 15 total tests)
  but narrative is confusing.
- **L2 (stream 2)**: 9 uncovered sub_op chains remain —
  `modelo_130_2024` (6 chains, clone of 2025), `modelo_303_2024`
  (2 chains, clone), `modelo_111_2025` (casilla 30),
  `modelo_115_2025` (casilla 06), `modelo_123_2025` (casilla 11),
  `modelo_100_summary_2025` (one top-level sub_op), and
  `modelo_390_2025` (casilla 97). Not in wave 62 scope but
  tracked for completion.
- **L3 (stream 4)**: Wave 48 H3 row says "(wave 63+)" which is
  vague — mirrors the H7 deferral-without-issue anti-pattern.
- **L4 (stream 4)**: Wave 63 commit message silently dropped the
  planned `wave 63e` slot without an audit-trail replacement
  sentence.
- **L5 (stream 3)**: No other citation errors found in
  test_modelo_111_2025, test_modelo_115_2025, test_modelo_180_2025,
  test_modelo_123_2025, test_modelo_200_2024, test_modelo_303_2025,
  test_modelo_390_2025 — clean reference set for the citation fix.

## Remediation plan — wave 65

- **Wave 65a** (citation accuracy — HIGH H1–H5, highest priority):
  fix all 5 test docstrings to cite the correct article/subsection.
  WebSearch-verify each cited instrument's plain-text role before
  committing.
- **Wave 65b** (provenance reconciliation — HIGH H6, MEDIUM M1):
  correct modelos.md provenance line; fix harness docstring
  invariant.
- **Wave 65c** (ADR author checklist — MEDIUM M2):
  add a citation-accuracy author checklist to the ADR `External-
  anchoring convention` section.
- **Wave 65d** (deferral target — HIGH H7):
  either ship consolidated wave-59/61/63 exec-record bundle OR
  create a concrete issue + add ADR note naming the closing wave.
- **Wave 65e** (harness breadth extension — LOW L2):
  add parametrization for the 9 uncovered sub_op chains.

Each sub-wave ships with regression tests. Wave 66 audit follows.
