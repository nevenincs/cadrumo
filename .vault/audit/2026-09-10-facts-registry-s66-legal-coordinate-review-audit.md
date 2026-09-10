---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:09b4de0725887eabdf11d4b273b3cc23fd72b1aff3bfdbb7873cf6030fe16e14'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# `facts-registry` audit: `S66 legal-coordinate review`

## Scope

Audited S66's retención and activity-selector applicability-coordinate migration. Checked canonical authority use, transaction date precedence and refusal, units, legal-reference routing, consumer propagation, and directly affected callers and tests. The focused pytest receipt was unavailable because of host CPU starvation, so test execution is not treated as a pass.

## Findings

### selector-caller-completeness | high | Required coordinate initially broke Art. 109 selector tests

`tipo_actividad_code_set` made `effective_date` mandatory while three assertions in `test_art109_base_excludes_subvenciones.py` still used the former zero-argument call. This produced a runtime `TypeError`, preventing the directly affected test module from running. Remediated during review: all three calls now supply `_PERIOD.end_date`; the final whole-tree caller scan found no remaining omission.

## Recommendations

Keep required-coordinate API migrations accompanied by a whole-tree call-site scan, including test-only callers.
