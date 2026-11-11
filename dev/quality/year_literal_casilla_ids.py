"""Where Python code places a string as a casilla id, so a box numbered like a year is no year.

The official designs number boxes ``2003``, ``2038`` or ``2057``. A string is a
casilla id only where the code places it as one: given to the canonical
casilla-id parsers, typed ``CasillaId``, held under a casilla-named name, or
compared with a casilla-named operand. Each helper yields the ``id()`` of the
string nodes it places, for the year gate's Python reader to admit.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator, Sequence

from .year_literal_python_rules import YEAR_WORDS, node_name

#: The canonical casilla-id parsers in ``cadrumo.core.casilla_id``: the text one
#: is given, or the keys of the mapping one is given, is a casilla id.
_CASILLA_ID_PARSERS = frozenset({"validated_casilla_id"})
_CASILLA_ID_MAP_PARSERS = frozenset({"validated_casilla_id_map"})
#: The keywords a casilla-id parser reads its text from, beside its first argument.
_CASILLA_ID_PARSER_KEYWORDS = frozenset({"value", "values"})
#: The canonical casilla-id type alias.
_CASILLA_ID_TYPE = "CasillaId"
_CASILLA_WORD = re.compile(r"^casillas?$")
#: Words that make a casilla-named value a coordinate in time rather than a box:
#: ``casilla_storage_baseline``, ``casillas_by_revision``, ``casilla_year``.
_TEMPORAL_WORD = re.compile(
    rf"^(?:{YEAR_WORDS}|revisions?|editions?|periods?|periodo|predecessor|successor|baseline|epoch"
    r"|dates?|fecha|version|generation)$"
)
_SEQUENCE_TYPES = frozenset(
    {"tuple", "list", "set", "frozenset", "Sequence", "Iterable", "Collection", "AbstractSet", "MutableSequence"}
)
_MAPPING_TYPES = frozenset({"dict", "Mapping", "MutableMapping"})
_COLLECTING_CALLS = frozenset({"set", "frozenset", "tuple", "list", "sorted"})


def casilla_named(name: str) -> bool:
    """Whether ``name`` says it holds casilla ids: a ``casilla`` word and no word of time.

    ``casillas_by_id``, ``casilla_id`` and ``_PARENT_CASILLA`` say so;
    ``casillas_by_revision``, ``casilla_storage_baseline``, ``ejercicio_casilla``
    and ``box_retired_in`` do not, so a year they hold stays a year.
    """
    words = [word.lower() for word in re.split(r"_+|(?<=[a-z0-9])(?=[A-Z])", name) if word]
    return any(_CASILLA_WORD.match(word) for word in words) and not any(_TEMPORAL_WORD.match(word) for word in words)


def _collected(node: ast.AST | None) -> ast.expr | None:
    """The one value a ``set()``, ``sorted()`` or kindred call gathers, if ``node`` is such a call."""
    if isinstance(node, ast.Call) and node_name(node.func) in _COLLECTING_CALLS and len(node.args) == 1:
        return node.args[0]
    return None


def casilla_operand(node: ast.AST) -> bool:
    """Whether a comparison operand is a casilla id or a collection of them.

    A casilla-named name or attribute (``row.casilla_id``), the ``id`` of a
    casilla-named value (``casilla.id``, ``revision.casillas[0].id``), or such an
    operand gathered by ``set()``, ``sorted()`` and their kin.
    """
    gathered = _collected(node)
    if gathered is not None:
        return casilla_operand(gathered)
    if isinstance(node, ast.Attribute) and node.attr == "id":
        return casilla_named(node_name(node.value))
    return isinstance(node, (ast.Name, ast.Attribute)) and casilla_named(node_name(node))


def _shape_members(node: ast.AST | None) -> Sequence[ast.AST | None]:
    """What a value's shape places: itself, its elements or its keys."""
    if isinstance(node, ast.Constant):
        return (node,)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return node.elts
    if isinstance(node, ast.Dict):
        return node.keys
    return ()


def shaped_texts(node: ast.AST | None) -> Iterator[int]:
    """The texts a value places as casilla ids by its shape: itself, its elements or its keys."""
    gathered = _collected(node)
    if gathered is not None:
        yield from shaped_texts(gathered)
        return
    for member in _shape_members(node):
        if isinstance(member, ast.Constant) and isinstance(member.value, str):
            yield id(member)


def typed_casilla_texts(annotation: ast.AST | None, value: ast.AST | None) -> Iterator[int]:
    """The texts a value annotated with ``CasillaId`` places as casilla ids.

    ``CasillaId`` (or ``Final[CasillaId]``, ``CasillaId | None``) types the
    value; a sequence of ``CasillaId`` types its elements; a mapping keyed by
    ``CasillaId`` types its keys.
    """
    if annotation is None or value is None:
        return
    if isinstance(annotation, ast.BinOp):
        yield from typed_casilla_texts(annotation.left, value)
        yield from typed_casilla_texts(annotation.right, value)
    elif isinstance(annotation, (ast.Name, ast.Attribute)):
        if node_name(annotation) == _CASILLA_ID_TYPE and isinstance(value, ast.Constant):
            yield from shaped_texts(value)
    elif isinstance(annotation, ast.Subscript):
        yield from _subscripted_casilla_texts(annotation, value)


def _subscripted_casilla_texts(annotation: ast.Subscript, value: ast.AST) -> Iterator[int]:
    """The casilla-id texts a value holds under ``Final[...]`` or a container of ``CasillaId``."""
    parameters = annotation.slice.elts if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
    if not parameters:
        return
    container = node_name(annotation.value)
    first = parameters[0]
    if container == "Final":
        yield from typed_casilla_texts(first, value)
    elif node_name(first) == _CASILLA_ID_TYPE and _container_shapes(container, value):
        yield from shaped_texts(value)


def _container_shapes(container: str, value: ast.AST) -> bool:
    """Whether a value written for a sequence or mapping container has that container's shape."""
    if container in _SEQUENCE_TYPES:
        return isinstance(value, (ast.Tuple, ast.List, ast.Set, ast.Call))
    return container in _MAPPING_TYPES and isinstance(value, ast.Dict)


def parsed_casilla_texts(called: str, node: ast.Call) -> Iterator[int]:
    """The texts a call to a canonical casilla-id parser is given as casilla ids."""
    parsed = [
        *node.args[:1],
        *(keyword.value for keyword in node.keywords if keyword.arg in _CASILLA_ID_PARSER_KEYWORDS),
    ]
    if called in _CASILLA_ID_PARSERS:
        yield from (id(text) for text in parsed if isinstance(text, ast.Constant))
    if called in _CASILLA_ID_MAP_PARSERS:
        for mapping in parsed:
            if isinstance(mapping, ast.Dict):
                yield from shaped_texts(mapping)


def keyword_casilla_texts(node: ast.Call) -> Iterator[int]:
    """The texts a call passes under casilla-named keywords."""
    for keyword in node.keywords:
        if keyword.arg is not None and casilla_named(keyword.arg):
            yield from shaped_texts(keyword.value)
