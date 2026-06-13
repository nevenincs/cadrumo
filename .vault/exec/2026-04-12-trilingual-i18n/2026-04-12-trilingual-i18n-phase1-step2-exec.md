---
tags:
  - "#exec"
  - "#trilingual-i18n"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-trilingual-i18n-plan]]"
---

# Implement core i18n primitives

Implemented in `src/aeat/core/i18n/__init__.py`:
- `Language` (StrEnum): es, en, hu
- `Translatable` (TypedDict): Nested-dict shape for translations
- `TranslationFallback` (StrEnum): fallback policies
- `get_translation`: retrieve translation with fallback
- `require_authoritative`: enforce presence of domain authoritative language
- `with_translation`: inject translations into dicts
- `TranslationError` inheriting from `aeat.core.errors.AeatError`

Used full type hinting and Google-style docstrings.
