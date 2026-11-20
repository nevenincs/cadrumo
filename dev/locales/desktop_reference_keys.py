"""Declared desktop shell keys for the Reference page.

The page words nothing of what the bundled corpus answers: passages, citations and terminology arrive as
the product serves them. These keys are only its chrome: the title, the notice that the answers are
orientation, the search field and the page's own states.
"""

from typing import Final

DESKTOP_REFERENCE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "desktop.reference.article",
        "desktop.reference.citation",
        "desktop.reference.empty",
        "desktop.reference.failed",
        "desktop.reference.idle",
        "desktop.reference.matched_on",
        "desktop.reference.orientation",
        "desktop.reference.passages",
        "desktop.reference.query_label",
        "desktop.reference.query_placeholder",
        "desktop.reference.results",
        "desktop.reference.search",
        "desktop.reference.search_again",
        "desktop.reference.searching",
        "desktop.reference.section",
        "desktop.reference.signed_out",
        "desktop.reference.source",
        "desktop.reference.terminology",
        "desktop.reference.title",
    }
)
