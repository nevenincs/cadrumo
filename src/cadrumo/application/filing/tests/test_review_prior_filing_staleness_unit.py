"""Unit coverage for prior-filing approval-basis fingerprints.

See Also:
    :func:`~application.filing._review._prior_filing_observations_fingerprint`
        Order-independent digest helper under test for bucket-local prior filed
        observations.
    :func:`~application.filing.empty_prior_filing_observations_fingerprint`
        Public empty-surface sentinel compared against the prior-observation
        digest helper.
    :class:`~domain.calculations.registry.RegistryModeloObservation`
        Typed observation envelope projected into the prior-filing approval
        basis.
    :class:`~domain.calculations.registry.CasillaObservation`
        Per-casilla value rows whose filed value and legal/source refs enter
        the digest.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import CasillaId, validated_casilla_id
from cadrumo.domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ...calculations import ObservationEnvelopePayload
from .. import empty_prior_filing_observations_fingerprint
from .._review import _prior_filing_observations_fingerprint

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LEGAL_REFS = ("ley-35-2006:art-99",)
_SOURCE_REFS = ("boe-modelo-130-2025-form",)


_M130_RESULTADO_CASILLA: CasillaId = validated_casilla_id("19", surface="prior filing staleness unit test")


def _prior_observation(*, value: str) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="130",
        filing_year=2026,
        period="1T",
        observations=(
            CasillaObservation(
                casilla_id=_M130_RESULTADO_CASILLA,
                value=Decimal(value),
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
        ),
    )


def _carrier(
    *, value: str, source_kind: str = "app_filing", stamped_revision_id: str = "2019-y-siguientes"
) -> ObservationEnvelopePayload:
    return ObservationEnvelopePayload(
        observation=_prior_observation(value=value),
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_kind=source_kind,
        member_nif=None,
        stamped_revision_id=stamped_revision_id,
        source_metadata={},
    )


def test_prior_filing_fingerprint_changes_when_a_filed_value_changes() -> None:
    before = _prior_filing_observations_fingerprint([_carrier(value="100.00")])
    after = _prior_filing_observations_fingerprint([_carrier(value="250.00")])

    assert before != after


def test_prior_filing_fingerprint_tracks_a_text_casilla_without_decimal_coercion() -> None:
    def carrier(value: str) -> ObservationEnvelopePayload:
        observation = RegistryModeloObservation(
            modelo="130",
            filing_year=2026,
            period="1T",
            observations=(
                CasillaObservation(
                    casilla_id=_M130_RESULTADO_CASILLA,
                    value_kind="text",
                    value=value,
                    legal_refs=_LEGAL_REFS,
                    source_refs=_SOURCE_REFS,
                ),
            ),
        )
        return ObservationEnvelopePayload(
            observation=observation,
            captured_at=datetime(2026, 1, 1, tzinfo=UTC),
            source_kind="app_filing",
            member_nif=None,
            stamped_revision_id="2019-y-siguientes",
            source_metadata={},
        )

    before = _prior_filing_observations_fingerprint([carrier("1T")])
    after = _prior_filing_observations_fingerprint([carrier("2T")])

    assert before != after


def test_prior_filing_fingerprint_tracks_the_stamped_revision() -> None:
    before = _prior_filing_observations_fingerprint([_carrier(value="100.00", stamped_revision_id="2019-y-siguientes")])
    after = _prior_filing_observations_fingerprint([_carrier(value="100.00", stamped_revision_id="2024-y-siguientes")])

    assert before != after


def test_prior_filing_fingerprint_is_deterministic_and_order_independent() -> None:
    a = _carrier(value="100.00")
    b = ObservationEnvelopePayload(
        observation=RegistryModeloObservation(
            modelo="130",
            filing_year=2025,
            period="1T",
            observations=(
                CasillaObservation(
                    casilla_id=_M130_RESULTADO_CASILLA,
                    value=Decimal("200.00"),
                    legal_refs=_LEGAL_REFS,
                    source_refs=_SOURCE_REFS,
                ),
            ),
        ),
        captured_at=datetime(2026, 1, 2, tzinfo=UTC),
        source_kind="app_filing",
        member_nif=None,
        stamped_revision_id="2019-y-siguientes",
        source_metadata={},
    )

    assert _prior_filing_observations_fingerprint([a, b]) == _prior_filing_observations_fingerprint([b, a])


def test_prior_filing_fingerprint_distinguishes_empty_from_populated() -> None:
    empty = _prior_filing_observations_fingerprint([])
    populated = _prior_filing_observations_fingerprint([_carrier(value="100.00")])

    assert empty != populated
    assert empty == empty_prior_filing_observations_fingerprint()
    assert empty == _prior_filing_observations_fingerprint([])
