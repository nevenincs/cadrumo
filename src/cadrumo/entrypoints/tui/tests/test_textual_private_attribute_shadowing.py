"""No screen or widget may reuse a private attribute name Textual owns.

Every Textual node inherits a large private surface from ``MessagePump`` and
its descendants, assigned in their ``__init__`` bodies rather than declared on
the class, so it is invisible to ``dir()`` and to an editor's completion. A
subclass that picks one of those names for its own state silently rebinds the
framework's, and the framework keeps reading it.

That shipped: the operation modal tracked whether its observation poll should
stop in ``self._closing``, which is Textual's own flag for "this message pump
has been asked to close". Setting it made ``MessagePump._close_messages``
take its already-closing early return WITHOUT posting the stop sentinel, so
the pump never ended, ``Screen.remove`` waited on it forever, and app
shutdown hung. Two tests in the modal lifecycle suite did not fail -- they
HUNG, which is worse, because a hang is a timeout budget rather than a
verdict and it trains a suite to be run with ``--timeout`` and skimmed.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
import textwrap
from types import ModuleType

import pytest
from textual.message_pump import MessagePump

from ... import tui as tui_package

_TEXTUAL_ROOT = "textual"

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _self_assigned_attributes(cls: type) -> set[str]:
    """Every name the class body assigns to ``self``, from its own source.

    Read from the AST rather than from an instance: these names are created
    inside ``__init__`` at runtime, so no static inspection of the class
    object can see them and constructing a Textual node outside a running app
    is not something a gate should need to do.
    """
    try:
        source = inspect.getsource(cls)
    except (OSError, TypeError):
        return set()
    assigned: set[str] = set()
    for node in ast.walk(ast.parse(textwrap.dedent(source))):
        if isinstance(node, ast.Assign):
            targets: list[ast.expr] = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        assigned.update(
            target.attr
            for target in targets
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self"
        )
    return assigned


def _private(names: set[str]) -> set[str]:
    """Keep single-underscore names only.

    Public attributes are excluded deliberately: ``title`` and ``sub_title``
    are reactives Textual intends a screen to set, so assigning them is the
    documented API rather than a collision. Dunders are excluded as Python's.
    """
    return {name for name in names if name.startswith("_") and not name.startswith("__")}


def _textual_private_surface(cls: type) -> set[str]:
    """The private names ``cls`` inherits from Textual's own classes."""
    return {
        name
        for ancestor in cls.__mro__
        if ancestor is not cls and ancestor.__module__.split(".")[0] == _TEXTUAL_ROOT
        for name in _private(_self_assigned_attributes(ancestor))
    }


def _tui_modules() -> list[ModuleType]:
    modules: list[ModuleType] = []
    for info in pkgutil.walk_packages(tui_package.__path__, tui_package.__name__ + "."):
        if info.name.endswith(".__main__"):
            continue
        modules.append(importlib.import_module(info.name))
    return modules


def _tui_node_classes() -> list[type]:
    """Every Textual node class this package defines, at its defining module."""
    return [
        obj
        for module in _tui_modules()
        for obj in vars(module).values()
        if isinstance(obj, type) and issubclass(obj, MessagePump) and obj.__module__ == module.__name__
    ]


class _AnchorNode(MessagePump):
    """A node used only to anchor the reserved-surface derivation above.

    Its whole purpose is to make the gate's basis checkable: it inherits
    exactly what any screen inherits, so if the derivation stops finding
    Textual's private ``__init__`` names, the assertion that names one of
    them fails instead of the gate quietly having nothing to compare against.
    """


def test_no_screen_or_widget_rebinds_a_private_textual_attribute() -> None:
    """A subclass's own state must not land on a name the framework reads."""
    classes = _tui_node_classes()
    assert classes, "no Textual node classes were discovered; this gate would pass vacuously"
    assert "_closing" in _textual_private_surface(_AnchorNode), (
        "the AST read of Textual's own __init__ bodies found nothing recognisable; "
        "the reserved surface is derived from that source, so an empty or renamed "
        "one makes every assertion below vacuous rather than true"
    )

    collisions = {
        f"{cls.__module__}.{cls.__qualname__}": sorted(reserved)
        for cls in classes
        if (reserved := _private(_self_assigned_attributes(cls)) & _textual_private_surface(cls))
    }
    assert not collisions, (
        f"these classes assign private names Textual's own base classes already use: {collisions}. "
        "Rename the attribute rather than the framework's expectation of it -- the framework "
        "keeps reading its own name, so the collision is silent until something it guards stops happening."
    )
