"""Real-behaviour tests for the recorded fitness verdict and the status that reads it.

The runtime is a real loopback endpoint speaking the ``/api/version``,
``/api/tags``, ``/api/ps``, ``/api/generate``, ``/api/pull`` and ``/api/delete``
wire shapes, with a mutable store whose digests change when a pull replaces
weights. The verdict record is a real file under an isolated storage root. The
text probe is the composition port the application receives; its answer is what
varies.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

import pytest

from ...core.config import Settings, load_settings, override_settings
from ...core.hardware import AcceleratorKind
from ...core.model_catalogue import ModelRole, default_model_runtime_id
from ...tests.loopback_llm import (
    SilentLoopbackHandler,
    read_json_body,
    read_text_body,
    serving_loopback,
    write_json_response,
    write_raw_response,
)
from ..local_reader import (
    EXTRACTION_READER_ROLES,
    LocalReaderDocumentReadiness,
    LocalReaderRoleStatus,
    LocalReaderStatus,
    RoleFitnessOutcome,
    RoleFitnessState,
    read_local_reader_status,
    role_model_targets,
    verify_role_target,
)
from ..provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    HardwareProfile,
    SystemMemoryReading,
    probe_hardware_profile,
)
from ..provisioning_contracts import ProvisioningPreconditionCondition, provisioning_no_recovery_verdict
from ..provisioning_fitness import (
    RecordedFitnessVerdict,
    RoleFitnessVerdict,
    fitness_verdict_path,
    invalidate_role_fitness,
    read_fitness_verdict,
    record_fitness_verdict,
)
from ..provisioning_runtime import pull_runtime_model, remove_runtime_model

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

GIB = 1024**3
_VISION = default_model_runtime_id(ModelRole.VISION_TRANSCRIPTION)
_TEXT = default_model_runtime_id(ModelRole.TEXT_EXTRACTION)
_MAPPING = default_model_runtime_id(ModelRole.COLUMN_ROLE_MAPPING)


class _Runtime(SilentLoopbackHandler):
    store: ClassVar[dict[str, str]] = {}
    pulls: ClassVar[int] = 0

    @override
    def do_GET(self) -> None:
        if self.path == "/api/version":
            write_json_response(self, {"version": "0.9.0"}, status=HTTPStatus.OK)
        elif self.path == "/api/tags":
            rows = [{"name": name, "size": GIB, "digest": digest} for name, digest in self.store.items()]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
        elif self.path == "/api/ps":
            rows = [{"name": name, "size": GIB, "size_vram": GIB} for name in self.store]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    @override
    def do_POST(self) -> None:
        body = read_json_body(self)
        if self.path == "/api/pull":
            name = str(body.get("model") or body.get("name"))
            type(self).pulls += 1
            # A pull replaces the weights, so the digest the runtime reports changes.
            type(self).store = {**self.store, name: f"sha256:pulled-{self.pulls}"}
            lines = [{"status": "downloading", "completed": GIB, "total": GIB}, {"status": "success"}]
            write_raw_response(
                self, "".join(json.dumps(line) + "\n" for line in lines).encode("utf-8"), status=HTTPStatus.OK
            )
            return
        if self.path != "/api/generate":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        write_json_response(self, {"done": True}, status=HTTPStatus.OK)

    @override
    def do_DELETE(self) -> None:
        payload = json.loads(read_text_body(self) or "{}")
        type(self).store = {name: digest for name, digest in self.store.items() if name != payload.get("model")}
        write_json_response(self, {"done": True}, status=HTTPStatus.OK)


@contextmanager
def _runtime(tmp_path: Path, **store: str) -> Generator[str]:
    _Runtime.store = dict(store) or {_TEXT: "sha256:text-1", _VISION: "sha256:vision-1"}
    _Runtime.pulls = 0
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
    """The injected fitness port: records calls and answers a fixed verdict."""

    def __init__(self, verdict: RoleFitnessVerdict | None) -> None:
        # ``None`` answers a transport failure: no verdict about the model.
        self.calls: list[str] = []
        self._verdict = verdict

    def __call__(self, model: str, settings: Settings) -> RoleFitnessOutcome:
        del settings
        self.calls.append(model)
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


def test_invalidation_drops_only_the_configured_endpoint(tmp_path: Path) -> None:
    with override_settings(
        cadrumo_local_storage_root=tmp_path, cadrumo_llm_ollama_chat_url="http://127.0.0.1:9/api/chat"
    ):
        record_fitness_verdict(_verdict())
        record_fitness_verdict(_verdict(endpoint="http://10.0.0.2:11434/api/chat"))
        invalidate_role_fitness()
        kept = json.loads(fitness_verdict_path().read_text(encoding="utf-8"))["verdicts"]

    assert [row["endpoint"] for row in kept] == ["http://10.0.0.2:11434/api/chat"]


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


def test_status_without_a_recorded_verdict_is_not_verified_rather_than_unfit(tmp_path: Path) -> None:
    with _runtime(tmp_path):
        status, row = _text_row()

    assert row.fitness is RoleFitnessState.NOT_VERIFIED
    assert row.fit_for_role is None, "no verdict is not evidence of unfitness"
    assert row.installed is True
    assert row.ready is False
    assert row.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_VERIFIED
    assert status.extraction_ready is False
    assert status.document_readiness is LocalReaderDocumentReadiness.TEXT_LAYER_ONLY
    assert status.text_layer_model_fill_available is False


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


def test_a_completed_pull_drops_the_recorded_verdict(tmp_path: Path) -> None:
    with _runtime(tmp_path):
        _verify_text(_Probe(RoleFitnessVerdict.FIT))
        pulled = pull_runtime_model(_VISION, GIB, profile=_roomy_profile())
        document = json.loads(fitness_verdict_path().read_text(encoding="utf-8"))

    assert pulled.pulled is True
    assert document["verdicts"] == []


def test_a_refused_pull_keeps_the_recorded_verdict(tmp_path: Path) -> None:
    starved = probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=4 * GIB, free_bytes=1 * GIB),
        accelerator=AcceleratorReading(kind=AcceleratorKind.NONE),
    )
    with _runtime(tmp_path):
        _verify_text(_Probe(RoleFitnessVerdict.FIT))
        refused = pull_runtime_model("huge-model:70b", 40 * GIB, profile=starved)
        _, row = _text_row()

    assert refused.pulled is False
    assert row.fitness is RoleFitnessState.FIT


def test_a_confirmed_removal_drops_the_recorded_verdict(tmp_path: Path) -> None:
    with _runtime(tmp_path):
        _verify_text(_Probe(RoleFitnessVerdict.FIT))
        removed = remove_runtime_model(_VISION)
        document = json.loads(fitness_verdict_path().read_text(encoding="utf-8"))

    assert removed.removed is True
    assert document["verdicts"] == []


def test_a_refused_removal_keeps_the_recorded_verdict(tmp_path: Path) -> None:
    with _runtime(tmp_path):
        _verify_text(_Probe(RoleFitnessVerdict.FIT))
        refused = remove_runtime_model("peer-model:70b")
        settings = load_settings()
        kept = read_fitness_verdict(
            endpoint=settings.cadrumo_llm_ollama_chat_url,
            model=_TEXT,
            digest="sha256:text-1",
            role=ModelRole.TEXT_EXTRACTION,
        )

    assert refused.removed is False
    assert kept is not None and kept.verdict is RoleFitnessVerdict.FIT
