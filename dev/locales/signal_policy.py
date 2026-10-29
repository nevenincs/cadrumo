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


# These reason codes come from runtime state; missing authored copy uses the
# generic availability or refusal message. New families require evidence of
# the same fallback, and the dynamic-prefix gate checks entries remain live.
OPEN_ENDED_NAMESPACES: Final[dict[str, str]] = {
    "workspace.declarations.refusal.reason": (
        "Keyed by the free-text reason_code a workbench zone carries; copy is optional "
        "and the page falls back to its generic refusal line for an unauthored reason."
    ),
    "tui.home.availability.reason": (
        "Keyed by the free-text reason_code a workbench zone carries; copy is optional "
        "and the page falls back to its generic availability line for an unauthored reason."
    ),
}
