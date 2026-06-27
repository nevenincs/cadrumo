"""Modelo work calculation input guards."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import CasillaId, Period, validated_casilla_id
from ....core.resources import resources
from ....tests.secure_sql import isolated_runtime_profile
from .. import create_work_unit
from .._calculate_input import (
    ModeloCalculateCasillaInputError,
    build_work_calculate_input_bundle,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M200_AMBIGUOUS_PRINTED_NUMBER: CasillaId = validated_casilla_id(
    "00562",
    surface="_M200_AMBIGUOUS_PRINTED_NUMBER",
)
_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200010:00562",
    surface="_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA",
)
_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00562",
    surface="_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA",
)


def test_work_calculate_input_bundle_rejects_ambiguous_reused_printed_number(tmp_path: Path) -> None:
    """A raw ``--casilla`` token must be the canonical ``casilla.id``."""
    period = Period.from_year_and_code(2024, "0A")
    snapshot = resources().modelos.authority.snapshot("200", filing_year=2024, period=period.registry_token)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="calculate-input-casilla-id") as profile:
        work_unit = create_work_unit(
            bucket_id=profile.bucket_id,
            modelo="200",
            filing_year=2024,
            period=period,
            revision_id=snapshot.revision.id,
            clock=datetime(2026, 6, 26, 12, 0, tzinfo=UTC),
        )

        with pytest.raises(ModeloCalculateCasillaInputError, match="is ambiguous") as exc_info:
            build_work_calculate_input_bundle(
                work_unit_id=work_unit.work_unit_id,
                casilla_overrides={_M200_AMBIGUOUS_PRINTED_NUMBER: "100.00"},
                binding_overrides={},
                relation_overrides={},
                detail_rows=(),
                borrador_snapshot_id=None,
            )

    assert _M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA in str(exc_info.value)
    assert _M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA in str(exc_info.value)
