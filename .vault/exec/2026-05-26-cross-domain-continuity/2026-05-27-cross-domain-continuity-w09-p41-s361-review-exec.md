---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-cross-domain-continuity-W07-P31-S361]]'
---

# cross-domain-continuity Code Review

## Review: S361 - M100 2024 final-settlement chain (commit 17cea3fe8)

**Status: PASS**

Scope: 6 casilla TOML patches + construct 0011-renta-2024-final-settlement.toml + 6 formula TOMLs (0169-0174) + test_modelo_100_settlement_chain.py.

---

### Critical Questions

**Q1. Construct source_refs includes lirpf-cuota-chain-authority?**

YES. 0011-renta-2024-final-settlement.toml line 23 lists lirpf-cuota-chain-authority. Khalid round-11 finding resolved.

**Q2. aeat app modelo bindings list --modelo 100 --year 2024 --period 0A succeeds?**

NO - pre-existing failures, unrelated to S361. Two errors: (1) aeat-modelo-721-procedure sha256 mismatch (Modelo 721 campaign drift); (2) construct renta-cuota-chain missing aeat-dr-100-2024-dictionary for formula renta-2024-base-liquidable-general-sometida-a-gravamen (pre-existing gap in renta-cuota-chain, not in renta-2024-final-settlement). S361 construct satisfies the modelo-100-2024-calculation application link which requires only lirpf-cuota-chain-authority.

**Q3. renta-2024-total-pagos-a-cuenta BOE citation issue resolved?**

PARTIALLY. Formula 0172 now carries source_refs = [boe-modelo-100-2024-form] with source_citations. The prior absence is fixed. However 0172 is the only settlement formula without aeat-renta-2024-manual-parte1 in source_refs (other five include it). See REGISTRY-001.

**Q4. 0414 dropout documented inline in TOML?**

YES. Formula 0170-renta-2024-cuota-resultante-autoliquidacion.toml carries a 3-line comment at lines 4-6: casilla 0414 does not exist in the 2024 revision, introduced in 2025; 2024 label confirms 0587-0588-0589-0590-0591.

**Q5. Tests grounded in AEAT Renta 2024 Manual oracle (Roberto-shape)?**

YES, with a discrepancy from the brief. Brief specified 0587=15141, 0610=13317. Tests derive 0587=14453.60, 0610=12629.60 from the registry Madrid escala parameter (0014-renta-2024-escala-autonomica-madrid-base-general.toml). The module docstring shows full bracket arithmetic. Registry autonomic escala is the correct authority; the brief oracle used different bracket rates. Code is correct. Discrepancy is in the brief.

---

### Gate Results

**G1 - No naked env reads:** No Python changed. PASS.

**G2 - Typed pydantic at boundaries:** No Python changed. PASS.

**G3 - User messages via tr():** No Python changed. PASS.

**G4 - No locale yml hand-edits:** No locale files changed. PASS.

**G5 - No shims, no duplication:** 2025 construct uses renta-2025-* formula IDs, includes 0414, has 7 formulas (pagos-fraccionados 2025-only), different legal_refs (art-81-bis, orden-hac-277-2026), 2025 source authority. 2024 construct is independently declared, year-scoped, not a copy. PASS.

**G6 - No tautological tests:** Oracle is LIRPF 2024 Art. 63 + Madrid 2024 autonomic escala from registry parameter. Full bracket derivation in module docstring. _EXPECTED_0587 computed from tarifa arithmetic, not from formula under test. Anti-tautology test varies 0153 from 1824 to 3000 and asserts 1176 EUR delta in 0610. PASS.

**Grounding gate:** All 6 formulas use 2024 source authority exclusively. Legal refs: Art. 50, Art. 79, Art. 99, Art. 101, Art. 103, RD 439/2007 Art. 100/109/110. No 2025 refs. Art. 63/64 (tarifa) live in escala parameter files, not in settlement formulas - correct architecture. PASS.

---

### Findings

REGISTRY-001 | LOW | 0172-renta-2024-total-pagos-a-cuenta.toml omits aeat-renta-2024-manual-parte1 from source_refs. All other five formulas cite it. Add in follow-up. Not blocking.

REGISTRY-002 | LOW | Test oracle 0587=14453.60 differs from brief oracle 0587=15141. Test is correct against registry Madrid escala; brief used different bracket rates. Documentation inconsistency in brief. Not blocking.

INFRA-003 | MEDIUM | bindings list fails on two pre-existing errors predating S361: aeat-modelo-721-procedure sha256 mismatch and renta-cuota-chain source_refs gap. Track as independent issues.

---

### Verdict

**PASS** - No Critical or High issues. Construct carries lirpf-cuota-chain-authority, formulas are 2024-scoped only, 0414 split documented inline, tests grounded in external tarifa authority with full derivation.
