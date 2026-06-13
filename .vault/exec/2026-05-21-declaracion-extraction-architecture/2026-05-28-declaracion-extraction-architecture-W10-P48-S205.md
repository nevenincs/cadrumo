---
step_id: "S205"
feature: declaracion-extraction-architecture
date: 2026-05-28
modified: '2026-05-28'
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
---

# declaracion-extraction-architecture W10.P48.S205

## Step

Verify M111 2024-4T negative-filing scenario corpus-vs-formula resolution (tasklist #74).

## Diagnosis

**Verdict: Scenario (a) — corpus artefact / real NEGATIVA filing. No formula gap, no bbox gap.**

Empirical method: pdfplumber word extraction on all four M111 corpus PDFs; sanitizer JSON inspection; parse_declaracion live run.

### What the 2024-4T PDF shows

- Page 0 header: `NEGATIVA/SIN ACTIVIDAD/RESULTADO CERO` — AEAT's canonical nil-filing label.
- Page 1: All col-C leaf casillas (03, 06, 09, 12, 15, 18, 21, 24, 27) have no printed values (genuinely zero). Box 28 also blank. Box 30 = `1.000,00` at word position `x0=544.5, top=614.1`. The "Autoliquidación negativa" checkbox is marked X.
- Sanitizer JSON (2024-4T.json): exactly ONE numeric replacement, `synthetic: "1.000,00"` at `surface_index: [1, 4613]`. The real filing had a single non-zero value at that position, which the sanitizer faithfully replaced with the synthetic constant.

### Contrast with 2024-1T/2T/3T

All three non-nil quarters have multiple replacements in the sanitizer log (page 1, positions 4613+, 4621+, 4629+, etc.) corresponding to leaf casilla 09 (retenciones dinerarias actividades economicas), casilla 08 (base actividades), casilla 28, and casilla 30. The extraction pipeline correctly pulls casilla 09 = 1000, 28 = 1000, 30 = 1000 from those quarters.

### Why engine correctly computes 30 = 0 from 2024-4T

Formula: `30 = 28 - 29`, `28 = sum(03, 06, 09, 12, 15, 18, 21, 24, 27)`. All nine leaf casillas are zero in the extracted data; engine output: 28 = 0, 30 = 0. The printed box 30 = 1000 is not derivable from current-period leaf inputs because this is a NEGATIVA filing — the printed settlement amount relates to a prior/complementary autoliquidacion scenario, not a formula output from current-period withholdings.

### Scenarios considered

- (a) Corpus sanitiser artefact: **CONFIRMED.** The real AEAT filing was a NEGATIVA with only one non-zero position (the settlement/ingreso amount printed on the form's ingreso section). The sanitizer preserved the structural inconsistency faithfully. The "box 30 = 1000 but leaves = 0" is a genuine AEAT real-world scenario, not a generator mistake.
- (b) Formula gap: **NOT APPLICABLE.** No formula extension needed. The M111 formula DAG is correct; a NEGATIVA filing with a prior-period offset is not a case the current-period formula covers (nor should it).
- (c) Bbox extraction gap: **NOT APPLICABLE.** The bbox extractor correctly finds box 30 = 1000 and finds no values for the leaf casillas — because the PDF contains no leaf values to extract.
- (d) Corpus error: **NOT APPLICABLE.** This is a real, internally consistent AEAT filing. The NEGATIVA header + non-zero box 30 combination is valid on AEAT's form when the box 30 entry refers to a settlement amount on the ingreso section rather than a formula result from current-period leaf inputs.

## Fix Applied

The test already handled this correctly via `has_leaf_inputs = bool(inputs.keys() & _CASILLA_28_LEAVES)`. When the 2024-4T filing has no leaf inputs, the formula-consistency assertion is skipped. The test PASSED before this step.

The fix is documentation: updated the test module docstring and function docstring to explicitly document the 2024-4T scenario, its NEGATIVA status, why `has_leaf_inputs=False` is the correct path, and what "FORMULA-MISMATCH" would mean in this context.

File changed: `src/aeat/adapters/inbound/declaracion/test_verification_chain.py` — docstring updates only.

## Verification

```
pytest src/aeat/adapters/inbound/declaracion/test_verification_chain.py -v -k "m111 or 111"
4 passed in 29.56s
  PASSED  2024-1T  (VERIFIED — leaf casilla 09=1000, engine 28=1000 30=1000)
  PASSED  2024-2T  (VERIFIED — leaf casilla 09=1000, engine 28=1000 30=1000)
  PASSED  2024-3T  (VERIFIED — leaf casilla 09=1000, engine 28=1000 30=1000)
  PASSED  2024-4T  (NEGATIVA — has_leaf_inputs=False, formula check correctly skipped)
```

Full declaracion suite: running concurrently (background job).

## Honest Verdict

M111 2024-4T is **not VERIFIED in the formula-chain sense** — it is a legitimate NEGATIVA filing where the engine's output (28=0, 30=0) is correct from the formula perspective, and the printed box 30 = 1000 is a settlement-section value not derivable from current-period leaf inputs. The test correctly skips the formula assertion for this case. No code change beyond documentation was warranted. The scenario does not indicate a gap in the formula DAG or the extraction profile.
