"""A served declaration form is reused only while every input it is read from is unchanged.

The memo key names the profile, the declaration, a digest of every stored row
of the profile, the authority generation, the public operation contracts, the
language, the Madrid date and the edit admission without its own identity and
lifetime. Each test below plants a marked form under the key a real read
computes with exactly one of those parts changed and proves the read does not
serve it; the same plant under the exact key is served, so the key alone
decides reuse. A served form is the one a fresh read returns, but for the
baseline every admission issues anew.
"""

from __future__ import annotations

import asyncio
import contextvars
import dataclasses
import inspect
import json
import logging
import threading
import time
from collections.abc import Callable, Hashable, Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from time import perf_counter
from typing import Any, cast, override
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...adapters.persistence.storage.secure_object_namespaces import OPERATION_SECURE_REFERENCE_NAMESPACE
from ...application.modelo.edit_models import (
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloScalarEditIntentV1,
)
from ...application.modelo.workbench_form_read_memo import WorkbenchFormReadKey
from ...application.modelo.workbench_operations import (
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloWorkbenchFormExecutor,
    ModeloWorkbenchFormRequest,
)
from ...application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1
from ...application.modelo.workbench_read import (
    ModeloWorkbenchReadPorts,
    admit_workbench_form_edit,
    read_modelo_workbench_form,
)
from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.operations.owner import OperationExecutorContext
from ...application.workbench_capture_memory import WorkbenchCaptureMemoryOwner, WorkbenchMemoSlot
from ...core.casilla_id import validated_casilla_id
from ...core.classification.policies import SensitivityClass
from ...core.diagnostic_log import DiagnosticFormatter
from ...core.external_constants import OutputLanguage
from ...core.hashing import content_hash_hex
from ...core.logging import LOG_FILE_FORMAT
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..operation_composition_inputs import build_modelo_workbench_read_ports
from .executor_context_stand_ins import RecordedEvents, RecordedOperands, UninterruptedCancellation
from .modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from .production_operation_registry import production_operation_registry

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LIFETIME = frozenset({"baseline_id", "issued_at", "expires_at"})

_OPERATIONS_LOGGER = "cadrumo.application.modelo.workbench_operations"

_FORM_INPUT_PORTS = frozenset(
    {
        "work_units",
        "calculations",
        "verifications",
        "activity_assets",
        "borrador_snapshots",
        "bucket_events",
        "filings",
        "own_accounts",
        "credit_resolutions",
        "m303_arrivals",
        "profile",
        "ledger",
        "reconciliation_sources",
        "observations",
        "store_epoch",
    }
)
"""Every port a form is read through; each reads the one profile store ``store_epoch`` digests."""

_FORM_READ_PARAMETERS = frozenset(
    {"work_unit_id", "bucket_id", "ports", "operation", "operation_contracts", "language", "admission"}
)

_SET_06 = ModeloScalarEditIntentV1(
    address=ModeloEditScalarAddressV1(casilla_id=validated_casilla_id("06")),
    kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
    value="100",
)


@dataclass(frozen=True, slots=True)
class _Context:
    identity: OperationIdentity
    authority_operation: PinnedAuthorityOperation
    events: RecordedEvents = field(default_factory=RecordedEvents)
    cancellation: UninterruptedCancellation = field(default_factory=UninterruptedCancellation)
    operands: RecordedOperands = field(default_factory=RecordedOperands)


class _RecordingSlot(WorkbenchMemoSlot[WorkbenchFormReadKey, ModeloWorkbenchFormProjectionV1]):
    """The session's form slot, recording each key a read asks it for and each form it builds."""

    def __init__(self) -> None:
        super().__init__()
        self.keys: list[WorkbenchFormReadKey] = []
        self.builds = 0
        self.recording = False

    @override
    def reuse(
        self, key: WorkbenchFormReadKey, build: Callable[[], ModeloWorkbenchFormProjectionV1]
    ) -> ModeloWorkbenchFormProjectionV1:
        if not self.recording:
            return super().reuse(key, build)
        self.keys.append(key)

        def counted() -> ModeloWorkbenchFormProjectionV1:
            self.builds += 1
            return build()

        return super().reuse(key, counted)


@dataclass(slots=True)
class _Reader:
    work: SeededOperatorWork
    owner: WorkbenchCaptureMemoryOwner
    recorder: _RecordingSlot = field(default_factory=_RecordingSlot)

    def __post_init__(self) -> None:
        self.owner.for_profile(self.work.work_unit.bucket_id).form_read = self.recorder

    @property
    def keys(self) -> list[WorkbenchFormReadKey]:
        return self.recorder.keys

    @property
    def builds(self) -> int:
        return self.recorder.builds

    def plant(self, key: WorkbenchFormReadKey, projection: ModeloWorkbenchFormProjectionV1) -> None:
        self.recorder.clear()
        self.recorder.reuse(key, lambda: projection)

    def read(self, language: OutputLanguage = OutputLanguage.EN) -> ModeloWorkbenchFormProjectionV1:
        self.recorder.recording = True
        try:
            return _execute(self.work, self.owner, language)
        finally:
            self.recorder.recording = False


def _execute(
    work: SeededOperatorWork, owner: WorkbenchCaptureMemoryOwner | None, language: OutputLanguage
) -> ModeloWorkbenchFormProjectionV1:
    contracts = production_operation_registry().public_contract_set
    executor = ModeloWorkbenchFormExecutor(
        ports_factory=build_modelo_workbench_read_ports, contracts=lambda: contracts, capture_memory=owner
    )
    payload = ModeloWorkbenchFormRequest(
        profile_id=UUID(work.work_unit.bucket_id), work_unit_id=work.work_unit_id, output_language=language
    )
    definition_id = MODELO_WORK_FORM_OPERATION_DEFINITION_ID
    context = _Context(
        identity=OperationIdentity(
            operation_id=content_hash_hex({"read": definition_id, "nonce": str(uuid4())}),
            definition_id=definition_id,
            subject_ref=work.work_unit_id,
        ),
        authority_operation=work.operation,
    )
    request = OperationRequest(definition_id=definition_id, subject_ref=work.work_unit_id, payload=payload)
    asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))
    (result,) = context.operands.results
    assert isinstance(result, ModeloWorkbenchFormProjectionV1)
    return result


def _without_lifetime(projection: ModeloWorkbenchFormProjectionV1) -> dict[str, Any]:
    dumped = projection.model_dump(mode="json")
    if dumped["admitted_baseline"] is not None:
        dumped["admitted_baseline"] = {
            name: value for name, value in dumped["admitted_baseline"].items() if name not in _LIFETIME
        }
    return dumped


def _marked(projection: ModeloWorkbenchFormProjectionV1) -> ModeloWorkbenchFormProjectionV1:
    return projection.model_copy(update={"rules_incomplete": not projection.rules_incomplete})


@pytest.fixture
def reader(tmp_path: Path) -> Iterator[_Reader]:
    with seeded_operator_work(tmp_path) as work:
        work.recalculate()
        owner = WorkbenchCaptureMemoryOwner()
        yield _Reader(work=work, owner=owner)
        owner.close()


def test_a_second_read_of_an_unchanged_form_is_served_and_says_what_a_fresh_read_says(reader: _Reader) -> None:
    reader.read()
    served = reader.read()
    fresh = _execute(reader.work, None, OutputLanguage.EN)

    assert reader.builds == 1
    assert reader.keys[0] == reader.keys[1]
    assert _without_lifetime(served) == _without_lifetime(fresh)
    assert served.model_dump_json(exclude={"admitted_baseline"}) == fresh.model_dump_json(exclude={"admitted_baseline"})


def test_a_served_form_carries_the_baseline_its_own_read_admitted(reader: _Reader) -> None:
    first = reader.read()
    second = reader.read()

    assert reader.builds == 1
    assert first.admitted_baseline is not None and second.admitted_baseline is not None
    assert first.admitted_baseline.baseline_id != second.admitted_baseline.baseline_id


_KEY_PARTS: dict[str, Callable[[WorkbenchFormReadKey], Hashable]] = {
    "profile_id": lambda key: uuid4(),
    "work_unit_id": lambda key: "f" * len(key.work_unit_id),
    "store_epoch": lambda key: "0" * len(key.store_epoch),
    "logical_generation": lambda key: "0" * len(key.logical_generation),
    "contract_set_digest": lambda key: "0" * len(key.contract_set_digest),
    "language": lambda key: OutputLanguage.ES if key.language is not OutputLanguage.ES else OutputLanguage.EN,
    "as_of": lambda key: key.as_of - timedelta(days=1),
    "admission": lambda key: key.admission + " ",
}


def test_every_field_of_the_key_is_one_this_suite_plants_a_miss_for() -> None:
    assert {part.name for part in dataclasses.fields(WorkbenchFormReadKey)} == set(_KEY_PARTS)


@pytest.mark.parametrize("part", sorted(_KEY_PARTS))
def test_a_form_kept_under_a_key_differing_in_one_part_is_not_served(reader: _Reader, part: str) -> None:
    current = reader.read()
    key = reader.keys[-1]
    planted = _marked(current)
    reader.plant(dataclasses.replace(key, **{part: _KEY_PARTS[part](key)}), planted)

    after = reader.read()

    assert reader.keys[-1] == key
    assert after.rules_incomplete == current.rules_incomplete, f"a form kept under another {part} was served"
    assert reader.builds == 2


def test_a_form_kept_under_the_exact_key_is_served(reader: _Reader) -> None:
    current = reader.read()
    planted = _marked(current)
    reader.plant(reader.keys[-1], planted)

    assert reader.read().rules_incomplete != current.rules_incomplete


def test_a_write_to_the_profile_moves_the_epoch_and_the_next_read_is_fresh(reader: _Reader) -> None:
    before = reader.read()
    applied = reader.work.apply(scalar=(_SET_06,))
    assert applied.refusal is None

    after = reader.read()

    assert reader.keys[0].store_epoch != reader.keys[1].store_epoch
    assert reader.builds == 2
    assert after.calculation_revision_id != before.calculation_revision_id


def _logged_fields(record: logging.LogRecord) -> dict[str, object]:
    """The fields as the diagnostic log file writes them, after its field allowlist."""
    fields: object = json.loads(DiagnosticFormatter(LOG_FILE_FORMAT).format(record).split(" | ", 1)[1])
    assert isinstance(fields, dict), fields
    return cast("dict[str, object]", fields)


def _memo_reads(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    return [_logged_fields(record) for record in caplog.records if record.getMessage() == "workbench_form_memo_read"]


def test_each_read_logs_whether_it_was_served_and_which_key_parts_moved(
    reader: _Reader, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger=_OPERATIONS_LOGGER)
    reader.read()
    reader.read()
    applied = reader.work.apply(scalar=(_SET_06,))
    assert applied.refusal is None
    reader.read()
    reader.read(OutputLanguage.ES)

    reads = _memo_reads(caplog)
    served = [(read.get("outcome"), read.get("changed_key_parts")) for read in reads]
    assert served == [("empty", ""), ("hit", ""), ("miss", "store_epoch,admission"), ("miss", "language")], reads
    for read in reads:
        built = read["outcome"] != "hit"
        timed = {"epoch_ms", "admission_ms", *(("form_ms", "projection_ms") if built else ())}
        assert all(isinstance(read.get(name), int) for name in timed), read
        assert built or not {"form_ms", "projection_ms"} & read.keys(), read


def test_a_rebuilt_read_logs_whether_the_projection_kept_for_its_form_served_it(
    reader: _Reader, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger=_OPERATIONS_LOGGER)
    reader.read()
    # The form memo forgets its form while the projection kept for that same form stays.
    reader.recorder.clear()
    reader.read()
    reader.read()
    applied = reader.work.apply(scalar=(_SET_06,))
    assert applied.refusal is None
    reader.read()

    reused = [(read.get("outcome"), read.get("projection_pair_reused")) for read in _memo_reads(caplog)]
    assert reused == [("empty", False), ("empty", True), ("hit", None), ("miss", False)], reused


def test_another_language_is_read_afresh(reader: _Reader) -> None:
    reader.read(OutputLanguage.EN)
    reader.read(OutputLanguage.ES)

    assert reader.builds == 2


def test_the_form_is_read_through_no_port_the_store_epoch_does_not_cover() -> None:
    declared = {port.name for port in dataclasses.fields(ModeloWorkbenchReadPorts)}

    assert declared == _FORM_INPUT_PORTS, (
        "a new form input: make the store epoch cover it, or add it to the memo key, then list it here"
    )


def test_the_form_read_takes_no_input_the_key_does_not_name() -> None:
    parameters = set(inspect.signature(read_modelo_workbench_form).parameters)
    admission = set(inspect.signature(admit_workbench_form_edit).parameters)

    assert parameters == _FORM_READ_PARAMETERS, "a new form read input belongs in the memo key first"
    assert admission <= _FORM_READ_PARAMETERS


def test_the_namespace_the_store_epoch_leaves_out_is_one_no_form_read_queries(reader: _Reader) -> None:
    namespace = OPERATION_SECURE_REFERENCE_NAMESPACE.namespace
    queried: list[str] = []

    def observe(_conn: object, _cursor: object, statement: str, parameters: object, *_rest: object) -> None:
        if namespace in repr(parameters) and "NOT IN" not in statement.upper():
            queried.append(statement)

    event.listen(Engine, "before_cursor_execute", observe)
    try:
        reader.read()
        read_queries = list(queried)
        secure_object_repository_for_bucket(reader.work.work_unit.bucket_id).load(
            namespace, "0" * 64, expected_class=SensitivityClass.FINANCIAL, max_supported_version=1
        )
    finally:
        event.remove(Engine, "before_cursor_execute", observe)

    assert reader.builds == 1
    assert read_queries == []
    assert queried, "a load of that namespace is seen, so the empty read above is evidence"


# A page return in the window allows 3000 ms end to end, of which the host and window take part.
_PAGE_RETURN_WORKER_BUDGET_SECONDS = 1.0


def _write_06(reader: _Reader, value: str) -> None:
    intent = _SET_06.model_copy(update={"value": value})
    assert reader.work.apply(scalar=(intent,)).refusal is None


def _refreshed(owner: WorkbenchCaptureMemoryOwner) -> None:
    thread = owner.refresh_settled_form()
    assert thread is not None, "a session that was served a form must refresh it"
    thread.join()


def test_a_form_returned_to_after_a_write_settles_is_served_from_its_refresh(reader: _Reader) -> None:
    before = reader.read()
    # An export's bucket event moves the epoch just as this write does.
    _write_06(reader, "100")
    _refreshed(reader.owner)

    began = perf_counter()
    returned = reader.read()
    elapsed = perf_counter() - began

    assert reader.builds == 1, "the read returning to the form built it again instead of serving the refresh"
    assert reader.keys[0].store_epoch != reader.keys[1].store_epoch
    assert returned.calculation_revision_id != before.calculation_revision_id
    fresh = _execute(reader.work, None, OutputLanguage.EN)
    assert returned.model_dump_json(exclude={"admitted_baseline"}) == fresh.model_dump_json(
        exclude={"admitted_baseline"}
    )
    assert elapsed <= _PAGE_RETURN_WORKER_BUDGET_SECONDS, elapsed


class _WritingSlot(_RecordingSlot):
    """The session's form slot, writing to the profile while a refresh builds."""

    def __init__(self, write: Callable[[], None]) -> None:
        super().__init__()
        self._write = write

    @override
    def refresh(
        self,
        key: WorkbenchFormReadKey,
        build: Callable[[], ModeloWorkbenchFormProjectionV1],
        *,
        current: Callable[[], bool],
    ) -> bool:
        def writing() -> ModeloWorkbenchFormProjectionV1:
            self._write()
            return build()

        return super().refresh(key, writing, current=current)


def test_a_write_while_the_form_is_refreshed_makes_the_returning_read_build_it(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        work.recalculate()
        owner = WorkbenchCaptureMemoryOwner()
        reader = _Reader(work=work, owner=owner)
        reader.read()
        _write_06(reader, "100")
        writing = _WritingSlot(lambda: _write_06(reader, "200"))
        owner.for_profile(work.work_unit.bucket_id).form_read = writing
        reader.recorder = writing
        _refreshed(owner)

        assert writing.kept_key() is None, "a refresh overtaken by a write kept its form"
        returned = reader.read()
        fresh = _execute(work, None, OutputLanguage.EN)
        owner.close()

    assert writing.builds == 1
    assert returned.model_dump_json(exclude={"admitted_baseline"}) == fresh.model_dump_json(
        exclude={"admitted_baseline"}
    )


def test_an_ended_session_refreshes_nothing_and_serves_nothing_refreshed(reader: _Reader) -> None:
    reader.read()
    _write_06(reader, "100")
    reader.owner.close()

    assert reader.owner.refresh_settled_form() is None
    reader.recorder = _RecordingSlot()
    reader.owner.for_profile(reader.work.work_unit.bucket_id).form_read = reader.recorder
    reader.read()

    assert reader.builds == 1


def test_another_profile_is_handed_no_refresh_of_this_profiles_form(reader: _Reader) -> None:
    reader.read()
    _write_06(reader, "100")
    held = reader.owner.for_profile(reader.work.work_unit.bucket_id)
    other = reader.owner.for_profile(str(uuid4()))

    assert reader.owner.refresh_settled_form() is None
    assert held.refresh_form() is None
    assert other.form_read.kept_key() is None


class _JoinedSlot(_RecordingSlot):
    """The session's form slot, letting a read join the refresh before it builds."""

    def __init__(self, join: Callable[[], None]) -> None:
        super().__init__()
        self._join = join

    @override
    def refresh(
        self,
        key: WorkbenchFormReadKey,
        build: Callable[[], ModeloWorkbenchFormProjectionV1],
        *,
        current: Callable[[], bool],
    ) -> bool:
        def joined() -> ModeloWorkbenchFormProjectionV1:
            self._join()
            return build()

        return super().refresh(key, joined, current=current)


def test_a_refresh_a_returning_read_joined_finishes_while_requests_stay_busy(tmp_path: Path) -> None:
    busy = threading.Event()
    with seeded_operator_work(tmp_path) as work:
        work.recalculate()
        owner = WorkbenchCaptureMemoryOwner(deferred=busy.is_set)
        reader = _Reader(work=work, owner=owner)
        reader.read()
        _write_06(reader, "100")
        returned: list[ModeloWorkbenchFormProjectionV1] = []
        reading: list[threading.Thread] = []

        def join() -> None:
            # The returning read is the request being served; it waits for this refresh rather than building.
            busy.set()
            context = contextvars.copy_context()
            thread = threading.Thread(target=lambda: returned.append(context.run(reader.read)))
            reading.append(thread)
            thread.start()
            joined_by = time.monotonic() + 60
            while not slot.refresh_joined() and thread.is_alive():
                assert time.monotonic() < joined_by, "the returning read never joined the refresh"
                threading.Event().wait(0.01)

        slot = _JoinedSlot(join)
        owner.for_profile(work.work_unit.bucket_id).form_read = slot
        reader.recorder = slot
        _refreshed(owner)
        reading[0].join(timeout=60)
        fresh = _execute(work, None, OutputLanguage.EN)
        owner.close()

    assert slot.builds == 0, "the read that joined the refresh built the form itself"
    assert [r.model_dump_json(exclude={"admitted_baseline"}) for r in returned] == [
        fresh.model_dump_json(exclude={"admitted_baseline"})
    ]
