"""Carried-prior-definitive seed coverage over real filed observations.

See Also:
    :func:`~application.prorrata_register._seed.evaluate_carried_prior_definitiva_seed`
        Seed evaluator under test for happy-path, divergent-revision, and
        legacy-missing-stamp outcomes.
    :class:`~application.calculations.CalculationObservationRepository`
        Real encrypted observation repository that stores the prior Modelo 303
        settlement observation.
    :class:`~application.calculations.CrossPeriodCleanStateBlocker`
        Blocking vocabulary asserted for registry-revision divergence findings.
    :func:`~tests.registry_observations.registry_grounded_modelo_observation`
        Test helper that builds registry-grounded Modelo 303 observation
        payloads instead of mirroring calculation logic.
"""

from __future__ import annotations

import json as _json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from ....adapters.persistence.storage.crypto import (
    decrypt_secure_object_payload,
    encrypt_secure_object_payload,
    secure_object_payload_aad,
)
from ....adapters.persistence.storage.sql import SecureObjectRow
from ....adapters.persistence.storage.sql.engine import get_engine
from ....adapters.persistence.storage.sql.session import session_scope
from ....core import Modelo, ProrrataProvisionalProvenance
from ....core.resources import resources
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository, CrossPeriodCleanStateBlocker, observation_key_for_token
from .. import evaluate_carried_prior_definitiva_seed

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SOURCE_KIND = "aeat_sede_justificante"
_CLOCK = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_CURRENT_YEAR = 2026
_PRIOR_YEAR = 2025
_SETTLEMENT_PERIOD = "4T"
_DIVERGENT_REVISION_ID = "not-the-law-determined-m303-2025-4t-revision"

_PORCENTAJE_ID: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")


def _prior_revision_id(*, filing_year: int = _PRIOR_YEAR, period: str = _SETTLEMENT_PERIOD) -> str:
    snapshot = resources().modelos.authority.snapshot(Modelo.M303.value, filing_year=filing_year, period=period)
    return str(snapshot.revision.id)


def _save_prior_prorrata_observation(
    repo: CalculationObservationRepository,
    *,
    percentage: Decimal,
    stamped_revision_id: str,
) -> None:
    observation = registry_grounded_modelo_observation(
        modelo=Modelo.M303.value,
        filing_year=_PRIOR_YEAR,
        period=_SETTLEMENT_PERIOD,
        casilla_values={_PORCENTAJE_ID: percentage},
    )
    repo.save_observation(
        observation,
        source_kind=_SOURCE_KIND,
        captured_at=_CLOCK,
        stamped_revision_id=stamped_revision_id,
    )


def _remove_stamped_revision_id_from_saved_observation(profile: object) -> None:
    namespace = CalculationObservationRepository.namespace
    object_key = observation_key_for_token(Modelo.M303.value, _PRIOR_YEAR, _SETTLEMENT_PERIOD)

    with session_scope(get_engine(profile.settings)) as session:
        row = session.execute(
            select(SecureObjectRow).where(
                SecureObjectRow.namespace == namespace,
                SecureObjectRow.object_key == object_key,
            ),
        ).scalar_one()
        aad = secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version)
        plain = decrypt_secure_object_payload(bytes(row.payload), associated_data=aad)
        envelope = _json.loads(plain.decode("utf-8"))
        assert envelope["payload"]["stamped_revision_id"] == _prior_revision_id()
        del envelope["payload"]["stamped_revision_id"]
        row.payload = encrypt_secure_object_payload(_json.dumps(envelope).encode("utf-8"), associated_data=aad)


def test_seed_happy_path_uses_prior_settlement_observation(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository(objects=profile.repository)
        _save_prior_prorrata_observation(repo, percentage=Decimal("87"), stamped_revision_id=_prior_revision_id())

        evaluation = evaluate_carried_prior_definitiva_seed(
            ejercicio=_CURRENT_YEAR,
            observation_repository=repo,
        )

    assert not evaluation.blocked
    assert evaluation.findings == ()
    seed = evaluation.seed
    assert seed is not None
    assert seed.source_modelo == Modelo.M303.value
    assert seed.source_filing_year == _PRIOR_YEAR
    assert seed.source_period == _SETTLEMENT_PERIOD
    assert seed.source_casilla_id == _PORCENTAJE_ID
    assert seed.stamped_revision_id == _prior_revision_id()
    assert seed.entry.ejercicio == _CURRENT_YEAR
    assert seed.entry.provisional_percentage == Decimal("87")
    assert seed.entry.provisional_provenance is ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA
    assert seed.entry.source_observation_ref == "303:2025:4T"


def test_seed_divergent_revision_stamp_blocks(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository(objects=profile.repository)
        _save_prior_prorrata_observation(
            repo,
            percentage=Decimal("91"),
            stamped_revision_id=_DIVERGENT_REVISION_ID,
        )

        evaluation = evaluate_carried_prior_definitiva_seed(
            ejercicio=_CURRENT_YEAR,
            observation_repository=repo,
        )

    assert evaluation.seed is None
    assert evaluation.blocked
    assert len(evaluation.findings) == 1
    finding = evaluation.findings[0]
    assert finding.code == CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE.value
    assert finding.blocking
    assert not finding.advisory
    assert finding.source_modelo == Modelo.M303.value
    assert finding.source_filing_year == _PRIOR_YEAR
    assert finding.source_period == _SETTLEMENT_PERIOD
    assert finding.stamped_revision_id == _DIVERGENT_REVISION_ID
    assert finding.selected_revision_id == _prior_revision_id()


def test_seed_missing_legacy_revision_stamp_advises_without_blocking(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository(objects=profile.repository)
        _save_prior_prorrata_observation(repo, percentage=Decimal("73"), stamped_revision_id=_prior_revision_id())
        _remove_stamped_revision_id_from_saved_observation(profile)

        evaluation = evaluate_carried_prior_definitiva_seed(
            ejercicio=_CURRENT_YEAR,
            observation_repository=repo,
        )

    assert not evaluation.blocked
    assert len(evaluation.findings) == 1
    finding = evaluation.findings[0]
    assert finding.code == "missing_legacy_revision_stamp"
    assert finding.advisory
    assert not finding.blocking
    assert finding.stamped_revision_id is None
    assert finding.selected_revision_id == _prior_revision_id()
    seed = evaluation.seed
    assert seed is not None
    assert seed.stamped_revision_id is None
    assert seed.entry.provisional_percentage == Decimal("73")
    assert seed.entry.source_observation_ref == "303:2025:4T"
