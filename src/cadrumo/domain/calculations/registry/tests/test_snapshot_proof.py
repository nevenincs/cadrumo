"""Snapshot cross-check proofs: the validator closure, proof keys and the proof-bearing build.

Every case runs against the published generation through the real reader,
selector and validator. The cross-checks a proof replaces are observed by
wrapping each entry of the validator's own check registry so it counts its
calls while still running the original check.
"""

from __future__ import annotations

import importlib.util
import re
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import date

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.errors.hierarchy import CadrumoError, InternalInvariantError
from .....core.time.clock import today_madrid
from .. import snapshot as snapshot_module
from ..authority import PinnedAuthorityOperation
from ..authority_location import bundled_authority_descriptor_path
from ..authority_store import SQLiteAuthorityReader
from ..errors import RegistryValidationError
from ..facts.resolution import GovernedFactQuery, ResolvedGovernedFact
from ..facts.schema import GovernedFact
from ..governed_fact_scope import GovernedFactSource, validating_governed_facts
from ..ids import RevisionId
from ..schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from ..snapshot_globals import SupportedFilingYearsCatalogue
from ..snapshot_proof import (
    SnapshotCrossCheckProof,
    SnapshotProofContract,
    SnapshotProofPublicationError,
    ValidatorSource,
    prove_snapshot_selectors,
    runtime_validator_matches,
    snapshot_proof_key,
    snapshot_validator_closure,
    validator_digest,
)
from ..temporal import ModeloRevisionDirectory, select_revision_metadata
from .snapshot_proof_support import count_cross_checks

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EVENT_SELECTOR = "EVENT-N"


@pytest.fixture(scope="module")
def reader() -> Iterator[SQLiteAuthorityReader]:
    reader = SQLiteAuthorityReader(bundled_authority_descriptor_path())
    try:
        yield reader
    finally:
        reader.close()


@pytest.fixture
def operation(reader: SQLiteAuthorityReader) -> PinnedAuthorityOperation:
    return PinnedAuthorityOperation(reader, reader.pin())


@pytest.fixture(scope="module")
def closure() -> tuple[ValidatorSource, ...]:
    return snapshot_validator_closure()


def _first_passing_cell(operation: PinnedAuthorityOperation) -> tuple[str, int, str, RegistryAuthorityGrade]:
    """Return the first declared cell, in declaration order, with the strictest grade it passes."""
    support = operation.supported_filing_years()
    for modelo_id in operation.modelo_ids():
        directory = operation.modelo_directory(modelo_id)
        for filing_year in range(support.floor, support.horizon + 1):
            for period in directory.revisions[0].period_selector.declared_periods:
                try:
                    select_revision_metadata(directory, filing_year=filing_year, period=period)
                except CadrumoError:
                    continue
                for grade in reversed(tuple(RegistryAuthorityGrade)):
                    try:
                        operation.build_unretained_snapshot(
                            modelo_id, filing_year=filing_year, period=period, grade=grade
                        )
                    except RegistryValidationError:
                        continue
                    return modelo_id, filing_year, period, grade
    raise AssertionError("the published generation declares no passing snapshot cell")


@pytest.fixture(scope="module")
def passing_cell(reader: SQLiteAuthorityReader) -> tuple[str, int, str, RegistryAuthorityGrade]:
    return _first_passing_cell(PinnedAuthorityOperation(reader, reader.pin()))


@dataclass(frozen=True, slots=True)
class _ValidatorInputs:
    """The exact arguments the pinned operation hands to the validator for one request."""

    modelo: ModeloDefinition
    catalogues: RegistryCatalogues
    filing_year: int
    period: str
    grade: RegistryAuthorityGrade
    revision_directory: ModeloRevisionDirectory | None

    def build(
        self,
        *,
        on: date | None = None,
        revision_id: RevisionId | None = None,
        proof: SnapshotCrossCheckProof | None = None,
    ) -> RegistrySnapshot:
        return snapshot_module.build_validated_snapshot(
            self.modelo,
            self.catalogues,
            filing_year=self.filing_year,
            period=self.period,
            on=on,
            revision_id=revision_id,
            grade=self.grade,
            revision_directory=self.revision_directory,
            proof=proof,
        )


def _captured_inputs(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    cell: tuple[str, int, str, RegistryAuthorityGrade],
) -> tuple[_ValidatorInputs, RegistrySnapshot]:
    """Observe the arguments the operation passes to the real validator for ``cell``."""
    real = snapshot_module.build_validated_snapshot
    captured: list[_ValidatorInputs] = []

    def observed(
        modelo: ModeloDefinition,
        catalogues: RegistryCatalogues,
        *,
        filing_year: int,
        period: str,
        on: date | None = None,
        revision_id: RevisionId | None = None,
        grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
        revision_directory: ModeloRevisionDirectory | None = None,
        proof: SnapshotCrossCheckProof | None = None,
    ) -> RegistrySnapshot:
        captured.append(_ValidatorInputs(modelo, catalogues, filing_year, period, grade, revision_directory))
        return real(
            modelo,
            catalogues,
            filing_year=filing_year,
            period=period,
            on=on,
            revision_id=revision_id,
            grade=grade,
            revision_directory=revision_directory,
            proof=proof,
        )

    modelo_id, filing_year, period, grade = cell
    with monkeypatch.context() as patch:
        patch.setattr(snapshot_module, "build_validated_snapshot", observed)
        full = operation.build_unretained_snapshot(modelo_id, filing_year=filing_year, period=period, grade=grade)
    (inputs,) = captured
    return inputs, full


def test_the_validator_closure_is_rooted_at_the_snapshot_validator_and_deterministic(
    closure: tuple[ValidatorSource, ...],
) -> None:
    modules = [source.module for source in closure]
    expected_roots = {
        snapshot_module.__name__,
        *(
            importlib.util.resolve_name(name, snapshot_module.__package__ or "")
            for name in snapshot_module._CROSS_DOMAIN_CHECK_MODULES
        ),
    }

    assert expected_roots <= set(modules)
    assert modules == sorted(modules)
    assert len(set(modules)) == len(modules)
    assert all(module == "cadrumo" or module.startswith("cadrumo.") for module in modules)
    assert snapshot_validator_closure() == closure
    assert validator_digest(reversed(closure)) == validator_digest(closure)


def test_the_running_validator_matches_its_own_closure(closure: tuple[ValidatorSource, ...]) -> None:
    contract = SnapshotProofContract(closure, validator_digest(closure), None, None)

    assert runtime_validator_matches(contract)


def test_a_changed_source_digest_turns_the_validator_off(closure: tuple[ValidatorSource, ...]) -> None:
    tampered = (replace(closure[0], sha256="0" * 64), *closure[1:])

    assert not runtime_validator_matches(SnapshotProofContract(tampered, validator_digest(tampered), None, None))


def test_an_unknown_module_turns_the_validator_off(closure: tuple[ValidatorSource, ...]) -> None:
    extended = (*closure, ValidatorSource("cadrumo.domain.calculations.registry.no_such_module", "0" * 64))

    assert not runtime_validator_matches(SnapshotProofContract(extended, validator_digest(extended), None, None))


def test_a_contract_whose_digest_does_not_name_its_sources_is_not_trusted(
    closure: tuple[ValidatorSource, ...],
) -> None:
    assert not runtime_validator_matches(SnapshotProofContract(closure, "0" * 64, None, None))
    assert not runtime_validator_matches(SnapshotProofContract((), validator_digest(()), None, None))


def _directories(operation: PinnedAuthorityOperation) -> Iterator[ModeloRevisionDirectory]:
    return (operation.modelo_directory(modelo_id) for modelo_id in operation.modelo_ids())


def test_a_proof_key_takes_the_declared_spelling_of_a_lower_case_period(operation: PinnedAuthorityOperation) -> None:
    revision, token = next(
        (revision, token)
        for directory in _directories(operation)
        for revision in directory.revisions
        for token in revision.period_selector.declared_periods
        if token.lower() != token and token.upper() != _EVENT_SELECTOR
    )

    key = snapshot_proof_key(
        revision, modelo_id="m", filing_year=2025, period=token.lower(), grade=RegistryAuthorityGrade.FILING
    )

    assert key.period == token


def test_a_proof_key_keeps_a_concrete_event_and_the_symbolic_event_selector(
    operation: PinnedAuthorityOperation,
) -> None:
    revision = next(
        revision
        for directory in _directories(operation)
        for revision in directory.revisions
        if _EVENT_SELECTOR in revision.period_selector.declared_periods
    )

    def period(requested: str) -> str:
        return snapshot_proof_key(
            revision, modelo_id="m", filing_year=2025, period=requested, grade=RegistryAuthorityGrade.FILING
        ).period

    assert period("EVENT-3") == "EVENT-3"
    assert period("event-3") == "EVENT-3"
    assert period(_EVENT_SELECTOR.lower()) == _EVENT_SELECTOR


def test_the_cross_check_registry_is_ordered_by_assembly_stage() -> None:
    stages = [check.stage for check in snapshot_module._SNAPSHOT_CROSS_CHECKS]
    ladder = list(type(stages[0]))

    assert [ladder.index(stage) for stage in stages] == sorted(ladder.index(stage) for stage in stages)


def test_a_matching_proof_builds_the_same_snapshot_without_running_any_cross_check(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    passing_cell: tuple[str, int, str, RegistryAuthorityGrade],
) -> None:
    inputs, _ = _captured_inputs(operation, monkeypatch, passing_cell)
    modelo_id, filing_year, period, grade = passing_cell
    counts = count_cross_checks(monkeypatch)
    with validating_governed_facts(operation):
        full = inputs.build()
    assert all(count == 1 for count in counts), counts
    proof = SnapshotCrossCheckProof(
        snapshot_proof_key(full.revision, modelo_id=modelo_id, filing_year=filing_year, period=period, grade=grade),
        full.revision.id,
    )

    counts[:] = [0] * len(counts)
    proven = inputs.build(proof=proof)

    assert counts == [0] * len(counts)
    assert proven == full


def test_a_proof_for_another_request_is_refused(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    passing_cell: tuple[str, int, str, RegistryAuthorityGrade],
) -> None:
    inputs, full = _captured_inputs(operation, monkeypatch, passing_cell)
    modelo_id, filing_year, period, grade = passing_cell
    key = snapshot_proof_key(full.revision, modelo_id=modelo_id, filing_year=filing_year, period=period, grade=grade)
    other_grades = (other for other in RegistryAuthorityGrade if other is not grade)
    mismatches = (
        SnapshotCrossCheckProof(key, f"{full.revision.id}-other"),
        SnapshotCrossCheckProof(replace(key, modelo_id=f"{modelo_id}-other"), full.revision.id),
        SnapshotCrossCheckProof(replace(key, filing_year=filing_year + 1), full.revision.id),
        SnapshotCrossCheckProof(replace(key, period=f"{period}-other"), full.revision.id),
        *(SnapshotCrossCheckProof(replace(key, grade=other), full.revision.id) for other in other_grades),
    )

    for proof in mismatches:
        with pytest.raises(InternalInvariantError, match="does not cover request"):
            inputs.build(proof=proof)


def test_a_proof_never_covers_an_explicit_date_or_revision(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    passing_cell: tuple[str, int, str, RegistryAuthorityGrade],
) -> None:
    inputs, full = _captured_inputs(operation, monkeypatch, passing_cell)
    modelo_id, filing_year, period, grade = passing_cell
    proof = SnapshotCrossCheckProof(
        snapshot_proof_key(full.revision, modelo_id=modelo_id, filing_year=filing_year, period=period, grade=grade),
        full.revision.id,
    )

    with pytest.raises(InternalInvariantError, match="without on or revision_id"):
        inputs.build(on=date(filing_year, 12, 31), proof=proof)
    with pytest.raises(InternalInvariantError, match="without on or revision_id"):
        inputs.build(revision_id=full.revision.id, proof=proof)


def test_the_published_proofless_generation_reports_no_proofs_and_validates_fully(
    reader: SQLiteAuthorityReader,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    passing_cell: tuple[str, int, str, RegistryAuthorityGrade],
) -> None:
    modelo_id, filing_year, period, grade = passing_cell
    selected = select_revision_metadata(operation.modelo_directory(modelo_id), filing_year=filing_year, period=period)
    counts = count_cross_checks(monkeypatch)

    operation.build_unretained_snapshot(modelo_id, filing_year=filing_year, period=period, grade=grade)

    assert reader.snapshot_proof_contract() is None
    assert operation.snapshot_proof_contract() is None
    assert (
        reader.snapshot_proof(
            snapshot_proof_key(selected, modelo_id=modelo_id, filing_year=filing_year, period=period, grade=grade)
        )
        is None
    )
    assert all(count == 1 for count in counts), counts


class _OneModeloOperation:
    """The real pinned operation with its modelo enumeration narrowed to one declared modelo."""

    def __init__(self, operation: PinnedAuthorityOperation, modelo_id: str, *, failing_period: str | None = None):
        self._operation = operation
        self._modelo_id = modelo_id
        self._failing_period = failing_period

    def modelo_ids(self) -> tuple[str, ...]:
        return (self._modelo_id,)

    def modelo_directory(self, modelo_id: str, /) -> ModeloRevisionDirectory:
        return self._operation.modelo_directory(modelo_id)

    def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
        return self._operation.supported_filing_years()

    def governed_fact(self, fact_id: str, /) -> GovernedFact:
        return self._operation.governed_fact(fact_id)

    def resolve_governed_fact(self, query: GovernedFactQuery, /) -> ResolvedGovernedFact:
        return self._operation.resolve_governed_fact(query)

    def snapshot_proof_contract(self) -> SnapshotProofContract | None:
        return self._operation.snapshot_proof_contract()

    def build_unretained_snapshot(
        self,
        modelo_id: str,
        /,
        *,
        filing_year: int,
        period: str,
        grade: RegistryAuthorityGrade,
        governed_facts: GovernedFactSource | None = None,
    ) -> RegistrySnapshot:
        if period == self._failing_period:
            raise RegistryValidationError(f"declared cell {modelo_id} {filing_year} {period} is broken")
        return self._operation.build_unretained_snapshot(
            modelo_id, filing_year=filing_year, period=period, grade=grade, governed_facts=governed_facts
        )


def test_the_sweep_records_exactly_the_passing_cells_with_their_selected_revision(
    operation: PinnedAuthorityOperation,
    closure: tuple[ValidatorSource, ...],
    passing_cell: tuple[str, int, str, RegistryAuthorityGrade],
) -> None:
    modelo_id = passing_cell[0]
    directory = operation.modelo_directory(modelo_id)
    support = operation.supported_filing_years()

    proven = prove_snapshot_selectors(_OneModeloOperation(operation, modelo_id))

    expected: list[SnapshotCrossCheckProof] = []
    for filing_year in range(support.floor, support.horizon + 1):
        for period in sorted({p for r in directory.revisions for p in r.period_selector.declared_periods}):
            try:
                selected = select_revision_metadata(directory, filing_year=filing_year, period=period)
            except CadrumoError:
                continue
            for grade in RegistryAuthorityGrade:
                try:
                    built = operation.build_unretained_snapshot(
                        modelo_id, filing_year=filing_year, period=period, grade=grade
                    )
                except RegistryValidationError:
                    continue
                key = snapshot_proof_key(
                    selected, modelo_id=modelo_id, filing_year=filing_year, period=period, grade=grade
                )
                expected.append(SnapshotCrossCheckProof(key, built.revision.id))
    assert proven.proofs == tuple(expected)
    assert proven.proofs
    assert proven.contract.validator_sources == closure
    assert proven.contract.validator_digest == validator_digest(closure)
    assert proven.contract.admits_date(today_madrid())


def test_a_failing_declared_cell_blocks_the_sweep(
    operation: PinnedAuthorityOperation,
    passing_cell: tuple[str, int, str, RegistryAuthorityGrade],
) -> None:
    modelo_id, _, period, _ = passing_cell

    expected = f"declared cell {re.escape(modelo_id)} .* {re.escape(period)} is broken"
    with pytest.raises(SnapshotProofPublicationError, match=expected):
        prove_snapshot_selectors(_OneModeloOperation(operation, modelo_id, failing_period=period))
