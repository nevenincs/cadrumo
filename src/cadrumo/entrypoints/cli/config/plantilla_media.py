"""``aeat config profile plantilla-media``: the average workforce per calendar year.

Each leaf parses its operands at the boundary and delegates to the shared
application service, so the CLI and the TUI write the same instances through
the same validation.  The average workforce crosses the boundary as text and
becomes a ``Decimal``; a float would lose the two decimal places LIS art.
102.1 counts.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

import typer

from ....application.user_profile.plantilla_media_rows import (
    PlantillaMediaWriteSurface,
    list_plantilla_media_years,
    remove_plantilla_media_year,
    set_plantilla_media_year,
)
from ....core.external_constants import OutputLanguage
from ....domain.user_profile.plantilla_media import PlantillaMediaState, PlantillaMediaYear
from .._config_plantilla_media_payloads import ConfigProfilePlantillaMediaResult, ProfilePlantillaMediaYearPayload
from ..common import activate_subcommand_output_language as _activate_subcommand_output_language
from ..common import emit_envelope
from ..errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._profile_support import require_active_profile_pointer as _active_profile_pointer

if TYPE_CHECKING:
    from ....domain.calculations.registry.authority_artifact import ProfileDecodeContext


def _decode_context(ctx: typer.Context) -> ProfileDecodeContext:
    from ..state_projection_support import authority_operation

    return authority_operation(ctx).profile_decode_context()


def _average_workforce(raw: str) -> Decimal:
    try:
        value = Decimal(raw.strip())
    except InvalidOperation as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.plantilla_media.average_workforce_not_a_number",
            context={"average_workforce": raw},
        ) from exc
    if not value.is_finite():
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.plantilla_media.average_workforce_not_a_number",
            context={"average_workforce": raw},
        )
    return value


def _emit(ctx: typer.Context, *, command: str, years: tuple[PlantillaMediaYear, ...]) -> None:
    emit_envelope(
        ctx,
        command=command,
        result=ConfigProfilePlantillaMediaResult(
            years=[
                ProfilePlantillaMediaYearPayload(
                    year=item.year,
                    average_workforce=item.average_workforce,
                    state=item.state,
                )
                for item in years
            ],
        ),
        lines=tuple(f"{item.year}\t{item.average_workforce}\t{item.state.value}" for item in years),
    )


def plantilla_media_set(
    ctx: typer.Context,
    year: int,
    average_workforce: str,
    state: PlantillaMediaState,
    output_language: OutputLanguage | None = None,
) -> None:
    """Declare or replace one calendar year's average workforce."""
    _activate_subcommand_output_language(ctx, output_language)
    pointer = _active_profile_pointer()
    years = set_plantilla_media_year(
        profile_id=pointer.bucket_id,
        year=year,
        average_workforce=_average_workforce(average_workforce),
        state=state,
        surface=PlantillaMediaWriteSurface.CLI,
        profile_decode_context=_decode_context(ctx),
    )
    _emit(ctx, command="config.profile.plantilla_media.set", years=years)


def plantilla_media_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """Show every declared year, in year order."""
    _activate_subcommand_output_language(ctx, output_language)
    pointer = _active_profile_pointer()
    years = list_plantilla_media_years(profile_id=pointer.bucket_id, profile_decode_context=_decode_context(ctx))
    _emit(ctx, command="config.profile.plantilla_media.list", years=years)


def plantilla_media_remove(
    ctx: typer.Context,
    year: int,
    output_language: OutputLanguage | None = None,
) -> None:
    """Withdraw one declared year."""
    _activate_subcommand_output_language(ctx, output_language)
    pointer = _active_profile_pointer()
    years = remove_plantilla_media_year(
        profile_id=pointer.bucket_id,
        year=year,
        surface=PlantillaMediaWriteSurface.CLI,
        profile_decode_context=_decode_context(ctx),
    )
    _emit(ctx, command="config.profile.plantilla_media.remove", years=years)


__all__ = ["plantilla_media_list", "plantilla_media_remove", "plantilla_media_set"]
