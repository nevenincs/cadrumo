"""Describe a widget's own keys in the language now on screen.

A binding description written in a class body is resolved once, at import, so
the footer would keep naming keys in whichever language the process started in.
Each widget therefore rewrites its own entries on render. Entries are replaced
by assignment, never edited in place: an instance's binding table shares its
lists with the class, so an in-place edit would re-describe every instance.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import replace

from textual.binding import Binding

from .....core.i18n.render import tr


def describe_bindings(
    table: dict[str, list[Binding]], descriptions: Mapping[str, str], *, shown: Collection[str] | None = None
) -> None:
    """Give each named key its catalogue description, showing in the footer those ``shown`` names.

    Without ``shown`` every described key is shown. A key left out of the
    footer keeps its description, so the help and the key panel still name it.
    """
    for key, translation_key in descriptions.items():
        entries = table.get(key)
        if entries:
            label = tr(translation_key)
            show = shown is None or key in shown
            table[key] = [replace(binding, description=label, show=show) for binding in entries]


__all__ = ["describe_bindings"]
