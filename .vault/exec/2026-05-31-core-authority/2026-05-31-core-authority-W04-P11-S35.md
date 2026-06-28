---
step_id: S35
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W04.P11.S35 — IVA rate mapping BOE cross-reference (MERGE-013)

## Outcome

**Finding: intentional documented divergence — NOT an oversight.**

## Evidence

The action tracker references `domain/iva/_classification.py _IVA_RATE_TO_VAT_KIND (3 entries)` — this file path is incorrect in the tracker. Actual locations via ripgrep:

- `src/aeat/domain/iva/_invoice_classification.py:63` — 5-entry mapping with explicit docstring
- `src/aeat/domain/invoices/_enums.py:76` — 3-entry mapping for a different purpose

### 5-entry mapping (`_invoice_classification.py:63`)
```
RATE_0 → ZERO
RATE_4 → SUPER_REDUCED
RATE_10 → REDUCED
RATE_21 → GENERAL
EXEMPT → EXEMPT
```
Docstring: "NOT_SUBJECT is intentionally absent — operations outside the scope of IVA do not carry a rate-tier classification."

### 3-entry mapping (`_enums.py:76`)
```
RATE_4 → SUPER_REDUCED
RATE_10 → REDUCED
RATE_21 → GENERAL
```
Purpose: `iva_rate_percentage()` uses this table ONLY for the three non-trivial rates. RATE_0 returns `Decimal("0")` hardcoded (line 109). EXEMPT and NOT_SUBJECT return `None` (line 111-112). The table is never consulted for these members.

### BOE cross-reference
Spanish IVA rates per Ley 37/1992 art. 91 (modified per RDL 8/2023): general 21%, reduced 10%, super-reduced 4%, zero-rated operations. EXEMPT operations (art. 20-26), NOT_SUBJECT operations (art. 7-9) do not carry a rate tier. Both mappings are BOE-correct for their respective use cases.

**The 3-entry vs 5-entry difference is intentional: the 3-entry table is for percentage resolution (where RATE_0, EXEMPT, NOT_SUBJECT are handled by earlier branches), and the 5-entry table is for VAT classification (where EXEMPT maps to its own category). No consolidation is warranted.**

## MERGE-013 disposition

MERGE-013 as specified (consolidate to `domain/iva/_classification.py` with a coverage test) is based on a faulty audit finding. The two mappings serve different domain contracts and should remain separate. Recommend closing MERGE-013 as "wontfix with documented rationale" in a follow-up plan.

## Files touched

None (BOE cross-reference / audit step).
