"""The calendar event payload carries the service state and never the taxpayer NIF.

contract: projecting an :class:`OverviewCalendarEvent` into
:class:`OverviewCalendarEventPayload` must carry
``notificacion_estado_servicio`` — an operator-facing Ley 39/2015 art. 43.2
service state — and must never carry ``authenticated_identity``, which is a
taxpayer NIF.

Nothing previously asserted either direction. The payload is a registered
``OutputSchema``: it crosses the CLI ``--json`` wire and external surfaces, so
a field added to the source event reaches an operator surface the moment the
payload mirrors it. The NIF is held out of that projection by ``exclude=True`` on
the source field, which is a single keyword one refactor away from deletion, and
its removal would leak silently — the projection would simply start succeeding
with an extra key rather than failing.

These drive the real models through the real ``strict_round_trip`` boundary the
renderer uses; nothing is stubbed.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....application.overview import OverviewCalendarEvent, OverviewCalendarEventType
from ....core import NotificacionEstadoServicio
from ....core.json_contract import strict_round_trip
from .._overview_payloads import OverviewCalendarEventPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_NIF = "12345678Z"


def _event(
    *,
    authenticated_identity: str | None = None,
    notificacion_estado_servicio: NotificacionEstadoServicio | None = None,
    event_type: OverviewCalendarEventType = OverviewCalendarEventType.FILING,
) -> OverviewCalendarEvent:
    return OverviewCalendarEvent(
        event_type=event_type,
        notificacion_estado_servicio=notificacion_estado_servicio,
        event_date=date(2026, 4, 15),
        source="live-snapshot",
        summary="Modelo 303 1T filed",
        reference_id="REF-303-1T",
        authenticated_identity=authenticated_identity,
    )


def test_the_service_state_reaches_the_payload() -> None:
    """POSITIVE CONTROL: the operator-facing service state is carried, not dropped.

    Without this, "keep the NIF out" could be satisfied by projecting neither
    field, which would silently lose the art. 43.2 state the operator needs to
    know whether a notification is still inside its access window.
    """
    state = next(iter(NotificacionEstadoServicio))
    projected = strict_round_trip(
        OverviewCalendarEventPayload,
        _event(
            event_type=OverviewCalendarEventType.MESSAGE,
            notificacion_estado_servicio=state,
        ),
    )

    assert projected.notificacion_estado_servicio == state.value


def test_the_authenticated_identity_never_reaches_the_payload() -> None:
    """The taxpayer NIF is absent from the projected payload's own field set."""
    assert "authenticated_identity" not in OverviewCalendarEventPayload.model_fields


def test_the_nif_value_does_not_survive_the_projection_boundary() -> None:
    """Stronger than a field-name check: the VALUE must not appear in the JSON.

    A field-name assertion passes if the identity is smuggled under a different
    key or folded into a rendered string. This drives a real event carrying a
    real NIF through the real projection and searches the serialized output for
    the value itself.
    """
    event = _event(authenticated_identity=_NIF)

    assert event.authenticated_identity == _NIF  # the source genuinely holds it
    assert _NIF not in event.model_dump_json(), "the source must not serialize the NIF"

    projected = strict_round_trip(OverviewCalendarEventPayload, event)

    assert _NIF not in projected.model_dump_json(), "the NIF must not reach the operator payload"


def test_the_projection_still_succeeds_with_both_fields_populated() -> None:
    """The two fields coexist: carrying the state does not re-admit the identity."""
    state = next(iter(NotificacionEstadoServicio))
    projected = strict_round_trip(
        OverviewCalendarEventPayload,
        _event(
            authenticated_identity=_NIF,
            event_type=OverviewCalendarEventType.MESSAGE,
            notificacion_estado_servicio=state,
        ),
    )

    assert projected.notificacion_estado_servicio == state.value
    assert _NIF not in projected.model_dump_json()


def test_a_filing_event_cannot_claim_a_notification_service_state() -> None:
    """A declaration reference can never reach the DEHu legal-effect notice path."""
    with pytest.raises(ValidationError, match="notificacion_estado_servicio may only be set on message events"):
        _event(notificacion_estado_servicio=NotificacionEstadoServicio.RECHAZO_TACITO)
