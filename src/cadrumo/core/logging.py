"""Logging configuration entry point.

Provides :func:`get_logger` as the consistent logger factory to avoid scattered
bare logging instances, with :func:`configure_logging` installing the project
defaults. The installed log-record factory reads the active correlation
contextvars, so every record automatically picks up the active ``run_id`` /
``step_id`` while a run context is bound.

This module attaches the log-record secret scrubber. Every handler
attached through :func:`configure_logging` receives a
:class:`SecretScrubbingFilter` so sensitive fields are redacted before
formatting. Shape-based NIF, URL, and bearer-token matching is delegated
to :func:`~cadrumo.core.redaction.rules.redact_for_log`; this module keeps only
logging-specific key-paired placeholders such as cookies, passphrases, and
certificate serial suffixes.
Callers must omit private values before logging: the scrubber cannot infer
that an ordinary decimal or validation input is taxpayer data.

Encoded document payloads are contained at two seams, because the diagnostic
log is plaintext on disk and a scanned invoice that reaches it has left secure
storage. ``_ThirdPartyDebugFilter`` holds non-Cadrumo loggers below DEBUG
at every sink, so a model or HTTP client never gets to dump a request body
carrying an image; :class:`SecretScrubbingFilter` then redacts base64 payloads
out of the records that remain, including a payload reachable only by rendering
an opaque ``%s`` argument. The first seam needs no knowledge of the payload's
shape, and the second covers first-party records the first seam admits.

Logging is a diagnostic channel, not the CLI result contract. Operator-facing
success payloads and typed :class:`~cadrumo.core.json_contract.Notice` values are
rendered through the JSON/text output stack; this module only prepares redacted
log records and plaintext diagnostic log files rooted by settings.

Producers hand off bounded builtin snapshots before redaction or output. Opaque
arguments are omitted without invoking application rendering hooks. Independent
background sinks expose delivery counters and finite flush/shutdown attempts;
overload rejects diagnostic work rather than blocking application progress.
Queued redaction uses conservative lexical identity matching without borrowing
application registry locks; identity-shaped technical references may be hashed.

Every handler receives a record once. A :func:`get_logger` logger withholds its
record from propagation, so the dispatch thread hands the scrubbed snapshot to
every handler in the hierarchy, foreign ones included. A plain stdlib logger
cannot be intercepted before propagation: foreign handlers already received the
original, so the snapshot goes only to this module's own handlers.
"""

from __future__ import annotations

import atexit
import logging
import math
import os
import sys
import time
from codecs import getincrementalencoder
from collections import deque
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from contextvars import Context, ContextVar, copy_context
from io import BufferedRandom, BufferedWriter, RawIOBase, TextIOWrapper
from pathlib import Path
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING, Any, NamedTuple, TextIO, cast, override

if TYPE_CHECKING:
    from .config import Settings
    from .log_file_handler import AnnouncingRotatingFileHandler
    from .observability.context import RunContextInfo
from .cli_metadata import is_metadata_invocation
from .diagnostic_dispatch import DiagnosticDispatch, DispatchStatus
from .diagnostic_log import DiagnosticFormatter, stamp_diagnostic_record
from .log_scrubbing import SCRUBBED_RECORD, SecretScrubbingFilter, scrub_text
from .log_snapshot import bound_format, snapshot_record, snapshot_value
from .redaction.tax_identity_admission import lexical_tax_identity_redaction

_configured = False
_factory_installed = False


def _is_cli_metadata_invocation() -> bool:
    """Return whether the current ``aeat`` CLI process renders metadata only.

    Help and version rendering must not initialise settings-derived diagnostic
    logging: an operator may need those state-free surfaces precisely because
    Cadrumo has refused a former product-state directory. Normal commands keep
    the existing logging configuration path.
    """
    program = Path(sys.argv[0])
    executable_names = {program.name.lower(), program.parent.name.lower()}
    if not executable_names.intersection({"aeat", "aeat.exe"}):
        return False
    return is_metadata_invocation(sys.argv[1:])


def _run_context_variables() -> tuple[ContextVar[RunContextInfo | None], ContextVar[str | None]]:
    """Return the run and step contextvars, importing their module on first use."""
    from .observability.context import RUN_CONTEXT_VAR, STEP_CONTEXT_VAR

    return RUN_CONTEXT_VAR, STEP_CONTEXT_VAR


#: Position of the message arguments in ``logging.LogRecord``'s positional constructor.
_LOG_RECORD_ARGS_INDEX = 5


def _safe_factory_args(args: tuple[Any, ...]) -> tuple[Any, ...]:
    if len(args) <= _LOG_RECORD_ARGS_INDEX or type(args[_LOG_RECORD_ARGS_INDEX]) is not tuple:
        return args
    arguments = cast(tuple[object, ...], args[_LOG_RECORD_ARGS_INDEX])
    if len(arguments) != 1:
        return args
    candidate = arguments[0]
    if type(candidate) in (str, int, float, bool, bytes, bytearray, tuple, list, dict) or candidate is None:
        return args
    return (*args[:5], (snapshot_value(candidate),), *args[6:])


def _install_run_context_record_factory() -> None:
    """Install a :class:`logging.LogRecord` factory that stamps ``run_id`` / ``step_id``.

    The contextvars live in :mod:`cadrumo.core.observability.context`. They are
    imported lazily, when the first record is made or :func:`configure_logging`
    runs, so installing the factory never triggers a partial import of
    :mod:`cadrumo.core.observability` (which would create a cycle through
    :mod:`cadrumo.core.config` → :mod:`cadrumo.adapters.outbound.aeat.auth` → this module).

    Both fields are EXPECTED to be empty strings on every record a normal CLI
    invocation emits, and that is the accepted design rather than a gap. Wrapping
    commands in run-trace context was deliberately retired from the CLI: material
    state-transition audit is owned by bucket event history and evidence replay by
    the evidence bundle, so a generic command-wrapper trace would be a parallel
    audit vocabulary over the same events. Nothing in a production path enters a
    run context, so nothing populates these.

    They are populated for the surfaces that do enter one — replay and
    golden-output capture, where the run-trace subsystem is the record/replay
    foundation. This note exists because an always-empty ``run_id`` on every log
    line reads as unwired plumbing, and has twice been reported as one.
    """
    global _factory_installed
    if _factory_installed:
        return
    previous_factory = logging.getLogRecordFactory()
    # Cache the contextvars across record creations: the factory runs in the
    # hottest path of the logging subsystem, and resolving them is an import.
    cached_vars: tuple[ContextVar[RunContextInfo | None], ContextVar[str | None]] | None = None

    # KWARGS-ANY-RATIONALE-LOG-RECORD-FACTORY: signature mirrors the stdlib
    # logging.setLogRecordFactory contract whose *args/**kwargs are the raw
    # LogRecord constructor arguments.
    def _factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        nonlocal cached_vars
        # The stdlib probes a lone operand as a Mapping before logger filters.
        # An opaque object's class/metaclass hooks must not run in that probe.
        args = _safe_factory_args(args)
        record = previous_factory(*args, **kwargs)
        if cached_vars is None:
            cached_vars = _run_context_variables()
        run_var, step_var = cached_vars
        ctx = run_var.get(None)
        record.run_id = ctx.run_id if ctx is not None else ""
        record.step_id = step_var.get(None) or ""
        if _OPERATOR_DOCUMENT_OUTPUT.get():
            record.__dict__["_cadrumo_operator_document_output"] = True
        stamp_diagnostic_record(record)
        return record

    logging.setLogRecordFactory(_factory)
    _factory_installed = True


class DropRunEventFilter(logging.Filter):
    """Suppress observability ``run_event`` records on the stderr handler.

    Records carrying a ``run_event`` extra are the per-run JSONL sink's
    diet — they are already delivered to the attached structured sink. Echoing them
    on stderr as well would spam the console with one
    ``run.event NAVIGATION`` line per step; suppressing them here
    removes the noise while leaving the record intact for any other
    handler (including the JSONL sink).
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        return getattr(record, "run_event", None) is None


#: First-party namespaces for Cadrumo and its hosted automation diagnostics. SDK
#: request-body DEBUG remains excluded even when it originates inside the automation.
_FIRST_PARTY_LOGGER_ROOTS = {"cadrumo"}


def register_first_party_logger(namespace: str) -> None:
    """Enroll this process's owning application namespace for scrubbed diagnostics."""
    if not namespace.isidentifier():
        raise ValueError("a logger namespace must be one application identifier")
    _FIRST_PARTY_LOGGER_ROOTS.add(namespace)


class _ThirdPartyDebugFilter(logging.Filter):
    """Hold third-party loggers below DEBUG at every sink that writes to disk.

    The root logger runs at DEBUG so Cadrumo's own diagnostics are complete,
    and that level is inherited by every third-party library in the process.
    An HTTP or model client at DEBUG dumps its full request object, and for a
    vision request that object carries the document itself -- so the record is
    written to the plaintext diagnostic log before any payload rule has to be
    right about its shape.

    Dropping the record at the handler is the categorical half of the defence:
    the record is never formatted, so nothing depends on recognising what the
    library chose to log, and the log stops accruing request-body volume it
    was never meant to hold. :class:`SecretScrubbingFilter` remains the other
    half, covering first-party records this filter deliberately lets through.

    Named libraries are not enumerated. A list would have to be extended for
    every dependency added later, and the one that leaks is the one nobody
    remembered to add.
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Return whether ``record`` may reach the handler.

        Args:
            record: The candidate log record.

        Returns:
            ``True`` for any record at INFO or above, and for DEBUG records
            emitted by a first-party registered application logger.
        """
        if record.levelno >= logging.INFO:
            return True
        return any(record.name == root or record.name.startswith(f"{root}.") for root in _FIRST_PARTY_LOGGER_ROOTS)


#: Extra key marking a record whose content the emitter has ALREADY written to
#: the operator's stream as a structured document. Pass it through ``extra`` on
#: any log call that accompanies such a write.
OPERATOR_DOCUMENT_LOG_EXTRA = "operator_document"
_OPERATOR_DOCUMENT_OUTPUT: ContextVar[bool] = ContextVar("cadrumo_operator_document_output", default=False)


@contextmanager
def operator_document_output() -> Generator[None]:
    """Keep invocation diagnostics in their file while stderr carries a JSON document.

    Records capture the scope when created, so deferred delivery and copied
    async/thread contexts keep the same routing. Other invocations and text
    output retain their stderr diagnostics; no process or handler level changes.
    """
    _install_run_context_record_factory()
    token = _OPERATOR_DOCUMENT_OUTPUT.set(True)
    try:
        yield
    finally:
        _OPERATOR_DOCUMENT_OUTPUT.reset(token)


def _operator_document_record(record: logging.LogRecord) -> bool:
    """Recognize document routing captured at emission, even after its scope ends."""
    return (
        getattr(record, OPERATOR_DOCUMENT_LOG_EXTRA, None) is not None
        or getattr(record, "_cadrumo_operator_document_output", False) is True
    )


#: Line format of every ``cadrumo.log`` record. Readers that parse the file,
#: such as the desktop log view, receive this value rather than a copy.
LOG_FILE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s | %(diagnostic_context)s"


class DropOperatorDocumentEchoFilter(logging.Filter):
    """Keep document-scoped diagnostics and rendered failures off stderr only.

    stderr is the machine-readable error channel: the CLI's terminal boundary
    writes the JSON error document there, and an automation or script parses that
    stream. A diagnostic log record about the same failure is therefore a
    *duplicate* on stderr, and a harmful one — the record carries the raw
    exception and its traceback, so echoing it prepends internal frames and the
    unredacted exception text to a document whose whole purpose is to present a
    translated, redacted message instead.

    Suppressing the echo here keeps the record intact for every other handler,
    so the rotating file sink still receives the full traceback. That matters:
    the INTERNAL document tells the operator to consult the diagnostic logs, so
    the traceback has to actually be in them.
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        return not _operator_document_record(record)


def default_log_file_path() -> Path:
    """Return the file path for non-interactive project logs.

    Resolved through the taxonomy accessor, so the log sits beneath the
    storage root and stays isolated per root rather than mixing every
    session's records into one system-wide file.

    The filename itself is read off the taxonomy's ``LOG_FILE`` member rather
    than declared as an untethered string literal here.
    """
    from .storage_taxonomy import StorageCategory
    from .storage_taxonomy_locations import storage_location, storage_path

    filename = Path(storage_location(StorageCategory.LOG_FILE).subpath).name
    return storage_path(StorageCategory.LOGS).expanduser() / filename


def _prepare_log_directory(log_file: Path) -> str | None:
    """Best-effort create the diagnostic log directory.

    Returns ``None`` when the directory already exists or was created, and a
    short ``"<ErrorType>: <detail>"`` reason string when creation failed with
    an :exc:`OSError`.

    File logging is a best-effort diagnostic channel, not the operator result
    contract. A ``CADRUMO_STORAGE_ROOT`` that the
    process cannot create — an inaccessible Windows path the operator's
    account may not write, a path routed under a non-directory, a
    ``PermissionError`` — MUST degrade to stderr-only logging rather than
    crash CLI startup. Because configuration can run on the first log record,
    before any CLI error boundary exists, an unguarded ``mkdir`` here escapes
    as a raw Python traceback. Swallowing the
    :exc:`OSError` into a reason string keeps startup alive; the caller
    surfaces the reason as an instructive, redacted diagnostic.
    """
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def _install_secret_scrubbing_filters() -> None:
    """Attach one :class:`SecretScrubbingFilter` to the root logger and each handler."""
    root_logger = logging.getLogger()
    if not any(isinstance(active_filter, _DispatchFilter) for active_filter in root_logger.filters):
        root_logger.filters.insert(0, _DispatchFilter())
    if not any(isinstance(active_filter, SecretScrubbingFilter) for active_filter in root_logger.filters):
        root_logger.addFilter(SecretScrubbingFilter())
    for handler in root_logger.handlers:
        if not any(isinstance(active_filter, SecretScrubbingFilter) for active_filter in handler.filters):
            handler.addFilter(SecretScrubbingFilter())


class _ConfigurationParts(NamedTuple):
    load_settings: Callable[[], Settings]
    former_state_error: type[Exception]
    file_handler: type[AnnouncingRotatingFileHandler]


def _configuration_parts() -> _ConfigurationParts:
    """Return what configuration builds its sinks from, importing it on first use."""
    from .config import load_settings
    from .config_state_root import FormerProductStateError
    from .log_file_handler import AnnouncingRotatingFileHandler

    return _ConfigurationParts(load_settings, FormerProductStateError, AnnouncingRotatingFileHandler)


#: Synthetic text shaped like each family redaction recognises. Scrubbing it
#: runs every import the first real record's redaction would otherwise perform.
_DELIVERY_WARMUP_TEXT = (
    "B12345678 12345678Z ES9121000418450200051332 Bearer warmup.token "
    "https://sede.agenciatributaria.gob.es/Sede/warmup?token=warmup password=warmup"
)
_delivery_modules_loaded = False


def _load_delivery_modules() -> None:
    """Import, on this thread, what configuration and the first records would import elsewhere.

    The dispatch thread's first work item imports the settings graph, and its
    first record imports redaction's lazily bound identity and classification
    modules. A producer's own first record imports the run-context module, which
    shares pydantic with that graph, so a producer that logs while the dispatch
    thread is mid-import waits on its import lock. Doing all of it here, before
    anything is queued, leaves no import for either thread to perform or wait on.
    """
    global _delivery_modules_loaded
    if _delivery_modules_loaded:
        return
    _run_context_variables()
    _configuration_parts()
    with lexical_tax_identity_redaction():
        scrub_text(_DELIVERY_WARMUP_TEXT)
    _delivery_modules_loaded = True


def configure_logging() -> None:
    """Schedule idempotent diagnostic configuration without entering its I/O.

    Module imports are the exception: the host's thread performs them, once,
    so that neither the dispatch thread nor a producer logging in the meantime
    stalls behind a cold import. Settings, directories and files are still
    reached only on the dispatch thread.
    """
    if not _configured and not _is_cli_metadata_invocation():
        # The dispatch thread repeats these imports and counts a failure there;
        # a host's startup must not raise for a diagnostic channel.
        with suppress(Exception):
            _load_delivery_modules()
    _submit_work(_configure_logging)


def _replace_root_handlers(sinks: list[logging.Handler], root_level: str) -> None:
    root_logger = logging.getLogger()
    previous = tuple(root_logger.handlers)
    root_logger.handlers = [
        handler
        for handler in previous
        if not isinstance(handler, _AsyncDiagnosticHandler | _ConfigureOnFirstRecordHandler)
    ]
    root_logger.handlers.extend(_AsyncDiagnosticHandler(sink) for sink in sinks)
    root_logger.setLevel(root_level)
    for handler in previous:
        if isinstance(handler, _AsyncDiagnosticHandler):
            handler.close()
    for name in ("alembic.runtime.plugins", "pdfminer", "pikepdf._core"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _configure_logging() -> None:
    """Configure the project-wide diagnostic logging defaults.

    Installs settings-derived stderr/file handlers, the run-context record
    factory, and :class:`SecretScrubbingFilter` on the root logger plus every
    configured handler. The file handler writes redacted diagnostic plaintext
    under :func:`default_log_file_path`; this module does not encrypt logs or
    persist them through secure-object repositories.

    When the diagnostic log directory cannot be created (an inaccessible
    ``CADRUMO_STORAGE_ROOT``), logging degrades to
    stderr-only and records an instructive diagnostic naming the likely
    remedy — it never crashes CLI startup with a raw traceback.

    The function is idempotent, so hosts and the first-record placeholder can
    both reach it without duplicating handlers.
    """
    global _configured
    if _configured or _is_cli_metadata_invocation():
        return

    parts = _configuration_parts()
    try:
        log_file = default_log_file_path()
        settings = parts.load_settings()
    except parts.former_state_error:
        # A normal command must reach the typed CLI refusal boundary instead
        # of crashing while its import-time logger tries to open former state.
        # Do not configure a file handler or inspect the rejected root.
        _configured = True
        _retire_first_record_configuration()
        return
    log_directory_failure = _prepare_log_directory(log_file)
    file_logging_enabled = log_directory_failure is None

    stderr = _DiagnosticStreamHandler(sys.stderr)
    stderr.setLevel(settings.cadrumo_log_stderr_level)
    stderr.addFilter(DropOperatorDocumentEchoFilter())
    sinks: list[logging.Handler] = [stderr]
    if file_logging_enabled:
        file = parts.file_handler(
            str(log_file),
            maxBytes=settings.cadrumo_log_file_max_bytes,
            backupCount=settings.cadrumo_log_file_backup_count,
            encoding="utf-8",
            delay=True,
        )
        file.setLevel(settings.cadrumo_log_file_level)
        sinks.append(file)
    for sink in sinks:
        sink.setFormatter(DiagnosticFormatter(LOG_FILE_FORMAT))
        sink.addFilter(DropRunEventFilter())
        sink.addFilter(_ThirdPartyDebugFilter())
        sink.addFilter(SecretScrubbingFilter())
    _replace_root_handlers(sinks, settings.cadrumo_log_root_level)

    # Local import: the observability layer imports ``cadrumo.core.logging`` for
    # its own get_logger() seed, so attaching the filter at module
    # import time would create a circular import. Inside this function
    # the import is safe because configure_logging() runs after both
    # modules finish loading.
    _install_run_context_record_factory()
    _install_secret_scrubbing_filters()

    _configured = True
    _flush_pending_records()

    if not file_logging_enabled:
        # Surface the degrade at ERROR so it clears the default ERROR-gated
        # stderr handler (a WARNING would be swallowed) and flows through the
        # secret-scrubbing filter installed above. Never silent: the operator
        # is told what failed and the concrete remedy, in place of the raw
        # import-time traceback this degrade replaces.
        logging.getLogger(__name__).error(
            "Diagnostic file logging disabled: cannot create the log directory %s (%s). "
            "Continuing with stderr-only logging. Ensure CADRUMO_STORAGE_ROOT "
            "points at a path your account can write; on Windows check the folder's permissions, "
            "run from a directory you own, or set CADRUMO_STORAGE_ROOT to a writable location.",
            log_file.parent,
            log_directory_failure,
        )


def set_log_level(level: int, *, file_level: int = logging.DEBUG) -> None:
    """Apply ``level`` to the root logger and every sink this module installed.

    The root logger itself is always set to ``logging.DEBUG`` so no
    record is discarded before reaching a handler; each sink then
    applies its own level gate.  ``FileHandler`` sinks receive
    ``file_level`` (default ``DEBUG``) to keep the diagnostic log
    comprehensive.  All other sinks (typically the stderr stream
    handler) receive ``level``.

    A handler some other owner attached to the root, such as a test
    harness's capture handler, keeps its own level: the CLI verbosity
    governs what Cadrumo writes, not what another observer records.

    Configuration and sink-level changes are queued before subsequent records.

    Args:
        level: The effective level for non-file handlers (e.g.
            ``logging.INFO`` for verbose mode).
        file_level: The level applied to :class:`logging.FileHandler`
            instances (default ``logging.DEBUG``).
    """
    # Admit records immediately; the queued command precedes their sink-level checks.
    logging.getLogger().setLevel(logging.DEBUG)

    def apply() -> None:
        _configure_logging()
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        for handler in root_logger.handlers:
            if isinstance(handler, _AsyncDiagnosticHandler):
                sink = handler.sink
                sink.setLevel(file_level if isinstance(sink, logging.FileHandler) else level)

    _submit_work(apply)


_configuration_deferred = False


def defer_logging_configuration() -> None:
    """Keep CLI parse/preflight state-free until dispatch is authorized."""
    global _configuration_deferred
    _configuration_deferred = True


def resume_logging_configuration() -> None:
    """Release a prior startup deferral without configuring by itself."""
    global _configuration_deferred
    _configuration_deferred = False


def logging_configuration_deferred() -> bool:
    """Return whether a host is still keeping this process's logging state-free."""
    return _configuration_deferred


_PENDING_RECORD_LIMIT = 200
_pending_records: deque[logging.LogRecord] = deque(maxlen=_PENDING_RECORD_LIMIT)
_root_level_before_buffering: int | None = None


class _ConfigureOnFirstRecordHandler(logging.Handler):
    """Root placeholder that installs the project configuration on first use.

    Obtaining a logger must not load settings or open the diagnostic log file:
    most production modules do so at import. Hosts configure explicitly at
    their process boundary; this placeholder covers the time before any host
    did. A warning or worse configures logging on the spot. Quieter records
    are held, newest :data:`_PENDING_RECORD_LIMIT` only, and replayed through
    the real handlers once configuration runs, so a host that configures late
    still keeps its early diagnostics. While configuration is deferred or
    suppressed, a warning goes to :data:`logging.lastResort`, which a root
    with any handler no longer reaches.
    """

    configuring = False

    @override
    def handle(self, record: logging.LogRecord) -> bool:
        if _active_record.get() is not record:
            _enqueue_record(record, offered_to_handlers=True)
            return True
        return bool(super().handle(record))

    @override
    def emit(self, record: logging.LogRecord) -> None:
        if _active_record.get() is not record:
            _enqueue_record(record, offered_to_handlers=True)
            return
        root_logger = logging.getLogger()
        walked = tuple(root_logger.handlers)
        _configure_for_first_record(self, record)
        if _defer_record_if_placeholder(self, root_logger, record):
            return
        _forward_first_record(root_logger, walked, record)


def _configure_for_first_record(handler: _ConfigureOnFirstRecordHandler, record: logging.LogRecord) -> None:
    if (
        record.levelno < logging.WARNING
        or _configured
        or _configuration_deferred
        or record.__dict__.get("_cadrumo_configuration_deferred") is True
        or type(handler).configuring
    ):
        return
    type(handler).configuring = True
    try:
        _configure_logging()
    finally:
        type(handler).configuring = False


def _defer_record_if_placeholder(
    handler: _ConfigureOnFirstRecordHandler,
    root_logger: logging.Logger,
    record: logging.LogRecord,
) -> bool:
    if handler not in root_logger.handlers:
        return False
    if record.levelno >= logging.WARNING:
        _handle_as_last_resort(record)
    else:
        _hold_pending_record(record)
    return True


def _forward_first_record(
    root_logger: logging.Logger,
    walked: tuple[logging.Handler, ...],
    record: logging.LogRecord,
) -> None:
    # Configuration replaces the root handler list, so the walk that reached the
    # placeholder never sees the sinks configuration installed, and still
    # reaches every handler it started with. Only the new sinks need the record.
    for active_handler in tuple(root_logger.handlers):
        if active_handler not in walked and record.levelno >= active_handler.level:
            active_handler.handle(record)


def _handle_as_last_resort(record: logging.LogRecord) -> None:
    if _operator_document_record(record):
        _hold_pending_record(record)
        return
    last_resort = logging.lastResort
    if last_resort is not None and record.levelno >= last_resort.level:
        last_resort.handle(record)


def _hold_pending_record(record: logging.LogRecord) -> None:
    if len(_pending_records) == _PENDING_RECORD_LIMIT:
        _dispatch.discard()
    # The walk that held it also reached every foreign handler; only the sinks
    # that configuration installs are still owed this record.
    record.__dict__[_OFFERED_TO_HANDLERS] = True
    _pending_records.append(record)


def _flush_pending_records() -> None:
    """Replay held records through the handlers configuration installed."""
    global _root_level_before_buffering
    _root_level_before_buffering = None
    while _pending_records:
        record = _pending_records.popleft()
        _deliver_work(record)


def _retire_first_record_configuration() -> None:
    """Drop the placeholder and its held records when configuration is refused."""
    global _root_level_before_buffering
    root_logger = logging.getLogger()
    # Replaced rather than removed in place: before CPython 3.13.15 and 3.14.7
    # (gh-79366) an in-place removal makes the walk that reached the placeholder
    # skip the handler after it.
    root_logger.handlers = [
        handler for handler in root_logger.handlers if not isinstance(handler, _ConfigureOnFirstRecordHandler)
    ]
    _pending_records.clear()
    if _root_level_before_buffering is not None:
        root_logger.setLevel(_root_level_before_buffering)
        _root_level_before_buffering = None


def _install_first_record_configuration() -> None:
    global _root_level_before_buffering
    root_logger = logging.getLogger()
    if _configured or any(isinstance(handler, _ConfigureOnFirstRecordHandler) for handler in root_logger.handlers):
        return
    root_logger.addHandler(_ConfigureOnFirstRecordHandler())
    if root_logger.level == logging.WARNING:
        # The stdlib default would discard quieter records before the
        # placeholder could hold them; configuration sets the real level.
        _root_level_before_buffering = root_logger.level
        root_logger.setLevel(logging.DEBUG)


_install_first_record_configuration()


def get_logger(name: str) -> logging.Logger:
    """Return the project logger for the given module name.

    Preferred over direct :func:`logging.getLogger` in production modules
    because it attaches :class:`SecretScrubbingFilter` directly to the
    returned logger. It never configures logging: hosts call
    :func:`configure_logging` at their process boundary, and a record that
    reaches the root first installs the configuration itself.

    Args:
        name: The name of the module, typically __name__.

    Returns:
        The named logging.Logger instance.
    """
    # Stamping run context onto records loads no settings and opens nothing, so
    # it is installed here rather than waiting for a host to configure logging;
    # otherwise records made before configuration carry no ``run_id`` at all.
    _install_run_context_record_factory()
    logger = logging.getLogger(name)
    if not any(isinstance(active_filter, _DispatchFilter) for active_filter in logger.filters):
        logger.filters.insert(0, _DispatchFilter())
    if not any(isinstance(active_filter, SecretScrubbingFilter) for active_filter in logger.filters):
        logger.addFilter(SecretScrubbingFilter())
    return logger


#: Snapshot attribute stating that its original already reached every handler of
#: its logger hierarchy during propagation.
_OFFERED_TO_HANDLERS = "_cadrumo_offered_to_handlers"
_active_record: ContextVar[logging.LogRecord | None] = ContextVar("diagnostic_delivery_record", default=None)

_sink_workers: list[DiagnosticDispatch[logging.LogRecord]] = []
_stdlib_shutdown = logging.shutdown


def _enqueue_record(record: logging.LogRecord, *, offered_to_handlers: bool) -> None:
    """Queue a snapshot of ``record`` for the dispatch thread.

    ``offered_to_handlers`` states whether ``record`` itself goes on to reach the
    handlers of its hierarchy. A logger filter withholds it, so the snapshot owes
    every handler a delivery. A handler that intercepts it during propagation
    leaves the other handlers to receive the original, so the snapshot owes only
    this module's own handlers.
    """
    if _active_record.get() is not None:
        _dispatch.discard()
        return
    # Several root handlers can see one third-party record. Admit it once.
    if record.__dict__.get("_cadrumo_queued_pid") == os.getpid():
        return
    record.__dict__["_cadrumo_queued_pid"] = os.getpid()
    record.__dict__["_cadrumo_configuration_deferred"] = _configuration_deferred
    try:
        snapshot = snapshot_record(record)
        snapshot.__dict__[_OFFERED_TO_HANDLERS] = offered_to_handlers
        _submit_work(snapshot)
    except Exception:
        # A malformed foreign LogRecord must not change the caller's result.
        _dispatch.discard()
        return


class _DispatchFilter(logging.Filter):
    @override
    def filter(self, record: logging.LogRecord) -> bool:
        if _active_record.get() is record:
            return True
        _enqueue_record(record, offered_to_handlers=False)
        return False


def _deliver_work(work: logging.LogRecord | Callable[[], None]) -> None:
    if not isinstance(work, logging.LogRecord):
        work()
        return
    token = _active_record.set(work)
    try:
        exception = work.__dict__.pop("_cadrumo_exception_snapshot", None)
        if exception is not None:
            sections: list[str] = []
            for name, arguments, frames, relation in reversed(exception):
                if sections:
                    sections.append(f"\nException {relation}:\n")
                stack = "".join(f'  File "{path}", line {line}, in {function}\n' for path, line, function in frames)
                sections.append(f"Traceback (most recent call last):\n{stack}{name}: {arguments}")
            work.exc_text = "\n".join(sections)
        bound_format(work)
        with lexical_tax_identity_redaction():
            SecretScrubbingFilter().filter(work)
        scrubbed = SCRUBBED_RECORD.set(work)
        try:
            if work.__dict__.get(_OFFERED_TO_HANDLERS) is True:
                _handle_by_own_handlers(work)
            else:
                logging.getLogger(work.name).handle(work)
        finally:
            SCRUBBED_RECORD.reset(scrubbed)
    finally:
        _active_record.reset(token)


def _handle_by_own_handlers(record: logging.LogRecord) -> None:
    """Offer a snapshot to this module's handlers, along the path ``callHandlers`` takes.

    The original of ``record`` was already offered to every handler of its
    hierarchy, so a foreign handler reached again here would log it twice. Each
    logger's handlers are read once, so a sink installed while the walk is in
    progress is not reached; the placeholder that installs sinks forwards the
    record to them itself.
    """
    found = False
    logger: logging.Logger | None = logging.getLogger(record.name)
    while logger is not None:
        for handler in tuple(logger.handlers):
            found = True
            if isinstance(handler, _AsyncDiagnosticHandler | _ConfigureOnFirstRecordHandler) and (
                record.levelno >= handler.level
            ):
                handler.handle(record)
        logger = logger.parent if logger.propagate else None
    fallback = logging.lastResort
    # The stdlib falls back to ``lastResort`` only for a hierarchy with no handler.
    if not found and isinstance(fallback, _AsyncDiagnosticHandler) and record.levelno >= fallback.level:
        fallback.handle(record)


class _AsyncDiagnosticHandler(logging.Handler):
    def __init__(self, sink: logging.Handler) -> None:
        super().__init__(logging.NOTSET)
        self.sink = sink
        self._worker = DiagnosticDispatch(
            self._write,
            name=f"diagnostic-{type(sink).__name__}",
            capacity=8192,
            finish=sink.close,
        )
        _sink_workers.append(self._worker)

    @override
    def handle(self, record: logging.LogRecord) -> bool:
        # Foreign loggers bypass logger-attached filters during propagation.
        # Intercept before handler filters can enter redaction or registry I/O.
        if _active_record.get() is not record:
            _enqueue_record(record, offered_to_handlers=True)
            return True
        return bool(super().handle(record))

    def _write(self, record: logging.LogRecord) -> None:
        token = _active_record.set(record)
        scrubbed = SCRUBBED_RECORD.set(record)
        try:
            self.sink.handle(record)
        finally:
            SCRUBBED_RECORD.reset(scrubbed)
            _active_record.reset(token)

    @override
    def emit(self, record: logging.LogRecord) -> None:
        if _active_record.get() is record:
            if record.levelno < self.sink.level:
                return
            snapshot = logging.LogRecord.__new__(logging.LogRecord)
            snapshot.__dict__ = record.__dict__.copy()
            self._worker.submit(snapshot, weight=record.__dict__.get("_cadrumo_snapshot_weight", 1024))
        else:
            _enqueue_record(record, offered_to_handlers=True)

    @override
    def close(self) -> None:
        self._worker.close(timeout=0)
        super().close()


class _DiagnosticStreamHandler(logging.StreamHandler[TextIO]):
    def __init__(self, stream: TextIO, *, follow_stderr: bool = False) -> None:
        super().__init__(stream)
        self._follow_stderr = follow_stderr
        self._raw: RawIOBase | None = None
        self._encoder = getincrementalencoder("utf-8")("backslashreplace")
        self._prepare_stream()

    def _prepare_stream(self) -> None:
        self._raw = None
        if type(self.stream) is TextIOWrapper:
            buffer = self.stream.buffer
            raw = (
                cast("BufferedWriter[RawIOBase] | BufferedRandom", buffer).raw
                if isinstance(buffer, BufferedWriter | BufferedRandom)
                else buffer
            )
            if isinstance(raw, RawIOBase):
                self._raw = raw
                self._encoder = getincrementalencoder(self.stream.encoding)(self.stream.errors or "backslashreplace")

    @override
    def emit(self, record: logging.LogRecord) -> None:
        if self._follow_stderr and sys.stderr is not self.stream and sys.stderr is not None:
            # setStream flushes the old stream, which can itself be blocked.
            self.stream = sys.stderr
            self._prepare_stream()
        if self._raw is None:
            super().emit(record)
            return
        # A daemon must never hold stderr's BufferedWriter lock: CPython takes
        # that lock again during finalization, beyond our bounded shutdown.
        data = self._encoder.encode((self.format(record) + self.terminator).replace("\n", os.linesep))
        with _stderr_write_guard:
            remaining = memoryview(data)
            while remaining:
                written = self._raw.write(remaining)
                if written is None or written <= 0:
                    raise OSError("diagnostic stream delivery failed")
                remaining = remaining[written:]

    @override
    def handleError(self, record: logging.LogRecord) -> None:
        # The stdlib fallback prints the unsanitized record and arguments.
        raise OSError("diagnostic stream delivery failed") from None


_stderr_write_guard = Lock()


def _reset_stderr_write_guard() -> None:
    global _stderr_write_guard
    _stderr_write_guard = Lock()


if sys.platform != "win32" and hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_stderr_write_guard)


_dispatch = DiagnosticDispatch[logging.LogRecord | Callable[[], None]](
    _deliver_work, name="diagnostic-records", capacity=8192
)


def _submit_work(work: logging.LogRecord | Callable[[], None]) -> None:
    """Keep configuration settings without retaining an invocation's authority lease."""
    if _configured:
        weight = work.__dict__.get("_cadrumo_snapshot_weight", 1024) if isinstance(work, logging.LogRecord) else 1024
        _dispatch.submit(work, weight=weight)
        return
    context = Context()
    for variable, value in copy_context().items():
        if variable.name == "settings_override":
            context.run(variable.set, value)
    weight = work.__dict__.get("_cadrumo_snapshot_weight", 1024) if isinstance(work, logging.LogRecord) else 1024
    _dispatch.submit(lambda: context.run(_deliver_work, work), weight=weight)


def flush_logging(*, timeout: float = 2.0) -> bool:
    """Attempt delivery within one bound; ordinary log calls never wait for this."""
    deadline = time.monotonic() + (max(0.0, timeout) if math.isfinite(timeout) else 0.0)
    if not _dispatch.flush(timeout=max(0.0, deadline - time.monotonic())):
        return False
    complete = True
    for worker in tuple(_sink_workers):
        complete = worker.flush(timeout=max(0.0, deadline - time.monotonic())) and complete
    return complete


def diagnostic_delivery_status() -> dict[str, DispatchStatus]:
    """Read delivery health without acquiring any formatter, handler or file lock."""
    return {
        "records": _dispatch.status(),
        **{f"sink_{index}": worker.status() for index, worker in enumerate(tuple(_sink_workers))},
    }


_shutdown_guard = Lock()
_shutdown_finished = Event()
_shutdown_thread: Thread | None = None


def shutdown_logging(*, timeout: float = 2.0) -> None:
    """Also bound stdlib shutdown, whose default waits indefinitely on sink locks."""
    global _shutdown_thread
    deadline = time.monotonic() + (max(0.0, timeout) if math.isfinite(timeout) else 0.0)
    flush_logging(timeout=max(0.0, deadline - time.monotonic()))
    for worker in tuple(_sink_workers):
        worker.close(timeout=max(0.0, deadline - time.monotonic()))

    def finish() -> None:
        try:
            _stdlib_shutdown()
        finally:
            _shutdown_finished.set()

    with _shutdown_guard:
        if _shutdown_thread is None:
            _shutdown_thread = Thread(target=finish, name="diagnostic-shutdown", daemon=True)
            try:
                _shutdown_thread.start()
            except RuntimeError:
                _shutdown_finished.set()
    _shutdown_finished.wait(max(0.0, deadline - time.monotonic()))


atexit.unregister(_stdlib_shutdown)
atexit.register(shutdown_logging)

# Preserve caller-installed fallback handlers. The stdlib default must use the
# same isolated sink as configured diagnostics, including before configuration.
if type(logging.lastResort) is getattr(logging, "_StderrHandler", None):
    _fallback_sink = _DiagnosticStreamHandler(sys.stderr, follow_stderr=True)
    _fallback_sink.addFilter(DropOperatorDocumentEchoFilter())
    _fallback_sink.addFilter(DropRunEventFilter())
    _fallback_sink.addFilter(_ThirdPartyDebugFilter())
    _fallback_handler = _AsyncDiagnosticHandler(_fallback_sink)
    _fallback_handler.setLevel(logging.WARNING)
    logging.lastResort = _fallback_handler
