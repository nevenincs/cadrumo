"""Derive a per-verb JSON input schema from the CLI's own click parameters.

Each operator-callable registry command key resolves to exactly one leaf in the
``aeat`` Typer/click command tree. This module walks that tree once, reads each
command's declared parameters (positional :class:`click.Argument`s and
``--option`` :class:`click.Option`s), and projects them into a strict, typed
:class:`VerbInputSchema`: the ordered parameter list, each parameter's JSON type,
requiredness, enum choices, multiplicity, and flag shape, plus the *resolved* CLI
path tokens.

The resolved path is load-bearing. A registry command key carries segment tokens
with underscores (``app.live.iva_wallet.pull``) while the live CLI command is
hyphenated (``aeat app live iva-wallet pull``); walking the real tree records the
command names as click knows them, so :func:`cli_argv_for` builds an argv that
actually dispatches. The prior ``{args: [string]}`` bag forced the operator to
run ``--help`` per verb and split the argv itself; a per-verb schema replaces it
so a client renders a typed form and the console maps named arguments back to CLI
tokens deterministically.

This module owns no MCP protocol detail. It reads the CLI command tree and emits
SDK-independent pydantic records, so it is unit-tested directly.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Typer builds its command tree on a vendored copy of click, not the top-level
# ``click`` package, so the tree-walk types and the ``Context`` used to resolve
# lazily-loaded subcommands must come from ``typer._click`` - the same source
# ``_command_suggestions`` uses - or a static type check sees two distinct
# ``Command`` classes.
from typer._click.core import Command as ClickCommand
from typer._click.core import Context as ClickContext
from typer._click.core import Parameter as ClickParameter
from typer.main import get_command as _typer_get_command

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class VerbParamKind(StrEnum):
    """Whether a parameter is a positional argument or a ``--`` option."""

    ARGUMENT = "argument"
    OPTION = "option"


class JsonType(StrEnum):
    """The JSON Schema scalar type a CLI parameter projects onto."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"


class VerbParameter(BaseModel):
    """One CLI parameter projected into a JSON-schema property.

    ``name`` is the click parameter name (the JSON property key). For an
    :attr:`VerbParamKind.OPTION` the ``cli_flag`` is the long option token
    (``--file``); for an :attr:`VerbParamKind.ARGUMENT` it is empty and the value
    is a bare positional. ``multiple`` renders the property as a JSON array and
    repeats the token per element; ``is_flag`` is a bare boolean switch that
    emits only its flag when truthy.
    """

    model_config = _STRICT_FROZEN

    name: str = Field(min_length=1)
    kind: VerbParamKind
    cli_flag: str = ""
    json_type: JsonType
    required: bool
    is_flag: bool
    multiple: bool
    choices: tuple[str, ...] = ()
    default: bool | int | float | str | None = None
    help: str = ""

    def _scalar_schema(self) -> dict[str, Any]:
        scalar: dict[str, Any] = {"type": self.json_type.value}
        if self.choices:
            scalar["enum"] = list(self.choices)
        if self.help:
            scalar["description"] = self.help
        return scalar

    def property_schema(self) -> dict[str, Any]:
        """Return the JSON-schema fragment for this parameter's property."""
        if self.multiple:
            return {"type": "array", "items": self._scalar_schema()}
        return self._scalar_schema()


class VerbInputSchema(BaseModel):
    """The strict per-verb input contract for one exposed MCP tool.

    ``cli_path`` is the resolved command path as click names it (hyphenated leaf
    tokens), so dispatch never re-derives it from the underscored command key.
    ``parameters`` preserves the CLI declaration order, which :func:`cli_argv_for`
    relies on to place positional arguments before options.
    """

    model_config = _STRICT_FROZEN

    command_key: str = Field(min_length=1)
    cli_path: tuple[str, ...] = Field(min_length=1)
    parameters: tuple[VerbParameter, ...] = ()

    def json_schema(self) -> dict[str, Any]:
        """Project the parameters into a JSON Schema object for the tool.

        Returns:
            A JSON Schema ``object`` with one property per parameter, the
            required names, and ``additionalProperties`` closed.
        """
        properties = {parameter.name: parameter.property_schema() for parameter in self.parameters}
        required = [parameter.name for parameter in self.parameters if parameter.required]
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }


def _json_type_for(parameter: ClickParameter, *, is_flag: bool, choices: tuple[str, ...]) -> JsonType:
    """Map a click parameter's type onto a JSON scalar type.

    Enum choices and custom Typer converters both surface as strings; only the
    numeric and boolean primitives narrow further. The mapping keys on the click
    ``ParamType`` class name so it works against Typer's vendored click types.
    """
    if is_flag:
        return JsonType.BOOLEAN
    if choices:
        return JsonType.STRING
    type_name = type(parameter.type).__name__
    if "Int" in type_name:
        return JsonType.INTEGER
    if "Float" in type_name:
        return JsonType.NUMBER
    if "Bool" in type_name:
        return JsonType.BOOLEAN
    return JsonType.STRING


def _option_flag(parameter: ClickParameter) -> str:
    """Return the long ``--`` option token for an option parameter."""
    opts = tuple(parameter.opts)
    return next((opt for opt in opts if opt.startswith("--")), opts[0] if opts else "")


def _json_safe_default(value: object) -> bool | int | float | str | None:
    """Coerce a click default to a JSON-safe scalar, dropping complex defaults."""
    if isinstance(value, bool | int | float | str):
        return value
    return None


def _parameter_from_click(parameter: ClickParameter) -> VerbParameter | None:
    """Project one click parameter into a :class:`VerbParameter`, or ``None``.

    Returns ``None`` for hidden parameters and the unnamed context parameter, so
    only operator-facing inputs reach the schema.
    """
    name = parameter.name
    if name is None or getattr(parameter, "hidden", False):
        return None
    # Typer's vendored click types are not the top-level ``click.Argument`` /
    # ``click.Option`` classes, so ``isinstance`` misclassifies them. The
    # ``param_type_name`` marker ("argument" / "option") is stable across both.
    is_argument = getattr(parameter, "param_type_name", "") == "argument"
    is_flag = bool(getattr(parameter, "is_flag", False))
    raw_choices = getattr(parameter.type, "choices", None)
    choices = tuple(str(choice) for choice in raw_choices) if raw_choices else ()
    return VerbParameter(
        name=name,
        kind=VerbParamKind.ARGUMENT if is_argument else VerbParamKind.OPTION,
        cli_flag="" if is_argument else _option_flag(parameter),
        json_type=_json_type_for(parameter, is_flag=is_flag, choices=choices),
        required=bool(getattr(parameter, "required", False)),
        is_flag=is_flag,
        multiple=bool(getattr(parameter, "multiple", False)),
        choices=choices,
        default=None if is_argument else _json_safe_default(parameter.default),
        help=str(getattr(parameter, "help", "") or ""),
    )


def _naive_cli_path(command_key: str) -> tuple[str, ...]:
    """Project a command key onto CLI path tokens without tree resolution.

    ``config.*`` and ``app.*`` keys carry their own root segment; every other key
    is a child of ``app``. Used as the fallback path when a key does not resolve
    to a live command (a stale registry key).
    """
    tokens = command_key.split(".")
    if tokens[0] in {"config", "app"}:
        return tuple(tokens)
    return ("app", *tokens)


def _resolve_command(
    root: ClickCommand,
    command_key: str,
) -> tuple[ClickCommand | None, tuple[str, ...]]:
    """Walk the CLI tree to the leaf command for ``command_key``.

    Threads a fresh child :class:`click.Context` at each level so lazily-loaded
    subcommand modules materialise exactly as they do under real dispatch. A key
    segment is matched against the underscored token first, then the hyphenated
    form, so ``iva_wallet`` resolves to the ``iva-wallet`` command. Returns the
    resolved command (or ``None``) and the command names as click knows them.
    """
    command: ClickCommand | None = root
    context = ClickContext(root, info_name=str(root.name))
    resolved: list[str] = []
    for token in _naive_cli_path(command_key):
        getter = getattr(command, "get_command", None)
        if getter is None:
            return None, tuple(resolved)
        try:
            child = getter(context, token) or getter(context, token.replace("_", "-"))
        except Exception:
            # Materialising a lazily-loaded subtree can raise when a command in it
            # declares a parameter type Typer cannot convert to click. Degrade to an
            # unresolved command so only that subtree's keys fall back to an
            # argument-free schema, rather than letting one hostile parameter brick
            # the entire tool surface.
            return None, tuple(resolved)
        if child is None:
            return None, tuple(resolved)
        resolved.append(str(child.name))
        context = ClickContext(child, parent=context, info_name=str(child.name))
        command = child
    return command, tuple(resolved)


def build_verb_input_schema(root: ClickCommand, command_key: str) -> VerbInputSchema:
    """Build the :class:`VerbInputSchema` for one command key.

    Resolves the leaf command in the tree rooted at ``root`` and reads its click
    parameters. A key that does not resolve to a live command - a stale registry
    key, or one whose subtree cannot be introspected because a command in it
    declares a Typer-unconvertible parameter type - falls back to an empty
    parameter set over the naive path, yielding a valid (argument-free) descriptor
    rather than crashing the whole tool-surface build.

    Returns:
        The strict :class:`VerbInputSchema` for the command.
    """
    command, resolved = _resolve_command(root, command_key)
    if command is None:
        return VerbInputSchema(command_key=command_key, cli_path=_naive_cli_path(command_key), parameters=())
    parameters = tuple(
        projected for parameter in command.params if (projected := _parameter_from_click(parameter)) is not None
    )
    cli_path = resolved or _naive_cli_path(command_key)
    return VerbInputSchema(command_key=command_key, cli_path=cli_path, parameters=parameters)


def build_verb_input_schemas(command_keys: tuple[str, ...]) -> dict[str, VerbInputSchema]:
    """Build the per-verb input schemas for every command key.

    Materialises the ``aeat`` click command once and walks it per key. The walk
    imports each lazily-loaded command subtree exactly as real dispatch does, so
    the schemas reflect the live CLI surface.

    Returns:
        A mapping of command key to its :class:`VerbInputSchema`.
    """
    from ..cli import app as cli_app

    root = _typer_get_command(cli_app)
    return {key: build_verb_input_schema(root, key) for key in command_keys}


def cli_argv_for(schema: VerbInputSchema, arguments: dict[str, object]) -> list[str]:
    """Build the ``aeat`` argv tail for a tool call from named ``arguments``.

    Positional arguments are emitted in their CLI declaration order and precede
    every option; a multiple argument or option repeats per element; a boolean
    flag emits only its token when truthy. ``--format json`` leads the tail so the
    machine envelope is always requested, followed by the resolved command path.

    Returns:
        The argv tokens that follow the ``aeat`` executable.
    """
    positional: list[str] = []
    options: list[str] = []
    for parameter in schema.parameters:
        if parameter.name not in arguments:
            continue
        value = arguments[parameter.name]
        if parameter.kind is VerbParamKind.ARGUMENT:
            if parameter.multiple and isinstance(value, list | tuple):
                positional.extend(str(item) for item in value)
            else:
                positional.append(str(value))
            continue
        if parameter.is_flag:
            if value:
                options.append(parameter.cli_flag)
        elif parameter.multiple and isinstance(value, list | tuple):
            for item in value:
                options.extend((parameter.cli_flag, str(item)))
        else:
            options.extend((parameter.cli_flag, str(value)))
    return ["--format", "json", *schema.cli_path, *positional, *options]
