"""E2E threshold/continuity: Modelo 840 IAE INCN exemption across 2 annual contexts.

Modelo 840 (Impuesto sobre Actividades Economicas - declaracion censal) is an
ad_hoc IAE declaration and communication surface (Orden HAC/2572/2003; TRLRHL
RDL 2/2004 arts. 82 and 90). The cross-year invariant for this enrollment is
the turnover-based exemption: each annual context must assess the
``importe neto de la cifra de negocios`` independently against the strict
1,000,000 EUR art. 82.1.c threshold.

The enrollment evidence class is THRESHOLD_CONTINUITY. The test constructs a
real two-year context (real domain assessment, real encrypted-SQLite store,
real registry-grounded Modelo 840 observations) spanning two distinct
``filing_year`` values and records both through the EnrollmentRecorder's
context mode. The context label is the un-fakeable evidence token.

Cross-year invariants tested:
- Year N records INCN below 1,000,000 EUR and is assessed exempt.
- Year N+2 records INCN equal to 1,000,000 EUR and is assessed not exempt,
  proving the legal threshold is strict ("inferior a 1.000.000").
- Both annual contexts are independently persisted and retrievable with their
  encrypted threshold source metadata intact.
- Anti-tautology probe: omitting the INCN metadata produces strict inequality
  against the reloaded payload.

Legal grounding: RDL 2/2004 arts. 78, 82, 90 (IAE obligation, exemption, and
INCN communications); Orden HAC/2572/2003 apartados 1, 6 (Modelo 840 layout and
alta/variacion/baja filing surface).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import (
    CasillaId,
    RegistryAuthorityGrade,
    validated_casilla_id,
)
from ....domain.calculations.registry import RegistryModeloObservation
from ....domain.modelos import (
    Modelo840IaeExemptionAssessment,
    Modelo840IaeExemptionStatus,
    assess_modelo_840_iae_cifra_negocios_exemption,
)
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository
from ._observation_lookup_support import find_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo id this module enrolls into the multi-year-renta authorization gate.
_MODELO = "840"

#: Two distinct annual contexts. M840 cadence is ad_hoc, period selector = ["0A"].
#: filing_year anchors which renta cycle the INCN assessment belongs to.
_YEAR_N = 2024
_YEAR_N_PLUS_2 = 2026

#: Context label for the EnrollmentRecorder (non-calculation / threshold-continuity mode).
_CONTEXT_LABEL = "840-iae-cifra-negocios-exemption-two-annual-contexts"

#: External-authority scenario values for TRLRHL art. 82.1.c.
_EXEMPT_CIFRA_NEGOCIOS_EUR = Decimal("999999.99")
_NOT_EXEMPT_CIFRA_NEGOCIOS_EUR = Decimal("1000000.00")
_LEGAL_THRESHOLD_EUR = Decimal("1000000.00")

_CLOCK_N = datetime(2024, 2, 1, 10, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_2 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)

_METADATA_CIFRA_NEGOCIOS_KEY = "iae_art82_importe_neto_cifra_negocios_eur"
_METADATA_THRESHOLD_KEY = "iae_art82_threshold_eur"
_METADATA_STATUS_KEY = "iae_art82_exemption_status"
_METADATA_LEGAL_REFS_KEY = "iae_art82_legal_refs"


_DECL_TIPO_DECLARACION_CASILLA: CasillaId = validated_casilla_id("decl.tipo-declaracion")
_DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id("decl.ejercicio")


def _threshold_source_metadata(assessment: Modelo840IaeExemptionAssessment) -> dict[str, str]:
    return {
        _METADATA_CIFRA_NEGOCIOS_KEY: str(assessment.importe_neto_cifra_negocios_eur),
        _METADATA_THRESHOLD_KEY: str(assessment.threshold_eur),
        _METADATA_STATUS_KEY: assessment.status.value,
        _METADATA_LEGAL_REFS_KEY: ",".join(assessment.legal_refs),
    }


def _threshold_assessment(
    *,
    filing_year: int,
    cifra_negocios_eur: Decimal,
) -> Modelo840IaeExemptionAssessment:
    return assess_modelo_840_iae_cifra_negocios_exemption(
        filing_year=filing_year,
        importe_neto_cifra_negocios_eur=cifra_negocios_eur,
    )


def _threshold_context_observation(*, filing_year: int) -> RegistryModeloObservation:
    """Build the annual 840 context observation.

    Casillas from the "2003-y-siguientes" revision:
    - ``decl.tipo-declaracion``: Decimal("2") = variacion / INCN communication context
    - ``decl.ejercicio``: the filing year

    The INCN amount and exemption status are persisted as encrypted source
    metadata on the real observation envelope. No undeclared registry casilla is
    fabricated for the threshold amount.
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=filing_year,
        period="0A",
        casilla_values={
            _DECL_TIPO_DECLARACION_CASILLA: Decimal("2"),
            _DECL_EJERCICIO_CASILLA: Decimal(str(filing_year)),
        },
        # The question here is an APPLICABILITY fact -- whether the IAE
        # exemption threshold is crossed, and the declaration-context casillas
        # that record it. Modelo 840 declares exactly that rung and no more, so
        # asking for filing (this helper's default) demands an authority this
        # work never exercises and the registry is right to withhold.
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )


def test_below_threshold_context_persists_exempt_assessment_metadata(tmp_path: Path) -> None:
    """Year-N 840 context stores an art.82 exempt INCN assessment."""
    obs = _threshold_context_observation(filing_year=_YEAR_N)
    assessment = _threshold_assessment(
        filing_year=_YEAR_N,
        cifra_negocios_eur=_EXEMPT_CIFRA_NEGOCIOS_EUR,
    )

    assert assessment.threshold_eur == _LEGAL_THRESHOLD_EUR
    assert assessment.status is Modelo840IaeExemptionStatus.EXEMPT
    assert assessment.is_exempt is True

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                obs,
                source_kind="app_filing",
                captured_at=_CLOCK_N,
                source_metadata=_threshold_source_metadata(assessment),
            )
        )
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")

        assert loaded is not None, f"year-N observation not found for ({_MODELO!r}, {_YEAR_N}, '0A') after save"
        assert loaded.observation == obs, "840 year-N observation did not survive the encrypted-SQL roundtrip"
        assert loaded.source_kind == "app_filing"
        assert loaded.captured_at == _CLOCK_N
        assert loaded.source_metadata == _threshold_source_metadata(assessment)


def test_at_threshold_context_persists_not_exempt_assessment_metadata(tmp_path: Path) -> None:
    """Year-N+2 840 context stores a non-exempt INCN assessment at the strict threshold."""
    obs = _threshold_context_observation(filing_year=_YEAR_N_PLUS_2)
    assessment = _threshold_assessment(
        filing_year=_YEAR_N_PLUS_2,
        cifra_negocios_eur=_NOT_EXEMPT_CIFRA_NEGOCIOS_EUR,
    )

    assert assessment.threshold_eur == _LEGAL_THRESHOLD_EUR
    assert assessment.status is Modelo840IaeExemptionStatus.NOT_EXEMPT
    assert assessment.is_exempt is False

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                obs,
                source_kind="app_filing",
                captured_at=_CLOCK_N_PLUS_2,
                source_metadata=_threshold_source_metadata(assessment),
            )
        )
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_2, period="0A")

        assert loaded is not None
        assert loaded.observation == obs
        assert loaded.source_kind == "app_filing"
        assert loaded.captured_at == _CLOCK_N_PLUS_2
        assert loaded.source_metadata == _threshold_source_metadata(assessment)


def test_exemption_assessments_are_independent_across_annual_contexts(tmp_path: Path) -> None:
    """The art.82 INCN exemption is assessed per annual context without value bleed."""
    obs_n = _threshold_context_observation(filing_year=_YEAR_N)
    obs_n2 = _threshold_context_observation(filing_year=_YEAR_N_PLUS_2)
    assessment_n = _threshold_assessment(
        filing_year=_YEAR_N,
        cifra_negocios_eur=_EXEMPT_CIFRA_NEGOCIOS_EUR,
    )
    assessment_n2 = _threshold_assessment(
        filing_year=_YEAR_N_PLUS_2,
        cifra_negocios_eur=_NOT_EXEMPT_CIFRA_NEGOCIOS_EUR,
    )

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                obs_n,
                source_kind="app_filing",
                captured_at=_CLOCK_N,
                source_metadata=_threshold_source_metadata(assessment_n),
            )
        )
        repo.save(
            repo.prepare_observation_envelope(
                obs_n2,
                source_kind="app_filing",
                captured_at=_CLOCK_N_PLUS_2,
                source_metadata=_threshold_source_metadata(assessment_n2),
            )
        )
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")
        loaded_n2 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_2, period="0A")

        assert loaded_n is not None
        assert loaded_n2 is not None
        assert loaded_n.observation == obs_n
        assert loaded_n2.observation == obs_n2

        assert loaded_n.source_metadata[_METADATA_CIFRA_NEGOCIOS_KEY] == str(_EXEMPT_CIFRA_NEGOCIOS_EUR)
        assert loaded_n.source_metadata[_METADATA_STATUS_KEY] == Modelo840IaeExemptionStatus.EXEMPT.value
        assert loaded_n2.source_metadata[_METADATA_CIFRA_NEGOCIOS_KEY] == str(_NOT_EXEMPT_CIFRA_NEGOCIOS_EUR)
        assert loaded_n2.source_metadata[_METADATA_STATUS_KEY] == Modelo840IaeExemptionStatus.NOT_EXEMPT.value

        ej_n = loaded_n.observation.casilla_values.get(_DECL_EJERCICIO_CASILLA)
        ej_n2 = loaded_n2.observation.casilla_values.get(_DECL_EJERCICIO_CASILLA)
        assert ej_n == Decimal(str(_YEAR_N)), f"ejercicio should be {_YEAR_N}; got {ej_n}"
        assert ej_n2 == Decimal(str(_YEAR_N_PLUS_2)), f"ejercicio should be {_YEAR_N_PLUS_2}; got {ej_n2}"

        assert loaded_n.captured_at == _CLOCK_N
        assert loaded_n2.captured_at == _CLOCK_N_PLUS_2


def test_anti_tautology_proof_missing_turnover_metadata_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: omitting INCN metadata is distinguishable after reload."""
    obs_n = _threshold_context_observation(filing_year=_YEAR_N)
    assessment_n = _threshold_assessment(
        filing_year=_YEAR_N,
        cifra_negocios_eur=_EXEMPT_CIFRA_NEGOCIOS_EUR,
    )
    full_metadata = _threshold_source_metadata(assessment_n)
    metadata_without_incn = dict(full_metadata)
    metadata_without_incn.pop(_METADATA_CIFRA_NEGOCIOS_KEY)

    assert full_metadata != metadata_without_incn, "full and INCN-omitted metadata must be unequal"

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                obs_n,
                source_kind="app_filing",
                captured_at=_CLOCK_N,
                source_metadata=full_metadata,
            )
        )
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")

        assert loaded is not None
        assert loaded.source_metadata != metadata_without_incn, (
            "loaded metadata equals the INCN-omitted payload - the roundtrip silently dropped threshold evidence"
        )
        assert loaded.source_metadata == full_metadata


def test_enrollment_recorder_evidences_two_distinct_annual_contexts_and_matches_manifest(
    tmp_path: Path,
) -> None:
    """EnrollmentRecorder proves both art.82 threshold contexts and matches the manifest."""
    obs_n = _threshold_context_observation(filing_year=_YEAR_N)
    obs_n2 = _threshold_context_observation(filing_year=_YEAR_N_PLUS_2)
    assessment_n = _threshold_assessment(
        filing_year=_YEAR_N,
        cifra_negocios_eur=_EXEMPT_CIFRA_NEGOCIOS_EUR,
    )
    assessment_n2 = _threshold_assessment(
        filing_year=_YEAR_N_PLUS_2,
        cifra_negocios_eur=_NOT_EXEMPT_CIFRA_NEGOCIOS_EUR,
    )

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        # --- Year N: below threshold, exempt -----------------------------
        repo.save(
            repo.prepare_observation_envelope(
                obs_n,
                source_kind="app_filing",
                captured_at=_CLOCK_N,
                source_metadata=_threshold_source_metadata(assessment_n),
            )
        )
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")
        assert loaded_n is not None
        assert loaded_n.observation == obs_n
        assert loaded_n.source_metadata[_METADATA_STATUS_KEY] == Modelo840IaeExemptionStatus.EXEMPT.value
        _count_n = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N)

        # --- Year N+2: at threshold, not exempt --------------------------
        repo.save(
            repo.prepare_observation_envelope(
                obs_n2,
                source_kind="app_filing",
                captured_at=_CLOCK_N_PLUS_2,
                source_metadata=_threshold_source_metadata(assessment_n2),
            )
        )
        loaded_n2 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_2, period="0A")
        assert loaded_n2 is not None
        assert loaded_n2.observation == obs_n2
        assert loaded_n2.source_metadata[_METADATA_STATUS_KEY] == Modelo840IaeExemptionStatus.NOT_EXEMPT.value
        _count_n2 = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N_PLUS_2)

    # --- Enrollment recording (outside the profile context) -------------
    recorder = EnrollmentRecorder(_MODELO)
    recorder.record_context_year(
        filing_year=_YEAR_N,
        context_label=_CONTEXT_LABEL,
        persisted_observation_count=(_count_n),
    )
    recorder.record_context_year(
        filing_year=_YEAR_N_PLUS_2,
        context_label=_CONTEXT_LABEL,
        persisted_observation_count=(_count_n2),
    )

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_2), (
        f"expected distinct renta years {(_YEAR_N, _YEAR_N_PLUS_2)!r}; got {evidence.distinct_renta_years!r}"
    )

    assert_enrollment_matches_manifest(evidence)
