"""The words the Renta design prototypes in the desktop's Storybook name.

The prototypes under ``native/desktop/frontend/src/dev/prototypes/renta`` are
the operator's review surface for the Renta workspace. They name two kinds of
key: their own chrome under ``desktop.renta.proto.``, and under
``workspace.renta.`` the words a proposed backend read would serve with its
data (outline headings, the imputation election, the settlement heading). A
key leaves this declaration when the prototype that names it is retired or the
backend serves the word itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

#: The groups of the proposed Renta outline the navigator names by template.
RENTA_OUTLINE_GROUPS: Final[tuple[str, ...]] = (
    "identification",
    "employment",
    "movable_capital",
    "real_estate",
    "activities",
    "capital_gains",
    "bases",
    "minimums",
    "liability",
    "result",
    "annexes",
    "other",
)

#: Every family the Renta prototypes build at run time, as ``prefix -> members``.
RENTA_FAMILIES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {"workspace.renta.outline.": RENTA_OUTLINE_GROUPS}
)

#: Every key the Renta prototypes name, each family member spelled out.
RENTA_KEYS: Final[frozenset[str]] = frozenset(
    {
        "workspace.renta.outline.credits",
        "workspace.renta.outline.family",
        "workspace.renta.election.title",
        "workspace.renta.election.undeclared",
        "workspace.renta.election.proposed",
        "workspace.renta.election.stated",
        "workspace.renta.result.settlement",
        "desktop.renta.proto.nav.title",
        "desktop.renta.proto.nav.served",
        "desktop.renta.proto.nav.proposed",
        "desktop.renta.proto.nav.technical",
        "desktop.renta.proto.nav.needs_you",
        "desktop.renta.proto.nav.failed",
        "desktop.renta.proto.nav.boxes",
        "desktop.renta.proto.nav.only_attention",
        "desktop.renta.proto.excerpt",
        "desktop.renta.proto.gap.title",
        "desktop.renta.proto.gap.body",
        "desktop.renta.proto.gap.operation",
        "desktop.renta.proto.family.profile",
        "desktop.renta.proto.family.boxes",
        "desktop.renta.proto.family.edit",
        "desktop.renta.proto.family.empty",
        "desktop.renta.proto.election.save",
        "desktop.renta.proto.election.year",
        "desktop.renta.proto.result.example",
        "desktop.renta.proto.result.composed",
    }
    | {f"{prefix}{member}" for prefix, members in RENTA_FAMILIES.items() for member in members}
)
