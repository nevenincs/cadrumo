"""Logging configuration entry point.

Provides :func:`get_logger` as the consistent logger factory to avoid scattered
bare logging instances, with :func:`configure_logging` installing the project
defaults. The installed log-record factory reads
:func:`cadrumo.core.observability.current_run_context` state indirectly through
contextvars, so every record automatically picks up the active ``run_id`` /
``step_id`` while a run context is bound.

This module attaches the log-record secret scrubber. Every handler
attached through :func:`configure_logging` receives a
:class:`SecretScrubbingFilter` so sensitive fields are redacted before
formatting. Shape-based NIF, URL, and bearer-token matching is delegated
to :func:`~cadrumo.core.redaction.redact_for_log`; this module keeps only
logging-specific key-paired placeholders such as cookies, passphrases, and
certificate serial suffixes. Per-run JSONL handlers are attached with
:func:`attach_run_sink` so the same filter protects observability output.

Logging is a diagnostic channel, not the CLI result contract. Operator-facing
success payloads and typed :class:`~cadrumo.core.json_contract.Notice` values are
rendered through the JSON/text output stack; this module only prepares redacted
log records and plaintext diagnostic log files rooted by settings.
"""

from __future__ import annotations

import logging
import logging.config
import logging.handlers
import re
import sys
from collections.abc import Mapping
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Any, overload, override

from pydantic import ConfigDict, RootModel

if TYPE_CHECKING:
    from .observability import RunContextInfo
from .cli_metadata import is_metadata_invocation
from .redaction import redact_for_log

_CONFIGURED = False
_FACTORY_INSTALLED = False
_STANDARD_LOG_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)
_EXCEPTION_FORMATTER = logging.Formatter()

SCRUB_FIELD_PATTERNS: tuple[str, ...] = (
    "access_token",
    "api_key",
    "authorization",
    "bearer",
    "bearer_header",
    "cert_password",
    "certificate_password",
    "certificate_serial",
    "cif",
    "cookie",
    "credential",
    "llm_api_key",
    "nif",
    "nie",
    "oauth_access_token",
    "oauth_refresh_token",
    "passphrase",
    "pkcs12",
    "profile_tax_id",
    "refresh_token",
    "secret",
    "session_cookie",
    "tax_id",
    "token",
)


LogExtraValue = str | int | float | bool | None
"""Closed union of stdlib-loggable scalar types accepted by :class:`LogExtra`."""


class LogExtra(RootModel[dict[str, LogExtraValue]]):
    """Typed logging ``extra`` payload restricted to flat loggable scalars.

    Upgrades the historical ``Mapping[str, object]`` return annotation on
    service-layer ``as_extra()`` log-field helpers (e.g.
    :class:`~cadrumo.application.aggregation.PerModeloAggregationLogFields`,
    :class:`~cadrumo.application.operator_surface.OperatorSurfaceContract`'s
    ``log_fields``): every current emitter only ever writes flat, non-secret
    scalars into :meth:`logging.Logger.debug`'s ``extra=`` mapping, so
    accepting bare ``object`` values understated the real contract. A future
    field that accidentally carried a nested mapping, a Decimal, or another
    non-serialisable value now fails loudly at construction with a
    :class:`pydantic.ValidationError` naming the offending field, instead of
    surfacing later as a JSONL-sink serialisation surprise.

    Use :meth:`for_logging` to materialise the plain ``dict`` the stdlib
    ``logging`` module's ``extra=`` parameter expects; the model itself is not
    iterable the way :meth:`logging.Logger.makeRecord` requires.
    """

    model_config = ConfigDict(frozen=True)

    def for_logging(self) -> dict[str, LogExtraValue]:
        """Return the payload as the plain ``dict`` ``logging`` extras expect."""
        return dict(self.root)


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


_SENSITIVE_KEY_SET = frozenset(pattern.lower() for pattern in SCRUB_FIELD_PATTERNS)
_SENSITIVE_ASSIGNMENT_KEYS: tuple[str, ...] = (*sorted(SCRUB_FIELD_PATTERNS, key=lambda p: len(p), reverse=True),)

_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<key>"
    + "|".join(re.escape(pattern) for pattern in _SENSITIVE_ASSIGNMENT_KEYS)
    + r")(?![A-Za-z0-9])(?P<separator>\s*[:=]\s*)"
    + r"(?P<value>\"[^\"]*\"|'[^']*'|[^,;\r\n]+?)"
    + r"(?=$|[,;\r\n]|\s+[A-Za-z0-9_.-]+\s*[:=])",
    flags=re.IGNORECASE,
)
_BEARER_TOKEN_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+\b")
_LLM_KEY_RE = re.compile(r"\b(?:sk-ant-|sk-proj-|sk-live-|sk-test-|sk-)[A-Za-z0-9_-]+\b")
_PERCENT_PLACEHOLDER_VALUE_RE = re.compile(r"^%[-#+ 0-9.]*[a-zA-Z]$")
_PERCENT_PLACEHOLDER_RE = re.compile(r"(?:(?P<key>[A-Za-z0-9_.-]+)\s*[:=]\s*)?(?P<placeholder>%[-#+ 0-9.]*[a-zA-Z])")
_DEFAULT_LOG_FILE_NAME = "cadrumo.log"


def _normalise_log_key(key: str) -> str:
    """Return a canonical, separator-stable representation of ``key``."""
    camel_split = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    collapsed = re.sub(r"[^A-Za-z0-9]+", "_", camel_split)
    return collapsed.strip("_").lower()


def _looks_sensitive_key(key: str | None) -> bool:
    """Return whether ``key`` should have its value redacted."""
    return key is not None and _normalise_log_key(key) in _SENSITIVE_KEY_SET


def _redacted_value(key: str | None, value: str) -> str:
    """Return the stable redaction marker for a sensitive value."""
    if key is not None and "serial" in key.lower():
        suffix = value[-4:] if len(value) >= 4 else "????"
        return f"<cert:....{suffix}>"
    return "<redacted>"


def _scrub_text(value: str, *, key: str | None = None) -> str:
    """Redact sensitive fragments from a free-form string."""
    if not value:
        return value
    if _looks_sensitive_key(key):
        return _redacted_value(key, value)

    scrubbed = redact_for_log(value)
    scrubbed = _SENSITIVE_ASSIGNMENT_RE.sub(
        lambda match: (
            match.group(0)
            if _PERCENT_PLACEHOLDER_RE.search(match.group("value"))
            else (
                f"{match.group('key')}{match.group('separator')}"
                f"{_redacted_value(match.group('key'), match.group('value'))}"
            )
        ),
        scrubbed,
    )
    scrubbed = _BEARER_TOKEN_RE.sub("Bearer <redacted>", scrubbed)
    scrubbed = _LLM_KEY_RE.sub("<redacted>", scrubbed)
    return scrubbed


@overload
def _scrub_value(value: str, *, key: str | None = ...) -> str: ...


@overload
def _scrub_value(value: Mapping[str, object], *, key: str | None = ...) -> dict[str, object]: ...


@overload
def _scrub_value(value: tuple[object, ...], *, key: str | None = ...) -> tuple[object, ...]: ...


@overload
def _scrub_value(value: list[object], *, key: str | None = ...) -> list[object]: ...


@overload
def _scrub_value(value: set[object], *, key: str | None = ...) -> set[object]: ...


@overload
def _scrub_value(value: object, *, key: str | None = ...) -> object: ...


# ANY-RETURN-RATIONALE-SCRUB-OVERLOAD-IMPL:
# The implementation overload returns Any to subsume all concrete overload
# return types per mypy overload rules.
def _scrub_value(value: object, *, key: str | None = None) -> Any:  # ANY-RETURN-RATIONALE-SCRUB-OVERLOAD-IMPL
    """Recursively scrub sensitive values in common logging payload shapes."""
    if isinstance(value, str):
        return _scrub_text(value, key=key)
    if isinstance(value, Mapping):
        return {item_key: _scrub_value(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, tuple):
        return tuple(_scrub_value(item, key=key) for item in value)
    if isinstance(value, list):
        return [_scrub_value(item, key=key) for item in value]
    if isinstance(value, set):
        return {_scrub_value(item, key=key) for item in value}
    if _looks_sensitive_key(key):
        return _redacted_value(key, str(value))
    return value


# ANY-RETURN-RATIONALE-LOGGING-POSITIONAL-ARGS: args/return mirror the stdlib
# logging.LogRecord positional-args tuple, whose element types are arbitrary
# %-formatting operands.
def _scrub_positional_args(message: str, args: tuple[Any, ...]) -> tuple[Any, ...]:
    """Scrub tuple-style logging args using keys inferred from ``message``."""
    placeholders = list(_PERCENT_PLACEHOLDER_RE.finditer(message))
    return tuple(
        _scrub_value(arg, key=placeholders[index].group("key") if index < len(placeholders) else None)
        for index, arg in enumerate(args)
    )


class SecretScrubbingFilter(logging.Filter):
    """Redact sensitive fields from log records before formatting.

    The filter mutates each :class:`logging.LogRecord` in place so handlers,
    stderr diagnostics, and JSONL run sinks see the same scrubbed record. It is
    deliberately narrower than CLI output redaction: structured command results
    still route through :mod:`cadrumo.core.output_rendering` or
    :mod:`cadrumo.core.json_contract`, while this filter protects logging-only
    message text, %-format args, exception text, and ``extra`` fields.
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Scrub sensitive values from ``record`` in-place and return ``True`` to allow it.

        Args:
            record: The log record whose ``msg``, ``args``, ``exc_info``,
                ``exc_text``, and extra fields are scrubbed before formatting.

        Returns:
            Always ``True`` — every record is allowed through after scrubbing.
        """
        if isinstance(record.msg, str):
            record.msg = _scrub_text(record.msg)
        else:
            record.msg = _scrub_value(record.msg)

        if isinstance(record.args, tuple | list) and isinstance(record.msg, str):
            scrubbed_args = _scrub_positional_args(record.msg, tuple(record.args))
            # ``logging.LogRecord.args`` is annotated ``tuple[object, ...]
            # | Mapping[str, object] | None``; ``list`` is not in the
            # union even though logging accepts it at runtime.
            # Normalising to a tuple sidesteps the union mismatch
            # without changing the runtime contract.
            record.args = tuple(scrubbed_args)
        elif isinstance(record.args, Mapping):
            scrubbed_mapping = {str(k): _scrub_value(v, key=str(k)) for k, v in record.args.items()}
            record.args = scrubbed_mapping
        elif isinstance(record.args, tuple | list):
            # Residual tuple/list args reached only when ``record.msg`` is not a
            # str (the positional branch above requires a str format). Preserve
            # the original ``_scrub_value`` element-wise scrubbing so no args
            # path skips redaction.
            record.args = tuple(_scrub_value(item) for item in record.args)

        if record.exc_info is not None:
            record.exc_text = _scrub_text(_EXCEPTION_FORMATTER.formatException(record.exc_info))
        elif record.exc_text:
            record.exc_text = _scrub_text(record.exc_text)

        for key, value in tuple(record.__dict__.items()):
            if key in _STANDARD_LOG_RECORD_FIELDS or key in {"msg", "args", "exc_info", "exc_text"}:
                continue
            record.__dict__[key] = _scrub_value(value, key=key)
        return True


def _install_run_context_record_factory() -> None:
    """Install a :class:`LogRecord` factory that stamps ``run_id`` / ``step_id``.

    The contextvars live in :mod:`cadrumo.core.observability._context`. They are
    imported lazily inside the closure so this function never triggers
    a partial import of :mod:`cadrumo.core.observability` (which would create a
    cycle through :mod:`cadrumo.core.config` → :mod:`cadrumo.adapters.outbound.aeat.auth` → this module).
    """
    global _FACTORY_INSTALLED
    if _FACTORY_INSTALLED:
        return
    previous_factory = logging.getLogRecordFactory()
    # Cache the contextvars across record creations. The `import` statement
    # is cheap after the first call (``sys.modules`` lookup), but hoisting
    # it into the closure eliminates the repeated try/except on every
    # single log record — the factory runs in the hottest path of the
    # logging subsystem.
    cached_vars: tuple[ContextVar[RunContextInfo | None], ContextVar[str | None]] | None = None

    # KWARGS-ANY-RATIONALE-LOG-RECORD-FACTORY: signature mirrors the stdlib
    # logging.setLogRecordFactory contract whose *args/**kwargs are the raw
    # LogRecord constructor arguments.
    def _factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        nonlocal cached_vars
        record = previous_factory(*args, **kwargs)
        if cached_vars is None:
            from .observability import (
                RUN_CONTEXT_VAR,
                STEP_CONTEXT_VAR,
            )

            cached_vars = (RUN_CONTEXT_VAR, STEP_CONTEXT_VAR)
        run_var, step_var = cached_vars
        ctx = run_var.get(None)
        record.run_id = ctx.run_id if ctx is not None else ""
        record.step_id = step_var.get(None) or ""
        return record

    logging.setLogRecordFactory(_factory)
    _FACTORY_INSTALLED = True


class _DropRunEventFilter(logging.Filter):
    """Suppress observability ``run_event`` records on the stderr handler.

    Records carrying a ``run_event`` extra are the per-run JSONL sink's
    diet — they're already persisted to ``events.jsonl`` via
    :class:`~cadrumo.core.observability._sink.JsonlRunSink`. Echoing them
    on stderr as well would spam the console with one
    ``run.event NAVIGATION`` line per step; suppressing them here
    removes the noise while leaving the record intact for any other
    handler (including the JSONL sink).
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        return getattr(record, "run_event", None) is None


#: Extra key marking a record whose content the emitter has ALREADY written to
#: the operator's stream as a structured document. Pass it through ``extra`` on
#: any log call that accompanies such a write.
OPERATOR_DOCUMENT_LOG_EXTRA = "operator_document"


class _DropOperatorDocumentEchoFilter(logging.Filter):
    """Suppress records already rendered as an operator document, on stderr only.

    stderr is the machine-readable error channel: the CLI's terminal boundary
    writes the JSON error document there, and an agent or script parses that
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
        return getattr(record, OPERATOR_DOCUMENT_LOG_EXTRA, None) is None


def default_log_file_path() -> Path:
    """Return the file path for non-interactive project logs.

    The diagnostic log is rooted under ``cadrumo_log_dir``, which the
    :class:`~cadrumo.core.config.Settings` validator derives from
    ``<cadrumo_local_storage_root>/logs`` when no explicit ``CADRUMO_LOG_DIR``
    override is supplied — so the log stays isolated per workspace
    rather than mixing every session's records into a single
    system-wide file.
    """
    from .config import load_settings

    log_dir = load_settings().cadrumo_log_dir
    if log_dir is None:  # pragma: no cover - validator always populates the field
        log_dir = load_settings().cadrumo_local_storage_root / "logs"
    return log_dir.expanduser() / _DEFAULT_LOG_FILE_NAME


def _prepare_log_directory(log_file: Path) -> str | None:
    """Best-effort create the diagnostic log directory.

    Returns ``None`` when the directory already exists or was created, and a
    short ``"<ErrorType>: <detail>"`` reason string when creation failed with
    an :exc:`OSError`.

    File logging is a best-effort diagnostic channel, not the operator result
    contract. An ``CADRUMO_LOCAL_STORAGE_ROOT`` / ``CADRUMO_LOG_DIR`` that the
    process cannot create — an inaccessible Windows path the operator's
    account may not write, a path routed under a non-directory, a
    ``PermissionError`` — MUST degrade to stderr-only logging rather than
    crash CLI startup. Because :func:`get_logger` (and therefore this call)
    runs at module-import time, an unguarded ``mkdir`` here escapes as a raw
    Python traceback long before any CLI error boundary exists. Swallowing the
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
    if not any(isinstance(active_filter, SecretScrubbingFilter) for active_filter in root_logger.filters):
        root_logger.addFilter(SecretScrubbingFilter())
    for handler in root_logger.handlers:
        if not any(isinstance(active_filter, SecretScrubbingFilter) for active_filter in handler.filters):
            handler.addFilter(SecretScrubbingFilter())


def configure_logging() -> None:
    """Configure the project-wide diagnostic logging defaults.

    Installs settings-derived stderr/file handlers, the run-context record
    factory, and :class:`SecretScrubbingFilter` on the root logger plus every
    configured handler. The file handler writes redacted diagnostic plaintext
    under :func:`default_log_file_path`; this module does not encrypt logs or
    persist them through secure-object repositories.

    When the diagnostic log directory cannot be created (an inaccessible
    ``CADRUMO_LOCAL_STORAGE_ROOT`` / ``CADRUMO_LOG_DIR``), logging degrades to
    stderr-only and records an instructive diagnostic naming the likely
    remedy — it never crashes CLI startup with a raw traceback.

    The function is idempotent so early imports can safely call
    :func:`get_logger` without duplicating handlers.
    """
    global _CONFIGURED
    if _CONFIGURED or _is_cli_metadata_invocation():
        return

    from ._config_state_root import FormerProductStateError
    from .config import load_settings

    try:
        log_file = default_log_file_path()
        settings = load_settings()
    except FormerProductStateError:
        # A normal command must reach the typed CLI refusal boundary instead
        # of crashing while its import-time logger tries to open former state.
        # Do not configure a file handler or inspect the rejected root.
        _CONFIGURED = True
        return
    log_directory_failure = _prepare_log_directory(log_file)
    file_logging_enabled = log_directory_failure is None

    configured_handlers: dict[str, dict[str, Any]] = {
        "stderr": {
            "level": settings.cadrumo_log_stderr_level,
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "filters": ["drop_run_event", "drop_operator_document"],
        },
    }
    root_handlers = ["stderr"]
    if file_logging_enabled:
        configured_handlers["file"] = {
            "level": settings.cadrumo_log_file_level,
            "formatter": "standard",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_file),
            "maxBytes": settings.cadrumo_log_file_max_bytes,
            "backupCount": settings.cadrumo_log_file_backup_count,
            "encoding": "utf-8",
            "filters": ["drop_run_event"],
        }
        root_handlers.append("file")
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
            },
            "filters": {
                "drop_run_event": {"()": f"{__name__}._DropRunEventFilter"},
                "drop_operator_document": {"()": f"{__name__}._DropOperatorDocumentEchoFilter"},
            },
            "handlers": configured_handlers,
            "root": {
                "handlers": root_handlers,
                "level": settings.cadrumo_log_root_level,
            },
            "loggers": {
                "alembic.runtime.plugins": {
                    "level": "WARNING",
                    "propagate": True,
                },
                "pdfminer": {
                    "level": "WARNING",
                    "propagate": True,
                },
                "pikepdf._core": {
                    "level": "WARNING",
                    "propagate": True,
                },
            },
        },
    )

    # Local import: the observability layer imports ``cadrumo.core.logging`` for
    # its own get_logger() seed, so attaching the filter at module
    # import time would create a circular import. Inside this function
    # the import is safe because configure_logging() runs after both
    # modules finish loading.
    _install_run_context_record_factory()
    _install_secret_scrubbing_filters()

    _CONFIGURED = True

    if not file_logging_enabled:
        # Surface the degrade at ERROR so it clears the default ERROR-gated
        # stderr handler (a WARNING would be swallowed) and flows through the
        # secret-scrubbing filter installed above. Never silent: the operator
        # is told what failed and the concrete remedy, in place of the raw
        # import-time traceback this degrade replaces.
        logging.getLogger(__name__).error(
            "Diagnostic file logging disabled: cannot create the log directory %s (%s). "
            "Continuing with stderr-only logging. Ensure CADRUMO_LOCAL_STORAGE_ROOT / CADRUMO_LOG_DIR "
            "points at a path your account can write; on Windows check the folder's permissions, "
            "run from a directory you own, or set CADRUMO_LOCAL_STORAGE_ROOT to a writable location.",
            log_file.parent,
            log_directory_failure,
        )


def set_log_level(level: int, *, file_level: int = logging.DEBUG) -> None:
    """Apply ``level`` to the root logger and every attached handler.

    The root logger itself is always set to ``logging.DEBUG`` so no
    record is discarded before reaching a handler; each handler then
    applies its own level gate.  ``FileHandler`` instances receive
    ``file_level`` (default ``DEBUG``) to keep the diagnostic log
    comprehensive.  All other handlers (typically the stderr stream
    handler) receive ``level``.

    :func:`configure_logging` is called first so the dictConfig contract
    is in place before any level mutation.

    Args:
        level: The effective level for non-file handlers (e.g.
            ``logging.INFO`` for verbose mode).
        file_level: The level applied to :class:`logging.FileHandler`
            instances (default ``logging.DEBUG``).
    """
    configure_logging()
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.setLevel(file_level)
        else:
            handler.setLevel(level)


def attach_run_sink(sink: logging.Handler) -> None:
    """Install ``SecretScrubbingFilter`` on ``sink`` then attach it to root.

    Ensures every record flowing through the JSONL run sink is scrubbed
    before it reaches the serialiser, even when the root-logger filter
    has already scrubbed the shared record in-place.  The filter is
    idempotent: a second call with the same sink is a no-op because the
    guard checks ``root_logger.handlers`` for an existing instance.

    Args:
        sink: The :class:`logging.Handler` (typically
            :class:`cadrumo.core.observability._sink.JsonlRunSink`) to
            attach to the root logger.

    The sink is a diagnostic observability target. It receives redacted log
    records, not CLI result payloads or secure-storage records.
    """
    if not any(isinstance(f, SecretScrubbingFilter) for f in sink.filters):
        sink.addFilter(SecretScrubbingFilter())
    logging.getLogger().addHandler(sink)


def detach_run_sink(sink: logging.Handler) -> None:
    """Remove ``sink`` from the root logger and perform symmetric teardown.

    Reverses every side-effect of :func:`attach_run_sink`: the handler is
    removed from the root logger, the :class:`SecretScrubbingFilter`
    instances that :func:`attach_run_sink` installed on the sink are
    removed, and the sink is flushed so in-flight records reach their
    destination before the handle is released.

    The caller is responsible for closing the sink after detach; this
    function deliberately does not call :meth:`~logging.Handler.close` so
    a caller can flush output and inspect state before teardown.

    Args:
        sink: The :class:`logging.Handler` previously attached by
            :func:`attach_run_sink`.
    """
    logging.getLogger().removeHandler(sink)
    sink.filters = [f for f in sink.filters if not isinstance(f, SecretScrubbingFilter)]
    sink.flush()


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name.

    Preferred over direct :func:`logging.getLogger` in production modules
    because it ensures the project defaults are installed and attaches
    :class:`SecretScrubbingFilter` directly to the returned logger. Startup
    modules that must use stdlib logging before settings load rely on later
    propagation through the configured root logger instead.

    Args:
        name: The name of the module, typically __name__.

    Returns:
        A configured logging.Logger instance.
    """
    configure_logging()
    logger = logging.getLogger(name)
    if not any(isinstance(active_filter, SecretScrubbingFilter) for active_filter in logger.filters):
        logger.addFilter(SecretScrubbingFilter())
    return logger
