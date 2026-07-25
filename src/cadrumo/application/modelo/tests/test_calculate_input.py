"""Modelo work calculation input guards."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import CasillaId, Period, validated_casilla_id
from ....core.resources import resources
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...user_profile import profile_create_storage_span
from ...workflow import workflow_state_repository
from .. import create_work_unit
from .._calculate_input import (
    ModeloCalculateCasillaInputError,
    ModeloCalculateDecimalInputError,
    WorkCalculateInputBundle,
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
_DECIMAL_GRAMMAR_PROFILE_ID = "20000000-0000-4000-8000-000000000001"
_M200_MANUAL_DECIMAL_CASILLA: CasillaId = validated_casilla_id(
    "00001",
    surface="_M200_MANUAL_DECIMAL_CASILLA",
)


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


# Forms a bare ``Decimal(raw_value)`` silently accepted before the canonical
# grammar was applied to this boundary. Each would have become a real casilla
# value feeding a tax calculation: ``1e3`` becomes 1000, ``+140000`` becomes
# 140000, ``.5`` becomes 0.5, and ``NaN``/``Infinity`` poison every downstream
# sum. The grammar refuses each with the boundary's own typed error.
_NON_CANONICAL_CASILLA_VALUES = (
    "1e3",
    "1E3",
    "1e-3",
    "+140000",
    "+1.50",
    "NaN",
    "Infinity",
    "-Infinity",
    "1_000",
    ".5",
    "1.",
)

# Canonical forms that MUST keep working, including sub-cent precision: the AEAT
# fixed-width encoder rounds such a value to cents with ROUND_HALF_UP, so the
# input boundary must not refuse it.
_CANONICAL_CASILLA_VALUES = ("140000", "140000.00", "-140000.55", "0", "2.345", "0.075")


def _m200_bundle_with_casilla_value(raw_value: str, *, tmp_path: Path) -> WorkCalculateInputBundle:
    """Drive the real calculate-input boundary with one manual ``--casilla`` value."""
    period = Period.from_year_and_code(2024, "0A")
    snapshot = resources().modelos.authority.snapshot("200", filing_year=2024, period=period.registry_token)
    bucket_id = _DECIMAL_GRAMMAR_PROFILE_ID
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
        return build_work_calculate_input_bundle(
            work_unit_id=work_unit.work_unit_id,
            casilla_overrides={_M200_MANUAL_DECIMAL_CASILLA: raw_value},
            binding_overrides={},
            relation_overrides={},
            detail_rows=(),
            borrador_snapshot_id=None,
        )


@pytest.mark.parametrize("raw_value", _NON_CANONICAL_CASILLA_VALUES)
def test_casilla_override_refuses_non_canonical_decimal(raw_value: str, tmp_path: Path) -> None:
    """A non-canonical ``--casilla`` value refuses instead of being coerced."""
    with pytest.raises(ModeloCalculateDecimalInputError, match="is not a decimal"):
        _m200_bundle_with_casilla_value(raw_value, tmp_path=tmp_path)


@pytest.mark.parametrize("raw_value", _CANONICAL_CASILLA_VALUES)
def test_casilla_override_accepts_canonical_decimal(raw_value: str, tmp_path: Path) -> None:
    """The tightening refuses only non-canonical text; real amounts still parse.

    Sub-cent precision is included deliberately: capping the fractional part at
    two digits here would refuse a value the AEAT encoder is built to round.
    """
    bundle = _m200_bundle_with_casilla_value(raw_value, tmp_path=tmp_path)
    assert bundle.casilla_inputs[_M200_MANUAL_DECIMAL_CASILLA] == Decimal(raw_value)
