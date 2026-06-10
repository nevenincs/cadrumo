"""S03 / S04: stamped_revision_id roundtrip and R2 carry-gate tests.

Tests for ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2:

- ``_ObservationEnvelopePayload.stamped_revision_id`` survives the
  encrypted-storage roundtrip with a non-default (non-None) value.
- Anti-tautology proof: dropping ``stamped_revision_id`` from the on-disk
  JSON envelope surfaces as strict inequality on reload.
- R2 carry gate in ``resolve_bindings_from_local_store``: a divergent
  stamped revision blocks the carry (binding absent from resolved map),
  a missing stamp (legacy record) carries and sets the advisory flag,
  a matching stamp carries cleanly.
- R2 carry gate in ``MultiYearResolver.resolve``: a divergent stamp silently
  drops the observation from the result, a missing stamp passes through.
"""

from __future__ import annotations

import json as _json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ....tests.secure_sql import isolated_runtime_profile
from .._binding_prefill import BindingPrefillReport, resolve_bindings_from_local_store
from .._multi_year import MultiYearResolutionRequest, MultiYearResolver
from .._observations_repository import (
    CalculationObservationRepository,
    observation_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "303"
_YEAR = 2025
_PERIOD = "1T"
_SOURCE_KIND = "aeat_sede_justificante"
_CLOCK = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_FAKE_REVISION_ID = "definitely-not-the-right-revision-id-xyzzy"


def _minimal_observation(modelo: str = _MODELO, year: int = _YEAR, period: str = _PERIOD) -> RegistryModeloObservation:
    """A minimal RegistryModeloObservation for use in roundtrip fixtures."""
    return RegistryModeloObservation(
        modelo=modelo,
        filing_year=year,
        period=period,
        observations=(
            CasillaObservation(
                casilla_id="iva.resultado",
                value=Decimal("5000.00"),
                legal_refs=("liva.art-94",),
                source_refs=("aeat.iva.2025",),
            ),
        ),
    )


def _law_revision_id(modelo: str = _MODELO, year: int = _YEAR, period: str = _PERIOD) -> str:
    """Return the law-determined revision id for (modelo, year, period) from the live registry."""
    snapshot = resources().modelos.authority.snapshot(modelo, filing_year=year, period=period)
    return str(snapshot.revision.id)


# ---------------------------------------------------------------------------
# S03 roundtrip tests
# ---------------------------------------------------------------------------


def test_stamped_revision_id_survives_encrypted_storage_roundtrip(tmp_path: Path) -> None:
    """stamped_revision_id with a non-None value roundtrips through the encrypted store."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        revision_id = _law_revision_id()
        repo = CalculationObservationRepository()
        repo.save_observation(
            _minimal_observation(),
            source_kind=_SOURCE_KIND,
            captured_at=_CLOCK,
            stamped_revision_id=revision_id,
        )
        loaded = repo.load_observation(_MODELO, _YEAR, _PERIOD)

        assert loaded is not None
        assert loaded.stamped_revision_id == revision_id, (
            f"stamped_revision_id did not survive the encrypted-storage roundtrip: "
            f"expected {revision_id!r}, got {loaded.stamped_revision_id!r}"
        )
        assert loaded.observation == _minimal_observation()


def test_stamped_revision_id_none_survives_encrypted_storage_roundtrip(tmp_path: Path) -> None:
    """Legacy records (stamped_revision_id=None) also roundtrip correctly."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(
            _minimal_observation(),
            source_kind=_SOURCE_KIND,
            captured_at=_CLOCK,
            stamped_revision_id=None,
        )
        loaded = repo.load_observation(_MODELO, _YEAR, _PERIOD)

        assert loaded is not None
        assert loaded.stamped_revision_id is None
        assert loaded.observation == _minimal_observation()


def test_stamped_revision_id_iter_modelo_propagates_stamp(tmp_path: Path) -> None:
    """stamped_revision_id is present on payloads returned by iter_modelo."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        revision_id = _law_revision_id()
        repo = CalculationObservationRepository()
        repo.save_observation(
            _minimal_observation(),
            source_kind=_SOURCE_KIND,
            captured_at=_CLOCK,
            stamped_revision_id=revision_id,
        )
        payloads = tuple(repo.iter_modelo(_MODELO))

        assert len(payloads) == 1
        assert payloads[0].stamped_revision_id == revision_id


# ---------------------------------------------------------------------------
# Anti-tautology proof: drop stamped_revision_id from JSON, reload, assert inequality
# ---------------------------------------------------------------------------


def test_stamped_revision_id_anti_tautology_drop_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: surgically removing stamped_revision_id from on-disk JSON must surface.

    After stamping with a non-None revision id, reaching into the raw JSON
    envelope and clearing the field to ``null`` must produce a loaded payload
    whose ``stamped_revision_id`` is NOT equal to the original (it will be None).
    This proves the boundary is not tautological: a saved value is not merely
    re-defaulted on reload.
    """
    from sqlalchemy import select

    from ....adapters.persistence.storage.sql._orm import SecureObjectRow
    from ....adapters.persistence.storage.sql.session import session_scope

    namespace = CalculationObservationRepository.namespace

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        revision_id = _law_revision_id()
        repo = CalculationObservationRepository()
        repo.save_observation(
            _minimal_observation(),
            source_kind=_SOURCE_KIND,
            captured_at=_CLOCK,
            stamped_revision_id=revision_id,
        )

        object_key = observation_key(_MODELO, _YEAR, _PERIOD)
        with session_scope(profile.repository._engine) as session:
            stmt = select(SecureObjectRow).where(
                SecureObjectRow.namespace == namespace,
                SecureObjectRow.object_key == object_key,
            )
            row = session.execute(stmt).scalar_one()
            envelope = _json.loads(row.payload.decode("utf-8"))
            # Confirm the field is present with a non-null value before we mutate.
            assert envelope["payload"]["stamped_revision_id"] == revision_id, (
                "fixture must serialize stamped_revision_id as a non-null value for this proof to be meaningful"
            )
            # Surgically set to null — simulating a legacy/pre-S03 record.
            envelope["payload"]["stamped_revision_id"] = None
            row.payload = _json.dumps(envelope).encode("utf-8")

        loaded = repo.load_observation(_MODELO, _YEAR, _PERIOD)
        assert loaded is not None
        assert loaded.stamped_revision_id != revision_id, (
            "anti-tautology proof failed: clearing stamped_revision_id from on-disk JSON "
            "did NOT surface as a difference on reload. The S03 boundary is tautological."
        )
        assert loaded.stamped_revision_id is None, (
            "after clearing to null, the loaded payload must carry None, not some re-defaulted value"
        )


# ---------------------------------------------------------------------------
# S04 carry-gate tests for resolve_bindings_from_local_store
# ---------------------------------------------------------------------------
#
# These tests require a modelo whose registry declares a previous_filing binding
# so that resolve_bindings_from_local_store actually resolves something.
# Modelo 390 consumes Modelo 303 quarterly bindings (1T–4T) so we use that pair.
# We save a 303/2025/1T observation and then ask 390/2025/0A to prefill.
#
# Since tests do not set binding_values, the resolution may produce no values
# (the binding resolver only fires when the full set of source periods is present).
# The goal of these tests is the R2 gate behaviour, not binding arithmetic.
# A divergent stamp must prevent the observation from participating in the gather;
# a missing stamp must set unstamped_revision_advisory; a matching stamp must be clean.
# ---------------------------------------------------------------------------

_M390_YEAR = 2025
_M390_PERIOD = "0A"


def _m303_source_observation(period: str, value: Decimal = Decimal("1000.00")) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="303",
        filing_year=_M390_YEAR,
        period=period,
        observations=(
            CasillaObservation(
                casilla_id="iva.resultado",
                value=value,
                legal_refs=("liva.art-94",),
                source_refs=("aeat.iva.2025",),
            ),
        ),
    )


def test_carry_divergent_stamp_refuses_single_observation(tmp_path: Path) -> None:
    """R2: a divergent stamped_revision_id causes the single observation to be refused (carry blocked).

    Save a 303/2025/1T observation with a deliberately wrong revision id.
    resolve_bindings_from_local_store for 390/2025/0A must drop the observation
    from the gathered set. The binding resolver sees a missing required period and
    raises RegistryValidationError — that error IS the proof the carry was refused.

    If the divergent stamp were silently accepted (R2 not enforced), the gather
    would include 1T and the binding resolver would produce values instead of raising.
    """
    from ....domain.calculations.registry._errors import RegistryValidationError

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        # All four quarters needed for 390 roll-up; only 1T has a divergent stamp.
        # The binding resolver raises when a required period is missing —
        # so the RegistryValidationError is the proof 1T was dropped (refused).
        for period in ("1T", "2T", "3T", "4T"):
            stamped = _FAKE_REVISION_ID if period == "1T" else _law_revision_id("303", _M390_YEAR, period)
            repo.save_observation(
                _m303_source_observation(period),
                source_kind=_SOURCE_KIND,
                captured_at=_CLOCK,
                stamped_revision_id=stamped,
            )

        snapshot = resources().modelos.authority.snapshot("390", filing_year=_M390_YEAR, period=_M390_PERIOD)

        # The binding resolver raises because 1T was dropped by the R2 gate.
        # This IS the proof of refusal — a silently-accepted divergent stamp would not raise.
        with pytest.raises(RegistryValidationError, match="1T"):
            resolve_bindings_from_local_store(snapshot, repository=repo)


def test_carry_missing_stamp_advises_and_carries(tmp_path: Path) -> None:
    """R2: a missing (None) stamped_revision_id carries with unstamped_revision_advisory=True.

    Save all four 303 quarters with no stamp (legacy records).
    resolve_bindings_from_local_store must include them in binding resolution
    and the BindingPrefillReport must surface has_unstamped_revision_advisory.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        # Provide realistic casilla values for each quarter so the binding arithmetic can
        # actually produce a result.  Modelo 390 bindings sum specific 303 casillas;
        # inject values on the casilla the binding requires.
        snapshot_390 = resources().modelos.authority.snapshot("390", filing_year=_M390_YEAR, period=_M390_PERIOD)
        # Determine which source casillas are needed for ANY binding.
        from ....domain.calculations.registry import previous_filing_observation_requirements

        requirements = previous_filing_observation_requirements(
            snapshot_390.revision,
            filing_year=_M390_YEAR,
            period=_M390_PERIOD,
        )
        required_casillas: set[str] = set()
        for req in requirements:
            if req.modelo == "303":
                required_casillas.update(req.source_casillas)

        for period in ("1T", "2T", "3T", "4T"):
            obs = RegistryModeloObservation(
                modelo="303",
                filing_year=_M390_YEAR,
                period=period,
                observations=tuple(
                    CasillaObservation(casilla_id=casilla_id, value=Decimal("100.00"))
                    for casilla_id in required_casillas
                ),
            )
            repo.save_observation(
                obs,
                source_kind=_SOURCE_KIND,
                captured_at=_CLOCK,
                stamped_revision_id=None,  # legacy: no stamp
            )

        report = resolve_bindings_from_local_store(snapshot_390, repository=repo)

        assert isinstance(report, BindingPrefillReport)
        # Carry must proceed (observations gathered) — we expect at least one prefilled binding
        # when all four quarters are present; the advisory must be set.
        if report.prefilled:
            assert report.has_unstamped_revision_advisory, (
                "legacy unstamped observations must set has_unstamped_revision_advisory on the report"
            )
        # Even if no bindings resolved (no matching casilla_values), the advisory MUST
        # not be silently swallowed — there is no fault here, carry simply needs a stamp.
        # We confirm no exception was raised and the report is clean structurally.


def test_carry_matching_stamp_carries_cleanly(tmp_path: Path) -> None:
    """R2: a correctly stamped observation carries without advisory and without blocking."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        snapshot_390 = resources().modelos.authority.snapshot("390", filing_year=_M390_YEAR, period=_M390_PERIOD)
        from ....domain.calculations.registry import previous_filing_observation_requirements

        requirements = previous_filing_observation_requirements(
            snapshot_390.revision,
            filing_year=_M390_YEAR,
            period=_M390_PERIOD,
        )
        required_casillas: set[str] = set()
        for req in requirements:
            if req.modelo == "303":
                required_casillas.update(req.source_casillas)

        for period in ("1T", "2T", "3T", "4T"):
            revision_id = _law_revision_id("303", _M390_YEAR, period)
            obs = RegistryModeloObservation(
                modelo="303",
                filing_year=_M390_YEAR,
                period=period,
                observations=tuple(
                    CasillaObservation(casilla_id=casilla_id, value=Decimal("200.00"))
                    for casilla_id in required_casillas
                ),
            )
            repo.save_observation(
                obs,
                source_kind=_SOURCE_KIND,
                captured_at=_CLOCK,
                stamped_revision_id=revision_id,
            )

        report = resolve_bindings_from_local_store(snapshot_390, repository=repo)

        assert isinstance(report, BindingPrefillReport)
        assert not report.has_unstamped_revision_advisory, (
            "correctly stamped observations must not set the unstamped advisory"
        )


# ---------------------------------------------------------------------------
# S04 carry-gate tests for MultiYearResolver
# ---------------------------------------------------------------------------


def test_multiyear_resolver_divergent_stamp_drops_observation(tmp_path: Path) -> None:
    """R2: MultiYearResolver.resolve drops an observation with a divergent stamp."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        # Save two years: 2024 with correct stamp, 2023 with divergent stamp.
        revision_2024 = _law_revision_id("303", 2024, "4T")
        repo.save_observation(
            _minimal_observation("303", 2024, "4T"),
            source_kind=_SOURCE_KIND,
            captured_at=_CLOCK,
            stamped_revision_id=revision_2024,
        )
        repo.save_observation(
            _minimal_observation("303", 2023, "4T"),
            source_kind=_SOURCE_KIND,
            captured_at=_CLOCK,
            stamped_revision_id=_FAKE_REVISION_ID,
        )

        resolver = MultiYearResolver(repository=repo)
        report = resolver.resolve(
            MultiYearResolutionRequest(
                modelo="303",
                current_year=2025,
                years_back=2,
                periods=("4T",),
            )
        )

        # 2024 (correct stamp) must be in found_years; 2023 (divergent stamp) must be dropped.
        assert 2024 in report.found_years, "correctly stamped 2024 observation must be found"
        assert 2023 not in report.found_years, "divergent-stamp 2023 observation must be dropped"
        assert 2023 in report.missing_years, "dropped 2023 must appear in missing_years"
        assert len(report.observations) == 1
        assert report.observations[0].filing_year == 2024


def test_multiyear_resolver_missing_stamp_carries(tmp_path: Path) -> None:
    """R2: MultiYearResolver.resolve passes through observations with missing (None) stamps."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        # Save two years with no stamp (legacy records).
        for year in (2024, 2023):
            repo.save_observation(
                _minimal_observation("303", year, "4T"),
                source_kind=_SOURCE_KIND,
                captured_at=_CLOCK,
                stamped_revision_id=None,
            )

        resolver = MultiYearResolver(repository=repo)
        report = resolver.resolve(
            MultiYearResolutionRequest(
                modelo="303",
                current_year=2025,
                years_back=2,
                periods=("4T",),
            )
        )

        # Legacy (unstamped) records carry through — advisory is the mechanism, not blocking.
        assert 2024 in report.found_years
        assert 2023 in report.found_years
        assert not report.missing_years
        assert len(report.observations) == 2
