"""The ledger classification measurement, driven by a recorded engine instead of a live model.

The router log lines below follow the llama.cpp server's slot and timing
lines the parser targets; the command envelopes are produced by the product's
own result models and envelope writers, then read back through the harness's
envelope parser, so nothing here starts llama-server, the runtime or a model.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import logging
import socket
import tempfile
import threading
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, override
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, JsonValue, SecretStr, TypeAdapter

from cadrumo.application.ledger.classification_job_consent import off_host_consent_refused
from cadrumo.application.ledger.classification_job_contracts import (
    LedgerClassifyJobApplyItemResult,
    LedgerClassifyJobApplyRefusal,
    LedgerClassifyJobApplyResult,
    LedgerClassifyJobChangeResult,
    LedgerClassifyJobItemProjection,
    LedgerClassifyJobLaneProjection,
    LedgerClassifyJobProjection,
    LedgerClassifyJobProposalProjection,
    LedgerClassifyJobReadResult,
    LedgerClassifyJobRunResult,
    LedgerClassifyJobStateCounts,
)
from cadrumo.core.errors.error_codes import (
    ErrorCategory,
    build_error_envelope,
    get_error_exit_code,
    render_error_json,
)
from cadrumo.core.json_contract import emit_json_success
from cadrumo.core.logging import LOG_FILE_FORMAT
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo.domain.transactions.classification_job import (
    ClassificationConsentScope,
    ClassificationItemFailureCause,
    ClassificationItemState,
    ClassificationJobScopeKind,
    ClassificationJobStatus,
)
from cadrumo.domain.transactions.enums import BusinessClassification
from cadrumo.entrypoints.cli.ledger_business_payloads import ConsentedDispatchPayload, EvidenceConsentListResult
from cadrumo.entrypoints.cli.ledger_llm_payloads import LedgerClassifyLlmSuggestResult
from cadrumo.entrypoints.cli.ledger_results import LedgerListResult, LedgerListRowPayload
from cadrumo_agent_service.admin import AdminAction, AdminServer
from cadrumo_agent_service.providers.application.contracts import LocalEngineStatus, LocalModelListStatus
from cadrumo_agent_service.providers.application.local_model_list import LocalModelListService
from cadrumo_agent_service.providers.application.served_catalog import catalog_nonconformance
from cadrumo_agent_service.providers.application.service import BaseUrlChange, ProviderSettingsService
from cadrumo_agent_service.providers.application.tests.memory_store import (
    MemoryLocalModelListStore,
    MemoryProviderSettingsStore,
)
from cadrumo_agent_service.providers.application.tests.synthetic_catalog import (
    GATEWAY_LANE,
    HOSTED_TEXT_MODELS,
    KEYLESS_TEXT_MODEL,
    ProvidedProviderCatalogSource,
    StaticLiveModels,
    UnavailableCatalogSource,
    engine_catalog,
)
from cadrumo_agent_service.providers.domain.record import ListedModel, LocalEngine, LocalPlacement
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.sign_in_refusal_projection import session_refusal_context, session_refusal_translation_key
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.model_runs import ModelRunTaskKind
from dev.desktop_agent_live.disposable_root import enclosing_git_project
from dev.paths import REPO_ROOT, TEMP_ROOT
from dev.runtime_lifecycle.agent_service_session import AgentServiceSession
from dev.runtime_lifecycle.caller_owned_root import AcceptanceError, parse_envelope
from dev.runtime_lifecycle.service_admin_channel import (
    owned_service_credential,
    owned_service_settings,
    service_admin,
)

from .. import ledger_classification_speed as harness
from ..ledger_classification_speed import (
    PREREQUISITE_ABSENT,
    KeptSignInCli,
    PrerequisiteAbsentError,
    Presented,
    ScratchInGitProjectError,
    ServerFacts,
    ServerLog,
    SetupNotAppliedError,
    SetupStepRefusedError,
    apply_window_settings,
    classify_flags,
    copy_run_logs,
    default_scratch_parent,
    distribution,
    lane_model,
    measure_ledger,
    model_weights,
    movement_record,
    output_directory,
    parse_arguments,
    prerequisite_absence,
    presented_context,
    preset_text,
    require_scratch_outside_git,
    router_id,
    run_record_count,
    sign_in_ended,
    summarise,
    synthetic_movements,
    transaction_ids,
    wait_healthy,
    write_statement,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = datetime.now(UTC).year
"""Any calendar year serves the synthetic rows; the harness books into the registry horizon."""


# --- recorded llama.cpp router output -------------------------------------------------------------


def _request_lines(
    task: int,
    *,
    prompt: int,
    evaluated: int,
    prompt_ms: str,
    generated: int,
    generation_ms: str,
    legacy_prompt_key: bool = False,
) -> list[str]:
    """One chat request as the llama.cpp server logs it: slot lines, timing block and the access line."""
    key = "n_prompt_tokens" if legacy_prompt_key else "task.n_tokens"
    cached = prompt - evaluated
    return [
        "srv  params_from_: Chat format: Content-only",
        f"slot launch_slot_: id  0 | task {task} | processing task",
        f"slot update_slots: id  0 | task {task} | new prompt, n_ctx_slot = 8192, n_keep = 0, {key} = {prompt}",
        f"slot update_slots: id  0 | task {task} | n_past = {cached}, memory_seq_rm [{cached}, end)",
        f"slot update_slots: id  0 | task {task} | prompt done, n_past = {prompt}, n_tokens = {evaluated}",
        f"slot print_timing: id  0 | task {task} | ",
        f"prompt eval time =     {prompt_ms} ms / {evaluated:5d} tokens (    1.00 ms per token,   100.00 tokens per"
        " second)",
        f"       eval time =    {generation_ms} ms / {generated:5d} tokens (   30.00 ms per token,    33.00 tokens per"
        " second)",
        f"      total time =    9999.99 ms / {prompt + generated:5d} tokens",
        f"slot      release: id  0 | task {task} | stop processing: n_past = {prompt + generated}, truncated = 0",
        "srv  update_slots: all slots are idle",
        "srv  log_server_r: request: POST /v1/chat/completions 127.0.0.1 200",
    ]


def _product_log_line(message: str) -> str:
    """A product log line in the product's own file format."""
    record = logging.LogRecord("cadrumo.adapters.outbound.llm.client", logging.INFO, __file__, 1, message, None, None)
    record.diagnostic_context = "-"
    return logging.Formatter(LOG_FILE_FORMAT).format(record)


def _run_record() -> str:
    return _product_log_line(
        "llm request completed provider=llamacpp model=synthetic-text:4b input_tokens=400 output_tokens=40"
    )


# --- recorded command envelopes ---------------------------------------------------------------------


def _transaction_id(index: int) -> str:
    return f"{index + 1:064x}"


def _success(command: str, result: object) -> dict[str, Any]:
    stream = io.StringIO()
    emit_json_success(command, result, stream=stream)
    return parse_envelope(stream.getvalue(), "")


def _suggestion(index: int, category: str) -> dict[str, Any]:
    return _success(
        "ledger.classify",
        LedgerClassifyLlmSuggestResult(
            llm=True,
            provider="llamacpp",
            transaction_id=_transaction_id(index),
            classification="business",
            category=category,
            confidence="0.9",
            reason="Synthetic reason.",
            provenance="llm:synthetic-text:4b",
        ),
    )


def _refusal(code: RefusalCode) -> tuple[int, dict[str, Any], str]:
    error = RefusalError(code)
    envelope = build_error_envelope(error)
    exit_code = get_error_exit_code(ErrorCategory(envelope.category))
    return exit_code, parse_envelope("", render_error_json(error, command="ledger.classify")), envelope.code


def _listing(count: int) -> dict[str, Any]:
    stamp = datetime(_YEAR, 1, 2, tzinfo=UTC).isoformat()
    rows = [
        LedgerListRowPayload(
            full_id=_transaction_id(index),
            display_id=_transaction_id(index)[:12],
            transaction_id=_transaction_id(index),
            date=f"{_YEAR}-01-02",
            booked_date=f"{_YEAR}-01-02",
            amount="10.00",
            currency="EUR",
            direction="expense",
            description=f"Synthetic movement {index}",
            business_classification="unclassified",
            lifecycle_state="active",
            review_status="pending",
            classified_by="none",
            classification_decided_by="none",
            figures_derived=False,
            created_at=stamp,
            modified_at=stamp,
        )
        for index in range(count)
    ]
    return _success("ledger.list", LedgerListResult(bucket_id="synthetic-bucket", rows=rows, total=count, shown=count))


@dataclass(frozen=True)
class _Ask:
    """One recorded classify answer: wall seconds, exit, envelope, router lines and product lines."""

    seconds: float
    code: int
    envelope: dict[str, Any]
    server: list[str]
    product: list[str]


class _RecordedEngine:
    """A TimedCli replaying recorded answers, writing the router's and product's log lines as a live run would."""

    def __init__(self, log: ServerLog, product_root: Path, asks: Sequence[_Ask], repeats: Sequence[_Ask]) -> None:
        self.log = log
        self.product_log = product_root / "logs" / "cadrumo.log"
        self.product_log.parent.mkdir(parents=True, exist_ok=True)
        self.product_log.write_text(_product_log_line("startup before the measured window") + "\n", encoding="utf-8")
        self.asks = list(asks)
        self.repeats = list(repeats)
        self.calls: list[tuple[str, ...]] = []
        self.listing = _listing(len(asks))
        self.import_answer: tuple[int, dict[str, Any]] = (0, {"status": "success", "result": {}})

    def __call__(self, *arguments: str) -> tuple[float, int, dict[str, Any]]:
        self.calls.append(arguments)
        verb = arguments[2]
        if verb == "import":
            code, envelope = self.import_answer
            return 0.75, code, envelope
        if verb == "list":
            return 0.25, 0, self.listing
        if verb == "history":
            return 0.125, 0, {}
        assert verb == "classify"
        ask = (self.asks or self.repeats).pop(0)
        for line in ask.server:
            self.log.append(line)
        with self.product_log.open("a", encoding="utf-8") as file:
            file.writelines(line + "\n" for line in ask.product)
        return ask.seconds, ask.code, ask.envelope


@pytest.fixture
def server_log(tmp_path: Path) -> ServerLog:
    log = ServerLog(tmp_path / "llama-server.log")
    log.append("main: server is listening on http://127.0.0.1:0 - starting the main loop")
    return log


def _recorded_asks() -> tuple[list[_Ask], str]:
    refusal_exit, refusal_envelope, refusal_code = _refusal(RefusalCode.TIMEOUT)
    asks = [
        _Ask(
            3.0,
            0,
            _suggestion(0, "material_oficina"),
            _request_lines(0, prompt=412, evaluated=412, prompt_ms="812.40", generated=46, generation_ms="1530.25"),
            [_run_record()],
        ),
        _Ask(
            3.5,
            0,
            _suggestion(1, "suministros"),
            [
                *_request_lines(1, prompt=420, evaluated=14, prompt_ms="30.10", generated=40, generation_ms="1300.00"),
                *_request_lines(
                    2,
                    prompt=470,
                    evaluated=50,
                    prompt_ms="95.50",
                    generated=38,
                    generation_ms="1250.50",
                    legacy_prompt_key=True,
                ),
            ],
            [_run_record(), _run_record()],
        ),
        _Ask(
            5.0,
            refusal_exit,
            refusal_envelope,
            _request_lines(3, prompt=418, evaluated=12, prompt_ms="28.00", generated=64, generation_ms="2100.00"),
            [_product_log_line("model run refused")],
        ),
        _Ask(
            2.0,
            0,
            _suggestion(3, "material_oficina"),
            _request_lines(4, prompt=415, evaluated=9, prompt_ms="20.00", generated=42, generation_ms="1400.00"),
            [_run_record()],
        ),
    ]
    return asks, refusal_code


def _repeats() -> list[_Ask]:
    return [
        _Ask(
            1.5,
            0,
            _suggestion(index, "material_oficina"),
            _request_lines(
                10 + index, prompt=412, evaluated=1, prompt_ms="5.00", generated=46, generation_ms="1500.00"
            ),
            [_run_record()],
        )
        for index in range(3)
    ]


# --- pure parts --------------------------------------------------------------------------------------


def test_synthetic_movements_are_deterministic_dated_in_the_year_and_signed_by_direction() -> None:
    rows = synthetic_movements(40, _YEAR, seed=7)
    assert rows == synthetic_movements(40, _YEAR, seed=7)
    assert rows != synthetic_movements(40, _YEAR, seed=8)
    assert len(rows) == 40
    assert len({row["referencia"] for row in rows}) == 40
    assert rows[0]["referencia"] == "SYN0007000000"
    incomes = {name for name, _ in harness._INCOME}
    for index, row in enumerate(rows):
        assert datetime.strptime(row["fecha"], "%d/%m/%Y").year == _YEAR
        assert row["moneda"] == "EUR"
        assert row["concepto"].endswith(f" {index + 1}")
        assert "," in row["importe"]
        assert "." not in row["importe"]
        assert row["importe"].startswith("-") == (row["beneficiario"] not in incomes)


def test_statement_is_a_semicolon_csv_that_reads_back_to_the_rows(tmp_path: Path) -> None:
    rows = synthetic_movements(5, _YEAR, seed=1)
    path = tmp_path / "statement.csv"
    write_statement(path, rows)
    with path.open(encoding="utf-8", newline="") as file:
        assert list(csv.DictReader(file, delimiter=";")) == rows
    assert path.read_text(encoding="utf-8").splitlines()[0] == "fecha;concepto;importe;moneda;beneficiario;referencia"


def test_router_lines_yield_requests_tokens_and_times_including_a_reask() -> None:
    lines = [
        *_request_lines(1, prompt=420, evaluated=14, prompt_ms="30.10", generated=40, generation_ms="1300.00"),
        *_request_lines(
            2,
            prompt=470,
            evaluated=50,
            prompt_ms="95.50",
            generated=38,
            generation_ms="1250.50",
            legacy_prompt_key=True,
        ),
        "srv  log_server_r: request: GET /health 127.0.0.1 200",
    ]
    facts = ServerFacts.read(lines)
    assert facts == ServerFacts(
        chat_requests=2,
        prompt_tokens=(420, 470),
        prompt_eval_tokens=(14, 50),
        prompt_eval_ms=(30.10, 95.50),
        generated_tokens=(40, 38),
        generation_ms=(1300.00, 1250.50),
    )
    assert facts.as_json()["prompt_tokens"] == [420, 470]
    assert facts.model_ms == pytest.approx(30.10 + 95.50 + 1300.00 + 1250.50)
    assert ServerFacts.read([]).as_json() == {
        "proxied_requests": 0,
        "chat_requests": 0,
        "prompt_tokens": [],
        "prompt_eval_tokens": [],
        "prompt_eval_ms": [],
        "generated_tokens": [],
        "generation_ms": [],
        "model_ms": None,
    }


# The router's own lines of one movement in the run-5 log (bundled llama.cpp b12184 in router mode): the
# gateway's and the worker's model reads and the chat request, each proxied to the spawned instance.
_ROUTER_LINES = (
    "\x1b[34m1.54.351.519\x1b[0m \x1b[32mI \x1b[0msrv  proxy_reques: proxying request to model m-56b131ebc138fe65 on"
    " port 59591",
    "\x1b[34m1.55.792.721\x1b[0m \x1b[32mI \x1b[0msrv  proxy_reques: proxying request to model m-56b131ebc138fe65 on"
    " port 59591",
    "\x1b[34m1.55.825.918\x1b[0m \x1b[32mI \x1b[0msrv  proxy_reques: proxying request to model m-56b131ebc138fe65 on"
    " port 59591",
)


def test_router_lines_alone_carry_no_model_time_never_a_zero_one() -> None:
    facts = ServerFacts.read(_ROUTER_LINES)
    assert facts.proxied_requests == 3
    assert facts.chat_requests == 0
    assert facts.model_ms is None


def test_instance_lines_the_router_forwards_with_their_port_and_colours_yield_the_timings() -> None:
    forwarded = [
        f"[59591] \x1b[34m0.10.{index:03d}.000\x1b[0m \x1b[32mI \x1b[0m{line}"
        for index, line in enumerate(
            _request_lines(7, prompt=600, evaluated=600, prompt_ms="1500.00", generated=30, generation_ms="900.50")
        )
    ]
    facts = ServerFacts.read([*_ROUTER_LINES, *forwarded])
    assert facts.proxied_requests == 3
    assert facts.chat_requests == 1
    assert (facts.prompt_tokens, facts.prompt_eval_tokens, facts.generated_tokens) == ((600,), (600,), (30,))
    assert facts.model_ms == pytest.approx(2400.50)
    # An instance that logs no access line at its verbosity still counts its completed request by its timings.
    without_access = [line for line in forwarded if "log_server_r" not in line]
    assert ServerFacts.read(without_access).chat_requests == 1


_TIMED: dict[str, Any] = {
    "prompt": 400,
    "evaluated": 400,
    "prompt_ms": "600.00",
    "generated": 20,
    "generation_ms": "400.00",
}


def test_a_movement_without_server_timings_has_no_model_time_and_the_summary_says_how_many_had_one() -> None:
    timed = movement_record(0, 3.0, 0, {}, _request_lines(0, **_TIMED), [], 3.0)
    untimed = [movement_record(index, 2.0, 0, {}, list(_ROUTER_LINES), [], 3.0 + index) for index in (1, 2)]
    late = movement_record(3, 2.5, 0, {}, _request_lines(3, **_TIMED), [], 6.0)
    assert timed["model_ms"] == pytest.approx(1000.0)
    assert timed["outside_model_seconds"] == pytest.approx(2.0)
    assert untimed[0]["model_ms"] is None and untimed[0]["outside_model_seconds"] is None

    summary = summarise([timed, *untimed, late])
    assert summary["succeeded_with_model_timings"] == 2
    assert summary["model_ms_per_item_warm"]["n"] == 1
    assert summary["outside_model_seconds_per_item_warm"]["max"] == pytest.approx(1.5)
    assert summary["model_seconds_total"] == pytest.approx(2.0)
    assert summary["outside_model_seconds_total"] == pytest.approx(3.5)
    assert summary["model_share_of_wall"] == pytest.approx(2.0 / 5.5, abs=1e-4)
    assert summary["proxied_requests_per_item"]["max"] == 3.0

    nothing = summarise(untimed)
    assert nothing["succeeded_with_model_timings"] == 0
    assert nothing["model_seconds_total"] is None and nothing["model_share_of_wall"] is None
    assert nothing["model_ms_per_item_warm"]["n"] == 0


def test_both_llama_server_streams_drain_into_one_log_and_file_in_arrival_order(tmp_path: Path) -> None:
    log = ServerLog(tmp_path / "llama-server.log", sink=(tmp_path / "llama-server.log").open("w", encoding="utf-8"))
    harness.drain_lines(io.BytesIO(b"srv router line\r\n"), log)
    harness.drain_lines(io.BytesIO(b"[59591] prompt eval time = 1.00 ms / 2 tokens\n"), log)
    log.close()
    log.append("after close")
    assert log.lines == ["srv router line", "[59591] prompt eval time = 1.00 ms / 2 tokens", "after close"]
    assert (tmp_path / "llama-server.log").read_text(encoding="utf-8").splitlines() == log.lines[:2]


def test_run_records_count_only_completed_model_runs() -> None:
    lines = [_run_record(), _product_log_line("llm request started provider=llamacpp"), _run_record()]
    assert run_record_count(lines) == 2
    assert run_record_count([]) == 0


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([], {"n": 0, "mean": None, "p50": None, "p95": None, "min": None, "max": None}),
        ([4.0], {"n": 1, "mean": 4.0, "p50": 4.0, "p95": 4.0, "min": 4.0, "max": 4.0}),
        (
            [float(value) for value in range(10, 0, -1)],
            {"n": 10, "mean": 5.5, "p50": 5.5, "p95": 10.0, "min": 1.0, "max": 10.0},
        ),
        (
            [float(value) for value in range(1, 21)],
            {"n": 20, "mean": 10.5, "p50": 10.5, "p95": 19.0, "min": 1.0, "max": 20.0},
        ),
    ],
)
def test_distribution_reports_nearest_rank_percentiles(values: list[float], expected: dict[str, object]) -> None:
    assert distribution(values) == expected


def _served_catalog(*, llamacpp_context: int | None) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    digest = "sha256:" + "0" * 64

    def model(entry: str, name: str, context: int | None) -> dict[str, Any]:
        return {
            "entry_id": entry,
            "model": name,
            "display_name": f"Synthetic {name}",
            "description": None,
            "capabilities": [],
            "native_control_ids": [],
            "efforts": ["low"],
            "default_effort": "low",
            "multi_agent_generation": None,
            "vision": False,
            "size_bytes": None,
            "context_length": 32768,
            "licence": {"spdx": None, "name": "Synthetic licence", "digest": digest},
            "llamacpp_default_context": context,
            "installed": True,
        }

    def lane(provider: str, models: list[dict[str, Any]], recommended: str) -> dict[str, Any]:
        local = provider == "llamacpp"
        health: dict[str, Any] = {
            "configured": "available",
            "transport": "available",
            "authentication": "not_applicable" if local else "authenticated",
            "catalog": "available",
            "admission": "unproven",
            "selectable": True,
            "reasons": [],
            "checked_at": now,
        }
        if local:
            health["engine"] = {"engine": "llamacpp", "state": "running", "reason": None, "door": None}
        return {
            "provider_id": provider,
            "transport": "api",
            "display_name": f"Synthetic {provider}",
            "auth_kind": "none" if local else "api_key",
            "execution_mode": "synthetic",
            "executable": True,
            "model_source": "catalog",
            "health": health,
            "catalog": {
                "schema_version": 2,
                "state": {
                    "status": "available",
                    "checked_at": now,
                    "revision": None,
                    "expires_at": None,
                    "reason": None,
                },
                "recommended_entry_id": recommended,
                "recommended": {"text": recommended},
                "models": models,
                "native_controls": [],
            },
            "hosted_certification": "unknown",
            "capability_proofs": [],
            "background_requests": {
                "text": "proven",
                "image": "unsupported",
                "pdf": "unsupported",
                "options": [],
                "accepts_images": False,
                "accepts_pdfs": False,
            },
            "model_download": "required" if local else "none",
        }

    hosted = model("hosted-reader", "hosted-reader", None)
    hosted.pop("installed")
    return {
        "api_version": "v1",
        "providers": [
            lane("deepseek", [hosted], "hosted-reader"),
            lane(
                "llamacpp",
                [
                    model("synthetic-text-4b", "synthetic-text:4b", llamacpp_context),
                    model("synthetic-text-8b", "synthetic-text:8b", 4096),
                ],
                "synthetic-text-4b",
            ),
        ],
        "task_kinds": [
            {
                "id": "classification",
                "display_name": "Synthetic classification",
                "description": "A synthetic sentence about labelling a record.",
            },
            {
                "id": "extraction",
                "display_name": "Synthetic extraction",
                "description": "A synthetic sentence about reading fields out of a document.",
            },
        ],
    }


def test_lane_selection_reads_the_served_catalogue_llamacpp_lane_not_the_first_lane() -> None:
    catalog = _served_catalog(llamacpp_context=8192)
    assert catalog_nonconformance(catalog) is None
    assert lane_model(catalog, None) == ("llamacpp_api", "synthetic-text:4b", 8192)
    assert lane_model(catalog, "synthetic-text:8b") == ("llamacpp_api", "synthetic-text:8b", 4096)
    assert lane_model(catalog, "synthetic-text-8b") == ("llamacpp_api", "synthetic-text:8b", 4096)
    assert lane_model(catalog, "other:1b") == ("llamacpp_api", "other:1b", None)
    assert lane_model(_served_catalog(llamacpp_context=None), None) == ("llamacpp_api", "synthetic-text:4b", None)


def test_lane_selection_refuses_a_catalogue_without_a_llamacpp_lane() -> None:
    catalog = _served_catalog(llamacpp_context=8192)
    catalog["providers"] = catalog["providers"][:1]
    with pytest.raises(AcceptanceError):
        lane_model(catalog, None)
    with pytest.raises(AcceptanceError):
        lane_model({"kind": "refused", "code": "catalog_unavailable"}, None)


def test_presented_context_is_the_catalogue_context_and_never_above_it() -> None:
    assert presented_context(None, 8192, "synthetic-text:4b") == 8192
    assert presented_context(4096, 8192, "synthetic-text:4b") == 4096
    assert presented_context(None, 4096, "synthetic-text:8b") == 4096
    for requested in (8193, 16384, 0, -1):
        with pytest.raises(AcceptanceError):
            presented_context(requested, 8192, "synthetic-text:4b")
    with pytest.raises(AcceptanceError):
        presented_context(4096, None, "other:1b")


def test_preset_names_the_model_by_digest_and_pins_cpu_only_when_asked(tmp_path: Path) -> None:
    presented = Presented(name="synthetic-text:4b", weights=tmp_path / "blob", context=8192)
    section = router_id("synthetic-text:4b")
    assert section.startswith("m-")
    assert len(section) == 18
    assert ":" not in section
    assert preset_text(presented, cpu_only=False) == (
        f"[{section}]\nalias = synthetic-text:4b\nmodel = {tmp_path / 'blob'}\nctx-size = 8192\n\n"
    )
    assert preset_text(presented, cpu_only=True).endswith("ctx-size = 8192\nn-gpu-layers = 0\n\n")


def _store_model(store: Path, name: str, payload: bytes, *, size: int | None = None) -> Path:
    model, _, tag = name.partition(":")
    manifest = store / "manifests" / "registry.ollama.ai" / "library" / model / tag
    manifest.parent.mkdir(parents=True)
    digest = "sha256:" + "a" * 64
    manifest.write_text(
        json.dumps(
            {
                "layers": [
                    {"mediaType": "application/vnd.ollama.image.license", "digest": "sha256:" + "b" * 64, "size": 1},
                    {
                        "mediaType": "application/vnd.ollama.image.model",
                        "digest": digest,
                        "size": len(payload) if size is None else size,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    blob = store / "blobs" / digest.replace(":", "-")
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(payload)
    return blob


def test_model_weights_resolve_the_stored_layer_and_name_an_absent_or_damaged_model(tmp_path: Path) -> None:
    store = tmp_path / "models"
    blob = _store_model(store, "synthetic-text:4b", b"GGUF synthetic")
    assert model_weights(store, "synthetic-text:4b") == blob
    with pytest.raises(PrerequisiteAbsentError):
        model_weights(store, "synthetic-text:8b")
    blob.unlink()
    with pytest.raises(PrerequisiteAbsentError):
        model_weights(store, "synthetic-text:4b")
    damaged = tmp_path / "damaged"
    _store_model(damaged, "synthetic-text:4b", b"GGUF", size=99)
    with pytest.raises(AcceptanceError):
        model_weights(damaged, "synthetic-text:4b")


# --- the measured path with a recorded engine -------------------------------------------------------


def test_recorded_engine_run_yields_per_movement_records_and_summary(
    tmp_path: Path, server_log: ServerLog, capsys: pytest.CaptureFixture[str]
) -> None:
    asks, refusal_code = _recorded_asks()
    engine = _RecordedEngine(server_log, tmp_path / "root", asks, _repeats())
    timings: dict[str, float] = {}
    fields = measure_ledger(
        engine,
        server_log,
        tmp_path / "root",
        tmp_path,
        count=4,
        year=_YEAR,
        seed=3,
        mode="classification",
        budget_seconds=600.0,
        timings=timings,
    )

    imported = engine.calls[0]
    assert imported[:4] == ("app", "ledger", "import", "--file")
    with Path(imported[4]).open(encoding="utf-8", newline="") as file:
        assert list(csv.DictReader(file, delimiter=";")) == synthetic_movements(4, _YEAR, seed=3)
    classified = [call for call in engine.calls if call[2] == "classify"]
    assert classified == [
        ("app", "ledger", "classify", _transaction_id(index), "--llm") for index in (0, 1, 2, 3, 0, 1, 2)
    ]
    assert [call[3] for call in engine.calls if call[2] == "history"] == [_transaction_id(i) for i in range(4)]
    assert timings["import_seconds"] == 0.75
    assert timings["list_seconds"] == 0.25
    assert timings["classify_wall_seconds"] > 0
    assert fields["cli_baseline_history_seconds"]["n"] == 4
    assert fields["cli_baseline_history_seconds"]["mean"] == 0.125
    assert "stopped_at_budget" not in fields

    items = fields["items"]
    assert [item["index"] for item in items] == [0, 1, 2, 3]
    assert [item["seconds"] for item in items] == [3.0, 3.5, 5.0, 2.0]
    assert [item["exit"] for item in items] == [0, 0, _refusal(RefusalCode.TIMEOUT)[0], 0]
    assert items[2]["exit"] != 0
    assert [item["error"] for item in items] == [None, None, refusal_code, None]
    assert [item.get("category") for item in items] == ["material_oficina", "suministros", None, "material_oficina"]
    assert "classification" not in items[2]
    assert items[0]["classification"] == "business"
    assert items[0]["confidence"] == "0.9"
    assert items[0]["provider"] == "llamacpp"
    assert [item["run_records"] for item in items] == [1, 2, 0, 1]
    assert items[1]["server"] == {
        "proxied_requests": 0,
        "chat_requests": 2,
        "prompt_tokens": [420, 470],
        "prompt_eval_tokens": [14, 50],
        "prompt_eval_ms": [30.10, 95.50],
        "generated_tokens": [40, 38],
        "generation_ms": [1300.00, 1250.50],
        "model_ms": 2676.1,
    }
    assert items[1]["model_ms"] == pytest.approx(2676.10)
    assert items[1]["outside_model_seconds"] == pytest.approx(3.5 - 2.6761)
    assert items[0]["server"]["chat_requests"] == 1
    assert items[0]["server"]["prompt_eval_tokens"] == [412]
    assert [item["elapsed"] for item in items] == sorted(item["elapsed"] for item in items)

    repeat = fields["repeat_same_movement"]
    assert [entry["seconds"] for entry in repeat] == [1.5, 1.5, 1.5]
    assert all(entry["server"]["prompt_eval_tokens"] == [1] for entry in repeat)

    progress = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [line["item"] for line in progress] == [0, 1, 2, 3]
    assert progress[2]["error"] == refusal_code

    summary = summarise(items)
    assert summary["attempted"] == 4
    assert summary["succeeded"] == 3
    assert summary["errors"] == {refusal_code: 1}
    assert summary["first_result_seconds"] == 3.0
    assert summary["per_item_seconds_warm"] == {"n": 2, "mean": 2.75, "p50": 2.75, "p95": 3.5, "min": 2.0, "max": 3.5}
    assert summary["movements_per_minute"] == round(60 * 4 / 13.5, 3)
    assert summary["movements_per_minute_warm"] == round(60 * 2 / 5.5, 3)
    assert summary["chat_requests_per_item"] == {"n": 4, "mean": 1.25, "p50": 1.0, "p95": 2.0, "min": 1.0, "max": 2.0}
    assert summary["reask_items"] == 1
    # Token figures cover every request, the refused movement's included.
    assert summary["prompt_tokens"] == {"n": 5, "mean": 427.0, "p50": 418.0, "p95": 470.0, "min": 412.0, "max": 470.0}
    assert summary["prompt_eval_tokens_after_cache"] == {
        "n": 5,
        "mean": 99.4,
        "p50": 14.0,
        "p95": 412.0,
        "min": 9.0,
        "max": 412.0,
    }
    assert summary["prompt_eval_ms"]["mean"] == pytest.approx(986.0 / 5)
    assert summary["generated_tokens"] == {"n": 5, "mean": 46.0, "p50": 42.0, "p95": 64.0, "min": 38.0, "max": 64.0}
    assert summary["generation_ms"]["mean"] == pytest.approx(7580.75 / 5)
    # The warm model time is the successful movements after the first: 30.10+95.50+1300+1250.50 and 20+1400.
    assert summary["model_ms_per_item_warm"]["n"] == 2
    assert summary["model_ms_per_item_warm"]["min"] == pytest.approx(1420.0)
    assert summary["model_ms_per_item_warm"]["max"] == pytest.approx(2676.10)
    assert summary["outside_model_seconds_per_item_warm"]["min"] == pytest.approx(0.58)
    assert summary["outside_model_seconds_per_item_warm"]["max"] == pytest.approx(0.8239)


def test_saturated_mode_asks_with_saturate(tmp_path: Path, server_log: ServerLog) -> None:
    asks, _ = _recorded_asks()
    engine = _RecordedEngine(server_log, tmp_path / "root", asks[:1], _repeats()[:1])
    measure_ledger(
        engine,
        server_log,
        tmp_path / "root",
        tmp_path,
        count=1,
        year=_YEAR,
        seed=1,
        mode="saturated",
        budget_seconds=600.0,
        timings={},
    )
    assert classify_flags("saturated") == ("--llm", "--saturate")
    assert classify_flags("classification") == ("--llm",)
    assert [call[4:] for call in engine.calls if call[2] == "classify"] == [("--llm", "--saturate")] * 2


def test_an_exhausted_budget_stops_before_asking_and_still_summarises(tmp_path: Path, server_log: ServerLog) -> None:
    asks, _ = _recorded_asks()
    engine = _RecordedEngine(server_log, tmp_path / "root", [], _repeats())
    engine.listing = _listing(len(asks))
    fields = measure_ledger(
        engine,
        server_log,
        tmp_path / "root",
        tmp_path,
        count=4,
        year=_YEAR,
        seed=1,
        mode="classification",
        budget_seconds=-1.0,
        timings={},
    )
    assert fields["stopped_at_budget"] == 0
    assert fields["items"] == []
    assert len(fields["repeat_same_movement"]) == 3
    summary = summarise(fields["items"])
    assert summary["attempted"] == 0
    assert summary["first_result_seconds"] is None
    assert summary["movements_per_minute"] is None


def test_a_refused_import_or_a_short_listing_is_a_setup_failure(tmp_path: Path, server_log: ServerLog) -> None:
    asks, _ = _recorded_asks()
    refused = _RecordedEngine(server_log, tmp_path / "root", asks, [])
    refusal_exit, refusal_envelope, refusal_code = _refusal(RefusalCode.UNAVAILABLE)
    refused.import_answer = (refusal_exit, refusal_envelope)
    arguments: dict[str, Any] = {
        "count": 4,
        "year": _YEAR,
        "seed": 1,
        "mode": "classification",
        "budget_seconds": 600.0,
    }
    with pytest.raises(AcceptanceError, match=refusal_code):
        measure_ledger(refused, server_log, tmp_path / "root", tmp_path, timings={}, **arguments)
    short = _RecordedEngine(server_log, tmp_path / "root", asks, [])
    short.listing = _listing(2)
    with pytest.raises(AcceptanceError, match="lists 2 movements, expected 4"):
        measure_ledger(short, server_log, tmp_path / "root", tmp_path, timings={}, **arguments)


def test_listing_identifiers_are_read_once_each_in_order() -> None:
    listing = _listing(3)
    assert transaction_ids(listing["result"]) == [_transaction_id(index) for index in range(3)]
    assert transaction_ids(
        [{"transaction_id": "a"}, {"nested": [{"transaction_id": "a"}, {"transaction_id": "b"}]}]
    ) == [
        "a",
        "b",
    ]


# --- command line and prerequisites -----------------------------------------------------------------


def test_argument_defaults_put_the_disposable_root_outside_every_git_project() -> None:
    arguments = parse_arguments(["--out", "result.json"])
    scratch = Path(arguments.scratch)
    assert scratch == default_scratch_parent()
    # The agent's own rule: no directory at or above the root may hold ``.git``.
    assert enclosing_git_project(scratch) is None
    assert datetime.strptime(arguments.stamp, "%Y%m%dT%H%M%S")
    # The dated folder and the run's stamp name the same start.
    assert datetime.strptime(arguments.stamp, "%Y%m%dT%H%M%S").date().isoformat() == arguments.day
    assert Path(arguments.package) == REPO_ROOT / "build" / "windows-x64" / "stage" / "Release" / "app"
    assert Path(arguments.model_store) == Path.home() / ".ollama" / "models"
    assert (arguments.count, arguments.mode, arguments.seed, arguments.budget_seconds) == (
        1,
        "classification",
        1,
        1200.0,
    )
    assert (arguments.model, arguments.context, arguments.cpu_only, arguments.inspect) == (None, None, False, False)
    assert (arguments.select, arguments.placement) == (True, LocalPlacement.AUTO)
    assert parse_arguments(["--out", "x", "--cpu-only"]).placement is LocalPlacement.CPU_ONLY
    assert parse_arguments(["--out", "x", "--no-select"]).select is False


def test_the_default_scratch_is_the_account_temporary_folder_not_a_temp_variable(tmp_path: Path) -> None:
    # A test run points TEMP into the checkout; the account folder does not follow it.
    assert default_scratch_parent({"LOCALAPPDATA": str(tmp_path)}) == tmp_path / "Temp"
    assert default_scratch_parent({}) == Path(tempfile.gettempdir())


def test_a_scratch_inside_a_git_project_is_refused_by_the_agents_rule(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    for inside in (checkout, checkout / "not" / "yet" / "made", worktree / ".tmp"):
        with pytest.raises(ScratchInGitProjectError, match="inside the Git project"):
            require_scratch_outside_git(inside)
    with pytest.raises(PrerequisiteAbsentError):
        require_scratch_outside_git(REPO_ROOT / ".tmp" / "ledger-classification-speed")


def test_a_scratch_inside_a_git_project_exits_three_before_anything_starts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "models"
    (store / "manifests").mkdir(parents=True)
    package = _package(tmp_path, llama=True)
    (tmp_path / "project" / ".git").mkdir(parents=True)
    inside = tmp_path / "project" / "scratch"

    def must_not_start(arguments: Any) -> dict[str, Any]:
        raise AssertionError("a refused scratch must stop the run before it starts")

    monkeypatch.setattr(harness, "measure", must_not_start)
    code, said = _main(capsys, "--package", str(package), "--model-store", str(store), "--scratch", str(inside))
    assert code == PREREQUISITE_ABSENT
    assert said["error"] == "ScratchInGitProjectError"
    assert str(tmp_path / "project") in said["absent"]
    assert not inside.exists()


def test_outputs_go_to_the_dated_purpose_folder_with_one_child_per_run() -> None:
    stamp = f"test-{uuid4().hex}"
    day = date(_YEAR, 3, 4)
    purpose = TEMP_ROOT / f"{_YEAR}-03-04-ledger-classification-speed"
    left = purpose.exists()
    outputs = output_directory(stamp, day=day, pid=4242)
    try:
        assert outputs == purpose / f"{stamp}-4242"
        assert outputs.is_dir() and outputs.resolve().is_relative_to(REPO_ROOT.resolve() / ".tmp")
        # Another process started in the same second writes apart; the same run's child is never shared.
        other = output_directory(stamp, day=day, pid=4243)
        assert other != outputs and other.is_dir()
        other.rmdir()
        with pytest.raises(AcceptanceError, match="already exists"):
            output_directory(stamp, day=day, pid=4242)
    finally:
        outputs.rmdir()
        if not left:
            purpose.rmdir()


def test_out_is_required_and_mode_is_closed(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as missing:
        parse_arguments([])
    assert missing.value.code == 2
    with pytest.raises(SystemExit) as unknown:
        parse_arguments(["--out", "x", "--mode", "fast"])
    assert unknown.value.code == 2
    capsys.readouterr()


def _package(tmp_path: Path, *, llama: bool) -> Path:
    package = tmp_path / "app"
    folder = package / "bin" / "llama"
    folder.mkdir(parents=True)
    if llama:
        (folder / harness.LLAMA_EXECUTABLE).write_bytes(b"")
    return package


def _main(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, dict[str, Any]]:
    code = harness.main([*argv, "--out", "unused.json"])
    return code, json.loads(capsys.readouterr().err.strip().splitlines()[-1])


def test_absent_package_llama_server_or_model_store_exits_three(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = tmp_path / "models"
    (store / "manifests").mkdir(parents=True)
    code, said = _main(capsys, "--package", str(tmp_path / "nowhere"), "--model-store", str(store))
    assert (code, said) == (PREREQUISITE_ABSENT, {"absent": f"no package at {tmp_path / 'nowhere'}"})
    without_llama = _package(tmp_path / "a", llama=False)
    code, said = _main(capsys, "--package", str(without_llama), "--model-store", str(store))
    assert code == PREREQUISITE_ABSENT
    assert harness.LLAMA_EXECUTABLE in said["absent"]
    package = _package(tmp_path / "b", llama=True)
    code, said = _main(capsys, "--package", str(package), "--model-store", str(tmp_path / "no-store"))
    assert (code, said) == (PREREQUISITE_ABSENT, {"absent": f"no model store at {tmp_path / 'no-store'}"})
    assert prerequisite_absence(package, store) is None


def test_a_model_the_store_does_not_hold_exits_three(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "models"
    (store / "manifests").mkdir(parents=True)
    package = _package(tmp_path, llama=True)

    def measure_up_to_the_model(arguments: Any, document: dict[str, Any]) -> dict[str, Any]:
        # The catalogue named a model; the real store lookup is what refuses.
        model_weights(Path(arguments.model_store), "synthetic-text:4b")
        raise AssertionError("an absent model must stop the run")

    monkeypatch.setattr(harness, "measure", measure_up_to_the_model)
    code, said = _main(capsys, "--package", str(package), "--model-store", str(store))
    assert code == PREREQUISITE_ABSENT
    assert said == {"absent": "the model store holds no manifest for synthetic-text:4b"}


# --- the health wait against a fake llama-server ----------------------------------------------------


class _FakeLlamaServer(BaseHTTPRequestHandler):
    """Answers ``/health`` 503 while loading, then 200, as llama-server does once its router is up."""

    loading_answers = 2
    lock = threading.Lock()

    def do_GET(self) -> None:
        with self.lock:
            loading = type(self).loading_answers > 0
            type(self).loading_answers -= 1
        status = 503 if loading or self.path != "/health" else 200
        body = json.dumps({"status": "loading model" if loading else "ok"}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @override
    def log_message(self, format: str, *args: object) -> None:
        del format, args


@pytest.fixture
def fake_llama_server() -> Iterator[str]:
    _FakeLlamaServer.loading_answers = 2
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeLlamaServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"{host!s}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_health_wait_polls_through_loading_until_ok(fake_llama_server: str) -> None:
    assert harness.healthy(fake_llama_server) is False
    wait_healthy(fake_llama_server, 10.0)
    assert _FakeLlamaServer.loading_answers < 0
    assert harness.healthy(fake_llama_server) is True


def test_health_wait_fails_when_nothing_answers_within_the_bound() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        address = f"127.0.0.1:{probe.getsockname()[1]}"
    with pytest.raises(AcceptanceError, match="did not answer /health"):
        wait_healthy(address, 0.3)


# --- the window's settings, through the real admin wire and the real model list service ---------------


_JSON_OBJECT: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])
_LANE = f"{LocalEngine.LLAMACPP.value}_api"
"""The synthetic catalogue's keyless llama.cpp lane."""


class _WindowSettingsService:
    """The agent service's dispatch of the window's settings actions, onto the real model list service.

    It maps each validated request the admin server hands on to the same
    ``LocalModelListService`` call the service makes and answers the result's
    JSON, as the service does; the store is the in-memory one that keeps the
    secure store's revision contract.
    """

    def __init__(self, models: LocalModelListService) -> None:
        self._models = models

    def admin(self, action: AdminAction, **fields: Any) -> JsonValue:
        answer = self._answer(action, fields)
        if answer is None:
            return {"kind": "refused", "code": "invalid_request"}
        return _JSON_OBJECT.validate_python(answer.model_dump(mode="json"))

    def _answer(self, action: AdminAction, fields: dict[str, Any]) -> BaseModel | None:
        models = self._models
        revision = fields.get("expected_revision")
        lane, model = fields.get("provider"), fields.get("model")
        if action == "local_engine":
            return models.engine_status()
        if action == "local_models":
            return models.status()
        if revision is None:
            return None
        if action == "local_engine_choose":
            return models.choose_engine(
                LocalEngine(fields["engine"]), LocalPlacement(fields["placement"]), expected_revision=revision
            )
        if lane is None or model is None:
            return None
        if action == "local_model_add":
            return models.add(lane, model=model, expected_revision=revision)
        if action == "reading_model_choose":
            return models.choose_reading(lane, model=model, expected_revision=revision)
        if action == "task_model_choose":
            listed = ListedModel(lane=lane, model=model)
            return models.choose_task(
                fields["task_kind"], model=listed, effort=fields.get("effort"), expected_revision=revision
            )
        return None


@pytest.fixture
def settings_service() -> Iterator[tuple[LocalModelListService, Any]]:
    """The model list service behind the real admin server, and the harness's owned settings exchange to it."""
    models = LocalModelListService(
        store=MemoryLocalModelListStore(),
        catalog_source=ProvidedProviderCatalogSource(engine_catalog()),
        live_models=StaticLiveModels(),
        default_engine=LocalEngine.LLAMACPP,
    )
    bearer = bytearray(b"synthetic-parent-admin-authority")
    server = AdminServer(_WindowSettingsService(models), bearer=bearer)

    def exchange(action: AdminAction, /, **fields: Any) -> dict[str, Any]:
        return owned_service_settings(bearer, server.port, action, **fields)

    try:
        yield models, exchange
    finally:
        server.close()
        bearer[:] = bytes(len(bearer))


def test_window_settings_store_engine_list_reading_and_classification_model_at_each_read_revision(
    settings_service: tuple[LocalModelListService, Any],
) -> None:
    models, exchange = settings_service
    before = models.engine_status()
    assert isinstance(before, LocalEngineStatus) and not before.chosen

    replies = apply_window_settings(exchange, lane=_LANE, model=KEYLESS_TEXT_MODEL, placement=LocalPlacement.CPU_ONLY)

    assert list(replies) == [
        "local_engine",
        "local_engine_choose",
        "local_model_add",
        "reading_model_choose",
        "task_model_choose",
    ]
    engine = models.engine_status()
    assert isinstance(engine, LocalEngineStatus)
    assert (engine.chosen, engine.engine, engine.placement) == (True, LocalEngine.LLAMACPP, LocalPlacement.CPU_ONLY)
    listed = models.status()
    assert isinstance(listed, LocalModelListStatus)
    assert listed.reading is not None and (listed.reading.lane, listed.reading.model) == (_LANE, KEYLESS_TEXT_MODEL)
    assert [(task.task_kind, task.lane, task.model, task.effort) for task in listed.tasks] == [
        (ModelRunTaskKind.CLASSIFICATION.value, _LANE, KEYLESS_TEXT_MODEL, None)
    ]
    # Each guarded step carried the revision the step before it answered.
    revisions = [replies[step]["revision"] for step in replies]
    assert revisions[-1] == listed.revision
    assert revisions[0] != revisions[1]

    # Asking again stores nothing new and still answers every step.
    again = apply_window_settings(exchange, lane=_LANE, model=KEYLESS_TEXT_MODEL, placement=LocalPlacement.CPU_ONLY)
    assert again["task_model_choose"] == replies["task_model_choose"]


def test_a_setting_changed_between_steps_is_a_named_revision_refusal(
    settings_service: tuple[LocalModelListService, Any],
) -> None:
    models, exchange = settings_service

    def with_a_concurrent_edit(action: AdminAction, /, **fields: Any) -> dict[str, Any]:
        if action == "reading_model_choose":
            # Someone else stores a list change after the harness read its revision.
            current = models.status()
            assert isinstance(current, LocalModelListStatus)
            models.add(_LANE, model="custom-model:test", expected_revision=current.revision)
        return exchange(action, **fields)

    with pytest.raises(SetupStepRefusedError, match="reading_model_choose refused: revision_conflict") as refused:
        apply_window_settings(
            with_a_concurrent_edit, lane=_LANE, model=KEYLESS_TEXT_MODEL, placement=LocalPlacement.AUTO
        )
    assert (refused.value.step, refused.value.code) == ("reading_model_choose", "revision_conflict")
    listed = models.status()
    assert isinstance(listed, LocalModelListStatus) and listed.tasks == ()


def test_an_unknown_lane_or_an_unreadable_catalogue_is_a_named_refusal(
    settings_service: tuple[LocalModelListService, Any],
) -> None:
    _models, exchange = settings_service
    with pytest.raises(SetupStepRefusedError, match="local_model_add refused: unknown"):
        apply_window_settings(exchange, lane="no_such_lane", model=KEYLESS_TEXT_MODEL, placement=LocalPlacement.AUTO)

    models = LocalModelListService(
        store=MemoryLocalModelListStore(),
        catalog_source=UnavailableCatalogSource(),
        live_models=StaticLiveModels(),
        default_engine=LocalEngine.LLAMACPP,
    )
    bearer = bytearray(b"synthetic-parent-admin-authority")
    server = AdminServer(_WindowSettingsService(models), bearer=bearer)
    try:
        with pytest.raises(SetupStepRefusedError, match="local_model_add refused: catalog_unavailable"):
            apply_window_settings(
                lambda action, /, **fields: owned_service_settings(bearer, server.port, action, **fields),
                lane=_LANE,
                model=KEYLESS_TEXT_MODEL,
                placement=LocalPlacement.AUTO,
            )
    finally:
        server.close()


def test_an_answer_outside_the_settings_contract_is_named_not_applied() -> None:
    def departing(action: AdminAction, /, **fields: Any) -> dict[str, Any]:
        return {"engine": "llamacpp"}

    with pytest.raises(SetupNotAppliedError, match="local_engine answered outside its contract"):
        apply_window_settings(departing, lane=_LANE, model=KEYLESS_TEXT_MODEL, placement=LocalPlacement.AUTO)


def test_the_owned_channel_carries_only_settings_and_the_shared_one_stays_read_only() -> None:
    bearer = bytearray(b"synthetic-parent-admin-authority")
    for action in ("set", "auth", "sign_in", "start", "stop", "local_models_reset", "console_environment"):
        with pytest.raises(AcceptanceError, match="local-model settings reads and choices only"):
            owned_service_settings(bearer, 1, action)
    with pytest.raises(AcceptanceError, match="credential frames"):
        owned_service_settings(bearer, 1, "local_engine", secret_bytes=8)
    for action in ("local_engine_choose", "reading_model_choose", "task_model_choose", "local_model_add"):
        with pytest.raises(AcceptanceError, match="permits catalog and status reads only"):
            service_admin(bearer, 1, action)

    shared = object.__new__(AgentServiceSession)
    shared._owned = False
    with pytest.raises(AcceptanceError, match="shared agent service session does not change"):
        shared.settings("local_engine")


# --- the person's sign-in kept across the run ---------------------------------------------------------


def _sign_in_refusal(reason: ProfileSessionRefusalReason) -> dict[str, Any]:
    """The envelope a command answers with when the stored sign-in it resumes was refused for ``reason``."""
    error = CliRefusedBoundaryError(
        translated_message=session_refusal_translation_key(reason, None),
        context=session_refusal_context(reason, None),
    )
    return parse_envelope("", render_error_json(error, command="ledger.classify"))


class _Keeper:
    """A sign-in that ends at a set instant and is renewed for a fixed window, counting renewals."""

    def __init__(self, clock: list[datetime], *, window: timedelta) -> None:
        self.clock = clock
        self.window = window
        self.ends = clock[0] + window
        self.renewed = 0

    def deadline(self) -> datetime | None:
        return self.ends

    def renew(self) -> dict[str, Any]:
        self.renewed += 1
        self.ends = self.clock[0] + self.window
        return {"agent_event": "agent_ready"}


class _LapsingCli:
    """Answers each command after advancing the clock; refuses as the runtime does once the sign-in has ended."""

    def __init__(self, clock: list[datetime], keeper: _Keeper, *, seconds: float) -> None:
        self.clock = clock
        self.keeper = keeper
        self.seconds = seconds
        self.calls = 0
        self.refused = 0

    def __call__(self, *arguments: str) -> tuple[float, int, dict[str, Any]]:
        self.calls += 1
        if self.clock[0] >= self.keeper.ends:
            self.refused += 1
            return 0.1, 4, _sign_in_refusal(ProfileSessionRefusalReason.EXPIRED_IDLE)
        self.clock[0] += timedelta(seconds=self.seconds)
        return self.seconds, 0, {"status": "success", "result": {}}


def test_a_sign_in_ended_refusal_is_told_from_any_other_refusal() -> None:
    for reason in (
        ProfileSessionRefusalReason.EXPIRED_IDLE,
        ProfileSessionRefusalReason.EXPIRED_ABSOLUTE,
        ProfileSessionRefusalReason.ABSENT,
    ):
        assert sign_in_ended(_sign_in_refusal(reason)) == reason.value
    assert sign_in_ended(_sign_in_refusal(ProfileSessionRefusalReason.KEYRING_UNAVAILABLE)) is None
    assert sign_in_ended(_refusal(RefusalCode.TIMEOUT)[1]) is None
    assert sign_in_ended({"status": "success", "result": {}}) is None


def test_the_sign_in_is_renewed_before_it_can_end_during_a_command() -> None:
    clock = [datetime(_YEAR, 3, 1, 9, tzinfo=UTC)]
    keeper = _Keeper(clock, window=timedelta(minutes=15))
    engine = _LapsingCli(clock, keeper, seconds=30.0)
    kept = KeptSignInCli(engine, keeper, clock=lambda: clock[0], margin_seconds=120.0)

    answers = [kept("app", "ledger", "classify", _transaction_id(index), "--llm") for index in range(60)]

    assert all(code == 0 for _seconds, code, _envelope in answers)
    assert engine.refused == 0
    assert engine.calls == 60
    # 30 minutes of commands in a 15-minute sign-in: renewed ahead of its end, never after it.
    assert keeper.renewed == len(kept.renewals) >= 2
    assert {renewal["cause"] for renewal in kept.renewals} == {"ahead_of_end"}
    assert all(renewal["remaining_seconds"] < 120.0 for renewal in kept.renewals)
    assert all(renewal["agent_event"] == "agent_ready" for renewal in kept.renewals)


def test_a_command_refused_because_the_sign_in_ended_runs_again_once_after_signing_in_again() -> None:
    clock = [datetime(_YEAR, 3, 1, 9, tzinfo=UTC)]
    keeper = _Keeper(clock, window=timedelta(minutes=15))
    engine = _LapsingCli(clock, keeper, seconds=30.0)
    kept = KeptSignInCli(engine, keeper, clock=lambda: clock[0], margin_seconds=120.0)
    # The runtime ended the sign-in earlier than the deadline last read said.
    keeper.ends = clock[0]

    seconds, code, _envelope = kept("app", "ledger", "classify", _transaction_id(0), "--llm")

    assert (seconds, code) == (30.0, 0)
    assert (engine.calls, engine.refused, keeper.renewed) == (2, 1, 1)
    assert [renewal["cause"] for renewal in kept.renewals] == [ProfileSessionRefusalReason.EXPIRED_IDLE.value]


def test_a_sign_in_without_a_deadline_is_never_renewed_ahead() -> None:
    clock = [datetime(_YEAR, 3, 1, 9, tzinfo=UTC)]

    class _Silent(_Keeper):
        @override
        def deadline(self) -> datetime | None:
            return None

    keeper = _Silent(clock, window=timedelta(days=1))
    kept = KeptSignInCli(_LapsingCli(clock, keeper, seconds=30.0), keeper, clock=lambda: clock[0])
    kept.keep_ahead()
    kept("app", "ledger", "list")
    assert kept.renewals == []


# --- a run that fails part way still writes what it measured and keeps its logs ---------------------


class _FailingEngine(_RecordedEngine):
    """The recorded engine, failing on the classify ask ``fail_at`` with ``failure``."""

    def __init__(self, *args: Any, fail_at: int, failure: BaseException) -> None:
        super().__init__(*args)
        self.fail_at = fail_at
        self.failure = failure
        self.asked = 0

    @override
    def __call__(self, *arguments: str) -> tuple[float, int, dict[str, Any]]:
        if arguments[2] == "classify":
            if self.asked == self.fail_at:
                raise self.failure
            self.asked += 1
        return super().__call__(*arguments)


@pytest.mark.parametrize(
    ("failure", "exit_code"),
    [(AcceptanceError("the agent service exited"), 1), (KeyboardInterrupt(), 130)],
    ids=["failure", "interruption"],
)
def test_a_run_failing_mid_way_writes_its_partial_json_and_keeps_its_logs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
    exit_code: int,
) -> None:
    store = tmp_path / "models"
    (store / "manifests").mkdir(parents=True)
    package = _package(tmp_path, llama=True)
    scratch = tmp_path / "scratch"
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    root = scratch / "disposable"
    removed: list[Path] = []

    def create(parent: Path) -> Path:
        root.mkdir(parents=True)
        return root

    def remove(target: Path, parent: Path) -> list[str]:
        # The logs must be out before the root goes.
        assert (outputs / "logs" / "session" / "storage" / "logs" / "cadrumo.log").is_file()
        removed.append(target)
        return []

    def measure_on(arguments: Any, document: dict[str, Any], package: Path, root: Path, outputs: Path, *_: Any) -> None:
        storage = root / "session" / "storage"
        (root / "session" / "runtime-stderr.log").parent.mkdir(parents=True)
        (root / "session" / "runtime-stderr.log").write_text("runtime stderr\n", encoding="utf-8")
        log = ServerLog(outputs / "llama-server.log")
        log.append("main: server is listening on http://127.0.0.1:0 - starting the main loop")
        asks, _code = _recorded_asks()
        engine = _FailingEngine(log, storage, asks, _repeats(), fail_at=2, failure=failure)
        timings: dict[str, float] = {}
        document["timings"] = timings
        document["sign_ins"] = []
        measure_ledger(
            engine,
            log,
            storage,
            outputs,
            count=4,
            year=_YEAR,
            seed=3,
            mode="classification",
            budget_seconds=600.0,
            timings=timings,
            fields=document,
        )

    # pytest's temporary folder lies inside this worktree; the refusal itself is tested above.
    monkeypatch.setattr(harness, "require_scratch_outside_git", lambda parent: None)
    monkeypatch.setattr(harness, "create_root", create)
    monkeypatch.setattr(harness, "remove_root", remove)
    monkeypatch.setattr(harness, "output_directory", lambda stamp, *, day, pid: outputs)
    monkeypatch.setattr(harness, "_measure_on", measure_on)
    out = tmp_path / "result.json"

    code = harness.main(
        ["--package", str(package), "--model-store", str(store), "--scratch", str(scratch), "--out", str(out)]
    )
    said = capsys.readouterr().err

    assert code == exit_code, said
    assert removed == [root]
    document = json.loads(out.read_text(encoding="utf-8"))
    assert [item["index"] for item in document["items"]] == [0, 1]
    assert document["phase"] == "classify"
    assert document["failure"]["phase"] == "classify"
    assert document["failure"]["type"] == type(failure).__name__
    assert document["summary"]["complete"] is False
    assert document["summary"]["sign_in_renewals"] == 0
    assert sorted(document["copied_logs"]) == ["session/runtime-stderr.log", "session/storage/logs/cadrumo.log"]
    copied = outputs / "logs" / "session" / "storage" / "logs" / "cadrumo.log"
    assert "startup before the measured window" in copied.read_text(encoding="utf-8")
    assert (outputs / "logs" / "session" / "runtime-stderr.log").read_text(encoding="utf-8") == "runtime stderr\n"


def test_log_copy_skips_links_and_files_that_are_not_logs(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "a" / "logs").mkdir(parents=True)
    (root / "a" / "logs" / "agent.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "a" / "state.db").write_bytes(b"not a log")
    (root / "b.log").write_text("b\n", encoding="utf-8")
    outside = tmp_path / "outside.log"
    outside.write_text("outside\n", encoding="utf-8")
    with contextlib.suppress(OSError):  # a link needs a privilege Windows may withhold
        (root / "linked.log").symlink_to(outside)

    copied = copy_run_logs(root, tmp_path / "out")

    assert sorted(copied) == ["a/logs/agent.jsonl", "b.log"]
    assert not (tmp_path / "out" / "linked.log").exists()
    assert not (tmp_path / "out" / "a" / "state.db").exists()


# --- a hosted lane: the credential file, the lane, the settings and the job queue ------------------------


_CREDENTIAL_VALUE = "synthetic-credential-value-0042"


def _credential_file(tmp_path: Path, text: str, *, name: str = "credentials.env") -> Path:
    path = tmp_path / name
    path.write_bytes(text.encode("utf-8"))
    return path


def test_the_credential_reader_takes_the_last_assignment_and_strips_comments_quotes_and_export(
    tmp_path: Path,
) -> None:
    path = _credential_file(
        tmp_path,
        "\N{ZERO WIDTH NO-BREAK SPACE}# synthetic credential file\r\n"
        "SYN_KEY=first-value-replaced\r\n"
        "OTHER_SYN_KEY=unrelated-value\n"
        "\n"
        "  export SYN_KEY = 'synthetic-credential-value-0042'  # trailing comment\n"
        "SYN_KEY_LONGER=not-this-one\n"
        "SYN_PLAIN=plain-value # comment\n"
        'SYN_URL="https://gateway.example.invalid/v1"\n',
    )
    value = harness.read_credential(path, "SYN_KEY")
    assert value == bytearray(_CREDENTIAL_VALUE.encode())
    assert harness.read_credential(path, "SYN_PLAIN") == bytearray(b"plain-value")
    assert harness.read_credential(path, "SYN_URL") == bytearray(b"https://gateway.example.invalid/v1")
    harness.wipe(value)
    assert not any(value)


def test_a_credential_refusal_names_the_file_and_variable_never_the_value(tmp_path: Path) -> None:
    path = _credential_file(tmp_path, f"SYN_KEY={_CREDENTIAL_VALUE}\nSYN_EMPTY=\nSYN_QUOTED_EMPTY=''\n")
    refusals = [
        (path, "SYN_ABSENT", "assigns no SYN_ABSENT"),
        (path, "SYN_EMPTY", "SYN_EMPTY is empty"),
        (path, "SYN_QUOTED_EMPTY", "SYN_QUOTED_EMPTY is empty"),
        (path, "not a name", "is not a variable name"),
        (tmp_path / "absent.env", "SYN_KEY", "cannot be read"),
    ]
    for source, variable, said in refusals:
        with pytest.raises(harness.CredentialFileError, match=said) as refused:
            harness.read_credential(source, variable)
        assert _CREDENTIAL_VALUE not in str(refused.value)
        assert _CREDENTIAL_VALUE not in repr(refused.value)
        assert refused.value.__cause__ is None
    assert isinstance(harness.CredentialFileError("x"), PrerequisiteAbsentError)


def test_a_base_url_comes_from_the_option_or_the_file_and_nothing_means_the_lanes_own(tmp_path: Path) -> None:
    path = _credential_file(tmp_path, f"SYN_KEY={_CREDENTIAL_VALUE}\nSYN_URL=https://gateway.example.invalid/v1\n")
    base = ["--out", "x", "--lane", "deepseek_cli", "--credential-file", str(path), "--credential-variable", "SYN_KEY"]
    assert harness.credential_base_url(parse_arguments(base)) is None
    assert (
        harness.credential_base_url(parse_arguments([*base, "--base-url", "https://other.example.invalid"]))
        == "https://other.example.invalid"
    )
    assert (
        harness.credential_base_url(parse_arguments([*base, "--base-url-variable", "SYN_URL"]))
        == "https://gateway.example.invalid/v1"
    )
    assert harness.base_url_host("https://gateway.example.invalid/v1?token=synthetic") == "gateway.example.invalid"
    assert harness.hosts_only({"entry": {"base_url": "https://a.example.invalid/x", "default_base_url": None}}) == {
        "entry": {"base_url": "a.example.invalid", "default_base_url": None}
    }


def test_hosted_lane_options_default_to_job_mode_and_refuse_what_the_lane_cannot_measure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    hosted = parse_arguments(["--out", "x", "--lane", "deepseek_cli", "--model", "deepseek-flash"])
    assert (hosted.hosted, hosted.mode, hosted.lane, hosted.model, hosted.hostile) == (
        True,
        "job",
        "deepseek_cli",
        "deepseek-flash",
        False,
    )
    assert hosted.apply_count == 5
    local = parse_arguments(["--out", "x"])
    assert (local.hosted, local.mode, local.lane) == (False, "classification", None)
    assert parse_arguments(["--out", "x", "--mode", "job", "--hostile"]).mode == "job"
    assert parse_arguments(["--out", "x", "--lane", "llamacpp_api"]).hosted is False
    refused = (
        ["--lane", "deepseek_cli", "--mode", "classification"],
        ["--lane", "deepseek_cli", "--credential-file", "c.env"],
        ["--lane", "deepseek_cli", "--credential-variable", "SYN_KEY"],
        ["--lane", "deepseek_cli", "--base-url-variable", "SYN_URL"],
        ["--lane", "deepseek_cli", "--base-url", "https://a.example.invalid", "--base-url-variable", "SYN_URL"],
        ["--base-url", "https://a.example.invalid"],
        ["--lane", "deepseek_cli", "--apply-count", "-1"],
    )
    for argv in refused:
        with pytest.raises(SystemExit) as exited:
            parse_arguments(["--out", "x", *argv])
        assert exited.value.code == 2, argv
    capsys.readouterr()


def test_a_hosted_lane_needs_no_llama_server_or_store_and_job_mode_needs_the_package_interpreter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    package = _package(tmp_path, llama=False)
    absent_store = tmp_path / "no-store"
    assert prerequisite_absence(package, absent_store, hosted=True) is None
    assert prerequisite_absence(package, absent_store, hosted=True, job=True) == f"no python.exe in {package}"
    (package / "python.exe").write_bytes(b"")
    assert prerequisite_absence(package, absent_store, hosted=True, job=True) is None

    credentials = _credential_file(tmp_path, f"OTHER_SYN_KEY={_CREDENTIAL_VALUE}\n")
    code, said = _main(
        capsys,
        "--package",
        str(package),
        "--lane",
        "deepseek_cli",
        "--credential-file",
        str(credentials),
        "--credential-variable",
        "SYN_KEY",
    )
    assert code == PREREQUISITE_ABSENT
    assert "assigns no SYN_KEY" in said["absent"]
    assert _CREDENTIAL_VALUE not in json.dumps(said)


def test_a_hosted_lane_is_read_from_the_served_catalogue_and_without_a_recommendation_needs_a_model() -> None:
    catalog = _served_catalog(llamacpp_context=8192)
    assert harness.is_hosted_lane("deepseek_api") and not harness.is_hosted_lane(None)
    assert lane_model(catalog, None, "deepseek_api") == ("deepseek_api", "hosted-reader", None)
    assert lane_model(catalog, "deepseek-flash", "deepseek_api") == ("deepseek_api", "deepseek-flash", None)
    assert lane_model(catalog, None, "llamacpp_api") == ("llamacpp_api", "synthetic-text:4b", 8192)
    facts = harness.lane_facts(catalog, "deepseek_api")
    assert (facts["auth_kind"], facts["background_text"], facts["models"]) == ("api_key", "proven", ["hosted-reader"])
    assert facts["health"]["authentication"] == "authenticated"

    unrecommended = json.loads(json.dumps(catalog))
    unrecommended["providers"][0]["catalog"]["recommended"] = {}
    with pytest.raises(AcceptanceError, match="recommends no text model on deepseek_api; name one with --model"):
        lane_model(unrecommended, None, "deepseek_api")
    with pytest.raises(AcceptanceError, match="serves no lane kimi_cli"):
        lane_model(catalog, "kimi-model", "kimi_cli")


# --- the hosted settings, through the real admin wire and the real provider and model list services -----


_GATEWAY_KEY = b"synthetic-gateway-credential-0001"


class _HostedSettingsService(_WindowSettingsService):
    """The service's dispatch of the lane read and the credential ``set``, beside the window's model settings."""

    def __init__(self, models: LocalModelListService, providers: ProviderSettingsService) -> None:
        super().__init__(models)
        self._providers = providers

    @override
    def admin(self, action: AdminAction, **fields: Any) -> JsonValue:
        answer: BaseModel
        if action == "provider_lanes":
            answer = self._providers.lanes(reads_pending=lambda _lanes: False)
        elif action == "set":
            base_url = fields.get("base_url")
            answer = self._providers.set_credential(
                fields["provider"],
                secret=SecretStr(bytes(fields["secret"]).decode("utf-8")),
                expected_revision=fields["expected_revision"],
                base_url=BaseUrlChange.KEEP if base_url is None else base_url,
            )
        else:
            return super().admin(action, **fields)
        return _JSON_OBJECT.validate_python(answer.model_dump(mode="json"))


type HostedSettings = tuple[
    MemoryProviderSettingsStore, LocalModelListService, Any, Callable[[str], dict[str, JsonValue]]
]
"""The provider store, the model list service, the settings exchange and the credential exchange."""


@pytest.fixture
def hosted_settings() -> Iterator[HostedSettings]:
    """The provider and model list services behind the real admin server, and the harness's two owned channels."""
    catalog = ProvidedProviderCatalogSource(engine_catalog())
    store = MemoryProviderSettingsStore()
    providers = ProviderSettingsService(
        store=store, catalog_source=catalog, selected_engine=lambda: LocalEngine.LLAMACPP
    )
    models = LocalModelListService(
        store=MemoryLocalModelListStore(),
        catalog_source=catalog,
        live_models=StaticLiveModels(),
        default_engine=LocalEngine.LLAMACPP,
    )
    bearer = bytearray(b"synthetic-parent-admin-authority")
    server = AdminServer(_HostedSettingsService(models, providers), bearer=bearer)

    def exchange(action: AdminAction, /, **fields: Any) -> dict[str, Any]:
        return owned_service_settings(bearer, server.port, action, **fields)

    def credential(expected_revision: str, /) -> dict[str, JsonValue]:
        return owned_service_credential(
            bearer,
            server.port,
            provider=GATEWAY_LANE,
            expected_revision=expected_revision,
            base_url=None,
            secret=bytearray(_GATEWAY_KEY),
        )

    try:
        yield store, models, exchange, credential
    finally:
        server.close()
        bearer[:] = bytes(len(bearer))


def test_hosted_settings_store_the_credential_then_the_reading_and_classification_model_with_no_list_step(
    hosted_settings: HostedSettings,
) -> None:
    store, models, exchange, credential = hosted_settings
    model = HOSTED_TEXT_MODELS[0]

    replies, entry = harness.apply_hosted_settings(exchange, credential, lane=GATEWAY_LANE, model=model)

    assert list(replies) == ["provider_lanes", "set", "local_models", "reading_model_choose", "task_model_choose"]
    stored = store.records[GATEWAY_LANE].record.credential
    assert stored is not None and stored.secret.get_secret_value() == _GATEWAY_KEY.decode()
    assert (entry.id, entry.credential_saved) == (GATEWAY_LANE, True)
    assert _GATEWAY_KEY.decode() not in json.dumps(replies)
    recorded = harness.lane_settings_record(entry)
    assert recorded["default_base_url_host"] == "gateway.example.invalid"
    assert _GATEWAY_KEY.decode() not in json.dumps(recorded)
    listed = models.status()
    assert isinstance(listed, LocalModelListStatus)
    assert listed.reading is not None and (listed.reading.lane, listed.reading.model) == (GATEWAY_LANE, model)
    assert [(task.task_kind, task.lane, task.model) for task in listed.tasks] == [
        (ModelRunTaskKind.CLASSIFICATION.value, GATEWAY_LANE, model)
    ]

    # After a renewal of the sign-in the saved credential is kept, not sent again.
    again, kept = harness.apply_hosted_settings(
        exchange, credential, lane=GATEWAY_LANE, model=model, replace_credential=False
    )
    assert "set" not in again and kept.credential_saved


def test_a_hosted_settings_refusal_is_named_and_an_unserved_lane_is_not_applied(
    hosted_settings: HostedSettings,
) -> None:
    store, _models, exchange, credential = hosted_settings

    def at_another_revision(_expected_revision: str, /) -> dict[str, JsonValue]:
        return credential("f" * 64)

    with pytest.raises(SetupStepRefusedError, match="set refused: revision_conflict"):
        harness.apply_hosted_settings(exchange, at_another_revision, lane=GATEWAY_LANE, model=HOSTED_TEXT_MODELS[0])
    assert GATEWAY_LANE not in store.records
    with pytest.raises(SetupNotAppliedError, match="lists no lane no_such_lane"):
        harness.apply_hosted_settings(exchange, credential, lane="no_such_lane", model=HOSTED_TEXT_MODELS[0])


# --- the classification job queue, with recorded job answers in the product's own contracts --------------


_CREATED = datetime(_YEAR, 3, 1, 9, tzinfo=UTC)
_PROFILE = UUID(int=7)
_JOB_ID = "a" * 64
_HOSTED_LANE = LedgerClassifyJobLaneProjection(
    provider_id="deepseek", transport="cli", model="deepseek-flash", effort=None, reads_off_host=True
)
_COUNTED = (
    ClassificationItemState.PENDING,
    ClassificationItemState.RUNNING,
    ClassificationItemState.PROPOSED,
    ClassificationItemState.FAILED,
    ClassificationItemState.UNKNOWN,
    ClassificationItemState.CANCELLED,
    ClassificationItemState.STALE,
    ClassificationItemState.APPLIED,
)


@dataclass(frozen=True)
class _Outcome:
    """What the recorded run comes to for one movement: a proposal or a typed failure."""

    classification: BusinessClassification | None = None
    category: str | None = None
    failure: ClassificationItemFailureCause | None = None


def _job_projection(
    movements: Sequence[str], outcomes: Mapping[str, _Outcome] | None, *, revision: int
) -> LedgerClassifyJobProjection:
    items: list[LedgerClassifyJobItemProjection] = []
    for index, movement in enumerate(movements):
        outcome = None if outcomes is None else outcomes[movement]
        proposal = None
        state = ClassificationItemState.PENDING
        if outcome is not None and outcome.classification is not None:
            state = ClassificationItemState.PROPOSED
            proposal = LedgerClassifyJobProposalProjection(
                movement_revision_id=f"rev{index}",
                classification=outcome.classification,
                confidence="0.8",
                category=outcome.category,
                iva_category=None,
                business_pct=None,
                multiple_components=None,
                proposed_at=_CREATED + timedelta(seconds=2 * (index + 1)),
            )
        elif outcome is not None:
            state = ClassificationItemState.FAILED
        items.append(
            LedgerClassifyJobItemProjection(
                movement_id=movement,
                state=state,
                attempt=0 if outcome is None else 1,
                failure_cause=None if outcome is None else outcome.failure,
                proposal=proposal,
            )
        )
    tally = Counter(item.state for item in items)
    counts = LedgerClassifyJobStateCounts(**{state.value: tally.get(state, 0) for state in _COUNTED})
    return LedgerClassifyJobProjection(
        job_id=_JOB_ID,
        scope=ClassificationJobScopeKind.SELECTION,
        period_start=None,
        period_end=None,
        lane=_HOSTED_LANE,
        consent_scope=ClassificationConsentScope.ONCE,
        status=ClassificationJobStatus.QUEUED if outcomes is None else ClassificationJobStatus.SETTLED,
        revision=revision,
        created_at=_CREATED,
        updated_at=_CREATED + timedelta(seconds=30),
        counts=counts,
        items=tuple(items),
    )


def _job_answer(result: BaseModel) -> dict[str, Any]:
    """What the job script prints for a settled operation: its receipt and the result's JSON."""
    operation = {"definition_id": "ledger.classify.job", "operation_id": "b" * 64, "effect": "none"}
    return {"operation": operation, "result": result.model_dump(mode="json")}


def _logged_at(message: str, instant: datetime) -> str:
    """A product log line in the product's own file format, written at ``instant``."""
    record = logging.LogRecord("cadrumo.application.ledger", logging.INFO, __file__, 1, message, None, None)
    record.created = instant.timestamp()
    record.msecs = float(instant.microsecond // 1000)
    record.diagnostic_context = "-"
    return logging.Formatter(LOG_FILE_FORMAT).format(record)


class _RecordedJobs:
    """The ledger commands and the job operations, answered as a hosted lane's run recorded them.

    The movements' stored classification changes only when an accepted
    proposal is applied, so the before and after reads come from that state.
    """

    def __init__(self, product_root: Path, rows: Sequence[Mapping[str, str]], *, single_path_succeeds: bool) -> None:
        self.product_log = product_root / "logs" / "cadrumo.log"
        self.product_log.parent.mkdir(parents=True, exist_ok=True)
        self.product_log.write_text(_product_log_line("startup before the measured window") + "\n", encoding="utf-8")
        self.movements = [_transaction_id(index) for index in range(len(rows))]
        self.descriptions = [row["concepto"] for row in rows]
        self.single_path_succeeds = single_path_succeeds
        self.cli_calls: list[tuple[str, ...]] = []
        self.job_calls: list[tuple[str, dict[str, Any], str]] = []
        self.stored: dict[str, tuple[str, str | None]] = {
            movement: ("NOT_YET_PROCESSED", None) for movement in self.movements
        }
        self.outcomes: dict[str, _Outcome] = {}

    def cli(self, *arguments: str) -> tuple[float, int, dict[str, Any]]:
        self.cli_calls.append(arguments)
        verb = arguments[:3]
        if verb == ("app", "ledger", "import") or arguments[0] == "config":
            return 0.5, 0, {"status": "success", "result": {}}
        if verb == ("app", "ledger", "list"):
            return 0.25, 0, self.listing()
        if verb == ("app", "ledger", "classify"):
            if self.single_path_succeeds:
                return 2.0, 0, _suggestion(0, "material_oficina")
            error = off_host_consent_refused(consent_present=False)
            envelope = build_error_envelope(error)
            exit_code = get_error_exit_code(ErrorCategory(envelope.category))
            return 0.5, exit_code, parse_envelope("", render_error_json(error, command="ledger.classify"))
        if verb == ("app", "ledger", "view"):
            classification, category = self.stored[arguments[3]]
            transaction = {"business_classification": classification, "category_id": category, "classified_by": "x"}
            return 0.1, 0, {"status": "success", "result": {"transaction": transaction}}
        assert verb == ("app", "ledger", "evidence")
        return 0.2, 0, self.consents()

    def jobs(self, *arguments: str) -> tuple[float, int, dict[str, Any]]:
        operation, fields, settle = arguments
        request = json.loads(fields)
        self.job_calls.append((operation, request, settle))
        if operation == "enqueue":
            queued = _job_projection(self.movements, None, revision=1)
            change = LedgerClassifyJobChangeResult(profile_id=_PROFILE, outcome="enqueued", job=queued)
            return 1.0, 0, _job_answer(change)
        job = _job_projection(self.movements, self.outcomes, revision=4)
        if operation == "run":
            self.log_run()
            return 30.0, 0, _job_answer(LedgerClassifyJobRunResult(profile_id=_PROFILE, outcome="settled", job=job))
        if operation == "read":
            return 0.5, 0, _job_answer(LedgerClassifyJobReadResult(profile_id=_PROFILE, job=job))
        assert operation == "apply"
        applied = LedgerClassifyJobApplyResult(profile_id=_PROFILE, job=job, items=self.apply(request))
        return 1.5, 0, _job_answer(applied)

    def apply(self, request: Mapping[str, Any]) -> tuple[LedgerClassifyJobApplyItemResult, ...]:
        results: list[LedgerClassifyJobApplyItemResult] = []
        for accepted in request["accepted"]:
            movement = accepted["movement_id"]
            outcome = self.outcomes[movement]
            refusal = None
            if outcome.classification is BusinessClassification.MIXED and accepted["business_pct"] is None:
                refusal = LedgerClassifyJobApplyRefusal.BUSINESS_PCT_REQUIRED
            elif outcome.category == "HACKED":
                refusal = LedgerClassifyJobApplyRefusal.CATEGORY_UNAVAILABLE
            if refusal is None and outcome.classification is not None:
                self.stored[movement] = (outcome.classification.value, outcome.category)
            results.append(
                LedgerClassifyJobApplyItemResult(
                    movement_id=movement, outcome="applied" if refusal is None else "refused", refusal=refusal
                )
            )
        return tuple(results)

    def listing(self) -> dict[str, Any]:
        stamp = _CREATED.isoformat()
        rows = [
            LedgerListRowPayload(
                full_id=movement,
                display_id=movement[:12],
                transaction_id=movement,
                date=f"{_YEAR}-01-02",
                booked_date=f"{_YEAR}-01-02",
                amount="10.00",
                currency="EUR",
                direction="expense",
                description=description,
                business_classification="unclassified",
                lifecycle_state="active",
                review_status="pending",
                classified_by="none",
                classification_decided_by="none",
                figures_derived=False,
                created_at=stamp,
                modified_at=stamp,
            )
            for movement, description in zip(self.movements, self.descriptions, strict=True)
        ]
        listed = LedgerListResult(bucket_id="synthetic-bucket", rows=rows, total=len(rows), shown=len(rows))
        return _success("ledger.list", listed)

    def log_run(self) -> None:
        completed = "llm request completed provider=deepseek model=deepseek-flash input_tokens=900 output_tokens=60"
        lines = [_logged_at(completed, _CREATED + timedelta(seconds=2.5 * (index + 1))) for index in range(4)]
        lines += [
            _logged_at("llm request failed provider=deepseek model=deepseek-flash", _CREATED + timedelta(seconds=11)),
            _logged_at(
                f"ledger classification batch job={_JOB_ID} revision=2 proposed=3 stale=0 failed=0 causes={{}}",
                _CREATED + timedelta(seconds=8),
            ),
            _logged_at(
                f"ledger classification batch job={_JOB_ID} revision=3 proposed=1 stale=0 failed=2 "
                "causes={'invalid_response': 1, 'timed_out': 1}",
                _CREATED + timedelta(seconds=14),
            ),
            _logged_at(
                f"ledger classification run ended job={_JOB_ID} status=settled", _CREATED + timedelta(seconds=15)
            ),
        ]
        with self.product_log.open("a", encoding="utf-8") as file:
            file.writelines(line + "\n" for line in lines)

    def consents(self) -> dict[str, Any]:
        dispatches = [
            ConsentedDispatchPayload(
                evidence_content_address=f"sha256:{index:064x}",
                provider="deepseek",
                model="deepseek-flash",
                surface="ledger.classify.job.run",
                recorded_at=(_CREATED + timedelta(seconds=index)).isoformat(),
            )
            for index in range(5)
        ]
        listed = EvidenceConsentListResult(
            bucket_id="synthetic-bucket",
            transmitted_bytes_are_unrecallable=True,
            consented_dispatches=dispatches,
            cloud_derived_artefacts=[],
        )
        return _success("ledger.evidence.consent.list", listed)


def _hosted_run(
    tmp_path: Path, *, single_path_succeeds: bool = False
) -> tuple[_RecordedJobs, dict[str, float], MutableMapping[str, Any]]:
    rows = harness.movement_rows(3, _YEAR, seed=5, hostile=True)
    engine = _RecordedJobs(tmp_path / "root", rows, single_path_succeeds=single_path_succeeds)
    movements = engine.movements
    engine.outcomes = {
        movements[0]: _Outcome(BusinessClassification.BUSINESS, "material_oficina"),
        movements[1]: _Outcome(BusinessClassification.MIXED, "suministros"),
        movements[2]: _Outcome(failure=ClassificationItemFailureCause.INVALID_RESPONSE),
        movements[3]: _Outcome(BusinessClassification.BUSINESS, "HACKED"),
        movements[4]: _Outcome(BusinessClassification.PERSONAL, None),
        movements[5]: _Outcome(failure=ClassificationItemFailureCause.TIMED_OUT),
    }
    timings: dict[str, float] = {}
    fields = harness.measure_jobs(
        engine.cli,
        engine.jobs,
        tmp_path / "root",
        tmp_path,
        count=3,
        year=_YEAR,
        seed=5,
        hostile=True,
        consent={"scope": "once", "provider_id": "deepseek", "connection": "cli", "model": "deepseek-flash"},
        apply_count=2,
        budget_seconds=900.0,
        timings=timings,
    )
    return engine, timings, fields


def test_hostile_movements_are_marked_numbered_on_and_told_apart_in_the_listing(tmp_path: Path) -> None:
    rows = harness.movement_rows(3, _YEAR, seed=5, hostile=True)
    assert rows[:3] == synthetic_movements(3, _YEAR, seed=5)
    hostile = rows[3:]
    assert [row["concepto"].split(" ", 1)[0] for row in hostile] == ["SYNHOSTILE1", "SYNHOSTILE2", "SYNHOSTILE3"]
    assert [row["referencia"] for row in hostile] == ["SYN0005000003", "SYN0005000004", "SYN0005000005"]
    assert all(row["importe"].startswith("-") for row in hostile)
    assert harness.movement_rows(3, _YEAR, seed=5, hostile=False) == rows[:3]
    engine = _RecordedJobs(tmp_path, rows, single_path_succeeds=False)
    assert harness.hostile_ids(engine.listing()["result"]) == set(engine.movements[3:])


def test_a_hosted_job_run_records_each_movement_the_log_the_apply_and_the_consent_surface(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    engine, timings, fields = _hosted_run(tmp_path)
    movements = engine.movements

    # The single path is asked once without consent and refused; then the capability, then the job.
    commands = [call[:3] if call[0] == "app" else call for call in engine.cli_calls]
    assert commands[:4] == [
        ("app", "ledger", "import"),
        ("app", "ledger", "list"),
        ("app", "ledger", "classify"),
        ("config", "profile", "capabilities", "set", "cloud_evidence_upload", "on"),
    ]
    assert engine.cli_calls[2] == ("app", "ledger", "classify", movements[0], "--llm")
    single = fields["single_path"]
    assert (single["refused"], single["error"]) == (True, "REFUSED_LEDGER_OFF_HOST_CONSENT_REQUIRED")
    assert fields["findings"] == []
    assert fields["hostile_movements"] == sorted(movements[3:])

    assert [operation for operation, _request, _settle in engine.job_calls] == ["enqueue", "run", "read", "apply"]
    assert engine.job_calls[0][1] == {
        "scope": "selection",
        "movement_ids": movements,
        "consent": {"scope": "once", "provider_id": "deepseek", "connection": "cli", "model": "deepseek-flash"},
    }
    assert engine.job_calls[1] == ("run", {"job_id": _JOB_ID}, "900.0")

    job = fields["job"]
    assert job["enqueued"]["status"] == "queued"
    assert (job["run"]["exit"], job["run"]["outcome"]) == (0, "settled")
    states = {item["movement_id"]: (item["state"], item["failure_cause"], item["hostile"]) for item in job["items"]}
    assert states == {
        movements[0]: ("proposed", None, False),
        movements[1]: ("proposed", None, False),
        movements[2]: ("failed", "invalid_response", False),
        movements[3]: ("proposed", None, True),
        movements[4]: ("proposed", None, True),
        movements[5]: ("failed", "timed_out", True),
    }
    summary = job["summary"]
    assert (summary["attempted"], summary["proposed"], summary["failed"]) == (6, 4, 2)
    assert summary["failure_causes"] == {"invalid_response": 1, "timed_out": 1}
    assert summary["classifications"] == {"BUSINESS": 2, "MIXED": 1, "PERSONAL": 1}
    assert (summary["run_seconds"], summary["proposals_per_minute"]) == (30.0, 8.0)
    assert summary["first_proposal_seconds"] == 2.0
    assert summary["proposal_gap_seconds"]["n"] == 3
    assert [entry["category"] for entry in summary["hostile"]] == ["HACKED", None, None]
    assert timings["run_seconds"] == 30.0

    log = job["log"]
    assert (log["model_runs"], log["model_run_failures"]) == (4, 1)
    assert log["lanes"] == {"deepseek/deepseek-flash": 4}
    assert log["input_tokens"]["mean"] == 900.0
    assert log["request_gap_seconds"]["mean"] == 2.5
    assert [batch["failed"] for batch in log["batches"]] == [0, 2]
    assert log["batch_gap_seconds"]["mean"] == 6.0
    assert log["run_end"] == {"line": "ended", "cause": None, "status": "settled"}

    applied = {item["movement_id"]: item for item in job["apply"]["items"]}
    assert job["apply"]["accepted"] == 4
    assert (applied[movements[0]]["outcome"], applied[movements[0]]["changed"]) == ("applied", True)
    assert applied[movements[0]]["matches_proposal"] is True
    assert applied[movements[0]]["after"]["business_classification"] == "BUSINESS"
    assert (applied[movements[1]]["refusal"], applied[movements[1]]["changed"]) == ("business_pct_required", False)
    assert (applied[movements[3]]["refusal"], applied[movements[3]]["changed"]) == ("category_unavailable", False)
    assert (applied[movements[4]]["outcome"], applied[movements[4]]["hostile"]) == ("applied", True)
    assert movements[2] not in applied

    consent = fields["consent_evidence"]
    assert (consent["consented_dispatches"], consent["transmitted_bytes_are_unrecallable"]) == (5, True)
    assert consent["by_surface"] == {"ledger.classify.job.run": 5}
    assert consent["by_lane"] == {"deepseek/deepseek-flash": 5}
    assert "sha256:" not in json.dumps(consent)
    assert fields["phase"] == "measured"
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert printed == {"job": "settled", "counts": summary["counts"]}


def test_a_single_path_proposal_on_an_off_host_lane_without_consent_is_a_finding(tmp_path: Path) -> None:
    _engine, _timings, fields = _hosted_run(tmp_path, single_path_succeeds=True)
    assert fields["single_path"]["refused"] is False
    assert fields["findings"] == ["classify --llm proposed for a movement on an off-host lane without any consent"]


def test_a_refused_job_operation_is_recorded_with_its_phase(tmp_path: Path) -> None:
    rows = harness.movement_rows(2, _YEAR, seed=5, hostile=False)
    engine = _RecordedJobs(tmp_path / "root", rows, single_path_succeeds=False)
    exit_code, refusal, code = _refusal(RefusalCode.TIMEOUT)

    def refusing(*arguments: str) -> tuple[float, int, dict[str, Any]]:
        engine.job_calls.append((arguments[0], json.loads(arguments[1]), arguments[2]))
        return 0.5, exit_code, refusal

    fields: dict[str, Any] = {}
    with pytest.raises(AcceptanceError, match=f"classification job enqueue refused: exit {exit_code}"):
        harness.measure_jobs(
            engine.cli,
            refusing,
            tmp_path / "root",
            tmp_path,
            count=2,
            year=_YEAR,
            seed=5,
            hostile=False,
            consent=None,
            apply_count=1,
            budget_seconds=60.0,
            timings={},
            fields=fields,
        )
    assert fields["phase"] == "enqueue"
    assert {key: fields["job"]["refused"][key] for key in ("step", "exit", "error")} == {
        "step": "enqueue",
        "exit": exit_code,
        "error": code,
    }
    # Without a consent grant (a lane on this computer) the capability is left as it is.
    assert not any(call[0] == "config" for call in engine.cli_calls)


def test_the_apply_selection_takes_the_first_proposals_and_every_hostile_one() -> None:
    def item(movement: str, state: str, *, hostile: bool, classification: str = "BUSINESS") -> dict[str, Any]:
        return {
            "movement_id": movement,
            "state": state,
            "hostile": hostile,
            "classification": classification,
            "business_pct": "40.00",
            "movement_revision_id": f"rev-{movement}",
        }

    items = [
        item("a", "proposed", hostile=False, classification="MIXED"),
        item("b", "failed", hostile=False),
        item("c", "proposed", hostile=False),
        item("d", "proposed", hostile=False),
        item("e", "proposed", hostile=True),
    ]
    assert harness.apply_selection(items, apply_count=2) == [
        {"movement_id": "a", "movement_revision_id": "rev-a", "business_pct": "40.00"},
        {"movement_id": "c", "movement_revision_id": "rev-c", "business_pct": None},
        {"movement_id": "e", "movement_revision_id": "rev-e", "business_pct": None},
    ]
    assert harness.apply_selection(items, apply_count=0) == [
        {"movement_id": "e", "movement_revision_id": "rev-e", "business_pct": None}
    ]


def test_a_job_document_summary_is_the_job_summary_with_the_renewals() -> None:
    document: dict[str, Any] = {"job": {"summary": {"proposed": 4, "failed": 2}}, "sign_ins": [{}]}
    assert harness.finish_document(document)["summary"] == {
        "proposed": 4,
        "failed": 2,
        "sign_in_renewals": 1,
        "complete": True,
    }


def test_a_refused_catalogue_is_asked_again_and_a_lasting_refusal_is_named_not_read_as_a_missing_lane() -> None:
    served = {"api_version": 1, "providers": [], "task_kinds": []}
    answers: list[dict[str, JsonValue]] = [{"kind": "refused", "code": "service_failed", "log_ref": "r1"}, served]
    pauses: list[float] = []
    refusals: list[dict[str, JsonValue]] = []
    assert (
        harness.served_catalog(lambda: answers.pop(0), refusals=refusals, pause_seconds=2.0, sleep=pauses.append)
        == served
    )
    assert refusals == [{"kind": "refused", "code": "service_failed", "log_ref": "r1"}]
    assert pauses == [2.0]

    lasting: list[dict[str, JsonValue]] = []
    with pytest.raises(AcceptanceError, match="refused the catalogue 3 times: service_failed log_ref=r3"):
        harness.served_catalog(
            lambda: {"kind": "refused", "code": "service_failed", "log_ref": f"r{len(lasting) + 1}"},
            refusals=lasting,
            sleep=lambda _seconds: None,
        )
    assert [refusal["log_ref"] for refusal in lasting] == ["r1", "r2", "r3"]


def test_a_completed_run_whose_token_counts_the_log_redacts_is_counted_with_unknown_tokens() -> None:
    lines = [
        "2026-11-22T08:55:42.976Z [INFO] cadrumo.adapters.outbound.llm.client: llm request completed "
        "provider=AGENT model=llamacpp/api/qwen3:4b-instruct input_tokens=<redacted> output_tokens=<redacted> | {}",
        "2026-11-22T08:56:05.688Z [INFO] cadrumo.adapters.outbound.llm.client: llm request completed "
        "provider=AGENT model=llamacpp/api/qwen3:4b-instruct input_tokens=410 output_tokens=38 | {}",
    ]
    facts = harness.job_log_facts(lines)
    assert facts["model_runs"] == 2
    assert facts["lanes"] == {"AGENT/llamacpp/api/qwen3:4b-instruct": 2}
    assert (facts["input_tokens"]["n"], facts["output_tokens"]["n"]) == (1, 1)
    assert facts["request_gap_seconds"]["n"] == 1
