---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:a108d84f74fc97a8eb25d57a5955152c463fd35a9766a6b14bb5c1b89c54eeca'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
---
# S58 Filing Evidence and Calculation Authority Audit

## Review outcome

Luna verdict: **APPROVE**.

The approved v9 candidate closes S58's immutable filing-evidence, revision-aware calculation, Orden/formula, amendment, import/export, prorrata, and legacy-removal scope without retaining compatibility surfaces. The canonical homes remain the domain calculation and filing-evidence models, the application model lifecycle, and the registry-backed formula/Orden resolution paths; no duplicate producer or fallback authority was accepted.

## Grounding

Bounded `vaultspec-rag` discovery (eight-result cap) located this audit, the governing plan, and related architecture records. Its code endpoint reflected the stale landed/main snapshot rather than the approved v9 candidate, so exact production-code grounding fell back to the approved v9 source tree and the reviewer's recorded command evidence. This fallback is explicit and does not broaden the reviewed scope.

## Final verification evidence

- Engine, Orden, formula, and amendment lane: **73 passed**.
- Evidence, import, export, prorrata, and legacy-removal lane: **156 passed**, plus **one unchanged translated-message assertion** verified separately.
- Exact quickfile help and integration lane: **2 passed**.
- Focused core `basedpyright`: **0 errors, 0 warnings**.
- Ruff, `compileall`, and `git diff --check`: clean.
- AST call census and retired-surface scans: clean; no legacy compatibility surface remains.

## Baseline exclusions

Five failures were outside the S58 acceptance verdict and remain unverified by the reviewer: four pre-existing prorrata-especial advisory-emission failures and one parent-only M390 carry-disposition failure. They are recorded as baseline exclusions, not as S58 passes and not as resolved by this audit.

## Canonical-home reconciliation

The reviewed candidate removes redeclared and legacy producer paths instead of adapting callers through compatibility shims. Filing evidence is carried by the canonical revision content, formula and Orden resolution refuse unresolved authority, quickfile flows thread the same evidence contract, and prorrata decisions remain scoped to their canonical calculation inputs. Retired-name and AST scans found no contradictory legacy call surface in the modified scope.

## Decision

S58 is accepted at approved v9. The exact evidence above supersedes every earlier provisional PASS claim or count for this step.
