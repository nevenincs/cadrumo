"""Modelo 100 vivienda-habitual deducción eligibility advisory tests.

Covers the ``modelo-100-YYYY-deduccion-vivienda-habitual-requiere-adquisicion-anterior-2013``
ADVISORY guard shipped on the 2024 and 2025 revisions. The deducción por
inversión en vivienda habitual was abolished for acquisitions after 31-12-2012;
only the transitional régimen (LIRPF DT 18ª) survives, and only for taxpayers
who acquired their dwelling (or satisfied construction/rehabilitation amounts)
before 01-01-2013. The advisory fires when the deducción is claimed
(casilla 0547 > 0) without any pre-2013 eligibility signal — neither a
pre-01-01-2013 acquisition date (casilla 0708) nor a construction-transitional
date (casilla 0690) — so a post-2013 acquirer claiming the abolished deducción
does not silently over-declare the deducción (under-declare tax). It stays
silent for a grounded pre-2013 acquisition and for the construction-transitional
case, per no-silent-under-declaration.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from cadrumo.application.modelo.tests.verification_substance_fixtures import workflow_profile

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ....domain.calculations.registry.tests.published_authority import (
    PublishedGovernedFactSource,
    published_revision,
)
from ....domain.modelos.verification_report import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from ..verification_predicates import evaluate_verification_predicates

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_DEDUCCION_ESTATAL: CasillaId = validated_casilla_id(
    "0547",
    surface="test_verification_m100_vivienda_advisory",
)
_FECHA_ADQUISICION: CasillaId = validated_casilla_id(
    "0708",
    surface="test_verification_m100_vivienda_advisory",
)
_FECHA_CONSTRUCCION: CasillaId = validated_casilla_id(
    "0690",
    surface="test_verification_m100_vivienda_advisory",
)
_SUPPORT = PublishedGovernedFactSource().supported_filing_years()
# The two newest authored Modelo 100 editions below the projecting horizon ship the
# advisory; revision ids are their exercises.
_YEARS = tuple(str(year) for year in (_SUPPORT.horizon - 2, _SUPPORT.horizon - 1))
# LIRPF DT 18: only acquisitions before this day keep the transitional deduction.
_TRANSITIONAL_CUTOFF = date(2013, 1, 1)


def _predicate_id(year: str) -> str:
    return f"modelo-100-{year}-deduccion-vivienda-habitual-requiere-adquisicion-anterior-2013"


def _vivienda_advisory_predicate(year: str) -> VerificationPredicateDefinition:
    """Load the shipped M100 vivienda-habitual eligibility advisory for a revision year."""
    revision = published_revision("100", year)
    predicate = next(p for p in revision.verification_predicates if p.predicate_id == _predicate_id(year))
    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == (
        f'deduccion_requires_adquisicion_before(["0547", "0708", "0690", "{_TRANSITIONAL_CUTOFF.isoformat()}"])'
    )
    return predicate


def test_vivienda_advisory_ships_with_dt_18_grounding() -> None:
    """The advisory cites LIRPF DT 18ª (the transitional-régimen legal basis)."""
    for year in _YEARS:
        predicate = _vivienda_advisory_predicate(year)
        assert "ley-35-2006:dt-18" in tuple(str(r) for r in predicate.legal_refs), year


def test_vivienda_advisory_fires_when_claimed_without_any_eligibility_signal() -> None:
    """A claimed deducción with no acquisition/construction date surfaces a warning advisory."""
    for year in _YEARS:
        predicate = _vivienda_advisory_predicate(year)
        casilla_values: dict[CasillaId, Decimal] = {_DEDUCCION_ESTATAL: Decimal("678.00")}

        findings = evaluate_verification_predicates((predicate,), casilla_values, workflow_profile())

        assert len(findings) == 1, year
        assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY, year
        assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING, year
        assert "ley-35-2006:dt-18" in findings[0].legal_refs, year
        assert findings[0].message_locale_key == "application.modelo.findings.registry_advisory_predicate_fired", year
        assert dict(findings[0].message_facts) == {"predicate_id": _predicate_id(year)}, year


def test_vivienda_advisory_fires_when_acquisition_date_is_after_the_transitional_cutoff() -> None:
    """A claimed deducción with an acquisition date on/after 01-01-2013 fires the advisory."""
    for year in _YEARS:
        predicate = _vivienda_advisory_predicate(year)
        casilla_values: dict[CasillaId, Decimal] = {_DEDUCCION_ESTATAL: Decimal("678.00")}
        after_cutoff = date(_TRANSITIONAL_CUTOFF.year + 2, 6, 15)
        text_values: dict[CasillaId, str] = {_FECHA_ADQUISICION: after_cutoff.strftime("%d/%m/%Y")}

        findings = evaluate_verification_predicates((predicate,), casilla_values, workflow_profile(), text_values)

        assert len(findings) == 1, year
        assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY, year
        assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING, year


def test_vivienda_advisory_fires_when_acquisition_date_on_cutoff() -> None:
    """The cutoff is exclusive: an acquisition dated exactly 01-01-2013 is NOT eligible."""
    for year in _YEARS:
        predicate = _vivienda_advisory_predicate(year)
        casilla_values: dict[CasillaId, Decimal] = {_DEDUCCION_ESTATAL: Decimal("678.00")}
        text_values: dict[CasillaId, str] = {_FECHA_ADQUISICION: _TRANSITIONAL_CUTOFF.isoformat()}

        findings = evaluate_verification_predicates((predicate,), casilla_values, workflow_profile(), text_values)
        assert len(findings) == 1, year


def test_vivienda_advisory_silent_for_grounded_acquisition_before_the_transitional_cutoff() -> None:
    """A claimed deducción with a pre-01-01-2013 acquisition date holds — no advisory."""
    for year in _YEARS:
        predicate = _vivienda_advisory_predicate(year)
        casilla_values: dict[CasillaId, Decimal] = {_DEDUCCION_ESTATAL: Decimal("678.00")}

        earlier = date(_TRANSITIONAL_CUTOFF.year - 3, 3, 10)
        last_eligible_day = _TRANSITIONAL_CUTOFF - timedelta(days=1)
        for before_cutoff in (
            earlier.strftime("%d/%m/%Y"),
            earlier.isoformat(),
            last_eligible_day.strftime("%d/%m/%Y"),
        ):
            text_values: dict[CasillaId, str] = {_FECHA_ADQUISICION: before_cutoff}
            findings = evaluate_verification_predicates((predicate,), casilla_values, workflow_profile(), text_values)
            assert findings == [], f"{year}: acquisition {before_cutoff!r} before the cutoff must not fire the advisory"


def test_vivienda_advisory_silent_for_construction_transitional_case() -> None:
    """A claimed deducción with a construction-transitional date (0690) holds — no advisory."""
    for year in _YEARS:
        predicate = _vivienda_advisory_predicate(year)
        casilla_values: dict[CasillaId, Decimal] = {_DEDUCCION_ESTATAL: Decimal("678.00")}
        text_values: dict[CasillaId, str] = {_FECHA_CONSTRUCCION: "20/07/2013"}

        findings = evaluate_verification_predicates((predicate,), casilla_values, workflow_profile(), text_values)
        assert findings == [], year


def test_vivienda_advisory_silent_when_no_deduccion_claimed() -> None:
    """A zero or absent deducción amount holds the eligibility check trivially."""
    for year in _YEARS:
        predicate = _vivienda_advisory_predicate(year)

        explicit_zero: dict[CasillaId, Decimal] = {_DEDUCCION_ESTATAL: Decimal("0")}
        absent: dict[CasillaId, Decimal] = {}

        assert evaluate_verification_predicates((predicate,), explicit_zero, workflow_profile()) == [], year
        assert evaluate_verification_predicates((predicate,), absent, workflow_profile()) == [], year
