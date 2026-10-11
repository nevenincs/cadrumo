"""Real supervision of the local-reader and browser provisioning operations for tests.

Every run goes through the real registry, supervisor, journal and encrypted
operand store. The model runtime is a real loopback endpoint speaking the
Ollama wire shapes; only the process spawner, the installers and the text
fitness probe are injected ports, as production composition injects them.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine, Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

from pydantic import BaseModel

from .....application.browser_runtime_operation import (
    build_browser_runtime_operation_definition,
    build_browser_runtime_operation_registration,
)
from .....application.local_reader import RoleFitnessOutcome
from .....application.local_reader_operation import (
    build_local_reader_operation_definition,
    build_local_reader_operation_registration,
)
from .....application.local_reader_provisioning import RuntimeServerOwnerStart
from .....application.local_reader_report import (
    build_local_reader_report_definition,
    build_local_reader_report_registration,
)
from .....application.local_reader_status_operation import (
    build_local_reader_status_definition,
    build_local_reader_status_registration,
)
from .....application.operations.composition import OperationComposedServices, compose_operation_services
from .....application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from .....application.operations.models import OperationIdentity, OperationRequest
from .....application.operations.registry import OperationRegistry
from .....application.operations.tests.authority_test_support import unread_authority_operation
from .....application.provisioning_host import RuntimeInstaller
from .....core.config import Settings, override_settings
from .....core.model_catalogue import ModelRole, default_model_runtime_id
from .....core.operations import OperationEffect, OperationEventKind, OperationTerminalCondition
from .....tests.loopback_llm import SilentLoopbackHandler, read_json_body, serving_loopback, write_json_response
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..journal import OperationJournalRepository
from ..lease import OperationLeaseFilesystemRepository
from ..secure_references import operation_secure_reference_repository

__all__ = [
    "MAPPING_MODEL",
    "TEXT_MODEL",
    "VISION_MODEL",
    "LoopbackModelRuntime",
    "ProvisioningPorts",
    "SupervisedRun",
    "loopback_model_runtime",
    "provisioning_registry",
    "run_supervised",
    "run_supervised_in",
]

VISION_MODEL = default_model_runtime_id(ModelRole.VISION_TRANSCRIPTION)
TEXT_MODEL = default_model_runtime_id(ModelRole.TEXT_EXTRACTION)
MAPPING_MODEL = default_model_runtime_id(ModelRole.COLUMN_ROLE_MAPPING)


class LoopbackModelRuntime(SilentLoopbackHandler):
    """A loopback runtime whose inventory and resident set change as a real one's would."""

    installed: ClassVar[set[str]] = set()
    residents: ClassVar[set[str]] = set()
    pull_fails: ClassVar[bool] = False
    requests: ClassVar[list[tuple[str, Mapping[str, object]]]] = []

    @override
    def do_GET(self) -> None:
        if self.path == "/api/version":
            write_json_response(self, {"version": "0.9.0"}, status=HTTPStatus.OK)
        elif self.path == "/api/tags":
            rows = [{"name": name, "size": 1024, "digest": f"sha256:{name}"} for name in sorted(self.installed)]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
        elif self.path == "/api/ps":
            rows = [{"name": name, "size": 1024, "size_vram": 0} for name in sorted(self.residents)]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    @override
    def do_POST(self) -> None:
        body = read_json_body(self)
        type(self).requests.append((self.path, body))
        model = str(body.get("model"))
        if self.path == "/api/pull":
            self._pull(model)
        elif self.path == "/api/generate":
            if model not in self.installed:
                write_json_response(self, {"error": "model not found"}, status=HTTPStatus.NOT_FOUND)
                return
            if "prompt" not in body:
                self.residents.add(model)
                write_json_response(self, {"done": True, "done_reason": "load"}, status=HTTPStatus.OK)
                return
            write_json_response(self, {"done": True, "response": "ok"}, status=HTTPStatus.OK)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    @override
    def do_DELETE(self) -> None:
        body = read_json_body(self)
        type(self).requests.append((self.path, body))
        model = str(body.get("model"))
        if self.path != "/api/delete" or model not in self.installed:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.installed.discard(model)
        self.residents.discard(model)
        write_json_response(self, {}, status=HTTPStatus.OK)

    def _pull(self, model: str) -> None:
        if self.pull_fails:
            lines = [{"status": "pulling manifest"}, {"error": "registry unavailable"}]
        else:
            self.installed.add(model)
            lines = [{"status": "downloading", "completed": 512, "total": 1024}, {"status": "success"}]
        payload = "".join(json.dumps(line) + "\n" for line in lines).encode()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@contextmanager
def loopback_model_runtime(
    *, installed: set[str], residents: set[str], pull_fails: bool = False, required_headroom_bytes: int | None = None
) -> Generator[str]:
    """Serve the loopback runtime and point the reader's settings at it.

    Admission is overridden open by default, so it does not depend on how busy
    the test host's memory happens to be. ``required_headroom_bytes`` instead
    enforces admission with that safety margin, which a test about a refused
    load sets beyond any host's memory.
    """
    LoopbackModelRuntime.installed = set(installed)
    LoopbackModelRuntime.residents = set(residents)
    LoopbackModelRuntime.pull_fails = pull_fails
    LoopbackModelRuntime.requests = []
    with (
        serving_loopback(LoopbackModelRuntime, path="/api/chat") as chat_url,
        override_settings(
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_ollama_vision_model=VISION_MODEL,
            cadrumo_llm_ollama_text_model=TEXT_MODEL,
            cadrumo_llm_ollama_mapping_model=MAPPING_MODEL,
            cadrumo_llm_contention_safety_margin_bytes=required_headroom_bytes or 0,
            cadrumo_llm_contention_check_override=required_headroom_bytes is None,
        ),
    ):
        yield chat_url


class ProvisioningPorts:
    """Injected process, installer and fitness ports that record every call."""

    def __init__(
        self,
        *,
        browser_install: Callable[[], int] = lambda: 0,
        owner_start: Callable[[OperationIdentity], Coroutine[None, None, int | None]] | None = None,
    ) -> None:
        """Start with nothing spawned, installed or probed.

        ``browser_install`` stands in for the vendor download. ``owner_start``
        binds the runtime server start to the process that owns the executing
        one, as a contained worker binds it, in place of :meth:`spawn`.
        """
        self.spawned: list[Path] = []
        self.installers: list[RuntimeInstaller] = []
        self.probed: list[str] = []
        self.browser_installs = 0
        self.owner_start = owner_start
        self._browser_install = browser_install

    def spawn(self, executable: Path, env: Mapping[str, str]) -> int:
        """Record a runtime server start and report a process id."""
        del env
        self.spawned.append(executable)
        return 1

    def install(self, installer: RuntimeInstaller, executable: Path, timeout_s: float) -> int:
        """Record a package-manager install and report success."""
        del executable, timeout_s
        self.installers.append(installer)
        return 0

    def probe(self, model: str, settings: Settings) -> RoleFitnessOutcome:
        """Record a fitness probe and report the model fit."""
        del settings
        self.probed.append(model)
        return RoleFitnessOutcome(
            role=ModelRole.TEXT_EXTRACTION,
            model=model,
            fit=True,
            answer_parseable=True,
            grounded=True,
            answer_budget_tokens=1024,
            elapsed_ms=1,
        )

    def install_browser(self, timeout_s: float) -> int:
        """Record a browser install and report what the stand-in download returned."""
        del timeout_s
        self.browser_installs += 1
        return self._browser_install()


def provisioning_registry(ports: ProvisioningPorts) -> OperationRegistry:
    """Register the four provisioning-family operations over ``ports``."""
    provision = build_local_reader_operation_definition(
        spawn=ports.spawn if ports.owner_start is None else RuntimeServerOwnerStart(ports.owner_start),
        run_installer=ports.install,
        text_probe=ports.probe,
    )
    status = build_local_reader_status_definition(text_probe=ports.probe)
    report = build_local_reader_report_definition()
    browser = build_browser_runtime_operation_definition(run_installer=ports.install_browser)
    return OperationRegistry(
        definitions=(browser, provision, report, status),
        public_registrations=(
            build_browser_runtime_operation_registration(browser),
            build_local_reader_operation_registration(provision),
            build_local_reader_report_registration(report),
            build_local_reader_status_registration(status),
        ),
    )


def _services(root: Path, registry: OperationRegistry) -> tuple[OperationComposedServices, OperationJournalRepository]:
    journal = OperationJournalRepository(storage_root=root)
    services = compose_operation_services(
        registry=registry,
        authority_operation=unread_authority_operation(),
        journal=journal,
        reader=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=operation_secure_reference_repository(),
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: datetime.now(UTC),
        lease_duration=timedelta(minutes=5),
        execution_timeout=timedelta(seconds=60),
        cleanup_timeout=timedelta(seconds=5),
    )
    return services, journal


@dataclass(frozen=True, slots=True)
class SupervisedRun[ResultT: BaseModel]:
    """One settled operation: its public result, committed effect and published phases."""

    result: ResultT
    effect: OperationEffect
    phases: tuple[str, ...]


def run_supervised[RequestT: BaseModel, ResultT: BaseModel](
    tmp_path: Path,
    ports: ProvisioningPorts,
    request: OperationRequest[RequestT],
    result_type: type[ResultT],
) -> SupervisedRun[ResultT]:
    """Settle ``request`` over the recording ``ports`` and resolve its public result as a frontend would."""
    return run_supervised_in(tmp_path, provisioning_registry(ports), request, result_type)


def run_supervised_in[RequestT: BaseModel, ResultT: BaseModel](
    tmp_path: Path,
    registry: OperationRegistry,
    request: OperationRequest[RequestT],
    result_type: type[ResultT],
) -> SupervisedRun[ResultT]:
    """Submit, start and settle ``request`` in ``registry``, then resolve its public result as a frontend would."""

    async def run(root: Path) -> SupervisedRun[ResultT]:
        services, journal = _services(root, registry)
        try:
            submitted = await services.submission.submit(request, actor_ref="operator:local-reader-test")
            operation_id = submitted.receipt.operation_id
            await services.submission.start(operation_id)
            await services.submission.settled(operation_id)
            terminal = await journal.load(operation_id)
            replay = await journal.read_after(operation_id, 0, limit=64)
            observed = await services.observation.observe(
                OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=64)
            )
            assert isinstance(observed, OperationObservationSuccessV1)
            projection = observed.projection
            assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
            schema = projection.definition_contract.result_schema
            assert schema is not None
            resolved = await services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=projection.revision,
                    definition_contract_digest=projection.definition_contract.definition_contract_digest,
                    result_schema=schema,
                ),
                result_type,
            )
        finally:
            await services.shutdown()
        assert isinstance(resolved, OperationResultProjectionSuccessV1)
        assert isinstance(resolved.projection, result_type)
        phases = tuple(event.phase_code for event in replay.events if event.kind is OperationEventKind.PHASE)
        return SupervisedRun(resolved.projection, terminal.effect, phases)

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        return asyncio.run(run(profile.storage_root))
