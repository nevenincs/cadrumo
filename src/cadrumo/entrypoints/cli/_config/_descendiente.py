"""Operator-facing entry surface for Modelo 100 ``renta_family.descendiente.*`` facts.

The Art. 58/61 LIRPF minimo por descendientes engine
(:meth:`~domain.contribuyente.RentaFamilyProfile.minimo_descendientes_estatal`,
consumed at calculate time by
:func:`~application.modelo._profile_binding.inject_derived_minimo_descendientes_facts`) reads the
active profile's ``renta_family.descendiente.{n}.*`` facts. Before this module, no
production CLI surface wrote those facts: :func:`~domain.contribuyente.parse_descendiente_flag`
and :func:`~domain.contribuyente.descendant_facts_from_list` had zero non-test
callers, so casillas 0513/0514 computed to zero for every filer with children. This
module closes that gap with three flag verbs mounted under ``config profile descendiente``:
``add`` (append one or more descendants), ``list`` (show the declared descendants), and
``remove`` (drop one descendant by 0-based index).

Invoked with no subcommand (``aeat config profile descendiente``), the group opens the
paged descendant door: a deep link onto the setup flow's descendant repeating group
(:func:`~application.wizard.build_descendant_door`) that seeds from the profile's existing
``renta_family.descendiente.*`` facts, lets the operator add / edit / remove rows on the
best frontend the host supports, and commits the reviewed set back through one atomic
write (:func:`~application.wizard.persist_descendant_door_answers`). The three flag verbs
remain the flag-driven automation contract for non-interactive callers, unchanged.

Every verb rewrites the FULL declared descendant set on the active profile: a partial
patch of only the changed index would leave stale higher-index facts behind after a
``remove`` shrinks the set. ``descendant_list_from_facts`` reconstructs the current set,
the verb mutates the in-memory tuple, and ``descendant_facts_from_list`` re-derives the
canonical fact rows, which are then upserted (or cleared with ``value=None`` for indices
no longer present) via :func:`~application.user_profile.set_active_fields`.

See Also:
    :mod:`~application.modelo._profile_binding`:
        ``inject_derived_minimo_descendientes_facts`` reads the facts this module writes.
    :func:`~domain.contribuyente.parse_descendiente_flag`:
        Parses the ``--descendiente`` flag's ``KEY=VALUE,...`` grammar.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import typer

from ....application.workflow import ProfileBucketPointer
from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from ....domain.contribuyente import DescendantInfo
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError

if TYPE_CHECKING:
    from ....application.flows import FlowDefinition, FlowState

descendiente_app = typer.Typer(
    name="descendiente",
    help=tr(
        "cli.config.profile.descendiente.help",
        default="Declare descendants for the Art. 58/61 LIRPF minimo por descendientes.",
    ),
    no_args_is_help=False,
    invoke_without_command=True,
)

_resolve_active_profile_pointer: Callable[[], ProfileBucketPointer | None] | None = None
_mounted_profile_app_ids: set[int] = set()


def register_descendiente_commands(
    profile_app: typer.Typer,
    *,
    resolve_active_profile_pointer: Callable[[], ProfileBucketPointer | None],
) -> None:
    """Mount the ``descendiente`` sub-app on ``config profile``."""
    global _resolve_active_profile_pointer

    _resolve_active_profile_pointer = resolve_active_profile_pointer
    profile_app_id = id(profile_app)
    if profile_app_id in _mounted_profile_app_ids:
        return
    profile_app.add_typer(descendiente_app, name="descendiente")
    _mounted_profile_app_ids.add(profile_app_id)


def _active_profile_pointer() -> ProfileBucketPointer:
    if _resolve_active_profile_pointer is None:
        raise RuntimeError("descendiente commands were not registered")
    pointer = _resolve_active_profile_pointer()
    if pointer is None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.no_active_profile",
        )
    return pointer


def _load_descendientes(bucket_id: str) -> tuple[DescendantInfo, ...]:
    """Return the active profile's declared descendants, oldest fact-order preserved."""
    from ....domain.contribuyente import descendant_list_from_facts
    from ....domain.user_profile import ProfileNotFoundError
    from ._profile_readiness import _read_profile_record

    try:
        record = _read_profile_record(profile_id=bucket_id, bucket_id=bucket_id)
    except ProfileNotFoundError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.no_active_profile",
        ) from exc
    facts = {fact.path: str(fact.value) for fact in record.facts if fact.value is not None}
    return descendant_list_from_facts(facts)


def _write_descendientes(bucket_id: str, descendientes: tuple[DescendantInfo, ...]) -> None:
    """Rewrite the active profile's full descendiente fact set, clearing stale rows.

    Clears every ``renta_family.descendiente.{n}.*`` and the count/aggregate facts
    before rewriting, so a ``remove`` that shrinks the set never leaves a stale
    higher-index fact behind for :func:`descendant_list_from_facts` to re-discover.
    """
    from ....domain.contribuyente import descendant_facts_from_list
    from ....domain.user_profile import ProfileNotFoundError, UserProfileFact
    from ._profile_readiness import _read_profile_record

    try:
        record = _read_profile_record(profile_id=bucket_id, bucket_id=bucket_id)
    except ProfileNotFoundError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.no_active_profile",
        ) from exc
    stale_paths = {
        fact.path
        for fact in record.facts
        if fact.path.startswith("renta_family.descendiente.") or fact.path == "renta_family.descendientes_count"
    }
    new_pairs = dict(descendant_facts_from_list(descendientes))
    clears = tuple(UserProfileFact(path=path, value=None) for path in stale_paths if path not in new_pairs)
    upserts = tuple(UserProfileFact(path=path, value=value) for path, value in new_pairs.items())

    from ....application.user_profile import set_active_fields
    from ....application.workflow import workflow_state_repository

    workflow_state_repository().update(lambda current: set_active_fields(current, (*clears, *upserts)))


def _descendiente_row_lines(descendientes: tuple[DescendantInfo, ...]) -> list[str]:
    lines: list[str] = []
    for index, descendant in enumerate(descendientes):
        lines.append(
            "\t".join(
                (
                    f"descendiente[{index}]",
                    f"nacimiento={descendant.birth_date.isoformat()}",
                    f"adopcion={descendant.adoption_date.isoformat() if descendant.adoption_date else '-'}",
                    f"discapacidad={descendant.discapacidad_grado if descendant.discapacidad_grado is not None else 0}",
                    f"convivencia={str(descendant.convive_con_contribuyente).lower()}",
                    f"custodia={str(descendant.custodia_compartida).lower()}",
                    f"nif={descendant.nif or '-'}",
                ),
            ),
        )
    return lines


def _emit_descendiente_list(
    ctx: typer.Context,
    pointer: ProfileBucketPointer,
    descendientes: tuple[DescendantInfo, ...],
) -> None:
    """Emit the active profile's declared descendant set as the list envelope."""
    from .._config_payloads import ConfigProfileDescendienteListResult, ProfileDescendientePayload

    result = ConfigProfileDescendienteListResult(
        profile=pointer.label,
        total=len(descendientes),
        descendientes=[
            ProfileDescendientePayload(
                index=index,
                birth_date=descendant.birth_date.isoformat(),
                adoption_date=descendant.adoption_date.isoformat() if descendant.adoption_date else None,
                discapacidad_grado=descendant.discapacidad_grado,
                convive_con_contribuyente=descendant.convive_con_contribuyente,
                custodia_compartida=descendant.custodia_compartida,
                nif=descendant.nif,
            )
            for index, descendant in enumerate(descendientes)
        ],
    )
    lines = [f"profile\t{pointer.label}", f"total\t{len(descendientes)}"]
    lines.extend(_descendiente_row_lines(descendientes))
    _emit_envelope(ctx, command="config.profile.descendiente.list", result=result, lines=lines)


@descendiente_app.callback()
def descendiente_door(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Open the paged descendant door, or dispatch to a flag subcommand.

    Invoked with no subcommand (``aeat config profile descendiente``) this opens
    the interactive paged descendant editor: the operator's existing descendants
    seed the setup flow's repeating group, they add / edit / remove rows on the
    best frontend the host supports, and the reviewed set commits back to the
    ``renta_family.descendiente.*`` facts in one atomic write. The
    ``add`` / ``list`` / ``remove`` subcommands remain the flag-driven automation
    contract and are dispatched unchanged when named.
    """
    if ctx.invoked_subcommand is not None:
        return
    _activate_subcommand_output_language(ctx, output_language)
    _run_descendant_door(ctx)


def _run_descendant_door(ctx: typer.Context) -> None:
    """Seed, host, and commit the paged descendant door for the active profile.

    Reads the active profile record, seeds a MODIFY-mode door state from its
    existing descendant facts, drives the interactive editor, then commits the
    reviewed answers as the full descendant fact set through the single
    application-layer seam. A piped / no-console host refuses with the substrate's
    translated no-console error mapped to the CLI refusal boundary.
    """
    from ....application.flows import FlowUnsupportedConsoleError
    from ....application.wizard import build_descendant_door, persist_descendant_door_answers
    from ....application.workflow import workflow_state_repository
    from ....core.errors import resolve_error_message
    from ....domain.user_profile import ProfileNotFoundError
    from ._profile_readiness import _read_profile_record

    workflow_state_repository().load()
    pointer = _active_profile_pointer()
    try:
        record = _read_profile_record(profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id)
    except ProfileNotFoundError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.no_active_profile",
        ) from exc

    definition, resume_state = build_descendant_door(record)
    try:
        final_state = _host_descendant_door(definition, resume_state)
    except FlowUnsupportedConsoleError as exc:
        raise _CliRefusedBoundaryError(resolve_error_message(exc)) from exc

    persist_descendant_door_answers(dict(final_state.answers))
    _emit_descendiente_list(ctx, pointer, _load_descendientes(pointer.bucket_id))


def _host_descendant_door(definition: FlowDefinition, resume_state: FlowState) -> FlowState:
    """Drive the door on the best frontend, seeding it with ``resume_state``.

    Mirrors the capability selection the shared setup-flow runner performs, but
    threads ``resume_state`` — the seeded MODIFY-mode state — into the substrate's
    own run helpers (:func:`~adapters.inbound.tui.run_flow_tui` full-screen,
    :meth:`~application.flows.LineFlowFrontend.run` line), both of which accept it.
    The shared ``run_setup_flow_frontend`` wrapper exposes no ``resume_state``
    channel, so the door hosts through the two substrate run entrypoints directly
    rather than forking the substrate. A piped / no-console host refuses with the
    substrate's translated no-console error.
    """
    from ....application.flows import FlowUnsupportedConsoleError, LineFlowFrontend, detect_frontend_capability
    from ....core.flows import FlowMode, FrontendCapability

    capability = detect_frontend_capability()
    if capability is FrontendCapability.NON_INTERACTIVE:
        raise FlowUnsupportedConsoleError(translated_message="flows.errors.unsupported_console")
    if capability is FrontendCapability.LINE:
        state, _projection = LineFlowFrontend(definition, checkpoint_store=None).run(
            mode=FlowMode.MODIFY,
            resume_state=resume_state,
        )
        return state

    from ....adapters.inbound.tui import run_flow_tui

    state, _projection = run_flow_tui(
        definition,
        mode=FlowMode.MODIFY,
        resume_state=resume_state,
        registered_values=None,
    )
    return state


@descendiente_app.command(
    "add",
    help=tr(
        "cli.config.profile.descendiente.add_help",
        default="Add one or more descendants to the active profile.",
    ),
)
def descendiente_add(
    ctx: typer.Context,
    descendiente: list[str] = typer.Option(
        ...,
        "--descendiente",
        help=tr(
            "cli.config.profile.descendiente.add_flag_help",
            default=(
                "NACIMIENTO=YYYY-MM-DD[,ADOPCION=YYYY-MM-DD][,DISCAPACIDAD=0|33|65]"
                "[,CONVIVENCIA=true|false][,CUSTODIA=true|false][,MESES_TRABAJO=0..12]"
                "[,GASTOS_GUARDERIA=N][,NIF=XXXXXXXXX]. Repeatable."
            ),
        ),
    ),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Append one or more ``--descendiente`` rows to the active profile.

    Each ``--descendiente`` flag is parsed by
    :func:`~domain.contribuyente.parse_descendiente_flag`; a malformed flag
    refuses instructively before any profile write. The new rows are appended after
    the existing declared descendants and the full set is rewritten so the
    Art. 58/61 LIRPF minimo por descendientes engine
    (:func:`~application.modelo._profile_binding.inject_derived_minimo_descendientes_facts`) has
    real facts to compute from on the next M100 calculate.
    """
    _activate_subcommand_output_language(ctx, output_language)
    from ....core.errors import ProfileAnswerTypeError
    from ....domain.contribuyente import parse_descendiente_flag

    pointer = _active_profile_pointer()
    existing = _load_descendientes(pointer.bucket_id)

    new_rows: list[DescendantInfo] = []
    for raw in descendiente:
        try:
            new_rows.append(parse_descendiente_flag(raw))
        except ProfileAnswerTypeError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.descendiente.invalid_flag",
                context={"flag": raw, "detail": str(exc)},
            ) from exc

    combined = (*existing, *new_rows)
    _write_descendientes(pointer.bucket_id, combined)

    from .._config_payloads import ConfigProfileDescendienteAddResult

    result = ConfigProfileDescendienteAddResult(
        profile=pointer.label,
        added=len(new_rows),
        total=len(combined),
    )
    _emit_envelope(
        ctx,
        command="config.profile.descendiente.add",
        result=result,
        lines=(
            f"profile\t{pointer.label}",
            f"added\t{len(new_rows)}",
            f"total\t{len(combined)}",
            *_descendiente_row_lines(combined),
        ),
    )


@descendiente_app.command(
    "list",
    help=tr(
        "cli.config.profile.descendiente.list_help",
        default="List descendants declared on the active profile.",
    ),
)
def descendiente_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """List every ``DescendantInfo`` row declared on the active profile."""
    _activate_subcommand_output_language(ctx, output_language)
    pointer = _active_profile_pointer()
    _emit_descendiente_list(ctx, pointer, _load_descendientes(pointer.bucket_id))


@descendiente_app.command(
    "remove",
    help=tr(
        "cli.config.profile.descendiente.remove_help",
        default="Remove one descendant by 0-based index from the active profile.",
    ),
)
def descendiente_remove(
    ctx: typer.Context,
    index: int = typer.Argument(..., help=tr("cli.config.profile.descendiente.remove_index_help")),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Remove the descendant at ``index`` and re-index the remaining rows."""
    _activate_subcommand_output_language(ctx, output_language)
    pointer = _active_profile_pointer()
    existing = _load_descendientes(pointer.bucket_id)
    if index < 0 or index >= len(existing):
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.descendiente.index_out_of_range",
            context={"index": str(index), "total": str(len(existing))},
        )
    remaining = tuple(d for i, d in enumerate(existing) if i != index)
    _write_descendientes(pointer.bucket_id, remaining)

    from .._config_payloads import ConfigProfileDescendienteRemoveResult

    result = ConfigProfileDescendienteRemoveResult(
        profile=pointer.label,
        removed_index=index,
        total=len(remaining),
    )
    _emit_envelope(
        ctx,
        command="config.profile.descendiente.remove",
        result=result,
        lines=(
            f"profile\t{pointer.label}",
            f"removed_index\t{index}",
            f"total\t{len(remaining)}",
        ),
    )


__all__ = ["descendiente_app", "register_descendiente_commands"]
