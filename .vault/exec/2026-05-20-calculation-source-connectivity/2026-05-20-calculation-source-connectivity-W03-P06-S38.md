---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S38'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace calculation-source-connectivity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S38 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Test region scoped category profiles select by profile CCAA and ## Scope

- `src/aeat/application/aggregation/test_renta_ledger_region.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Test region scoped category profiles select by profile CCAA

## Scope

- `src/aeat/application/aggregation/test_renta_ledger_region.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

Add a domain unit test pinning all four `select_deductibility_profile` branches (no override, override selected by matching comunidad, override for a different comunidad falls through to state, override with undeclared residence returns fail-closed). Add application tests: `test_region_override_selected_when_residence_matches` (a synthetic per-comunidad override halves the deductible versus the full-deductible state profile) and `test_region_override_undeclared_residence_fails_closed` (emits `REGION_UNDECLARED_FOR_OVERRIDE`, no observation).

## Outcome

Proves selection-by-comunidad and the D4 fail-closed refusal using a SYNTHETIC test override (never a real regime figure). 30 tests passed across the domain and application layers. Landed in commit `1ca532e93a`. Gates green.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Implements the S38 test and decision D4 of ADR `2026-07-04-renta-region-deductibility`. The override profile is a test double for the selection mechanism; no regulated deductibility value is asserted, satisfying the no-tautological-calculation-tests discipline.

Sibling step S36 (derive the residence comunidad from the active `TaxResidenceProfile` inside the aggregation) is intentionally LEFT OPEN / deferred. A best-effort profile read was prototyped and proven (guarded, byte-identical, tests green) but backed out at coordinator direction: it adds a profile-load and failure surface to the hot aggregation path for a field that is inert while the override layer is empty, and the cleaner shape is caller-side wiring introduced when a real territorial-regime override is first populated. The ADR remains `proposed`; these records document the proposed design the landed mechanism implements.
