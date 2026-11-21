"""The ledger classification measurement, driven by a recorded engine instead of a live model.

The router log lines below follow the llama.cpp server's slot and timing
lines the parser targets; the command envelopes are produced by the product's
own result models and envelope writers, then read back through the harness's
envelope parser, so nothing here starts llama-server, the runtime or a model.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import socket
import threading
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, override

import pytest

from cadrumo.core.errors.error_codes import (
    ErrorCategory,
    build_error_envelope,
    get_error_exit_code,
    render_error_json,
)
from cadrumo.core.json_contract import emit_json_success
from cadrumo.core.logging import LOG_FILE_FORMAT
from cadrumo.entrypoints.cli.ledger_llm_payloads import LedgerClassifyLlmSuggestResult
from cadrumo.entrypoints.cli.ledger_results import LedgerListResult, LedgerListRowPayload
from cadrumo_agent_service.providers.application.served_catalog import catalog_nonconformance
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from dev.paths import REPO_ROOT
from dev.runtime_lifecycle.caller_owned_root import AcceptanceError, parse_envelope

from .. import ledger_classification_speed as harness
from ..ledger_classification_speed import (
    PREREQUISITE_ABSENT,
    PrerequisiteAbsentError,
    Presented,
    ServerFacts,
    ServerLog,
    classify_flags,
    distribution,
    lane_model,
    measure_ledger,
    model_weights,
    parse_arguments,
    prerequisite_absence,
    preset_text,
    router_id,
    run_record_count,
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
    arguments = {"count": 4, "year": _YEAR, "seed": 1, "mode": "classification", "budget_seconds": 600.0}
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


def test_argument_defaults_keep_scratch_under_the_worktree_tmp() -> None:
    arguments = parse_arguments(["--out", "result.json"])
    scratch = Path(arguments.scratch)
    assert scratch.parent == REPO_ROOT / ".tmp" / "ledger-classification-speed"
    assert datetime.strptime(scratch.name, "%Y%m%dT%H%M%S")
    assert Path(arguments.package) == REPO_ROOT / "build" / "windows-x64" / "stage" / "Release" / "app"
    assert Path(arguments.model_store) == Path.home() / ".ollama" / "models"
    assert (arguments.count, arguments.mode, arguments.seed, arguments.budget_seconds) == (
        1,
        "classification",
        1,
        1200.0,
    )
    assert (arguments.model, arguments.context, arguments.cpu_only, arguments.inspect) == (None, None, False, False)
    assert arguments.admin_steps("llamacpp_api", "synthetic-text:4b") == [
        ("local_engine_choose", {"engine": "llamacpp"}),
        ("reading_model_choose", {"provider": "llamacpp_api", "model": "synthetic-text:4b"}),
    ]
    assert parse_arguments(["--out", "x", "--no-select"]).admin_steps("llamacpp_api", "m") == []


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

    def measure_up_to_the_model(arguments: Any) -> dict[str, Any]:
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
