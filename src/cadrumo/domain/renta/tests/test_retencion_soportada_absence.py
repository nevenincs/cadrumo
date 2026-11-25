"""The absence attestation's model and the class-to-category applicability table.

The table is checked against the bundled income-category vocabulary, so a
token the profile can never declare cannot make a class read as absent.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from ....core.retencion_soportada import RetencionSoportadaClase
from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.irpf_income_categories import resolve_irpf_income_category_catalogue
from ..retencion_soportada_absence import (
    ABSENCE_ATTESTATION_NOTE_MAX_LENGTH,
    RetencionSoportadaAbsence,
    RetencionSoportadaAbsenceState,
)
from ..retencion_soportada_applicability import (
    RETENCION_SOPORTADA_INCOME_CATEGORIES,
    RetencionSoportadaApplicability,
    retencion_soportada_applicability,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_AT = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
_NOTE = "Rental with no withholding: the tenant is a private individual."


def _attestation(**overrides: object) -> RetencionSoportadaAbsence:
    payload: dict[str, object] = {
        "ejercicio": 2025,
        "income_class": "arrendamiento_inmueble_urbano",
        "note": _NOTE,
        "attested_at": _AT.isoformat(),
    }
    payload.update(overrides)
    return RetencionSoportadaAbsence.model_validate_json(json.dumps(payload))


def test_an_attestation_round_trips_and_withdraws_without_losing_when_it_was_made() -> None:
    attestation = _attestation()
    assert attestation.active
    assert attestation.kind == "absence_attestation"
    assert attestation.identity == (2025, RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO)
    assert RetencionSoportadaAbsence.model_validate_json(attestation.model_dump_json()) == attestation

    withdrawn = attestation.withdrawn(_AT + timedelta(days=3))
    assert not withdrawn.active
    assert withdrawn.state is RetencionSoportadaAbsenceState.WITHDRAWN
    assert withdrawn.attested_at == _AT
    assert withdrawn.withdrawn_at == _AT + timedelta(days=3)
    assert withdrawn.note == _NOTE


@pytest.mark.parametrize(
    "overrides",
    [
        {"note": ""},
        {"note": "   "},
        {"note": "x" * (ABSENCE_ATTESTATION_NOTE_MAX_LENGTH + 1)},
        {"state": "withdrawn"},
        {"withdrawn_at": (_AT + timedelta(days=1)).isoformat()},
        {"state": "withdrawn", "withdrawn_at": (_AT - timedelta(days=1)).isoformat()},
        {"attested_at": "2026-04-02T09:00:00"},
        {"ejercicio": 999},
        {"income_class": "pension"},
        {"kind": "payer_certificate"},
    ],
    ids=[
        "empty-note",
        "blank-note",
        "overlong-note",
        "withdrawn-without-instant",
        "instant-while-active",
        "withdrawn-before-made",
        "naive-instant",
        "three-digit-year",
        "unknown-class",
        "foreign-kind",
    ],
)
def test_an_incoherent_attestation_is_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _attestation(**overrides)


def test_the_note_at_its_limit_is_kept() -> None:
    note = "x" * ABSENCE_ATTESTATION_NOTE_MAX_LENGTH
    assert _attestation(note=note).note == note


def test_every_category_the_table_names_is_declared_by_the_bundled_vocabulary(
    operation: PinnedAuthorityOperation,
) -> None:
    vocabulary = resolve_irpf_income_category_catalogue(effective_date=date(2026, 3, 10), authority=operation)
    declared = {str(token) for token in vocabulary.all_categories}
    named = {
        token
        for categories in RETENCION_SOPORTADA_INCOME_CATEGORIES.values()
        if categories is not None
        for token in categories
    }
    assert named
    assert named <= declared
    assert set(RETENCION_SOPORTADA_INCOME_CATEGORIES) == set(RetencionSoportadaClase)


@pytest.mark.parametrize(
    ("income_class", "declared", "expected"),
    [
        (RetencionSoportadaClase.TRABAJO, frozenset({"trabajo"}), RetencionSoportadaApplicability.DECLARED),
        (RetencionSoportadaClase.TRABAJO, frozenset({"pension"}), RetencionSoportadaApplicability.DECLARED),
        (
            RetencionSoportadaClase.TRABAJO,
            frozenset({"actividad_economica"}),
            RetencionSoportadaApplicability.DECLARED_ABSENT,
        ),
        (
            RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO,
            frozenset({"capital_inmobiliario"}),
            RetencionSoportadaApplicability.DECLARED,
        ),
        (
            RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO_ACTIVIDAD,
            frozenset({"capital_inmobiliario"}),
            RetencionSoportadaApplicability.DECLARED_ABSENT,
        ),
        # Activity income alone does not say whether one activity is a rental: without the
        # activities' IAE groups the class is unknown, never declared absent.
        (
            RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO_ACTIVIDAD,
            frozenset({"actividad_economica"}),
            RetencionSoportadaApplicability.UNKNOWN,
        ),
        (
            RetencionSoportadaClase.GANANCIA_PATRIMONIAL,
            frozenset({"trabajo"}),
            RetencionSoportadaApplicability.DECLARED_ABSENT,
        ),
        (RetencionSoportadaClase.CAPITAL_MOBILIARIO, None, RetencionSoportadaApplicability.UNKNOWN),
        (RetencionSoportadaClase.CAPITAL_MOBILIARIO, frozenset(), RetencionSoportadaApplicability.UNKNOWN),
        (
            RetencionSoportadaClase.ATRIBUCION_CAPITAL_MOBILIARIO,
            frozenset({"trabajo"}),
            RetencionSoportadaApplicability.UNKNOWN,
        ),
        (
            RetencionSoportadaClase.IMPUTACION_DERECHOS_IMAGEN,
            frozenset({"trabajo", "capital_mobiliario"}),
            RetencionSoportadaApplicability.UNKNOWN,
        ),
    ],
)
def test_applicability_reads_the_declared_categories_and_never_infers_absence_from_silence(
    income_class: RetencionSoportadaClase,
    declared: frozenset[str] | None,
    expected: RetencionSoportadaApplicability,
) -> None:
    assert retencion_soportada_applicability(income_class, declared, effective_date=_AT.date()) is expected


def test_a_class_without_a_category_is_unknown_under_every_declaration() -> None:
    every_category = frozenset(
        token
        for categories in RETENCION_SOPORTADA_INCOME_CATEGORIES.values()
        if categories is not None
        for token in categories
    )
    for income_class, categories in RETENCION_SOPORTADA_INCOME_CATEGORIES.items():
        if categories is None:
            for declared in (None, frozenset(), frozenset({"trabajo"}), every_category):
                assert retencion_soportada_applicability(income_class, declared, effective_date=_AT.date()) is (
                    RetencionSoportadaApplicability.UNKNOWN
                )
