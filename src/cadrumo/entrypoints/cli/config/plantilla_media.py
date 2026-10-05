"""``aeat config profile plantilla-media``: the average workforce per calendar year.

Each leaf parses its operands at the boundary and reads or mutates through
the authenticated runtime. The average workforce crosses the boundary as
text and becomes a ``Decimal``; a float would lose the two decimal places
LIS art. 102.1 counts.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import typer

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.frontend_client_contracts import ProfileViewCollection
from ....adapters.local_runtime.profile_mutations import ProfileMutationCompletion
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.user_profile.profile_operation_contracts import (
    ProfilePlantillaMediaOperationProjection,
    ProfilePlantillaMediaOperationRequest,
    ProfilePlantillaMediaRemove,
    ProfilePlantillaMediaSet,
)
from ....application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from ....core.decimal.grammar import try_parse_canonical_decimal
from ....core.external_constants import OutputLanguage
from ....domain.user_profile.errors import UserProfileValidationError
from ....domain.user_profile.plantilla_media import PlantillaMediaState, PlantillaMediaYear, plantilla_media_years
from .._config_plantilla_media_payloads import ConfigProfilePlantillaMediaResult, ProfilePlantillaMediaYearPayload
from ..common import activate_subcommand_output_language as _activate_subcommand_output_language
from ..common import emit_envelope
from ..errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ..runtime_profile_binding import require_profile_client
from ._profile_support import require_active_profile_pointer as _active_profile_pointer
from ._runtime_profile_mutation import execute_profile_mutation, mutation_deadline, read_mutation_baseline
from .runtime_profile_view import resolve_runtime_profile_output_language


def _average_workforce(raw: str) -> Decimal:
    value = try_parse_canonical_decimal(raw)
    if value is None:
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


def _years_from_facts(collection: ProfileViewCollection) -> tuple[PlantillaMediaYear, ...]:
    """Restore only typed complete facts from one authorized revision."""
    items = collection.items(ProfileViewPageKind.FACTS)
    if not all(isinstance(item, ProfileViewFactItem) for item in items):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    facts = tuple(item for item in items if isinstance(item, ProfileViewFactItem))
    values = {item.path: item.value for item in facts}
    if len(values) != len(facts):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    try:
        return plantilla_media_years(values)
    except UserProfileValidationError:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None


def _client(ctx: typer.Context, *, requested_language: OutputLanguage | None) -> RuntimeFrontendClient:
    pointer = _active_profile_pointer()
    client = require_profile_client(ctx, expected_profile_id=UUID(str(pointer.bucket_id)))
    language = resolve_runtime_profile_output_language(client, requested=requested_language)
    _activate_subcommand_output_language(ctx, language)
    return client


def _committed_years(
    completed: ProfileMutationCompletion, current: ProfileViewCollection, *, requested_year: int
) -> tuple[PlantillaMediaYear, ...]:
    """Retain a settled mutation's identity if its final view is unusable."""
    try:
        if (
            not isinstance(completed.projection, ProfilePlantillaMediaOperationProjection)
            or completed.projection.year != requested_year
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return _years_from_facts(current)
    except RuntimeRefusalError as error:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.mutation.committed_view_unavailable",
            context={
                "operation_id": str(completed.operation_id),
                "commit_state": "succeeded",
                "record_revision": completed.projection.record_revision,
                "read_state": "unavailable",
            },
        ) from error


def plantilla_media_set(
    ctx: typer.Context,
    year: int,
    average_workforce: str,
    state: PlantillaMediaState,
    output_language: OutputLanguage | None = None,
) -> None:
    """Declare or replace one calendar year's average workforce."""
    client = _client(ctx, requested_language=output_language)
    amount = _average_workforce(average_workforce)
    deadline = mutation_deadline()
    baseline = read_mutation_baseline(client, deadline=deadline)
    completed, current = execute_profile_mutation(
        client,
        ProfilePlantillaMediaOperationRequest(
            profile_id=client.profile_id,
            expected_revision=baseline.record_revision,
            expected_content_digest=baseline.content_digest,
            year=year,
            change=ProfilePlantillaMediaSet(average_workforce=str(amount), state=state),
        ),
        deadline=deadline,
    )
    years = _committed_years(completed, current, requested_year=year)
    _emit(ctx, command="config.profile.plantilla_media.set", years=years)


def plantilla_media_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """Show every declared year, in year order."""
    client = _client(ctx, requested_language=output_language)
    years = _years_from_facts(read_mutation_baseline(client, deadline=mutation_deadline()))
    _emit(ctx, command="config.profile.plantilla_media.list", years=years)


def plantilla_media_remove(
    ctx: typer.Context,
    year: int,
    output_language: OutputLanguage | None = None,
) -> None:
    """Withdraw one declared year."""
    client = _client(ctx, requested_language=output_language)
    deadline = mutation_deadline()
    baseline = read_mutation_baseline(client, deadline=deadline)
    completed, current = execute_profile_mutation(
        client,
        ProfilePlantillaMediaOperationRequest(
            profile_id=client.profile_id,
            expected_revision=baseline.record_revision,
            expected_content_digest=baseline.content_digest,
            year=year,
            change=ProfilePlantillaMediaRemove(),
        ),
        deadline=deadline,
    )
    years = _committed_years(completed, current, requested_year=year)
    _emit(ctx, command="config.profile.plantilla_media.remove", years=years)


__all__ = ["plantilla_media_list", "plantilla_media_remove", "plantilla_media_set"]
