---
tags:
  - '#exec'
  - '#locale-scaffold-fstring'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S01
related:
  - "[[2026-05-31-locale-scaffold-fstring-research]]"
  - "[[2026-05-31-locale-scaffold-fstring-adr]]"
---

# locale-scaffold-fstring S01 — explicit f-string key registry

## Summary

Implemented explicit registration surface for bounded f-string `tr()` locale key
patterns. Closes GitHub issue #565.

## Problem addressed

The locale scaffold tool emitted namespace markers (`wizard.setup.*`) for f-string
`tr()` call sites but could not enumerate concrete keys. Adding a new enum value
(e.g. `LegalEntityForm.SAL`) left locale files incomplete and required hand-edits
under structural-repair exceptions — the pattern recurred three times in the
hu-locale campaign.

## Deliverables

- `src/aeat/locales/_fstring_registry.py` — new module; `FStringKeyRegistration`
  dataclass, `_build_registrations()`, `get_registered_keys()`, `get_registrations()`.
- `src/aeat/locales/manager.py` — `get_codebase_keys()` now calls
  `get_registered_keys()` and merges the 44 concrete keys into the scaffold set.
- `src/aeat/locales/test_parity.py` — 5 new tests (16 total, all pass).
- `.vault/research/2026-05-31-locale-scaffold-fstring-research.md`
- `.vault/adr/2026-05-31-locale-scaffold-fstring-adr.md`

## Inventory

- **12 production f-string `tr()` sites** enumerated across `src/aeat/`.
- **9 bounded patterns** registered (iterate over a fixed enum/frozenset).
- **3 open-ended patterns** left as namespace markers only (section+question IDs,
  profile key, registry binding row_field).
- **44 concrete keys** expanded from the 9 registered patterns.
- **0 locales missing any registered key** — all 44 keys already exist in ca, en, es,
  hu locale files.

## Test results

16 parity tests pass. 5 new tests:
- `test_fstring_registry_expands_sal_and_sll_keys` — verifies incident-causing keys
- `test_fstring_registry_covers_all_legal_entity_form_members` — enum coverage gate
- `test_fstring_registry_covers_all_fiscal_residency_members` — enum coverage gate
- `test_fstring_registry_all_keys_present_in_all_locales` — live locale file check
- `test_scaffold_inserts_fstring_registry_keys` — scaffold integration from empty

## Commit

`9407b2e93` — feat(locales): explicit f-string key registry closes #565

## Code review

Self-reviewed as vaultspec-code-reviewer. All 6 standing gates pass (G1-G6).
No tautological tests; expected values derived from the SAL/SLL incident specification
and real enum members, not from implementation output.
