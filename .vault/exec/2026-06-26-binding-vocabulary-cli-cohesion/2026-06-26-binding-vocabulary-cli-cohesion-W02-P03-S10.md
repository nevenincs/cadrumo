---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S10'
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
     The S10 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Rename the IvaCompensationAuthoritySourceKind type alias (Literal, not a class) to IvaCompensationAuthorityKind (wallet/compensation authority axis) as one atomic relocation:IvaCompensationAuthoritySourceKind commit, sweeping the def, the two field annotations, __all__, and the docs/conf.py nitpicky-resolver allowlist and ## Scope

- `do NOT touch the legitimate M303 compensacion carve-out binding usages in the same module`
- `regen docs-scaffold + API-stub + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/domain/iva_compensation/_reconciliation.py`
- `docs/conf.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename the IvaCompensationAuthoritySourceKind type alias (Literal, not a class) to IvaCompensationAuthorityKind (wallet/compensation authority axis) as one atomic relocation:IvaCompensationAuthoritySourceKind commit, sweeping the def, the two field annotations, __all__, and the docs/conf.py nitpicky-resolver allowlist

## Scope

- `do NOT touch the legitimate M303 compensacion carve-out binding usages in the same module`
- `regen docs-scaffold + API-stub + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/domain/iva_compensation/_reconciliation.py`
- `docs/conf.py`

## Description

- Rename the wallet/compensation authority TYPE ALIAS (a PEP 695 `type = Literal[...]`, not a StrEnum) from the `SourceKind` homonym to `IvaCompensationAuthorityKind` (the compensation-authority axis).
- Sweep the alias def, the two `source_kind` field annotations, the `_reconciliation` `__all__` (repositioned alphabetically), and the `docs/conf.py` nitpicky-resolver allowlist entry.
- Leave the legitimate M303 compensacion carve-out binding usages in the same module untouched, per the reserved-binding-name rule.

## Outcome

Landed as one atomic commit `relocation:IvaCompensationAuthoritySourceKind` (`93d035381`). The axis is NOT folded into `BindingSourceKind`. The `Literal` member string values are unchanged. collect-only clean, ruff clean, the 33 iva-compensation and compensation-history tests green.

## Notes

Confirmed the C3 anchor is a `type` alias, not a class, matching the reference's ADR-vs-HEAD drift correction. Both scoped files (`_reconciliation.py` and `docs/conf.py`) were clean of peer WIP. The M303 carve-out binding docstring lines (the prior-compensation binding decision for Modelo 303) were verified untouched.
