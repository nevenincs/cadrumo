"""A listed absence attestation names its state in the operator's language."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ....core.config import override_settings
from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.renta.retencion_soportada_absence import RetencionSoportadaAbsence, RetencionSoportadaAbsenceState
from ..results import RetencionSoportadaAbsenceRowProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_AT = datetime(filing_year_envelope().horizon, 3, 1, 9, 0, tzinfo=UTC)


def _row(state: RetencionSoportadaAbsenceState) -> RetencionSoportadaAbsenceRowProjection:
    attestation = RetencionSoportadaAbsence(
        ejercicio=filing_year_envelope().horizon,
        income_class=RetencionSoportadaClase.CAPITAL_MOBILIARIO,
        note="Sin pagador",
        attested_at=_AT,
    )
    if state is RetencionSoportadaAbsenceState.WITHDRAWN:
        attestation = attestation.withdrawn(_AT)
    return RetencionSoportadaAbsenceRowProjection.from_attestation(attestation, revision_id="r1")


@pytest.mark.parametrize(
    ("language", "state", "words"),
    [
        ("en", RetencionSoportadaAbsenceState.ACTIVE, "In force"),
        ("en", RetencionSoportadaAbsenceState.WITHDRAWN, "Withdrawn"),
        ("es", RetencionSoportadaAbsenceState.ACTIVE, "Vigente"),
        ("ca", RetencionSoportadaAbsenceState.WITHDRAWN, "Retirada"),
        ("hu", RetencionSoportadaAbsenceState.ACTIVE, "Hatályos"),
    ],
)
def test_each_state_is_served_in_the_operators_language(
    language: str, state: RetencionSoportadaAbsenceState, words: str
) -> None:
    with override_settings(cadrumo_output_language=language):
        row = _row(state)
    assert row.state is state
    assert row.state_label == words
