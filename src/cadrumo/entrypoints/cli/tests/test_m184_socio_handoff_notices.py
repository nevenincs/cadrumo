"""Coverage for the Modelo 184 per-socio régimen-de-atribución handoff Notices.

The ``work verify`` and ``work file`` CLI paths emit one info Notice per socio
carrying the attributed base plus the ``attribution_received`` fact keys the
socio records on their own workspace: the cross-bucket value is handed over by
hand, not auto-flowed. The helper stays
silent for any revision without Modelo 184 member rows, so a non-M184 filing —
or an M184 with no socios — never emits a spurious handoff.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.json_contract import NoticeSeverity
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    Modelo184MemberRow,
    Modelo349OperadorRow,
    ModeloDetailRow,
    derive_calculation_revision_id,
)
from .._modelo_rendering import m184_socio_handoff_notices

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLOCK = datetime(2026, 7, 9, tzinfo=UTC)
_WORK_UNIT_ID = "a" * 64


def _revision(*detail_rows: ModeloDetailRow) -> CalculationRevision:
    revision_id = derive_calculation_revision_id(
        work_unit_id=_WORK_UNIT_ID,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        detail_rows=tuple(detail_rows),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=_WORK_UNIT_ID,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        detail_rows=tuple(detail_rows),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def test_handoff_emits_one_info_notice_per_socio() -> None:
    revision = _revision(
        Modelo184MemberRow(
            nif="12345678A", nombre="Ana Socia", porcentaje=Decimal("60.00"), importe=Decimal("58100.00")
        ),
        Modelo184MemberRow(
            nif="87654321B", nombre="Beto Comunero", porcentaje=Decimal("40.00"), importe=Decimal("38700.00")
        ),
    )

    notices = m184_socio_handoff_notices(revision)

    assert len(notices) == 2
    assert all(notice.severity is NoticeSeverity.INFO for notice in notices)
    first, second = notices
    assert first.context is not None
    assert second.context is not None
    assert first.context["nif"] == "12345678A"
    assert first.context["nombre"] == "Ana Socia"
    assert first.context["base_imponible_attributed"] == "58100.00"
    # The message carries nif/nombre/importe. A socio handoff has no executable
    # action because it crosses profiles and still requires the operator's own
    # target selection and manual binding decision.
    assert "58100.00" in first.message
    assert "Ana Socia" in first.message
    assert "attribution_received" in first.message
    assert first.action is None
    assert first.context["target_casilla"] == "1577"
    assert second.context["nif"] == "87654321B"
    assert second.context["base_imponible_attributed"] == "38700.00"
    assert second.action is None


def test_handoff_silent_without_member_rows() -> None:
    assert m184_socio_handoff_notices(_revision()) == []


def test_handoff_silent_for_non_m184_detail_rows() -> None:
    # A revision carrying only a non-atribución detail row (e.g. an M349
    # intra-community operator row) must not emit a socio handoff — the helper
    # filters on the typed row, it does not fire for any detail row.
    non_m184 = Modelo349OperadorRow(
        codigo_pais="DE",
        nif_comunitario="DE123456789",
        razon_social="Deutschland GmbH",
        clave_operacion="E",
        importe=Decimal("300.00"),
    )
    assert m184_socio_handoff_notices(_revision(non_m184)) == []
