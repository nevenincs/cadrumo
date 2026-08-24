"""Shared CLI error-emission boundary.

This module is the single funnel for translating exceptions raised
inside Typer callbacks into the structured CLI error contract — a
stable stderr payload (text or JSON) plus a stable :class:`~typer.Exit`
code drawn from the core error-category registry.

Two narrow boundary exceptions wrap unexpected failures so they reach
:func:`render_error_text` and
:func:`render_error_json` with a predictable shape:

- :exc:`CliValidationBoundaryError` wraps a leaked
  :exc:`~pydantic.ValidationError`.
- :exc:`CliUnexpectedBoundaryError` wraps any
  other non-control-flow exception.

A third type, :exc:`CliRefusedBoundaryError`, is
reserved for refusals emitted in JSON mode whose payload is intentionally
stderr-only.

The :func:`command_error_boundary` decorator wraps a callback so that
:class:`CadrumoError` instances are emitted via
:func:`_emit_error_and_exit`.
:func:`decorate_typer_app` walks a
:class:`~typer.Typer` tree and applies the error boundary to every graph-materialized command
and group callback (with an opt-out via ``skip_paths``).
:func:`error_boundary_under_test` toggles the
boundary off for tests that want to assert on the raised exception directly.
"""

from __future__ import annotations

import contextlib
import functools
import inspect
import io
import json
import logging
import sys
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Final, Never, Protocol, TypeGuard, cast, get_args

import click
import typer
from pydantic import BaseModel, ValidationError

from ...application.operator_actions import PreconditionVerdict
from ...core import FormerProductStateError
from ...core.click_context import argv_requests_json, json_output_requested
from ...core.errors import (
    ActiveProfilePointerError,
    CadrumoError,
    get_error_exit_code,
    get_registered_error_code,
    render_error_json,
    render_error_text,
)
from ...core.json_contract import Notice, ResolvedPreconditionAction
from ...core.redaction import redact_for_cli_output
from ...domain.user_profile import StoredProfileDriftError

_log = logging.getLogger(__name__)

_UNDER_TEST: ContextVar[bool] = ContextVar("cadrumo_cli_error_boundary_under_test", default=False)
#: Dotted identifier of the command whose callback is currently executing,
#: set by :func:`command_error_boundary` at entry so the error spine's
#: ``command`` field can name the failing command (byte-identical to the
#: ``command=`` its success envelope would emit). ``None`` before any command
#: resolves — an argv parse failure — so the field is honestly null there.
_ACTIVE_COMMAND_ID: ContextVar[str | None] = ContextVar("cadrumo_cli_active_command_id", default=None)
_WRAPPED_CALLBACKS: dict[int, Callable[..., object]] = {}


class _ReconfigurableTextIO(Protocol):
    """Structural type for a text stream that supports ``reconfigure``."""

    def reconfigure(self, *, encoding: str | None = None, errors: str | None = None) -> None:
        """Reconfigure the underlying text stream's encoding and error mode."""

    def write(self, s: str, /) -> int:
        """Write string ``s`` to the stream."""
        ...

    def flush(self) -> None:
        """Flush the write buffers of the stream."""
        ...


class CliValidationBoundaryError(CadrumoError):
    """Raised when a CLI callback leaks a :exc:`~pydantic.ValidationError`.

    The original exception is preserved on
    :attr:`CliValidationBoundaryError.original_exception` so
    downstream renderers and tests can inspect it without losing the
    typed pydantic detail.

    This class covers input-time validation failures (the operator passed
    an invalid argument or body).  It is distinct from
    :exc:`CliStoredDataValidationBoundaryError`,
    which handles schema drift on persisted records and legitimately suggests
    ``aeat config repair``.
    Suggesting ``aeat config repair`` here would be misleading: repair
    diagnoses local configuration state and cannot fix an application
    schema mismatch or an invalid CLI argument.

    **The message stays generic and the detail rides ``context``.** The
    per-field list is genuinely too noisy to read as a refusal sentence, which
    is why it was once withheld entirely --- but withholding it from the
    ENVELOPE too left "check the command's arguments" as the whole of what an
    operator was told, and that instruction is wrong precisely when the breached
    constraint is on a field they never supplied. A tax identifier read off a
    document is such a field: the operator's arguments are all correct and
    re-reading them discovers nothing. Splitting the two channels keeps the
    sentence readable and makes the failure diagnosable, which is the same split
    :exc:`CliOutboundPayloadBoundaryError` and
    :exc:`CliStoredDataValidationBoundaryError` already use.

    The context names the failing record, the field path and the rule broken,
    and never the value --- see :func:`internal_record_fault_context` for why
    that exclusion is load-bearing rather than incidental.

    Attributes:
        original_exception: The underlying :exc:`~pydantic.ValidationError`.
    """

    def __init__(self, error: ValidationError) -> None:
        """Wrap ``error`` in the structured CLI boundary contract.

        Args:
            error: The pydantic validation error raised inside the
                Typer callback.
        """
        super().__init__(
            translated_message="errors.refused.refused_cli_validation_boundary",
            context=internal_record_fault_context(error),
        )
        self.original_exception: ValidationError = error


class CliUnexpectedBoundaryError(CadrumoError):
    """Raised when a CLI callback leaks an unexpected exception.

    Used for any exception that is not :class:`CadrumoError`,
    :exc:`~pydantic.ValidationError`, or Typer/Click control flow. The
    original exception is preserved on
    :attr:`CliUnexpectedBoundaryError.original_exception`.

    Attributes:
        original_exception: The underlying exception raised by the
            callback.
    """

    def __init__(self, error: Exception) -> None:
        """Wrap ``error`` in the structured CLI boundary contract.

        Args:
            error: The unexpected exception raised inside the Typer
                callback.
        """
        # An unexpected exception is a code or environment fault, not a storage
        # repair instruction. The error envelope records an explicit
        # no-recovery outcome at emission time.
        super().__init__(
            translated_message="errors.internal.internal_cli_unexpected_boundary",
        )
        self.original_exception: Exception = error


class CliStoredDataValidationBoundaryError(CadrumoError):
    """Raised when a CLI callback loads stored profile data that fails validation.

    Distinct from
    :exc:`CliValidationBoundaryError` (which wraps
    input-time validation failures) so downstream handlers and tests can
    discriminate between malformed user input and drifted stored profile data.  The stored
    record was valid when it was written; schema evolution or an out-of-band
    edit caused the drift.

    The original exception is preserved on
    :attr:`CliStoredDataValidationBoundaryError.original_exception` so
    renderers and tests can inspect the typed pydantic detail.

    Attributes:
        original_exception: The underlying :exc:`~pydantic.ValidationError`
            raised while deserialising a stored record.
    """

    def __init__(self, error: ValidationError) -> None:
        """Wrap ``error`` in the stored-data validation boundary contract.

        Args:
            error: The pydantic validation error raised while loading a
                stored profile record.
        """
        super().__init__(
            translated_message="errors.storage.stored_data_validation_boundary",
        )
        self.original_exception: ValidationError = error


#: Ceiling on the number of field violations named in an internal-fault context.
#: A record failing every field would otherwise turn one refusal into a wall of
#: text; the first few name the record and the constraint, which is what makes
#: the report actionable.
_INTERNAL_FAULT_VIOLATION_LIMIT: Final[int] = 5


#: Pydantic error types whose ``msg`` is prose authored by the validator that
#: raised, rather than a sentence pydantic composed from the declared constraint.
#: Their text is not under this module's control and routinely quotes the value
#: that failed -- ``ValueError(f"tax identifier {value!r} must be ...")`` is the
#: ordinary way to write a domain validator, so the leak is the NORM on this
#: shape rather than an unlucky case.
_VALIDATOR_AUTHORED_MESSAGE_TYPES: Final[frozenset[str]] = frozenset({"value_error", "assertion_error"})


#: Stands in for a path component this module cannot prove is a declared field
#: name. Fixed text, never derived from the component, so it carries nothing.
_REDACTED_PATH_COMPONENT: Final[str] = "<key>"

#: Emitted where a violation has no path at all -- a model-level validator.
_ROOT_PATH: Final[str] = "<root>"


def _declared_field_names(record: type[BaseModel] | None) -> frozenset[str]:
    """Return every field name declared anywhere in *record*'s model tree.

    A flat SET rather than a positional walk of the annotation graph, and the
    imprecision is deliberate. The question this projection has to answer is
    "could this component be taxpayer data", and a string that a programmer
    declared as a field name somewhere in the record's own tree cannot be: it is
    a source identifier either way. Resolving which model each component belongs
    to would buy precision the guarantee does not need, at the cost of walking
    unions, generics and forward references correctly -- and getting that walk
    subtly wrong fails OPEN.

    The residual imprecision is that a mapping key which happens to equal a
    declared field name elsewhere in the tree is emitted. That is a key spelling
    a programmer's identifier, not a tax identifier, an amount or a name.
    """
    if record is None:
        return frozenset[str]()
    names: set[str] = set()
    seen: set[type] = set()

    def walk(model: object) -> None:
        if not (isinstance(model, type) and issubclass(model, BaseModel)) or model in seen:
            return
        seen.add(model)
        for name, field in model.model_fields.items():
            names.add(name)
            for nested in (field.annotation, *get_args(field.annotation)):
                walk(nested)
                for deeper in get_args(nested):
                    walk(deeper)

    walk(record)
    return frozenset(names)


def _violation_path(loc: tuple[object, ...], declared: frozenset[str]) -> str:
    """Return the failing path with anything unprovable replaced, never elided.

    Integer components are list indices and are emitted verbatim: a position is
    not data. String components are emitted only when *declared* confirms them as
    field names somewhere in the record's own tree.

    **Replaced rather than dropped**, so the path keeps its DEPTH. An elided
    component would make ``rows.0.n`` and ``rows.0.<key>.n`` read alike, which
    hides the presence of a mapping exactly where an engineer needs to see one.
    """
    if not loc:
        return _ROOT_PATH
    parts = [str(part) if isinstance(part, int) or str(part) in declared else _REDACTED_PATH_COMPONENT for part in loc]
    return ".".join(parts)


def _violation_rule(item: Mapping[str, object]) -> str:
    """Return the rule an error broke, with no text the validator authored.

    Pydantic's own messages are composed from the DECLARED constraint -- "String
    should have at most 9 characters", "Input should be a valid integer" -- and
    name the rule without the value, which is exactly the projection this module
    promises. A ``value_error`` or ``assertion_error`` message is different in
    kind: it is whatever a domain validator chose to write, and this module
    cannot constrain it.

    For those, the rule is reported as the pydantic error type plus the class of
    the exception that raised. Both are identifiers from the source tree, so
    neither can carry taxpayer data, and together they say which contract failed
    -- which is what makes the fault reportable. The prose is dropped rather than
    trimmed or pattern-scrubbed: a redactor over free text is a guess about what
    is sensitive, and the whole point of this projection is that it never has to
    make one.
    """
    kind = str(item.get("type", "validation_error"))
    if kind not in _VALIDATOR_AUTHORED_MESSAGE_TYPES:
        return str(item.get("msg", "validation error"))
    context = item.get("ctx")
    typed_context = cast(Mapping[str, object], context) if isinstance(context, Mapping) else None
    raised = typed_context.get("error") if typed_context is not None else None
    named = type(raised).__name__ if raised is not None else None
    return f"{kind} ({named})" if named else kind


def internal_record_fault_context(
    error: ValidationError,
    *,
    record: type[BaseModel] | None = None,
) -> dict[str, object]:
    """Summarise ``error`` as operator-safe context naming the failing contract.

    The generic validation boundary discards the pydantic detail entirely and
    writes it only to the error log, so an operator meeting an internal fault is
    told to check arguments that are correct and has no way to discover the real
    cause. This projects the same detail into the error envelope's ``context``,
    which both the JSON and text renderers already emit.

    Carries the failing model's name and, per violation, the field path and the
    rule that was broken -- never ``input``, and never a message a domain
    validator authored. A validated record on this path holds taxpayer data, and
    the value that breached a constraint is exactly the value that must not
    cross an output boundary.

    **Withholding ``input`` alone did not achieve that**, and the docstring
    asserted it for as long as it did not. A ``value_error`` carries the value
    inside its own message text, because formatting the offending value into the
    refusal is how domain validators are normally written -- so the guarantee was
    defeated by the commonest validator shape rather than by an exotic one. The
    message is now withheld for exactly those types and the rule reported as the
    error type plus the raising exception's class.

    A withheld message is COUNTED in ``violation_messages_withheld`` rather than
    dropped silently, so an engineer reading a thin report can tell the detail
    was suppressed on purpose and go to the error log, which still holds the
    unredacted ``errors()`` payload.

    **The path is projected under the same rule as the message**, because a
    violation's ``loc`` reproduces mapping KEYS as well as field names -- a
    record holding a mapping keyed by a tax identifier puts that identifier in
    the path, and this docstring once called the path non-sensitive.

    A :exc:`~pydantic.ValidationError` carries only the failing model's NAME, so
    a component cannot be classified from the error alone; *record* is how a
    caller that knows the model supplies the missing half. Every string
    component is replaced unless that model's tree declares it as a field name.
    **Without *record* every string component is replaced**, which is a real loss
    of detail and the deliberate direction to fail in: a projection that guesses
    which strings are safe is the guess this whole helper exists to avoid, and
    ``failing_record`` plus the broken rule still identify the contract. Pattern
    matching the component against known identifier shapes was rejected for the
    same reason it was rejected for the message.
    """
    violations = error.errors()
    reported = violations[:_INTERNAL_FAULT_VIOLATION_LIMIT]
    declared = _declared_field_names(record)
    named = tuple(f"{_violation_path(tuple(item['loc']), declared)}: {_violation_rule(item)}" for item in reported)
    withheld = sum(1 for item in reported if str(item.get("type", "")) in _VALIDATOR_AUTHORED_MESSAGE_TYPES)
    context: dict[str, object] = {
        "failing_record": error.title,
        "violation_count": len(violations),
        "violations": "; ".join(named),
    }
    if withheld:
        context["violation_messages_withheld"] = withheld
    if len(violations) > _INTERNAL_FAULT_VIOLATION_LIMIT:
        context["violations_omitted"] = len(violations) - _INTERNAL_FAULT_VIOLATION_LIMIT
    return context


class CliOutboundPayloadBoundaryError(CadrumoError):
    """Raised when the application builds an outbound payload that fails validation.

    The third member of this family, and the one neither sibling covered.
    :exc:`CliValidationBoundaryError` is scoped to input-time failures -- the
    operator passed an invalid argument or body -- and
    :exc:`CliStoredDataValidationBoundaryError` to drift on a record that was
    valid when written. This case is neither: the operator's input was fine and
    nothing was loaded, but a record the application ITSELF constructed on the
    way out violated its own contract. That is a program defect, so it is
    INTERNAL rather than REFUSED.

    Classifying it as either sibling misdirects the operator. The observed case
    was a Modelo 100 reconcile diverging on several casillas: the per-diff
    grounding overflowed a bucket-event payload field, and the operator was told
    "the command input failed validation, check the command's arguments" about
    arguments that were entirely correct, on the modelo most likely to trigger
    it.

    Attributes:
        original_exception: The underlying :exc:`~pydantic.ValidationError`
            raised while constructing the outbound record.
    """

    def __init__(self, error: ValidationError, *, record: type[BaseModel] | None = None) -> None:
        """Wrap ``error`` in the outbound-payload boundary contract.

        Args:
            error: The pydantic validation error raised while constructing a
                payload the application emits or persists.
            record: The model being validated, when the raising site knows it.
                Supplying it is what lets the fault name its field path: a
                :exc:`~pydantic.ValidationError` carries only the model's name,
                so without the class every path component is redacted rather
                than guessed at. Optional because several raise sites guard a
                block in which more than one model is validated and genuinely
                cannot say which one failed.
        """
        super().__init__(
            translated_message="errors.internal.cli_outbound_payload_boundary",
            context=internal_record_fault_context(error, record=record),
        )
        self.original_exception: ValidationError = error


class CliCommandGroupUnavailableError(CadrumoError):
    """Raised when a command group cannot be imported and the cause is not an optional extra.

    A command group's module is imported lazily, the first time an operator
    dispatches into that subtree. When the import fails with a
    :exc:`ModuleNotFoundError` naming a package outside the
    :data:`~core.OPTIONAL_EXTRAS` registry, the missing package is a *required*
    dependency: the installation is incomplete, not merely un-extended.

    Degrading that case to an unavailable-command placeholder would turn a hard
    dependency failure into an invisible capability loss — the whole subtree
    would answer every invocation with a plausible refusal while naming no
    cause. This refusal names the module, the group it broke, and the
    reinstall remedy instead.

    Attributes:
        group: The command-group name whose subtree failed to load.
        module: The missing required module the import named.
    """

    def __init__(self, *, group: str, module: str) -> None:
        """Build the refusal for ``group`` failing on required ``module``.

        Args:
            group: The command-group name whose subtree failed to load.
            module: The dotted module name the failed import named.
        """
        super().__init__(
            translated_message="errors.fail.fail_cli_command_group_unavailable",
            context={"group": group, "module": module},
        )
        self.group = group
        self.module = module


class CliRefusedBoundaryError(CadrumoError):
    """Raised when JSON-mode CLI must refuse a request with stderr-only output.

    Refusals are emitted as plain stderr text even in JSON mode because
    the structured payload contract intentionally does not expose them
    on stdout.
    """


class CliTuiNotImplementedError(CadrumoError):
    """Raised when an explicit TUI request has no enrolled command route."""

    def __init__(self, *, command: str) -> None:
        super().__init__(
            translated_message="errors.refused.refused_tui_not_implemented",
            context={"command": command},
        )


def command_error_boundary[**P, R](callback: Callable[P, R]) -> Callable[P, R]:
    """Wrap ``callback`` so :class:`CadrumoError` emits the structured stderr form.

    The wrapper catches four exception families and routes them to
    :func:`_emit_error_and_exit`:

    - :exc:`StoredProfileDriftError` is
      wrapped in
      :exc:`CliStoredDataValidationBoundaryError`
      so operators see a repair-oriented message distinct from input-time
      validation failures. Checked before the broad
      :class:`CadrumoError` arm by typed exception, not field-path
      introspection.
    - :class:`CadrumoError` is forwarded verbatim.
    - :exc:`~pydantic.ValidationError` is wrapped in
      :exc:`CliValidationBoundaryError`.
    - Any other non-control-flow exception is wrapped in
      :exc:`CliUnexpectedBoundaryError`.

    Typer/Click control-flow exceptions (e.g. :exc:`~click.exceptions.Exit`,
    :exc:`~click.Abort`, :exc:`~typer.Exit`) propagate untouched so the
    framework can act on them. When
    :func:`error_boundary_under_test` is active
    the original exception is re-raised instead of being emitted.

    Calls are memoised by callback identity so wrapping the same
    callback twice returns the original wrapper.

    Args:
        callback: Typer callback to wrap.

    Returns:
        Wrapped callback with the original signature preserved.
    """
    existing = _WRAPPED_CALLBACKS.get(id(callback))
    if existing is not None and _is_memoised_wrapper(existing):
        # Safe: _WRAPPED_CALLBACKS stores only the _wrapped closure produced
        # by THIS function from a callback[P, R] argument. The memo key is
        # id(callback), which uniquely identifies the object at this call site.
        # Both the forward and reverse entries are written atomically at the end
        # of this function, so a hit guarantees the stored callable has exactly
        # the same ParamSpec P and return type R as callback. The widening to
        # Callable[..., object] in the dict value type is the only escape hatch;
        # it cannot be eliminated without making _WRAPPED_CALLBACKS generic over
        # P and R, which the stdlib dict does not support.
        # CAST-RATIONALE-ERRORS-MEMOISED-WRAPPER (future: replace with generic ClassVar alias)
        return cast(Callable[P, R], existing)  # CAST-RATIONALE-ERRORS-MEMOISED-WRAPPER

    @functools.wraps(callback)
    def _wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        token = _ACTIVE_COMMAND_ID.set(_resolve_active_command_id(*args, *kwargs.values()))
        try:
            return callback(*args, **kwargs)
        except Exception as error:
            # Typer/Click control flow (Exit, Abort, BadParameter) propagates
            # untouched so the framework can render it; the under-test override
            # re-raises the original so tests can assert on the typed exception.
            # Everything else routes through the ordered specificity dispatch.
            if _is_click_control_flow(error):
                raise
            if _UNDER_TEST.get():
                raise
            _emit_error_and_exit(_project_boundary_error(error, callback))
        finally:
            _ACTIVE_COMMAND_ID.reset(token)

    _WRAPPED_CALLBACKS[id(callback)] = _wrapped
    _WRAPPED_CALLBACKS[id(_wrapped)] = _wrapped
    return _wrapped


def decorate_typer_app(
    app: typer.Typer,
    *,
    skip_paths: Sequence[tuple[str, ...]] = (),
) -> None:
    """Apply :func:`command_error_boundary` across an entire Typer tree.

    Walks ``app`` recursively and wraps every command and group callback
    that is a plain function. Sub-apps are descended into.

    Args:
        app: Root or nested :class:`~typer.Typer` app to decorate.
        skip_paths: Fully-qualified command paths (as tuples of name
            segments) that must remain undecorated. Useful for callbacks
            that intentionally manage their own error reporting.
    """
    skip_set = set(skip_paths)
    _decorate_typer_node(app, prefix=(), skip_paths=skip_set)


def write_stderr(text: str, *, stream: io.TextIOBase | None = None) -> None:
    """Write ``text`` to stderr with UTF-8-safe fallback behaviour.

    On Windows consoles whose default encoding is cp1252, raw writes of
    non-ASCII characters raise ``UnicodeEncodeError``. This helper
    first attempts to reconfigure the stream to UTF-8 via
    :class:`_ReconfigurableTextIO`; on encoding
    failure it falls back to the underlying byte buffer with
    ``errors="replace"``, and finally to an ASCII-safe replacement string.

    Args:
        text: Text payload to emit.
        stream: Optional target stream to write to instead of
            :data:`~sys.stderr`. Primarily useful in tests.
    """
    target = sys.stderr if stream is None else stream
    redacted_text = redact_for_cli_output(text)
    if _supports_reconfigure(target):
        with contextlib.suppress(Exception):
            target.reconfigure(encoding="utf-8", errors="replace")
    try:
        target.write(redacted_text)
        target.flush()
        return
    except UnicodeEncodeError:
        buffer = getattr(target, "buffer", None)
        if buffer is not None:
            buffer.write(redacted_text.encode("utf-8", errors="replace"))
            with contextlib.suppress(Exception):
                buffer.flush()
            return
        target.write(redacted_text.encode("ascii", errors="replace").decode("ascii"))
        target.flush()


def active_profile_label_for_error() -> str | None:
    """Return the active-profile label for the error-document spine, best-effort.

    The error boundary is the one place that must never be disrupted by
    identity resolution: a failure resolving the active-profile label must
    not mask the original error being reported. Delegates to the CLI
    transport's :func:`_common.active_profile_label` (the same plaintext
    manifest-label read the success path uses, never the redacted UUID)
    and collapses any failure to ``None`` so the error still emits with a
    null identity anchor. The import is function-local to avoid a module
    cycle with :mod:`_common`, which imports this module.
    """
    try:
        from ._common import active_profile_label

        return active_profile_label()
    except Exception:  # identity resolution must never break error emit
        _log.debug("cli error boundary: active-profile label resolution failed", exc_info=True)
        return None


def sandbox_notice_for_error() -> Notice | None:
    """Return the sandbox-active :class:`Notice` for an error document, best-effort.

    The success envelope carries this indicator on both its JSON ``notices``
    channel and its text banner line, so without it here a failure inside a
    discardable sandbox bucket renders byte-identically to the same failure
    against the operator's real profile. Delegates to the one resolver the
    success path uses
    (:func:`~cadrumo.application.operator_output.sandbox_notice_for_active_bucket`)
    and collapses any failure to ``None`` for the same reason
    :func:`active_profile_label_for_error` does: resolving a purely-advisory
    indicator must never mask the original error being reported.
    """
    try:
        from ...application.operator_output import sandbox_notice_for_active_bucket

        return sandbox_notice_for_active_bucket()
    except Exception:  # the sandbox indicator must never break error emit
        _log.debug("cli error boundary: sandbox notice resolution failed", exc_info=True)
        return None


def _render_precondition_action_text(
    text: str,
    *,
    command: str | None,
    action: ResolvedPreconditionAction,
) -> str:
    """Append the canonical action DTO to text output without inventing prose.

    Text mode remains a derived view of the same strict wire record passed to
    :func:`render_error_json`.  The field names below are the
    :class:`ResolvedPreconditionAction` schema names, not independently authored
    recovery labels, and nested values use deterministic JSON so condition
    evidence and binding provenance cannot be flattened into ambiguous prose.
    """
    lines = [text.rstrip("\n")]
    if command is not None:
        lines.append(f"  command: {command}")
    action_document = action.model_dump(mode="json")
    for field_name in (
        "failed_condition_id",
        "evidence",
        "action",
        "argument_bindings",
        "missing_argument_names",
        "conditionality",
        "no_recovery_outcome",
    ):
        value = json.dumps(
            action_document[field_name],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        lines.append(f"  action.{field_name}: {value}")
    return "\n".join(lines) + "\n"


def render_error_payload(
    error: BaseException,
    *,
    as_json: bool,
    command: str | None = None,
    action: ResolvedPreconditionAction | None = None,
) -> str:
    """Render ``error`` to its stderr payload, carrying typed action data.

    The single renderer both terminal funnels use — the command boundary's
    :func:`_emit_error_and_exit` and the process boundary's
    :func:`_terminal_errors._emit_crash` — so the two cannot drift on which
    spine fields an error document carries. In JSON mode the sandbox
    :class:`Notice` rides the ``notices`` channel; in text mode the same notice
    renders through
    :func:`~cadrumo.application.operator_output.sandbox_banner_line`, the same
    formatter the text-mode success path uses, so the banner is byte-identical
    across success and failure. A supplied ``action`` is the already-resolved
    application verdict projection: JSON places it in the canonical error
    member, while text serializes that exact DTO beneath the localized error
    line without reconstructing a command or recovery sentence.
    """
    notice = sandbox_notice_for_error()
    from ._profile_authentication_notice import drain_profile_authentication_notices

    authentication_notices = drain_profile_authentication_notices()
    if as_json:
        return render_error_json(
            error,
            action=action,
            active_profile=active_profile_label_for_error(),
            command=command,
            notices=(*(() if notice is None else (notice,)), *authentication_notices),
        )
    text = render_error_text(error)
    if action is not None:
        text = _render_precondition_action_text(text, command=command, action=action)
    if authentication_notices:
        from ._common import notice_lines

        text = "\n".join((*notice_lines(authentication_notices), text))
    if notice is None:
        return text
    from ...application.operator_output import sandbox_banner_line

    return f"{sandbox_banner_line(notice)}\n{text}"


def _command_identifier_from_path(command_path: str) -> str | None:
    """Map a click ``command_path`` to the dotted envelope command identifier.

    The click command *path* uses the root prog token plus hyphenated CLI
    tokens (``aeat config repair reset-progress``); the envelope ``command``
    identifier uses dotted, underscored tokens (``config.repair.reset_progress``).
    Drop the root
    prog token, join the rest with ``.``, map ``-`` to ``_`` per token — the
    inverse of that convention, so a command's error envelope names it
    identically to the ``command=`` its success envelope emits, and the two can
    never disagree. ``None`` for the bare root (no subcommand).
    """
    segments = command_path.split()[1:]
    if not segments:
        return None
    return ".".join(segment.replace("-", "_") for segment in segments)


def _active_command_identifier() -> str | None:
    """Return the dotted identifier of the command currently executing, or ``None``.

    Read from the :data:`_ACTIVE_COMMAND_ID` context var, which
    :func:`command_error_boundary` sets from the executing command's injected
    :class:`click.Context` at callback entry (click's global context stack is
    not populated under the Typer/cached-tree invocation, so the injected ctx
    parameter is the reliable source). ``None`` when no command has resolved —
    an argv parse failure raised before any command callback runs.
    """
    return _ACTIVE_COMMAND_ID.get()


def _resolve_active_command_id(*values: object) -> str | None:
    """Return the dotted command identifier from the callback's injected Context.

    Name the executing command on the error spine: Typer injects the Context as
    a callback parameter, so scan the positional and keyword argument ``values``
    for the first with a string ``command_path`` and map it to the dotted
    envelope identifier (the global click context stack is not populated under
    this invocation). Duck-type on ``command_path`` rather than
    ``isinstance(click.Context)`` — the vendored Typer Context is not a
    guaranteed upstream subclass. ``None`` before any command resolves (an argv
    parse failure), so the spine's ``command`` field is honestly null there.
    """
    command_path = next(
        (path for value in values if isinstance(path := getattr(value, "command_path", None), str)),
        None,
    )
    return _command_identifier_from_path(command_path) if command_path is not None else None


def _boundary_no_recovery_verdict(error: CadrumoError) -> PreconditionVerdict | None:
    """Classify a boundary failure that arrived without a typed projection."""
    from ...application.cli_exception_preconditions import (
        CliExceptionPrecondition,
        cli_exception_no_recovery_verdict,
    )
    from ._config._errors import ConfigBoundaryError
    from ._tty import NonTtyRefusedError

    if isinstance(error, CliValidationBoundaryError):
        condition = CliExceptionPrecondition.VALIDATION_BOUNDARY
    elif isinstance(error, CliUnexpectedBoundaryError):
        condition = CliExceptionPrecondition.UNEXPECTED_BOUNDARY
    elif isinstance(error, CliStoredDataValidationBoundaryError):
        condition = CliExceptionPrecondition.STORED_DATA_VALID
    elif isinstance(error, CliCommandGroupUnavailableError):
        condition = CliExceptionPrecondition.COMMAND_GROUP_AVAILABLE
    elif isinstance(error, ConfigBoundaryError):
        condition = CliExceptionPrecondition.CONFIG_BOUNDARY
    elif isinstance(error, NonTtyRefusedError):
        condition = CliExceptionPrecondition.STDIN_INTERACTIVE
    elif isinstance(error, CliRefusedBoundaryError):
        condition = CliExceptionPrecondition.REFUSAL_RETRIED
    else:
        return None
    return cli_exception_no_recovery_verdict(
        condition,
        facts={"boundary_error_type": type(error).__name__},
    )


def boundary_no_recovery_verdict(error: CadrumoError) -> PreconditionVerdict | None:
    """Return the canonical generic boundary outcome for terminal transport."""
    return _boundary_no_recovery_verdict(error)


def _emit_error_and_exit(error: CadrumoError) -> Never:
    """Render ``error`` to stderr and terminate with its registered exit code.

    Selects the JSON or text renderer based on whether the active
    callback opted into JSON output via
    :func:`json_output_requested`, writes the payload
    through :func:`write_stderr`, and raises
    :class:`~typer.Exit` with the category-mapped exit code. In JSON mode
    the shared-spine ``active_profile`` identity anchor and the dotted
    ``command`` identifier are resolved best-effort and injected into the
    error document; the sandbox indicator rides both output modes via
    :func:`render_error_payload`.
    """
    from ._common import cli_policy_refusal_projection, project_cli_policy_refusal

    projection = cli_policy_refusal_projection(error)
    if projection is None:
        verdict = _boundary_no_recovery_verdict(error)
        if verdict is not None:
            projection = project_cli_policy_refusal(requested_leaf=None, verdict=verdict)
    command = _active_command_identifier()
    action: ResolvedPreconditionAction | None = None
    if projection is not None:
        action = projection.precondition_action
        if projection.requested_leaf is not None:
            command = projection.requested_leaf.subject_leaf_key

    code = get_registered_error_code(error)
    payload = render_error_payload(
        error,
        as_json=json_output_requested() or argv_requests_json(sys.argv[1:]),
        command=command,
        action=action,
    )
    write_stderr(payload)
    raise typer.Exit(code=get_error_exit_code(code.category)) from error


@contextmanager
def error_boundary_under_test() -> Generator[None]:
    """Temporarily force :func:`command_error_boundary` to re-raise originals.

    Tests that need to assert on the raised exception type rather than
    the rendered stderr payload should wrap their invocation in this
    context manager. The override is scoped to the active context via
    :class:`~contextvars.ContextVar`, so concurrent callbacks are
    unaffected.

    Yields:
        ``None``. The context's only purpose is the side effect on the internal
        flag.
    """
    token: Token[bool] = _UNDER_TEST.set(True)
    try:
        yield
    finally:
        _UNDER_TEST.reset(token)


def _decorate_typer_node(
    app: typer.Typer,
    *,
    prefix: tuple[str, ...],
    skip_paths: set[tuple[str, ...]],
) -> None:
    """Recursively decorate every command/group callback under ``app``."""
    registered_callback = app.registered_callback
    if (
        registered_callback is not None
        and _is_wrap_candidate(registered_callback.callback)
        and prefix not in skip_paths
    ):
        registered_callback.callback = command_error_boundary(registered_callback.callback)
    for command in app.registered_commands:
        name = command.name or _callback_name(command.callback)
        path = (*prefix, name)
        if _is_wrap_candidate(command.callback) and path not in skip_paths:
            command.callback = command_error_boundary(command.callback)
    for group in app.registered_groups:
        name = group.name or _callback_name(group.callback)
        path = (*prefix, name)
        if _is_wrap_candidate(group.callback) and path not in skip_paths:
            group.callback = command_error_boundary(group.callback)
        if group.typer_instance is not None:
            _decorate_typer_node(group.typer_instance, prefix=path, skip_paths=skip_paths)


def _callback_name(callback: Callable[..., object] | None) -> str:
    """Return a stable name for a Typer callback, even if it's a callable class."""
    if callback is None:
        return "<unknown>"
    if inspect.isfunction(callback):
        return callback.__name__
    class_name = callback.__class__.__name__
    return class_name if isinstance(class_name, str) else "<unknown>"


def _is_memoised_wrapper(obj: object) -> TypeGuard[Callable[..., object]]:
    """Narrow ``obj`` to a callable produced by the command error boundary.

    The callable must have been produced by
    :func:`command_error_boundary`.

    A hit in ``_WRAPPED_CALLBACKS`` guarantees the stored value is the ``_wrapped``
    closure returned by this module; all such closures satisfy ``Callable[..., object]``.
    The full ``Callable[P, R]`` refinement is recovered at the call site via a
    documented cast (CAST-RATIONALE-ERRORS-MEMOISED-WRAPPER).
    """
    return callable(obj)


def _is_wrap_candidate(callback: object) -> TypeGuard[Callable[..., object]]:
    """Narrow ``callback`` to a plain function suitable for wrapping."""
    return inspect.isfunction(callback)


def _supports_reconfigure(stream: object) -> TypeGuard[_ReconfigurableTextIO]:
    """Narrow ``stream`` to a text stream that exposes ``reconfigure``."""
    return hasattr(stream, "reconfigure")


def _unwrap_cadrumo_error(error: BaseException) -> CadrumoError | None:
    """Return the typed :class:`CadrumoError` wrapped inside ``error``, if any.

    A library boundary (notably SQLAlchemy) can catch an
    :class:`CadrumoError` raised inside its own machinery and
    re-raise it wrapped in a library-specific exception. The typed refusal is
    then reachable only through the ``orig`` attribute SQLAlchemy sets, or
    through the standard ``__cause__`` / ``__context__`` chain. This helper walks
    both so the refusal can be forwarded verbatim rather than mis-reported as an
    unexpected internal error.

    The walk is depth-bounded to avoid pathological cycles.
    """
    seen: set[int] = set()
    current: BaseException | None = error
    depth = 0
    while current is not None and depth < 16:
        if isinstance(current, CadrumoError):
            return current
        if id(current) in seen:
            return None
        seen.add(id(current))
        depth += 1
        nxt = getattr(current, "orig", None)
        if not isinstance(nxt, BaseException):
            nxt = current.__cause__ or current.__context__
        current = nxt
    return None


# Typer vendors its own Click fork; ``typer.BadParameter`` and friends descend
# from ``typer._click.exceptions.ClickException`` rather than the upstream
# ``click.ClickException``. Derive the vendored base from ``typer.BadParameter``'s
# MRO so both hierarchies are recognised without a brittle private-module import.
_typer_click_exc_raw = next(base for base in typer.BadParameter.__mro__ if base.__name__ == "ClickException")
assert issubclass(_typer_click_exc_raw, BaseException)
_TYPER_CLICK_EXCEPTION: type[BaseException] = _typer_click_exc_raw
_CONTROL_FLOW_EXCEPTIONS: tuple[type[BaseException], ...] = (
    click.ClickException,
    click.exceptions.Exit,
    click.Abort,
    typer.Exit,
    _TYPER_CLICK_EXCEPTION,
)


def _is_click_control_flow(error: Exception) -> bool:
    """Return ``True`` when ``error`` is Typer/Click control flow, not a bug.

    Recognises :exc:`~click.ClickException`, :exc:`~click.exceptions.Exit`,
    :exc:`~click.Abort`, and :exc:`~typer.Exit`. Typer vendors its own Click
    fork (``typer._click.exceptions``), so ``typer.BadParameter`` raised by a
    ``_bad(...)`` refusal is NOT an instance of the upstream
    :exc:`~click.ClickException`; recognise the vendored hierarchy too so an
    instructive operator refusal is re-raised for Click/CliRunner to render
    rather than mis-classified as an unexpected internal error.
    """
    return isinstance(error, _CONTROL_FLOW_EXCEPTIONS)


_BoundaryProjection = Callable[[Exception, Callable[..., object]], CadrumoError]


def _project_stored_data_drift(error: Exception, callback: Callable[..., object]) -> CadrumoError:
    """Discriminate stored-data drift from input-time validation failures.

    A schema mismatch on a persisted profile record and an invalid CLI argument
    both originate from a pydantic ``ValidationError`` but the operator-facing
    messages and recovery paths differ, so the drift is wrapped in the typed CLI
    boundary rather than emitted as the raw domain error code.
    """
    assert isinstance(error, StoredProfileDriftError)
    return CliStoredDataValidationBoundaryError(error.original_exception)


def _project_former_product_state(error: Exception, callback: Callable[..., object]) -> CadrumoError:
    """Emit a former-product-state refusal as stderr-only output."""
    from ...application.profile_preconditions import FormerProductDetectionScope, former_product_state_verdict
    from ._common import attach_cli_policy_verdict

    return attach_cli_policy_verdict(
        CliRefusedBoundaryError(str(error)),
        verdict=former_product_state_verdict(FormerProductDetectionScope.STARTUP),
    )


def _project_cadrumo_error(error: Exception, callback: Callable[..., object]) -> CadrumoError:
    """Forward a typed error, attaching boundary-owned terminal policy when proven."""
    assert isinstance(error, CadrumoError)
    from ...application.cli_exception_preconditions import (
        cli_exception_envelope_view,
        nested_terminal_precondition_verdict,
    )
    from ._common import attach_cli_policy_verdict

    if isinstance(error, ActiveProfilePointerError):
        verdict = _active_profile_pointer_error_verdict(error)
        if verdict is not None:
            return attach_cli_policy_verdict(error, verdict=verdict)
    storage_verdict = _storage_session_failure_verdict(error)
    if storage_verdict is not None:
        return attach_cli_policy_verdict(error, verdict=storage_verdict)
    verdict = nested_terminal_precondition_verdict(error)
    view = cli_exception_envelope_view(error)
    assert isinstance(view, CadrumoError)
    return view if verdict is None else attach_cli_policy_verdict(view, verdict=verdict)


def _active_profile_pointer_error_verdict(error: ActiveProfilePointerError) -> PreconditionVerdict | None:
    """Project the core pointer-corruption facts through application action policy."""
    context = error.context
    if not isinstance(context, Mapping):
        return None
    path = context.get("path")
    if (
        not isinstance(path, str)
        or context.get("pointer_corrupt") is not True
        or context.get("root_fallback_refused") is not True
    ):
        return None
    from ...application.operator_actions import corrupt_active_profile_pointer_verdict

    return corrupt_active_profile_pointer_verdict(path=path)


_STORAGE_SESSION_NO_ACTIONS: Final[
    Mapping[str, tuple["CliExceptionPrecondition", Mapping[str, str | bool]]]
] = {
    "REFUSED_STORAGE_MASTER_KEY_NO_ACTIVE_SESSION": (
        CliExceptionPrecondition.ACTIVE_BUCKET_SESSION_AVAILABLE,
        {"active_bucket_session_available": False},
    ),
    "REFUSED_STORAGE_SESSION_EXPIRED": (
        CliExceptionPrecondition.BUCKET_SESSION_FRESH,
        {"active_session_fresh": False, "session_expired": True},
    ),
    "REFUSED_STORAGE_BUCKET_NO_ACTIVE": (
        CliExceptionPrecondition.ACTIVE_BUCKET_SELECTED,
        {"active_bucket_selected": False},
    ),
    "AUTH_STORAGE_MASTER_KEY_UNAVAILABLE": (
        CliExceptionPrecondition.RESUMED_SESSION_KEK_MATERIAL_AVAILABLE,
        {"resumed_profile_session": True, "resumed_session_kek_material_available": False},
    ),
    "AUTH_STORAGE_MASTER_KEY_MATERIAL_MISSING": (
        CliExceptionPrecondition.MASTER_KEY_MATERIAL_AVAILABLE,
        {"active_bucket_selected": True, "master_key_material_available": False},
    ),
    "LOCKED_STORAGE_BUCKET_SESSION": (
        CliExceptionPrecondition.BUCKET_SESSION_UNLOCKED,
        {"bucket_session_unlocked": False},
    ),
}


def _storage_session_failure_verdict(error: CadrumoError) -> PreconditionVerdict | None:
    """Project S70 storage observations without letting adapters author actions.

    Only absence and idle expiry establish a real profile-session refusal.  A
    login action is therefore valid only when the CLI can resolve the public
    profile label the catalogue requires.  The remaining storage observations
    are deliberately terminal, fact-only operator decisions.
    """
    code = get_registered_error_code(error).code
    from ...application.cli_exception_preconditions import (
        CliExceptionPrecondition,
        cli_exception_no_recovery_verdict,
    )

    if code in {
        "REFUSED_STORAGE_MASTER_KEY_NO_ACTIVE_SESSION",
        "REFUSED_STORAGE_SESSION_EXPIRED",
    }:
        profile_name = active_profile_label_for_error()
        if profile_name is not None:
            from ...application.profile_preconditions import profile_session_failure_verdict
            from ...core import ProfileSessionRefusalReason

            reason = (
                ProfileSessionRefusalReason.ABSENT
                if code == "REFUSED_STORAGE_MASTER_KEY_NO_ACTIVE_SESSION"
                else ProfileSessionRefusalReason.EXPIRED_IDLE
            )
            return profile_session_failure_verdict(reason, profile_name=profile_name)

    no_action = _STORAGE_SESSION_NO_ACTIONS.get(code)
    if no_action is None:
        return None
    condition, facts = no_action
    return cli_exception_no_recovery_verdict(
        condition,
        facts=facts,
    )


def _project_validation_error(error: Exception, callback: Callable[..., object]) -> CadrumoError:
    """Log the pydantic detail, then wrap the input-time validation failure.

    The wrapped :class:`CliValidationBoundaryError` keeps the refusal SENTENCE
    free of the per-field error list, which is too noisy to read as prose, while
    carrying the failing record, field path and broken rule on the envelope's
    ``context``. The log line stays: it holds the raw ``errors()`` payload,
    including the input values the envelope deliberately withholds, which is
    what an engineer triaging a failing surface or fixture needs.
    """
    assert isinstance(error, ValidationError)
    _log.error(
        "command_error_boundary: pydantic ValidationError in %s: %s",
        getattr(callback, "__name__", repr(callback)),
        error.errors(),
    )
    boundary = CliValidationBoundaryError(error)
    from ...application.cli_exception_preconditions import nested_terminal_precondition_verdict
    from ._common import attach_cli_policy_verdict

    verdict = nested_terminal_precondition_verdict(error)
    if verdict is None:
        return boundary
    return attach_cli_policy_verdict(boundary, verdict=verdict)


#: Exception-family projections walked in DECLARATION ORDER by
#: :func:`_project_boundary_error` — order IS specificity, mirroring the former
#: ``except`` ladder exactly: the stored-drift and former-product refusals are
#: matched before the broad :class:`CadrumoError` arm, and
#: :exc:`~pydantic.ValidationError` before the unexpected fallback.
_ERROR_PROJECTIONS: tuple[tuple[type[Exception], _BoundaryProjection], ...] = (
    (StoredProfileDriftError, _project_stored_data_drift),
    (FormerProductStateError, _project_former_product_state),
    (CadrumoError, _project_cadrumo_error),
    (ValidationError, _project_validation_error),
)


def _project_unexpected(error: Exception, callback: Callable[..., object]) -> CadrumoError:
    """Project an unexpected exception: unwrap a wrapped refusal, else internal error.

    SQLAlchemy wraps an exception raised inside bind-param processing (e.g.
    ``NoActiveBucketSessionError`` raised by an encrypted-column codec when no
    session is unlocked) into a ``StatementError``. The wrapped cause is a typed
    :class:`CadrumoError` carrying a clean operator refusal. Unwrap it and forward
    the refusal verbatim — otherwise the no-session refusal is mis-classified as
    an unexpected internal error and a full traceback is written to the log file,
    where ``aeat config repair logs`` later echoes it back at the operator as if
    it were a live crash.
    """
    wrapped = _unwrap_cadrumo_error(error)
    if wrapped is not None:
        return _project_cadrumo_error(wrapped, callback)
    _log.error(
        "command_error_boundary: unexpected exception in %s",
        getattr(callback, "__name__", repr(callback)),
        exc_info=True,
    )
    return CliUnexpectedBoundaryError(error)


def _project_boundary_error(error: Exception, callback: Callable[..., object]) -> CadrumoError:
    """Map a boundary exception to the :class:`CadrumoError` to emit.

    Walks :data:`_ERROR_PROJECTIONS` in declaration order (order = specificity),
    falling back to :func:`_project_unexpected`. Control-flow re-raise and the
    under-test re-raise are applied by the caller before this runs, so neither
    reaches the table.
    """
    for exc_type, project in _ERROR_PROJECTIONS:
        if isinstance(error, exc_type):
            return project(error, callback)
    return _project_unexpected(error, callback)


def project_cli_boundary_error(error: Exception, callback: Callable[..., object]) -> CadrumoError:
    """Project an escaped exception without duplicating terminal crash logging."""
    for exc_type, project in _ERROR_PROJECTIONS:
        if isinstance(error, exc_type):
            return project(error, callback)
    wrapped = _unwrap_cadrumo_error(error)
    return _project_cadrumo_error(wrapped, callback) if wrapped is not None else CliUnexpectedBoundaryError(error)


__all__ = [
    "CliCommandGroupUnavailableError",
    "CliOutboundPayloadBoundaryError",
    "CliRefusedBoundaryError",
    "CliStoredDataValidationBoundaryError",
    "CliValidationBoundaryError",
    "boundary_no_recovery_verdict",
    "decorate_typer_app",
    "error_boundary_under_test",
    "internal_record_fault_context",
    "project_cli_boundary_error",
    "write_stderr",
]
