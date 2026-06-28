---
tags:
  - '#plan'
  - '#operator-workflows-expansion'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-operator-workflows-expansion-research]]"
  - "[[2026-04-25-operator-workflows-expansion-adr]]"
---

# `operator-workflows-expansion` plan: cli-integration-coverage

Implementation plan for wgergely/aeat#340. Drives the ten new test
classes documented in the ADR.

## Phase 1 — file edits

`tests/integration/test_kent_workflows.py` is the only source file
modified. Additions:

1. New module-level imports (within the existing import block):
   - `Modelo100GenParams`, `generate as generate_modelo_100` from
     `tests.fixtures.pdf_corpus.l3_synthetic._generators.modelo_100_generator`
   - `Modelo303GenParams`, `generate as generate_modelo_303` from
     `tests.fixtures.pdf_corpus.l3_synthetic._generators.modelo_303_generator`
   - `QuarterlyGenParams`, `generate as generate_quarterly` from
     `tests.fixtures.pdf_corpus.l3_synthetic._generators._generic_quarterly_generator`

2. Per-modelo helper-rendering functions (private to the test module):
   - `_synth_modelo_100_summary_pdf`
   - `_synth_quarterly_pdf` (general — modelo + label-map + values)
   - `_synth_annual_pdf` (general — modelo + label-map + values, annual period)
   - `_synth_modelo_303_pdf`
   Each helper takes `tmp_path` plus modelo-specific kwargs and returns
   the on-disk Path. Mirrors the existing `_synth_modelo_130_pdf`
   pattern.

3. Per-modelo label maps inlined as module-level constants (mirroring
   the existing `aeat.adapters.inbound.declaracion.test_quarterly_extractors` references
   so the values stay aligned with parser ground truth).

4. Per-modelo happy-path values that satisfy the formulas in each
   ruleset. Derived from the formula bodies catalogued in research:
   - **111**: 03=1000, 06=500, 08=1000, 09=190 (19% of 1000), 11=1000,
     12=190 (19% of 1000), 15=100, 18=50, 28=2030 (sum), 29=0, 30=2030.
     Apartado-perceptor counters (01, 02, 04, 05, 07, 10, 13, 14, 16,
     17) carry plausible non-zero counts.
   - **115**: 02=10000, 03=1900 (19% of 10000), 04=0, 05=0, 06=1900.
     01=2.
   - **123**: 01=2, 02=3, 03=5 (sum), 04=1500, 05=8000, 06=9500 (sum),
     07=285, 08=1520, 09=1805 (sum), 10=0, 11=1805 (09-10).
   - **131**: 01=10000, 02=200, 03=5000, 04=100 (2% of 5000), 05=2000,
     06=40 (2% of 2000), 07=340 (sum 02+04+06), 08=0, 09=0, 10=340
     (07-08-09), 11=0, 12=0, 13=340 (10-11-12), 14=0, 15=340 (13-14).
   - **180**: 01=5, 02=48000, 03=9120 (19% of 48000), 04=0.
   - **200**: full 16-casilla set with arbitrary values; verdict will
     be UNVERIFIABLE regardless of formula coherence (no 2025 ruleset).
   - **202**: 16=100000, 17=25, 18=25000 (25% of 100000), 27=0,
     28=2500, 30=0, 32=22500 (18-27-28-30), 33=0, 34=22500 (max(32,33)).
   - **303**: full 33-casilla set computed against the formula chain
     in research findings (apartado 1: 4% / 10% / 21% rates plus the
     resultado chain 44/45/64/66/69/71). Casilla 65=100 (100%
     attributable to estado), 67=0.
   - **390**: full 15-casilla set; 100, 101 sum into 104; 96-104=105;
     105+108+109=190.
   - **100-summary**: full 27-casilla set; 0550+0551+0560+0561=0595;
     0620+0622=0630; max(0595-0630, 0)=0698; 0698-0699-0700=0720.

5. Ten new test classes per the ADR.

## Phase 2 — local gates

In order:
1. `just lint` — ruff format + ruff check + relative-imports check.
2. `just typecheck` — `ty` strict mode.
3. `just test` — pytest unit tier (the new tests run here).
4. `just test-cov` — confirm `src/aeat` coverage >= 60%.
5. `just hooks` — prek hooks (large files, EOL, conventional commits, etc.).

If any gate fails, fix at root and re-run. No skips.

## Phase 3 — docs

`docs/coverage/modelos.md` updated to flip the CLI-integration column
(or footnote) from missing -> present for the ten newly-covered modelos.

## Phase 4 — vault exec records

For each meaningful chunk of work (research, ADR, plan, implementation,
test-suite green, docs), persist a step record under
`.vault/exec/2026-04-25-operator-workflows-expansion/` and a final phase
summary at
`.vault/exec/2026-04-25-operator-workflows-expansion/2026-04-25-operator-workflows-expansion-phase1-summary.md`.

## Phase 5 — code review

`vaultspec-code-review` skill invoked on the changed files.

## Phase 6 — commit + branch

Conventional-commits, recommended sequence (each commit independently
green):

1. `test(integration): TestKentImportsModelo303Declaracion (#340)` -
   prove the formula-heavy path works.
2. `test(integration): Modelo 100-summary + Modelo 200 import classes (#340)` -
   the special-case modelos.
3. `test(integration): IRPF-withholding family Modelos 111/115/123/131/180 (#340)`.
4. `test(integration): Modelos 202 + 390 import classes (#340)`.
5. `docs(coverage): modelos.md CLI-integration column for #340`.

## Plan review

Reviewed against:

- CLAUDE.md core mandates - no new abstractions, no comments
  describing changes, no unrelated edits.
- `.claude/rules/aeat-project-mandates.md` - no mocks/fakes/stubs/skips,
  pytest-only, real CLI surface.
- Issue #340 DoD - all 6 acceptance bullets covered.
- Existing Modelo 130 template at line 97 - new classes mirror its
  structure (fixture intake, rendered PDF, CliRunner.invoke,
  stable-marker assertions).
- No-mocks discipline - confirmed.
- Module marker preserved - D8 in ADR.
- Stable markers only - D5 in ADR.
- Spanish path on every modelo - mandatory case 2.
- Coverage 60% on `src/aeat` - addition raises it.

Plan accepted for execution.
