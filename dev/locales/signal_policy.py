"""Policy for the authoritative locale audit."""

from __future__ import annotations

from typing import Final

LOCALES: Final[tuple[str, ...]] = ("ca", "en", "es", "hu")


LANGUAGE_CORE_FIELDS: Final[frozenset[str]] = frozenset({"definition", "scope_note", "short_description"})


SPELLING_SURFACES: Final[tuple[str, ...]] = ("docs_po", "generated_docs", "runtime", "toml")


NEAR_ECHO_THRESHOLD: Final[float] = 0.90


ECHO_SAMPLE_LIMIT: Final[int] = 20


INVARIANT_ECHO_REASONS: Final[tuple[str, ...]] = (
    "inline_code",
    "symbol_only",
    "modelo_form",
    "platform_format",
    "canonical_product_identity",
    "target_dictionary_shared_term",
)
