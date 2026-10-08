"""Operator-facing entry surface for Modelo 100 ``renta_family.descendiente.*`` facts.

The Art. 58/61 LIRPF minimo por descendientes engine
(:meth:`~domain.contribuyente.family_profile.RentaFamilyProfile.minimo_descendientes_estatal`,
consumed at calculate time by
:func:`~application.modelo.profile_binding.inject_derived_minimo_descendientes_facts`) reads the
active profile's ``renta_family.descendiente.{n}.*`` facts. Before this module, no
production CLI surface wrote those facts: :func:`~domain.contribuyente.descendant_facts.parse_descendiente_flag`
and :func:`~domain.contribuyente.descendant_facts.descendant_facts_from_list` had zero non-test
callers, so casillas 0513/0514 computed to zero for every filer with children. This
module closes that gap with three flag verbs mounted under ``config profile descendiente``:
``add`` (append one or more descendants), ``list`` (show the declared descendants), and
``remove`` (drop one descendant by 0-based index).

Invoked with no subcommand (``aeat config profile descendiente``), the group opens the
paged descendant door on the same verified runtime profile view and registered
family-replacement operation as the flag verbs.

Every verb rewrites the FULL declared descendant set on the active profile: a partial
patch of only the changed index would leave stale higher-index facts behind after a
``remove`` shrinks the set. The verified FACTS view reconstructs the current set,
the verb mutates that tuple, and the registered operation publishes one
revision-bound replacement.

See Also:
    :mod:`~application.modelo.profile_binding`:
        ``inject_derived_minimo_descendientes_facts`` reads the facts this module writes.
    :func:`~domain.contribuyente.descendant_facts.parse_descendiente_flag`:
        Parses the ``--descendiente`` flag's ``KEY=VALUE,...`` grammar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from ....core.errors.hierarchy import CadrumoError
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.meses_trabajo import serialise_meses_trabajo
from ..common import activate_subcommand_output_language as _activate_subcommand_output_language
from ..common import emit_envelope
from ..errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._profile_support import require_active_profile_pointer as _active_profile_pointer

if TYPE_CHECKING:
    from datetime import date

    from ....application.workflow.profile_bucket_models import ProfileBucketPointer
    from ....core.json_contract import Notice


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
    from ....domain.contribuyente.guarderia_mensual import serialise_guarderia_mensual

    return serialise_guarderia_mensual(descendant.gastos_guarderia_mensuales) or "-"


_GUARDERIA_CONFLICT_LOCALE_KEY = "cli.config.profile.descendiente.guarderia_spend_shapes_conflict"
_MISSING_BIRTH_DATE_LOCALE_KEY = "cli.config.profile.descendiente.invalid_flag"
_INVALID_ROW_LOCALE_KEY = "cli.config.profile.descendiente.invalid_row"


def _offending_flag_key(error: CadrumoError) -> dict[str, str]:
    """Return the ``--descendiente`` key a parse refusal names, when it names one.

    The flag carries about twenty keys and the refusal lists them all, so an
    operator reading only the typed envelope could not tell which of their own
    values was unreadable. The parser records it; an older refusal that records
    none yields no context rather than a guess.
    """
    key = (error.context or {}).get("key")
    return {"key": key} if isinstance(key, str) and key else {}


def _descendiente_refusal_key(error: CadrumoError) -> tuple[str, dict[str, str]]:
    """Map a ``--descendiente`` parse refusal to the translated key that states its cause.

    Only a refusal the parser attributes to ``NACIMIENTO`` may use the copy that
    tells the operator every row must declare a birth date; any other refusal
    rendered through it names a cause that is not the one that happened.
    """
    context = _offending_flag_key(error)
    if (error.context or {}).get("refusal") == "guarderia_spend_shapes":
        return _GUARDERIA_CONFLICT_LOCALE_KEY, context
    if context.get("key") == "NACIMIENTO":
        return _MISSING_BIRTH_DATE_LOCALE_KEY, context
    return _INVALID_ROW_LOCALE_KEY, context


def _ambiguous_relacion_indices(new_rows: list[DescendantInfo], *, index_offset: int) -> tuple[int, ...]:
    """Indices, in the combined set, of newly-added rows this Step's advisory targets.

    Fires only for a row BOTH declaring real working months AND left at the
    unstated default relación — the same narrow conjunction
    :func:`~application.modelo.calculate_input._ambiguous_relacion_hijo_ids`
    checks at calculate time. Checked here too, immediately at declaration,
    because an operator actively answering questions is better served by
    disclosure at the point they typed the figure than by discovering it only
    on the next calculate; the calculate-time check remains the one that
    reaches an already-stored row, including one declared before this notice
    existed at all.

    Which relación is ambiguous is the domain's answer, not this surface's:
    :func:`~domain.contribuyente.descendant_maternity.relacion_is_ambiguous_for_maternidad` states it
    once, with the manual's reasoning. The months gate stays here because it
    genuinely differs between the two callers -- this one asks whether the
    operator declared months, the calculate-time one whether those months
    actually contribute to the filing.
    """
    from ....domain.contribuyente.descendant_maternity import relacion_is_ambiguous_for_maternidad

    return tuple(
        index_offset + position
        for position, row in enumerate(new_rows)
        if row.meses_madre_trabajo and relacion_is_ambiguous_for_maternidad(row.relacion)
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
                    f"segundo_ciclo_infantil_inicio_mes={descendant.segundo_ciclo_infantil_inicio_mes or '-'}",
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
                gastos_guarderia_mensuales=descendant.gastos_guarderia_mensuales,
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
    """Drive the descendant application flow through its line-mode frontend."""
    from .runtime_descendant_door import run_runtime_descendant_door

    pointer = _active_profile_pointer()
    rows = run_runtime_descendant_door(ctx)
    _emit_descendiente_list(ctx, pointer, rows)


def descendiente_add(
    ctx: typer.Context,
    descendiente: list[str],
    output_language: OutputLanguage | None = None,
) -> None:
    """Append one or more ``--descendiente`` rows to the active profile.

    Each ``--descendiente`` flag is parsed by
    :func:`~domain.contribuyente.descendant_facts.parse_descendiente_flag`; a malformed flag
    refuses instructively before any profile write. The new rows are appended after
    the existing declared descendants and the full set is rewritten so the
    Art. 58/61 LIRPF minimo por descendientes engine
    (:func:`~application.modelo.profile_binding.inject_derived_minimo_descendientes_facts`) has
    real facts to compute from on the next M100 calculate.

    Parsing reads the registry's disability grades and relación default, and
    the stored rows are validated against the same authority: the governed-fact
    scope dispatch opens for this command.
    """
    from uuid import UUID

    from pydantic import ValidationError

    from ....core.errors.hierarchy import ProfileAnswerTypeError
    from ....domain.contribuyente.descendant_facts import parse_descendiente_flag
    from ..runtime_profile_binding import require_profile_client
    from ..state_projection_support import authority_operation
    from ._runtime_profile_mutation import mutation_deadline
    from .runtime_descendants import read_runtime_descendants, replace_runtime_descendants

    _activate_subcommand_output_language(ctx, output_language)
    pointer = _active_profile_pointer()
    # Stored rows and the flag's relationship and disability vocabularies are
    # governed facts, so reading and parsing need the command's pinned
    # authority, not only the write.
    authority = authority_operation(ctx)
    client = require_profile_client(ctx, expected_profile_id=UUID(str(pointer.bucket_id)))
    deadline = mutation_deadline()
    baseline, existing = read_runtime_descendants(client, operation=authority, deadline=deadline)

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
            new_rows.append(parse_descendiente_flag(raw, authority=authority))
        except ProfileAnswerTypeError as exc:
            # The exception CLASS NAME is not operator-facing vocabulary: putting it
            # in context leaks "ValidationError" into the envelope the operator
            # reads. The translated message carries what they can act on. The KEY
            # does belong there: the message lists every accepted key, which does
            # not tell an automated operator which one of theirs was unreadable.
            # The mutually-exclusive guarderia spend forms are a known, safe
            # condition with a dedicated localised refusal. Other parser prose can
            # include the supplied value, so it stays behind the generic boundary.
            translated_message, context = _descendiente_refusal_key(exc)
            raise _CliRefusedBoundaryError(translated_message=translated_message, context=context) from exc
        except ValidationError as exc:
            # Name the FIELDS that conflict, never the exception class. The class
            # name leaks "ValidationError" into the envelope the operator reads and
            # tells them nothing; the field paths are exactly what they can act on.
            raise _CliRefusedBoundaryError(
                translated_message=_INVALID_ROW_LOCALE_KEY,
                context={
                    # The coherence rules are MODEL-level validators, so `loc` is
                    # empty and the conflicting field is named in the message. Take
                    # the messages, never str(exc): that appends the pydantic help
                    # URL and the exception class the operator must never see.
                    "detail": "; ".join(str(error["msg"]) for error in exc.errors()),
                },
            ) from exc

    combined = (*existing, *new_rows)
    committed = replace_runtime_descendants(
        client,
        baseline=baseline,
        descendants=combined,
        operation=authority,
        deadline=deadline,
    )

    from .._config_descendiente_payloads import ConfigProfileDescendienteAddResult

    result = ConfigProfileDescendienteAddResult(
        profile=pointer.label,
        added=len(new_rows),
        total=len(committed),
    )
    ambiguous_indices = _ambiguous_relacion_indices(new_rows, index_offset=len(existing))
    emit_envelope(
        ctx,
        command="config.profile.descendiente.add",
        result=result,
        lines=(
            f"profile\t{pointer.label}",
            f"added\t{len(new_rows)}",
            f"total\t{len(committed)}",
            *_descendiente_row_lines(committed),
        ),
        notices=[_ambiguous_relacion_notice(ambiguous_indices)] if ambiguous_indices else None,
    )


def descendiente_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """List every ``DescendantInfo`` row declared on the active profile."""
    from time import monotonic
    from uuid import UUID

    from ..runtime_profile_binding import require_profile_client
    from ..state_projection_support import authority_operation
    from .runtime_descendants import read_runtime_descendants

    _activate_subcommand_output_language(ctx, output_language)
    pointer = _active_profile_pointer()
    client = require_profile_client(ctx, expected_profile_id=UUID(str(pointer.bucket_id)))
    _baseline, rows = read_runtime_descendants(client, operation=authority_operation(ctx), deadline=monotonic() + 60)
    _emit_descendiente_list(ctx, pointer, rows)


def descendiente_remove(
    ctx: typer.Context,
    index: int,
    output_language: OutputLanguage | None = None,
) -> None:
    """Remove the descendant at ``index`` and re-index the remaining rows."""
    from uuid import UUID

    from ..runtime_profile_binding import require_profile_client
    from ._runtime_profile_mutation import mutation_deadline
    from .runtime_descendants import read_runtime_descendants, replace_runtime_descendants

    _activate_subcommand_output_language(ctx, output_language)
    from ..state_projection_support import authority_operation

    pointer = _active_profile_pointer()
    # Stored rows validate against governed vocabularies, so decoding them needs
    # the command's pinned authority, not only the write.
    authority = authority_operation(ctx)
    client = require_profile_client(ctx, expected_profile_id=UUID(str(pointer.bucket_id)))
    deadline = mutation_deadline()
    baseline, existing = read_runtime_descendants(client, operation=authority, deadline=deadline)
    if index < 0 or index >= len(existing):
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.descendiente.index_out_of_range",
            context={"index": str(index), "total": str(len(existing))},
        )
    remaining = tuple(d for i, d in enumerate(existing) if i != index)
    committed = replace_runtime_descendants(
        client,
        baseline=baseline,
        descendants=remaining,
        operation=authority,
        deadline=deadline,
    )

    from .._config_descendiente_payloads import ConfigProfileDescendienteRemoveResult

    result = ConfigProfileDescendienteRemoveResult(
        profile=pointer.label,
        removed_index=index,
        total=len(committed),
    )
    emit_envelope(
        ctx,
        command="config.profile.descendiente.remove",
        result=result,
        lines=(
            f"profile\t{pointer.label}",
            f"removed_index\t{index}",
            f"total\t{len(committed)}",
        ),
    )


__all__ = ["descendiente_add", "descendiente_door", "descendiente_list", "descendiente_remove"]
