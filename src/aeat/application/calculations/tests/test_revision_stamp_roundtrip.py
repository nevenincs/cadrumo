"""Stamped_revision_id roundtrip and R2 carry-gate tests.

Tests for the period-revision-resolution decision, Ruling 3 / R2:

- ``_ObservationEnvelopePayload.stamped_revision_id`` survives the
  encrypted-storage roundtrip with a non-default (non-None) value.
- Anti-tautology proof: dropping ``stamped_revision_id`` from the on-disk
  JSON envelope surfaces as strict inequality on reload.
- R2 carry gate in ``resolve_bindings_from_local_store``: a divergent
  stamped revision blocks the carry (binding absent from resolved map),
  a missing stamp (pre-stamp record) carries and sets the advisory flag,
  a matching stamp carries cleanly.
  Subject: Modelo 303/2025/2T whose single ``previous_filing`` binding
  ``modelo-303-compensacion-pendiente-anteriores`` reads from M303/2025/1T.
  M390's five M303-sourced bindings migrated to ``relation_prefill``
  via the relation path; the stamp R2 gate tests now use the M303 self-carry
  (prior quarter compensacion carry) as subject instead.
"""

from __future__ import annotations

import json as _json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaId,
    CasillaObservation,
    RegistryModeloObservation,
    validated_casilla_id,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._binding_prefill import BindingPrefillReport, resolve_bindings_from_local_store
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
_DIVERGENT_REVISION_ID = "definitely-not-the-right-revision-id-xyzzy"


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"revision stamp fixture casilla key {value!r} is not a CasillaId") from exc


_M303_RESULTADO_CASILLA: CasillaId = _casilla_id("iva.resultado")
_M303_CARRY_SOURCE_CASILLA: CasillaId = _casilla_id("iva.compensacion-disponible-fin-periodo")


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
# Roundtrip tests for stamped_revision_id
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
        loaded = repo.load_observation(_MODELO, _filing_period())

        assert loaded is not None
        assert loaded.stamped_revision_id == revision_id, (
            f"stamped_revision_id did not survive the encrypted-storage roundtrip: "
            f"expected {revision_id!r}, got {loaded.stamped_revision_id!r}"
        )
        assert loaded.observation == _minimal_observation()


def test_stamped_revision_id_none_survives_encrypted_storage_roundtrip(tmp_path: Path) -> None:
    """Unstamped records (stamped_revision_id=None) also roundtrip correctly."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(
            _minimal_observation(),
            source_kind=_SOURCE_KIND,
            captured_at=_CLOCK,
            stamped_revision_id=None,
        )
        loaded = repo.load_observation(_MODELO, _filing_period())

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

    from ....adapters.persistence.storage.crypto._encrypted_columns import (
        decrypt_secure_object_payload,
        encrypt_secure_object_payload,
        secure_object_payload_aad,
    )
    from ....adapters.persistence.storage.sql._orm import SecureObjectRow
    from ....adapters.persistence.storage.sql.engine import get_engine
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

        object_key = observation_key(_MODELO, _filing_period())
        with session_scope(get_engine(profile.settings)) as session:
            stmt = select(SecureObjectRow).where(
                SecureObjectRow.namespace == namespace,
                SecureObjectRow.object_key == object_key,
            )
            row = session.execute(stmt).scalar_one()
            _h3_aad = secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version)
            _h3_plain = decrypt_secure_object_payload(bytes(row.payload), associated_data=_h3_aad)
            envelope = _json.loads(_h3_plain.decode("utf-8"))
            # Confirm the field is present with a non-null value before we mutate.
            assert envelope["payload"]["stamped_revision_id"] == revision_id, (
                "fixture must serialize stamped_revision_id as a non-null value for this proof to be meaningful"
            )
            # Surgically set to null — simulating a pre-stamp record.
            envelope["payload"]["stamped_revision_id"] = None
            row.payload = encrypt_secure_object_payload(_json.dumps(envelope).encode("utf-8"), associated_data=_h3_aad)

        loaded = repo.load_observation(_MODELO, _filing_period())
        assert loaded is not None
        assert loaded.stamped_revision_id != revision_id, (
            "anti-tautology proof failed: clearing stamped_revision_id from on-disk JSON "
            "did NOT surface as a difference on reload. The S03 boundary is tautological."
        )
        assert loaded.stamped_revision_id is None, (
            "after clearing to null, the loaded payload must carry None, not some re-defaulted value"
        )


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
# NOTE: Modelo 390's five M303-sourced bindings (cuota-devengada-total,
# cuota-deducible-total, resultado-regimen-general, compensacion-ultimo-periodo,
# compensacion-generada-ejercicio-no-97) migrated from ``previous_filing`` to
# ``relation_prefill`` via the relation path.  resolve_bindings_from_local_store
# for M390/0A now returns an empty BindingPrefillReport; it can no longer be used
# as the R2 gate subject.  These three tests were repurposed to the M303 self-carry
# (quarterly compensacion carry) instead, which retains a direct-selector
# ``previous_filing`` binding.
#
# R2 carry gate behaviors under test:
# - divergent stamp on 1T → 1T observation refused by the gate;
#   _gather_observations returns () → early return with empty BindingPrefillReport.
#   Proof: binding absent from report.binding_values.
# - missing stamp (None) on 1T → carry proceeds with has_unstamped_revision_advisory.
# - matching stamp on 1T → carry proceeds cleanly without advisory.
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
        repo.save_observation(
            _m303_carry_source_observation(),
            source_kind=_SOURCE_KIND,
            captured_at=_CLOCK,
            stamped_revision_id=_DIVERGENT_REVISION_ID,  # divergent: wrong revision
        )

        snapshot = resources().modelos.authority.snapshot(
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


def test_carry_missing_stamp_advises_and_carries(tmp_path: Path) -> None:
    """R2: a missing (None) stamped_revision_id on M303/1T carries with unstamped_revision_advisory=True.

    Subject: M303/2025/2T prefill; the single ``previous_filing`` binding
    ``modelo-303-compensacion-pendiente-anteriores`` reads M303/2025/1T.

    Save 303/2025/1T with no stamp.
    resolve_bindings_from_local_store must include it in binding resolution
    and the BindingPrefillReport must surface has_unstamped_revision_advisory.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(
            _m303_carry_source_observation(),
            source_kind=_SOURCE_KIND,
            captured_at=_CLOCK,
            stamped_revision_id=None,  # intentionally unstamped
        )

        snapshot = resources().modelos.authority.snapshot(
            "303",
            filing_year=_M303_CARRY_YEAR,
            period=_M303_CARRY_TARGET_PERIOD,
        )
        report = resolve_bindings_from_local_store(snapshot, repository=repo)

        assert isinstance(report, BindingPrefillReport)
        # Carry must proceed (unstamped observation is not refused).
        assert report.prefilled, "missing-stamp observation must still carry; the prefill must not be empty."
        assert _M303_CARRY_BINDING_ID in report.binding_values, (
            f"binding {_M303_CARRY_BINDING_ID!r} must be resolved from the unstamped 1T observation."
        )
        assert report.has_unstamped_revision_advisory, (
            "unstamped observation must set has_unstamped_revision_advisory on the report."
        )


def test_carry_matching_stamp_carries_cleanly(tmp_path: Path) -> None:
    """R2: a correctly stamped M303/1T observation carries without advisory and without blocking.

    Subject: M303/2025/2T prefill; the single ``previous_filing`` binding
    ``modelo-303-compensacion-pendiente-anteriores`` reads M303/2025/1T.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        revision_id = _law_revision_id("303", _M303_CARRY_YEAR, _M303_CARRY_SOURCE_PERIOD)
        repo.save_observation(
            _m303_carry_source_observation(),
            source_kind=_SOURCE_KIND,
            captured_at=_CLOCK,
            stamped_revision_id=revision_id,
        )

        snapshot = resources().modelos.authority.snapshot(
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
        assert not report.has_unstamped_revision_advisory, (
            "correctly stamped observation must not set the unstamped advisory."
        )


# The R2 carry-gate coverage for ``MultiYearResolver`` was removed with the
# orphaned resolver itself; the live-path R2 gate (``_revision_prefill_divergence``)
# stays comprehensively covered by ``test_carry_gate_parity.py`` across the
# matching / divergent / missing / indeterminate outcomes.
