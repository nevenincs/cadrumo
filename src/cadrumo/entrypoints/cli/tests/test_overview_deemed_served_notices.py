"""Tests for the rechazo-tácito notice surfaced on the overview.

A DEHu notification left unopened for the Ley 39/2015 art. 43.2 window is
legally served -- every downstream plazo already running -- even though the
taxpayer never read it. That consequence attaches to the notification's
delivery state, not to its :class:`PostFilingEventKind`, so the kind-keyed
pending-post-filing notice cannot report it: a plain ``notificacion``
contributes nothing to that notice's kind list or context map. These tests pin
the separate notice that does report it, its legal-catalogue provenance, and
that an in-window or already-read notification stays silent.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....application.overview.calendar_models import OverviewCalendarEvent, OverviewCalendarEventType
from ....core import NotificacionEstadoServicio, PostFilingEventKind
from ....core.json_contract import NoticeSeverity, ResolvedNoticeAction
from ....domain.calculations.registry.authority import bundled_authority
from .._overview_rendering import (
    DEEMED_SERVED_LEGAL_REF,
    overview_deemed_served_notification_notices,
    overview_post_filing_event_notices,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _notificacion(
    *,
    reference_id: str,
    estado: NotificacionEstadoServicio | None,
    kind: PostFilingEventKind | None = None,
) -> OverviewCalendarEvent:
    return OverviewCalendarEvent(
        event_type=OverviewCalendarEventType.MESSAGE,
        post_filing_kind=kind,
        event_date=date(2025, 3, 12),
        source="aeat_sede_notifications",
        summary="AEAT notificación",
        reference_id=reference_id,
        status="unread",
        notificacion_estado_servicio=estado,
    )


def test_deemed_served_notifications_emit_one_warning_notice_with_legal_provenance() -> None:
    """Lapsed notifications produce one warning notice citing art. 43.2 and the certificados."""
    events = (
        _notificacion(reference_id="2596230606502", estado=NotificacionEstadoServicio.RECHAZO_TACITO),
        _notificacion(reference_id="2596230606501", estado=NotificacionEstadoServicio.RECHAZO_TACITO),
        _notificacion(reference_id="2596230606503", estado=NotificacionEstadoServicio.EN_PLAZO),
    )

    notices = overview_deemed_served_notification_notices(events)

    assert len(notices) == 1
    notice = notices[0]
    assert notice.code == "overview.notificacion.rechazo_tacito"
    assert notice.severity is NoticeSeverity.WARNING
    assert isinstance(notice.action, ResolvedNoticeAction)

    context = notice.context or {}
    assert context["legal_ref"] == DEEMED_SERVED_LEGAL_REF == "ley-39-2015:art-43.2"
    assert context["count"] == "2"
    # Only the lapsed rows, sorted, and never the in-window one.
    assert context["certificado_ids"] == "2596230606501,2596230606502"


def test_deemed_served_legal_ref_resolves_against_the_registry_catalogue() -> None:
    """The provenance the notice hands the operator is a real, corpus-backed entry."""
    from ....core.resources import bundled_path
    from ....domain.calculations.registry.legal import verify_legal_catalogue

    catalogue = bundled_authority().catalogues.legal
    assert DEEMED_SERVED_LEGAL_REF in catalogue, (
        f"the notice cites {DEEMED_SERVED_LEGAL_REF!r}, absent from the registry legal catalogue"
    )
    reference = catalogue[DEEMED_SERVED_LEGAL_REF]
    verify_legal_catalogue({DEEMED_SERVED_LEGAL_REF: reference}, source_root=bundled_path())
    assert reference.article == "43.2"


def test_plain_notificacion_is_invisible_to_the_kind_keyed_notice() -> None:
    """The reason this notice exists: the pending-post-filing map cannot carry the row.

    A deemed-served plain ``notificacion`` reaches
    :func:`actionable_post_filing_events` (since widened), so the pending
    notice fires -- but its ``kinds`` list and its context map are both keyed on
    ``post_filing_kind``, which the row does not have. Without the dedicated
    notice the operator is told something needs attention and never told what.
    """
    events = (_notificacion(reference_id="2596230606502", estado=NotificacionEstadoServicio.RECHAZO_TACITO),)

    pending = overview_post_filing_event_notices(events)
    assert len(pending) == 1
    assert (pending[0].context or {}) == {}

    deemed = overview_deemed_served_notification_notices(events)
    assert (deemed[0].context or {})["certificado_ids"] == "2596230606502"


@pytest.mark.parametrize(
    "estado",
    [
        None,
        NotificacionEstadoServicio.NO_ENTREGADA,
        NotificacionEstadoServicio.ACCEDIDA,
        NotificacionEstadoServicio.EN_PLAZO,
    ],
)
def test_notifications_not_deemed_served_emit_no_notice(estado: NotificacionEstadoServicio | None) -> None:
    """Only the deemed-served state qualifies; the surface does not flag every message."""
    events = (_notificacion(reference_id="2596230606502", estado=estado),)

    assert overview_deemed_served_notification_notices(events) == []


def test_no_events_emit_no_notice() -> None:
    assert overview_deemed_served_notification_notices(()) == []
