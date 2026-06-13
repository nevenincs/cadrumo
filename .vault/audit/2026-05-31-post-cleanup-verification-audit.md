---
tags:
  - '#audit'
  - '#post-cleanup-verification'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-22-schema-hardening-plan]]"
---

# post-cleanup-verification audit: standing-gates G1-G8

## Scope

Verification audit of commits ef1d12738, 661cec2d4, 84ad2414c, 14223f3eb, 9407b2e93, b7fc9890c, 4681bd1b5 plus in-flight commits landed within 2 hours (ee3656cf5, c44434b55, 7fa4e9e3e, e32e8028d, 934d9b6d8, 557b30fcd, ace73d7ea, 308f13db8, 1cb42e7ff). Gates G1-G8, diagnostics test (21 clauses), and locale audit.

## Findings

All 21 diagnostics clauses pass. Locale audit reports ok for all four locales (ca/en/es/hu).

### ef1d12738 — swarm-audit rule amendment

Vault/rules only. No production code. G1-G8: PASS.

### 661cec2d4 / 84ad2414c / 14223f3eb — translation campaign EN/ES/CA

Pure value-swap edits: 68/182/237 placeholder keys translated. Zero structural key additions or removals confirmed by diff analysis. G4: PASS (no structure hand-edits). G1-G8: PASS.

### 9407b2e93 — f-string key registry

New `_fstring_registry.py`. `__all__` lists exactly the three symbols declared in that module. No shims, no re-exports. G5: PASS. G1-G8: PASS.

### b7fc9890c — IVA wallet first_period_zero divergence

`reconcile_iva_compensation_wallet` adds `is_first_iva_period=False` parameter and emits `first_period_zero` divergence. CLI help uses `tr()` with locale key; English text is `default=` fallback — correct pattern. `reason` field is internal persisted state, not user-facing. Tests assert legal-grounding contracts (LIVA art. 99.5), not hand-computed formula outputs. G3/G6: PASS. G1-G8: PASS.

### 4681bd1b5 — BOE export coverage ledger

Vault/plan only. No production code. G1-G8: PASS.

### In-flight commits (ee3656cf5 et al.)

UTF-8 fix, provenance additions (formula_id/legal_refs/source_refs), relation-prefill tests, renta-ledger tests, filing roundtrip additions, axis-finisher markers: all production additions use `tr()` for operator-surface strings; broad-except additions carry `BROAD-EXCEPT-RATIONALE-*` comments per established pattern; no naked env reads, shims, or source-hygiene violations. G1-G8: PASS.

## Recommendations

No action required. All gates pass clean. Swarm cadence amendment (ef1d12738) is now active — next swarm trigger fires at the 6-8-commit mark from this audit point.
