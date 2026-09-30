"""Describe a widget's own keys in the language now on screen.

A binding description written in a class body is resolved once, at import, so
the footer would keep naming keys in whichever language the process started in.
Each widget therefore rewrites its own entries on render. Entries are replaced
by assignment, never edited in place: an instance's binding table shares its
lists with the class, so an in-place edit would re-describe every instance.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from textual.binding import Binding

from .....core.i18n.render import tr


def describe_bindings(table: dict[str, list[Binding]], descriptions: Mapping[str, str]) -> None:
    """Give each named key its catalogue description and show it in the footer."""
    for key, translation_key in descriptions.items():
        entries = table.get(key)
        if entries:
            label = tr(translation_key)
            table[key] = [replace(binding, description=label, show=True) for binding in entries]


__all__ = ["describe_bindings"]
