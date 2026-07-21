---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-08'
step_id: 'S16'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Author the ley-37-1992 art-101 legal entry corpus-grounded, noting the art-101.Dos common-deduction regime is deferred

## Scope

- `src/aeat/_data/registry/aeat/legal/iva.toml`

## Description

- Author the `ley-37-1992:art-101` legal entry in `src/aeat/_data/registry/aeat/legal/iva.toml` (régimen de deducciones en sectores diferenciados) with `corpus_ref` pointing at the bundled consolidated LIVA `ley-37-1992.html#a101` and a five-clause `required_text` cross-check: the art. 101.Uno separate-regime-per-sector obligation, the independent prorrata-especial-per-sector clause, the common-use → art. 104.Dos routing clause, and the two art. 101.Dos clauses (the AEAT-authorised common regime and its +20 % void test).
- Author a distinct `ley-37-1992:art-9-1-c` legal entry (the sectores-diferenciados definition, `section = "sectores-diferenciados"`) grounded in the same bundled corpus `#a9`, with a four-clause `required_text`: the sector-definition preamble, the letra a' CNAE-group distinctness clause, the >50-puntos-porcentuales spread clause (the legal basis of `PRORRATA_SECTORAL_SEPARATION_SPREAD_PP = 50`), and the letra b' special-regime-activities clause.
- Record in the art. 101 `notes` that art. 101.Dos (the AEAT-authorised common deduction regime and its +20 % void test) is DEFERRED as an authorisation case (`register authorisation_reference`), with the register schema already shaped to admit it.

## Outcome

The art. 101 sectores-diferenciados regime and the art. 9.1.c sector definition are now first-class, corpus-grounded legal entries citable by per-sector bindings and constructs. Both entries verify against the bundled consolidated LIVA: `test_catalogue_verification_normatives.py` passes (28 passed) and the registry collect-only gate is clean (2948 tests collected, 0 errors). The art. 101.Dos common-deduction regime and its +20 % void test are recorded as a deferred authorisation case, not implemented.

## Notes

- All nine `required_text` clauses were confirmed present verbatim in the normalised bundled corpus (`ley-37-1992.html`) via `normalise_corpus_text` before authoring; zero fabricated legal text.
- The art. 9.1.c grounding is a NEW distinct legal id (`ley-37-1992:art-9-1-c`), not an edit of the existing autoconsumo-focused `ley-37-1992:art-9` entry in `iva-flow.toml`; the two coexist as separate ids over the same consolidated corpus file.
- `reviewed_by` records honest agent-authored provenance ("operator to re-stamp") per the legal-grounding rule; the entries are agent-prepared pending operator re-stamp, not asserted as human-reviewed filing-grade.
