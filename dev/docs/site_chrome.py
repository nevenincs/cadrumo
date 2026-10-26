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
through :func:`~dev.docs._locale_chrome.template_chrome`, which is as strict as
the resolver the generated reference surfaces use -- a key with no authored
value in the build language raises instead of degrading to English -- and which
records the string as the templates' own, because a template escapes and
educates nothing the way a docutils writer does.  ``docs/conf.py`` calls the two
functions below once when the configuration loads and hands the results to the
templates through ``html_context``; the build publishes the
:func:`site_chrome` mapping once per site root as the script the interaction
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

from ._locale_chrome import template_chrome

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
        "meta_title": template_chrome("docs.site.meta.title", language, product=product),
        "meta_short_title": template_chrome("docs.site.meta.short_title", language, product=product),
        "meta_description": template_chrome("docs.site.meta.description", language, product=product),
        "nav_getting_started": template_chrome("docs.site.nav.getting_started", language),
        "nav_cli_reference": template_chrome("docs.site.nav.cli_reference", language),
        "nav_how_it_works": template_chrome("docs.site.nav.how_it_works", language),
        "nav_api": template_chrome("docs.site.nav.api", language),
        "link_updates": template_chrome("docs.site.link.updates", language),
        "link_get_cadrumo": template_chrome("docs.site.link.get_cadrumo", language),
        "link_report_issue": template_chrome("docs.site.link.report_issue", language),
        "link_critical_updates": template_chrome("docs.site.link.critical_updates", language),
        "link_release_notes": template_chrome("docs.site.link.release_notes", language),
        "link_disclaimer": template_chrome("docs.site.link.disclaimer", language),
        "link_events_and_deadlines": template_chrome("docs.site.link.events_and_deadlines", language),
        "link_repository": template_chrome("docs.site.link.repository", language),
        "broadcast_label": template_chrome("docs.site.broadcast.label", language),
        "broadcast_message": template_chrome("docs.site.broadcast.message", language),
        "footer_stay_current": template_chrome("docs.site.footer.stay_current", language),
        "footer_get_help": template_chrome("docs.site.footer.get_help", language),
        "footer_trust_and_responsibility": template_chrome("docs.site.footer.trust_and_responsibility", language),
        "footer_note": template_chrome("docs.site.footer.note", language),
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
        "aria_site_updates": template_chrome("docs.site.aria.site_updates", language),
        "aria_broadcast_links": template_chrome("docs.site.aria.broadcast_links", language),
        "aria_dismiss_notice": template_chrome("docs.site.aria.dismiss_notice", language),
        "aria_toggle_navigation": template_chrome("docs.site.aria.toggle_navigation", language),
        "aria_primary_navigation": template_chrome("docs.site.aria.primary_navigation", language),
        "aria_search_documentation": template_chrome("docs.site.aria.search_documentation", language),
        "aria_repository": template_chrome("docs.site.aria.repository", language),
        "aria_toggle_theme": template_chrome("docs.site.aria.toggle_theme", language),
        "aria_toggle_toc": template_chrome("docs.site.aria.toggle_toc", language),
        "aria_breadcrumb": template_chrome("docs.site.aria.breadcrumb", language),
        "aria_language": template_chrome("docs.site.aria.language", language, language=language_endonym),
        "aria_footer_channels": template_chrome("docs.site.aria.footer_channels", language),
        "breadcrumb_home": template_chrome("docs.site.breadcrumb.home", language),
        "footer_kicker": template_chrome("docs.site.footer.kicker", language),
        # Search: the dedicated page, the sidebar trigger, and the palette.
        "search_page_title": template_chrome("docs.site.search.page_title", language),
        "search_noscript": template_chrome("docs.site.search.noscript", language),
        "search_placeholder": template_chrome("docs.site.search.placeholder", language),
        "search_query_label": template_chrome("docs.site.search.query_label", language),
        "search_searching": template_chrome("docs.site.search.searching", language),
        "search_result_one": template_chrome("docs.site.search.result_one", language),
        "search_result_many": template_chrome("docs.site.search.result_many", language),
        "search_full_text_for": template_chrome("docs.site.search.full_text_for", language),
        "search_open_full_text": template_chrome("docs.site.search.open_full_text", language),
        "search_full_text_crumb": template_chrome("docs.site.search.full_text_crumb", language),
        "search_on_this_page": template_chrome("docs.site.search.on_this_page", language),
        "search_result_fallback": template_chrome("docs.site.search.result_fallback", language),
        "search_hint_navigate": template_chrome("docs.site.search.hint_navigate", language),
        "search_hint_open": template_chrome("docs.site.search.hint_open", language),
        "search_hint_close": template_chrome("docs.site.search.hint_close", language),
        # Result category labels, keyed on the shipped display class and record kind.
        "class_label_casilla": template_chrome("docs.site.class_label.casilla", language),
        "class_label_modelo": template_chrome("docs.site.class_label.modelo", language),
        "class_label_legal": template_chrome("docs.site.class_label.legal", language),
        "class_label_cli": template_chrome("docs.site.class_label.cli", language),
        "class_label_technical": template_chrome("docs.site.class_label.technical", language),
        "class_label_doc": template_chrome("docs.site.class_label.doc", language),
        "kind_label_concept": template_chrome("docs.site.kind_label.concept", language),
        "kind_label_cli": template_chrome("docs.site.kind_label.cli", language),
        "kind_label_casilla": template_chrome("docs.site.kind_label.casilla", language),
        "kind_label_page": template_chrome("docs.site.kind_label.page", language),
        # The executed-sequence widget's controls.
        "sequence_show_output": template_chrome("docs.site.sequence.show_output", language),
        "sequence_hide_output": template_chrome("docs.site.sequence.hide_output", language),
        "sequence_rundown": template_chrome("docs.site.sequence.rundown", language),
        "sequence_previous_command": template_chrome("docs.site.sequence.previous_command", language),
        "sequence_next_command": template_chrome("docs.site.sequence.next_command", language),
        "sequence_shell": template_chrome("docs.site.sequence.shell", language),
        "sequence_copy_command": template_chrome("docs.site.sequence.copy_command", language),
        "sequence_copied": template_chrome("docs.site.sequence.copied", language),
        "sequence_copy_failed": template_chrome("docs.site.sequence.copy_failed", language),
        "sequence_command_output": template_chrome("docs.site.sequence.command_output", language),
        "sequence_command_error_output": template_chrome("docs.site.sequence.command_error_output", language),
        # The CLI token hover help.
        "cli_help_close": template_chrome("docs.site.cli_help.close", language),
        "cli_help_required": template_chrome("docs.site.cli_help.required", language),
        # The release download cards.
        "download_direct_heading": template_chrome("docs.site.download.direct_heading", language),
    }
