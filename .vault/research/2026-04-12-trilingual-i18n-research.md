---
tags:
  - "#research"
  - "#trilingual-i18n"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-trilingual-i18n-adr]]"
---

# Trilingual i18n Research

## Context
The project requires trilingual internationalization (i18n) support, primarily handling Spanish (es), English (en), and Hungarian (hu). We need to determine the best approach for storing, validating, and displaying these translations across the application, specifically within data models, CLI output, and internal documentation.

## Storage Shape Options
We evaluated three primary approaches for storing translatable fields in our models:

1.  **Field-suffix (`name_es`, `name_en`, `name_hu`)**:
    *   *Pros*: Simple schema, easy to query in SQL, straightforward type checking.
    *   *Cons*: Inflexible if more languages are added later, cluttering of model definitions, requires schema migration for new languages.
2.  **Nested-dict (`name: {"es": "...", "en": "...", "hu": "..."}`)**:
    *   *Pros*: Highly flexible, keeps the model namespace clean, easy to serialize/deserialize to JSON, fits well with NoSQL or JSONB columns in SQL.
    *   *Cons*: Slightly more complex querying depending on the database, requires custom validation logic to ensure required languages are present.
3.  **Side-table (separate translations table joined at read time)**:
    *   *Pros*: Normalized database design, very flexible.
    *   *Cons*: Overkill for a strictly trilingual setup, adds significant read overhead (JOINs), complex ORM setup.

## Default and Authoritative Languages
Different types of data in the system have different primary contexts:
*   **AEAT Terminology**: The Spanish Tax Agency (AEAT) uses Spanish natively. Translations to English or Hungarian might be approximations or explanatory. Therefore, Spanish is the authoritative source.
*   **Code and Internal Docs**: Standard software engineering practices dictate English as the primary language.
*   **User-facing Output**: Depending on the user, Hungarian or English might be preferred.

## Validation
Strict validation (requiring all translations) can hinder data entry and development. A more pragmatic approach is to enforce the authoritative language for a given field and treat missing translations in other languages as warnings or fallback to the authoritative language.

## CLI Output Language Selection
Users need a way to specify their preferred language for CLI interactions. Standard practices include:
*   Environment variables (e.g., `AEAT_OUTPUT_LANGUAGE`, `LANG`).
*   CLI flags (e.g., `--lang`).
*   Fallback chain: Flag -> Env Var -> System Default -> Hardcoded Default (English).

## Encoding
Consistent encoding is crucial for i18n to avoid character corruption, especially with accented characters in Spanish and Hungarian. UTF-8 is the industry standard. NFC (Normalization Form C) ensures that composed characters (like 'é') are represented consistently.

## GNU gettext (`.po` files)
Traditional i18n tools like gettext are powerful but heavy. They are designed for large-scale string externalization and translation workflows. Given our requirement for structured data translation (models) and specific trilingual constraints, gettext adds unnecessary complexity and tooling overhead compared to inline dictionaries or structured data.
