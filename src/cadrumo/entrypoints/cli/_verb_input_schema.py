"""Derive a per-verb JSON input schema from the CLI's own click parameters.

Each operator-callable registry command key resolves to exactly one leaf in the
``aeat`` Typer/click command tree. This module walks that tree once, reads each
command's declared parameters (positional :class:`~click.Argument`s and
``--option`` :class:`~click.Option`s), and projects them into a strict, typed
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

from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar, Final, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Typer builds its command tree on a vendored copy of click, not the top-level
# ``click`` package, so the tree-walk types and the ``Context`` used to resolve
# lazily-loaded subcommands must come from ``typer._click`` - the same source
# ``_command_suggestions`` uses - or a static type check sees two distinct
# ``Command`` classes.
from typer._click.core import Command as ClickCommand
from typer._click.core import Context as ClickContext
from typer._click.core import Parameter as ClickParameter
from typer.main import get_command as _typer_get_command

from ...application.operator_actions import (
    OPERATOR_ACTION_CATALOGUE,
    ActionArgumentBindingSpecification,
    ActionCatalogue,
)
from ...application.operator_surface import (
    CommandSchemaRef,
    InputSchemaInventoryRow,
    LiveLeafInventoryRow,
    OperatorSurfaceReconciliation,
    ReconciledOperatorLeaf,
    ResultSchemaInventoryRow,
    resolve_action_catalogue,
)
from ..schema_surface import CLI_PATH_BY_SCHEMA_KEY, GROUP_CALLBACK_SCHEMA_KEYS, ROOT_LANDING_SCHEMA_KEYS

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")
_ACTION_CAPABILITIES_SCHEMA_KEY = "x-cadrumo-action-capabilities"


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


class VerbLeafKind(StrEnum):
    """The live Click surface addressed by one registered schema key."""

    COMMAND = "command"
    CALLBACK = "callback"


class VerbParameter(BaseModel):
    """One CLI parameter projected into a JSON-schema property.

    ``name`` is the click parameter name (the JSON property key). For an
    :attr:`~entrypoints.cli._verb_input_schema.VerbParamKind.OPTION` the
    ``cli_flag`` is the long option token (``--file``); for an
    :attr:`~entrypoints.cli._verb_input_schema.VerbParamKind.ARGUMENT` it is empty
    and the value is a bare positional. ``multiple`` renders the property as a
    JSON array and repeats the token per element; ``is_flag`` is a bare boolean
    switch that emits its ``cli_flag`` when truthy and, for a ``--flag/--no-flag``
    pair, its ``off_flag`` (the secondary ``--no-`` token) when explicitly false.
    ``default`` carries the parameter's click default rendered JSON-safely, so a
    client can see the real default (including a default-on flag it may disable).
    """

    model_config = _STRICT_FROZEN

    name: str = Field(min_length=1)
    kind: VerbParamKind
    cli_flag: str = ""
    off_flag: str = ""
    json_type: JsonType
    required: bool
    is_flag: bool
    multiple: bool
    choices: tuple[str, ...] = ()
    default: bool | int | float | str | list[Any] | None = None
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
        schema: dict[str, Any] = (
            {"type": "array", "items": self._scalar_schema()} if self.multiple else self._scalar_schema()
        )
        if self.default is not None:
            # The default is already JSON-safe (see ``_json_safe_default``); surface
            # it so a client renders the real default rather than a blank field.
            schema["default"] = self.default
        return schema


class ResolvedVerbLeaf(BaseModel):
    """One registered subject leaf resolved against the live Click command tree.

    ``subject_leaf_key`` is the stable result-schema identity used by every
    operator-surface join. ``cli_path`` is the canonical path Click dispatches.
    ``alias_paths`` records the symbolic path used to reach a relocated or
    hyphenated Click leaf; it is evidence of resolution, never an alternate
    dispatch target. A caller must always execute ``cli_path``.
    """

    model_config = _STRICT_FROZEN

    subject_leaf_key: str = Field(min_length=1)
    cli_path: tuple[str, ...]
    alias_paths: tuple[tuple[str, ...], ...] = ()
    kind: VerbLeafKind


class VerbLeafResolutionFailure(BaseModel):
    """Evidence retained when a registered subject leaf cannot resolve.

    A schema build must fail rather than emit a parameter-free fallback, but the
    error must preserve the stable subject key, complete attempted path, and
    successfully resolved prefix so the live-surface reconciliation can locate
    the broken registration or lazy subtree.
    """

    model_config = _STRICT_FROZEN

    subject_leaf_key: str = Field(min_length=1)
    attempted_cli_path: tuple[str, ...]
    resolved_cli_path: tuple[str, ...] = ()
    reason: str = Field(min_length=1)


class McpActionCapability(BaseModel):
    """One canonical action capability projected onto its target MCP tool.

    The application action catalogue remains the declaration authority and the
    shared operator-surface resolver remains the live-schema authority.  This
    DTO carries only their resolution evidence: the stable action and target
    identities, the resolved Click path, the complete required-input names,
    and the catalogue's argument-source specifications.  It contains no
    applicability predicate, runtime argument value, localized prose, or CLI
    command string.
    """

    model_config = _STRICT_FROZEN

    action_id: str = Field(min_length=1)
    target_command_key: str = Field(min_length=1)
    cli_path: tuple[str, ...]
    required_input_names: tuple[str, ...] = ()
    argument_specifications: tuple[ActionArgumentBindingSpecification, ...] = ()

    @field_validator("required_input_names")
    @classmethod
    def _required_inputs_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("MCP action capability required input names must be unique")
        return value


class VerbInputSchema(BaseModel):
    """The strict per-verb input contract for one exposed MCP tool.

    ``cli_path`` is the resolved command path as click names it (hyphenated leaf
    tokens), so dispatch never re-derives it from the underscored command key.
    ``parameters`` preserves the CLI declaration order, which :func:`cli_argv_for`
    relies on to place positional arguments before options.
    """

    model_config = _STRICT_FROZEN

    command_key: str = Field(min_length=1)
    cli_path: tuple[str, ...]
    parameters: tuple[VerbParameter, ...] = ()
    #: The command's own one-line help (its click ``short_help`` / first help
    #: line), so the MCP tool description can be verb-specific rather than the
    #: shared family intent.
    help: str = ""
    action_capabilities: tuple[McpActionCapability, ...] = ()

    @field_validator("action_capabilities")
    @classmethod
    def _action_ids_are_unique_and_ordered(
        cls,
        value: tuple[McpActionCapability, ...],
    ) -> tuple[McpActionCapability, ...]:
        action_ids = tuple(capability.action_id for capability in value)
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("MCP action capability IDs must be unique per target command")
        return tuple(sorted(value, key=lambda capability: capability.action_id))

    @model_validator(mode="after")
    def _capabilities_target_this_live_schema(self) -> VerbInputSchema:
        required_input_names = tuple(parameter.name for parameter in self.required_inputs)
        for capability in self.action_capabilities:
            if capability.target_command_key != self.command_key:
                raise ValueError(
                    f"MCP action capability target mismatch: schema={self.command_key}, "
                    f"action={capability.action_id}, target={capability.target_command_key}"
                )
            if capability.cli_path != self.cli_path:
                raise ValueError(
                    f"MCP action capability Click-path mismatch for {capability.action_id}: "
                    f"schema={' '.join(self.cli_path)}, action={' '.join(capability.cli_path)}"
                )
            if capability.required_input_names != required_input_names:
                raise ValueError(
                    f"MCP action capability required-input mismatch for {capability.action_id}: "
                    f"schema={required_input_names}, action={capability.required_input_names}"
                )
        return self

    @property
    def resolved_leaf(self) -> ResolvedVerbLeaf:
        """Return this schema's immutable identity in the live Click tree.

        The descriptor is derived from the canonical schema key, resolved Click
        path, and callback inventory. It deliberately does not invent a second
        source of truth for those identities.
        """
        symbolic_path = _symbolic_cli_path(self.command_key)
        aliases = () if symbolic_path == self.cli_path else (symbolic_path,)
        return ResolvedVerbLeaf(
            subject_leaf_key=self.command_key,
            cli_path=self.cli_path,
            alias_paths=aliases,
            kind=VerbLeafKind.CALLBACK if self.command_key in GROUP_CALLBACK_SCHEMA_KEYS else VerbLeafKind.COMMAND,
        )

    @property
    def required_inputs(self) -> tuple[VerbParameter, ...]:
        """Return the complete live metadata for every required CLI input.

        The result is derived from the projected Click parameters rather than a
        second handwritten list, retaining positional/option shape, flags,
        multiplicity, types, choices, and requiredness for action validation.
        """
        return tuple(parameter for parameter in self.parameters if parameter.required)

    def json_schema(self) -> dict[str, Any]:
        """Project the parameters into a JSON Schema object for the tool.

        Returns:
            A JSON Schema ``object`` with one property per parameter, the
            required names, and ``additionalProperties`` closed.
        """
        properties = {parameter.name: parameter.property_schema() for parameter in self.parameters}
        required = [parameter.name for parameter in self.parameters if parameter.required]
        schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }
        if self.action_capabilities:
            schema[_ACTION_CAPABILITIES_SCHEMA_KEY] = [
                capability.model_dump(mode="json") for capability in self.action_capabilities
            ]
        return schema


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


def _secondary_flag(parameter: ClickParameter) -> str:
    """Return the long ``--no-`` off-token of a boolean flag pair, or ``""``.

    A click boolean option declared as ``--flag/--no-flag`` records the negative
    token in ``secondary_opts``; a bare ``--flag`` switch has none. The off-token
    is what lets a client turn a default-on flag OFF through the MCP surface.
    """
    secondary = tuple(getattr(parameter, "secondary_opts", ()) or ())
    for option in secondary:
        if isinstance(option, str) and option.startswith("--"):
            return option
    return ""


def _json_safe_default(value: object) -> bool | int | float | str | list[Any] | None:
    """Render a click default JSON-safely, or ``None`` when unserialisable.

    Scalars pass through unchanged; a :class:`~pathlib.Path` renders as its
    string form; a tuple or list renders as a JSON array of its recursively
    json-safe items. Only a genuinely unserialisable object falls back to
    ``None`` (rather than every non-scalar default silently becoming null).
    """
    if isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple | list):
        return [_json_safe_default(item) for item in cast(Sequence[object], value)]
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
    if raw_choices is None:
        # A ``click_type=click.Choice(...)`` passed to ``typer.Option`` is wrapped
        # in Typer's ``FuncParamType`` whose own ``.choices`` is ``None``; the
        # original ``click.Choice`` (and its closed value set) survives on
        # ``.func``. Without this unwrap the enum axis renders as a bare string in
        # the MCP input schema (``aeat-architecture-boundaries``: a closed value
        # set must surface its accepted values). Typing the option as an enum is
        # the preferred form, but for options whose enum values differ in case
        # from the CLI tokens the ``click_type`` Choice is the only way to keep
        # the lowercase tokens, so the schema must read through the wrapper.
        raw_choices = getattr(getattr(parameter.type, "func", None), "choices", None)
    choices = tuple(str(choice) for choice in raw_choices) if raw_choices else ()
    return VerbParameter(
        name=name,
        kind=VerbParamKind.ARGUMENT if is_argument else VerbParamKind.OPTION,
        cli_flag="" if is_argument else _option_flag(parameter),
        off_flag="" if is_argument else _secondary_flag(parameter),
        json_type=_json_type_for(parameter, is_flag=is_flag, choices=choices),
        required=bool(getattr(parameter, "required", False)),
        is_flag=is_flag,
        multiple=bool(getattr(parameter, "multiple", False)),
        choices=choices,
        default=None if is_argument else _json_safe_default(cast(object, parameter.default)),
        help=str(getattr(parameter, "help", "") or ""),
    )


def _symbolic_cli_path(command_key: str) -> tuple[str, ...]:
    """Project a schema key into its unrelocated symbolic CLI path."""
    if command_key in ROOT_LANDING_SCHEMA_KEYS:
        return () if command_key == "root.status" else (command_key.removeprefix("root."),)
    tokens = command_key.split(".")
    if tokens[0] in {"config", "app"}:
        return tuple(tokens)
    return ("app", *tokens)


def _naive_cli_path(command_key: str) -> tuple[str, ...]:
    """Project a command key onto the path to attempt without tree resolution.

    ``config.*`` and ``app.*`` keys carry their own root segment; every other key
    is a child of ``app``. Used as the fallback path when a key does not resolve
    to a live command (a stale registry key).
    """
    override = CLI_PATH_BY_SCHEMA_KEY.get(command_key)
    if override is not None:
        return override
    return _symbolic_cli_path(command_key)


def _resolve_command(
    root: ClickCommand,
    command_key: str,
) -> tuple[ClickCommand | None, tuple[str, ...], VerbLeafResolutionFailure | None]:
    """Walk the CLI tree to the leaf command for ``command_key``.

    Threads a fresh child :class:`~click.Context` at each level so lazily-loaded
    subcommand modules materialise exactly as they do under real dispatch. A key
    segment is matched against the underscored token first, then the hyphenated
    form, so ``iva_wallet`` resolves to the ``iva-wallet`` command.

    Returns the resolved command (or ``None``), the command names as click knows
    them, and a failure reason. The reason is ``None`` only for a clean
    resolution. A missing segment and an exception while materialising a lazy
    subtree are both coverage failures; neither may silently ship an
    argument-free schema.
    """
    command: ClickCommand | None = root
    context = ClickContext(root, info_name=str(root.name))
    resolved: list[str] = []
    attempted_path = _naive_cli_path(command_key)
    for token in attempted_path:
        getter = getattr(command, "get_command", None)
        if getter is None:
            return (
                None,
                tuple(resolved),
                VerbLeafResolutionFailure(
                    subject_leaf_key=command_key,
                    attempted_cli_path=attempted_path,
                    resolved_cli_path=tuple(resolved),
                    reason=f"resolving {token!r}: command has no subcommands",
                ),
            )
        try:
            child = getter(context, token) or getter(context, token.replace("_", "-"))
        except Exception as exc:
            # Materialising a lazily-loaded subtree can raise when a command in it
            # declares a parameter type Typer cannot convert to click. Signal the
            # failure so the coverage gate can name the verb rather than letting one
            # hostile parameter silently ship as an argument-free schema.
            return (
                None,
                tuple(resolved),
                VerbLeafResolutionFailure(
                    subject_leaf_key=command_key,
                    attempted_cli_path=attempted_path,
                    resolved_cli_path=tuple(resolved),
                    reason=f"resolving {token!r}: {type(exc).__name__}: {exc}",
                ),
            )
        if child is None:
            return (
                None,
                tuple(resolved),
                VerbLeafResolutionFailure(
                    subject_leaf_key=command_key,
                    attempted_cli_path=attempted_path,
                    resolved_cli_path=tuple(resolved),
                    reason=f"resolving {token!r}: command segment not found",
                ),
            )
        if not isinstance(child, ClickCommand):
            return (
                None,
                tuple(resolved),
                VerbLeafResolutionFailure(
                    subject_leaf_key=command_key,
                    attempted_cli_path=attempted_path,
                    resolved_cli_path=tuple(resolved),
                    reason=f"resolving {token!r}: command segment is not a click command",
                ),
            )
        resolved.append(str(child.name))
        context = ClickContext(child, parent=context, info_name=str(child.name))
        command = child
    return command, tuple(resolved), None


class SchemaResolutionError(RuntimeError):
    """A command key's CLI subtree failed to materialise during schema build.

    Raised by :func:`assert_schema_coverage` when the tree walk RAISED while
    materialising a lazily-loaded subcommand. Such a failure would otherwise
    degrade silently to an argument-free schema, shipping a
    verb whose parameters vanished because of a Typer declaration bug; this error
    turns that silent degradation into a loud, verb-named build-time failure.
    """

    __bare_base_rationale__: ClassVar[str] = (
        "MCP input-schema build-coverage error; intentionally a plain RuntimeError (a loud build-time "
        "signal that a command's CLI subtree failed to materialise, which would otherwise ship a "
        "silent argument-free schema), not an operator-facing registry-bound filing error"
    )

    def __init__(self, failures: tuple[VerbLeafResolutionFailure, ...]) -> None:
        """Initialise the typed failure with every unresolved subject leaf."""
        self.failures = failures
        detail = "; ".join(
            (
                f"{failure.subject_leaf_key} "
                f"(attempted {' '.join(failure.attempted_cli_path)!r}; "
                f"resolved {' '.join(failure.resolved_cli_path)!r}; {failure.reason})"
            )
            for failure in failures
        )
        super().__init__(
            f"MCP input-schema build could not resolve {len(failures)} command "
            f"subtree(s), which would silently ship an argument-free schema: {detail}"
        )


DECLARED_UNIMPLEMENTED_SURFACES: Final[Mapping[str, str]] = {
    "config.profile.subject_access_request": (
        "Data-protection subject-access request. The operator verb was removed as collateral "
        "of the profile-capsule cutover rather than by a decision, and no other surface "
        "answers the obligation it existed to satisfy. Its schema declaration is therefore "
        "kept where every other unresolved declaration was deleted as residue: deleting this "
        "one would retire a legal obligation by tidying, and the absence would stop being "
        "visible anywhere. Restoring the verb removes this entry."
    ),
    "config.profile.rename": (
        "Profile relabelling. The implementation survives as rename_label on the profile custody "
        "service, with a domain protocol declaring it, and no caller reaches it. Held on the same "
        "grounds as the deletion verb above: the capability outlived its door, so deleting the "
        "declaration would erase the last visible evidence of that rather than tidy a retirement."
    ),
    "config.profile.export": (
        "Profile bundle transfer. Held rather than deleted because whether this capability "
        "returns is an open question about the bundle transfer surface, not residue of a "
        "retirement already executed, and deleting the declaration would answer that "
        "question by making it invisible. Restoring the verb removes this entry."
    ),
    "config.profile.import": (
        "Profile bundle transfer, the inbound half of config.profile.export and held on the "
        "same grounds: the capability question is open, so the declaration stays until it is "
        "answered rather than being settled by deletion."
    ),
}
"""Command keys whose schema is declared while the verb is knowingly absent.

An entry is a STATED gap, never a silenced one. The build stays green for these
keys because someone declared the obligation here with its reason, not because
the failure was hidden; every other unresolvable key still raises. Adding an
entry is a decision about a capability, so it belongs to whoever owns that
capability rather than to whoever is trying to make a build pass.
"""


def is_exposable_command(command_key: str) -> bool:
    """Return True when a registry command key is operator-callable.

    A group-callback or root-landing key (:data:`ROOT_LANDING_SCHEMA_KEYS`) is a
    help emit surface, not a verb. A key declared in
    :data:`DECLARED_UNIMPLEMENTED_SURFACES` is never callable either: the
    declaration records that no verb backs it, and advertising a surface whose
    verb does not exist hands an operator an instruction it cannot recover from.
    The declaration keeps the gap visible in source; it must not put a dead
    surface on the wire.
    """
    return command_key not in ROOT_LANDING_SCHEMA_KEYS and command_key not in DECLARED_UNIMPLEMENTED_SURFACES


def assert_schema_coverage(resolution_errors: tuple[VerbLeafResolutionFailure, ...]) -> None:
    """Fail the build when any command key's subtree failed to materialise.

    ``resolution_errors`` is the typed evidence from the tree walk. An empty
    tuple is the healthy state. Any entry names a missing or unmaterialisable
    verb that would otherwise silently ship an argument-free schema and raises
    :class:`SchemaResolutionError`.

    Keys listed in :data:`DECLARED_UNIMPLEMENTED_SURFACES` are the one exception,
    and they are excluded here rather than upstream so the walk still produces
    its typed evidence for them: the gap stays measurable, it simply does not
    fail the build. The gate keeps its teeth for everything else.
    """
    undeclared = tuple(
        failure for failure in resolution_errors if failure.subject_leaf_key not in DECLARED_UNIMPLEMENTED_SURFACES
    )
    if not undeclared:
        return
    raise SchemaResolutionError(undeclared)


def _schema_from_resolution(
    command_key: str,
    command: ClickCommand,
    resolved: tuple[str, ...],
) -> VerbInputSchema:
    """Project a resolved command into its strict :class:`VerbInputSchema`."""
    parameters = tuple(
        projected for parameter in command.params if (projected := _parameter_from_click(parameter)) is not None
    )
    cli_path = resolved or _naive_cli_path(command_key)
    return VerbInputSchema(
        command_key=command_key,
        cli_path=cli_path,
        parameters=parameters,
        help=_command_help(command),
    )


def _command_help(command: ClickCommand) -> str:
    """Return the command's one-line help (its ``short_help`` or first help line)."""
    short = str(getattr(command, "short_help", "") or "").strip()
    if short:
        return short
    full = str(getattr(command, "help", "") or "").strip()
    return full.splitlines()[0].strip() if full else ""


def build_verb_input_schemas(command_keys: tuple[str, ...]) -> dict[str, VerbInputSchema]:
    """Build the per-verb input schemas for every command key.

    Materialises the ``aeat`` click command once and walks it per key. The walk
    imports each lazily-loaded command subtree exactly as real dispatch does, so
    the schemas reflect the live CLI surface. Any subtree whose materialisation
    RAISES fails the coverage gate (:func:`assert_schema_coverage`) with the
    offending verb named, rather than silently degrading to an argument-free
    schema.

    Returns:
        A mapping of command key to its :class:`VerbInputSchema`.
    """
    from . import app as cli_app

    root = _typer_get_command(cli_app)
    schemas: dict[str, VerbInputSchema] = {}
    resolution_errors: list[VerbLeafResolutionFailure] = []
    for key in command_keys:
        command, resolved, error = _resolve_command(root, key)
        if error is not None or command is None:
            resolution_errors.append(
                error
                or VerbLeafResolutionFailure(
                    subject_leaf_key=key,
                    attempted_cli_path=_naive_cli_path(key),
                    resolved_cli_path=resolved,
                    reason="command did not resolve",
                )
            )
            continue
        schemas[key] = _schema_from_resolution(key, command, resolved)
    assert_schema_coverage(tuple(resolution_errors))
    return schemas


def resolve_mcp_action_capabilities(
    *,
    catalogue: ActionCatalogue,
    command_schemas: tuple[CommandSchemaRef, ...],
    verb_schemas: Mapping[str, VerbInputSchema],
) -> dict[str, tuple[McpActionCapability, ...]]:
    """Resolve catalogue actions through the shared live-surface resolver.

    ``command_schemas`` and ``verb_schemas`` must describe the same already
    MCP-exposed command-key set.  The function builds only the pure inventory
    rows accepted by :func:`resolve_action_catalogue`; it does not claim a
    profile-policy, mounted-family, or applicability projection.  Any stale
    result/input identity, ambiguous Click path, orphan target, or insufficient
    argument source fails in the shared resolver before an MCP capability is
    emitted.
    """
    schema_ref_by_key: dict[str, CommandSchemaRef] = {}
    for schema_ref in command_schemas:
        if schema_ref.command in schema_ref_by_key:
            raise ValueError(f"duplicate MCP result-schema identity: {schema_ref.command}")
        schema_ref_by_key[schema_ref.command] = schema_ref

    # A declared-unimplemented surface has a result schema and, by construction,
    # no input schema: there is no verb to read parameters from. Excluding it
    # here is the same declaration honoured a second time rather than a second
    # exemption -- were it demanded, the build would still fail on the very keys
    # the declaration exists to hold open, and the gap would have to be hidden
    # by deleting the result schema, which is the outcome it prevents.
    result_keys = frozenset(schema_ref_by_key) - frozenset(DECLARED_UNIMPLEMENTED_SURFACES)
    input_keys = frozenset(verb_schemas)
    if result_keys != input_keys:
        missing_input = tuple(sorted(result_keys - input_keys))
        missing_result = tuple(sorted(input_keys - result_keys))
        raise ValueError(
            "MCP action projection requires an exact result/input schema join; "
            f"missing input schemas={missing_input}, missing result schemas={missing_result}"
        )
    for command_key, verb_schema in verb_schemas.items():
        if verb_schema.command_key != command_key:
            raise ValueError(
                f"MCP input-schema identity mismatch: mapping={command_key}, schema={verb_schema.command_key}"
            )

    reconciliation = OperatorSurfaceReconciliation(
        leaves=tuple(
            ReconciledOperatorLeaf(
                live_leaf=LiveLeafInventoryRow(
                    subject_leaf_key=command_key,
                    canonical_cli_path=verb_schema.resolved_leaf.cli_path,
                    alias_cli_paths=verb_schema.resolved_leaf.alias_paths,
                    provenance="MCP production Click input-schema projection",
                ),
                result_schema=ResultSchemaInventoryRow(
                    subject_leaf_key=command_key,
                    schema_name=schema_ref_by_key[command_key].schema_name,
                    provenance="MCP production result-schema registry projection",
                ),
                input_schema=InputSchemaInventoryRow(
                    subject_leaf_key=command_key,
                    required_input_names=tuple(parameter.name for parameter in verb_schema.required_inputs),
                    provenance="MCP production Click required-input projection",
                ),
                mounted_family=None,
                profile_policy=None,
                mcp_exposure=None,
                exclusions=(),
            )
            for command_key, verb_schema in sorted(verb_schemas.items())
        )
    )
    resolved_actions = resolve_action_catalogue(
        catalogue=catalogue,
        reconciliation=reconciliation,
    )

    capabilities_by_target: dict[str, list[McpActionCapability]] = {}
    for resolved_action in resolved_actions:
        input_schema = resolved_action.target_leaf.input_schema
        if input_schema is None:
            raise ValueError(f"resolved MCP action target lacks input-schema evidence: {resolved_action.action_id}")
        capability = McpActionCapability(
            action_id=resolved_action.action_id,
            target_command_key=resolved_action.target_command_key,
            cli_path=resolved_action.target_leaf.live_leaf.canonical_cli_path,
            required_input_names=input_schema.required_input_names,
            argument_specifications=resolved_action.declaration.argument_specifications,
        )
        capabilities_by_target.setdefault(capability.target_command_key, []).append(capability)

    return {
        target_key: tuple(sorted(capabilities, key=lambda capability: capability.action_id))
        for target_key, capabilities in sorted(capabilities_by_target.items())
    }


def build_mcp_action_input_schemas(
    command_schemas: tuple[CommandSchemaRef, ...],
    *,
    catalogue: ActionCatalogue = OPERATOR_ACTION_CATALOGUE,
) -> dict[str, VerbInputSchema]:
    """Build live MCP input schemas enriched by resolver-backed capabilities."""
    verb_schemas = build_verb_input_schemas(tuple(schema_ref.command for schema_ref in command_schemas))
    capabilities_by_target = resolve_mcp_action_capabilities(
        catalogue=catalogue,
        command_schemas=command_schemas,
        verb_schemas=verb_schemas,
    )
    return {
        command_key: VerbInputSchema(
            command_key=verb_schema.command_key,
            cli_path=verb_schema.cli_path,
            parameters=verb_schema.parameters,
            help=verb_schema.help,
            action_capabilities=capabilities_by_target.get(command_key, ()),
        )
        for command_key, verb_schema in verb_schemas.items()
    }


def cli_argv_for(schema: VerbInputSchema, arguments: dict[str, object]) -> list[str]:
    """Build the ``aeat`` argv tail for a tool call from named ``arguments``.

    Positional arguments are emitted in their CLI declaration order and precede
    every option; a multiple argument or option repeats per element; a boolean
    flag emits its on-token when truthy and, for a ``--flag/--no-flag`` pair, its
    ``off_flag`` (``--no-flag``) when explicitly false — so a default-on flag can
    be turned off through the surface. A bare switch (no off-token) emits nothing
    when false. ``--format json`` leads the tail so the machine envelope is always
    requested, followed by the resolved command path.

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
                positional.extend(str(item) for item in cast(Sequence[object], value))
            else:
                positional.append(str(value))
            continue
        if parameter.is_flag:
            if value:
                options.append(parameter.cli_flag)
            elif parameter.off_flag:
                options.append(parameter.off_flag)
        elif parameter.multiple and isinstance(value, list | tuple):
            for item in cast(Sequence[object], value):
                options.extend((parameter.cli_flag, str(item)))
        else:
            options.extend((parameter.cli_flag, str(value)))
    return ["--format", "json", *schema.cli_path, *positional, *options]
