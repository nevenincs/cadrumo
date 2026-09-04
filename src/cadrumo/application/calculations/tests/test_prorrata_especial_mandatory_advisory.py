"""Behaviour regressions for the LIVA art. 103.Dos.2 mandatory-especial advisory.

See Also:
    :func:`~application.calculations.build_prorrata_especial_mandatory_advisory`
        The settlement-time +10% advisory builder under test.
    :func:`~domain.iva.is_especial_mandatory`
        The pure LIVA art. 103.Dos.2 gate the builder consumes.
"""

from __future__ import annotations

from datetime import date as _esp_date
from decimal import Decimal

import pytest

from ....core.json_contract import NoticeSeverity
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema_base import ThresholdComparison
from ....domain.iva.prorrata_especial_parameters import (
    ProrrataEspecialMandatoryParameterError,
    ProrrataEspecialMandatoryParameters,
    resolve_prorrata_especial_mandatory_parameters,
)
from ..prorrata_regularizacion import build_prorrata_especial_mandatory_advisory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


#: An explicit resolved margin. These tests exercise the PREDICATE and the
#: advisory wording, not the law; whether 10 inclusive is what art. 103.Dos.2
#: states is answered against the registry by the modelo 303 parameter gate.
_ESPECIAL_PARAMS = ProrrataEspecialMandatoryParameters(
    margin_percentage=Decimal("10"),
    comparison=ThresholdComparison.INCLUSIVE,
    modelo_id="303",
    revision_id="2025",
    resolved_on=_esp_date(2025, 12, 31),
)


def test_advisory_fires_when_general_exceeds_especial_by_more_than_ten_percent() -> None:
    """A >10% general-over-especial spread makes especial obligatory (art. 103.Dos.2)."""
    notice = build_prorrata_especial_mandatory_advisory(
        deduction_under_general=Decimal("111.00"),
        deduction_under_especial=Decimal("100.00"),
        ejercicio=2026,
        parameters=_ESPECIAL_PARAMS,
    )

    assert notice is not None
    # Non-blocking: a warning notice, never a raised refusal.
    assert notice.severity is NoticeSeverity.WARNING
    assert notice.code == "modelo.work.calculate.prorrata_especial_obligatoria"
    assert notice.context is not None
    # Both compared totals ride on the notice context.
    assert notice.context["deduction_under_general"] == "111.00"
    assert notice.context["deduction_under_especial"] == "100.00"
    assert notice.context["ejercicio"] == "2026"
    assert notice.context["regime"] == "especial"
    assert notice.context["legal_refs"] == "ley-37-1992:art-103"


def test_advisory_fires_at_exactly_ten_percent_boundary_from_2015() -> None:
    """Art. 103.Dos.2.º reads "exceda en un 10 por ciento o más", so the boundary itself is obligatory.

    110 against 100 is an excess of exactly ten percent. "O más" reaches the
    margin, so the advisory must fire. The paired below-margin case keeps the
    assertion from passing on a predicate that always fires.
    """
    notice = build_prorrata_especial_mandatory_advisory(
        deduction_under_general=Decimal("110.00"),
        deduction_under_especial=Decimal("100.00"),
        ejercicio=2026,
        parameters=_ESPECIAL_PARAMS,
    )

    assert notice is not None
    assert notice.severity is NoticeSeverity.WARNING
    assert notice.code == "modelo.work.calculate.prorrata_especial_obligatoria"
    assert notice.context is not None
    assert notice.context["margin_percentage"] == "10"
    assert notice.context["margin_inclusive"] == "true"

    assert (
        build_prorrata_especial_mandatory_advisory(
            deduction_under_general=Decimal("109.99"),
            deduction_under_especial=Decimal("100.00"),
            ejercicio=2026,
            parameters=_ESPECIAL_PARAMS,
        )
        is None
    )


def test_the_advisory_envelope_reports_the_margin_it_was_handed() -> None:
    """The notice quotes the bundle's figures, so a reader can tell which text applied.

    This replaces a test that asserted the repealed pre-2015 twenty-percent
    exclusive margin. That redaction is declared nowhere in this tree -- no
    modelo 303 revision covers a pre-2015 filing year, and the bundled
    consolidated corpus carries only the text in force -- so the advisory can no
    longer produce it, and asserting it here would be a legal claim with no
    citable authority behind it. A companion test pins that such an ejercicio is
    refused at the resolver instead.

    Probed with a margin that is deliberately NOT the shipped one, so an
    advisory that reinstated a hardcoded figure would fail rather than pass by
    coincidence.
    """
    arbitrary = ProrrataEspecialMandatoryParameters(
        margin_percentage=Decimal("37"),
        comparison=ThresholdComparison.EXCLUSIVE,
        modelo_id="303",
        revision_id="2025",
        resolved_on=_esp_date(2025, 12, 31),
    )
    # Exclusive at exactly the margin: 137 against 100 must NOT fire.
    assert (
        build_prorrata_especial_mandatory_advisory(
            deduction_under_general=Decimal("137.00"),
            deduction_under_especial=Decimal("100.00"),
            ejercicio=2025,
            parameters=arbitrary,
        )
        is None
    )
    notice = build_prorrata_especial_mandatory_advisory(
        deduction_under_general=Decimal("137.01"),
        deduction_under_especial=Decimal("100.00"),
        ejercicio=2025,
        parameters=arbitrary,
    )
    assert notice is not None
    assert notice.context is not None
    assert notice.context["margin_percentage"] == "37"
    assert notice.context["margin_inclusive"] == "false"


def test_a_pre_2015_ejercicio_is_refused_at_the_resolver() -> None:
    """TEETH: the uncitable redaction is refused rather than silently reused.

    The advisory itself no longer decides anything by year, so the defence
    against applying today's margin to a 2014 ejercicio lives one layer up, at
    the resolver that would have to supply the bundle.
    """
    authority = bundled_authority()
    revision = authority.modelo("303").revisions["2025"]
    with pytest.raises(ProrrataEspecialMandatoryParameterError) as excinfo:
        resolve_prorrata_especial_mandatory_parameters(revision, modelo_id="303", ejercicio=2014)
    assert "predates the only redaction" in str(excinfo.value)


def test_advisory_silent_when_general_does_not_exceed_especial() -> None:
    """A general deduction at or below the especial deduction never fires."""
    notice = build_prorrata_especial_mandatory_advisory(
        deduction_under_general=Decimal("95.00"),
        deduction_under_especial=Decimal("100.00"),
        ejercicio=2026,
        parameters=_ESPECIAL_PARAMS,
    )

    assert notice is None


def test_advisory_fires_when_especial_is_zero_and_general_is_positive() -> None:
    """A zero especial deduction with any positive general deduction is obligatory."""
    notice = build_prorrata_especial_mandatory_advisory(
        deduction_under_general=Decimal("0.01"),
        deduction_under_especial=Decimal("0.00"),
        ejercicio=2026,
        parameters=_ESPECIAL_PARAMS,
    )

    assert notice is not None
    assert notice.severity is NoticeSeverity.WARNING
    assert notice.context is not None
    assert notice.context["deduction_under_especial"] == "0.00"
