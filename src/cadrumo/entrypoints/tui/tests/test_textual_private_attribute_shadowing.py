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
import inspect
import textwrap
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest
from textual.message_pump import MessagePump

from .....tests.inventory import (
    import_binding_map,
    package_python_files,
    python_files_under,
    qualified_name,
    resolve_dotted_origin,
)
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
    if isinstance(cls, _SourceTuiClass):
        return set(cls.assigned_attributes)
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


@dataclass(frozen=True)
class _SourceTuiClass:
    """A module-level TUI class declaration read from source."""

    module: str
    qualname: str
    bases: tuple[str, ...]
    assigned_attributes: frozenset[str]

    @property
    def __module__(self) -> str:
        return self.module

    @property
    def __qualname__(self) -> str:
        return self.qualname


def _source_class_catalogue(root: Path, package_name: str) -> tuple[_SourceTuiClass, ...]:
    """Parse module-level class declarations below *root* without importing them."""
    found: list[_SourceTuiClass] = []
    paths = (
        package_python_files(include_data=True)
        if root == Path(tui_package.__file__).resolve().parent
        else python_files_under(root)
    )
    for path in paths:
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if path.name == "__main__.py" or "tests" in relative.parts or path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        module = package_name + ("." + ".".join(relative.with_suffix("").parts[:-1]) if len(relative.parts) > 1 else "")
        if relative.stem != "__init__":
            module = f"{module}.{relative.stem}"
        bindings = import_binding_map(tree)
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            assigned: set[str] = set()
            for child in ast.walk(node):
                if isinstance(child, (ast.Assign, ast.AnnAssign)):
                    targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                    assigned.update(
                        target.attr
                        for target in targets
                        if isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                    )
            found.append(
                _SourceTuiClass(
                    module,
                    node.name,
                    tuple(
                        resolve_dotted_origin(qualified_name(base) or ast.unparse(base), bindings)
                        for base in node.bases
                    ),
                    frozenset(assigned),
                )
            )
    return tuple(found)


def _class_reference(origin: str, classes: tuple[_SourceTuiClass, ...]) -> _SourceTuiClass | None:
    exact = {f"{item.module}.{item.qualname}": item for item in classes}.get(origin)
    if exact is not None:
        return exact
    leaf = origin.rsplit(".", 1)[-1]
    matches = [item for item in classes if item.qualname.rsplit(".", 1)[-1] == leaf]
    return matches[0] if len(matches) == 1 else None


@cache
def _textual_private_by_class() -> dict[str, frozenset[str]]:
    """Return private ``self`` names for each Textual class, from installed source."""
    textual_root = Path(inspect.getfile(MessagePump)).resolve().parent
    classes = _source_class_catalogue(textual_root, "textual")
    by_key = {f"{item.module}.{item.qualname}": item for item in classes}
    by_name: dict[str, list[_SourceTuiClass]] = {}
    for item in classes:
        by_name.setdefault(item.qualname.rsplit(".", 1)[-1], []).append(item)
    memo: dict[str, frozenset[str]] = {}

    def resolve(origin: str) -> _SourceTuiClass | None:
        item = by_key.get(origin)
        if item is not None:
            return item
        matches = by_name.get(origin.rsplit(".", 1)[-1], [])
        return matches[0] if len(matches) == 1 else None

    def names(item: _SourceTuiClass) -> frozenset[str]:
        key = f"{item.module}.{item.qualname}"
        if key in memo:
            return memo[key]
        inherited = frozenset().union(*(names(base) for base in (resolve(origin) for origin in item.bases) if base))
        result = _private(set(item.assigned_attributes)) | inherited
        memo[key] = frozenset(result)
        return memo[key]

    # Only classes in Textual's MessagePump hierarchy are reserved surfaces.
    roots = {key for key in by_key if key.rsplit(".", 1)[-1] == "MessagePump"}
    result: dict[str, frozenset[str]] = {}
    for item in classes:
        key = f"{item.module}.{item.qualname}"
        if key in roots or any(
            (base := resolve(origin)) is not None and f"{base.module}.{base.qualname}" in roots for origin in item.bases
        ):
            result[key] = names(item)
    changed = True
    while changed:
        changed = False
        for item in classes:
            key = f"{item.module}.{item.qualname}"
            if key in result:
                continue
            if any(
                (base := resolve(origin)) is not None and f"{base.module}.{base.qualname}" in result
                for origin in item.bases
            ):
                result[key] = names(item)
                changed = True
    return result


@cache
def _tui_node_classes() -> tuple[_SourceTuiClass, ...]:
    classes = _source_class_catalogue(Path(tui_package.__file__).resolve().parent, tui_package.__name__)
    textual = _textual_private_by_class()
    by_key = {f"{item.module}.{item.qualname}": item for item in classes}
    by_name: dict[str, list[_SourceTuiClass]] = {}
    for item in classes:
        by_name.setdefault(item.qualname.rsplit(".", 1)[-1], []).append(item)

    def resolve(origin: str) -> _SourceTuiClass | None:
        key = origin
        if key in by_key:
            return by_key[key]
        matches = by_name.get(origin.rsplit(".", 1)[-1], [])
        return matches[0] if len(matches) == 1 else None

    textual_names = set(textual)
    selected: set[str] = set()
    changed = True
    while changed:
        changed = False
        for item in classes:
            key = f"{item.module}.{item.qualname}"
            if key in selected:
                continue
            if any(origin in textual_names for origin in item.bases) or any(
                (base := resolve(origin)) is not None and f"{base.module}.{base.qualname}" in selected
                for origin in item.bases
            ):
                selected.add(key)
                changed = True
    return tuple(item for item in classes if f"{item.module}.{item.qualname}" in selected)


def _textual_private_surface(cls: type) -> set[str]:
    """The private names ``cls`` inherits from Textual's own classes."""
    if isinstance(cls, _SourceTuiClass):
        return set(_textual_private_by_class().get(f"{cls.module}.{cls.qualname}", ()))
    return {
        name
        for ancestor in cls.__mro__
        if ancestor is not cls and ancestor.__module__.split(".")[0] == _TEXTUAL_ROOT
        for name in _private(_self_assigned_attributes(ancestor))
    }


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
