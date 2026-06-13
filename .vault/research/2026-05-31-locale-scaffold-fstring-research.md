---
tags:
  - '#research'
  - '#locale-scaffold-fstring'
date: '2026-05-31'
modified: '2026-05-31'
related: []
---

# `locale-scaffold-fstring` research: f-string tr() scaffold blind-spot

Investigation of f-string `tr()` call sites in `src/aeat/` that the locale scaffold
cannot enumerate concretely, causing missing locale entries when new enum values are
added.

## Root cause

The locale scaffold tool in `src/aeat/locales/` uses two discovery paths:

1. **Regex scanner** (`manager.py:pattern`) — captures `tr("literal.key")` forms.
2. **AST scanner** (`_ast_scanner.py`) — captures programmatic emission patterns
   (exception constructors, `message_key=` kwargs, `build_entry` portal keys) and
   f-string / concatenation patterns as namespace markers (`<prefix>.*`).

For f-string `tr()` calls, the AST scanner emits a namespace marker (e.g.
`wizard.setup.*`) but cannot enumerate the concrete keys because the dynamic tail is
computed at runtime. The parity check only verifies that at least one concrete locale
entry exists under each declared prefix — it does not verify that every possible key
the runtime can build is present.

When a new enum value is added (e.g. `LegalEntityForm.SAL`, `LegalEntityForm.SLL` in
commit `9aeb99765`), the scaffold cannot insert the missing locale keys because it has
no knowledge of what values the enum produces. The CLI `locales set` fails with "key
not found, run scaffold first", and `scaffold` reports success because the namespace
prefix already exists.

This caused a three-incident hand-edit pattern (hu locale campaign, beef1e1d7) and was
documented in that commit as "Companion to follow-on #565 to fix the scaffold tooling".

## F-string tr() site inventory (production modules only, tests excluded)

| File | Line | Pattern | Dynamic source |
|------|------|---------|----------------|
| `application/wizard/_catalogue.py` | 57 | `tr(f"wizard.setup.{suffix}.{qid}.prompt")` | WizardFlow section.id + question.id (not enumerable statically) |
| `application/wizard/_catalogue.py` | 106 | `tr(f"wizard.setup.taxpayer-type.entity-type.choices.{member.value.replace('_', '-')}.label")` | `EntityType` StrEnum (3 values) |
| `application/wizard/_catalogue.py` | 114 | `tr(f"wizard.setup.taxpayer-type.legal-entity-form.choices.{member.value.replace('_', '-')}.label")` | `LegalEntityForm` StrEnum (8 values) |
| `application/wizard/_catalogue.py` | 122 | `tr(f"wizard.setup.taxpayer-type.irpf-income-categories.choices.{member.value.replace('_', '-')}.label")` | `IrpfIncomeCategory` StrEnum (6 values) |
| `application/wizard/_catalogue.py` | 130 | `tr(f"wizard.setup.obligations.irpf-estimation-regime.choices.{member.value.replace('_', '-')}.label")` | `IrpfEstimationRegime` StrEnum (3 values) |
| `application/wizard/_catalogue.py` | 138 | `tr(f"wizard.setup.obligations.irpf-special-regime.choices.{member.value.replace('_', '-')}.label")` | `IrpfSpecialRegime` StrEnum (2 values) |
| `application/wizard/_catalogue.py` | 148 | `tr(f"wizard.setup.residence.fiscal-residency.choices.{member.value.replace('_', '-')}.label")` | `FiscalResidency` StrEnum (2 values) |
| `application/wizard/_catalogue.py` | 161 | `tr(f"wizard.setup.residence.ccaa.choices.{member.value}.label")` | `CCAA` StrEnum (15 values, no hyphen transform) |
| `application/wizard/_catalogue.py` | 169 | `tr(f"wizard.setup.profile.output-language.choices.{language}.label")` | `SUPPORTED_OUTPUT_LANGUAGES` frozenset (4 values) |
| `application/wizard/_compiler.py` | 93 | `tr(f"profile.keys.{question.profile_key}")` | WizardQuestion.profile_key (open, not statically enumerable) |
| `application/wizard/_commands.py` | 923 | `tr(f"wizard.{flow.id}.description")` | WIZARD_FLOWS catalogue (enumerable) |
| `application/storage/calc_sheets/_engine.py` | 851 | `tr(f"sheets.detalle.headers.{row_field}", default=binding.id)` | registry binding row_field (open, uses default) |

**Total production f-string tr() sites: 12**

Of these, **9 sites** iterate over a bounded enumeration whose values are fully known at
import time. The remaining 3 sites iterate over open/runtime-computed values (section
suffix + question ID, profile key, registry binding row_field). The `sheets.detalle.headers.*`
and `profile.keys.*` sites both use `default=` fallback which means missing locale
entries degrade gracefully.

## Enumerable concrete key count

Running the 9 bounded sites against current enum values produces **43 concrete keys**
that scaffold cannot currently emit:

- `wizard.setup.taxpayer-type.entity-type.choices.*.label` — 3 keys
- `wizard.setup.taxpayer-type.legal-entity-form.choices.*.label` — 8 keys
- `wizard.setup.taxpayer-type.irpf-income-categories.choices.*.label` — 6 keys
- `wizard.setup.obligations.irpf-estimation-regime.choices.*.label` — 3 keys
- `wizard.setup.obligations.irpf-special-regime.choices.*.label` — 2 keys
- `wizard.setup.residence.fiscal-residency.choices.*.label` — 2 keys
- `wizard.setup.residence.ccaa.choices.*.label` — 15 keys
- `wizard.setup.profile.output-language.choices.*.label` — 4 keys
- `wizard.*.description` (WIZARD_FLOWS ids — need verification)

All 43 keys currently exist in all locale files because they were hand-maintained, but
any new enum value added to these enums will not be auto-scaffolded.

## Current parity check coverage

`test_codebase_namespaces_are_satisfied_by_locale_entries` verifies that at least one
concrete locale entry matches each namespace marker. It does NOT verify that every
possible runtime key is present. This means the test passes even when the SAL/SLL keys
are missing if other legal-entity-form entries already exist under `wizard.setup.*`.

## Chosen approach

**Explicit registration surface** (`_fstring_registry.py` in `src/aeat/locales/`):

A module declares a mapping from `(prefix_template, transform)` to an iterable of
values. The scaffold expands each registration into concrete locale keys.

Design rationale:
- Does not require AST-level enum resolution (brittle, requires import at scan time).
- Keeps the enumeration source declaration close to where it is actually used (the
  locales module, not the production domain module).
- The registration is the authoritative contract: if an enum value is added but the
  registration is not updated, scaffold cannot produce the key — making the gap visible
  at scaffold time rather than at runtime.

Alternative considered: auto-import and enumerate enums at AST-scan time by resolving
the source module. Rejected: creates import dependency between the locale scanner and
the domain model; fragile to import errors; harder to test in isolation.

## Test strategy

1. A test asserts that `LocaleManager.get_codebase_keys()` returns the concrete
   `wizard.setup.taxpayer-type.legal-entity-form.choices.sal.label` and `...sll.label`
   keys (the keys that caused the #553 incident).
2. A test asserts that scaffold (on a tmp locale dir) inserts all 43 enumerable keys
   as placeholder entries.
3. A test asserts that the registration surface covers all current enum values (fails
   fast when a new enum value is added without updating the registration).
