"""Declared desktop shell keys for the Home page.

The page words its zones from what the application serves with them, so these keys are
only its chrome: the page's title and headings, the standing of a zone that shows no data,
and the page's own states.
"""

from typing import Final

DESKTOP_HOME_KEYS: Final[frozenset[str]] = frozenset(
    {
        "desktop.home.aeat_evidence",
        "desktop.home.availability_locked",
        "desktop.home.availability_never_captured",
        "desktop.home.availability_stale",
        "desktop.home.availability_stale_observed",
        "desktop.home.availability_unavailable",
        "desktop.home.empty",
        "desktop.home.failed",
        "desktop.home.heading_actions",
        "desktop.home.heading_agenda",
        "desktop.home.heading_declarations",
        "desktop.home.heading_ledger",
        "desktop.home.heading_messages",
        "desktop.home.loading",
        "desktop.home.messages_attention",
        "desktop.home.modelo",
        "desktop.home.observed",
        "desktop.home.refresh",
        "desktop.home.signed_out",
        "desktop.home.title",
        "desktop.home.unworded",
    }
)
