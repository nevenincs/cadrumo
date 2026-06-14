---
tags:
  - '#audit'
  - '#legal-grounding-verification'
date: '2026-06-14'
modified: '2026-06-14'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace legal-grounding-verification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `legal-grounding-verification` audit: `Legal Codification vs Code Surface — Semantic + Online Verification Pass 1`

## Scope

Campaign 3: semantic + online verification of the legal-law codification and the
code surfaces that implement it — hunting calculation/legal overlaps, centralisation
drift, and (most consequentially) regulatory values whose inlined figure DISAGREES
with the binding law. Two indispensable instruments, used together:

1. **`vaultspec-rag` semantic search** (`--type code` / `--type vault`) to map each
   legal/calculation concept to the registry/corpus where it is codified and the
   code surfaces that implement it.
2. **Online search of the authoritative source** (AEAT sede + BOE consolidated
   text) to verify that each inlined regulatory figure matches the law — a value
   that is grounded-in-docstring but wrong is invisible to any static gate.

This complements the prior `calculation-truth-registry` and registry-legal-grounding
campaigns by auditing the post-centralisation residual: values that bypass the
registry `legal_refs`→`corpus_ref` mechanism and carry their grounding inline.

## Findings

### F1 (HIGH — calculation error, FIXED) — Ley 44/2015 art. 14 reserva especial cap wrong by 4x

`domain/modelos/_sal_reserva_especial.py` capped the SAL/SLL special-reserve
obligation at **50% of capital social** (`capital_social * Decimal("0.50")`), with
the docstring asserting "until the accumulated reserve reaches 50% of the share
capital". The authoritative BOE text — **Ley 44/2015 art. 14.1 (BOE-A-2015-11071)**:
"se dotará con el diez por ciento del beneficio líquido de cada ejercicio, **hasta
que alcance al menos una cifra superior al doble del capital social**" — requires
the reserve to accrue until it reaches **more than twice (2x) the capital social**.
The 10% dotación was correct; the **cap was 4x too low**, stopping the mandatory
reserve far too early and under-declaring it (`no-silent-under-declaration`). It
feeds a production modelo calculation via `_calculate_input`
(`is_sal_reserva_especial_dotacion`). Fixed: cap → `capital_social * Decimal("2")`,
docstring re-grounded against the BOE wording, and the four cap-dependent tests —
which had hand-computed against the wrong 50% cap (a tautological codification of
the bug) — re-derived from the BOE rule. 7 reserva tests pass (`fa2f9f029`).
Discovered by RAG (located the surface) + BOE fetch (verified the figure) — neither
alone would have caught it.

### F2 (verified correct) — LIRPF art. 23.2 rental-reducción tiers

`domain/fincas/_tier_resolver.py` inlines the 90/70/60/50% reducción tiers and the
">5% rent-cut" threshold. Online verification against AEAT and BOE-A-2023-12203
(Ley 12/2023) confirms the figures and the transitional 60%-grandfathering of
pre-Ley-12/2023 contracts. Values correct; grounded in code via `boe_citation_id`.

### F2b (verified correct) — M202 art. 40.3 LIS INCN threshold

`domain/calculations/registry/_applicability_modelo202.py:_MODELO_202_ART_40_3_INCN_THRESHOLD
= Decimal("6000000")`. Online verification against AEAT Modelo-202 instructions and
LIS art. 40.3 confirms the figure: the modalidad of art. 40.3 is obligatoria when
the importe neto de la cifra de negocios exceeds 6.000.000 €. Correct.

### F3 (centralisation-mechanism observation, not wrong values) — two parallel legal-grounding mechanisms

The codebase carries legal grounding two ways: the registry
`legal_refs`→`corpus_ref` standard (recargo de equivalencia, recargo extemporáneo,
M347 threshold, IVA rates via `lookup_rate` — all registry/corpus-grounded and gate-
enforced, e.g. the `test_edit_iva_rate_boundary` ban on local IVA-rate literals),
and inline-domain `boe_citation_id` strings + docstring quotes (the fincas tiers,
the DT12 reducción, the reserva especial). The inline-grounded values are legally
documented but bypass the registry's corpus-verified mechanism, so a wrong figure
(F1) survives every static gate until checked against the source. This is a
grounding-mechanism inconsistency, not a missing-grounding or (mostly) wrong-value
drift.

## Recommendations

- Continue the RAG + online-verification pass across the remaining inline-grounded
  regulatory figures (the DT12 40% reducción, the M202 art. 40.3 €6 000 000 INCN
  threshold, the M202 micro-empresa tipos, the maritime art. 7.p €60 100 ceiling —
  note the maritime engine currently applies no explicit ceiling constant), each
  fetched against its BOE/AEAT source. F1 proves that an inline-grounded figure can
  be wrong and silently under-declare; every such figure is a verification target.
- Where a figure is confirmed correct but inline-grounded, prefer migrating it to
  the registry `legal_refs`→`corpus_ref` mechanism so the corpus-text cross-check
  gate (`registry-calculation-legal-grounding`) guards it, rather than a
  `boe_citation_id` string that no gate validates against the source.
- Treat any test that hand-computes a calculation's expected value from the same
  (possibly wrong) constant the code uses as tautological (`no-tautological-
  calculation-tests`); derive cap/threshold expectations from the BOE figure.

## Codification candidates

<!-- Findings that satisfy the three durability criteria
(cross-session, constraint-shaped, project-bound) and should be
promoted into project-shared rules under `.vaultspec/rules/rules/`
via `vaultspec-core vault rule promote --from <this-audit-stem>
--as <rule-name>`.

Each candidate names the finding it derives from, the proposed
rule slug (kebab-case, naming the constraint's subject not the
failure), and a one-sentence statement of the rule.

Most audits produce zero codification candidates. Some produce one.
Only the rare framework-wide-pattern audit produces several. If
none of the findings above meet the bar, state that explicitly and
move on -- an empty Codification candidates section is a positive
signal, not a failure. -->

<!-- Example:

- **Source:** finding S04 (destructive verbs lack preview).
  **Rule slug:** `destructive-verbs-need-dry-run`.
  **Rule:** Every CLI verb that writes or removes state must
  accept `--dry-run` and emit a usable preview before applying.

-->
