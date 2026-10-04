"""Coverage for the Modelo 184 per-socio régimen-de-atribución handoff Notices.

The ``work verify`` and ``work file`` CLI paths render one info Notice per
recorded socio handoff carrying the attributed base plus the
``attribution_received`` fact keys the socio records on their own workspace:
the cross-bucket value is handed over by hand, not auto-flowed. The renderer
stays silent when the writer recorded no handoff.
"""

from __future__ import annotations

import pytest

from ....application.modelo.lifecycle_advisories import Modelo184SocioHandoffV1
from ....core.json_contract import NoticeSeverity
from .._modelo_rendering import m184_socio_handoff_advisory_notices

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_CODE = "modelo.work.m184_socio_handoff"
_TARGET_CASILLA = "1577"
_LEGAL_REFS = "ley-35-2006:art-86"


def _handoff(*, nif: str, nombre: str, porcentaje: str, importe: str) -> Modelo184SocioHandoffV1:
    return Modelo184SocioHandoffV1(
        nif=nif,
        nombre=nombre,
        porcentaje=porcentaje,
        importe=importe,
        code=_CODE,
        target_casilla=_TARGET_CASILLA,
        legal_refs=_LEGAL_REFS,
    )


def test_handoff_emits_one_info_notice_per_socio() -> None:
    notices = m184_socio_handoff_advisory_notices(
        (
            _handoff(nif="12345678A", nombre="Ana Socia", porcentaje="60.00", importe="58100.00"),
            _handoff(nif="87654321B", nombre="Beto Comunero", porcentaje="40.00", importe="38700.00"),
        )
    )

    assert len(notices) == 2
    assert all(notice.severity is NoticeSeverity.INFO for notice in notices)
    first, second = notices
    assert first.code == _CODE
    assert first.context is not None
    assert second.context is not None
    assert first.context["nif"] == "12345678A"
    assert first.context["nombre"] == "Ana Socia"
    assert first.context["base_imponible_attributed"] == "58100.00"
    assert first.context["target_casilla"] == _TARGET_CASILLA
    assert first.context["legal_refs"] == _LEGAL_REFS
    # A socio handoff has no executable action because it crosses profiles and
    # still requires the operator's own target selection and manual binding.
    assert "58100.00" in first.message
    assert "Ana Socia" in first.message
    assert "attribution_received" in first.message
    assert first.action is None
    assert second.context["nif"] == "87654321B"
    assert second.context["base_imponible_attributed"] == "38700.00"
    assert second.action is None


def test_handoff_silent_without_recorded_handoffs() -> None:
    assert m184_socio_handoff_advisory_notices(()) == []
