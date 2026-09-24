"""Render each page's sidebar navigation as Sphinx's collapsed toctree.

Furo builds its sidebar by asking the page context's ``toctree`` callable for
the whole site tree (``collapse=False``) on every page. Sphinx then deep-copies
the table of contents of every document for every page, so rendering cost and
page size both grow with the square of the page count; on the full-scope site
the sidebar was most of every page and most of the build.

With ``collapse=True`` Sphinx copies only the current branch: the page's
ancestors, their siblings, the top-level sections and the page's own children.
This module supplies Furo with that tree by wrapping the context's ``toctree``
callable before Furo reads it. The output is Sphinx's own collapsed rendering,
so Furo's decoration, styling and keyboard behaviour are unchanged and every page
stays fully navigable without JavaScript.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from docutils import nodes
    from sphinx.application import Sphinx

#: Runs before Furo's own ``html-page-context`` handler, which is registered at
#: Sphinx's default priority (500) and reads ``context["toctree"]``.
NAVIGATION_PRIORITY: Final[int] = 400


def collapsed_toctree(toctree: Callable[..., str]) -> Callable[..., str]:
    """Return ``toctree`` with every call forced to the collapsed tree."""

    def collapsed(**kwargs: Any) -> str:
        return toctree(**{**kwargs, "collapse": True})

    return collapsed


def collapse_page_navigation(
    app: Sphinx,
    pagename: str,
    templatename: str,
    context: dict[str, Any],
    doctree: nodes.document | None,
) -> None:
    """Replace the page context's ``toctree`` callable with its collapsed form."""
    del app, pagename, templatename, doctree
    toctree = context.get("toctree")
    if callable(toctree):
        context["toctree"] = collapsed_toctree(toctree)


def register(app: Sphinx) -> None:
    """Connect the collapsed navigation ahead of the theme's page-context handler."""
    app.connect("html-page-context", collapse_page_navigation, priority=NAVIGATION_PRIORITY)
