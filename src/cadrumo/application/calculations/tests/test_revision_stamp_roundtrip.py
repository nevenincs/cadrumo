"""Stamped_revision_id roundtrip and revision-stamp carry-gate tests.

- :class:`ObservationEnvelopePayload` preserves the required
  ``stamped_revision_id`` through a secure-repository round trip.
- ``save_observation`` derives the law-determined stamp when callers omit it.
- Anti-tautology proof: deleting ``stamped_revision_id`` from the on-disk JSON
  envelope refuses on reload.
- Carry gate in ``resolve_bindings_from_local_store``: a divergent or
  unreconfirmable stamped revision blocks the carry (binding absent from
  resolved map), and a matching stamp carries cleanly.
  Subject: Modelo 303/2025/2T whose single ``previous_filing`` binding
  ``modelo-303-compensacion-pendiente-anteriores`` reads from M303/2025/1T.
  M390's five M303-sourced bindings migrated to ``relation_prefill``
  via the relation path; the stamp R2 gate tests now use the M303 self-carry
  (prior quarter compensacion carry) as subject instead.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from .._binding_prefill import BindingPrefillReport, resolve_bindings_from_local_store
from ..observations_repository import (
    CalculationObservationRepository,
    observation_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "303"
_YEAR = 2025
_PERIOD = "1T"
_SOURCE_KIND = "aeat_sede_justificante"
_CLOCK = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_DIVERGENT_REVISION_ID = "definitely-not-the-right-revision-id-xyzzy"


_M303_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_M303_CARRY_SOURCE_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")


def _filing_period(year: int = _YEAR, period: str = _PERIOD) -> Period:
    return Period.from_year_and_code(year, period)


def _minimal_observation(modelo: str = _MODELO, year: int = _YEAR, period: str = _PERIOD) -> RegistryModeloObservation:
    """A minimal RegistryModeloObservation for use in roundtrip fixtures."""
    return RegistryModeloObservation(
        modelo=modelo,
        filing_year=year,
        period=period,
        observations=(
            CasillaObservation(
                casilla_id=_M303_RESULTADO_CASILLA,
                value=Decimal("5000.00"),
                legal_refs=("ley-37-1992:art-94",),
                source_refs=("aeat-iva-2025",),
            ),
        ),
    )


def _law_revision_id(modelo: str = _MODELO, year: int = _YEAR, period: str = _PERIOD) -> str:
    """Return the law-determined revision id for (modelo, year, period) from the live registry."""
    snapshot = bundled_authority().snapshot(modelo, filing_year=year, period=period)
    return str(snapshot.revision.id)


# ---------------------------------------------------------------------------
# Roundtrip tests for stamped_revision_id
# ---------------------------------------------------------------------------


def test_stamped_revision_id_survives_encrypted_storage_roundtrip(tmp_path: Path) -> None:
    """The required stamped_revision_id roundtrips through the encrypted store."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        revision_id = _law_revision_id()
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                _minimal_observation(),
                source_kind=_SOURCE_KIND,
                captured_at=_CLOCK,
                stamped_revision_id=revision_id,
            )
        )
        loaded = repo.load_observation(_MODELO, _filing_period())

        assert loaded is not None
        assert loaded.stamped_revision_id == revision_id, (
            f"stamped_revision_id did not survive the encrypted-storage roundtrip: "
            f"expected {revision_id!r}, got {loaded.stamped_revision_id!r}"
        )
        assert loaded.observation == _minimal_observation()


def test_save_observation_derives_stamped_revision_id(tmp_path: Path) -> None:
    """Omitting stamped_revision_id on save persists the law-determined revision id."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        expected = _law_revision_id()
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                _minimal_observation(),
                source_kind=_SOURCE_KIND,
                captured_at=_CLOCK,
            )
        )
        loaded = repo.load_observation(_MODELO, _filing_period())

        assert loaded is not None
        assert loaded.stamped_revision_id == expected
        assert loaded.observation == _minimal_observation()


def test_stamped_revision_id_iter_modelo_propagates_stamp(tmp_path: Path) -> None:
    """stamped_revision_id is present on payloads returned by iter_modelo."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        revision_id = _law_revision_id()
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                _minimal_observation(),
                source_kind=_SOURCE_KIND,
                captured_at=_CLOCK,
                stamped_revision_id=revision_id,
            )
        )
        payloads = tuple(repo.iter_modelo(_MODELO))

        assert len(payloads) == 1
        assert payloads[0].stamped_revision_id == revision_id


# ---------------------------------------------------------------------------
# Anti-tautology proof: drop stamped_revision_id from JSON and refuse reload
# ---------------------------------------------------------------------------


def test_stamped_revision_id_anti_tautology_missing_refuses_load(tmp_path: Path) -> None:
    """Anti-tautology: deleting stamped_revision_id from on-disk JSON must refuse.

    After stamping with a non-empty revision id, reaching into the raw JSON
    envelope and deleting the field must fail strict payload
    validation. This proves the boundary is not tautological: a saved value is
    not re-derived on reload.
    """
    from sqlalchemy import select

    from ....adapters.persistence.storage.sql import SecureObjectRow
    from ....adapters.persistence.storage.sql.engine import get_engine

    namespace = CalculationObservationRepository.namespace

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        revision_id = _law_revision_id()
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                _minimal_observation(),
                source_kind=_SOURCE_KIND,
                captured_at=_CLOCK,
                stamped_revision_id=revision_id,
            )
        )

        object_key = observation_key(_MODELO, _filing_period())
        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == namespace,
            SecureObjectRow.object_key == object_key,
        )

        def mutate(envelope):
            # Confirm the field is present with a non-null value before we mutate.
            assert envelope["payload"]["stamped_revision_id"] == revision_id, (
                "fixture must serialize stamped_revision_id as a non-null value for this proof to be meaningful"
            )
            del envelope["payload"]["stamped_revision_id"]

        mutate_encrypted_secure_object_json(
            get_engine(profile.settings),
            row_statement=stmt,
            mutate=mutate,
        )

        with pytest.raises(ValidationError):
            repo.load_observation(_MODELO, _filing_period())


# ---------------------------------------------------------------------------
# Carry-gate tests for resolve_bindings_from_local_store
# ---------------------------------------------------------------------------
#
# These tests require a modelo whose registry declares a previous_filing binding
# so that resolve_bindings_from_local_store actually resolves something.
#
# Subject: Modelo 303/2025/2T whose single ``previous_filing`` binding
# ``modelo-303-compensacion-pendiente-anteriores`` reads
# ``iva.compensacion-disponible-fin-periodo`` from M303/2025/1T
# (source_period_offset_from_target = -1).
#
# NOTE: Modelo 390's ordinary M303 annual-total bindings migrated from
# ``previous_filing`` to ``relation_prefill``; its compensation boxes are now
# resolved by ``iva_compensation_annual_partition``. resolve_bindings_from_local_store
# for M390/0A returns an empty BindingPrefillReport; it can no longer be used as
# the R2 gate subject. These three tests were repurposed to the M303 self-carry
# (quarterly compensacion carry) instead, which retains a direct-selector
# ``previous_filing`` binding.
#
# R2 carry gate behaviors under test:
# - divergent stamp on 1T → 1T observation refused by the gate;
#   _gather_observations returns () → early return with empty BindingPrefillReport.
#   Proof: binding absent from report.binding_values.
# - matching stamp on 1T → carry proceeds cleanly.
# ---------------------------------------------------------------------------

_M303_CARRY_YEAR = 2025
_M303_CARRY_TARGET_PERIOD = "2T"
_M303_CARRY_SOURCE_PERIOD = "1T"  # offset -1 from 2T
_M303_CARRY_BINDING_ID = "modelo-303-compensacion-pendiente-anteriores"


def _m303_carry_source_observation(value: Decimal = Decimal("500.00")) -> RegistryModeloObservation:
    """M303/2025/1T observation providing the compensacion carry casilla for the 2T binding."""
    return RegistryModeloObservation(
        modelo="303",
        filing_year=_M303_CARRY_YEAR,
        period=_M303_CARRY_SOURCE_PERIOD,
        observations=(
            CasillaObservation(
                casilla_id=_M303_CARRY_SOURCE_CASILLA,
                value=value,
                legal_refs=("ley-37-1992:art-99",),
                source_refs=("aeat-dr-303-2025",),
            ),
        ),
    )


def test_carry_divergent_stamp_refuses_single_observation(tmp_path: Path) -> None:
    """R2: a divergent stamped_revision_id causes the M303/1T observation to be refused (carry blocked).

    Subject: M303/2025/2T prefill; the single ``previous_filing`` binding
    ``modelo-303-compensacion-pendiente-anteriores`` reads M303/2025/1T.

    Save 303/2025/1T with a deliberately wrong revision id.
    resolve_bindings_from_local_store for 303/2025/2T must drop the observation
    from the gathered set via the R2 gate.  _gather_observations returns ()
    (all gathered observations were refused), triggering the early-return path
    in resolve_bindings_from_local_store that yields an empty BindingPrefillReport.

    Proof: the binding ``modelo-303-compensacion-pendiente-anteriores`` is ABSENT
    from report.binding_values.  If the divergent stamp were silently accepted,
    the binding would be resolved and present in the map.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                _m303_carry_source_observation(),
                source_kind=_SOURCE_KIND,
                captured_at=_CLOCK,
                stamped_revision_id=_DIVERGENT_REVISION_ID,  # divergent: wrong revision
            )
        )

        snapshot = bundled_authority().snapshot(
            "303",
            filing_year=_M303_CARRY_YEAR,
            period=_M303_CARRY_TARGET_PERIOD,
        )
        report = resolve_bindings_from_local_store(snapshot, repository=repo)

        assert isinstance(report, BindingPrefillReport)
        # The carry was refused: 1T was dropped by the R2 gate.
        # The binding must NOT appear in binding_values — its absence IS the refusal proof.
        assert _M303_CARRY_BINDING_ID not in report.binding_values, (
            f"R2 gate failure: divergent-stamp observation for M303/1T was not refused; "
            f"binding {_M303_CARRY_BINDING_ID!r} appeared in report.binding_values when it must be absent."
        )
        assert not report.prefilled, (
            "R2 gate failure: prefilled must be empty when all source observations were refused."
        )


def test_carry_matching_stamp_carries_cleanly(tmp_path: Path) -> None:
    """R2: a correctly stamped M303/1T observation carries without blocking.

    Subject: M303/2025/2T prefill; the single ``previous_filing`` binding
    ``modelo-303-compensacion-pendiente-anteriores`` reads M303/2025/1T.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        revision_id = _law_revision_id("303", _M303_CARRY_YEAR, _M303_CARRY_SOURCE_PERIOD)
        repo.save(
            repo.prepare_observation_envelope(
                _m303_carry_source_observation(),
                source_kind=_SOURCE_KIND,
                captured_at=_CLOCK,
                stamped_revision_id=revision_id,
            )
        )

        snapshot = bundled_authority().snapshot(
            "303",
            filing_year=_M303_CARRY_YEAR,
            period=_M303_CARRY_TARGET_PERIOD,
        )
        report = resolve_bindings_from_local_store(snapshot, repository=repo)

        assert isinstance(report, BindingPrefillReport)
        assert report.prefilled, "correctly stamped 1T observation must carry; the prefill must not be empty."
        assert _M303_CARRY_BINDING_ID in report.binding_values, (
            f"binding {_M303_CARRY_BINDING_ID!r} must be resolved from the correctly stamped 1T observation."
        )


# The R2 carry-gate coverage for ``MultiYearResolver`` was removed with the
# orphaned resolver itself; the shared live-path gate stays comprehensively
# covered by ``test_carry_gate_parity.py`` across the
# matching / divergent / indeterminate outcomes.
