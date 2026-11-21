"""Measure how fast the ledger classifies movements with a local model, through the built package.

One run stands up a disposable product root from a built native package, the
way the runtime lifecycle harness does: the packaged runtime, a synthetic
profile signed in and held, and the packaged agent service admitted for it,
which starts the bundled cadrumo-agent. The package's llama-server is started
here in router mode on its fixed loopback address with a preset written from
the model store, as the runtime manager writes it, because no manager runs on
a disposable root. The model is the text model the served catalogue's llama.cpp
lane recommends, at the context its catalogue records for it, unless ``--model``
names another one the store holds.

The run imports ``--count`` synthetic movements through ``aeat app ledger
import`` and asks for one classification suggestion per movement with ``aeat
app ledger classify ID --llm``, one after the other, as a person or the window
asks today. Each ask is the registered ``ledger.llm.review`` operation in the
profile worker, whose text reader reaches the agent service through the
runtime's model-run relay. Nothing is applied.

Per movement it records the wall time of the command, the outcome, and what
the llama-server router logged for the requests the movement caused: how many
chat requests (a second one is the reader's JSON re-ask), prompt tokens,
prompt tokens evaluated after the server's prefix cache, generated tokens and
the server's prompt and generation times. The product log's run records give
the number of model runs the reader completed. A fixed command without a model
call measures the command line's own cost on the same root.

Exit 0 means every phase ran and the JSON was written; per-movement refusals
are counted in it, not raised. Exit 1 names a setup failure. Exit 3 means a
prerequisite is absent: the package, its llama-server, the model store or the
model in it.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import random
import re
import statistics
import sys
import time
from collections.abc import Generator, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Final, Protocol
from urllib.error import URLError
from urllib.request import urlopen

import psutil

from cadrumo.core.config_runtime_fields import LLAMA_SERVER_ADDRESS
from cadrumo_agent_service.admin import AdminAction
from cadrumo_client.transport.windows_process import WindowsProcessScope, unreturned_windows_process_scope
from dev.paths import REPO_ROOT
from dev.runtime_lifecycle.agent_service_session import AgentServiceSession, agent_service_session
from dev.runtime_lifecycle.caller_owned_root import AcceptanceError
from dev.runtime_lifecycle.proof_support import supported_filing_year

PREREQUISITE_ABSENT: Final = 3
_LLAMA_FOLDER: Final = Path("bin") / "llama"
LLAMA_EXECUTABLE: Final = "llama-server.exe" if sys.platform == "win32" else "llama-server"
_MODEL_MEDIA_TYPE: Final = "application/vnd.ollama.image.model"
_DEFAULT_REGISTRY: Final = "registry.ollama.ai"
_DEFAULT_NAMESPACE: Final = "library"
_ENGINE_PROVIDER: Final = "llamacpp"
_HEALTH_SECONDS: Final = 120.0
MAX_CONTEXT: Final = 16384
"""The largest context this measurement loads a model with."""

_PROMPT_EVAL: Final = re.compile(r"prompt eval time =\s*([\d.]+) ms /\s*(\d+) tokens")
_EVAL: Final = re.compile(r"(?<!prompt )eval time =\s*([\d.]+) ms /\s*(\d+) (?:tokens|runs)")
_PROMPT_TOKENS: Final = re.compile(r"(?:task\.n_tokens|n_prompt_tokens|prompt_tokens)\s*=\s*(\d+)")
_CHAT_REQUEST: Final = re.compile(r"(?:POST|done request:\s*POST) /v1/chat/completions|/chat/completions .* 200")
_RUN_RECORD: Final = re.compile(r"llm request completed provider=(\S+) model=(\S+)")

# Synthetic counterparties and descriptions: invented business names and ordinary
# Spanish statement wording, no person or account of anyone.
_EXPENSES: Final = (
    ("Restaurante La Plaza Ficticia", "Comida con cliente proyecto {n}"),
    ("Gasolinera Ejemplo Norte", "Repostaje vehiculo {n}"),
    ("Papeleria Demo SL", "Material de oficina pedido {n}"),
    ("Software Nube Prueba SL", "Suscripcion mensual licencia {n}"),
    ("Telefonia Sintetica SA", "Factura movil linea {n}"),
    ("Inmobiliaria Modelo SL", "Alquiler despacho mes {n}"),
    ("Supermercado Ficticio", "Compra domestica ticket {n}"),
    ("Libreria Tecnica Demo", "Libro formacion profesional {n}"),
    ("Hotel Ejemplo Centro", "Alojamiento viaje trabajo {n}"),
    ("Transportes Prueba SA", "Billete tren desplazamiento {n}"),
    ("Asesoria Sintetica SL", "Honorarios gestion trimestre {n}"),
    ("Electricidad Demo SA", "Recibo luz periodo {n}"),
)
_INCOME: Final = (
    ("Cliente Ficticio SL", "Cobro factura {n}"),
    ("Empresa Ejemplo SA", "Transferencia pago servicios {n}"),
    ("Consultora Demo SL", "Pago proyecto consultoria {n}"),
)


class PrerequisiteAbsentError(Exception):
    """A prerequisite of the measurement is not on this machine: the run cannot start, it did not fail."""


class TimedCli(Protocol):
    """One JSON ``aeat`` command on the measured root: its wall seconds, exit code and envelope."""

    def __call__(self, *arguments: str) -> tuple[float, int, dict[str, Any]]:
        """Run ``aeat --format json ARGUMENTS`` and time it."""
        ...


@dataclass(slots=True)
class ServerLog:
    """The llama-server router's standard error, drained to a file and kept for reading."""

    path: Path
    lines: list[str] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)

    def append(self, line: str) -> None:
        """Keep one line in order."""
        with self.lock:
            self.lines.append(line)

    def since(self, offset: int) -> tuple[list[str], int]:
        """Return the lines after ``offset`` and the new offset."""
        with self.lock:
            return self.lines[offset:], len(self.lines)


@dataclass(frozen=True, slots=True)
class ServerFacts:
    """What the router logged for one movement's requests."""

    chat_requests: int
    prompt_tokens: tuple[int, ...]
    prompt_eval_tokens: tuple[int, ...]
    prompt_eval_ms: tuple[float, ...]
    generated_tokens: tuple[int, ...]
    generation_ms: tuple[float, ...]

    @classmethod
    def read(cls, lines: Sequence[str]) -> ServerFacts:
        """Collect the timing lines of ``lines``."""
        prompt_eval = [_PROMPT_EVAL.search(line) for line in lines]
        generation = [_EVAL.search(line) for line in lines]
        totals = [_PROMPT_TOKENS.search(line) for line in lines]
        return cls(
            chat_requests=sum(1 for line in lines if _CHAT_REQUEST.search(line)),
            prompt_tokens=tuple(int(match.group(1)) for match in totals if match),
            prompt_eval_tokens=tuple(int(match.group(2)) for match in prompt_eval if match),
            prompt_eval_ms=tuple(float(match.group(1)) for match in prompt_eval if match),
            generated_tokens=tuple(int(match.group(2)) for match in generation if match),
            generation_ms=tuple(float(match.group(1)) for match in generation if match),
        )

    def as_json(self) -> dict[str, Any]:
        """Return the facts as plain JSON values."""
        return {
            "chat_requests": self.chat_requests,
            "prompt_tokens": list(self.prompt_tokens),
            "prompt_eval_tokens": list(self.prompt_eval_tokens),
            "prompt_eval_ms": list(self.prompt_eval_ms),
            "generated_tokens": list(self.generated_tokens),
            "generation_ms": list(self.generation_ms),
        }


@dataclass(frozen=True, slots=True)
class Presented:
    """The one model the router presents: its name, weights file and context."""

    name: str
    weights: Path
    context: int


def run_record_count(lines: Sequence[str]) -> int:
    """Count the product log's completed model-run records among ``lines``."""
    return sum(1 for line in lines if _RUN_RECORD.search(line))


def router_id(name: str) -> str:
    """The preset section name the runtime manager gives a model: a digest, since a colon is rewritten."""
    return "m-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]


def model_weights(store: Path, name: str) -> Path:
    """Return the stored model layer of ``name`` (``model:tag`` in the default namespace)."""
    model, _, tag = name.partition(":")
    manifest = store / "manifests" / _DEFAULT_REGISTRY / _DEFAULT_NAMESPACE / model / (tag or "latest")
    if not manifest.is_file():
        raise PrerequisiteAbsentError(f"the model store holds no manifest for {name}")
    document = json.loads(manifest.read_text(encoding="utf-8"))
    layers = [layer for layer in document["layers"] if layer.get("mediaType") == _MODEL_MEDIA_TYPE]
    if len(layers) != 1:
        raise AcceptanceError(f"manifest of {name} names {len(layers)} model layers")
    weights = store / "blobs" / str(layers[0]["digest"]).replace(":", "-")
    if not weights.is_file():
        raise PrerequisiteAbsentError(f"the model store holds no model layer for {name}")
    if weights.stat().st_size != int(layers[0]["size"]):
        raise AcceptanceError(f"model layer of {name} is not stored at its size")
    return weights


def preset_text(presented: Presented, *, cpu_only: bool) -> str:
    """The router preset the manager writes for one presented model."""
    lines = [
        f"[{router_id(presented.name)}]",
        f"alias = {presented.name}",
        f"model = {presented.weights}",
        f"ctx-size = {presented.context}",
    ]
    if cpu_only:
        lines.append("n-gpu-layers = 0")
    return "\n".join(lines) + "\n\n"


@contextmanager
def llama_router(package: Path, scratch: Path, presented: Presented, *, cpu_only: bool) -> Generator[ServerLog]:
    """Run the package's llama-server as the manager runs it, contained in a kill-on-close job."""
    executable = (package / _LLAMA_FOLDER / LLAMA_EXECUTABLE).resolve(strict=True)
    home = scratch / "llama-server"
    for folder in (home / "AppData" / "Roaming", home / "AppData" / "Local", home / "tmp", home / "cache"):
        folder.mkdir(parents=True, exist_ok=True)
    preset = home / "models.ini"
    preset.write_text(preset_text(presented, cpu_only=cpu_only), encoding="utf-8", newline="\n")
    host, _, port = LLAMA_SERVER_ADDRESS.rpartition(":")
    environment = {
        "SystemRoot": os.environ.get("SYSTEMROOT", r"C:\Windows"),
        "PATH": os.pathsep.join((str(executable.parent), os.environ.get("SYSTEMROOT", r"C:\Windows") + r"\System32")),
        "USERPROFILE": str(home),
        "APPDATA": str(home / "AppData" / "Roaming"),
        "LOCALAPPDATA": str(home / "AppData" / "Local"),
        "TEMP": str(home / "tmp"),
        "TMP": str(home / "tmp"),
        "LLAMA_CACHE": str(home / "cache"),
    }
    arguments = (
        *("--host", host, "--port", port, "--models-preset", str(preset)),
        *("--models-max", "1", "--no-models-autoload"),
    )
    log = ServerLog(scratch / "llama-server.log")
    try:
        scope = WindowsProcessScope()
    except BaseException as error:
        retained = unreturned_windows_process_scope(error)
        if retained is not None:
            retained.terminate(timeout=10.0)
        raise
    try:
        _, standard_error = scope.launch_with_standard_error(
            executable=executable, arguments=arguments, directory=home, environment=environment
        )

        def drain() -> None:
            with log.path.open("w", encoding="utf-8", newline="\n") as file:
                for raw in iter(standard_error.readline, b""):
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    log.append(line)
                    file.write(line + "\n")
                    file.flush()

        Thread(target=drain, name="llama-server-log", daemon=True).start()
        wait_healthy(LLAMA_SERVER_ADDRESS, _HEALTH_SECONDS)
        yield log
    finally:
        scope.terminate(timeout=10.0)


def healthy(address: str) -> bool:
    """Whether the llama-server at ``host:port`` answers ``/health`` with 200."""
    try:
        with urlopen(f"http://{address}/health", timeout=2.0) as response:
            status = response.status
            return isinstance(status, int) and status == 200
    except (URLError, OSError):
        return False


def wait_healthy(address: str, seconds: float) -> None:
    """Poll ``/health`` until it answers, or fail when ``seconds`` pass without an answer."""
    deadline = time.monotonic() + seconds
    while not healthy(address):
        if time.monotonic() > deadline:
            raise AcceptanceError("llama-server did not answer /health within its bound")
        time.sleep(0.2)


def synthetic_movements(count: int, year: int, *, seed: int) -> list[dict[str, str]]:
    """Return ``count`` invented statement rows in ``year``, deterministic for ``seed``."""
    chooser = random.Random(seed)  # noqa: S311 -- synthetic data, not security
    start = date(year, 1, 2)
    rows: list[dict[str, str]] = []
    for index in range(count):
        income = chooser.random() < 0.2
        counterparty, description = chooser.choice(_INCOME if income else _EXPENSES)
        amount = round(chooser.uniform(8, 2400), 2)
        booked = start + timedelta(days=chooser.randrange(0, 360))
        rows.append(
            {
                "fecha": booked.strftime("%d/%m/%Y"),
                "concepto": description.format(n=index + 1),
                "importe": f"{amount if income else -amount:.2f}".replace(".", ","),
                "moneda": "EUR",
                "beneficiario": counterparty,
                "referencia": f"SYN{seed:04d}{index:06d}",
            }
        )
    return rows


def write_statement(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    """Write the rows as a semicolon-separated statement CSV."""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def transaction_ids(result: object) -> list[str]:
    """Return every ``transaction_id`` in a ledger listing, once each, in listed order."""
    found: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, dict):
            identifier = value.get("transaction_id")
            if isinstance(identifier, str):
                found.append(identifier)
                return
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(result)
    return list(dict.fromkeys(found))


def lane_model(catalog: Mapping[str, Any], wanted: str | None) -> tuple[str, str, int | None]:
    """Return the llama.cpp lane id, the model to present and its catalogue context, from the served catalogue.

    The served catalogue lists lanes under ``providers``, each named by
    ``provider_id`` and ``transport``; a lane's ``catalog`` holds its
    ``recommended`` entry ids and its model entries.
    """
    lanes = catalog.get("providers")
    for lane in lanes if isinstance(lanes, list) else ():
        if not isinstance(lane, dict) or lane.get("provider_id") != _ENGINE_PROVIDER:
            continue
        served = lane.get("catalog")
        served = served if isinstance(served, dict) else {}
        listed = served.get("models")
        entries = [entry for entry in listed if isinstance(entry, dict)] if isinstance(listed, list) else []
        recommended = served.get("recommended")
        chosen = wanted or (recommended.get("text") if isinstance(recommended, dict) else None)
        if not isinstance(chosen, str):
            continue
        entry = next((entry for entry in entries if chosen in (entry.get("entry_id"), entry.get("model"))), {})
        name = entry.get("model")
        context = entry.get("llamacpp_default_context")
        return (
            f"{_ENGINE_PROVIDER}_{lane.get('transport')}",
            name if isinstance(name, str) else chosen,
            context if isinstance(context, int) else None,
        )
    raise AcceptanceError("the agent catalogue serves no llama.cpp lane with a recommended text model")


def product_log_lines(root: Path, offset: int) -> tuple[list[str], int]:
    """Return the product log's lines written after byte ``offset`` and the new offset."""
    path = root / "logs" / "cadrumo.log"
    if not path.is_file():
        return [], offset
    with path.open("rb") as file:
        file.seek(offset)
        data = file.read()
    return data.decode("utf-8", errors="replace").splitlines(), offset + len(data)


def distribution(values: Sequence[float]) -> dict[str, float | int | None]:
    """Count, mean, median, nearest-rank 95th percentile and range of ``values``."""
    if not values:
        return {"n": 0, "mean": None, "p50": None, "p95": None, "min": None, "max": None}
    ordered = sorted(values)
    p95_index = max(0, min(len(ordered) - 1, round(0.95 * len(ordered)) - 1))
    return {
        "n": len(ordered),
        "mean": round(statistics.fmean(ordered), 4),
        "p50": round(statistics.median(ordered), 4),
        "p95": round(ordered[p95_index], 4),
        "min": round(ordered[0], 4),
        "max": round(ordered[-1], 4),
    }


def _machine() -> dict[str, Any]:
    memory = psutil.virtual_memory().total
    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpus": psutil.cpu_count(logical=True),
        "physical_cpus": psutil.cpu_count(logical=False),
        "memory_gib": round(memory / 2**30, 1),
        "python": platform.python_version(),
    }


def session_cli(session: AgentServiceSession) -> TimedCli:
    """Time JSON ``aeat`` commands under the session's sign-in, identifiers revealed."""

    def timed(*arguments: str) -> tuple[float, int, dict[str, Any]]:
        started = time.perf_counter()
        code, envelope = session.cli_read(*arguments, reveal_identifiers=True)
        return time.perf_counter() - started, code, envelope

    return timed


def error_code(envelope: Mapping[str, Any]) -> str | None:
    """The registered error code of a refusal envelope, ``None`` for a success."""
    error = envelope.get("error")
    if isinstance(error, dict):
        code = error.get("code")
        return str(code) if code is not None else None
    return None


def result_fields(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """The suggestion fields a classification envelope's result carries."""
    result = envelope.get("result")
    if not isinstance(result, dict):
        return {}
    return {key: result.get(key) for key in ("classification", "category", "iva_category", "confidence", "provider")}


def classify_flags(mode: str) -> tuple[str, ...]:
    """The ``classify`` flags of a measurement mode."""
    return ("--llm", "--saturate") if mode == "saturated" else ("--llm",)


def movement_record(
    index: int,
    seconds: float,
    code: int,
    envelope: Mapping[str, Any],
    server_lines: Sequence[str],
    product_lines: Sequence[str],
    elapsed: float,
) -> dict[str, Any]:
    """One movement's measured facts: the command's outcome and what the router and product logged for it."""
    return {
        "index": index,
        "seconds": round(seconds, 4),
        "exit": code,
        "error": error_code(envelope),
        **result_fields(envelope),
        "server": ServerFacts.read(server_lines).as_json(),
        "run_records": run_record_count(product_lines),
        "elapsed": round(elapsed, 3),
    }


def measure_ledger(
    cli: TimedCli,
    log: ServerLog,
    product_root: Path,
    scratch: Path,
    *,
    count: int,
    year: int,
    seed: int,
    mode: str,
    budget_seconds: float,
    timings: dict[str, float],
) -> dict[str, Any]:
    """Import the synthetic movements, then classify each one, reading the router's and product's logs per movement.

    Returns the document's ledger fields; phase timings are added to ``timings``.
    """
    fields: dict[str, Any] = {}
    rows = synthetic_movements(count, year, seed=seed)
    statement = scratch / "synthetic-statement.csv"
    write_statement(statement, rows)
    seconds, code, envelope = cli("app", "ledger", "import", "--file", str(statement), "--provider", "csv")
    timings["import_seconds"] = seconds
    if code != 0:
        raise AcceptanceError(f"ledger import refused: exit {code}, code {error_code(envelope)}")
    seconds, code, envelope = cli("app", "ledger", "list")
    timings["list_seconds"] = seconds
    identifiers = transaction_ids(envelope.get("result"))
    if len(identifiers) < count:
        raise AcceptanceError(f"ledger lists {len(identifiers)} movements, expected {count}")
    identifiers = identifiers[:count]

    baseline = []
    for identifier in identifiers[: min(5, len(identifiers))]:
        seconds, _, _ = cli("app", "ledger", "history", identifier)
        baseline.append(seconds)
    fields["cli_baseline_history_seconds"] = distribution(baseline)

    classify = ("app", "ledger", "classify")
    flags = classify_flags(mode)
    items: list[dict[str, Any]] = []
    server_offset = log.since(0)[1]
    product_offset = product_log_lines(product_root, 0)[1]
    run_started = time.perf_counter()
    deadline = run_started + budget_seconds
    for index, identifier in enumerate(identifiers):
        if time.perf_counter() > deadline:
            fields["stopped_at_budget"] = index
            break
        seconds, code, envelope = cli(*classify, identifier, *flags)
        time.sleep(0.05)
        server_lines, server_offset = log.since(server_offset)
        product_lines, product_offset = product_log_lines(product_root, product_offset)
        item = movement_record(
            index, seconds, code, envelope, server_lines, product_lines, time.perf_counter() - run_started
        )
        items.append(item)
        print(json.dumps({"item": index, "seconds": item["seconds"], "exit": code, "error": item["error"]}), flush=True)
    timings["classify_wall_seconds"] = time.perf_counter() - run_started

    repeat = []
    for identifier in identifiers[: min(3, len(identifiers))]:
        seconds, code, _ = cli(*classify, identifier, *flags)
        server_lines, server_offset = log.since(server_offset)
        repeat.append({"seconds": round(seconds, 4), "exit": code, "server": ServerFacts.read(server_lines).as_json()})
    fields["repeat_same_movement"] = repeat
    fields["items"] = items
    return fields


def measure(arguments: _Arguments) -> dict[str, Any]:
    """Run the whole measurement and return its JSON document."""
    package = Path(arguments.package).resolve(strict=True)
    scratch = Path(arguments.scratch).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    store = Path(arguments.model_store).expanduser().resolve(strict=True)
    year = supported_filing_year()
    document: dict[str, Any] = {
        "started_at": datetime.now(UTC).isoformat(),
        "package": str(package),
        "machine": _machine(),
        "count": arguments.count,
        "mode": arguments.mode,
        "placement": "cpu_only" if arguments.cpu_only else "auto",
        "booking_year": year,
    }
    timings: dict[str, float] = {}
    phase = time.perf_counter()
    with ExitStack() as stack:
        session = stack.enter_context(agent_service_session(package, scratch / "session"))
        timings["session_setup_seconds"] = time.perf_counter() - phase
        document["session_timings"] = session.timings
        document["agent_event"] = {
            key: session.agent_event.get(key) for key in ("event", "code", "agent_version", "hosting_contract")
        }
        if session.first_refusal_code is not None:
            raise AcceptanceError(f"agent service refused the agent: {session.first_refusal_code}")
        catalog = session.catalog()
        (scratch / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
        lane, model, context = lane_model(catalog, arguments.model)
        context = min(arguments.context or context or MAX_CONTEXT, MAX_CONTEXT)
        presented = Presented(name=model, weights=model_weights(store, model), context=context)
        document["lane"] = {"provider": lane, "model": model, "context": context}
        if arguments.inspect:
            for action in ("status", "local_models", "local_engine", "provider_lanes"):
                (scratch / f"{action}.json").write_text(json.dumps(session.admin(action), indent=2), encoding="utf-8")
            return document

        phase = time.perf_counter()
        log = stack.enter_context(llama_router(package, scratch, presented, cpu_only=arguments.cpu_only))
        timings["llama_server_health_seconds"] = time.perf_counter() - phase
        for action, fields in arguments.admin_steps(lane, model):
            reply = session.admin(action, **fields)
            (scratch / f"admin-{action}.json").write_text(json.dumps(reply, indent=2), encoding="utf-8")

        document.update(
            measure_ledger(
                session_cli(session),
                log,
                session.root,
                scratch,
                count=arguments.count,
                year=year,
                seed=arguments.seed,
                mode=arguments.mode,
                budget_seconds=arguments.budget_seconds,
                timings=timings,
            )
        )
        document["timings"] = {key: round(value, 3) for key, value in timings.items()}
        document["summary"] = summarise(document["items"])
    document["finished_at"] = datetime.now(UTC).isoformat()
    return document


def summarise(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate per-movement facts into the reported figures."""
    succeeded = [item for item in items if item["exit"] == 0]
    warm = [item["seconds"] for item in succeeded[1:]]
    prompts = [tokens for item in items for tokens in item["server"]["prompt_tokens"]]
    evaluated = [tokens for item in items for tokens in item["server"]["prompt_eval_tokens"]]
    prompt_ms = [ms for item in items for ms in item["server"]["prompt_eval_ms"]]
    generated = [tokens for item in items for tokens in item["server"]["generated_tokens"]]
    generation_ms = [ms for item in items for ms in item["server"]["generation_ms"]]
    model_ms = [sum(item["server"]["prompt_eval_ms"]) + sum(item["server"]["generation_ms"]) for item in succeeded[1:]]
    requests = [item["server"]["chat_requests"] for item in items]
    total = sum(item["seconds"] for item in items)
    errors: dict[str, int] = {}
    for item in items:
        if item["exit"] != 0:
            key = str(item["error"])
            errors[key] = errors.get(key, 0) + 1
    return {
        "attempted": len(items),
        "succeeded": len(succeeded),
        "errors": errors,
        "first_result_seconds": items[0]["seconds"] if items else None,
        "per_item_seconds_warm": distribution(warm),
        "movements_per_minute": round(60 * len(items) / total, 3) if total else None,
        "movements_per_minute_warm": round(60 * len(warm) / sum(warm), 3) if warm else None,
        "chat_requests_per_item": distribution([float(value) for value in requests]),
        "reask_items": sum(1 for value in requests if value > 1),
        "prompt_tokens": distribution([float(value) for value in prompts]),
        "prompt_eval_tokens_after_cache": distribution([float(value) for value in evaluated]),
        "prompt_eval_ms": distribution(prompt_ms),
        "generated_tokens": distribution([float(value) for value in generated]),
        "generation_ms": distribution(generation_ms),
        "model_ms_per_item_warm": distribution(model_ms),
        "outside_model_seconds_per_item_warm": distribution(
            [item["seconds"] - model / 1000 for item, model in zip(succeeded[1:], model_ms, strict=True)]
        ),
    }


class _Arguments(argparse.Namespace):
    package: str
    scratch: str
    model_store: str
    model: str | None
    context: int | None
    count: int
    out: str
    mode: str
    seed: int
    cpu_only: bool
    inspect: bool
    budget_seconds: float
    select: bool

    def admin_steps(self, lane: str, model: str) -> list[tuple[AdminAction, dict[str, Any]]]:
        """The window's settings the run applies before asking: engine, then the reading model."""
        if not self.select:
            return []
        return [
            ("local_engine_choose", {"engine": "llamacpp"}),
            ("reading_model_choose", {"provider": lane, "model": model}),
        ]


def parse_arguments(argv: Sequence[str] | None = None) -> _Arguments:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    parser.add_argument("--package", default=str(REPO_ROOT / "build" / "windows-x64" / "stage" / "Release" / "app"))
    parser.add_argument("--scratch", default=str(REPO_ROOT / ".tmp" / "ledger-classification-speed" / stamp))
    parser.add_argument("--model-store", default=str(Path.home() / ".ollama" / "models"))
    parser.add_argument("--model", default=None, help="model to present; default: the lane's recommended text model")
    parser.add_argument("--context", type=int, default=None, help=f"context size, at most {MAX_CONTEXT}")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--out", required=True)
    parser.add_argument("--mode", choices=("classification", "saturated"), default="classification")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--cpu-only", action="store_true")
    parser.add_argument("--inspect", action="store_true", help="dump the agent catalogue and settings, then stop")
    parser.add_argument("--budget-seconds", type=float, default=1200.0)
    parser.add_argument("--no-select", dest="select", action="store_false")
    return parser.parse_args(argv, namespace=_Arguments())


def prerequisite_absence(package: Path, model_store: Path) -> str | None:
    """Name the first absent prerequisite the command line points at, or ``None`` when all are present."""
    if not package.is_dir():
        return f"no package at {package}"
    executable = package / _LLAMA_FOLDER / LLAMA_EXECUTABLE
    if not executable.is_file():
        return f"no {LLAMA_EXECUTABLE} in {executable.parent}"
    if not (model_store / "manifests").is_dir():
        return f"no model store at {model_store}"
    return None


def main(argv: Sequence[str] | None = None) -> int:
    """Run the measurement and write its JSON."""
    arguments = parse_arguments(argv)
    absent = prerequisite_absence(Path(arguments.package), Path(arguments.model_store).expanduser())
    if absent is not None:
        print(json.dumps({"absent": absent}), file=sys.stderr)
        return PREREQUISITE_ABSENT
    try:
        document = measure(arguments)
    except PrerequisiteAbsentError as error:
        print(json.dumps({"absent": str(error)}), file=sys.stderr)
        return PREREQUISITE_ABSENT
    except (AcceptanceError, OSError, KeyError, ValueError) as error:
        print(json.dumps({"failed": f"{type(error).__name__}: {error}"}), file=sys.stderr)
        return 1
    out = Path(arguments.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out), "summary": document.get("summary"), "lane": document.get("lane")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
