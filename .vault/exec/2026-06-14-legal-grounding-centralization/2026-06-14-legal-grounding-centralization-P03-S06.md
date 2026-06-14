---
tags:
  - '#exec'
  - '#legal-grounding-centralization'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S06'
related:
  - "[[2026-06-14-legal-grounding-centralization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace legal-grounding-centralization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-06-14-legal-grounding-centralization-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The F4: author the ledger_iva_aggregation base_amount_sum bindings (INTRA_COMMUNITY_SUPPLY->59, EXPORT_THIRD_COUNTRY_ZERO_RATED->60) and delete the dormant casilla_59/60 Python helpers and ## Scope

- `src/aeat/application/aggregation/_iva_ledger.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# F4: author the ledger_iva_aggregation base_amount_sum bindings (INTRA_COMMUNITY_SUPPLY->59, EXPORT_THIRD_COUNTRY_ZERO_RATED->60) and delete the dormant casilla_59/60 Python helpers

## Scope

- `src/aeat/application/aggregation/_iva_ledger.py`

## Description

- Author `303/.../bindings/0003-intracom-export-base.part-001.toml`: two
  `ledger_iva_aggregation` bindings with `fact = "base_amount_sum"` —
  casilla 59 ← INTRA_COMMUNITY_SUPPLY / repercutido / zero (LIVA art. 25), casilla 60 ←
  EXPORT_THIRD_COUNTRY_ZERO_RATED / repercutido / zero (LIVA art. 21). Reuses the
  existing human-reviewed legal refs; no new legal-authority authoring.
- Flip casillas 59/60 in the 2023-y-siguientes revision from `input_kind = "manual"` to
  `"bound"` with `binding = <id>`.
- Delete the dormant application-tier `casilla_59_base_imponible` /
  `casilla_60_base_imponible` helpers (zero production callers) and their `__all__`
  entries from `_iva_ledger.py`.
- Migrate `test_intracom_export.py` to resolve casilla 59/60 through the registry binding
  resolver (the canonical path), proving the binding reproduces the helper values
  (5000.00 / 3000.00). Add the two bindings to the isolated M303 registry tests' facts
  dicts and the calculation-completeness manifest (the now-computed boxes join the closure).

## Outcome

M303 casillas 59/60 (informativa base imponible of exempt entregas intracomunitarias and
exportaciones) are now auto-computed from the ledger via registry bindings, replacing the
dormant helpers — the category→casilla routing moved from feature code into the registry
(`aeat-schema-central-config`), closing finding F4. Empirically proven: rate_kind for 0%
supplies = zero; binding resolver reproduces 5000/3000 exactly; production's
`_registry_provider` supplies the facts via the same path as the reverse-charge bound
casillas. 2326 registry + 497 aggregation/calc-sheets tests pass; ruff clean.

## Notes

Making optional informativa casillas `bound` rippled to three surfaces, all resolved: the
calc engine requires a binding fact for every bound casilla (production supplies it via
`resolve_ledger_iva_aggregation_binding_values`, which returns 0 for empty matches; the
isolated registry tests' hand-built facts dicts needed the two ids added), and the
calculation-completeness manifest had to enumerate the new computed boxes. The art. 22
"operaciones asimiladas a las exportaciones" leg of casilla 60 remains uncaptured (no
IvaCategory member exists for it) — same scope as the prior helper, noted in the binding
fragment. The 2009-y-siguientes revision keeps casillas 59/60 manual (the binding is
authored only on the current 2023+ revision).
