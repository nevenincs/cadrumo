"""Executable command syntax derived from the production command graphs."""

from __future__ import annotations

import re
import shlex
from functools import lru_cache
from typing import TYPE_CHECKING, get_args

from pydantic import BaseModel

from cadrumo_client.commands.shared_contracts import BindingState

if TYPE_CHECKING:
    from cadrumo_client.commands.graph import CommandSpecGraph


def _command_graphs() -> tuple[CommandSpecGraph, ...]:
    """Load spec authorities only when needed, without resolving their handlers."""
    from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH
    from cadrumo_runtime.commands.command_specs import RUNTIME_COMMAND_GRAPH

    return COMMAND_GRAPH, RUNTIME_COMMAND_GRAPH


@lru_cache(maxsize=1)
def executable_command_paths() -> frozenset[tuple[str, ...]]:
    """Cache complete implemented leaf paths for one audit process."""
    return frozenset(
        node.path
        for graph in _command_graphs()
        for node in graph.nodes()
        if node.spec.kind == "leaf" and node.spec.handler is not None and node.spec.handler.state is BindingState.TARGET
    )


@lru_cache(maxsize=1)
def _compile_command_paths(paths: frozenset[tuple[str, ...]]) -> re.Pattern[str]:
    """Match horizontal command spacing and refuse partial word/hyphen matches."""
    alternatives = [
        r"[ \t]+".join(re.escape(token) for token in path) for path in sorted(paths, key=lambda p: (-len(p), p))
    ]
    if not alternatives:
        return re.compile(r"(?!)")
    return re.compile(r"(?<![\w-])(?:" + "|".join(alternatives) + r")(?![\w-])")


def command_path_pattern() -> re.Pattern[str]:
    """Return exact executable path syntax; arguments and prose remain separate."""
    return _compile_command_paths(executable_command_paths())


@lru_cache(maxsize=1)
def registered_operation_id_pattern() -> re.Pattern[str]:
    """Match complete operation identifiers from the generated command contract."""
    from cadrumo.entrypoints.cli.command_operation_table import COMMAND_OPERATION_ROWS

    operations = {operation for _path, operation in COMMAND_OPERATION_ROWS if operation is not None}
    alternatives = "|".join(re.escape(value) for value in sorted(operations, key=lambda value: (-len(value), value)))
    return re.compile(r"(?<![\w.-])(?:" + alternatives + r")(?![\w.-])") if alternatives else re.compile(r"(?!)")


def _admitted_wire_row(model: object, admitted: set[str]) -> tuple[str, tuple[frozenset[str], frozenset[str]]] | None:
    """Project one admitted wire model's required and allowed fields."""
    if not isinstance(model, type) or not issubclass(model, BaseModel):
        raise TypeError("detail-row union contains a non-model variant")
    kind = model.model_fields["row_type"].default
    if not isinstance(kind, str):
        raise ValueError("detail-row discriminator is missing")
    if kind not in admitted:
        return None
    allowed = frozenset(model.model_fields) - {"row_type"}
    required = frozenset(name for name, field in model.model_fields.items() if field.is_required()) - {"row_type"}
    return kind, (allowed, required)


@lru_cache(maxsize=1)
def _detail_row_fields() -> dict[str, tuple[frozenset[str], frozenset[str]]]:
    """Read allowed and required field names from the public wire union."""
    from cadrumo.application.modelo.edit_apply_row_contracts import ModeloDetailRowWireV1
    from cadrumo.entrypoints.cli.modelo_row_contracts import SUPPORTED_DETAIL_ROW_MODELS

    union = get_args(ModeloDetailRowWireV1.__value__)[0]
    result: dict[str, tuple[frozenset[str], frozenset[str]]] = {}
    admitted = {str(model.model_fields["row_type"].default) for model in SUPPORTED_DETAIL_ROW_MODELS}
    for model in get_args(union):
        entry = _admitted_wire_row(model, admitted)
        if entry is None:
            continue
        kind, fields = entry
        if kind in result:
            raise ValueError("detail-row discriminator is duplicated")
        result[kind] = fields
    if set(result) != admitted:
        raise ValueError("CLI detail-row models do not match the wire union")
    return result


_ROW_EXAMPLE_RE = re.compile(r"(?<![\w-])--row[ \t]+'(?P<spec>[^'\r\n]+)'")
_QUOTED_ROW_KIND_RE = re.compile(r"(?<!\w)'(?P<kind>[a-z][a-z0-9_.-]*)'(?!\w)")


def _valid_detail_row_fields(parts: list[str], field_sets: tuple[frozenset[str], frozenset[str]]) -> bool:
    """Require nonempty, unique fields belonging to the selected wire row."""
    pairs = [part.partition("=") for part in parts]
    if any(not separator or not field_value for _name, separator, field_value in pairs):
        return False
    names = [name for name, _separator, _field_value in pairs]
    allowed, required = field_sets
    return len(set(names)) == len(names) and required <= set(names) <= allowed


def _valid_detail_row_spec(spec: str) -> bool:
    """Check CLI token structure against the wire model's field names."""
    try:
        parts = shlex.split(spec)
    except ValueError:
        return False
    fields = _detail_row_fields().get(parts[0]) if parts else None
    return fields is not None and len(parts) >= 2 and _valid_detail_row_fields(parts[1:], fields)


def _filter_complete_row_kind_list(value: str) -> tuple[str, int]:
    """Remove only a complete, unique list of the real wire discriminators."""
    matches = tuple(_QUOTED_ROW_KIND_RE.finditer(value))
    known = _detail_row_fields()
    if len(matches) != len(known) or {match.group("kind") for match in matches} != set(known):
        return value, 0
    text = list(value)
    for match in matches:
        text[match.start() : match.end()] = [" "] * (match.end() - match.start())
    return "".join(text), 1


def filter_detail_row_examples(value: str) -> tuple[str, int]:
    """Exclude complete row arguments only when their wire field names exist."""
    excluded = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal excluded
        if not _valid_detail_row_spec(match.group("spec")):
            return match.group()
        excluded += 1
        return " "

    value = _ROW_EXAMPLE_RE.sub(replace, value)
    if not excluded:
        return value, 0
    value, list_excluded = _filter_complete_row_kind_list(value)
    return value, excluded + list_excluded
