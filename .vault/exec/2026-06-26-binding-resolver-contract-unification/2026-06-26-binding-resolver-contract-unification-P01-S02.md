---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S02'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-resolver-contract-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S02 and 2026-06-26-binding-resolver-contract-unification-plan placeholders are machine-filled by
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
     The Migrate the M349-only PerModeloRegistryBindingResolution consumer onto CalculationSourceResolution, then delete the PerModeloRegistryBindingResolution model and resolve_per_modelo_registry_binding_values in the same atomic relocation commit and ## Scope

- `src/aeat/application/aggregation/_registry_provider.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Migrate the M349-only PerModeloRegistryBindingResolution consumer onto CalculationSourceResolution, then delete the PerModeloRegistryBindingResolution model and resolve_per_modelo_registry_binding_values in the same atomic relocation commit

## Scope

- `src/aeat/application/aggregation/_registry_provider.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

Commit `52edec4b1` (covers S02 + S04). Deleted the vestigial M349-only
`_registry_provider` module (`PerModeloRegistryBindingResolution` +
`resolve_per_modelo_registry_binding_values` + its test) after confirming ZERO
production callers at HEAD. Dropped the two re-exports from the aggregation package
`__all__` / import surface (S04). Removed the dead `_COUNTERPART_BINDING_SOURCE_KINDS`
guard in `test_service.py`. Regenerated API doc stubs (orphan `_registry_provider.rst`
+ toctree line) in the same commit.

## Outcome

P01.S02 + S04 complete. The M349 counterpart binding resolution the deleted function
duplicated is reached in production through the live registry-binding mesh path
(the 349 collectible/payable invoice bindings, covered by
`test_modelo_349_intracomunitario_fidelity`, `test_counterpart_bindings`,
`test_modelo_349_registry`). No production path changed; no casilla value shifts.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The `apidocs scaffold` run pulled in ~22 peer-module stub deltas (withholding,
invoices, casilla-id, refund modules from concurrent campaigns). Surgically reverted
all peer-drift stubs and kept ONLY my `_registry_provider.rst` deletion + its single
aggregation-toctree line, so the commit carries only my stub change.
