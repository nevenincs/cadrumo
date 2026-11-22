r"""Measure how fast the ledger classifies movements with a local model, through the built package.

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

Before asking, the run stores the settings the window stores when a person
picks the local model, through the service's parent administration, which the
run holds as the window does because it launched the service with the bearer
the service authenticates its parent by: the local engine (llama.cpp, at the
placement ``--cpu-only`` names), the model on the lane's list, the model
documents are read with, and the model the ``classification`` task kind runs
with, which a classification run reads before the reading model. Each choice
carries the revision the step before it read, and a refused or unapplied step
ends the run with a named error. ``--no-select`` leaves the settings as the
service starts them.

The disposable product root (runtime storage, the agent's hosted root and the
llama-server home) lies outside every Git project, because the bundled
cadrumo-agent refuses a hosted root inside one (``hosted_root_in_git_project``):
a fresh ``cadrumo-e2e-<random>`` directory below ``--scratch``, which defaults
to the account's own temporary folder (``%LOCALAPPDATA%\Temp``, else the
interpreter's temporary directory). A ``--scratch`` inside a Git project is
refused before anything starts. The root is removed at the end without
following links, and only that exactly named directory. The outputs a person
reads afterwards, the served catalogue, the settings replies, the synthetic
statement and the router log, go below the worktree's ``.tmp/`` instead, beside
``--out``.

The person's sign-in runs out: the runtime ends it after its idle window
(15 minutes by default) unless the person's own input extends it, and a
script's commands never do, so the stored sign-in the commands resume, the held
person session and the agent service's lease, which descends from it, all end
then. A run that outlasts the window does what the person does when the window
says their sign-in is about to end: before a command that could outlast the
sign-in, and again after a command refused because it had ended, it signs in
again, starts a new held session, admits a new agent service under it and
stores the window's settings again. Each renewal is recorded under
``sign_ins``; its time is not any movement's.

Exit 0 means every phase ran and the JSON was written; per-movement refusals
are counted in it, not raised. Exit 1 names a failure and exit 130 an
interruption; either way the JSON written so far is still written to
``--out``: the movements measured until then, the phase that failed and the
failure, and the summary of those movements. The logs the run left in the
disposable root (the product's, the runtime's, the agent's) are copied below
the outputs before the root is removed, on success and failure alike. Exit 3
means a prerequisite is absent: the package, its llama-server, the model store
or the model in it, or a ``--scratch`` inside a Git project.
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
import shutil
import statistics
import sys
import tempfile
import time
from collections.abc import Callable, Generator, Mapping, MutableMapping, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Final, Protocol
from urllib.error import URLError
from urllib.request import urlopen

import psutil
from pydantic import BaseModel, JsonValue, ValidationError

from cadrumo.core.config_runtime_fields import LLAMA_SERVER_ADDRESS
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo_agent_service.admin import AdminAction
from cadrumo_agent_service.providers.application.contracts import (
    LocalEngineStatus,
    LocalModelListEntry,
    LocalModelListStatus,
    ProviderSettingsRefusal,
    TaskModelEntry,
)
from cadrumo_agent_service.providers.domain.record import LocalEngine, LocalPlacement
from cadrumo_client.contracts.model_runs import ModelRunTaskKind
from cadrumo_client.transport.windows_process import WindowsProcessScope, unreturned_windows_process_scope
from dev.desktop_agent_live.disposable_root import create_root, enclosing_git_project, remove_root
from dev.paths import REPO_ROOT, TEMP_ROOT
from dev.runtime_lifecycle.agent_service_session import AgentServiceSession, agent_service_session
from dev.runtime_lifecycle.caller_owned_root import AcceptanceError
from dev.runtime_lifecycle.proof_support import supported_filing_year
from dev.temporary_output import prepare_temp_root

PREREQUISITE_ABSENT: Final = 3
_LLAMA_FOLDER: Final = Path("bin") / "llama"
LLAMA_EXECUTABLE: Final = "llama-server.exe" if sys.platform == "win32" else "llama-server"
_MODEL_MEDIA_TYPE: Final = "application/vnd.ollama.image.model"
_DEFAULT_REGISTRY: Final = "registry.ollama.ai"
_DEFAULT_NAMESPACE: Final = "library"
_ENGINE_PROVIDER: Final = LocalEngine.LLAMACPP.value
_OUTPUTS: Final = "ledger-classification-speed"
_HEALTH_SECONDS: Final = 120.0
_INTERRUPTED: Final = 130
_RENEWAL_MARGIN_SECONDS: Final = 120.0
"""The least sign-in left before a command; a renewal happens below it, or below twice the longest command."""
_SIGN_IN_ENDED: Final = frozenset(
    {
        ProfileSessionRefusalReason.EXPIRED_IDLE.value,
        ProfileSessionRefusalReason.EXPIRED_ABSOLUTE.value,
        ProfileSessionRefusalReason.ABSENT.value,
    }
)
"""The stored sign-in refusals that mean it ran out (or was removed when it did), not that the command was wrong."""
_LOG_COPY_LIMIT_BYTES: Final = 256 * 2**20

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


class ScratchInGitProjectError(PrerequisiteAbsentError):
    """``--scratch`` lies inside a Git project, where the bundled agent refuses its hosted root."""


class SetupStepRefusedError(AcceptanceError):
    """The agent service refused one of the window's settings steps; ``code`` is its typed refusal."""

    def __init__(self, step: str, code: str) -> None:
        """Name the step and the service's refusal code."""
        super().__init__(f"setup step {step} refused: {code}")
        self.step = step
        self.code = code


class SetupNotAppliedError(AcceptanceError):
    """A settings step answered, but outside its contract or without the setting it was asked to store."""


class SettingsExchange(Protocol):
    """One parent-administration settings request on the measured service: its action, fields and answer."""

    def __call__(self, action: AdminAction, /, **fields: Any) -> dict[str, JsonValue]:
        """Send ``action`` with ``fields`` and return the service's typed result."""
        ...


class TimedCli(Protocol):
    """One JSON ``aeat`` command on the measured root: its wall seconds, exit code and envelope."""

    def __call__(self, *arguments: str) -> tuple[float, int, dict[str, Any]]:
        """Run ``aeat --format json ARGUMENTS`` and time it."""
        ...


class SignInKeeper(Protocol):
    """The person's sign-in on the measured root: when it ends, and signing in again."""

    def deadline(self) -> datetime | None:
        """When the sign-in ends unless renewed, read without extending it; ``None`` when nothing says."""
        ...

    def renew(self) -> Mapping[str, Any]:
        """Sign in again and stand the service up under it; return what the renewal did."""
        ...


def sign_in_ended(envelope: Mapping[str, Any]) -> str | None:
    """The refusal reason when a command was refused because the stored sign-in ran out, else ``None``."""
    error = envelope.get("error")
    if not isinstance(error, dict) or error.get("code") != "REFUSED_CLI_BOUNDARY":
        return None
    context = error.get("context")
    reason = context.get("sign_in_reason") if isinstance(context, dict) else None
    return reason if isinstance(reason, str) and reason in _SIGN_IN_ENDED else None


class KeptSignInCli:
    """Run JSON commands while keeping the person's sign-in, as the person does when it is about to end.

    Before a command, a sign-in with less left than the margin, or than twice
    the longest command so far, is renewed first. A command refused because
    the sign-in had ended anyway is run once more after a renewal; that refused
    attempt is not timed. Every renewal is kept in ``renewals``.
    """

    def __init__(
        self,
        cli: TimedCli,
        keeper: SignInKeeper,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        margin_seconds: float = _RENEWAL_MARGIN_SECONDS,
    ) -> None:
        """Wrap ``cli`` with ``keeper``; the deadline is read once now and after each renewal."""
        self._cli = cli
        self._keeper = keeper
        self._clock = clock
        self._margin = margin_seconds
        self._longest = 0.0
        self._started = time.perf_counter()
        self.renewals: list[dict[str, Any]] = []
        self._deadline = keeper.deadline()

    def remaining_seconds(self) -> float | None:
        """Seconds of sign-in left by the last deadline read, ``None`` when nothing says."""
        return None if self._deadline is None else (self._deadline - self._clock()).total_seconds()

    def keep_ahead(self) -> None:
        """Renew now when the sign-in may end before the next command does."""
        remaining = self.remaining_seconds()
        if remaining is not None and remaining < max(self._margin, 2 * self._longest):
            self._renew("ahead_of_end", remaining)

    def _renew(self, cause: str, remaining: float | None) -> None:
        started = time.perf_counter()
        record = dict(self._keeper.renew())
        self._deadline = self._keeper.deadline()
        self.renewals.append(
            {
                "cause": cause,
                "remaining_seconds": None if remaining is None else round(remaining, 1),
                "elapsed": round(started - self._started, 3),
                "seconds": round(time.perf_counter() - started, 3),
                **record,
            }
        )

    def __call__(self, *arguments: str) -> tuple[float, int, dict[str, Any]]:
        """Run one command under a live sign-in."""
        self.keep_ahead()
        seconds, code, envelope = self._cli(*arguments)
        ended = sign_in_ended(envelope)
        if ended is not None:
            self._renew(ended, self.remaining_seconds())
            seconds, code, envelope = self._cli(*arguments)
        self._longest = max(self._longest, seconds)
        return seconds, code, envelope


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


def presented_context(requested: int | None, recorded: int | None, model: str) -> int:
    """Return the context the router presents ``model`` with: ``requested``, or else ``recorded``.

    The catalogue's recorded context is the ceiling, as for the runtime manager's preset; a
    model the catalogue records no context for is not presented, and a larger request is refused.
    """
    if recorded is None:
        raise AcceptanceError(f"the agent catalogue records no llama.cpp context for {model}")
    if requested is not None and not 0 < requested <= recorded:
        raise AcceptanceError(f"--context {requested} is outside 1..{recorded}, the context recorded for {model}")
    return requested or recorded


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
def llama_router(
    package: Path, root: Path, log_path: Path, presented: Presented, *, cpu_only: bool
) -> Generator[ServerLog]:
    """Run the package's llama-server as the manager runs it, contained in a kill-on-close job.

    Its home lies in the disposable ``root``; its standard error is kept at ``log_path``.
    """
    executable = (package / _LLAMA_FOLDER / LLAMA_EXECUTABLE).resolve(strict=True)
    home = root / "llama-server"
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
    log = ServerLog(log_path)
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


def _first_value(value: object, key: str) -> object:
    """The first value stored under ``key`` anywhere in ``value``, depth first."""
    if isinstance(value, dict):
        if key in value:
            return value[key]
        children: Sequence[object] = list(value.values())
    elif isinstance(value, list):
        children = value
    else:
        return None
    for child in children:
        found = _first_value(child, key)
        if found is not None:
            return found
    return None


def error_detail(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """What a refusal says happened: its context and the agent's model-run refusal code, wherever it states it."""
    error = envelope.get("error")
    if not isinstance(error, dict):
        return {}
    refusal = _first_value(error, "model_run_refusal")
    return {
        "error_context": error.get("context"),
        "model_run_refusal": refusal if isinstance(refusal, str) else None,
    }


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
        **error_detail(envelope),
        **result_fields(envelope),
        "server": ServerFacts.read(server_lines).as_json(),
        "run_records": run_record_count(product_lines),
        "elapsed": round(elapsed, 3),
    }


def measure_ledger(
    cli: TimedCli,
    log: ServerLog,
    product_root: Path,
    outputs: Path,
    *,
    count: int,
    year: int,
    seed: int,
    mode: str,
    budget_seconds: float,
    timings: dict[str, float],
    fields: MutableMapping[str, Any] | None = None,
) -> MutableMapping[str, Any]:
    """Import the synthetic movements, then classify each one, reading the router's and product's logs per movement.

    Returns the document's ledger fields, written into ``fields`` as they are
    measured, so a failure part way leaves the movements measured so far and
    the ``phase`` it failed in; phase timings are added to ``timings``.
    """
    fields = {} if fields is None else fields
    fields["phase"] = "import"
    rows = synthetic_movements(count, year, seed=seed)
    statement = outputs / "synthetic-statement.csv"
    write_statement(statement, rows)
    seconds, code, envelope = cli("app", "ledger", "import", "--file", str(statement), "--provider", "csv")
    timings["import_seconds"] = seconds
    if code != 0:
        raise AcceptanceError(f"ledger import refused: exit {code}, code {error_code(envelope)}")
    fields["phase"] = "list"
    seconds, code, envelope = cli("app", "ledger", "list")
    timings["list_seconds"] = seconds
    identifiers = transaction_ids(envelope.get("result"))
    if len(identifiers) < count:
        raise AcceptanceError(f"ledger lists {len(identifiers)} movements, expected {count}")
    identifiers = identifiers[:count]

    fields["phase"] = "baseline"
    baseline = []
    for identifier in identifiers[: min(5, len(identifiers))]:
        seconds, _, _ = cli("app", "ledger", "history", identifier)
        baseline.append(seconds)
    fields["cli_baseline_history_seconds"] = distribution(baseline)

    classify = ("app", "ledger", "classify")
    flags = classify_flags(mode)
    items: list[dict[str, Any]] = []
    fields["items"] = items
    fields["phase"] = "classify"
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

    fields["phase"] = "repeat"
    repeat: list[dict[str, Any]] = []
    fields["repeat_same_movement"] = repeat
    for identifier in identifiers[: min(3, len(identifiers))]:
        seconds, code, _ = cli(*classify, identifier, *flags)
        server_lines, server_offset = log.since(server_offset)
        repeat.append({"seconds": round(seconds, 4), "exit": code, "server": ServerFacts.read(server_lines).as_json()})
    fields["phase"] = "measured"
    return fields


def _refusal_code(reply: Mapping[str, JsonValue]) -> str | None:
    """The typed refusal code of a settings answer: the admin wire's ``refused`` or the settings refusal."""
    if reply.get("kind") == "refused":
        return str(reply.get("code"))
    if set(reply) == {"code"}:
        try:
            return ProviderSettingsRefusal.model_validate_json(json.dumps(reply)).code.value
        except ValidationError:
            return str(reply["code"])
    return None


def _settings_answer[Answer: BaseModel](step: str, reply: Mapping[str, JsonValue], contract: type[Answer]) -> Answer:
    """Read one settings answer through the service's own result model, or name the refusal."""
    code = _refusal_code(reply)
    if code is not None:
        raise SetupStepRefusedError(step, code)
    # A computed field is served but is no input of the model.
    stated = {key: value for key, value in reply.items() if key not in contract.model_computed_fields}
    try:
        return contract.model_validate_json(json.dumps(stated))
    except ValidationError as error:
        raise SetupNotAppliedError(f"setup step {step} answered outside its contract") from error


def apply_window_settings(
    settings: SettingsExchange, *, lane: str, model: str, placement: LocalPlacement
) -> dict[str, dict[str, JsonValue]]:
    """Store the settings the window stores for a local model, each at the revision the step before read.

    The engine read gives the record's revision; then the engine and placement,
    the model on ``lane``'s list (a recommended or already added one is kept as
    it is), the model documents are read with, and the model the classification
    task kind runs with are stored in turn. Returns each step's answer by step.
    """
    replies: dict[str, dict[str, JsonValue]] = {}

    def step[Answer: BaseModel](action: AdminAction, contract: type[Answer], **fields: Any) -> Answer:
        reply = settings(action, **fields)
        replies[action] = reply
        return _settings_answer(action, reply, contract)

    engine = step("local_engine", LocalEngineStatus)
    if engine.unreadable:
        raise SetupNotAppliedError("setup step local_engine read an unreadable model list record")
    chosen = step(
        "local_engine_choose",
        LocalEngineStatus,
        engine=LocalEngine.LLAMACPP,
        placement=placement,
        expected_revision=engine.revision,
    )
    if (chosen.engine, chosen.placement, chosen.chosen) != (LocalEngine.LLAMACPP, placement, True):
        raise SetupNotAppliedError(f"setup step local_engine_choose left {chosen.engine} at {chosen.placement}")
    listed = step(
        "local_model_add", LocalModelListStatus, provider=lane, model=model, expected_revision=chosen.revision
    )
    reading = step(
        "reading_model_choose", LocalModelListStatus, provider=lane, model=model, expected_revision=listed.revision
    )
    wanted = LocalModelListEntry(lane=lane, model=model)
    if reading.reading != wanted:
        raise SetupNotAppliedError(
            f"setup step reading_model_choose reads with {reading.reading} ({reading.reading_source.value})"
        )
    kind = ModelRunTaskKind.CLASSIFICATION.value
    tasked = step(
        "task_model_choose",
        LocalModelListStatus,
        task_kind=kind,
        provider=lane,
        model=model,
        expected_revision=reading.revision,
    )
    if TaskModelEntry(task_kind=kind, lane=lane, model=model, effort=None) not in tasked.tasks:
        raise SetupNotAppliedError(f"setup step task_model_choose stored no {kind} setting for {lane} {model}")
    return replies


def default_scratch_parent(environment: Mapping[str, str] | None = None) -> Path:
    r"""The account's own temporary folder, ``%LOCALAPPDATA%\Temp``, else the interpreter's temporary directory.

    The account folder comes first because a development shell or test run may
    point ``TEMP`` into the checkout, where the agent refuses its hosted root.
    """
    local = (os.environ if environment is None else environment).get("LOCALAPPDATA", "").strip()
    return Path(local) / "Temp" if local else Path(tempfile.gettempdir())


def require_scratch_outside_git(parent: Path) -> None:
    """Refuse a ``--scratch`` inside a Git project, by the rule the agent judges its hosted root with."""
    project = enclosing_git_project(parent.absolute())
    if project is not None:
        raise ScratchInGitProjectError(
            f"--scratch {parent} is inside the Git project {project}; the bundled agent refuses a hosted root "
            "there, so the disposable root must lie outside every Git project"
        )


def output_directory(stamp: str) -> Path:
    """The run's outputs below the worktree's ``.tmp/``, created."""
    return prepare_temp_root(override=TEMP_ROOT / _OUTPUTS / stamp)


def copy_run_logs(root: Path, destination: Path) -> list[str]:
    """Copy every log the run left in ``root`` below ``destination``, at its path relative to ``root``.

    A log is a file in a ``logs`` folder or named ``*.log``. Links are never
    followed or copied. Returns the copied relative paths; a file that cannot
    be read, or would pass the copy limit, is named with why instead, so a
    failed copy never hides the failure that brought the run here.
    """
    copied: list[str] = []
    budget = _LOG_COPY_LIMIT_BYTES
    for folder, directories, files in os.walk(root, followlinks=False):
        here = Path(folder)
        directories[:] = [name for name in directories if not (here / name).is_symlink()]
        for name in sorted(files):
            source = here / name
            relative = source.relative_to(root)
            if source.is_symlink() or not ("logs" in relative.parts[:-1] or name.endswith(".log")):
                continue
            try:
                size = source.stat().st_size
                if size > budget:
                    copied.append(f"{relative.as_posix()} (not copied: over the copy limit)")
                    continue
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                budget -= size
                copied.append(relative.as_posix())
            except OSError as error:
                copied.append(f"{relative.as_posix()} (not copied: {type(error).__name__})")
    return copied


def failure_record(error: BaseException, phase: object) -> dict[str, Any]:
    """The failure as the JSON names it: the phase, and each error of its chain by type and message."""
    chain: list[dict[str, str]] = []
    current: BaseException | None = error
    while current is not None and len(chain) < 8:
        chain.append({"type": type(current).__name__, "message": str(current)[:500]})
        current = current.__cause__ or current.__context__
    return {"phase": phase, "type": type(error).__name__, "message": str(error)[:500], "chain": chain}


def measure(arguments: _Arguments, document: dict[str, Any]) -> dict[str, Any]:
    """Run the whole measurement, filling ``document`` as it goes, and return it.

    On any failure, an interruption included, the document keeps what was
    measured, names the phase and the failure, and the run's logs are copied
    out of the disposable root before it is removed; then the failure is raised.
    """
    document["phase"] = "prerequisites"
    package = Path(arguments.package).resolve(strict=True)
    parent = Path(arguments.scratch).absolute()
    require_scratch_outside_git(parent)
    parent.mkdir(parents=True, exist_ok=True)
    outputs = output_directory(arguments.stamp)
    store = Path(arguments.model_store).expanduser().resolve(strict=True)
    year = supported_filing_year()
    document.update(
        {
            "started_at": datetime.now(UTC).isoformat(),
            "package": str(package),
            "outputs": str(outputs),
            "machine": _machine(),
            "count": arguments.count,
            "mode": arguments.mode,
            "placement": arguments.placement.value,
            "booking_year": year,
        }
    )
    root = create_root(parent)
    try:
        _measure_on(arguments, document, package, root, outputs, store, year)
    except BaseException as error:
        document["failure"] = failure_record(error, document.get("phase"))
        raise
    finally:
        document["copied_logs"] = copy_run_logs(root, outputs / "logs")
        left = remove_root(root, parent)
        document["disposable_root_left"] = left
        if left:
            print(json.dumps({"disposable_root_left": left}), file=sys.stderr, flush=True)
        document["finished_at"] = datetime.now(UTC).isoformat()
    return document


def _measure_on(
    arguments: _Arguments,
    document: dict[str, Any],
    package: Path,
    root: Path,
    outputs: Path,
    store: Path,
    year: int,
) -> None:
    """Stand up the session on ``root``, apply the settings and measure, filling ``document``."""
    timings: dict[str, float] = {}
    document["timings"] = timings
    phase = time.perf_counter()
    document["phase"] = "session_setup"
    with ExitStack() as stack:
        session = stack.enter_context(agent_service_session(package, root / "session", owned=True))
        timings["session_setup_seconds"] = time.perf_counter() - phase
        document["session_timings"] = session.timings
        document["agent_event"] = {
            key: session.agent_event.get(key) for key in ("event", "code", "agent_version", "hosting_contract")
        }
        if session.first_refusal_code is not None:
            raise AcceptanceError(f"agent service refused the agent: {session.first_refusal_code}")
        document["phase"] = "catalog"
        catalog = session.catalog()
        (outputs / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
        lane, model, context = lane_model(catalog, arguments.model)
        context = presented_context(arguments.context, context, model)
        presented = Presented(name=model, weights=model_weights(store, model), context=context)
        document["lane"] = {"provider": lane, "model": model, "context": context}
        if arguments.inspect:
            (outputs / "status.json").write_text(json.dumps(session.status(), indent=2), encoding="utf-8")
            for action in ("local_models", "local_engine", "provider_lanes"):
                reply = session.settings(action)
                (outputs / f"{action}.json").write_text(json.dumps(reply, indent=2), encoding="utf-8")
            return

        phase = time.perf_counter()
        document["phase"] = "llama_server"
        log = stack.enter_context(
            llama_router(package, root, outputs / "llama-server.log", presented, cpu_only=arguments.cpu_only)
        )
        timings["llama_server_health_seconds"] = time.perf_counter() - phase
        if arguments.select:
            phase = time.perf_counter()
            document["phase"] = "settings"
            try:
                replies = apply_window_settings(session.settings, lane=lane, model=model, placement=arguments.placement)
            finally:
                timings["settings_seconds"] = time.perf_counter() - phase
            (outputs / "settings.json").write_text(json.dumps(replies, indent=2), encoding="utf-8")
            document["settings"] = {
                "reading": replies["reading_model_choose"].get("reading"),
                "reading_source": replies["reading_model_choose"].get("reading_source"),
                "tasks": replies["task_model_choose"].get("tasks"),
            }

        def renew() -> dict[str, Any]:
            record = session.sign_in_again()
            if session.first_refusal_code is not None:
                raise AcceptanceError(
                    f"agent service refused the agent after signing in again: {session.first_refusal_code}"
                )
            if arguments.select:
                apply_window_settings(session.settings, lane=lane, model=model, placement=arguments.placement)
            return record

        document["phase"] = "sign_in"
        kept = KeptSignInCli(session_cli(session), _SessionSignIn(session, renew))
        document["sign_ins"] = kept.renewals
        measure_ledger(
            kept,
            log,
            session.root,
            outputs,
            count=arguments.count,
            year=year,
            seed=arguments.seed,
            mode=arguments.mode,
            budget_seconds=arguments.budget_seconds,
            timings=timings,
            fields=document,
        )
        # The session is retired by its own cleanup: the sign-in must still be live for its sign-out.
        document["phase"] = "teardown"
        kept.keep_ahead()


@dataclass(frozen=True, slots=True)
class _SessionSignIn:
    """The measured session's sign-in: its deadline as the runtime states it, and the person's renewal."""

    session: AgentServiceSession
    renewal: Callable[[], dict[str, Any]]

    def deadline(self) -> datetime | None:
        """The earlier of the stored sign-in's and the held session's end."""
        return self.session.sign_in_deadline()

    def renew(self) -> Mapping[str, Any]:
        """Sign in again, admit a new service and store the window's settings again."""
        return self.renewal()


def finish_document(document: dict[str, Any]) -> dict[str, Any]:
    """Round the timings and summarise the movements measured, however far the run got."""
    timings = document.get("timings")
    if isinstance(timings, dict):
        document["timings"] = {key: round(value, 3) for key, value in timings.items()}
    items = document.get("items")
    if isinstance(items, list):
        document["summary"] = {
            **summarise(items),
            "sign_in_renewals": len(document.get("sign_ins") or ()),
            "complete": "failure" not in document,
        }
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
    stamp: str

    @property
    def placement(self) -> LocalPlacement:
        """Where the run asks the local engine to run the model: the processor only with ``--cpu-only``."""
        return LocalPlacement.CPU_ONLY if self.cpu_only else LocalPlacement.AUTO


def parse_arguments(argv: Sequence[str] | None = None) -> _Arguments:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    parser.set_defaults(stamp=stamp)
    parser.add_argument("--package", default=str(REPO_ROOT / "build" / "windows-x64" / "stage" / "Release" / "app"))
    parser.add_argument(
        "--scratch",
        default=str(default_scratch_parent()),
        help="where the disposable product root is made; outside every Git project",
    )
    parser.add_argument("--model-store", default=str(Path.home() / ".ollama" / "models"))
    parser.add_argument("--model", default=None, help="model to present; default: the lane's recommended text model")
    parser.add_argument("--context", type=int, default=None, help="context size, at most the catalogue's")
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
        require_scratch_outside_git(Path(arguments.scratch))
    except ScratchInGitProjectError as error:
        print(json.dumps({"absent": str(error), "error": type(error).__name__}), file=sys.stderr)
        return PREREQUISITE_ABSENT
    document: dict[str, Any] = {}
    try:
        measure(arguments, document)
    except PrerequisiteAbsentError as error:
        # Nothing was measured, so there is no document to write.
        print(json.dumps({"absent": str(error)}), file=sys.stderr)
        return PREREQUISITE_ABSENT
    except KeyboardInterrupt as error:
        document.setdefault("failure", failure_record(error, document.get("phase")))
        print(json.dumps({"interrupted": document.get("phase"), "out": arguments.out}), file=sys.stderr)
        _write_document(arguments.out, document)
        return _INTERRUPTED
    except Exception as error:  # every failure still writes what was measured
        document.setdefault("failure", failure_record(error, document.get("phase")))
        print(json.dumps({"failed": f"{type(error).__name__}: {error}", "out": arguments.out}), file=sys.stderr)
        _write_document(arguments.out, document)
        return 1
    _write_document(arguments.out, document)
    print(json.dumps({"out": arguments.out, "summary": document.get("summary"), "lane": document.get("lane")}))
    return 0


def _write_document(out: str, document: dict[str, Any]) -> None:
    """Write the JSON document, finished as far as the run got, when the run started measuring."""
    if not document:
        return
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(finish_document(document), indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
