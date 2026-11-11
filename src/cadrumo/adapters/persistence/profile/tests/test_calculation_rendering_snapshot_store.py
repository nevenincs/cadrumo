"""Saved renderings stored once per profile by rendering digest, read back whole.

The calculation-revision catalogue keeps each revision's rendering as a typed
reference to one row of the rendering-snapshot namespace. These cases run the
real repository against a real encrypted store: a catalogue written before
references existed still reads and converts on its next ordinary write, every
way a referenced row can be lost or altered refuses with its own reason, and
a referenced row cannot vanish between the write's preparation and its commit.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text

from cadrumo.domain.modelos.tests.work_unit_catalogue_support import build_work_unit_catalogue

from .....application.export.review_form_data import capture_review_form
from .....core.casilla_id import validated_casilla_id
from .....core.period import Period, PeriodError
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.errors import NoRevisionForPeriodError
from .....domain.calculations.registry.schema import RegistrySnapshot
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.modelos.calculation_repository import CalculationRevisionPersistenceError
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .....domain.modelos.calculation_revision_rendering import CalculationRenderingSnapshot
from .....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...storage.errors import SecureObjectRevisionConflictError
from ...storage.secure_object_namespaces import (
    MODELO_CALCULATION_RENDERING_SNAPSHOT_NAMESPACE,
    MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE,
)
from ...storage.sql.secure_objects import SecureObjectRepository
from ...storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from ..modelos_work_units import WorkUnitCatalogueRepository
from .embedded_rendering_fixture import EMBEDDED_RENDERING_FIXTURE_BUCKET_ID, install_embedded_rendering_fixture
from .published_authority_support import published_authority_operation

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter, pytest.mark.usefixtures("authority_operation")]

_FIXTURE_BUCKET_ID = EMBEDDED_RENDERING_FIXTURE_BUCKET_ID
_CATALOGUE = MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE
_SNAPSHOTS = MODELO_CALCULATION_RENDERING_SNAPSHOT_NAMESPACE
_REFERENCE_FORM = "rendering_digest_reference"
_CREATED_AT = datetime(_YEAR, 4, 2, 9, 0, 0, tzinfo=UTC)
_BASE = validated_casilla_id("iva.base-imponible", surface="_BASE")


def _stored_catalogue_record(profile: TestRuntimeProfile):
    record = profile.repository.load(
        _CATALOGUE.namespace,
        _CATALOGUE.require_default_object_key(),
        expected_class=_CATALOGUE.sensitivity,
        max_supported_version=_CATALOGUE.schema_version,
    )
    assert record is not None
    return record


def _stored_renderings(profile: TestRuntimeProfile) -> list[Any]:
    stored = json.loads(_stored_catalogue_record(profile).payload)
    return [revision.get("rendering_snapshot") for revision in stored["payload"]["revisions"].values()]


def _rewrite_stored_catalogue(profile: TestRuntimeProfile, rewrite: Callable[[Any], None]) -> None:
    record = _stored_catalogue_record(profile)
    stored = json.loads(record.payload)
    rewrite(stored)
    profile.repository.save(
        namespace=_CATALOGUE.namespace,
        object_key=_CATALOGUE.require_default_object_key(),
        classification=_CATALOGUE.sensitivity,
        schema_version=record.schema_version,
        written_at=record.written_at,
        payload=json.dumps(stored).encode(),
    )


def _fresh_load(profile: TestRuntimeProfile, operation: PinnedAuthorityOperation) -> CalculationRevisionCatalogue:
    return CalculationRevisionCatalogueRepository(objects=profile.repository).load(operation=operation)


def _refusal(profile: TestRuntimeProfile, operation: PinnedAuthorityOperation) -> dict[str, object]:
    with pytest.raises(CalculationRevisionPersistenceError) as refused:
        _fresh_load(profile, operation)
    assert refused.value.__context__ is None
    assert refused.value.context is not None
    return dict(refused.value.context)


def _digests(catalogue: CalculationRevisionCatalogue) -> list[str]:
    return sorted(
        {revision.rendering_snapshot.rendering_digest for revision in catalogue.values() if revision.rendering_snapshot}
    )


def _sql(repository: SecureObjectRepository, statement: str, **parameters: object) -> int:
    with repository._engine.begin() as connection:
        return connection.execute(text(statement), parameters).rowcount


def _key(digest: str) -> bytes:
    return SecureObjectRepository.object_key_digest(digest)


@contextmanager
def _converted_fixture(tmp_path: Path) -> Generator[tuple[TestRuntimeProfile, PinnedAuthorityOperation, list[str]]]:
    """Yield a profile whose fixture catalogue has been rewritten once into reference form."""
    operation = published_authority_operation()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FIXTURE_BUCKET_ID) as profile:
        install_embedded_rendering_fixture(profile)
        repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        catalogue = repository.load(operation=operation)
        repository.save(catalogue)
        digests = _digests(catalogue)
        assert len(digests) == 2
        yield profile, operation, digests


def test_an_embedded_catalogue_reads_unchanged_and_converts_on_its_next_ordinary_write(tmp_path: Path) -> None:
    operation = published_authority_operation()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FIXTURE_BUCKET_ID) as profile:
        install_embedded_rendering_fixture(profile)
        embedded = _stored_renderings(profile)
        repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        legacy, _revision_id = repository.load_revisioned(operation=operation)
        assert _stored_renderings(profile) == embedded, "a read never rewrites the stored form"
        forms_before = {revision.calculation_revision_id: capture_review_form(revision) for revision in legacy}

        repository.save(legacy)

        converted = _fresh_load(profile, operation)
        forms_after = {revision.calculation_revision_id: capture_review_form(revision) for revision in converted}
        stored = _stored_renderings(profile)
        record = _stored_catalogue_record(profile)
        snapshot_keys = profile.repository.list_keys(_SNAPSHOTS.namespace)

    assert sum(value is None for value in embedded) == 1
    assert all("form" not in value and "registry_snapshot" in value for value in embedded if value is not None)
    assert converted == legacy
    assert [revision.calculation_revision_id for revision in converted] == [
        revision.calculation_revision_id for revision in legacy
    ]
    for revision in converted:
        before = legacy.get(revision.calculation_revision_id)
        assert before is not None
        if before.rendering_snapshot is None:
            assert revision.rendering_snapshot is None
            continue
        assert revision.rendering_snapshot is not None
        assert revision.rendering_snapshot.rendering_digest == before.rendering_snapshot.rendering_digest
        assert revision.rendering_snapshot.registry_digest == before.rendering_snapshot.registry_digest
        assert revision.rendering_snapshot.authority_generation == before.rendering_snapshot.authority_generation
    assert forms_after == forms_before
    assert sum(form is not None for form in forms_after.values()) == 3
    assert sum(value is None for value in stored) == 1
    references = [value for value in stored if value is not None]
    assert all(value["form"] == _REFERENCE_FORM and "registry_snapshot" not in value for value in references)
    assert len(snapshot_keys) == len({value["rendering_digest"] for value in references}) == 2
    assert record.namespace == _CATALOGUE.namespace
    assert record.schema_version == _CATALOGUE.schema_version


def test_a_missing_rendering_row_refuses(tmp_path: Path) -> None:
    with _converted_fixture(tmp_path) as (profile, operation, digests):
        assert profile.repository.delete(_SNAPSHOTS.namespace, digests[0])
        assert _refusal(profile, operation) == {"reason": "rendering_snapshot_missing"}


def test_a_warm_reader_refuses_once_a_referenced_row_is_gone(tmp_path: Path) -> None:
    with _converted_fixture(tmp_path) as (profile, operation, digests):
        reader = CalculationRevisionCatalogueRepository(objects=profile.repository)
        warm, _revision_id = reader.load_revisioned(operation=operation)
        assert reader.load_revisioned(operation=operation)[0] == warm
        assert profile.repository.delete(_SNAPSHOTS.namespace, digests[1])
        with pytest.raises(CalculationRevisionPersistenceError) as refused:
            reader.load_revisioned(operation=operation)

    assert refused.value.context == {"reason": "rendering_snapshot_missing"}


def test_a_tampered_rendering_row_refuses(tmp_path: Path) -> None:
    with _converted_fixture(tmp_path) as (profile, operation, digests):
        row = {"ns": _SNAPSHOTS.namespace, "key": _key(digests[0])}
        select = text("SELECT payload FROM secure_objects WHERE namespace = :ns AND object_key = :key")
        with profile.repository._engine.begin() as connection:
            stored = bytes(connection.execute(select, row).scalar_one())
        # One flipped ciphertext bit: the row keeps its key and lineage columns.
        tampered = stored[:-1] + bytes([stored[-1] ^ 0x01])
        update = "UPDATE secure_objects SET payload = :payload WHERE namespace = :ns AND object_key = :key"
        assert _sql(profile.repository, update, payload=tampered, **row)
        assert _refusal(profile, operation) == {"reason": "rendering_snapshot_unreadable"}


def test_a_rendering_row_moved_under_another_digest_refuses(tmp_path: Path) -> None:
    with _converted_fixture(tmp_path) as (profile, operation, digests):
        moved, displaced = digests
        assert _sql(
            profile.repository,
            "DELETE FROM secure_objects WHERE namespace = :ns AND object_key = :key",
            ns=_SNAPSHOTS.namespace,
            key=_key(displaced),
        )
        assert _sql(
            profile.repository,
            "UPDATE secure_objects SET object_key = :to WHERE namespace = :ns AND object_key = :key",
            to=_key(displaced),
            ns=_SNAPSHOTS.namespace,
            key=_key(moved),
        )
        assert _refusal(profile, operation) == {"reason": "rendering_snapshot_unreadable"}


def test_a_validly_encrypted_body_of_another_digest_refuses(tmp_path: Path) -> None:
    with _converted_fixture(tmp_path) as (profile, operation, digests):
        kept, overwritten = digests
        other = profile.repository.load(
            _SNAPSHOTS.namespace,
            kept,
            expected_class=_SNAPSHOTS.sensitivity,
            max_supported_version=_SNAPSHOTS.schema_version,
        )
        assert other is not None
        profile.repository.save(
            namespace=_SNAPSHOTS.namespace,
            object_key=overwritten,
            classification=_SNAPSHOTS.sensitivity,
            schema_version=_SNAPSHOTS.schema_version,
            written_at=other.written_at,
            payload=other.payload,
        )
        assert _refusal(profile, operation) == {"reason": "rendering_snapshot_digest_mismatch"}


def test_an_unknown_rendering_storage_form_refuses(tmp_path: Path) -> None:
    with _converted_fixture(tmp_path) as (profile, operation, _digests_stored):

        def rename_form(stored: Any) -> None:
            for revision in stored["payload"]["revisions"].values():
                if revision.get("rendering_snapshot") is not None:
                    revision["rendering_snapshot"]["form"] = "rendering_digest_reference_v2"
                    return

        _rewrite_stored_catalogue(profile, rename_form)
        assert _refusal(profile, operation) == {"reason": "unknown_rendering_form"}


def test_a_referenced_row_removed_before_commit_refuses_the_whole_write(tmp_path: Path) -> None:
    with _converted_fixture(tmp_path) as (profile, operation, digests):
        repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        current = repository.load(operation=operation)
        before = _stored_catalogue_record(profile).revision_id
        sharing = next(revision for revision in current.values() if revision.rendering_snapshot is not None)
        added = _revision_like(sharing, amount="500.00", minutes=10)
        unit = repository.to_secure_object_write_unit(
            CalculationRevisionCatalogue(revisions={**current.revisions, added.calculation_revision_id: added})
        )
        assert sharing.rendering_snapshot is not None
        asserted = {assertion.object_key for assertion in unit.assertions}
        assert sharing.rendering_snapshot.rendering_digest in asserted
        assert [write.namespace for write in unit.writes] == [_CATALOGUE.namespace]

        assert profile.repository.delete(_SNAPSHOTS.namespace, sharing.rendering_snapshot.rendering_digest)
        with pytest.raises(SecureObjectRevisionConflictError):
            profile.repository.apply_batch(unit.writes, assertions=unit.assertions)

        assert _stored_catalogue_record(profile).revision_id == before
        assert set(digests) >= asserted


def test_two_writers_of_one_new_rendering_lose_no_revision(tmp_path: Path) -> None:
    operation = published_authority_operation()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FIXTURE_BUCKET_ID) as profile:
        install_embedded_rendering_fixture(profile, with_calculations=False)
        units = {unit.period.code: unit for unit in WorkUnitCatalogueRepository(objects=profile.repository).load()}
        snapshot = operation.snapshot("303", filing_year=_YEAR, period="1T")
        rendering = CalculationRenderingSnapshot.capture(
            snapshot, authority_generation=operation.pin().logical_generation
        )
        first = _revision(units["1T"], snapshot, rendering, amount="100.00", minutes=1)
        second = _revision(units["1T"], snapshot, rendering, amount="200.00", minutes=2)
        writer_a = CalculationRevisionCatalogueRepository(objects=profile.repository)
        writer_b = CalculationRevisionCatalogueRepository(objects=profile.repository)
        unit_a = writer_a.to_secure_object_write_unit(
            CalculationRevisionCatalogue(revisions={first.calculation_revision_id: first})
        )
        unit_b = writer_b.to_secure_object_write_unit(
            CalculationRevisionCatalogue(revisions={second.calculation_revision_id: second})
        )
        assert [write.namespace for write in unit_a.writes] == [_CATALOGUE.namespace, _SNAPSHOTS.namespace]
        assert [write.namespace for write in unit_b.writes] == [_CATALOGUE.namespace, _SNAPSHOTS.namespace]

        profile.repository.apply_batch(unit_a.writes, assertions=unit_a.assertions)
        with pytest.raises(SecureObjectRevisionConflictError):
            profile.repository.apply_batch(unit_b.writes, assertions=unit_b.assertions)
        after_conflict = _fresh_load(profile, operation)

        current, revision_id = writer_b.load_revisioned(operation=operation)
        merged = CalculationRevisionCatalogue(revisions={**current.revisions, second.calculation_revision_id: second})
        retry = writer_b.to_secure_object_write_unit(merged, expected_revision_id=revision_id)
        profile.repository.apply_batch(retry.writes, assertions=retry.assertions)
        final = _fresh_load(profile, operation)
        snapshot_keys = profile.repository.list_keys(_SNAPSHOTS.namespace)

    assert [revision.calculation_revision_id for revision in after_conflict] == [first.calculation_revision_id]
    assert [write.namespace for write in retry.writes] == [_CATALOGUE.namespace]
    assert {revision.calculation_revision_id for revision in final} == {
        first.calculation_revision_id,
        second.calculation_revision_id,
    }
    assert final.get(first.calculation_revision_id) == first
    assert final.get(second.calculation_revision_id) == second
    assert len(snapshot_keys) == 1


def _revision(
    unit: WorkUnit,
    snapshot: RegistrySnapshot,
    rendering: CalculationRenderingSnapshot | None,
    *,
    amount: str | None,
    minutes: int,
) -> CalculationRevision:
    values = {_BASE: amount} if amount is not None else {}
    revision_id = derive_calculation_revision_id(
        work_unit_id=unit.work_unit_id,
        input_values_by_casilla_id=values,
        binding_overrides={},
        casilla_values={},
        source_transaction_ids=(),
        filing_instance_evidence=None,
        source_provenance=(),
        rendering_snapshot=rendering,
    )
    at = _CREATED_AT + timedelta(minutes=minutes)
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=unit.work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=values,
        filing_instance_evidence=None,
        rendering_snapshot=rendering,
        created_at=at,
        updated_at=at,
        source_provenance=(),
    )


def _revision_like(revision: CalculationRevision, *, amount: str, minutes: int) -> CalculationRevision:
    values = {_BASE: amount}
    revision_id = derive_calculation_revision_id(
        work_unit_id=revision.work_unit_id,
        input_values_by_casilla_id=values,
        binding_overrides={},
        casilla_values={},
        source_transaction_ids=(),
        filing_instance_evidence=None,
        source_provenance=(),
        rendering_snapshot=revision.rendering_snapshot,
    )
    at = _CREATED_AT + timedelta(minutes=minutes)
    return revision.model_copy(
        update={
            "calculation_revision_id": revision_id,
            "input_values_by_casilla_id": values,
            "created_at": at,
            "updated_at": at,
        }
    )


def _rendering_with_form(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> CalculationRenderingSnapshot:
    """Capture the rendering a calculation saves: the snapshot joined with its separately published form."""
    layout = operation.form_layout(snapshot.modelo.id, snapshot.revision.id)
    if layout is not None:
        snapshot = snapshot.model_copy(
            update={"revision": snapshot.revision.model_copy(update={"form_layouts": (layout,)})}
        )
    return CalculationRenderingSnapshot.capture(snapshot, authority_generation=operation.pin().logical_generation)


def _calculable_coordinates(
    operation: PinnedAuthorityOperation, year: int
) -> Iterator[tuple[str, Period, RegistrySnapshot]]:
    """Yield, per modelo, the first declared period of ``year`` the registry resolves, at its reachable grade."""
    for modelo_id in operation.modelo_ids():
        selector = operation.modelo_directory(modelo_id).revisions[-1].period_selector
        periods = next((item.periods for item in selector.period_overrides if item.year == year), selector.periods)
        for code in periods:
            try:
                period = Period.from_year_and_code(year, code)
                grade = operation.reachable_authority_grade(modelo_id, filing_year=year, period=code)
                snapshot = operation.snapshot(modelo_id, filing_year=year, period=code, grade=grade)
            except (NoRevisionForPeriodError, PeriodError):
                continue
            yield modelo_id, period, snapshot
            break


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_every_supported_year_round_trips_each_saved_rendering_through_its_reference(tmp_path: Path, year: int) -> None:
    operation = published_authority_operation()
    bucket_id = "7c1d2e3f-4a5b-4c6d-8e9f-0a1b2c3d4e5f"
    units: list[WorkUnit] = []
    revisions: dict[str, CalculationRevision] = {}
    for minutes, (modelo_id, period, snapshot) in enumerate(_calculable_coordinates(operation, year)):
        rendering = _rendering_with_form(snapshot, operation)
        unit = WorkUnit(
            work_unit_id=derive_work_unit_id(
                bucket_id=bucket_id,
                modelo=modelo_id,
                filing_year=year,
                period=period,
                revision_id=snapshot.snapshot_ref.revision_id,
            ),
            bucket_id=bucket_id,
            modelo=modelo_id,
            filing_year=year,
            period=period,
            revision_id=snapshot.snapshot_ref.revision_id,
            name=f"{modelo_id}-{year}-{period.code}",
            created_at=_CREATED_AT,
            updated_at=_CREATED_AT,
        )
        units.append(unit)
        revision = _revision(unit, snapshot, rendering, amount=None, minutes=minutes)
        revisions[revision.calculation_revision_id] = revision
    catalogue = CalculationRevisionCatalogue(revisions=revisions)
    # A modelo is left out only where the registry refuses the year (before its
    # inception) or none of its periods is a work-unit period.
    assert "303" in {unit.modelo for unit in units}

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        WorkUnitCatalogueRepository(objects=profile.repository).save(build_work_unit_catalogue(tuple(units)))
        CalculationRevisionCatalogueRepository(objects=profile.repository).save(catalogue)
        loaded = _fresh_load(profile, operation)
        stored = _stored_renderings(profile)
        snapshot_keys = profile.repository.list_keys(_SNAPSHOTS.namespace)

    assert loaded == catalogue
    assert all(value["form"] == _REFERENCE_FORM for value in stored)
    assert len(snapshot_keys) == len(_digests(catalogue))
