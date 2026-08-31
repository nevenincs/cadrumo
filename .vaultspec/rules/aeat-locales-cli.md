# AEAT locale and CLI language contract

- Locale changes are performed through the canonical CLI workflow and catalogue implementation, not by editing generated catalogues or maintaining a parallel translation path.
- The supported locale set is the live product set. Each supported locale contains a real translation for every required key; copying the source text or filling placeholders does not satisfy coverage.
- CLI help, notices, errors, and model or registry presentation use the same canonical keys and catalogue. Transport tokens, identifiers, enum values, and stored data remain stable and untranslated.
- A concept has one canonical translation key. Reuse it across revisions when continuity is proven; create a distinct key when legal meaning differs.
- Do not restore a retired command, locale family, or compatibility alias to make an old test or document pass.

Verify catalogue completeness, source-key parity, fallback/refusal behavior, and live CLI rendering for every supported locale through the owning tests.
