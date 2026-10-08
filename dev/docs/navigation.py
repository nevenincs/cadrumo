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

The collapsed branch still carries every sibling of the current page, so a
section of N pages spends N squared entries on its own sidebars. A generated
reference set whose index page already lists every member is named in
``cadrumo_navigation_listed_on_index``; inside such a section the sidebar keeps
the section and the page being read, and the index is where the others are found.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Final

from docutils import nodes
from sphinx.builders.html import StandaloneHTMLBuilder
from sphinx.environment.adapters.toctree import global_toctree_for_doc

if TYPE_CHECKING:
    from sphinx.application import Sphinx

#: Runs before Furo's own ``html-page-context`` handler, which is registered at
#: Sphinx's default priority (500) and reads ``context["toctree"]``.
NAVIGATION_PRIORITY: Final[int] = 400

#: Docnames of the section indexes whose members the sidebar does not enumerate.
LISTED_ON_INDEX_CONFIG: Final[str] = "cadrumo_navigation_listed_on_index"


def collapsed_toctree(toctree: Callable[..., str]) -> Callable[..., str]:
    """Return ``toctree`` with every call forced to the collapsed tree."""

    def collapsed(**kwargs: Any) -> str:
        return toctree(**{**kwargs, "collapse": True})

    return collapsed


def _members(app: Sphinx, section: str) -> frozenset[str]:
    """Return every page under one section index, at any depth."""
    includes = app.env.toctree_includes
    found: set[str] = set()
    pending = list(includes.get(section, ()))
    while pending:
        docname = pending.pop()
        if docname not in found:
            found.add(docname)
            pending.extend(includes.get(docname, ()))
    return frozenset(found)


def _drop_unread_members(tree: nodes.Element, unread: frozenset[str]) -> None:
    """Remove the entries that link to ``unread`` and any list left empty by it."""
    for item in list(tree.findall(nodes.list_item)):
        reference = next(iter(item.findall(nodes.reference)), None)
        if reference is None or "current" in item["classes"] or reference.get("refuri") not in unread:
            continue
        parent = item.parent
        parent.remove(item)
        if not parent.children:
            parent.parent.remove(parent)


def section_toctree(builder: StandaloneHTMLBuilder, pagename: str, members: frozenset[str]) -> Callable[..., str]:
    """Return the collapsed tree of a page in a section whose index lists its members.

    The tree is Sphinx's own collapsed tree less the members other than the page
    itself and its ancestors, so the section entry and the current entry keep the
    classes and nesting the theme decorates.
    """

    def rendered(**kwargs: Any) -> str:
        options = {"includehidden": False, **kwargs, "collapse": True}
        if options.get("maxdepth") == "":
            del options["maxdepth"]
        tree = global_toctree_for_doc(builder.env, pagename, builder, **options)
        if tree is None:
            return ""
        _drop_unread_members(tree, frozenset(builder.get_relative_uri(pagename, member) for member in members))
        return builder.render_partial(tree)["fragment"]

    return rendered


def collapse_page_navigation(
    app: Sphinx,
    pagename: str,
    templatename: str,
    context: dict[str, Any],
    doctree: nodes.document | None,
) -> None:
    """Replace the page context's ``toctree`` callable with its collapsed form."""
    del templatename, doctree
    toctree = context.get("toctree")
    if not callable(toctree):
        return
    builder = app.builder
    if isinstance(builder, StandaloneHTMLBuilder):
        for section in getattr(app.config, LISTED_ON_INDEX_CONFIG):
            members = _members(app, section)
            if pagename == section or pagename in members:
                context["toctree"] = section_toctree(builder, pagename, members)
                return
    context["toctree"] = collapsed_toctree(toctree)


def register(app: Sphinx) -> None:
    """Connect the collapsed navigation ahead of the theme's page-context handler."""
    app.add_config_value(LISTED_ON_INDEX_CONFIG, default=[], rebuild="html", types=frozenset({list, tuple}))
    app.connect("html-page-context", collapse_page_navigation, priority=NAVIGATION_PRIORITY)
