# AEAT naming

## Domain language

- Use the official Spanish tax-domain term for public concepts and stable product language for technical concepts. Names describe legal or business meaning, not the current implementation trick.
- A public type, command, registry key, or file family uses one canonical stem. Avoid synonyms, abbreviations without domain currency, English/Spanish duplicates, and aliases kept only for old callers.
- Modelo identifiers use the canonical typed modelo representation; casilla, revision, period, and legal-reference identifiers keep their established structured forms.
- CLI verbs follow the live hierarchy. For local censo ingestion, use `aeat config profile censo import --file ...`, not a parallel `file` command.

## Files and modules

- Public modules are semantically named and define the symbols consumers import from them. Leading-underscore modules are private to their package and are not cross-package APIs.
- A filename, class, and registry family should reveal the same responsibility. Do not use generic buckets such as `utils`, `helpers`, `common`, or `misc` for domain behavior.
- Renames are atomic across code, tests, dynamic references, documentation, and generated outputs. Delete the displaced name unless an explicit released compatibility floor requires it.
