"""A proof-bearing authority database: admission of its proof tables and runtime use of its proofs.

Each case copies this checkout's published database, replaces its proof
tables with ones from their single domain definition, writes proof rows for
one declared cell the real validator passes, and republishes the copy under
its own content address, so admission's digest check holds and only the proof
tables decide.
The cross-checks a proof replaces are observed by wrapping every entry of the
validator's own check registry so it counts its calls and still runs.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.config import override_settings
from .....core.errors.hierarchy import CadrumoError
from .....core.storage_materialization import ensure_storage_tree
from .....core.time.clock import frozen_clock, today_madrid
from ..authority import PinnedAuthorityOperation
from ..authority_location import bundled_authority_descriptor_path
from ..authority_store import AuthorityStoreCorruptionError, SQLiteAuthorityReader
from ..errors import RegistryValidationError
from ..schema import RegistrySnapshot
from ..snapshot_proof import (
    SNAPSHOT_PROOF_TABLES,
    SnapshotCrossCheckProof,
    SnapshotProofContract,
    SnapshotProofPublicationError,
    ValidatorSource,
    prove_snapshot_selectors,
    snapshot_proof_key,
    snapshot_validator_closure,
    validator_digest,
)
from ..temporal import select_revision_metadata
from .snapshot_proof_support import count_cross_checks, republished_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_Cell = tuple[str, int, str, RegistryAuthorityGrade]


@pytest.fixture(autouse=True)
def _own_receipts(tmp_path: Path) -> Iterator[None]:
    """Keep admission receipts to a provisioned root of this test's own."""
    with override_settings(cadrumo_local_storage_root=tmp_path / "storage"):
        ensure_storage_tree()
        yield


@pytest.fixture(scope="module")
def closure() -> tuple[ValidatorSource, ...]:
    return snapshot_validator_closure()


@pytest.fixture(scope="module")
def proven_cell() -> tuple[_Cell, SnapshotCrossCheckProof]:
    """Return the first declared cell the published generation passes, with the proof it earns."""
    reader = SQLiteAuthorityReader(bundled_authority_descriptor_path())
    try:
        operation = PinnedAuthorityOperation(reader, reader.pin())
        support = operation.supported_filing_years()
        for modelo_id in operation.modelo_ids():
            directory = operation.modelo_directory(modelo_id)
            for filing_year in range(support.floor, support.horizon + 1):
                for period in directory.revisions[0].period_selector.declared_periods:
                    try:
                        selected = select_revision_metadata(directory, filing_year=filing_year, period=period)
                    except CadrumoError:
                        continue
                    for grade in reversed(tuple(RegistryAuthorityGrade)):
                        try:
                            operation.build_unretained_snapshot(
                                modelo_id, filing_year=filing_year, period=period, grade=grade
                            )
                        except RegistryValidationError:
                            continue
                        key = snapshot_proof_key(
                            selected, modelo_id=modelo_id, filing_year=filing_year, period=period, grade=grade
                        )
                        return (modelo_id, filing_year, period, grade), SnapshotCrossCheckProof(key, selected.id)
    finally:
        reader.close()
    raise AssertionError("the published generation declares no passing snapshot cell")


def _proof_rows(
    contract: SnapshotProofContract | None,
    proofs: tuple[SnapshotCrossCheckProof, ...],
) -> tuple[tuple[str, tuple[object, ...]], ...]:
    statements: list[tuple[str, tuple[object, ...]]] = []
    if contract is not None:
        statements.append(
            (
                "INSERT INTO snapshot_proof_contract VALUES (1, ?, ?, ?)",
                (
                    contract.validator_digest,
                    None if contract.window_from is None else contract.window_from.isoformat(),
                    None if contract.window_to is None else contract.window_to.isoformat(),
                ),
            )
        )
        statements.extend(
            ("INSERT INTO snapshot_proof_validator_sources VALUES (?, ?)", (source.module, source.sha256))
            for source in contract.validator_sources
        )
    statements.extend(
        (
            "INSERT INTO snapshot_proofs VALUES (?, ?, ?, ?, ?)",
            (proof.key.modelo_id, proof.key.filing_year, proof.key.period, proof.key.grade.value, proof.revision_id),
        )
        for proof in proofs
    )
    return tuple(statements)


def _snapshot(
    operation: PinnedAuthorityOperation, cell: _Cell, *, grade: RegistryAuthorityGrade | None = None
) -> RegistrySnapshot:
    modelo_id, filing_year, period, cell_grade = cell
    return operation.snapshot(modelo_id, filing_year=filing_year, period=period, grade=grade or cell_grade)


def test_a_current_database_with_empty_proof_tables_is_admitted_without_proofs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    proven_cell: tuple[_Cell, SnapshotCrossCheckProof],
) -> None:
    cell, proof = proven_cell
    reader = SQLiteAuthorityReader(republished_authority(tmp_path / "empty"), max_connections=1)
    try:
        operation = PinnedAuthorityOperation(reader, reader.pin())
        counts = count_cross_checks(monkeypatch)

        _snapshot(operation, cell)

        assert reader.snapshot_proof_contract() is None
        assert reader.snapshot_proof(proof.key) is None
        assert all(count == 1 for count in counts), counts
    finally:
        reader.close()


@pytest.mark.parametrize("missing", SNAPSHOT_PROOF_TABLES)
def test_a_current_database_missing_a_proof_table_is_refused(tmp_path: Path, missing: str) -> None:
    descriptor = republished_authority(
        tmp_path / "missing", tables=tuple(table for table in SNAPSHOT_PROOF_TABLES if table != missing)
    )

    with pytest.raises(AuthorityStoreCorruptionError, match="lacks its snapshot proof tables"):
        SQLiteAuthorityReader(descriptor, max_connections=1)


def test_proof_rows_without_a_contract_are_refused(
    tmp_path: Path, proven_cell: tuple[_Cell, SnapshotCrossCheckProof]
) -> None:
    _, proof = proven_cell
    descriptor = republished_authority(tmp_path / "orphan", statements=_proof_rows(None, (proof,)))

    with pytest.raises(AuthorityStoreCorruptionError, match="without a proof contract"):
        SQLiteAuthorityReader(descriptor, max_connections=1)


def test_a_malformed_window_bound_is_refused_when_the_contract_is_read(
    tmp_path: Path,
    closure: tuple[ValidatorSource, ...],
    proven_cell: tuple[_Cell, SnapshotCrossCheckProof],
) -> None:
    _, proof = proven_cell
    contract = SnapshotProofContract(closure, validator_digest(closure), None, None)
    statements = (
        *_proof_rows(contract, (proof,)),
        ("UPDATE snapshot_proof_contract SET window_from = ?", ("20260101",)),
    )
    reader = SQLiteAuthorityReader(
        republished_authority(tmp_path / "malformed", statements=statements), max_connections=1
    )
    try:
        with pytest.raises(AuthorityStoreCorruptionError, match="not canonical ISO date text"):
            reader.snapshot_proof_contract()
    finally:
        reader.close()


@pytest.fixture
def proven_reader(
    tmp_path: Path,
    closure: tuple[ValidatorSource, ...],
    proven_cell: tuple[_Cell, SnapshotCrossCheckProof],
) -> Iterator[tuple[SQLiteAuthorityReader, SnapshotProofContract]]:
    """Admit a copy recording one proven cell under the running validator, valid this year and next."""
    _, proof = proven_cell
    today = today_madrid()
    contract = SnapshotProofContract(
        closure, validator_digest(closure), date(today.year, 1, 1), date(today.year + 1, 12, 31)
    )
    reader = SQLiteAuthorityReader(
        republished_authority(tmp_path / "proven", statements=_proof_rows(contract, (proof,))), max_connections=1
    )
    try:
        yield reader, contract
    finally:
        reader.close()


def test_the_reader_returns_the_recorded_contract_and_proof(
    proven_reader: tuple[SQLiteAuthorityReader, SnapshotProofContract],
    proven_cell: tuple[_Cell, SnapshotCrossCheckProof],
) -> None:
    reader, contract = proven_reader
    _, proof = proven_cell

    assert reader.snapshot_proof_contract() == contract
    assert reader.snapshot_proof(proof.key) == proof
    other_grades = (grade for grade in RegistryAuthorityGrade if grade is not proof.key.grade)
    assert all(reader.snapshot_proof(replace(proof.key, grade=grade)) is None for grade in other_grades)


def test_a_usable_proof_skips_every_cross_check_and_builds_the_same_snapshot(
    proven_reader: tuple[SQLiteAuthorityReader, SnapshotProofContract],
    monkeypatch: pytest.MonkeyPatch,
    proven_cell: tuple[_Cell, SnapshotCrossCheckProof],
    tmp_path: Path,
) -> None:
    reader, _ = proven_reader
    cell, _ = proven_cell
    modelo_id, filing_year, period, grade = cell
    proofless = SQLiteAuthorityReader(republished_authority(tmp_path / "proofless"), max_connections=1)
    try:
        full = PinnedAuthorityOperation(proofless, proofless.pin()).build_unretained_snapshot(
            modelo_id, filing_year=filing_year, period=period, grade=grade
        )
    finally:
        proofless.close()
    counts = count_cross_checks(monkeypatch)

    proven = _snapshot(PinnedAuthorityOperation(reader, reader.pin()), cell)

    assert counts == [0] * len(counts)
    assert proven == full


def test_a_request_outside_the_proven_set_runs_every_cross_check(
    proven_reader: tuple[SQLiteAuthorityReader, SnapshotProofContract],
    monkeypatch: pytest.MonkeyPatch,
    proven_cell: tuple[_Cell, SnapshotCrossCheckProof],
) -> None:
    reader, _ = proven_reader
    cell, _ = proven_cell
    modelo_id, filing_year, period, grade = cell
    operation = PinnedAuthorityOperation(reader, reader.pin())
    counts = count_cross_checks(monkeypatch)

    operation.snapshot(modelo_id, filing_year=filing_year, period=period, on=date(filing_year, 12, 31), grade=grade)
    assert all(count == 1 for count in counts), counts

    lower_grades = tuple(RegistryAuthorityGrade)[: tuple(RegistryAuthorityGrade).index(grade)]
    for lower in lower_grades:
        counts[:] = [0] * len(counts)
        _snapshot(operation, cell, grade=lower)
        assert all(count == 1 for count in counts), (lower, counts)


def test_a_date_outside_the_window_runs_every_cross_check(
    proven_reader: tuple[SQLiteAuthorityReader, SnapshotProofContract],
    monkeypatch: pytest.MonkeyPatch,
    proven_cell: tuple[_Cell, SnapshotCrossCheckProof],
) -> None:
    reader, contract = proven_reader
    cell, _ = proven_cell
    assert contract.window_to is not None
    after = contract.window_to + timedelta(days=1)
    counts = count_cross_checks(monkeypatch)

    with frozen_clock(datetime(after.year, after.month, after.day, 12, tzinfo=UTC)):
        _snapshot(PinnedAuthorityOperation(reader, reader.pin()), cell)

    assert all(count == 1 for count in counts), counts


def test_a_changed_validator_runs_every_cross_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    closure: tuple[ValidatorSource, ...],
    proven_cell: tuple[_Cell, SnapshotCrossCheckProof],
) -> None:
    cell, proof = proven_cell
    recorded = (replace(closure[0], sha256="0" * 64), *closure[1:])
    contract = SnapshotProofContract(recorded, validator_digest(recorded), None, None)
    reader = SQLiteAuthorityReader(
        republished_authority(tmp_path / "other-validator", statements=_proof_rows(contract, (proof,))),
        max_connections=1,
    )
    try:
        counts = count_cross_checks(monkeypatch)

        _snapshot(PinnedAuthorityOperation(reader, reader.pin()), cell)

        assert all(count == 1 for count in counts), counts
    finally:
        reader.close()


def test_a_proof_naming_another_revision_runs_every_cross_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    closure: tuple[ValidatorSource, ...],
    proven_cell: tuple[_Cell, SnapshotCrossCheckProof],
) -> None:
    cell, proof = proven_cell
    contract = SnapshotProofContract(closure, validator_digest(closure), None, None)
    stale = SnapshotCrossCheckProof(proof.key, f"{proof.revision_id}-other")
    reader = SQLiteAuthorityReader(
        republished_authority(tmp_path / "stale", statements=_proof_rows(contract, (stale,))), max_connections=1
    )
    try:
        counts = count_cross_checks(monkeypatch)

        _snapshot(PinnedAuthorityOperation(reader, reader.pin()), cell)

        assert all(count == 1 for count in counts), counts
    finally:
        reader.close()


def test_a_database_that_already_records_proofs_cannot_be_swept(
    proven_reader: tuple[SQLiteAuthorityReader, SnapshotProofContract],
) -> None:
    reader, _ = proven_reader

    with pytest.raises(SnapshotProofPublicationError, match="records no proof contract yet"):
        prove_snapshot_selectors(PinnedAuthorityOperation(reader, reader.pin()))
