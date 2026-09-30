"""Resolve the documentation site's own chrome in the language the root is built for.

The user documentation is published as one site root per language, and page
CONTENT is substituted from the gettext catalogues under ``docs/locales``.  The
site CHROME -- the header navigation, the broadcast strip, the footer, every
accessible name, and the strings the interaction layer writes into the DOM -- is
not page content: it lives in the Sphinx templates and in
``docs/_static/cadrumo-docs.js``, which gettext never reads.  Left alone it
renders English around translated pages, which is exactly the silent fallback
the localization contract refuses.

This module is the single place those strings are named.  Every one is resolved
through :func:`~dev.docs._locale_chrome.docs_chrome`, the same strict resolver
the generated reference surfaces use: a key with no authored value in the build
language raises instead of degrading to English.  ``docs/conf.py`` calls the two
functions below once when the configuration loads and hands the results to the
templates through ``html_context``; the templates serialise the
:func:`site_chrome` mapping into one inline JSON payload that the interaction
layer reads, so the browser-side strings come from the same catalogue as the
server-rendered ones.

The two functions split on destination rather than on kind.  :func:`site_labels`
holds the strings ``conf.py`` composes into structured context (navigation
entries, broadcast links, footer groups), each of which also carries a link
target.  :func:`site_chrome` holds the flat strings a template or the
interaction layer reads by name.
"""

from __future__ import annotations

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.product_identity import PRODUCT_IDENTITY

from ._locale_chrome import docs_chrome

__all__ = ["site_chrome", "site_labels"]


def site_labels(language: OutputLanguage, /) -> dict[str, str]:
    """Return the navigation, broadcast, and footer copy for one build language.

    Each of these strings is paired with a link target or a layout position by
    ``docs/conf.py``, or set as a Sphinx configuration value (the page title
    and the description metadata), which is why they are not part of the flat
    :func:`site_chrome` mapping.

    Args:
        language: The language this documentation root is being built for.

    Returns:
        A mapping of flat name to authored string.

    Raises:
        DocsChromeError: If any key has no authored value in ``language``.
    """
    product = PRODUCT_IDENTITY.prose_name
    return {
        "meta_title": docs_chrome("docs.site.meta.title", language, product=product),
        "meta_short_title": docs_chrome("docs.site.meta.short_title", language, product=product),
        "meta_description": docs_chrome("docs.site.meta.description", language, product=product),
        "nav_getting_started": docs_chrome("docs.site.nav.getting_started", language),
        "nav_cli_reference": docs_chrome("docs.site.nav.cli_reference", language),
        "nav_how_it_works": docs_chrome("docs.site.nav.how_it_works", language),
        "nav_api": docs_chrome("docs.site.nav.api", language),
        "link_updates": docs_chrome("docs.site.link.updates", language),
        "link_get_cadrumo": docs_chrome("docs.site.link.get_cadrumo", language),
        "link_report_issue": docs_chrome("docs.site.link.report_issue", language),
        "link_critical_updates": docs_chrome("docs.site.link.critical_updates", language),
        "link_release_notes": docs_chrome("docs.site.link.release_notes", language),
        "link_disclaimer": docs_chrome("docs.site.link.disclaimer", language),
        "link_events_and_deadlines": docs_chrome("docs.site.link.events_and_deadlines", language),
        "link_repository": docs_chrome("docs.site.link.repository", language),
        "broadcast_label": docs_chrome("docs.site.broadcast.label", language),
        "broadcast_message": docs_chrome("docs.site.broadcast.message", language),
        "footer_stay_current": docs_chrome("docs.site.footer.stay_current", language),
        "footer_get_help": docs_chrome("docs.site.footer.get_help", language),
        "footer_trust_and_responsibility": docs_chrome("docs.site.footer.trust_and_responsibility", language),
        "footer_note": docs_chrome("docs.site.footer.note", language),
    }


def site_chrome(language: OutputLanguage, /, *, language_endonym: str) -> dict[str, str]:
    """Return every template and interaction-layer chrome string, by flat name.

    The names are the dotted catalogue keys with the ``docs.site.`` prefix
    dropped and the remaining separators written as underscores, so a template
    reading ``cadrumo_chrome.aria_breadcrumb`` and a catalogue entry
    ``docs.site.aria.breadcrumb`` are the same fact spelled two ways.

    Three values keep a placeholder for a substitution the reader's browser
    performs -- ``{count}`` for a result tally, ``{query}`` for the text typed --
    because the number and the query exist only at that moment.  They are
    resolved here without interpolation so the authored translation, including
    its word order around the placeholder, is what the browser fills.

    Args:
        language: The language this documentation root is being built for.
        language_endonym: The build language's name in itself, used in the
            language switcher's accessible name.

    Returns:
        A mapping of flat name to authored string.

    Raises:
        DocsChromeError: If any key has no authored value in ``language``.
    """
    return {
        # Landmark and control accessible names rendered by the page template.
        "aria_site_updates": docs_chrome("docs.site.aria.site_updates", language),
        "aria_broadcast_links": docs_chrome("docs.site.aria.broadcast_links", language),
        "aria_dismiss_notice": docs_chrome("docs.site.aria.dismiss_notice", language),
        "aria_toggle_navigation": docs_chrome("docs.site.aria.toggle_navigation", language),
        "aria_primary_navigation": docs_chrome("docs.site.aria.primary_navigation", language),
        "aria_search_documentation": docs_chrome("docs.site.aria.search_documentation", language),
        "aria_repository": docs_chrome("docs.site.aria.repository", language),
        "aria_toggle_theme": docs_chrome("docs.site.aria.toggle_theme", language),
        "aria_toggle_toc": docs_chrome("docs.site.aria.toggle_toc", language),
        "aria_breadcrumb": docs_chrome("docs.site.aria.breadcrumb", language),
        "aria_language": docs_chrome("docs.site.aria.language", language, language=language_endonym),
        "aria_footer_channels": docs_chrome("docs.site.aria.footer_channels", language),
        "breadcrumb_home": docs_chrome("docs.site.breadcrumb.home", language),
        "footer_kicker": docs_chrome("docs.site.footer.kicker", language),
        # Search: the dedicated page, the sidebar trigger, and the palette.
        "search_page_title": docs_chrome("docs.site.search.page_title", language),
        "search_noscript": docs_chrome("docs.site.search.noscript", language),
        "search_placeholder": docs_chrome("docs.site.search.placeholder", language),
        "search_query_label": docs_chrome("docs.site.search.query_label", language),
        "search_searching": docs_chrome("docs.site.search.searching", language),
        "search_result_one": docs_chrome("docs.site.search.result_one", language),
        "search_result_many": docs_chrome("docs.site.search.result_many", language),
        "search_full_text_for": docs_chrome("docs.site.search.full_text_for", language),
        "search_open_full_text": docs_chrome("docs.site.search.open_full_text", language),
        "search_full_text_crumb": docs_chrome("docs.site.search.full_text_crumb", language),
        "search_on_this_page": docs_chrome("docs.site.search.on_this_page", language),
        "search_result_fallback": docs_chrome("docs.site.search.result_fallback", language),
        "search_hint_navigate": docs_chrome("docs.site.search.hint_navigate", language),
        "search_hint_open": docs_chrome("docs.site.search.hint_open", language),
        "search_hint_close": docs_chrome("docs.site.search.hint_close", language),
        # Result category labels, keyed on the shipped display class and record kind.
        "class_label_casilla": docs_chrome("docs.site.class_label.casilla", language),
        "class_label_modelo": docs_chrome("docs.site.class_label.modelo", language),
        "class_label_legal": docs_chrome("docs.site.class_label.legal", language),
        "class_label_cli": docs_chrome("docs.site.class_label.cli", language),
        "class_label_technical": docs_chrome("docs.site.class_label.technical", language),
        "class_label_doc": docs_chrome("docs.site.class_label.doc", language),
        "kind_label_concept": docs_chrome("docs.site.kind_label.concept", language),
        "kind_label_cli": docs_chrome("docs.site.kind_label.cli", language),
        "kind_label_casilla": docs_chrome("docs.site.kind_label.casilla", language),
        "kind_label_page": docs_chrome("docs.site.kind_label.page", language),
        # The executed-sequence widget's controls.
        "sequence_show_output": docs_chrome("docs.site.sequence.show_output", language),
        "sequence_hide_output": docs_chrome("docs.site.sequence.hide_output", language),
        "sequence_rundown": docs_chrome("docs.site.sequence.rundown", language),
        "sequence_previous_command": docs_chrome("docs.site.sequence.previous_command", language),
        "sequence_next_command": docs_chrome("docs.site.sequence.next_command", language),
        "sequence_shell": docs_chrome("docs.site.sequence.shell", language),
        "sequence_copy_command": docs_chrome("docs.site.sequence.copy_command", language),
        "sequence_copied": docs_chrome("docs.site.sequence.copied", language),
        "sequence_copy_failed": docs_chrome("docs.site.sequence.copy_failed", language),
        "sequence_command_output": docs_chrome("docs.site.sequence.command_output", language),
        "sequence_command_error_output": docs_chrome("docs.site.sequence.command_error_output", language),
        # The CLI token hover help.
        "cli_help_close": docs_chrome("docs.site.cli_help.close", language),
        "cli_help_required": docs_chrome("docs.site.cli_help.required", language),
        # The release download cards.
        "download_direct_heading": docs_chrome("docs.site.download.direct_heading", language),
    }
