"""Tests for the ledger-backed Modelo 210 IRNR rendimientos-íntegros registry binding.

No prior test exercised
:func:`resolve_ledger_irnr_income_aggregation_binding_values` against a real
Decimal outcome — the only existing coverage was structural (selector
shape, source kind taxonomy, precedence ladder membership). This file
grounds it in the committed M210 ``2025`` registry revision, whose sole
``ledger_irnr_income_aggregation`` binding
(``m210-2025-ledger-irnr-rendimientos-integros``) targets casilla
``rendimientos_integros`` per TRLIRNR art. 13.1 / art. 24. It also serves as
the F15 regression net for this family's refactor onto the shared
:func:`~....registry._ledger_binding_resolution.resolve_ledger_family_binding_values`
skeleton, and :func:`unsupported_ledger_irnr_income_observations`'s
matching refactor onto
:func:`~....registry._ledger_binding_resolution.unsupported_ledger_family_observations`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from .. import (
    build_snapshot,
    resolve_ledger_irnr_income_aggregation_binding_values,
    unsupported_ledger_irnr_income_observations,
    validate_ledger_irnr_income_aggregation_binding_definition,
)
from ..binding_selector_utils import selector_as_dict
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IRNR_INCOME_BINDING = "m210-2025-ledger-irnr-rendimientos-integros"
_M210_RENDIMIENTOS_CASILLA: CasillaId = validated_casilla_id(
    "rendimientos_integros",
    surface="_M210_RENDIMIENTOS_CASILLA",
)
_M210_OTHER_CASILLA: CasillaId = validated_casilla_id("cuota_diferencial", surface="_M210_OTHER_CASILLA")


@dataclass(frozen=True)
class _IrnrIncomeObservation:
    """Minimal stand-in satisfying ``IrnrIncomeObservationProtocol``."""

    target_casilla_id: CasillaId
    gross_income_amount: Decimal


def _modelo_210_snapshot():
    modelo, catalogues = _committed_modelo("210")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )


def test_committed_m210_rendimientos_binding_reads_gross_income_sum_fact() -> None:
    """The committed registry routes rendimientos_integros through gross_income_sum."""
    revision = _modelo_210_snapshot().revision

    binding = next(binding for binding in revision.bindings if binding.id == _IRNR_INCOME_BINDING)
    assert binding.source == "ledger_irnr_income_aggregation"
    assert selector_as_dict(binding) == {
        "modelo": "210",
        "target_casilla_id": _M210_RENDIMIENTOS_CASILLA,
        "fact": "gross_income_sum",
    }
    validate_ledger_irnr_income_aggregation_binding_definition(binding)


def test_resolver_sums_matching_casilla_and_excludes_other_casilla() -> None:
    """The binding sums only observations targeting rendimientos_integros.

    Two gross-income rows feed the casilla (400.00 + 250.50 = 650.50); a
    third, distinguishing amount is routed to an unrelated casilla. The
    expected total is derived from the two matching inputs alone, never
    copied from what the resolver under test returns.
    """
    revision = _modelo_210_snapshot().revision
    binding = next(binding for binding in revision.bindings if binding.id == _IRNR_INCOME_BINDING)

    first, second = Decimal("400.00"), Decimal("250.50")
    off_casilla_amount = Decimal("999.99")
    matching_one = _IrnrIncomeObservation(target_casilla_id=_M210_RENDIMIENTOS_CASILLA, gross_income_amount=first)
    matching_two = _IrnrIncomeObservation(target_casilla_id=_M210_RENDIMIENTOS_CASILLA, gross_income_amount=second)
    off_casilla = _IrnrIncomeObservation(target_casilla_id=_M210_OTHER_CASILLA, gross_income_amount=off_casilla_amount)

    resolved = resolve_ledger_irnr_income_aggregation_binding_values(
        revision,
        (matching_one, matching_two, off_casilla),
    )

    assert resolved[binding.id] == first + second
    assert resolved[binding.id] != first + second + off_casilla_amount, (
        "an observation routed to another casilla must not feed rendimientos_integros"
    )


def test_unsupported_flags_non_zero_income_routed_to_no_binding() -> None:
    """A non-zero gross income whose target_casilla_id matches no binding is surfaced."""
    revision = _modelo_210_snapshot().revision

    routed = _IrnrIncomeObservation(target_casilla_id=_M210_RENDIMIENTOS_CASILLA, gross_income_amount=Decimal("500"))
    unrouted = _IrnrIncomeObservation(target_casilla_id=_M210_OTHER_CASILLA, gross_income_amount=Decimal("120"))

    result = unsupported_ledger_irnr_income_observations(revision, (routed, unrouted))

    assert result == (unrouted,)


def test_unsupported_does_not_flag_zero_gross_income() -> None:
    """A zero-income observation routed to no binding must NOT false-fire."""
    revision = _modelo_210_snapshot().revision

    zero_unrouted = _IrnrIncomeObservation(target_casilla_id=_M210_OTHER_CASILLA, gross_income_amount=Decimal("0"))

    result = unsupported_ledger_irnr_income_observations(revision, (zero_unrouted,))

    assert result == ()
