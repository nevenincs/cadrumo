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
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, override
from uuid import uuid4

import pytest
from pydantic import BaseModel, JsonValue, TypeAdapter

from cadrumo.core.errors.error_codes import (
    ErrorCategory,
    build_error_envelope,
    get_error_exit_code,
    render_error_json,
)
from cadrumo.core.json_contract import emit_json_success
from cadrumo.core.logging import LOG_FILE_FORMAT
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo.entrypoints.cli.ledger_llm_payloads import LedgerClassifyLlmSuggestResult
from cadrumo.entrypoints.cli.ledger_results import LedgerListResult, LedgerListRowPayload
from cadrumo_agent_service.admin import AdminAction, AdminServer
from cadrumo_agent_service.providers.application.contracts import LocalEngineStatus, LocalModelListStatus
from cadrumo_agent_service.providers.application.local_model_list import LocalModelListService
from cadrumo_agent_service.providers.application.served_catalog import catalog_nonconformance
from cadrumo_agent_service.providers.application.tests.memory_store import MemoryLocalModelListStore
from cadrumo_agent_service.providers.application.tests.synthetic_catalog import (
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
from dev.runtime_lifecycle.service_admin_channel import owned_service_settings, service_admin

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
    assert ServerFacts.read([]).as_json() == {
        "chat_requests": 0,
        "prompt_tokens": [],
        "prompt_eval_tokens": [],
        "prompt_eval_ms": [],
        "generated_tokens": [],
        "generation_ms": [],
    }


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
        "chat_requests": 2,
        "prompt_tokens": [420, 470],
        "prompt_eval_tokens": [14, 50],
        "prompt_eval_ms": [30.10, 95.50],
        "generated_tokens": [40, 38],
        "generation_ms": [1300.00, 1250.50],
    }
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


def test_outputs_stay_below_the_worktree_tmp() -> None:
    stamp = f"test-{uuid4().hex}"
    outputs = output_directory(stamp)
    try:
        assert outputs == TEMP_ROOT / "ledger-classification-speed" / stamp
        assert outputs.is_dir() and outputs.resolve().is_relative_to(REPO_ROOT.resolve() / ".tmp")
    finally:
        outputs.rmdir()


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
    monkeypatch.setattr(harness, "output_directory", lambda stamp: outputs)
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
