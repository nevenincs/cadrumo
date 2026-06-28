---
tags:
  - "#adr"
  - "#trilingual-i18n"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-trilingual-i18n-research]]"
---

# Architecture Decision Record: Trilingual i18n

## Status
Accepted

## Context
The application needs to handle data and output in three languages: Spanish (es), English (en), and Hungarian (hu). We need a consistent, maintainable strategy for storing translatable data, validating it, and presenting it to the user.

## Decisions

### 1. Storage Shape for Translatable Fields
We will use the **Nested-dict** approach: `field: {"es": "...", "en": "...", "hu": "..."}` keyed by ISO 639-1 code.
*   *Rationale*: It provides the best balance of flexibility and clean model design. It avoids schema clutter and aligns well with modern JSON-based serialization and storage (e.g., JSONB in databases). Field-suffixes would make models unwieldy, and side-tables are overly complex for our needs.

### 2. Default and Authoritative Languages
*   **AEAT Terminology**: Spanish (`es`) is the authoritative language.
*   **Internal Project Docs/Code**: English (`en`) is the authoritative language.
*   **User-facing Output**: Hungarian (`hu`) where appropriate, falling back to English.
*   *Fallback*: When a translation is missing for AEAT data, the system will default to Spanish. For code/system messages, it defaults to English.

### 3. Validation Strategy
*   Every translatable field MUST contain at least the authoritative language for its context (e.g., AEAT terms must have `es`).
*   Missing non-authoritative languages will be treated as warnings, not errors, allowing for iterative translation without blocking data entry.

### 4. CLI / Output Language Selection
The output language will be determined by the following fallback chain:
1.  CLI flag: `--lang <code-2>` (e.g., `--lang es`)
2.  Environment variable: `AEAT_OUTPUT_LANGUAGE`
3.  Default fallback based on context.

### 5. Encoding
*   **UTF-8** will be strictly enforced everywhere (input, storage, output).
*   **NFC (Normalization Form C)** normalization must be applied to all text inputs to ensure consistent representation of characters across the application.

### 6. Tooling
*   We will **NOT** use gettext or `.po` files.
*   *Rationale*: Our translation needs are closely tied to data models (Nested-dicts) rather than static UI string externalization. Gettext introduces unnecessary build steps and complexity that do not align with our chosen storage shape.

## Consequences
*   We need to implement custom pydantic validators (or equivalent) to enforce the authoritative language requirement and handle warnings for missing translations.
*   The CLI layer needs a standard utility to parse the language preference from flags/env vars and propagate it to output formatters.
*   Database queries involving localized fields will need to utilize JSON-specific querying functions if filtering or sorting by translated values is required.
