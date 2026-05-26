"""Application tests for relation prefill source mesh enrollment."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.storage.master_key._active_session import activate_session
from ...adapters.persistence.storage.master_key._bucket_session import BucketSession
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...core.config import override_settings
from ...core.resources import resources
from ...domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ..aggregation import CalculationSourceContext
from ._observations_repository import CalculationObservationRepository
from ._relation_prefill import RelationPrefillSourceResolver, resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_BUCKET_ID = "operator"
_KEK = b"r" * 32
_DEK = b"p" * 32


@pytest.fixture(autouse=True)
def _isolated_secure_sql(tmp_path: Path) -> Iterator[None]:
    with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_BUCKET_ID) as settings:
        dispose_engine(settings)
        with activate_session(_session()):
            try:
                yield
            finally:
                dispose_engine(settings)


def _session() -> BucketSession:
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=_KEK,
        dek=_DEK,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )


def _modelo_115_observations() -> tuple[RegistryModeloObservation, ...]:
    values_by_period = {
        "1T": {"01": Decimal("1"), "02": Decimal("250.10"), "03": Decimal("47.52")},
        "2T": {"01": Decimal("1"), "02": Decimal("749.90"), "03": Decimal("142.48")},
        "3T": {"01": Decimal("2"), "02": Decimal("1200.00"), "03": Decimal("228.00")},
        "4T": {"01": Decimal("1"), "02": Decimal("-50.25"), "03": Decimal("0.00")},
    }
    return tuple(
        RegistryModeloObservation(
            modelo="115",
            filing_year=2026,
            period=period,
            observations=tuple(CasillaObservation(casilla_id=cid, value=val) for cid, val in casilla_values.items()),
        )
        for period, casilla_values in values_by_period.items()
    )


def test_relation_prefill_source_resolver_matches_local_store_prefill() -> None:
    repository = CalculationObservationRepository(bucket_id=_BUCKET_ID)
    for observation in _modelo_115_observations():
        repository.save_observation(observation, source_kind="app_filing")

    snapshot = resources().modelos.authority.snapshot("180", filing_year=2026, period="0A")
    prefill = resolve_relations_from_local_store(snapshot, repository=repository)
    source_resolution = RelationPrefillSourceResolver(
        repository=repository,
        registry_snapshot=snapshot,
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="180",
            filing_year=2026,
            period="0A",
            revision=snapshot.revision,
        )
    )

    assert source_resolution.relation_values == {
        item.relation: item.value for item in prefill.values if item.value is not None
    }
    assert source_resolution.owned_sources == ("relation_prefill",)
    assert source_resolution.provenance
    assert all(item.source_kind == "relation_prefill" for item in source_resolution.provenance)
    assert {
        item.source_ref for item in source_resolution.provenance
    } == {
        "modelo-180-rel-115-perceptores-anual:2026:1T,2T,3T,4T",
        "modelo-180-rel-115-base-anual:2026:1T,2T,3T,4T",
        "modelo-180-rel-115-retenciones-anual:2026:1T,2T,3T,4T",
    }
