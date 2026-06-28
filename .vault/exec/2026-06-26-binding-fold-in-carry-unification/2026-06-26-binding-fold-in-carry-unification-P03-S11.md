---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S11'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-fold-in-carry-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-06-26-binding-fold-in-carry-unification-plan placeholders are machine-filled by
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
     The vaultspec-high-executor: reconcile the registry previous_filing compensacion formula path to feed or defer to the iva-wallet authority disposition-aware, removing the back-door observation-injection second route (apply-cached on collision, peer-WIP likely) and ## Scope

- `src/aeat/application/calculations/_iva_wallet_reconciliation.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# vaultspec-high-executor: reconcile the registry previous_filing compensacion formula path to feed or defer to the iva-wallet authority disposition-aware, removing the back-door observation-injection second route (apply-cached on collision, peer-WIP likely)

## Scope

- `src/aeat/application/calculations/_iva_wallet_reconciliation.py`

## Description

- Anchor the Modelo 303 compensación carry on the iva-wallet decision authority by removing the back-door IVA-compensation-history injection from the generic binding-resolution path.
- Stop `resolve_bindings_from_local_store` defaulting the IVA history repository to a real repository; pass the caller's value through so the previous_filing gather stays pure (registry observations only).
- Default the IVA history repository explicitly inside the wallet-feeding `extract_modelo_303_local_iva_compensation_recurrence` so it keeps reconstructing the local recurrence the reconciliation compares against live wallet evidence.

## Outcome

- Landed in the P03 commit `fe86795fa`. The live calculate path's compensación value is already owned exclusively by the iva-wallet decision (ruling D3 exclusion), so the injected value was always discarded there; removing the implicit injection shifts no calculate value. The wallet-engine integration, binding-prefill, and filed-capture suites pass (64 tests).

## Notes

- Scope finding: M303 declares exactly ONE previous_filing binding (the compensación one, already wallet-owned and excluded from the live previous_filing resolution), so the injection had no other live binding to affect. The risk surface of the removal was concentrated entirely in the wallet's local-recurrence reconstruction, which is preserved by the explicit-default relocation.
