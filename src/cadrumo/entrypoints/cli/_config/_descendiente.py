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
canonical fact rows, which are published through one authenticated
revision-bound replacement command.

See Also:
    :mod:`~application.modelo._profile_binding`:
        ``inject_derived_minimo_descendientes_facts`` reads the facts this module writes.
    :func:`~domain.contribuyente.parse_descendiente_flag`:
        Parses the ``--descendiente`` flag's ``KEY=VALUE,...`` grammar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from ....domain.contribuyente import DescendantInfo, serialise_meses_trabajo
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._common import emit_envelope
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import date

    from ....adapters.inbound.tui import FormChoice, FormFieldKind, FormPage
    from ....application.workflow import ProfileBucketPointer
    from ....core.json_contract import Notice


def _active_profile_pointer() -> ProfileBucketPointer:
    from ._profile_support import resolve_active_profile_pointer

    pointer = resolve_active_profile_pointer()
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

    from ....application.user_profile import ProfileFactWriteDoor, apply_profile_fact_changes

    apply_profile_fact_changes(
        profile_id=bucket_id,
        changes=(*clears, *upserts),
        door=ProfileFactWriteDoor.CLI_DESCENDIENTE,
    )


def _tri(value: bool | None) -> str:
    """Render a tri-state answer, keeping UNSET distinct from an explicit no."""
    return "-" if value is None else str(value).lower()


def _iso_or_dash(value: date | None) -> str:
    """Render an optional entry-event date for the text row, or a dash when absent."""
    return value.isoformat() if value is not None else "-"


def _guarderia_mensual_or_dash(descendant: DescendantInfo) -> str:
    """Render a descendant's monthly guardería map in the one canonical form.

    Rendered through the same serialiser the fact index and the ``--descendiente``
    flag round-trip, so what an operator reads back is a value they could paste
    straight into ``GASTOS_GUARDERIA_MENSUAL=`` unchanged.
    """
    from ....domain.contribuyente import serialise_guarderia_mensual

    return serialise_guarderia_mensual(descendant.gastos_guarderia_mensuales) or "-"


def _ambiguous_relacion_indices(new_rows: list[DescendantInfo], *, index_offset: int) -> tuple[int, ...]:
    """Indices, in the combined set, of newly-added rows this Step's advisory targets.

    Fires only for a row BOTH declaring real working months AND left at the
    unstated default relación — the same narrow conjunction
    :func:`~application.modelo._calculate_input._ambiguous_relacion_hijo_ids`
    checks at calculate time. Checked here too, immediately at declaration,
    because an operator actively answering questions is better served by
    disclosure at the point they typed the figure than by discovering it only
    on the next calculate; the calculate-time check remains the one that
    reaches an already-stored row, including one declared before this notice
    existed at all.

    ``DESCENDIENTE`` is the only ambiguous value: the AEAT manual positively
    documents a grandchild or other descendant by consanguinidad other than a
    child, and a minor held under judicial guarda y custodia, as mínimo-
    eligible under Art. 58.1 while excluding both from the Art. 81.1 deducción
    by name — and the relación axis has no member for either today, so
    neither can be stated even by an operator who knows the distinction
    matters. Every other relación this flag accepts is unambiguous by
    construction, whether or not it is entitled.
    """
    from ....core import DescendantRelacion

    return tuple(
        index_offset + position
        for position, row in enumerate(new_rows)
        if row.meses_madre_trabajo and row.relacion is DescendantRelacion.DESCENDIENTE
    )


def _ambiguous_relacion_notice(ambiguous_indices: tuple[int, ...]) -> Notice:
    """Advisory notice for :func:`_ambiguous_relacion_indices`.

    Routed through the locale catalogues, unlike the calculate-time sibling in
    ``_calculate_input.py``: every other operator-facing string this module
    emits is a translated key (the flag help, every refusal), so this notice
    follows the surface it actually reaches rather than the diagnostic layer's
    own (deliberately untranslated) convention.
    """
    from .._modelo_rendering import advisory_notice

    ids = ", ".join(str(index) for index in ambiguous_indices)
    return advisory_notice(
        "config.profile.descendiente.ambiguous_relacion",
        tr(
            "cli.config.profile.descendiente.ambiguous_relacion_advisory",
            indices=ids,
        ),
        context={"indices": ids},
    )


def _descendiente_row_lines(descendientes: tuple[DescendantInfo, ...]) -> list[str]:
    lines: list[str] = []
    for index, descendant in enumerate(descendientes):
        lines.append(
            "\t".join(
                (
                    f"descendiente[{index}]",
                    f"nacimiento={descendant.birth_date.isoformat()}",
                    f"relacion={descendant.relacion.value}",
                    f"inscripcion={_iso_or_dash(descendant.inscripcion_registro_civil_date)}",
                    f"acogimiento={_iso_or_dash(descendant.acogimiento_resolucion_date)}",
                    f"fallecimiento={_iso_or_dash(descendant.death_date)}",
                    f"discapacidad={descendant.discapacidad_grado if descendant.discapacidad_grado is not None else 0}",
                    f"convivencia={str(descendant.convive_con_contribuyente).lower()}",
                    f"dependencia={_tri(descendant.dependencia_economica)}",
                    f"custodia={str(descendant.custodia_compartida).lower()}",
                    f"meses_madre_trabajo={serialise_meses_trabajo(descendant.meses_madre_trabajo) or '-'}",
                    f"alta_posterior_nacimiento_mes={descendant.alta_posterior_nacimiento_mes or '-'}",
                    f"gastos_guarderia_euros={descendant.gastos_guarderia_euros}",
                    f"gastos_guarderia_mensuales={_guarderia_mensual_or_dash(descendant)}",
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
    from .._config_descendiente_payloads import (
        ConfigProfileDescendienteListResult,
        GuarderiaMonthSpendPayload,
        ProfileDescendientePayload,
    )

    result = ConfigProfileDescendienteListResult(
        profile=pointer.label,
        total=len(descendientes),
        descendientes=[
            ProfileDescendientePayload(
                index=index,
                birth_date=descendant.birth_date,
                relacion=descendant.relacion,
                inscripcion_registro_civil_date=descendant.inscripcion_registro_civil_date,
                acogimiento_resolucion_date=descendant.acogimiento_resolucion_date,
                death_date=descendant.death_date,
                discapacidad_grado=descendant.discapacidad_grado,
                convive_con_contribuyente=descendant.convive_con_contribuyente,
                dependencia_economica=descendant.dependencia_economica,
                custodia_compartida=descendant.custodia_compartida,
                rentas_anuales_euros=descendant.rentas_anuales_euros,
                presenta_declaracion_propia=descendant.presenta_declaracion_propia,
                prorrata_minimo=descendant.prorrata_minimo,
                meses_madre_trabajo=descendant.meses_madre_trabajo,
                alta_posterior_nacimiento_mes=descendant.alta_posterior_nacimiento_mes,
                segundo_ciclo_infantil_inicio_mes=descendant.segundo_ciclo_infantil_inicio_mes,
                gastos_guarderia_euros=descendant.gastos_guarderia_euros,
                gastos_guarderia_mensuales=tuple(
                    GuarderiaMonthSpendPayload(month=entry.month, amount_euros=entry.amount_euros)
                    for entry in descendant.gastos_guarderia_mensuales
                ),
                nif=descendant.nif,
            )
            for index, descendant in enumerate(descendientes)
        ],
    )
    lines = [f"profile\t{pointer.label}", f"total\t{len(descendientes)}"]
    lines.extend(_descendiente_row_lines(descendientes))
    emit_envelope(ctx, command="config.profile.descendiente.list", result=result, lines=lines)


def descendiente_door(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
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
    from ....application.wizard import descendant_answers_from_record, persist_descendant_door_answers
    from ....application.workflow import workflow_state_repository
    from ....domain.user_profile import ProfileNotFoundError
    from ._manager_frontend import host_can_run_full_screen, present_form
    from ._profile_readiness import _read_profile_record

    workflow_state_repository().load()
    pointer = _active_profile_pointer()
    try:
        record = _read_profile_record(profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id)
    except ProfileNotFoundError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.no_active_profile",
        ) from exc

    if not host_can_run_full_screen():
        raise _CliRefusedBoundaryError(translated_message="flows.errors.unsupported_console")

    seed = descendant_answers_from_record(record)
    collected = present_form(_descendant_page(seed), rebuild=_descendant_page)
    if collected is None:
        _emit_descendiente_list(ctx, pointer, _load_descendientes(pointer.bucket_id))
        return

    persist_descendant_door_answers(dict(collected))
    _emit_descendiente_list(ctx, pointer, _load_descendientes(pointer.bucket_id))


def _descendant_page(values: Mapping[str, str]) -> FormPage:
    """Build the descendant page for the answers collected so far.

    The count row decides how many children the page asks about, so the
    page is rebuilt whenever an answer changes: raise the count and the new
    child's rows appear, lower it and they stop being collected. Keys are
    the canonical ``descendientes#<index>.<page-id>`` shape the application
    layer already projects to and from profile facts, so this screen adds
    no second answer vocabulary.
    """
    from ....adapters.inbound.tui import FormField, FormPage, form_choices
    from ....application.wizard import DESCENDANT_PAGE_IDS, DESCENDANTS_COUNT_PAGE_ID
    from ....core.i18n import tr as _tr

    raw_count = values.get(DESCENDANTS_COUNT_PAGE_ID, "0")
    count = int(raw_count) if raw_count.isdigit() else 0
    fields: list[FormField] = [
        FormField(
            key=DESCENDANTS_COUNT_PAGE_ID,
            label=_tr("wizard.setup.descendientes.count.prompt"),
            value=raw_count,
            validate=_check_count,
        ),
    ]
    yes_no = form_choices([("true", _tr("flows.confirm.yes")), ("false", _tr("flows.confirm.no"))])
    grades = form_choices(
        [
            ("0", _tr("wizard.setup.descendientes.discapacidad.choices.0.label")),
            ("33", _tr("wizard.setup.descendientes.discapacidad.choices.33.label")),
            ("65", _tr("wizard.setup.descendientes.discapacidad.choices.65.label")),
        ],
    )
    for index in range(count):
        for page_id in DESCENDANT_PAGE_IDS:
            key = f"descendientes#{index}.{page_id}"
            kind, choices = _descendant_field_shape(page_id, yes_no=yes_no, grades=grades)
            fields.append(
                FormField(
                    key=key,
                    label=f"{index + 1}. {_descendant_prompt(page_id)}",
                    value=values.get(key, ""),
                    kind=kind,
                    choices=choices,
                ),
            )
    return FormPage(
        title=_tr("cli.config.profile.descendiente.help"),
        section=_tr("wizard.setup.descendientes.title"),
        fields=tuple(fields),
    )


def _descendant_prompt(page_id: str) -> str:
    """Return one per-descendant question's prompt.

    Every key is a literal ``tr(...)`` argument in an exhaustive match
    rather than an f-string over the page id: the locale scaffolder finds
    keys by static scan, so a key built at runtime is invisible to it and
    would silently fall out of the catalogues once the flow module that
    declares these constants is retired.
    """
    from ....core.i18n import tr as _tr

    match page_id:
        case "birth-date":
            return _tr("wizard.setup.descendientes.birth-date.prompt")
        case "relacion":
            return _tr("wizard.setup.descendientes.relacion.prompt")
        case "inscripcion-registro-civil":
            return _tr("wizard.setup.descendientes.inscripcion-registro-civil.prompt")
        case "acogimiento-resolucion":
            return _tr("wizard.setup.descendientes.acogimiento-resolucion.prompt")
        case "discapacidad":
            return _tr("wizard.setup.descendientes.discapacidad.prompt")
        case "convivencia":
            return _tr("wizard.setup.descendientes.convivencia.prompt")
        case "dependencia-economica":
            return _tr("wizard.setup.descendientes.dependencia-economica.prompt")
        case "custodia-compartida":
            return _tr("wizard.setup.descendientes.custodia-compartida.prompt")
        case "rentas-anuales":
            return _tr("wizard.setup.descendientes.rentas-anuales.prompt")
        case "declaracion-propia":
            return _tr("wizard.setup.descendientes.declaracion-propia.prompt")
        case "prorrata-minimo":
            return _tr("wizard.setup.descendientes.prorrata-minimo.prompt")
        case "meses-madre-trabajo":
            return _tr("wizard.setup.descendientes.meses-madre-trabajo.prompt")
        case "gastos-guarderia":
            return _tr("wizard.setup.descendientes.gastos-guarderia.prompt")
        case "gastos-guarderia-mensuales":
            return _tr("wizard.setup.descendientes.gastos-guarderia-mensuales.prompt")
        # Only ``nif`` reaches here: every other member of DESCENDANT_PAGE_IDS is
        # named above. Three of them were NOT, and this arm answered for them --
        # the guided screen labelled the rentas, declaración-propia and prórrata
        # rows with the NIF question, so an operator was asked for a tax id three
        # times and the figures they typed went to fields they never saw named.
        case _:
            return _tr("wizard.setup.descendientes.nif.prompt")


def _descendant_field_shape(
    page_id: str,
    *,
    yes_no: tuple[FormChoice, ...],
    grades: tuple[FormChoice, ...],
) -> tuple[FormFieldKind, tuple[FormChoice, ...]]:
    """Return the edit kind and choices for one per-descendant question."""
    from ....adapters.inbound.tui import FormFieldKind

    if page_id in {"convivencia", "custodia-compartida"}:
        return FormFieldKind.SINGLE_CHOICE, yes_no
    if page_id == "discapacidad":
        return FormFieldKind.SINGLE_CHOICE, grades
    return FormFieldKind.TEXT, ()


def _check_count(candidate: str) -> str | None:
    """Refuse a count that is not a plain non-negative whole number."""
    from ....core.i18n import tr as _tr

    if candidate.isdigit():
        return None
    return _tr("wizard.setup.format.units-count")


def descendiente_add(
    ctx: typer.Context,
    descendiente: list[str],
    output_language: OutputLanguage | None = None,
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
    from pydantic import ValidationError

    from ....core.errors import ProfileAnswerTypeError
    from ....domain.contribuyente import parse_descendiente_flag

    pointer = _active_profile_pointer()
    existing = _load_descendientes(pointer.bucket_id)

    new_rows: list[DescendantInfo] = []
    for raw in descendiente:
        # BOTH refusal families, because this flag has two kinds of guard and
        # only one of them was reaching the operator intact. The parser's own
        # pre-validations raise the typed error; the canonical record's
        # validators raise through pydantic, and those are the coherence rules
        # this Phase itself shipped.
        #
        # The unhandled arm did not crash -- the error boundary's catch-all
        # projected it to a GENERIC translated refusal. That is the subtler
        # failure: an operator writing a tutela row with an adoption anchor was
        # told validation failed, in their own language, while the sentence
        # naming the conflicting field and both ways out was discarded. The copy
        # existed and nobody saw it. Catching here also keeps the declared record
        # out of the error log, which the projection wrote in clear.
        try:
            new_rows.append(parse_descendiente_flag(raw))
        except ProfileAnswerTypeError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.descendiente.invalid_flag",
                context={"error_type": type(exc).__name__},
            ) from exc
        except ValidationError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.descendiente.invalid_flag",
                context={"error_type": type(exc).__name__},
            ) from exc

    combined = (*existing, *new_rows)
    _write_descendientes(pointer.bucket_id, combined)

    from .._config_descendiente_payloads import ConfigProfileDescendienteAddResult

    result = ConfigProfileDescendienteAddResult(
        profile=pointer.label,
        added=len(new_rows),
        total=len(combined),
    )
    ambiguous_indices = _ambiguous_relacion_indices(new_rows, index_offset=len(existing))
    emit_envelope(
        ctx,
        command="config.profile.descendiente.add",
        result=result,
        lines=(
            f"profile\t{pointer.label}",
            f"added\t{len(new_rows)}",
            f"total\t{len(combined)}",
            *_descendiente_row_lines(combined),
        ),
        notices=[_ambiguous_relacion_notice(ambiguous_indices)] if ambiguous_indices else None,
    )


def descendiente_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """List every ``DescendantInfo`` row declared on the active profile."""
    _activate_subcommand_output_language(ctx, output_language)
    pointer = _active_profile_pointer()
    _emit_descendiente_list(ctx, pointer, _load_descendientes(pointer.bucket_id))


def descendiente_remove(
    ctx: typer.Context,
    index: int,
    output_language: OutputLanguage | None = None,
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

    from .._config_descendiente_payloads import ConfigProfileDescendienteRemoveResult

    result = ConfigProfileDescendienteRemoveResult(
        profile=pointer.label,
        removed_index=index,
        total=len(remaining),
    )
    emit_envelope(
        ctx,
        command="config.profile.descendiente.remove",
        result=result,
        lines=(
            f"profile\t{pointer.label}",
            f"removed_index\t{index}",
            f"total\t{len(remaining)}",
        ),
    )


__all__ = ["descendiente_add", "descendiente_door", "descendiente_list", "descendiente_remove"]
