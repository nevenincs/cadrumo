"""One filed Modelo 303 period projects both its rows into one encrypted store.

A locally filed M303 writes two rows describing the same event: the cross-period
carry observation, and the IVA compensation history state. Their readers each
resolve a repository through the active bucket independently, so the pair is
only coherent when both rows live in the same encrypted database. Split across
two, the carry row stays discoverable while the history lookup returns ``None``
-- and nothing reports the divergence.

These tests use real adapters throughout: two genuinely separate encrypted
SQLite profiles, the production repositories, and the production serializers.
Nothing is stubbed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import CasillaId, Modelo, Period, ResultDisposition, validated_casilla_id
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.iva_compensation.filed_derivation import M303_COMPENSATION_RESULTADO_CASILLA
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository, IvaCompensationHistoryRepository
from .._action_errors import ModeloLocalObservationError
from .._filed_revision_observation import persist_filed_revision_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_A = "3aa00000-0000-4000-8000-0000000000aa"
_BUCKET_B = "3bb00000-0000-4000-8000-0000000000bb"
_TAX_ID = "X1234567L"
_CAPTURED_AT = datetime(2026, 4, 15, 12, 0, 0, tzinfo=UTC)
_FILING_RECORD_ID = "filing-record-split-context"

_DISPONIBLE_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-disponible-fin-periodo",
    surface="test casilla id",
)


def _work_unit(bucket_id: str) -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=Modelo.M303.value,
            filing_year=2026,
            period=period,
            revision_id="2026-y-siguientes",
        ),
        bucket_id=bucket_id,
        name="303-2026-1T",
        modelo=Modelo.M303.value,
        filing_year=2026,
        period=period,
        revision_id="2026-y-siguientes",
        created_at=_CAPTURED_AT,
        updated_at=_CAPTURED_AT,
    )


def _revision(work_unit: WorkUnit) -> CalculationRevision:
    casilla_values = {
        _DISPONIBLE_CASILLA: Decimal("125.00"),
        M303_COMPENSATION_RESULTADO_CASILLA: Decimal("-125.00"),
    }
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values=casilla_values,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        casilla_values=casilla_values,
        observations=(
            CasillaObservation(
                casilla_id=_DISPONIBLE_CASILLA,
                value=Decimal("125.00"),
                legal_refs=("ley-37-1992:art-99",),
                source_refs=("aeat-manual-iva",),
            ),
            CasillaObservation(
                casilla_id=M303_COMPENSATION_RESULTADO_CASILLA,
                value=Decimal("-125.00"),
                legal_refs=("ley-37-1992:art-99",),
                source_refs=("aeat-manual-iva",),
            ),
        ),
        created_at=_CAPTURED_AT,
        updated_at=_CAPTURED_AT,
        verified_at=_CAPTURED_AT,
        verified_by="operator",
        filed_at=_CAPTURED_AT,
        filed_by="operator",
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _persist(work_unit: WorkUnit, *, repository, history_repository=None) -> str:
    return persist_filed_revision_observation(
        revision=_revision(work_unit),
        work_unit=work_unit,
        repository=repository,
        captured_at=_CAPTURED_AT,
        result_disposition=ResultDisposition.COMPENSACION,
        taxpayer_nif=_TAX_ID,
        filing_record_id=_FILING_RECORD_ID,
        iva_compensation_history_repository=history_repository,
    )


def test_history_defaults_into_the_observation_repository_store(tmp_path: Path) -> None:
    """With no override, both rows land in the observation repository's own store.

    The default previously resolved the ACTIVE bucket while the observation
    repository was whatever the caller threaded in, so the two could diverge
    without any override at all.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_A) as profile:
        observations = CalculationObservationRepository(objects=profile.repository)
        work_unit = _work_unit(profile.bucket_id)

        _persist(work_unit, repository=observations)

        history = IvaCompensationHistoryRepository(objects=profile.repository)
        stored = tuple(history.iter_records())

    assert len(stored) == 1
    assert stored[0].taxpayer_nif == _TAX_ID


def test_foreign_history_repository_is_refused_before_either_row_lands(
    tmp_path: Path,
) -> None:
    """A history repository on another database refuses, leaving no carry row.

    The split the finding names: the calculation row would be discoverable in
    the canonical bucket while the history row existed only in the injected
    database. The refusal must precede the observation write, so a rejected
    pairing cannot leave the carry half behind.
    """
    with isolated_runtime_profile(tmp_path=tmp_path / "a", bucket_id=_BUCKET_A) as profile_a:
        observations = CalculationObservationRepository(objects=profile_a.repository)
        work_unit = _work_unit(profile_a.bucket_id)

        with isolated_runtime_profile(tmp_path=tmp_path / "b", bucket_id=_BUCKET_B) as profile_b:
            foreign_history = IvaCompensationHistoryRepository(objects=profile_b.repository)
            assert (
                foreign_history.secure_object_repository.engine.url != observations.secure_object_repository.engine.url
            )

            with pytest.raises(ModeloLocalObservationError) as exc_info:
                _persist(work_unit, repository=observations, history_repository=foreign_history)

            assert tuple(foreign_history.iter_records()) == ()

        assert exc_info.value.context is not None
        assert exc_info.value.context["history_backend"] != exc_info.value.context["observation_backend"]
        assert tuple(CalculationObservationRepository(objects=profile_a.repository).iter_records()) == ()


def test_same_backend_history_override_is_honoured(tmp_path: Path) -> None:
    """A distinct repository object over the same database is still accepted.

    The guard compares storage context, not object identity: the filing path and
    its tests legitimately construct a second repository instance over the one
    encrypted store, and refusing that would break the real caller.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_A) as profile:
        observations = CalculationObservationRepository(objects=profile.repository)
        sibling_history = IvaCompensationHistoryRepository(objects=profile.repository)
        work_unit = _work_unit(profile.bucket_id)

        _persist(work_unit, repository=observations, history_repository=sibling_history)

        stored = tuple(IvaCompensationHistoryRepository(objects=profile.repository).iter_records())
        carried = tuple(observations.iter_records())

    assert len(stored) == 1
    assert len(carried) == 1
