"""Publication proves the snapshot cross-checks of the declared selectors, and runtime relies on that proof.

Every case publishes a synthetic artifact through the real installer, which
builds, proves and installs the database exactly as a full publication does,
and reads it back through the real runtime reader and validator. The
cross-checks a proof replaces are observed by wrapping every entry of the
validator's own check registry so it counts its calls and still runs. Variant
databases are byte copies of a publication changed in place and republished
under their own content address, so admission's digest check holds and only
the proof records differ.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.config import override_settings
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.storage_materialization import ensure_storage_tree
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_path
from cadrumo.core.time.clock import frozen_clock, today_madrid
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.authority_store import (
    AUTHORITY_DATABASE_FORMAT,
    AuthorityDescriptor,
    SQLiteAuthorityReader,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from cadrumo.domain.calculations.registry.snapshot_proof import (
    SNAPSHOT_PROOF_DDL,
    SNAPSHOT_PROOF_TABLES,
    SnapshotProofPublicationError,
    ValidatorSource,
    snapshot_validator_closure,
    validator_digest,
)
from cadrumo.domain.calculations.registry.tests.artifact_runtime_support import minimal_revision
from cadrumo.domain.calculations.registry.tests.snapshot_proof_support import count_cross_checks

from ..pipeline.authority_publication import install_validated_authority_database
from ._authority_generation_support import synthetic_authority_artifact

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESCRIPTOR_NAME = "authority.current.json"
_PROOFLESS_FORMAT = "cadrumo-authority-sqlite-v4"
_Cell = tuple[str, int, str, RegistryAuthorityGrade]
_Statements = tuple[tuple[str, tuple[object, ...]], ...]


@pytest.fixture(autouse=True)
def _own_storage(tmp_path: Path) -> Iterator[None]:
    """Keep admission receipts to a provisioned storage root of this test's own."""
    with override_settings(cadrumo_storage_root=tmp_path / "storage"):
        ensure_storage_tree()
        yield


def _publish(
    destination: Path, revision: ModeloRevision | None = None, *, facts_restated_on: date | None = None
) -> Path:
    install_validated_authority_database(
        synthetic_authority_artifact(revision, facts_restated_on=facts_restated_on),
        destination=destination,
        require_current=lambda: None,
    )
    return destination / _DESCRIPTOR_NAME


def _database(descriptor_path: Path) -> Path:
    return descriptor_path.parent / AuthorityDescriptor.read(descriptor_path).database


def _query(descriptor_path: Path, sql: str) -> list[tuple[object, ...]]:
    uri = _database(descriptor_path).resolve().as_uri() + "?mode=ro"
    rows: list[tuple[object, ...]] = []
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        rows.extend(tuple(row) for row in connection.execute(sql))
    return rows


def _proven_cells(descriptor_path: Path) -> tuple[_Cell, ...]:
    rows = _query(
        descriptor_path,
        "SELECT modelo_id, filing_year, period, grade FROM snapshot_proofs "
        "ORDER BY modelo_id, filing_year, period, grade",
    )
    return tuple(
        (str(modelo), int(str(year)), str(period), RegistryAuthorityGrade(grade))
        for modelo, year, period, grade in rows
    )


def _republished_copy(descriptor_path: Path, directory: Path, statements: _Statements) -> Path:
    """Copy a publication, change its database in place and publish the copy under its own digest."""
    source = AuthorityDescriptor.read(descriptor_path)
    directory.mkdir()
    staging = directory / "staged.sqlite3"
    shutil.copyfile(_database(descriptor_path), staging)
    with closing(sqlite3.connect(staging)) as connection:
        for statement, parameters in statements:
            connection.execute(statement, parameters)
        connection.commit()
    payload = staging.read_bytes()
    digest = sha256_hex(payload)
    staging.replace(directory / f"authority-{digest}.sqlite3")
    (directory / _DESCRIPTOR_NAME).write_bytes(
        AuthorityDescriptor(
            database=f"authority-{digest}.sqlite3",
            database_size=len(payload),
            database_sha256=digest,
            logical_generation=source.logical_generation,
        ).to_bytes()
    )
    return directory / _DESCRIPTOR_NAME


def _without_proofs(descriptor_path: Path, directory: Path) -> Path:
    """Return the same publication with empty proof tables, which runtime reads as carrying no proofs."""
    return _republished_copy(
        descriptor_path,
        directory,
        (
            *((f"DROP TABLE {table}", ()) for table in SNAPSHOT_PROOF_TABLES),
            *((statement, ()) for statement in SNAPSHOT_PROOF_DDL),
        ),
    )


def _build(descriptor_path: Path, cell: _Cell) -> RegistrySnapshot:
    modelo_id, filing_year, period, grade = cell
    reader = SQLiteAuthorityReader(descriptor_path, max_connections=1)
    try:
        operation = PinnedAuthorityOperation(reader, reader.pin())
        return operation.snapshot(modelo_id, filing_year=filing_year, period=period, grade=grade)
    finally:
        reader.close()


def _ladder_up_to(grade: RegistryAuthorityGrade) -> frozenset[RegistryAuthorityGrade]:
    ladder = tuple(RegistryAuthorityGrade)
    return frozenset(ladder[: ladder.index(grade) + 1])


def test_publication_records_the_passing_cells_under_the_running_validator(tmp_path: Path) -> None:
    descriptor_path = _publish(tmp_path / "published")
    closure = snapshot_validator_closure()
    declared = minimal_revision().effective_authority_grade

    reader = SQLiteAuthorityReader(descriptor_path, max_connections=1)
    try:
        contract = reader.snapshot_proof_contract()
    finally:
        reader.close()
    cells = _proven_cells(descriptor_path)

    assert _query(descriptor_path, "SELECT format FROM authority_manifest") == [(AUTHORITY_DATABASE_FORMAT,)]
    assert contract is not None
    assert contract.validator_sources == closure
    assert contract.validator_digest == validator_digest(closure)
    assert contract.admits_date(today_madrid())
    assert cells
    assert {grade for *_, grade in cells} == _ladder_up_to(declared)


def test_publication_leaves_no_receipt_for_the_unpublished_staged_bytes(tmp_path: Path) -> None:
    descriptor_path = _publish(tmp_path / "published")

    receipts = {path.name for path in storage_path(StorageCategory.AUTHORITY_ADMISSION_RECEIPTS).glob("*.json")}

    assert receipts <= {f"{AuthorityDescriptor.read(descriptor_path).database_sha256}.json"}


def test_a_proven_request_runs_no_cross_check_and_equals_full_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor_path = _publish(tmp_path / "published")
    cell = _proven_cells(descriptor_path)[0]
    proofless = _without_proofs(descriptor_path, tmp_path / "proofless")
    counts = count_cross_checks(monkeypatch)

    full = _build(proofless, cell)
    assert all(count == 1 for count in counts), counts
    counts[:] = [0] * len(counts)
    proven = _build(descriptor_path, cell)

    assert counts == [0] * len(counts)
    assert proven == full


def test_every_proven_cell_builds_the_same_snapshot_with_and_without_its_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor_path = _publish(tmp_path / "published")
    proofless = _without_proofs(descriptor_path, tmp_path / "proofless")
    cells = _proven_cells(descriptor_path)
    counts = count_cross_checks(monkeypatch)

    for cell in cells:
        counts[:] = [0] * len(counts)
        full = _build(proofless, cell)
        assert all(count == 1 for count in counts), (cell, counts)
        counts[:] = [0] * len(counts)
        assert _build(descriptor_path, cell) == full, cell
        assert counts == [0] * len(counts), (cell, counts)


def _tampered_validator(sources: tuple[ValidatorSource, ...]) -> _Statements:
    """Record another digest for one validator module, under a contract digest that names the changed list."""
    first, *rest = sources
    recorded = (ValidatorSource(first.module, "0" * 64), *rest)
    return (
        ("UPDATE snapshot_proof_validator_sources SET sha256 = ? WHERE module = ?", ("0" * 64, first.module)),
        ("UPDATE snapshot_proof_contract SET validator_digest = ?", (validator_digest(recorded),)),
    )


def test_a_validator_digest_mismatch_runs_every_cross_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    descriptor_path = _publish(tmp_path / "published")
    cell = _proven_cells(descriptor_path)[0]
    proven = _build(descriptor_path, cell)
    changed = _republished_copy(
        descriptor_path, tmp_path / "other-validator", _tampered_validator(snapshot_validator_closure())
    )
    counts = count_cross_checks(monkeypatch)

    assert _build(changed, cell) == proven
    assert all(count == 1 for count in counts), counts


def test_a_date_outside_the_fact_window_runs_every_cross_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    restated_on = date(today_madrid().year + 5, 1, 1)
    descriptor_path = _publish(tmp_path / "published", facts_restated_on=restated_on)
    cell = _proven_cells(descriptor_path)[0]
    reader = SQLiteAuthorityReader(descriptor_path, max_connections=1)
    try:
        contract = reader.snapshot_proof_contract()
    finally:
        reader.close()
    proven = _build(descriptor_path, cell)
    counts = count_cross_checks(monkeypatch)

    with frozen_clock(datetime(restated_on.year, restated_on.month, restated_on.day, 12, tzinfo=UTC)):
        outside = _build(descriptor_path, cell)

    assert contract is not None
    assert contract.window_to == restated_on - timedelta(days=1)
    assert outside == proven
    assert all(count == 1 for count in counts), counts


def test_a_database_of_the_preceding_format_runs_every_cross_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descriptor_path = _publish(tmp_path / "published")
    cell = _proven_cells(descriptor_path)[0]
    proven = _build(descriptor_path, cell)
    proofless = _republished_copy(
        descriptor_path,
        tmp_path / "preceding-format",
        (
            ("UPDATE authority_manifest SET format = ?", (_PROOFLESS_FORMAT,)),
            *((f"DROP TABLE {table}", ()) for table in SNAPSHOT_PROOF_TABLES),
        ),
    )
    counts = count_cross_checks(monkeypatch)

    assert _build(proofless, cell) == proven
    assert all(count == 1 for count in counts), counts


def _declaring(grade: RegistryAuthorityGrade | None) -> ModeloRevision:
    return minimal_revision().model_copy(update={"authority_grade": grade})


def test_a_failure_at_or_below_the_declared_grade_refuses_publication_and_keeps_the_previous_descriptor(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "published"
    descriptor_path = _publish(destination)
    previous = descriptor_path.read_bytes()
    databases = sorted(path.name for path in destination.glob("authority-*.sqlite3"))

    # The miniature revision declares no export layout, so a filing claim
    # fails its own filing-grade snapshot check.
    with pytest.raises(SnapshotProofPublicationError, match="at or below their declared authority grade"):
        _publish(destination, _declaring(RegistryAuthorityGrade.FILING))

    assert descriptor_path.read_bytes() == previous
    assert sorted(path.name for path in destination.glob("authority-*.sqlite3")) == databases


def test_a_revision_declaring_no_grade_publishes_without_proving_any_of_its_cells(tmp_path: Path) -> None:
    descriptor_path = _publish(tmp_path / "published", _declaring(None))

    reader = SQLiteAuthorityReader(descriptor_path, max_connections=1)
    try:
        contract = reader.snapshot_proof_contract()
    finally:
        reader.close()

    assert contract is not None
    assert _proven_cells(descriptor_path) == ()
