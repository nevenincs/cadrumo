---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S27'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-vocabulary-cli-cohesion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S27 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The DEFERRED FOLLOW-UP verification: when F8 lands, run pytest --collect-only -q clean, test_schema_hygiene.py and the bindings-framework gate suite green, and assert the selector union is behaviour-preserving over the prior validate-time selector models and ## Scope

- `if F8 is deferred to a separate phase`
- `leave this Wave open and record the carve in the close note`
- `src/aeat/domain/calculations/registry/tests/test_schema_hygiene.py`
- `src/aeat/domain/calculations/registry/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# DEFERRED FOLLOW-UP verification: when F8 lands, run pytest --collect-only -q clean, test_schema_hygiene.py and the bindings-framework gate suite green, and assert the selector union is behaviour-preserving over the prior validate-time selector models

## Scope

- `if F8 is deferred to a separate phase`
- `leave this Wave open and record the carve in the close note`
- `src/aeat/domain/calculations/registry/tests/test_schema_hygiene.py`
- `src/aeat/domain/calculations/registry/tests`

## Description

- Confirm the F8 implementation (`S25` selector discriminated-union, `S26` typed_enum) is landed at HEAD and its blocker cleared: commit `71367c6b9d` enrolled `DONATIVO_DONOR` in the selector-shape expected set, and the previously non-authored `test_selector_shape.py` WIP is now committed and clean.
- Run `pytest --collect-only -q` over the registry test surface; observe clean collection.
- Run `test_schema_hygiene.py` and `test_selector_shape.py`; observe green.
- Run the bindings-framework gate suite over the registry tests; observe green.

## Outcome

F8 verification passes. `test_schema_hygiene.py` + `test_selector_shape.py` are green (50 passed), and the registry bindings-framework gate suite is green (469 passed, 0 failed). The selector discriminated union hydrates every live `BindingSourceKind` selector family — including the `DONATIVO_DONOR` source that previously outran the expected set — and `typed_enum` hydrates to `BindingTypedEnumKind`, behaviour-preserving over the prior validate-time selector models. Collect-only over the registry test surface is clean.

## Notes

S27 was the deferred F8 verification carry-forward. Its two blockers named in the campaign audit — non-authored WIP on `test_selector_shape.py` and the un-currentized `DONATIVO_DONOR` expected set — both cleared via peer commit `71367c6b9d`. No production code was modified in this Step; it is verification-only.
