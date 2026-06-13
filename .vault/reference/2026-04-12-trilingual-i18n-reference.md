---
tags:
  - "#reference"
  - "#trilingual-i18n"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-trilingual-i18n-adr]]"
---

# Trilingual i18n Reference

## Package Structure
- `src/aeat/core/i18n/`: Core primitives for managing translations.

## Core Primitives
- `Language(StrEnum)`: `ES` (es), `EN` (en), `HU` (hu).
- `Translatable(TypedDict)`: Represents a nested dictionary `{"es": str, "en": str, "hu": str}`.
- `TranslationFallback(StrEnum)`: `STRICT`, `FALLBACK_TO_EN`, `FALLBACK_TO_ES`.

## Implementation Methods
- `get_translation`: Fetches value according to `target_lang` and `fallback_policy`.
- `require_authoritative`: Verifies presence of the domain's authoritative language.
- `with_translation`: Attaches a translation nested object to a dictionary.

## Configuration
- `AEAT_OUTPUT_LANGUAGE`: Determines output language for users.
- `AEAT_AUTHORITATIVE_LANGUAGE_AEAT_TERMS`: Default `es`.
- `AEAT_AUTHORITATIVE_LANGUAGE_PROJECT_DOCS`: Default `en`.
- `AEAT_FALLBACK_LANGUAGES`: Fallbacks logic list.

## Testing Strategy
- Tests are collocated in `src/aeat/core/i18n/test_i18n.py`.
- No mock/patch logic applied. Pure primitives tested with literal input dictionaries.
