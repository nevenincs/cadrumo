"""Strict roundtrip across the encrypted Modelo work-unit + calculation catalogues.

Two repositories share the modelo-domain encrypted persistence
boundary and were flagged as untested in the persistence-boundary
identity audit:

  * ``WorkUnitCatalogueRepository`` persists
    :class:`WorkUnitCatalogue`, a keyed mapping of :class:`WorkUnit`
    records at ``SensitivityClass.FINANCIAL``.
  * (``CalculationRevisionCatalogueRepository`` is already covered
    by ``domain/filing/test_secure_storage_roundtrip.py`` —
    keep the focus here on the work-unit half.)
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.engine import Engine

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.secure_object_namespaces import MODELO_WORK_UNIT_CATALOGUE_NAMESPACE
from ....core.classification.policies import SensitivityClass
from ....core.period import Period
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....tests.secure_sql import isolated_runtime_profile
from ..codes import ModeloCode
from ..repository import WorkUnitPersistenceError
from ..work_unit import (
    WorkUnit,
    WorkUnitCatalogue,
    WorkUnitState,
    derive_work_unit_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_ID = "df5dd25a-ff53-4086-9cc4-a13e61538a09"  # was 'modelo-runtime'
# The registry definition is the sole authority for this namespace's identifier,
# singleton object key, and envelope schema version; the probe reads it rather
# than restating the values the repository under test writes at.
_WORK_UNIT_NAMESPACE = MODELO_WORK_UNIT_CATALOGUE_NAMESPACE.namespace
_WORK_UNIT_OBJECT_KEY = MODELO_WORK_UNIT_CATALOGUE_NAMESPACE.require_default_object_key()
_WORK_UNIT_CATALOGUE_VERSION = MODELO_WORK_UNIT_CATALOGUE_NAMESPACE.schema_version
_WORK_UNIT_TIMESTAMP = datetime(2026, 5, 28, 10, 30, 0, tzinfo=UTC)
_CORRUPT_ENVELOPE_WRITTEN_AT = datetime(2026, 5, 28, 10, 35, 0, tzinfo=UTC)
_FUTURE_ENVELOPE_WRITTEN_AT = datetime(2026, 5, 28, 10, 40, 0, tzinfo=UTC)


def _is_secure_object_select(statement: str) -> bool:
    """Return whether one cursor statement reads the encrypted singleton table."""
    normalized = " ".join(statement.split()).upper()
    return normalized.startswith("SELECT") and " FROM SECURE_OBJECTS " in f" {normalized} "


@contextmanager
def _secure_object_select_log(engine: Engine) -> Iterator[list[str]]:
    """Observe live encrypted-SQL singleton reads without replacing a repository."""
    selects: list[str] = []

    def _record(
        _conn: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if _is_secure_object_select(statement):
            selects.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield selects
    finally:
        event.remove(engine, "before_cursor_execute", _record)


def _populated_work_unit(*, name_suffix: str = "default") -> WorkUnit:
    """Build a typed WorkUnit using **non-default** values everywhere possible.

    Every field defaulting to a value (state=DRAFT, discarded_at=None,
    discarded_by=None, discard_reason=None) is overridden with a real
    non-default value. This is the anti-tautology safeguard: if any
    boundary silently drops a field and the load side re-defaults it,
    the roundtrip equality would still hold under default-only
    fixtures. Forcing every defaultable field to a distinct sentinel
    makes a drop-and-redefault regression visible.
    """

    bucket_id = "b" * 32
    modelo = ModeloCode("303")
    filing_year = 2025
    period = Period.from_year_and_code(filing_year, "1T")
    revision_id = "2025-y-siguientes"
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"IVA-{filing_year}-{period.registry_token}-{name_suffix}",
        created_at=_WORK_UNIT_TIMESTAMP,
        updated_at=_WORK_UNIT_TIMESTAMP,
        # Non-default lifecycle state so a save-drops-state regression
        # would surface as state mismatch on load (default is DRAFT).
        state=WorkUnitState.DESCARTADO,
        # Discard metadata is required when state is DISCARDED;
        # populating it covers all three defaultable optional fields
        # at once.
        discarded_at=_WORK_UNIT_TIMESTAMP,
        discarded_by="cli/aeat",
        discard_reason="superseded by amended revision for roundtrip test fixture",
    )


def test_work_unit_catalogue_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A WorkUnitCatalogue with one typed WorkUnit roundtrips strictly."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        work_unit = _populated_work_unit()
        original = WorkUnitCatalogue(work_units={work_unit.work_unit_id: work_unit})

        repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID)
        repo.save(original)
        loaded = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert repo.bucket_id == _BUCKET_ID
    assert profile.paths.database_file.is_file()
    assert loaded == original
    loaded_unit = loaded.work_units[work_unit.work_unit_id]
    dumped_unit = loaded_unit.model_dump(mode="json")
    assert dumped_unit["filing_year"] == 2025
    assert dumped_unit["period"] == {"filing_year": 2025, "code": "1T"}
    assert "2025Q1" not in loaded_unit.model_dump_json()
    from ....tests.secure_sql import read_db_at_rest_bytes

    database_bytes = read_db_at_rest_bytes(profile.paths.database_file)
    assert b"2025Q1" not in database_bytes
    assert b"2025-1T" not in database_bytes
    # Per-field witnesses: ModeloCode preservation, year/period
    # round-trip, state enum identity, content-addressed work_unit_id,
    # and the discard metadata triple (which were the test's main
    # anti-tautology guard: every defaultable field carries a real
    # non-default value).
    assert loaded_unit.modelo == "303"
    assert loaded_unit.filing_year == 2025
    assert loaded_unit.period == Period.from_year_and_code(2025, "1T")
    assert loaded_unit.revision_id == "2025-y-siguientes"
    assert loaded_unit.state is WorkUnitState.DESCARTADO
    assert loaded_unit.work_unit_id == work_unit.work_unit_id
    # Discard metadata survives the cycle; a regression that dropped any
    # of these three on save would leave them as None on load and fail
    # the strict-equality check above, but also fail these witnesses.
    assert loaded_unit.discarded_at == work_unit.discarded_at
    assert loaded_unit.discarded_by == "cli/aeat"
    assert loaded_unit.discard_reason is not None
    assert "superseded" in loaded_unit.discard_reason


def test_load_revisioned_returns_one_enveloped_secure_object_record_across_an_interleaving(
    tmp_path: Path,
) -> None:
    """One live SQL SELECT keeps the envelope payload and revision inseparable."""
    first_unit = _populated_work_unit(name_suffix="first")
    second_unit = _populated_work_unit(name_suffix="second")
    first = WorkUnitCatalogue(work_units={first_unit.work_unit_id: first_unit})
    second = WorkUnitCatalogue(work_units={second_unit.work_unit_id: second_unit})
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = WorkUnitCatalogueRepository(objects=profile.repository)
        repository.save(first)
        expected_record = profile.repository.load(
            _WORK_UNIT_NAMESPACE,
            _WORK_UNIT_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_WORK_UNIT_CATALOGUE_VERSION,
        )
        assert expected_record is not None

        writer = WorkUnitCatalogueRepository(objects=profile.repository)
        selects: list[str] = []
        fired = False
        writing = False

        def _interleave_after_singleton_select(
            _conn: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            nonlocal fired, writing
            if not _is_secure_object_select(statement) or writing:
                return
            selects.append(statement)
            if fired:
                return
            fired = True
            writing = True
            try:
                writer.save(second)
            finally:
                writing = False

        engine = profile.repository.engine
        event.listen(engine, "after_cursor_execute", _interleave_after_singleton_select)
        try:
            observed, revision_id = repository.load_revisioned()
        finally:
            event.remove(engine, "after_cursor_execute", _interleave_after_singleton_select)

    assert fired
    assert len(selects) == 1
    assert observed == first
    assert revision_id == expected_record.revision_id


def test_load_revisioned_observes_an_absent_enveloped_singleton_with_one_select(
    tmp_path: Path,
) -> None:
    """The absent enveloped singleton outcome also uses exactly one encrypted-SQL read."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = WorkUnitCatalogueRepository(objects=profile.repository)
        with _secure_object_select_log(profile.repository.engine) as selects:
            observed, revision_id = repository.load_revisioned()

    assert len(selects) == 1
    assert observed == WorkUnitCatalogue()
    assert revision_id == ABSENT_SECURE_OBJECT_REVISION_ID


def test_work_unit_catalogue_lifecycle_drift_surfaces_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: flipping DISCARDED to DRAFT while retaining metadata must surface.

    :class:`WorkUnit` enforces a lifecycle invariant:
    DRAFT work units must NOT carry discard metadata; DISCARDED ones
    MUST. The catalogue also enforces that the dict key equals the
    work unit's content-addressed work_unit_id.

    Persists a DISCARDED work unit (with discard metadata populated),
    reloads the runtime-owned secure object, surgically flips the
    persisted ``state`` from ``"discarded"`` back to ``"draft"``
    without clearing the discard metadata, and asserts the load path
    catches the drift via the model_validator's
    DRAFT-must-not-carry-discard-metadata check.

    If this test ever passes silently with the flipped state, the
    work-unit catalogue boundary is tautological and the lifecycle
    state machine is not actually enforced post-persistence.
    """

    import json as _json

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        work_unit = _populated_work_unit()
        catalogue = WorkUnitCatalogue(work_units={work_unit.work_unit_id: work_unit})
        repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID)
        repo.save(catalogue)

        record = profile.repository.load(
            _WORK_UNIT_NAMESPACE,
            _WORK_UNIT_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_WORK_UNIT_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        work_units = envelope["payload"]["work_units"]
        unit_dict = work_units[work_unit.work_unit_id]
        assert unit_dict["state"] == "descartado", (
            "fixture must serialise state as 'descartado' for this proof test to be meaningful"
        )
        # Flip state back to borrador while leaving discard metadata
        # in place. The BORRADOR invariant must trip on load.
        unit_dict["state"] = "borrador"
        profile.repository.save(
            namespace=_WORK_UNIT_NAMESPACE,
            object_key=_WORK_UNIT_OBJECT_KEY,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        with pytest.raises(ValidationError):
            WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID).load()


def test_work_unit_catalogue_wrong_inner_classification_is_localized(
    tmp_path: Path,
) -> None:
    """A corrupted envelope classification raises a translated persistence error."""

    from ....adapters.persistence.storage.envelope.contract import Envelope

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        envelope = Envelope[WorkUnitCatalogue](
            schema_version=_WORK_UNIT_CATALOGUE_VERSION,
            written_at=_CORRUPT_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.AUDIT,
            payload=WorkUnitCatalogue(),
        )
        profile.repository.save(
            namespace=_WORK_UNIT_NAMESPACE,
            object_key=_WORK_UNIT_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_WORK_UNIT_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

        with pytest.raises(WorkUnitPersistenceError) as raised:
            WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert raised.value.translated_message == "errors.fail.fail_modelo_work_unit_persistence"
    assert raised.value.context == {
        "reason": "classification_mismatch",
        "expected_classification": "financial",
        "actual_classification": "audit",
    }


def test_work_unit_catalogue_unsupported_inner_version_is_localized(
    tmp_path: Path,
) -> None:
    """A future inner envelope schema version raises a translated persistence error."""

    from ....adapters.persistence.storage.envelope.contract import Envelope

    stored_schema_version = _WORK_UNIT_CATALOGUE_VERSION + 1
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        envelope = Envelope[WorkUnitCatalogue](
            schema_version=stored_schema_version,
            written_at=_FUTURE_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.FINANCIAL,
            payload=WorkUnitCatalogue(),
        )
        profile.repository.save(
            namespace=_WORK_UNIT_NAMESPACE,
            object_key=_WORK_UNIT_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_WORK_UNIT_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

        with pytest.raises(WorkUnitPersistenceError) as raised:
            WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert raised.value.translated_message == "errors.fail.fail_modelo_work_unit_persistence"
    assert raised.value.context == {
        "reason": "unsupported_envelope_version",
        "stored_schema_version": stored_schema_version,
        "max_supported_version": _WORK_UNIT_CATALOGUE_VERSION,
    }
