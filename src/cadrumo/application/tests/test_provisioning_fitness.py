"""Real-behaviour tests for the recorded fitness verdict and the status that reads it.

The runtime is a real loopback endpoint speaking the ``/api/version``,
``/api/tags``, ``/api/ps`` and ``/api/generate`` wire shapes, with a mutable
store whose digests a test replaces as new weights would. The verdict record is a real file under an isolated storage root. The
text probe is the composition port the application receives; its answer is what
varies.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

import pytest

from ...core.config import Settings, load_settings, override_settings
from ...core.hardware import AcceleratorKind
from ...core.locks_errors import LockAcquisitionError
from ...core.model_catalogue import ModelRole, default_model_runtime_id
from ...tests.loopback_llm import (
    SilentLoopbackHandler,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ..local_reader import (
    EXTRACTION_READER_ROLES,
    LocalReaderDocumentReadiness,
    LocalReaderRoleStatus,
    LocalReaderStatus,
    RoleFitnessOutcome,
    RoleFitnessState,
    admit_local_reader,
    probe_local_reader,
    read_local_reader_status,
    role_model_targets,
    verify_role_target,
)
from ..provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    DependencyStatus,
    HardwareProfile,
    SystemMemoryReading,
    probe_hardware_profile,
)
from ..provisioning_contracts import (
    LOCAL_AI_PROVISION_ACTION_ID,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
)
from ..provisioning_fitness import (
    RecordedFitnessVerdict,
    RoleFitnessVerdict,
    fitness_measurement_lock,
    fitness_verdict_path,
    read_fitness_verdict,
    record_fitness_verdict,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

GIB = 1024**3
_VISION = default_model_runtime_id(ModelRole.VISION_TRANSCRIPTION)
_TEXT = default_model_runtime_id(ModelRole.TEXT_EXTRACTION)
_MAPPING = default_model_runtime_id(ModelRole.COLUMN_ROLE_MAPPING)


class _Runtime(SilentLoopbackHandler):
    store: ClassVar[dict[str, str]] = {}
    reports_digests: ClassVar[bool] = True

    @override
    def do_GET(self) -> None:
        if self.path == "/api/version":
            write_json_response(self, {"version": "0.9.0"}, status=HTTPStatus.OK)
        elif self.path == "/api/tags":
            rows = [
                {"name": name, "size": GIB, **({"digest": digest} if self.reports_digests else {})}
                for name, digest in self.store.items()
            ]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
        elif self.path == "/api/ps":
            rows = [{"name": name, "size": GIB, "size_vram": GIB} for name in self.store]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    @override
    def do_POST(self) -> None:
        read_json_body(self)
        if self.path != "/api/generate":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        write_json_response(self, {"done": True}, status=HTTPStatus.OK)


@contextmanager
def _runtime(tmp_path: Path, **store: str) -> Generator[str]:
    _Runtime.store = dict(store) or {_TEXT: "sha256:text-1", _VISION: "sha256:vision-1"}
    _Runtime.reports_digests = True
    with (
        serving_loopback(_Runtime, path="/api/chat") as chat_url,
        override_settings(
            cadrumo_local_storage_root=tmp_path,
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_ollama_vision_model=_VISION,
            cadrumo_llm_ollama_text_model=_TEXT,
            cadrumo_llm_ollama_mapping_model=_MAPPING,
        ),
    ):
        yield chat_url


class _Probe:
    """The injected fitness port: records calls and answers a fixed verdict.

    ``during`` runs inside each call before it answers, which is where a test
    observes what holds while a measurement is in progress.
    """

    def __init__(
        self,
        verdict: RoleFitnessVerdict | None,
        *,
        during: Callable[[Settings], None] | None = None,
    ) -> None:
        # ``None`` answers a transport failure: no verdict about the model.
        self.calls: list[str] = []
        self._verdict = verdict
        self._during = during

    def __call__(self, model: str, settings: Settings) -> RoleFitnessOutcome:
        self.calls.append(model)
        if self._during is not None:
            self._during(settings)
        if self._verdict is RoleFitnessVerdict.FIT:
            return RoleFitnessOutcome(
                role=ModelRole.TEXT_EXTRACTION,
                model=model,
                fit=True,
                answer_parseable=True,
                grounded=True,
                answer_budget_tokens=1024,
                elapsed_ms=5,
            )
        condition = {
            RoleFitnessVerdict.UNFIT: ProvisioningPreconditionCondition.ROLE_MODEL_FIT_FOR_ROLE,
            RoleFitnessVerdict.TIMED_OUT: ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_WITHIN_TIMEOUT,
            None: ProvisioningPreconditionCondition.MODEL_READY,
        }[self._verdict]
        facts = {"model": model}
        return RoleFitnessOutcome(
            role=ModelRole.TEXT_EXTRACTION,
            model=model,
            fit=False,
            timed_out=self._verdict is RoleFitnessVerdict.TIMED_OUT,
            transport_failed=self._verdict is None,
            answer_budget_tokens=1024,
            elapsed_ms=5,
            facts=facts,
            precondition_verdict=provisioning_no_recovery_verdict(condition, facts=facts),
        )


def _verify_text(probe: _Probe) -> None:
    (target,) = role_model_targets((ModelRole.TEXT_EXTRACTION,))
    verify_role_target(target, text_probe=probe)


def _text_row(text_probe: _Probe | None = None) -> tuple[LocalReaderStatus, LocalReaderRoleStatus]:
    status = read_local_reader_status(roles=EXTRACTION_READER_ROLES, assess_load=False, text_probe=text_probe)
    return status, {row.role: row for row in status.roles}[ModelRole.TEXT_EXTRACTION]


def _verdict(**overrides: object) -> RecordedFitnessVerdict:
    fields: dict[str, object] = {
        "endpoint": "http://127.0.0.1:9/api/chat",
        "model": "text:1b",
        "digest": "sha256:a",
        "role": ModelRole.TEXT_EXTRACTION,
        "verdict": RoleFitnessVerdict.FIT,
        "elapsed_ms": 3,
        "recorded_at": datetime(2026, 9, 16, 12, 0, tzinfo=UTC),
    }
    fields.update(overrides)
    return RecordedFitnessVerdict.model_validate(fields)


# ---------------------------------------------------------------------------
# the record itself
# ---------------------------------------------------------------------------


def test_a_recorded_verdict_round_trips_through_the_fixed_file(tmp_path: Path) -> None:
    unfit = _verdict(
        verdict=RoleFitnessVerdict.UNFIT,
        failed_condition_id=ProvisioningPreconditionCondition.ROLE_MODEL_FIT_FOR_ROLE.value,
    )
    with override_settings(cadrumo_local_storage_root=tmp_path):
        record_fitness_verdict(unfit)
        path = fitness_verdict_path()
        read_back = read_fitness_verdict(
            endpoint=unfit.endpoint, model=unfit.model, digest=unfit.digest, role=unfit.role
        )
        other_digest = read_fitness_verdict(
            endpoint=unfit.endpoint, model=unfit.model, digest="sha256:b", role=unfit.role
        )

    assert path == tmp_path / "local-reader-fitness.json"
    assert read_back == unfit
    assert other_digest is None, "a verdict describes exact weights, never a different digest"


def test_a_new_verdict_replaces_the_old_one_for_the_same_model(tmp_path: Path) -> None:
    with override_settings(cadrumo_local_storage_root=tmp_path):
        record_fitness_verdict(_verdict(verdict=RoleFitnessVerdict.TIMED_OUT, failed_condition_id="x.y"))
        record_fitness_verdict(_verdict(digest="sha256:b"))
        record_fitness_verdict(_verdict(model="other:1b"))
        document = json.loads(fitness_verdict_path().read_text(encoding="utf-8"))

    assert document["schema_version"] == 1
    assert sorted((row["model"], row["digest"]) for row in document["verdicts"]) == [
        ("other:1b", "sha256:a"),
        ("text:1b", "sha256:b"),
    ]


def test_an_unreadable_record_reads_as_nothing_recorded_and_verify_replaces_it(tmp_path: Path) -> None:
    with _runtime(tmp_path):
        fitness_verdict_path().write_bytes(b"{not json")
        _, before = _text_row()
        _verify_text(_Probe(RoleFitnessVerdict.FIT))
        _, after = _text_row()

    assert before.fitness is RoleFitnessState.NOT_VERIFIED
    assert after.fitness is RoleFitnessState.FIT


# ---------------------------------------------------------------------------
# status reads the record; verify writes it
# ---------------------------------------------------------------------------


def test_status_without_a_recorded_verdict_is_not_verified_and_admitted(tmp_path: Path) -> None:
    """Fitness is the consumer's admission: only a verdict against the weights closes the role."""
    with _runtime(tmp_path):
        status, row = _text_row()

    assert row.fitness is RoleFitnessState.NOT_VERIFIED
    assert row.fit_for_role is None, "no verdict is not evidence of unfitness"
    assert row.installed is True
    assert row.ready is True
    assert row.failed_condition_id is None
    assert status.text_layer_model_fill_available is True


@pytest.mark.parametrize(
    ("verdict", "state", "condition"),
    [
        (
            RoleFitnessVerdict.UNFIT,
            RoleFitnessState.UNFIT,
            ProvisioningPreconditionCondition.ROLE_MODEL_FIT_FOR_ROLE,
        ),
        (
            RoleFitnessVerdict.TIMED_OUT,
            RoleFitnessState.TIMED_OUT,
            ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_WITHIN_TIMEOUT,
        ),
    ],
)
def test_status_reports_a_recorded_refusal_under_its_own_condition_without_probing(
    tmp_path: Path,
    verdict: RoleFitnessVerdict,
    state: RoleFitnessState,
    condition: ProvisioningPreconditionCondition,
) -> None:
    with _runtime(tmp_path):
        _verify_text(_Probe(verdict))
        status, row = _text_row()

    assert row.fitness is state
    assert row.fit_for_role is False
    assert row.ready is False
    assert row.failed_condition_id == condition
    assert status.extraction_ready is False


@pytest.mark.parametrize(
    ("verdict", "condition"),
    [
        (RoleFitnessVerdict.UNFIT, ProvisioningPreconditionCondition.ROLE_MODEL_FIT_FOR_ROLE),
        (RoleFitnessVerdict.TIMED_OUT, ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_WITHIN_TIMEOUT),
    ],
)
def test_a_recorded_refusal_closes_the_consumers_admission_and_offers_nothing(
    tmp_path: Path,
    verdict: RoleFitnessVerdict,
    condition: ProvisioningPreconditionCondition,
) -> None:
    with _runtime(tmp_path):
        before = probe_local_reader(ModelRole.TEXT_EXTRACTION)
        _verify_text(_Probe(verdict))
        after = probe_local_reader(ModelRole.TEXT_EXTRACTION)
        vision = probe_local_reader(ModelRole.VISION_TRANSCRIPTION)

    assert before.available is True, "no verdict admits the consumer"
    assert after.available is False
    assert after.facts["fitness"] == verdict.value
    assert after.precondition_verdict is not None
    assert after.precondition_verdict.failed_condition_id == condition
    assert after.precondition_verdict.action is None
    assert vision.available is True, "only the probed text role is admitted on its fitness"


def test_a_verified_fit_model_is_extraction_ready_from_the_record_alone(tmp_path: Path) -> None:
    probe = _Probe(RoleFitnessVerdict.FIT)
    with _runtime(tmp_path):
        _verify_text(probe)
        first, row = _text_row()
        second, _ = _text_row()

    assert probe.calls == [_TEXT], "status reads the record; only verify probed"
    assert row.fitness is RoleFitnessState.FIT
    assert row.fit_for_role is True
    assert first.extraction_ready is True and second.extraction_ready is True
    assert first.document_readiness is LocalReaderDocumentReadiness.ALL_DOCUMENTS
    assert first.text_layer_model_fill_available is True


def test_a_fit_text_model_without_the_vision_model_still_fills_text_layer_fields(tmp_path: Path) -> None:
    with _runtime(tmp_path, **{_TEXT: "sha256:text-1"}):
        _verify_text(_Probe(RoleFitnessVerdict.FIT))
        status, row = _text_row()

    assert row.ready is True
    assert status.extraction_ready is False
    assert status.document_readiness is LocalReaderDocumentReadiness.TEXT_LAYER_ONLY
    assert status.text_layer_model_fill_available is True


def test_a_transport_failure_during_verify_records_nothing(tmp_path: Path) -> None:
    with _runtime(tmp_path):
        _verify_text(_Probe(None))
        _, row = _text_row()

    assert row.fitness is RoleFitnessState.NOT_VERIFIED


def test_changed_weights_are_not_verified_even_with_a_fit_record(tmp_path: Path) -> None:
    with _runtime(tmp_path):
        _verify_text(_Probe(RoleFitnessVerdict.FIT))
        _Runtime.store = {**_Runtime.store, _TEXT: "sha256:text-2"}
        _, row = _text_row()

    assert row.fitness is RoleFitnessState.NOT_VERIFIED


# ---------------------------------------------------------------------------
# a fresh probe, on request
# ---------------------------------------------------------------------------


def test_a_requested_probe_runs_now_and_records_nothing(tmp_path: Path) -> None:
    probe = _Probe(RoleFitnessVerdict.TIMED_OUT)
    with _runtime(tmp_path):
        _verify_text(_Probe(RoleFitnessVerdict.FIT))
        _, probed = _text_row(text_probe=probe)
        _, recorded = _text_row()

    assert probe.calls == [_TEXT]
    assert probed.fitness is RoleFitnessState.TIMED_OUT
    assert probed.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_WITHIN_TIMEOUT
    assert recorded.fitness is RoleFitnessState.FIT, "a status probe must not overwrite the verify record"


def test_a_requested_probe_with_no_answer_is_not_verified(tmp_path: Path) -> None:
    with _runtime(tmp_path):
        _, row = _text_row(text_probe=_Probe(None))

    assert row.fitness is RoleFitnessState.NOT_VERIFIED
    assert row.fit_for_role is None
    assert row.ready is False, "a check asked for now that got no answer closes the role"
    assert row.failed_condition_id == ProvisioningPreconditionCondition.MODEL_READY


# ---------------------------------------------------------------------------
# the model store changing drops the record
# ---------------------------------------------------------------------------


def _roomy_profile() -> HardwareProfile:
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=64 * GIB, free_bytes=48 * GIB),
        accelerator=AcceleratorReading(
            kind=AcceleratorKind.NVIDIA_CUDA,
            devices=(AcceleratorDevice(index=0, name="card-0", total_vram_bytes=24 * GIB, free_vram_bytes=20 * GIB),),
        ),
    )


# ---------------------------------------------------------------------------
# a consumer's first use measures, once per installed digest
# ---------------------------------------------------------------------------


def _admit_text(probe: _Probe, settings: Settings | None = None) -> DependencyStatus:
    return admit_local_reader(ModelRole.TEXT_EXTRACTION, settings, text_probe=probe)


def _recorded_text_verdict(digest: str) -> RecordedFitnessVerdict | None:
    settings = load_settings()
    return read_fitness_verdict(
        endpoint=settings.cadrumo_llm_ollama_chat_url, model=_TEXT, digest=digest, role=ModelRole.TEXT_EXTRACTION
    )


def test_a_first_use_measures_the_unmeasured_model_once_and_records_it(tmp_path: Path) -> None:
    probe = _Probe(RoleFitnessVerdict.FIT)
    with _runtime(tmp_path):
        first = _admit_text(probe)
        second = _admit_text(probe)
        recorded = _recorded_text_verdict("sha256:text-1")
        _, row = _text_row()

    assert probe.calls == [_TEXT], "the second admission reads the verdict the first one recorded"
    assert first.available is True and second.available is True
    assert recorded is not None and recorded.verdict is RoleFitnessVerdict.FIT
    assert row.fitness is RoleFitnessState.FIT, "status reads the verdict the first use recorded"


@pytest.mark.parametrize(
    ("verdict", "condition"),
    [
        (RoleFitnessVerdict.UNFIT, ProvisioningPreconditionCondition.ROLE_MODEL_FIT_FOR_ROLE),
        (RoleFitnessVerdict.TIMED_OUT, ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_WITHIN_TIMEOUT),
    ],
)
def test_an_unfit_first_use_refuses_with_no_setup_action_and_is_not_measured_again(
    tmp_path: Path,
    verdict: RoleFitnessVerdict,
    condition: ProvisioningPreconditionCondition,
) -> None:
    probe = _Probe(verdict)
    with _runtime(tmp_path):
        first = _admit_text(probe)
        second = _admit_text(probe)

    assert probe.calls == [_TEXT]
    for refused in (first, second):
        assert refused.available is False
        assert refused.facts["fitness"] == verdict.value
        assert refused.precondition_verdict is not None
        assert refused.precondition_verdict.failed_condition_id == condition
        assert refused.precondition_verdict.action is None, "setup cannot change a model's answers"


def test_replaced_weights_are_measured_again_at_their_first_use(tmp_path: Path) -> None:
    probe = _Probe(RoleFitnessVerdict.FIT)
    with _runtime(tmp_path):
        _admit_text(probe)
        _Runtime.store = {**_Runtime.store, _TEXT: "sha256:text-2"}
        replaced = _admit_text(probe)
        _admit_text(probe)
        recorded = _recorded_text_verdict("sha256:text-2")

    assert probe.calls == [_TEXT, _TEXT], "one measurement per installed digest"
    assert replaced.available is True
    assert recorded is not None and recorded.verdict is RoleFitnessVerdict.FIT


def test_a_role_that_is_not_probed_is_admitted_without_measuring(tmp_path: Path) -> None:
    probe = _Probe(RoleFitnessVerdict.UNFIT)
    with _runtime(tmp_path):
        vision = admit_local_reader(ModelRole.VISION_TRANSCRIPTION, text_probe=probe)

    assert vision.available is True
    assert probe.calls == []


def test_a_missing_model_refuses_with_its_setup_before_any_measurement(tmp_path: Path) -> None:
    probe = _Probe(RoleFitnessVerdict.FIT)
    with _runtime(tmp_path, **{_VISION: "sha256:vision-1"}):
        status = _admit_text(probe)

    assert probe.calls == []
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED
    assert status.precondition_verdict.action is not None
    assert status.precondition_verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_a_model_listed_without_a_digest_is_admitted_unmeasured(tmp_path: Path) -> None:
    probe = _Probe(RoleFitnessVerdict.UNFIT)
    with _runtime(tmp_path):
        _Runtime.reports_digests = False
        status = _admit_text(probe)
        path = fitness_verdict_path()

    assert status.available is True, "a verdict could not be keyed to weights nobody can name"
    assert probe.calls == []
    assert not path.exists()


def test_the_measurement_holds_the_record_lock_while_it_probes(tmp_path: Path) -> None:
    excluded: list[bool] = []

    def try_the_lock(settings: Settings) -> None:
        try:
            with fitness_measurement_lock(settings, timeout=0):
                excluded.append(False)
        except LockAcquisitionError:
            excluded.append(True)

    with _runtime(tmp_path):
        _admit_text(_Probe(RoleFitnessVerdict.FIT, during=try_the_lock))

    assert excluded == [True], "a second first use cannot start measuring while one runs"


def test_concurrent_first_uses_measure_once(tmp_path: Path) -> None:
    probing = threading.Event()
    release = threading.Event()

    def hold_the_answer(settings: Settings) -> None:
        del settings
        probing.set()
        release.wait(timeout=30)

    probe = _Probe(RoleFitnessVerdict.FIT, during=hold_the_answer)
    admitted: list[DependencyStatus] = []
    with _runtime(tmp_path):
        settings = load_settings()
        start = threading.Barrier(2)

        def first_use() -> None:
            start.wait(timeout=30)
            admitted.append(_admit_text(probe, settings))

        users = [threading.Thread(target=first_use) for _ in range(2)]
        for user in users:
            user.start()
        assert probing.wait(timeout=30)
        release.set()
        for user in users:
            user.join(timeout=30)

    assert probe.calls == [_TEXT]
    assert [status.available for status in admitted] == [True, True]


def test_a_measurement_held_elsewhere_past_the_wait_refuses_as_not_verified(tmp_path: Path) -> None:
    probe = _Probe(RoleFitnessVerdict.FIT)
    with (
        _runtime(tmp_path),
        override_settings(cadrumo_llm_default_timeout_s=0),
        fitness_measurement_lock(timeout=0),
    ):
        status = _admit_text(probe)

    assert probe.calls == []
    assert status.available is False
    assert status.facts["fitness"] == RoleFitnessState.NOT_VERIFIED.value
    assert status.precondition_verdict is not None
    assert (
        status.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_VERIFIED
    )
    assert status.precondition_verdict.action is None


def test_a_probe_that_finds_the_server_stopped_refuses_with_the_local_ai_setup(tmp_path: Path) -> None:
    _Runtime.store = {_TEXT: "sha256:text-1"}
    _Runtime.reports_digests = True
    with ExitStack() as server:
        chat_url = server.enter_context(serving_loopback(_Runtime, path="/api/chat"))
        probe = _Probe(None, during=lambda _settings: server.close())
        with override_settings(
            cadrumo_local_storage_root=tmp_path,
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_ollama_text_model=_TEXT,
        ):
            status = _admit_text(probe)
            path = fitness_verdict_path()

    assert probe.calls == [_TEXT]
    assert status.available is False
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE
    assert status.precondition_verdict.action is not None, "a stopped server is the setup's, not the model's"
    assert status.precondition_verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    assert not path.exists(), "no answer is no verdict"


def test_a_probe_with_no_answer_from_a_running_server_refuses_and_records_nothing(tmp_path: Path) -> None:
    unanswered = _Probe(None)
    with _runtime(tmp_path):
        refused = _admit_text(unanswered)
        later = _Probe(RoleFitnessVerdict.FIT)
        admitted = _admit_text(later)

    assert refused.available is False
    assert refused.facts["fitness"] == RoleFitnessState.NOT_VERIFIED.value
    assert refused.precondition_verdict is not None
    assert refused.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.MODEL_READY
    assert refused.precondition_verdict.action is None
    assert later.calls == [_TEXT], "nothing was recorded, so the next first use measures"
    assert admitted.available is True
