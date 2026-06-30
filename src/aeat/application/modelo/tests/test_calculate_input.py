"""Modelo work calculation input guards."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import CasillaId, Period, validated_casilla_id
from ....core.resources import resources
from ....tests.secure_sql import isolated_profile_storage_root
from ...user_profile._orchestration import profile_create_storage_span
from ...user_profile._testing import register_minimal_profile
from ...workflow._persistence import workflow_state_repository
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
_PROFILE_ID = "20000000-0000-4000-8000-000000000562"


def test_work_calculate_input_bundle_rejects_ambiguous_reused_printed_number(tmp_path: Path) -> None:
    """A raw ``--casilla`` token must be the canonical ``casilla.id``."""
    period = Period.from_year_and_code(2024, "0A")
    snapshot = resources().modelos.authority.snapshot("200", filing_year=2024, period=period.registry_token)

    bucket_id = _PROFILE_ID
    with isolated_profile_storage_root(tmp_path=tmp_path), profile_create_storage_span(bucket_id):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id=bucket_id,
                overrides={
                    "identity.tax_id": "B66012345",
                    "identity.legal_name": "Calculate Input SL",
                    "taxpayer_type.entity_type": "legal_entity",
                    "taxpayer_type.legal_entity_form": "sl",
                },
            ),
        )
        work_unit = create_work_unit(
            bucket_id=bucket_id,
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
