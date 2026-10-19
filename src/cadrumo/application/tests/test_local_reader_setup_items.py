"""Real-behaviour tests for the local AI setup item: its program part and per-role model parts.

The model program is a real loopback endpoint speaking the ``/api/version``,
``/api/tags``, ``/api/ps``, ``/api/generate`` and ``/api/pull`` wire shapes;
its pull streams per-layer progress and can fail in-stream the way the program
reports an upstream failure. Cadrumo's model store is a real directory under an
isolated storage root. The installer, the server start, the backoff schedule
and the setup events are the ports the composition root supplies, so they are
the only parts replaced. Nothing here downloads, loads or runs a model.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import socket
import time
from collections.abc import AsyncGenerator, Generator, Mapping
from contextlib import asynccontextmanager, contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

import pytest
from pydantic import SecretStr

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ...core.config import Settings, load_settings, override_settings
from ...core.model_catalogue import ModelRole, default_model_runtime_id, model_candidate
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_path
from ...core.time.clock import now
from ...tests.loopback_llm import (
    SilentLoopbackHandler,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ..dependency_contracts import (
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyItemProvisioner,
    DependencyNote,
    DependencyProbeOutcome,
    DependencyProbeReading,
    DependencySetupStep,
    DependencyStaleReason,
    DependencyState,
    known_part_bytes_of,
)
from ..dependency_registry import LOCAL_AI_DECLARATION, derive_dependency_row
from ..local_reader import RoleFitnessOutcome, TextExtractionFitnessProbe
from ..local_reader_setup_items import (
    LOCAL_AI_PROGRAM_PART,
    HostReachability,
    LocalAiModelPart,
    LocalAiProgramPart,
    LocalAiSetupItem,
    local_ai_setup_item,
    pull_failure_category,
    runtime_version_at_least,
)
from ..provisioning_contracts import ProvisioningPreconditionCondition, provisioning_no_recovery_verdict
from ..provisioning_fitness import RecordedFitnessVerdict, RoleFitnessVerdict, record_fitness_verdict
from ..provisioning_host import RuntimeInstaller, runtime_proxy_environment
from ..provisioning_runtime import (
    PullFailureKind,
    StoredWeightsState,
    classify_runtime_pull_error,
    read_stored_weights,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TEXT = default_model_runtime_id(ModelRole.TEXT_EXTRACTION)
_VISION = default_model_runtime_id(ModelRole.VISION_TRANSCRIPTION)
_MAPPING = default_model_runtime_id(ModelRole.COLUMN_ROLE_MAPPING)
_HOSTS = ("registry.ollama.ai",)
_RUNTIME_HOSTS = ("ollama.com", "github.com")


def _pinned(model: str) -> str:
    candidate = model_candidate(model)
    assert candidate is not None
    assert candidate.weights_pin is not None
    return candidate.weights_pin.digest


class _Program(SilentLoopbackHandler):
    """The model program: a store of name -> digest, a resident set, and a scripted pull."""

    serving: ClassVar[bool] = True
    version: ClassVar[str] = "0.13.0"
    store: ClassVar[dict[str, str]] = {}
    resident: ClassVar[set[str]] = set()
    pull_script: ClassVar[list[list[Mapping[str, object]]]] = []
    pulls: ClassVar[list[str]] = []
    generates: ClassVar[list[Mapping[str, object]]] = []
    line_delay_s: ClassVar[float] = 0.0

    @override
    def do_GET(self) -> None:
        if not self.serving:
            self.send_error(HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if self.path == "/api/version":
            write_json_response(self, {"version": self.version}, status=HTTPStatus.OK)
        elif self.path == "/api/tags":
            rows = [{"name": name, "size": 1, "digest": digest} for name, digest in self.store.items()]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
        elif self.path == "/api/ps":
            rows = [{"name": name, "size": 1, "size_vram": 0} for name in self.resident]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    @override
    def do_POST(self) -> None:
        body = read_json_body(self)
        if self.path == "/api/generate":
            type(self).generates.append(dict(body))
            write_json_response(self, {"done": True}, status=HTTPStatus.OK)
            return
        if self.path != "/api/pull":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        name = str(body.get("model"))
        type(self).pulls.append(name)
        lines = self.pull_script.pop(0) if self.pull_script else [{"status": "success"}]
        refused = lines[0].get("http_status") if lines else None
        if isinstance(refused, int):
            write_json_response(self, {"error": "registry unavailable"}, status=refused)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "application/x-ndjson")
        self.end_headers()
        try:
            for line in lines:
                if line.get("status") == "success":
                    type(self).store = {**self.store, name: _pinned(name)}
                self.wfile.write((json.dumps(line) + "\n").encode("utf-8"))
                self.wfile.flush()
                if self.line_delay_s:
                    time.sleep(self.line_delay_s)
        except OSError:
            # The client closed the stream: the program stops this transfer and
            # keeps what it wrote, without completing the model.
            return


def _reset_program() -> None:
    _Program.serving = True
    _Program.version = "0.13.0"
    _Program.store = {}
    _Program.resident = set()
    _Program.pull_script = []
    _Program.pulls = []
    _Program.generates = []
    _Program.line_delay_s = 0.0


@contextmanager
def _settings(tmp_path: Path, chat_url: str, **extra: object) -> Generator[Settings]:
    with override_settings(
        cadrumo_local_storage_root=tmp_path,
        cadrumo_llm_ollama_chat_url=chat_url,
        cadrumo_llm_ollama_vision_model=_VISION,
        cadrumo_llm_ollama_text_model=_TEXT,
        cadrumo_llm_ollama_mapping_model=_MAPPING,
        **{"cadrumo_llm_model_runtime_memory_floor_bytes": 1, **extra},
    ):
        yield load_settings()


@contextmanager
def _program(tmp_path: Path, **extra: object) -> Generator[Settings]:
    _reset_program()
    with serving_loopback(_Program, path="/api/chat") as chat_url, _settings(tmp_path, chat_url, **extra) as settings:
        yield settings


def _closed_port_url() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return f"http://127.0.0.1:{port}/api/chat"


class _Events:
    """The setup operation's per-item event port, recording what the provisioner reported."""

    def __init__(self, *, cancel_after_progress: bool = False) -> None:
        self.steps: list[DependencySetupStep] = []
        self.transfers: list[tuple[int, int | None]] = []
        self.retries: list[tuple[int, float]] = []
        self.irreversible_entered = 0
        self._cancel_after_progress = cancel_after_progress

    async def step(self, step: DependencySetupStep) -> None:
        self.steps.append(step)

    async def transferred(self, *, completed: int, total: int | None) -> None:
        self.transfers.append((completed, total))

    async def retrying(self, *, attempt: int, delay_s: float) -> None:
        self.retries.append((attempt, delay_s))

    @property
    def cancellation_requested(self) -> bool:
        return self._cancel_after_progress and bool(self.transfers)

    @asynccontextmanager
    async def irreversible(self) -> AsyncGenerator[None]:
        self.irreversible_entered += 1
        yield


def _no_wait(attempt: int, elapsed_s: float) -> float | None:
    del elapsed_s
    return 0.0 if attempt < 3 else None


def _model_item(
    role: ModelRole = ModelRole.TEXT_EXTRACTION,
    *,
    text_probe: TextExtractionFitnessProbe | None = None,
    reachability: HostReachability | None = None,
) -> LocalAiModelPart:
    return LocalAiModelPart(
        role, source_hosts=_HOSTS, retry_delay=_no_wait, text_probe=text_probe, reachability=reachability
    )


def _check(
    item: LocalAiModelPart | LocalAiProgramPart | LocalAiSetupItem,
    mode: DependencyCheckMode = DependencyCheckMode.QUICK,
) -> DependencyProbeReading:
    return asyncio.run(item.check(mode))


def _layer_lines(*layers: tuple[str, int], success: bool = True) -> list[Mapping[str, object]]:
    lines: list[Mapping[str, object]] = [{"status": "pulling manifest"}]
    for digest, size in layers:
        lines.append({"status": f"pulling {digest}", "digest": digest, "total": size, "completed": size // 2})
        lines.append({"status": f"pulling {digest}", "digest": digest, "total": size, "completed": size})
    if success:
        lines.append({"status": "success"})
    return lines


class _FitProbe:
    def __init__(self, *, fit: bool) -> None:
        self.calls: list[str] = []
        self._fit = fit

    def __call__(self, model: str, settings: Settings) -> RoleFitnessOutcome:
        del settings
        self.calls.append(model)
        if self._fit:
            return RoleFitnessOutcome(
                role=ModelRole.TEXT_EXTRACTION,
                model=model,
                fit=True,
                answer_parseable=True,
                grounded=True,
                answer_budget_tokens=64,
                elapsed_ms=1,
            )
        facts = {"model": model}
        return RoleFitnessOutcome(
            role=ModelRole.TEXT_EXTRACTION,
            model=model,
            fit=False,
            answer_budget_tokens=64,
            elapsed_ms=1,
            facts=facts,
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.ROLE_MODEL_FIT_FOR_ROLE, facts=facts
            ),
        )


# ---------------------------------------------------------------------------
# pure classifications
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "kind"),
    [
        ("write /models/blobs/x: no space left on device", PullFailureKind.DISK_FULL),
        (
            "pull model manifest: Get https://registry: dial tcp: lookup registry: no such host",
            PullFailureKind.NAME_RESOLUTION,
        ),
        ("read tcp 10.0.0.2:5000: connection reset by peer", PullFailureKind.NETWORK_TRANSIENT),
        ("max retries exceeded: unexpected EOF", PullFailureKind.NETWORK_TRANSIENT),
        (
            "tls: failed to verify certificate: x509: certificate signed by unknown authority",
            PullFailureKind.SECURE_CONNECTION,
        ),
        ("net/http: TLS handshake timeout", PullFailureKind.NETWORK_TRANSIENT),
        ("digest mismatch, file must be downloaded again", PullFailureKind.INTEGRITY),
        ("pull model manifest: file does not exist", PullFailureKind.NOT_FOUND),
        ("Proxy Authentication Required", PullFailureKind.BLOCKED_BY_NETWORK),
        ("open /models/blobs: permission denied", PullFailureKind.NO_PERMISSION),
        ("something nobody expected", PullFailureKind.OTHER),
    ],
)
def test_the_programs_error_prose_maps_to_a_closed_kind(message: str, kind: PullFailureKind) -> None:
    assert classify_runtime_pull_error(message) is kind


def test_every_fetch_failure_names_a_closed_category() -> None:
    assert pull_failure_category(PullFailureKind.DISK_FULL) is DependencyFailureCategory.DISK_FULL
    assert pull_failure_category(PullFailureKind.INTEGRITY) is DependencyFailureCategory.DAMAGED_DOWNLOAD
    assert pull_failure_category(PullFailureKind.RUNTIME_UNREACHABLE) is DependencyFailureCategory.PROGRAM_NOT_RUNNING
    for kind in PullFailureKind:
        assert isinstance(pull_failure_category(kind), DependencyFailureCategory)


@pytest.mark.parametrize(
    ("version", "expected"),
    [("0.12.7", True), ("0.13.0", True), ("v0.12.10", True), ("0.12.6", False), ("0.9.0", False), ("0.12", False)],
)
def test_runtime_version_comparison(version: str, expected: bool) -> None:
    assert runtime_version_at_least(version) is expected


def test_an_unparseable_version_is_not_judged() -> None:
    assert runtime_version_at_least("dev-build") is None


def test_the_program_downloads_through_the_configured_proxy_with_loopback_exempt(tmp_path: Path) -> None:
    with _settings(
        tmp_path,
        _closed_port_url(),
        cadrumo_proxy_url="http://proxy.example:8080",
        cadrumo_proxy_username="ana",
        cadrumo_proxy_password_secret=SecretStr("p@ss"),
        cadrumo_proxy_bypass="intranet.example",
    ) as settings:
        environment = runtime_proxy_environment(settings)
    assert environment["HTTPS_PROXY"] == "http://ana:p%40ss@proxy.example:8080"
    assert environment["NO_PROXY"].split(",") == ["intranet.example", "localhost", "127.0.0.1", "::1"]
    with _settings(tmp_path, _closed_port_url()) as settings:
        assert runtime_proxy_environment(settings) == {}


# ---------------------------------------------------------------------------
# Cadrumo's own model store on disk
# ---------------------------------------------------------------------------


def _write_store(settings: Settings, model: str, *, blob_present: bool) -> str:
    root = storage_path(StorageCategory.OLLAMA_MODELS, settings=settings)
    name, _, tag = model.partition(":")
    blob = b"weights"
    blob_digest = "sha256:" + hashlib.sha256(blob).hexdigest()
    config = b"{}"
    config_digest = "sha256:" + hashlib.sha256(config).hexdigest()
    manifest = json.dumps(
        {
            "schemaVersion": 2,
            "config": {"digest": config_digest, "size": len(config)},
            "layers": [{"digest": blob_digest, "size": len(blob)}],
        }
    ).encode("utf-8")
    path = root / "manifests" / "registry.ollama.ai" / "library" / name / tag
    path.parent.mkdir(parents=True)
    path.write_bytes(manifest)
    (root / "blobs").mkdir(parents=True)
    (root / "blobs" / config_digest.replace(":", "-")).write_bytes(config)
    if blob_present:
        (root / "blobs" / blob_digest.replace(":", "-")).write_bytes(blob)
    return hashlib.sha256(manifest).hexdigest()


def test_the_store_reports_the_manifest_digest_the_program_would(tmp_path: Path) -> None:
    with _settings(tmp_path, _closed_port_url()) as settings:
        assert read_stored_weights(_TEXT, settings).state is StoredWeightsState.ABSENT
        digest = _write_store(settings, _TEXT, blob_present=True)
        stored = read_stored_weights(_TEXT, settings)
    assert stored.state is StoredWeightsState.COMPLETE
    assert stored.digest == digest


def test_a_store_missing_a_layer_is_incomplete_and_reads_as_absent(tmp_path: Path) -> None:
    with _settings(tmp_path, _closed_port_url()) as settings:
        _write_store(settings, _TEXT, blob_present=False)
        assert read_stored_weights(_TEXT, settings).state is StoredWeightsState.INCOMPLETE
        reading = _check(_model_item())
    assert reading.outcome is DependencyProbeOutcome.ABSENT


def test_a_complete_store_is_observed_while_the_program_is_not_running(tmp_path: Path) -> None:
    with _settings(tmp_path, _closed_port_url()) as settings:
        _write_store(settings, _TEXT, blob_present=True)
        reading = _check(_model_item())
    # The stored weights are not the pinned ones, so the model is usable but different.
    assert reading.outcome is DependencyProbeOutcome.DIFFERS
    assert reading.stale_reason is DependencyStaleReason.DIFFERENT_MODEL_VERSION


# ---------------------------------------------------------------------------
# model quick checks
# ---------------------------------------------------------------------------


def test_the_pinned_model_in_the_inventory_is_ready(tmp_path: Path) -> None:
    with _program(tmp_path):
        _Program.store = {_TEXT: _pinned(_TEXT)}
        reading = _check(_model_item())
    row = derive_dependency_row(LOCAL_AI_DECLARATION, reading)
    assert reading.outcome is DependencyProbeOutcome.PRESENT
    assert row.state is DependencyState.READY
    assert _Program.generates == []


def test_the_digest_comparison_accepts_the_prefixed_form(tmp_path: Path) -> None:
    with _program(tmp_path):
        _Program.store = {_TEXT: "sha256:" + _pinned(_TEXT)}
        assert _check(_model_item()).outcome is DependencyProbeOutcome.PRESENT


def test_a_different_digest_is_stale_until_a_fitness_verdict_says_otherwise(tmp_path: Path) -> None:
    with _program(tmp_path) as settings:
        _Program.store = {_TEXT: "a" * 64, _VISION: "b" * 64}
        text = _check(_model_item())
        vision = _check(_model_item(ModelRole.VISION_TRANSCRIPTION))
        record_fitness_verdict(
            RecordedFitnessVerdict(
                endpoint=settings.cadrumo_llm_ollama_chat_url,
                model=_TEXT,
                digest="a" * 64,
                role=ModelRole.TEXT_EXTRACTION,
                verdict=RoleFitnessVerdict.UNFIT,
                elapsed_ms=1,
                recorded_at=now(),
            ),
            settings,
        )
        unfit = _check(_model_item())
    assert text.outcome is DependencyProbeOutcome.DIFFERS
    assert text.stale_reason is DependencyStaleReason.DIFFERENT_MODEL_VERSION
    assert vision.outcome is DependencyProbeOutcome.DIFFERS
    assert unfit.outcome is DependencyProbeOutcome.FAILED
    assert unfit.failure_category is DependencyFailureCategory.UNEXPECTED


def test_a_model_missing_from_the_inventory_is_absent(tmp_path: Path) -> None:
    with _program(tmp_path):
        _Program.store = {_VISION: _pinned(_VISION)}
        reading = _check(_model_item())
    assert reading.outcome is DependencyProbeOutcome.ABSENT


def test_a_computer_below_the_memory_floor_is_blocked_by_hardware(tmp_path: Path) -> None:
    with _program(tmp_path, cadrumo_llm_model_runtime_memory_floor_bytes=1 << 60):
        reading = _check(_model_item())
    assert reading.outcome is DependencyProbeOutcome.BLOCKED
    assert reading.blocked_reason is DependencyBlockedReason.HARDWARE


# ---------------------------------------------------------------------------
# model full checks
# ---------------------------------------------------------------------------


def test_a_full_check_generates_one_token_with_the_load_keep_alive_and_asks_fitness(tmp_path: Path) -> None:
    probe = _FitProbe(fit=True)
    with _program(tmp_path):
        _Program.store = {_TEXT: _pinned(_TEXT)}
        _Program.resident = {_TEXT}
        reading = _check(_model_item(text_probe=probe), DependencyCheckMode.FULL)
    assert reading.outcome is DependencyProbeOutcome.PRESENT
    assert reading.note is None
    assert probe.calls == [_TEXT]
    (generate,) = _Program.generates
    assert generate["keep_alive"] == "30m"
    assert generate["options"] == {"num_predict": 1}


def test_a_full_check_with_an_unfit_answer_fails(tmp_path: Path) -> None:
    with _program(tmp_path):
        _Program.store = {_TEXT: _pinned(_TEXT)}
        _Program.resident = {_TEXT}
        reading = _check(_model_item(text_probe=_FitProbe(fit=False)), DependencyCheckMode.FULL)
    assert reading.outcome is DependencyProbeOutcome.FAILED
    assert reading.failure_category is DependencyFailureCategory.UNEXPECTED


def test_a_refused_admission_is_downloaded_not_loaded_and_loads_nothing(tmp_path: Path) -> None:
    with _program(tmp_path, cadrumo_llm_contention_safety_margin_bytes=1 << 60):
        _Program.store = {_TEXT: _pinned(_TEXT)}
        reading = _check(_model_item(text_probe=_FitProbe(fit=True)), DependencyCheckMode.FULL)
    row = derive_dependency_row(LOCAL_AI_DECLARATION, reading)
    assert reading.outcome is DependencyProbeOutcome.PRESENT
    assert reading.note is DependencyNote.DOWNLOADED_NOT_LOADED
    assert row.state is DependencyState.READY
    assert _Program.generates == []


def test_an_absent_model_offline_is_blocked_offline_on_a_full_check(tmp_path: Path) -> None:
    asked: list[tuple[str, ...]] = []

    async def offline(hosts: tuple[str, ...]) -> DependencyFailureCategory | None:
        asked.append(hosts)
        return DependencyFailureCategory.OFFLINE

    async def unreachable(hosts: tuple[str, ...]) -> DependencyFailureCategory | None:
        del hosts
        return DependencyFailureCategory.HOST_UNREACHABLE

    with _program(tmp_path):
        blocked = _check(_model_item(reachability=offline), DependencyCheckMode.FULL)
        failed = _check(_model_item(reachability=unreachable), DependencyCheckMode.FULL)
        quick = _check(_model_item(reachability=offline))
    assert blocked.blocked_reason is DependencyBlockedReason.OFFLINE
    assert failed.failure_category is DependencyFailureCategory.HOST_UNREACHABLE
    assert quick.outcome is DependencyProbeOutcome.ABSENT
    assert asked == [_HOSTS]


# ---------------------------------------------------------------------------
# model plan and fetch
# ---------------------------------------------------------------------------


def test_roles_sharing_a_model_plan_the_same_pinned_target(tmp_path: Path) -> None:
    with _program(tmp_path):
        text = asyncio.run(_model_item().plan(model_name=None))
        mapping = asyncio.run(_model_item(ModelRole.COLUMN_ROLE_MAPPING).plan(model_name=None))
        vision = asyncio.run(_model_item(ModelRole.VISION_TRANSCRIPTION).plan(model_name=None))
    candidate = model_candidate(_TEXT)
    assert candidate is not None
    assert candidate.weights_pin is not None
    assert text.download_bytes == candidate.weights_pin.download_bytes
    assert text.target_version == f"{_TEXT}@{candidate.weights_pin.digest}"
    assert mapping.target_version == text.target_version
    assert vision.target_version != text.target_version
    assert text.destination is StorageCategory.OLLAMA_MODELS
    assert (text.part_id, mapping.part_id) == ("text_extraction", "column_role_mapping")
    assert known_part_bytes_of([text, mapping, vision]) == (text.download_bytes or 0) + (vision.download_bytes or 0)


def test_an_uncatalogued_named_model_has_an_unknown_size(tmp_path: Path) -> None:
    with _program(tmp_path):
        entry = asyncio.run(_model_item().plan(model_name="someone/else:1b"))
    assert entry.download_bytes is None
    assert entry.target_version == "someone/else:1b"


def test_a_fetch_reports_the_sum_of_its_layers_and_a_shared_model_downloads_once(tmp_path: Path) -> None:
    with _program(tmp_path):
        text_item = _model_item()
        mapping_item = _model_item(ModelRole.COLUMN_ROLE_MAPPING)
        entry = asyncio.run(text_item.plan(model_name=None))
        _Program.pull_script = [_layer_lines(("sha256:aa", 600), ("sha256:bb", 400))]
        _Program.line_delay_s = 0.15
        events = _Events()
        result = asyncio.run(text_item.provision(entry, events))
        again = asyncio.run(mapping_item.provision(asyncio.run(mapping_item.plan(model_name=None)), _Events()))
    assert result.changed
    assert result.failure_category is None
    assert result.transferred_bytes == 1000
    assert events.steps == [DependencySetupStep.DOWNLOAD]
    assert events.transfers[-1] == (1000, entry.download_bytes)
    assert all(earlier[0] <= later[0] for earlier, later in zip(events.transfers, events.transfers[1:], strict=False))
    assert not again.changed
    assert _Program.pulls == [_TEXT]


def test_a_transient_failure_is_retried_and_then_completes(tmp_path: Path) -> None:
    with _program(tmp_path):
        item = _model_item()
        entry = asyncio.run(item.plan(model_name=None))
        _Program.pull_script = [
            [{"status": "pulling manifest"}, {"error": "read tcp: connection reset by peer"}],
            _layer_lines(("sha256:aa", 10)),
        ]
        events = _Events()
        result = asyncio.run(item.provision(entry, events))
    assert result.failure_category is None
    assert events.retries == [(2, 0.0)]
    assert _Program.pulls == [_TEXT, _TEXT]


def test_an_error_status_from_the_program_is_classified_and_retried_when_transient(tmp_path: Path) -> None:
    with _program(tmp_path):
        item = _model_item()
        entry = asyncio.run(item.plan(model_name=None))
        _Program.pull_script = [[{"http_status": 503}], [{"http_status": 400}]]
        events = _Events()
        result = asyncio.run(item.provision(entry, events))
    assert result.failure_category is DependencyFailureCategory.UNEXPECTED
    assert events.retries == [(2, 0.0)]
    assert len(_Program.pulls) == 2


def test_a_full_disk_is_never_retried(tmp_path: Path) -> None:
    with _program(tmp_path):
        item = _model_item()
        entry = asyncio.run(item.plan(model_name=None))
        _Program.pull_script = [[{"error": "write blob: no space left on device"}]]
        events = _Events()
        result = asyncio.run(item.provision(entry, events))
    assert result.failure_category is DependencyFailureCategory.DISK_FULL
    assert events.retries == []
    assert _Program.pulls == [_TEXT]


def test_a_spent_retry_budget_reports_the_network_category(tmp_path: Path) -> None:
    with _program(tmp_path):
        item = _model_item()
        entry = asyncio.run(item.plan(model_name=None))
        _Program.pull_script = [[{"error": "i/o timeout"}] for _ in range(5)]
        events = _Events()
        result = asyncio.run(item.provision(entry, events))
    assert result.failure_category is DependencyFailureCategory.HOST_UNREACHABLE
    assert [attempt for attempt, _ in events.retries] == [2, 3]
    assert len(_Program.pulls) == 3


def test_a_stream_that_ends_without_success_is_truncated_and_retried(tmp_path: Path) -> None:
    with _program(tmp_path):
        item = _model_item()
        entry = asyncio.run(item.plan(model_name=None))
        _Program.pull_script = [_layer_lines(("sha256:aa", 10), success=False), _layer_lines(("sha256:aa", 10))]
        result = asyncio.run(item.provision(entry, _Events()))
    assert result.failure_category is None
    assert len(_Program.pulls) == 2


def test_cancelling_stops_the_transfer_and_keeps_what_was_written(tmp_path: Path) -> None:
    with _program(tmp_path):
        item = _model_item()
        entry = asyncio.run(item.plan(model_name=None))
        _Program.pull_script = [_layer_lines(*((f"sha256:{index:02x}", 100) for index in range(40)))]
        _Program.line_delay_s = 0.1
        events = _Events(cancel_after_progress=True)
        result = asyncio.run(item.provision(entry, events))
    assert result.failure_category is DependencyFailureCategory.CANCELLED
    assert result.changed
    assert 0 < result.transferred_bytes < 4000
    assert _TEXT not in _Program.store


def test_a_fetch_with_the_program_not_running_names_it(tmp_path: Path) -> None:
    with _settings(tmp_path, _closed_port_url()):
        item = _model_item()
        entry = asyncio.run(item.plan(model_name=None))
        result = asyncio.run(item.provision(entry, _Events()))
    assert result.failure_category is DependencyFailureCategory.PROGRAM_NOT_RUNNING
    assert not result.changed


# ---------------------------------------------------------------------------
# the model program
# ---------------------------------------------------------------------------


class _Host:
    """Where the program and the package manager are found, and the installer and start ports."""

    def __init__(self, tmp_path: Path, *, installer: str | None = "winget") -> None:
        self.program = tmp_path / "bin" / "ollama.exe"
        self.installer_path = tmp_path / "bin" / "winget.exe"
        self.installer = installer
        self.installs: list[RuntimeInstaller] = []
        self.spawns: list[Mapping[str, str]] = []

    def which(self, name: str) -> str | None:
        if name == "ollama":
            return str(self.program) if self.program.is_file() else None
        if self.installer is not None and name == self.installer:
            return str(self.installer_path)
        return None

    def run_installer(self, installer: RuntimeInstaller, executable: Path, timeout_s: float) -> int:
        del executable, timeout_s
        self.installs.append(installer)
        self.program.parent.mkdir(parents=True, exist_ok=True)
        self.program.write_bytes(b"")
        return 0

    def spawn(self, executable: Path, environment: Mapping[str, str]) -> int:
        del executable
        self.spawns.append(dict(environment))
        _Program.serving = True
        return 4242


def _runtime_item(host: _Host) -> LocalAiProgramPart:
    return LocalAiProgramPart(
        source_hosts=_RUNTIME_HOSTS, run_installer=host.run_installer, spawn=host.spawn, which=host.which
    )


@pytest.fixture
def _isolated_install_locations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The program's standard install location is derived from these, so a
    # program installed on the machine running the tests is never found.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))


@pytest.mark.usefixtures("_isolated_install_locations")
def test_an_answering_program_is_present_and_an_old_one_is_stale(tmp_path: Path) -> None:
    host = _Host(tmp_path)
    with _program(tmp_path):
        current = _check(_runtime_item(host))
        _Program.version = "0.9.0"
        old = _check(_runtime_item(host))
    assert current.outcome is DependencyProbeOutcome.PRESENT
    assert current.version == "0.13.0"
    assert old.outcome is DependencyProbeOutcome.DIFFERS
    assert old.stale_reason is DependencyStaleReason.PROGRAM_TOO_OLD


@pytest.mark.usefixtures("_isolated_install_locations")
def test_a_program_not_answering_is_absent_not_running_or_needs_the_person(tmp_path: Path) -> None:
    with _settings(tmp_path, _closed_port_url()):
        absent = _check(_runtime_item(_Host(tmp_path)))
        no_installer = _check(_runtime_item(_Host(tmp_path, installer=None)))
        located = _Host(tmp_path)
        located.program.parent.mkdir(parents=True)
        located.program.write_bytes(b"")
        not_running = _check(_runtime_item(located))
    assert absent.outcome is DependencyProbeOutcome.ABSENT
    assert no_installer.outcome is DependencyProbeOutcome.BLOCKED
    assert no_installer.blocked_reason is DependencyBlockedReason.NEEDS_PERSON
    assert not_running.outcome is DependencyProbeOutcome.FAILED
    assert not_running.failure_category is DependencyFailureCategory.PROGRAM_NOT_RUNNING


@pytest.mark.usefixtures("_isolated_install_locations")
def test_setting_up_a_missing_program_installs_then_starts_it(tmp_path: Path) -> None:
    host = _Host(tmp_path)
    with _program(tmp_path):
        _Program.serving = False
        item = _runtime_item(host)
        entry = asyncio.run(item.plan())
        events = _Events()
        result = asyncio.run(item.provision(entry, events))
        after = _check(item)
        models_root = storage_path(StorageCategory.OLLAMA_MODELS, settings=load_settings())
    assert entry.installs_outside_program
    assert entry.download_bytes is None
    assert entry.destination is None
    assert host.installs == [RuntimeInstaller.WINGET]
    assert events.irreversible_entered == 1
    assert result.changed
    assert result.failure_category is None
    (environment,) = host.spawns
    assert environment["OLLAMA_MODELS"] == str(models_root)
    assert after.outcome is DependencyProbeOutcome.PRESENT


@pytest.mark.usefixtures("_isolated_install_locations")
def test_an_answering_program_plans_nothing_to_download_and_starts_nothing(tmp_path: Path) -> None:
    host = _Host(tmp_path)
    with _program(tmp_path):
        item = _runtime_item(host)
        entry = asyncio.run(item.plan())
        result = asyncio.run(item.provision(entry, _Events()))
    assert entry.download_bytes == 0
    assert not entry.installs_outside_program
    assert host.installs == []
    assert host.spawns == []
    assert not result.changed


@pytest.mark.usefixtures("_isolated_install_locations")
def test_cancelling_before_the_install_installs_nothing(tmp_path: Path) -> None:
    class _Cancelled(_Events):
        @property
        @override
        def cancellation_requested(self) -> bool:
            return True

    host = _Host(tmp_path)
    with _settings(tmp_path, _closed_port_url()):
        item = _runtime_item(host)
        entry = asyncio.run(item.plan())
        result = asyncio.run(item.provision(entry, _Cancelled()))
    assert result.failure_category is DependencyFailureCategory.CANCELLED
    assert host.installs == []


# ---------------------------------------------------------------------------
# composition
# ---------------------------------------------------------------------------


def _local_ai(host: _Host) -> LocalAiSetupItem:
    return LocalAiSetupItem(
        _runtime_item(host), [_model_item(role, text_probe=_FitProbe(fit=True)) for role in ModelRole]
    )


def test_the_local_ai_is_one_item_made_of_its_program_and_every_role(tmp_path: Path) -> None:
    host = _Host(tmp_path)
    item = local_ai_setup_item(
        runtime_hosts=_RUNTIME_HOSTS,
        model_hosts=_HOSTS,
        run_installer=host.run_installer,
        spawn=host.spawn,
        retry_delay=_no_wait,
    )
    assert item.declaration is LOCAL_AI_DECLARATION
    assert isinstance(item, DependencyItemProvisioner)
    with pytest.raises(ValueError, match="one model part per catalogue role"):
        LocalAiSetupItem(_runtime_item(host), [_model_item()])


def _store_every_role() -> None:
    _Program.store = {model: _pinned(model) for model in {_TEXT, _VISION, _MAPPING}}


@pytest.mark.usefixtures("_isolated_install_locations")
def test_the_local_ai_is_ready_only_when_its_program_and_every_roles_model_are(tmp_path: Path) -> None:
    host = _Host(tmp_path)
    with _program(tmp_path):
        _store_every_role()
        supply = asyncio.run(_model_item(ModelRole.SUPPLY_NATURE_PROPOSAL).plan(model_name=None))
        assert supply.target_version is not None
        supply_model = supply.target_version.split("@", 1)[0]
        _Program.store = {**_Program.store, supply_model: _pinned(supply_model)}
        ready = _check(_local_ai(host))
        _Program.store = {name: digest for name, digest in _Program.store.items() if name != _VISION}
        missing = _check(_local_ai(host))
        _Program.version = "0.9.0"
        old_and_missing = _check(_local_ai(host))
    assert ready.item_id == "local_ai"
    assert ready.outcome is DependencyProbeOutcome.PRESENT
    assert ready.version == "0.13.0"
    assert derive_dependency_row(LOCAL_AI_DECLARATION, ready).state is DependencyState.READY
    # A missing model decides before a program that only differs from what was tested.
    assert missing.outcome is DependencyProbeOutcome.ABSENT
    assert old_and_missing.outcome is DependencyProbeOutcome.ABSENT
    assert derive_dependency_row(LOCAL_AI_DECLARATION, missing).recovery_action_id == "operator.provision.local_ai"


@pytest.mark.usefixtures("_isolated_install_locations")
def test_a_computer_below_the_floor_holds_the_whole_local_ai_back(tmp_path: Path) -> None:
    host = _Host(tmp_path)
    with _program(tmp_path, cadrumo_llm_model_runtime_memory_floor_bytes=1 << 60):
        reading = _check(_local_ai(host))
    assert reading.outcome is DependencyProbeOutcome.BLOCKED
    assert reading.blocked_reason is DependencyBlockedReason.HARDWARE
    assert derive_dependency_row(LOCAL_AI_DECLARATION, reading).recovery is None


@pytest.mark.usefixtures("_isolated_install_locations")
def test_the_plan_names_the_program_then_only_the_roles_that_are_not_ready(tmp_path: Path) -> None:
    host = _Host(tmp_path)
    with _program(tmp_path):
        _Program.store = {_VISION: _pinned(_VISION)}
        entry = asyncio.run(_local_ai(host).plan(model_name=None))
    assert entry.item_id == "local_ai"
    parts = [part.part_id for part in entry.parts]
    assert parts[0] == LOCAL_AI_PROGRAM_PART
    assert "vision_transcription" not in parts
    assert set(parts[1:]) == {role.value for role in ModelRole if role is not ModelRole.VISION_TRANSCRIPTION}
    # The answering program only starts; each distinct model is counted once.
    assert entry.parts[0].download_bytes == 0
    assert entry.download_bytes == known_part_bytes_of(entry.parts)
    assert entry.installs_outside_program is False
    assert entry.destination is StorageCategory.OLLAMA_MODELS


@pytest.mark.usefixtures("_isolated_install_locations")
def test_setting_up_the_local_ai_runs_its_parts_in_order_with_one_progress_figure(tmp_path: Path) -> None:
    host = _Host(tmp_path)
    with _program(tmp_path):
        item = _local_ai(host)
        entry = asyncio.run(item.plan(model_name=None))
        _Program.pull_script = [_layer_lines(("sha256:aa", 600), ("sha256:bb", 400)) for _ in ModelRole]
        events = _Events()
        result = asyncio.run(item.provision(entry, events))
    assert result.item_id == "local_ai"
    assert result.failure_category is None
    assert result.changed
    # Each distinct model is fetched once, in catalogue order; shared ones move no byte.
    assert _Program.pulls == list(dict.fromkeys(_Program.pulls))
    assert set(_Program.pulls) >= {_VISION, _TEXT}
    assert events.steps.count(DependencySetupStep.DOWNLOAD) == len(_Program.pulls)
    total = entry.download_bytes
    assert total is not None and total > 0
    assert all(seen_total == total for _completed, seen_total in events.transfers)
    figures = [completed for completed, _total in events.transfers]
    assert figures == sorted(figures)
    assert all(0 <= completed <= total for completed in figures)


@pytest.mark.usefixtures("_isolated_install_locations")
def test_a_part_that_does_not_finish_stops_the_local_ai_there(tmp_path: Path) -> None:
    host = _Host(tmp_path)
    with _program(tmp_path):
        item = _local_ai(host)
        entry = asyncio.run(item.plan(model_name=None))
        _Program.pull_script = [[{"error": "write blob: no space left on device"}]]
        result = asyncio.run(item.provision(entry, _Events()))
    assert result.item_id == "local_ai"
    assert result.failure_category is DependencyFailureCategory.DISK_FULL
    assert len(_Program.pulls) == 1
