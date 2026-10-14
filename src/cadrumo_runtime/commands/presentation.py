"""Runtime command output helpers for the moved configuration surface."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import clear_output_language_cache, output_language
from cadrumo_client.commands.graph import CommandSpecGraph, resolve_command_target
from cadrumo_client.commands.shared_contracts import BindingState, DefaultKind
from cadrumo_client.commands.spec import CommandSpecNode
from cadrumo_client.contracts.command_ports import CommandNodeKind
from cadrumo_client.contracts.command_program import CommandProgram

if TYPE_CHECKING:
    from cadrumo.application.operator_actions.models import PreconditionVerdict
    from cadrumo.application.operator_surface.manifest import OperatorSurfaceReconciliation
    from cadrumo.core.json_contract import Notice, ResolvedPreconditionAction


def activate_subcommand_output_language(ctx: typer.Context, language: OutputLanguage | None) -> None:
    """Apply a leaf-level language choice to this runtime invocation."""
    if language is None:
        return
    from cadrumo.core.config import override_settings

    ctx.with_resource(override_settings(cadrumo_output_language=language))
    clear_output_language_cache()


def precondition_action_lines(action: ResolvedPreconditionAction | None) -> tuple[str, ...]:
    """Render the typed precondition action as stable machine-readable rows."""
    if action is None:
        return ()
    document = action.model_dump(mode="json")
    fields = (
        "failed_condition_id",
        "evidence",
        "action",
        "argument_bindings",
        "missing_argument_names",
        "conditionality",
        "no_recovery_outcome",
    )
    return tuple(
        f"precondition_action.{field}\t"
        f"{json.dumps(document[field], ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"
        for field in fields
    )


def resolve_cli_precondition_action(verdict: PreconditionVerdict) -> ResolvedPreconditionAction:
    """Resolve an application verdict against the owning command graph.

    Runtime-owned targets are reconciled from the live runtime graph, including
    its executable root. Actions that intentionally target a command retained
    by the AEAT CLI use the application-owned recorded projection.
    """
    from cadrumo.application.operator_surface.action_targets import (
        ACTION_TARGETS,
        recorded_action_target_reconciliation,
    )
    from cadrumo.application.operator_surface.precondition_action import resolve_precondition_action

    from .command_specs import RUNTIME_COMMAND_GRAPH

    runtime_nodes: dict[str, CommandSpecNode] = {}

    def target_reconciliation(command_key: str) -> OperatorSurfaceReconciliation:
        try:
            node = resolve_command_target(RUNTIME_COMMAND_GRAPH, command_key)
        except LookupError:
            return recorded_action_target_reconciliation(command_key)
        runtime_nodes[command_key] = node
        return _runtime_action_target_reconciliation(RUNTIME_COMMAND_GRAPH, command_key)

    resolved = resolve_precondition_action(verdict, target_reconciliation=target_reconciliation)
    if resolved.action is None:
        return resolved
    node = runtime_nodes.get(resolved.action.target_command_key)
    if node is not None:
        cli_path = node.path
        action = resolved.action.model_copy(update={"cli_path": cli_path})
        return resolved.model_copy(update={"action": action})
    target = next(item for item in ACTION_TARGETS if item.command_key == resolved.action.target_command_key)
    cli_path = resolved.action.cli_path
    if cli_path is None:
        cli_path = (target.program.executable_name,)
    elif not cli_path or cli_path[0] != target.program.executable_name:
        cli_path = (target.program.executable_name, *cli_path)
    action = resolved.action.model_copy(update={"cli_path": cli_path})
    return resolved.model_copy(update={"action": action})


def _runtime_action_target_reconciliation(graph: CommandSpecGraph, command_key: str) -> OperatorSurfaceReconciliation:
    """Reconcile one recovery target from the runtime's actual command graph."""
    from cadrumo.application.operator_surface.contract import get_operator_surface_contract
    from cadrumo.application.operator_surface.manifest import (
        InputSchemaInventoryRow,
        LiveLeafInventoryRow,
        MountedFamilyInventoryRow,
        ProfilePolicyInventoryRow,
        ResultSchemaInventoryRow,
        SurfaceExposureInventoryRow,
        reconcile_operator_surface_inventory,
    )

    node = resolve_command_target(graph, command_key)
    spec = node.spec
    target = spec.result_schema.target
    if target is None:
        raise LookupError(f"command schema identity has no result-schema target: {command_key}")
    if spec.kind is not CommandNodeKind.LEAF:
        raise LookupError(f"command schema identity is not an executable leaf: {command_key}")
    if spec.handler is None or spec.handler.state is not BindingState.TARGET:
        raise LookupError(f"command schema identity has no executable handler: {command_key}")

    # The reconciliation manifest describes command-family suffixes. The
    # executable root is added to the resolved action below from ``node.path``.
    command_path = node.path[1:]
    required_inputs = tuple(
        parameter.name
        for parameter in spec.parameters
        if not parameter.hidden and parameter.default.kind is DefaultKind.REQUIRED
    )
    family_identity = command_path[:2]
    mounted_families = tuple(
        MountedFamilyInventoryRow(
            root=family.root.value,
            child=family.child,
            provenance="OperatorSurfaceContract.command_families",
        )
        for family in get_operator_surface_contract().command_families
        if (family.root.value, family.child) == family_identity
    )
    profile_bound_write = getattr(spec.policy.write_route, "value", spec.policy.write_route) == "profile-bound"
    return reconcile_operator_surface_inventory(
        live_leaves=(
            LiveLeafInventoryRow(
                subject_leaf_key=command_key,
                canonical_cli_path=command_path,
                program=CommandProgram.AUTHENTICATION,
                alias_cli_paths=(),
                provenance="RUNTIME_COMMAND_GRAPH",
            ),
        ),
        result_schemas=(
            ResultSchemaInventoryRow(
                subject_leaf_key=command_key,
                schema_name=target.qualname,
                provenance="RUNTIME_COMMAND_GRAPH.result_schema",
            ),
        ),
        input_schemas=(
            InputSchemaInventoryRow(
                subject_leaf_key=command_key,
                required_input_names=required_inputs,
                provenance="RUNTIME_COMMAND_GRAPH.parameters",
            ),
        ),
        mounted_families=mounted_families,
        profile_policies=(
            ProfilePolicyInventoryRow(
                subject_leaf_key=command_key,
                classification="profile_bound_write" if profile_bound_write else "non_profile_bound",
                should_expose_externally=True,
                provenance="RUNTIME_COMMAND_GRAPH.policy",
            ),
        ),
        surface_exposures=(
            SurfaceExposureInventoryRow(
                subject_leaf_key=command_key,
                exposed=True,
                provenance="RUNTIME_COMMAND_GRAPH.exposure",
            ),
        ),
    )


def notice_lines(notices: Sequence[Notice]) -> tuple[str, ...]:
    """Render the notice channel into the text transport's corresponding rows."""
    return tuple(f"notice\t{notice.code}\t{notice.message}" for notice in notices)


def _format_name(ctx: typer.Context) -> str:
    root = ctx.find_root()
    state = root.obj if isinstance(root.obj, dict) else {}
    command_context = state.get("cadrumo.runtime.command_context")
    value = getattr(command_context, "output_format", None)
    if value is None:
        params = root.params
        value = params.get("format_", params.get("format", "text"))
    return str(getattr(value, "value", value))


@dataclass(frozen=True, slots=True)
class RuntimeErrorContext:
    """Invocation-owned envelope fields captured before profile resources close."""

    command: str | None
    active_profile: str | None
    output_format: str
    output_language: str
    notices: tuple[Notice, ...]


_RUNTIME_ERROR_CONTEXT_ATTRIBUTE = "_cadrumo_runtime_error_context"


def capture_runtime_error_context(ctx: typer.Context, error: BaseException) -> None:
    """Capture the live command identity, profile label and pending notices on refusal."""
    root = ctx.find_root()
    state = root.ensure_object(dict)
    raw_notices = state.pop("cadrumo.runtime.notices", ())
    notices: tuple[Notice, ...] = ()
    if isinstance(raw_notices, (list, tuple)):
        from cadrumo.core.json_contract import Notice

        try:
            notices = tuple(Notice.model_validate(item) for item in raw_notices)
        except Exception:
            notices = ()
    spec = state.get("cadrumo.runtime.command_spec")
    identity = getattr(getattr(spec, "result_schema", None), "identity", None)
    label = state.get("cadrumo.runtime.profile_label")
    if not isinstance(label, str):
        try:
            label = _active_profile_label()
        except Exception:
            label = None
    command_context = state.get("cadrumo.runtime.command_context")
    output_format = getattr(command_context, "output_format", None)
    output_format_value = str(getattr(output_format, "value", output_format or "text"))
    captured = RuntimeErrorContext(
        command=identity if isinstance(identity, str) else None,
        active_profile=label,
        output_format=output_format_value,
        output_language=output_language(),
        notices=notices,
    )
    try:
        setattr(error, _RUNTIME_ERROR_CONTEXT_ATTRIBUTE, captured)
    except (AttributeError, TypeError):
        return


def runtime_error_context(error: BaseException) -> RuntimeErrorContext | None:
    """Find invocation context captured on an error or one of its causes."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        value = getattr(current, _RUNTIME_ERROR_CONTEXT_ATTRIBUTE, None)
        if isinstance(value, RuntimeErrorContext):
            return value
        current = current.__cause__ or current.__context__
    return None


def _take_pending_notices(ctx: typer.Context) -> tuple[Notice, ...]:
    root = ctx.find_root()
    state = root.ensure_object(dict)
    raw = state.pop("cadrumo.runtime.notices", ())
    if not isinstance(raw, (list, tuple)):
        return ()
    from cadrumo.core.json_contract import Notice

    return tuple(Notice.model_validate(item) for item in raw)


def _active_profile_label() -> str | None:
    """Resolve the active profile's public manifest label without opening facts."""
    from cadrumo.adapters.persistence.storage.errors import StorageValidationError
    from cadrumo.application.workflow.profile_bucket_scan import resolve_profile_bucket
    from cadrumo.core.bucket_pointer import resolve_active_bucket_id
    from cadrumo.core.config_state_root import FormerProductStateError

    try:
        bucket_id = resolve_active_bucket_id()
        if bucket_id is None:
            return None
        pointer = resolve_profile_bucket(bucket_id)
        return pointer.label if pointer is not None else None
    except (FormerProductStateError, StorageValidationError):
        return None


def emit_envelope(
    ctx: typer.Context,
    *,
    command: str,
    result: object,
    lines: Iterable[str],
    notices: Sequence[Notice] | None = None,
    metadata_only: bool = False,
) -> None:
    """Emit the standard typed command envelope or its text projection."""
    from cadrumo.core.output_rendering import OutputFormat, render_command_output

    supplied = (*_take_pending_notices(ctx), *(notices or ()))
    output_format = _format_name(ctx)
    root_state = ctx.find_root().obj if isinstance(ctx.find_root().obj, dict) else {}
    profile_label = root_state.get("cadrumo.runtime.profile_label")
    if not isinstance(profile_label, str):
        profile_label = _active_profile_label()
    if output_format == OutputFormat.JSON.value:
        from cadrumo.application.operator_output.emit import emit_operator_json_success

        emit_operator_json_success(
            command,
            result,
            notices=supplied,
            active_profile=None if metadata_only else profile_label,
        )
        return
    rendered_lines = tuple(lines)
    if not metadata_only:
        rendered_lines = (*rendered_lines, *notice_lines(supplied))
    rendered = render_command_output(format_name=output_format, payload=result, lines=rendered_lines)
    if rendered.text:
        typer.echo(rendered.text)


__all__ = [
    "activate_subcommand_output_language",
    "capture_runtime_error_context",
    "emit_envelope",
    "notice_lines",
    "precondition_action_lines",
    "resolve_cli_precondition_action",
    "runtime_error_context",
]
