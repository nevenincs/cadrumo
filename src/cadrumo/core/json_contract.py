"""Shared primitives for the CLI's strict ``--json`` output contract.

Defines the strict pydantic v2 bases (:class:`OutputSchema`,
:class:`OutputRootSchema`), the canonical success envelope
(:class:`SchemaEnvelope`), the typed diagnostic channel
(:class:`Notice`), and
the emit helpers (:func:`emit_json_document`, :func:`emit_json_success`)
used by every authored machine-output path. CLI payload modules import
these primitives directly from this module and route JSON mode through
:func:`entrypoints.cli._common.emit_envelope`.

:func:`emit_json_success` derives :class:`EnvelopeStatus` from supplied
:class:`Notice` values via :func:`derive_status` and applies
:func:`core.redaction.redact_structured_for_cli_output` to the
entire envelope before writing stdout.  Text output remains owned by
:func:`core.output_rendering.render_command_output`, so redaction
and the ``reveal_cli_identifiers_opt_in`` switch stay consistent across
text and JSON surfaces.

Living in :mod:`core` keeps domain and adapter packages free of any
dependency on :mod:`entrypoints.cli`: a wrapped command emits its
strict-validated payload through :func:`emit_json_success` without
having to know how the CLI itself wires Click options.

This module owns the stdout success contract and schema registry. The
stderr failure document is rendered by :mod:`core.errors` using the
same :data:`ENVELOPE_SCHEMA_VERSION`, and text-mode layout remains owned
by :mod:`core.output_rendering`.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Mapping, Sequence
from enum import StrEnum
from types import MappingProxyType
from typing import IO, Any, Final, Protocol, cast, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    TypeAdapter,
    ValidationError,
    field_serializer,
    field_validator,
)

from .action_argument_resolution import ActionArgumentResolution
from .operator_action_enums import ActionArgumentStatus
from ._precondition_action_invariants import (
    PreconditionActionIdentity,
    PreconditionEvidence,
    PreconditionOutcomeInvariant,
)
from .errors.hierarchy import CadrumoError
from .identifier_grammar import FIELD_KEY_PATTERN
from .logging import get_logger
from .output_rendering import jsonable_output_payload
from .redaction import redact_structured_for_cli_output

_log = get_logger(__name__)

#: Case-SENSITIVE by mandate, not by oversight. The product-naming rule makes the
#: casing carry the meaning: the sole human CLI executable is the exact lowercase
#: token ``aeat``, while ``AEAT`` names the Spanish tax authority and is retained
#: wherever the referent is that authority, its official evidence, or its external
#: protocol. A case-insensitive match therefore cannot distinguish an executable
#: command from the authority's own name, and refuses legitimate prose such as
#: "No persisted AEAT session found on disk." What this reserves for the typed
#: action projection is command identity, which only the lowercase token carries.
_RAW_AEAT_COMMAND_PATTERN: Final[re.Pattern[str]] = re.compile(r"(?:^|[\s`'\";|&()])aeat(?=$|[\s`'\";|&()])")
_RESERVED_ACTION_CONTEXT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "action",
        "command",
        "fix_command",
        "next_action",
        "next_command",
        "recovery",
        "recovery_hint",
        "remediation",
        "suggestion",
    }
)

_STRICT_FROZEN_CONFIG = ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
    validate_assignment=True,
)
_STRICT_ROOT_CONFIG = ConfigDict(
    frozen=True,
    strict=True,
    validate_assignment=True,
)
#: Envelope contract version shared by the success :class:`SchemaEnvelope`
#: and the stderr error envelope. Both documents carry the same outer
#: spine (``schema_version``, ``command``, ``status``, ``notices``), so the
#: version is pinned once here and bumped only on a backwards-incompatible
#: change to that spine.
ENVELOPE_SCHEMA_VERSION = "2"


class EnvelopeStatus(StrEnum):
    """Outcome discriminator carried on every CLI return document.

    ``success`` and ``warning`` ride on the stdout :class:`SchemaEnvelope`
    (``warning`` when the command attached at least one warning-severity
    :class:`Notice`); ``error`` rides on the stderr error envelope. A
    machine consumer reads this single field to learn the outcome instead
    of branching on stdout-vs-stderr, and :func:`derive_status` is the
    success-envelope authority for computing it.

    :func:`emit_json_success` never emits :attr:`ERROR`; blocking
    failures route through the shared :class:`~core.errors.CadrumoError`
    boundary instead of being smuggled into stdout notices.
    """

    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class NoticeSeverity(StrEnum):
    """Severity of a single operator-facing :class:`Notice`.

    ``info`` is a non-fatal next-step hint or informational advisory;
    ``warning`` is a non-blocking advisory the operator should act on. A
    command that attaches any ``warning`` notice resolves to
    :attr:`EnvelopeStatus.WARNING` through :func:`derive_status`.
    """

    INFO = "info"
    WARNING = "warning"


class ActionConditionEvidence(PreconditionEvidence):
    """One evaluated failed-condition fact projected onto the wire.

    The model deliberately contains observed facts only. It does not select a
    condition, decide applicability, or resolve an action catalogue.
    """


class ResolvedActionReference(PreconditionActionIdentity):
    """One catalogue action after an outer resolver supplied its canonical target.

    The resolver is outside :mod:`cadrumo.core`; this record neither looks up
    the action ID nor discovers the live command surface.
    """

    target_command_key: str = Field(pattern=FIELD_KEY_PATTERN, min_length=1, max_length=160)
    cli_path: tuple[str, ...] | None = Field(default=None, exclude_if=lambda value: value is None)
    arguments: Mapping[str, str] | None = Field(default=None, exclude_if=lambda value: value is None)

    @field_validator("cli_path")
    @classmethod
    def _cli_path_is_canonical(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if value is None:
            return None
        if not value or any(not token or token != token.strip() or token.startswith("-") for token in value):
            raise ValueError("resolved action CLI path requires canonical command tokens")
        return value

    @field_validator("arguments")
    @classmethod
    def _freeze_arguments(cls, value: Mapping[str, str] | None) -> Mapping[str, str] | None:
        if value is None:
            return None
        if any(not key or key != key.strip() for key in value):
            raise ValueError("resolved action argument names must be non-blank canonical names")
        if any(not item or item != item.strip() for item in value.values()):
            raise ValueError("resolved action argument values must be non-blank canonical strings")
        return MappingProxyType(dict(sorted(value.items())))

    @field_serializer("arguments")
    def _serialize_arguments(self, value: Mapping[str, str] | None) -> dict[str, str] | None:
        return None if value is None else dict(value)


class ResolvedActionArgument(ActionArgumentResolution):
    """One resolved or missing target argument in the action wire projection."""

    model_config = _STRICT_FROZEN_CONFIG


class ResolvedPreconditionAction(
    PreconditionOutcomeInvariant[ActionConditionEvidence, ResolvedActionReference, ResolvedActionArgument],
):
    """A resolved precondition verdict projected for a machine consumer.

    This is intentionally a wire DTO. Application/domain guards own the
    rejected-condition policy and evidence; the operator surface owns the
    catalogue and live-schema resolution. The DTO only proves that the action
    target and each argument were resolved before presentation.
    """


class ResolvedNoticeAction(BaseModel):
    """A fully materialised next action carried by a successful notice.

    This transport record is deliberately distinct from
    :class:`ResolvedPreconditionAction`: success notices do not report a
    failed condition, conditional recovery state, or a terminal outcome.  The
    operator-surface resolver must establish the catalogue target and every
    required input before constructing this record; this DTO in turn refuses
    any unresolved argument so a consumer never receives a partial action.
    """

    model_config = _STRICT_FROZEN_CONFIG

    action: ResolvedActionReference
    argument_bindings: tuple[ResolvedActionArgument, ...] = Field(default_factory=tuple)

    @field_validator("argument_bindings")
    @classmethod
    def _canonicalize_resolved_arguments(
        cls,
        value: tuple[ResolvedActionArgument, ...],
    ) -> tuple[ResolvedActionArgument, ...]:
        """Require one concrete value for each supplied success-action argument."""
        names = tuple(item.argument_name for item in value)
        if len(set(names)) != len(names):
            raise ValueError("notice action argument names must be unique")
        if any(item.status is not ActionArgumentStatus.RESOLVED for item in value):
            raise ValueError("success notice actions require fully resolved argument bindings")
        return tuple(sorted(value, key=lambda item: item.argument_name))


class Notice(BaseModel):
    """One typed, non-blocking diagnostic on the envelope ``notices`` channel.

    The single uniform surface for operator-facing warnings, advisories,
    and next-step hints across every command. Domain diagnostics (e.g.
    ``ModeloFinding``, source-resolution advisories) are projected into
    this shape rather than re-modelled as bespoke per-command payload
    fields.  CLI helpers such as
    :func:`entrypoints.cli._common.emit_envelope` pass these values
    to :func:`emit_json_success`, while text renderers fold equivalent
    prose into their line output.

    Attributes:
        severity: ``info`` or ``warning``; drives the envelope ``status``.
        code: Stable machine-readable notice identifier (e.g.
            ``"modelo.calculate.unconsumed_iva"``).
        message: Localized operator-facing presentation text. It cannot carry
            an executable command identity.
        action: Optional schema-resolved action projection, and still the ONLY
            notice field that may identify an executable action. It carries a
            :class:`ResolvedPreconditionAction` for a failed precondition or a
            fully materialised :class:`ResolvedNoticeAction` after success.

            The success shape keeps forward guidance out of locale prose and
            retains every concrete target argument and its provenance.
        context: Optional deterministic non-action diagnostic metadata (e.g.
            source-resolution ``reason`` / ``source_kind``). Reserved action
            keys and executable command prose are rejected here.

    Blocking failures are not notices; they raise an
    :class:`~core.errors.CadrumoError` and emit on stderr. Command payload
    schemas should also avoid reintroducing bespoke advisory, hint, or
    warning fields inside ``result`` when a :class:`Notice` can carry the
    same non-blocking diagnostic.
    """

    model_config = _STRICT_FROZEN_CONFIG

    severity: NoticeSeverity
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    action: ResolvedPreconditionAction | ResolvedNoticeAction | None = None
    context: Mapping[str, str] | None = None

    @field_validator("message")
    @classmethod
    def _message_cannot_carry_command_identity(cls, value: str) -> str:
        """Reserve executable command identity for the typed action projection."""
        if _RAW_AEAT_COMMAND_PATTERN.search(value):
            raise ValueError("notice message cannot carry raw aeat command prose")
        return value

    @field_validator("context")
    @classmethod
    def _freeze_non_action_context(cls, value: Mapping[str, str] | None) -> Mapping[str, str] | None:
        """Preserve generic diagnostics while refusing a hidden action channel."""
        if value is None:
            return None
        if any(key in _RESERVED_ACTION_CONTEXT_KEYS for key in value):
            raise ValueError("notice context cannot carry action-guidance keys")
        if any(_RAW_AEAT_COMMAND_PATTERN.search(item) for item in value.values()):
            raise ValueError("notice context cannot carry raw aeat command prose")
        return MappingProxyType(dict(sorted(value.items())))

    @field_serializer("context")
    def _serialize_context(self, value: Mapping[str, str] | None) -> dict[str, str] | None:
        """Emit deterministic non-action context as a JSON object."""
        return None if value is None else dict(value)


def derive_status(notices: Sequence[Notice]) -> EnvelopeStatus:
    """Return :attr:`EnvelopeStatus.WARNING` if any notice is warning-severity.

    Success documents never carry :attr:`EnvelopeStatus.ERROR`; that
    status is reserved for the stderr error envelope. The returned
    :class:`EnvelopeStatus` is the stdout :class:`SchemaEnvelope` status
    used by :func:`emit_json_success`.
    """
    for notice in notices:
        if notice.severity is NoticeSeverity.WARNING:
            return EnvelopeStatus.WARNING
    return EnvelopeStatus.SUCCESS


class OutputSchemaError(CadrumoError):
    """Raised when a strict CLI output contract is violated.

    It deliberately inherits
    :class:`core.errors.CadrumoError` so registry defects route through
    the shared CLI error boundary instead of bypassing structured output.
    """


class OutputSchema(BaseModel):
    """Strict, frozen base class for every command-specific ``--json`` payload.

    Subclasses inherit ``extra="forbid"``, ``frozen=True``, ``strict=True``,
    and ``validate_assignment=True`` so accidental field drift between
    contract and implementation surfaces as a validation error rather
    than a silently-extended payload.  Each concrete result model should
    be referenced by the authored CLI command specification.

    The class describes the inner ``result`` payload only; the outer
    :class:`SchemaEnvelope` is applied later by :func:`emit_json_success`.
    """

    model_config = _STRICT_FROZEN_CONFIG


class OutputRootSchema[RootT](RootModel[RootT]):
    """Strict root/list base class for ``--json`` payloads with a non-mapping root.

    Use this for commands whose top-level JSON value is a list or scalar
    rather than an object. Carries the same strict / frozen / validate-on-
    assignment configuration as :class:`OutputSchema`, and participates in
    the same strict command-spec result contract.
    """

    model_config = _STRICT_ROOT_CONFIG


def strict_round_trip[ModelT: BaseModel](cls: type[ModelT], obj: BaseModel) -> ModelT:
    """Project *obj* into *cls* through a genuine JSON-text round trip.

    ``cls.model_validate(obj.model_dump(mode="json"))`` reads as a round trip
    but is not one under strict pydantic v2 validation: ``model_dump(mode="json")``
    projects a ``StrEnum`` to its bare string, a ``datetime`` to its isoformat
    string, and a ``tuple`` to a JSON array, and ``model_validate`` on the
    resulting plain ``dict`` does not coerce any of those back to their native
    type -- only ``model_validate_json``'s genuine JSON-text parse gets that
    leniency. A model that gains one of those field types after its call sites
    were written breaks silently at the two-step dict form with no local signal
    at the call site itself.

    Use this helper (or call ``cls.model_validate_json(obj.model_dump_json())``
    directly) at every typed cross-model projection boundary. It is the
    migration target the ``model_dump(mode="json")``-into-``model_validate``
    inventory gate enforces, not a substitute for the gate: the codebase already
    had ``model_dump_json``/``model_validate_json`` one method-name swap away
    and around forty call sites independently reached for the unsafe two-step
    form anyway, so a convenience helper alone would only add a second
    available idiom rather than retiring the first.
    """
    return cls.model_validate_json(obj.model_dump_json())


class SchemaEnvelope[ResultT: OutputSchema](BaseModel):
    """Stable outer envelope wrapping a successful command's payload.

    Every successful ``--json`` response is rendered through this
    envelope so consumers can rely on the same outer keys regardless of
    the inner payload shape. The outer spine (``schema_version``,
    ``command``, ``status``, ``notices``) is shared with the stderr error
    envelope so one shape describes success, warning, and error outcomes.
    :func:`emit_json_success` constructs the runtime mapping and the
    JSON-contract conformance gate specialises this generic envelope over
    every schema authored by the command-spec graph.

    The envelope is a wire contract, not the command dispatcher. It does
    not discover Click/Typer leaves, choose text output, or own command
    authorization; those layers supply a strict ``result`` and stable
    command path before entering this contract.

    Attributes:
        schema_version: Envelope version; bumped only on
            backwards-incompatible changes to the shared spine.
        command: Stable command path string (e.g. ``"workflow list"``).
        active_profile: Human-readable label of the active taxpayer
            profile (the operator-chosen display name), or ``None`` before
            any profile exists and for non-profile-bound commands. The
            identity anchor a caller reconciles against; it is the label,
            never the redacted profile/bucket UUID. Resolved and injected
            at the CLI transport boundary (the ``core`` layer never scans
            profile manifests), so it stays ``None`` for any emitter that
            does not supply it.
        status: Outcome discriminator (``success`` or ``warning`` here).
        result: The strict-validated command result.
        notices: Typed non-blocking diagnostics (warnings, advisories,
            next-step hints) surfaced to the caller. Replaces the former
            free-form ``warnings`` string list.
    """

    model_config = _STRICT_FROZEN_CONFIG

    schema_version: str = Field(default=ENVELOPE_SCHEMA_VERSION, min_length=1)
    command: str = Field(min_length=1)
    active_profile: str | None = Field(
        default=None,
        description=(
            "Human label of the active taxpayer profile, or null before a "
            "profile exists / for non-profile-bound commands; never the "
            "redacted profile or bucket UUID."
        ),
    )
    status: EnvelopeStatus
    result: ResultT
    notices: list[Notice] = Field(default_factory=list)


type RegisteredSchema = type[OutputSchema] | type[OutputRootSchema[Any]]


@runtime_checkable
class _ReconfigurableStream(Protocol):
    """Structural type for text streams that support runtime reconfiguration.

    Matches :class:`io.TextIOWrapper` so :func:`emit_json_document` can
    pin stdout to UTF-8 without a hard isinstance check on the concrete
    class — useful for tests that pass in a :class:`io.StringIO`.
    """

    def reconfigure(self, *, encoding: str, errors: str) -> None:
        """Reset the stream's encoding and error-handling mode."""
        ...

    def write(self, s: str, /) -> int:
        """Write ``s`` to the stream and return the number of characters written."""
        ...

    def flush(self) -> None:
        """Flush the write buffers."""
        ...


def emit_json_document(
    payload: object,
    *,
    indent: int | None = 2,
    sort_keys: bool = False,
    stream: IO[str] | None = None,
) -> None:
    r"""Serialise ``payload`` and write a single UTF-8 JSON document followed by ``\\n``.

    When ``stream`` exposes ``_ReconfigurableStream.reconfigure``,
    the helper pins it to ``encoding="utf-8", errors="strict"`` first so
    downstream cp1252 consoles can not silently corrupt non-ASCII
    characters in the rendered output. This is the low-level writer used
    by :func:`emit_json_success`; it does not itself apply the envelope or
    redaction policy.

    Use this for already-shaped JSON documents. Registered CLI success
    payloads should normally enter through :func:`emit_json_success` so
    the envelope, status derivation, and redaction pass remain uniform.

    Args:
        payload: Any object reachable by :func:`jsonable_output_payload`
            (typically a :class:`pydantic.BaseModel`, a mapping, or a
            collection thereof).
        indent: Indent width passed to :func:`json.dumps`; ``None``
            produces a single-line document.
        sort_keys: Whether to render mapping keys in lexicographic order.
        stream: Target text stream; defaults to :data:`sys.stdout`.
    """
    target = sys.stdout if stream is None else stream
    if isinstance(target, _ReconfigurableStream):
        try:
            target.reconfigure(encoding="utf-8", errors="strict")
        except (OSError, ValueError, AttributeError) as exc:
            _log.debug(
                "json_contract: stdout reconfigure to UTF-8 failed; emitting with current encoding (%s)",
                exc,
            )
    document = json.dumps(
        jsonable_output_payload(payload),
        ensure_ascii=False,
        indent=indent,
        sort_keys=sort_keys,
        default=str,
    )
    target.write(f"{document}\n")
    target.flush()


def emit_json_success(
    command: str,
    result: object,
    *,
    notices: Sequence[Notice] | None = None,
    active_profile: str | None = None,
    indent: int | None = 2,
    sort_keys: bool = False,
    stream: IO[str] | None = None,
) -> None:
    """Wrap ``result`` in the success spine and emit it via :func:`emit_json_document`.

    The envelope's ``schema_version`` is pinned to
    :data:`ENVELOPE_SCHEMA_VERSION`; bumping it is a contract-breaking
    change handled by the JSON-contract test suite, not a casual edit.
    The ``status`` is derived from the supplied notices
    (:func:`derive_status`) so the JSON outcome and the shell exit code
    never disagree. The assembled envelope is redacted through
    :func:`core.redaction.redact_structured_for_cli_output` before
    :func:`emit_json_document` writes it.

    This helper is stdout-only. Any raised :class:`~core.errors.CadrumoError`
    is handled by the CLI error boundary, which renders the sibling stderr
    envelope instead of returning a success document with an error-shaped
    ``result``.

    Args:
        command: Stable command path string (e.g. ``"workflow list"``).
        result: The strict-validated command payload to surface as
            ``envelope.result``.
        notices: Optional typed :class:`Notice` diagnostics (warnings,
            advisories, next-step hints); defaults to an empty list.
        active_profile: Optional human label of the active taxpayer
            profile placed on the shared spine (the identity anchor).
            The ``core`` layer never scans profile manifests, so the CLI
            transport resolves the label and passes it here; ``None`` for
            non-profile-bound emitters. It rides through the same
            redaction pass as the rest of the envelope, but it is the
            non-secret display name, not the redacted profile/bucket UUID.
        indent: Indent width forwarded to :func:`emit_json_document`.
        sort_keys: Sort-keys flag forwarded to :func:`emit_json_document`.
        stream: Target text stream; defaults to :data:`sys.stdout`.
    """
    from .output_rendering import reveal_cli_identifiers_opt_in

    resolved_notices = [] if notices is None else list(notices)
    envelope_payload = redact_structured_for_cli_output(
        {
            "schema_version": ENVELOPE_SCHEMA_VERSION,
            "command": command,
            "active_profile": active_profile,
            "status": derive_status(resolved_notices).value,
            "result": jsonable_output_payload(result),
            "notices": [jsonable_output_payload(notice) for notice in resolved_notices],
        },
        reveal_identifiers=reveal_cli_identifiers_opt_in(),
    )
    _record_captured_envelope(envelope_payload)
    emit_json_document(
        envelope_payload,
        indent=indent,
        sort_keys=sort_keys,
        stream=stream,
    )


def _record_captured_envelope(envelope_payload: object) -> None:
    """Feed the emitted envelope to the observability capture sink, best-effort.

    The deterministic-output substrate captures the verbatim emitted
    envelope so a recorded run can be replayed and asserted byte-identical
    after masking. Capture is off by default: when no
    :func:`core.observability.capture_envelopes` scope is active the
    recorder is a single ``ContextVar.get`` returning ``None``. The call
    is fully best-effort — a capture failure must never disturb the emit
    contract. The import is lazy so :mod:`core.json_contract` keeps
    no module-load dependency on the observability layer.
    """
    if not isinstance(envelope_payload, Mapping):
        return
    try:
        from .observability.capture import record_emitted_envelope

        # CAST-RATIONALE-ENVELOPE-CAPTURE-MAPPING: the isinstance check above
        # confirms only the erased runtime `Mapping` shape, not the `str, object`
        # type parameters; the cast narrows to the capture helper's declared
        # parameter type.
        record_emitted_envelope(cast("Mapping[str, object]", envelope_payload))
    except Exception:  # capture must never break emit
        _log.debug("json_contract: envelope capture failed; continuing", exc_info=True)


def validate_registered_result(command: str, result: object) -> OutputSchema | OutputRootSchema[Any]:
    """Strictly revalidate an already typed operator result.

    The low-level JSON emitter intentionally remains a transport primitive for
    metadata and diagnostic surfaces. Operator command output must enter
    through this check so an envelope cannot claim a registered command while
    carrying an arbitrary result shape.
    """
    if not isinstance(result, OutputSchema | OutputRootSchema):
        raise OutputSchemaError(f"operator JSON result for {command!r} is not a strict output schema")
    schema = type(result)
    payload = result.model_dump(mode="python") if isinstance(result, BaseModel) else result
    try:
        return schema.model_validate(payload)
    except ValidationError as error:
        raise OutputSchemaError(
            f"operator JSON result does not conform to the registered schema for {command!r}",
        ) from error


def validate_registered_envelope_document(
    document: object,
    schema: RegisteredSchema | None,
) -> dict[str, object]:
    """Strictly validate one emitted CLI success or error JSON document."""
    if not isinstance(document, dict):
        raise OutputSchemaError("operator JSON envelope must be an object")
    raw_document = cast("dict[object, object]", document)
    if not all(isinstance(key, str) for key in raw_document):
        raise OutputSchemaError("operator JSON envelope keys must be strings")
    typed_document: dict[str, object] = {key: value for key, value in raw_document.items() if isinstance(key, str)}
    if typed_document.get("status") == EnvelopeStatus.ERROR.value:
        return _validated_error_envelope(typed_document)
    if schema is None:
        raise OutputSchemaError("operator JSON success envelope requires its authored result schema")
    return _validated_success_envelope(typed_document, schema)


def _validated_error_envelope(typed_document: dict[str, object]) -> dict[str, object]:
    from .errors.error_codes import ErrorEnvelope

    required_keys = {"schema_version", "command", "active_profile", "status", "error", "notices"}
    if set(typed_document) != required_keys:
        raise OutputSchemaError("operator JSON error envelope has an invalid outer shape")
    if typed_document.get("schema_version") != ENVELOPE_SCHEMA_VERSION:
        raise OutputSchemaError("operator JSON envelope has an unsupported schema version")
    command = typed_document.get("command")
    active_profile = typed_document.get("active_profile")
    if command is not None and (not isinstance(command, str) or not command):
        raise OutputSchemaError("operator JSON error envelope has an invalid command")
    if active_profile is not None and not isinstance(active_profile, str):
        raise OutputSchemaError("operator JSON error envelope has an invalid active profile")
    try:
        ErrorEnvelope.model_validate(typed_document["error"])
        TypeAdapter(list[Notice]).validate_python(typed_document["notices"])
    except ValidationError as error:
        raise OutputSchemaError("operator JSON error envelope failed strict validation") from error
    return typed_document


def _validated_success_envelope(
    typed_document: dict[str, object],
    schema: RegisteredSchema,
) -> dict[str, object]:
    command = typed_document.get("command")
    if not isinstance(command, str) or not command:
        raise OutputSchemaError("operator JSON envelope has no usable command")
    required_keys = {"schema_version", "command", "active_profile", "status", "result", "notices"}
    if set(typed_document) != required_keys:
        raise OutputSchemaError("operator JSON success envelope has an invalid outer shape")
    if typed_document.get("schema_version") != ENVELOPE_SCHEMA_VERSION:
        raise OutputSchemaError("operator JSON envelope has an unsupported schema version")
    # CAST-RATIONALE-ENVELOPE-GENERIC: __class_getitem__ returns a bare `type`
    # at runtime; `schema` is an OutputSchema subclass, so the parameterized generic is
    # exactly SchemaEnvelope[OutputSchema].
    envelope_model = cast("type[SchemaEnvelope[OutputSchema]]", SchemaEnvelope.__class_getitem__(schema))
    try:
        validated = envelope_model.model_validate_json(json.dumps(typed_document))
    except ValidationError as error:
        raise OutputSchemaError("operator JSON success envelope failed strict validation") from error
    # CAST-RATIONALE-ENVELOPE-DUMP: model_dump(mode="json") is typed
    # dict[str, Any] by pydantic; the envelope's own strict schema already
    # constrains every value to JSON-safe scalars/containers.
    return cast(dict[str, object], validated.model_dump(mode="json"))


__all__ = [
    "ENVELOPE_SCHEMA_VERSION",
    "ActionConditionEvidence",
    "EnvelopeStatus",
    "Notice",
    "NoticeSeverity",
    "OutputRootSchema",
    "OutputSchema",
    "OutputSchemaError",
    "ResolvedActionArgument",
    "ResolvedActionReference",
    "ResolvedNoticeAction",
    "ResolvedPreconditionAction",
    "SchemaEnvelope",
    "derive_status",
    "emit_json_document",
    "emit_json_success",
    "strict_round_trip",
    "validate_registered_envelope_document",
    "validate_registered_result",
]


# ErrorEnvelope names ResolvedPreconditionAction, defined above. The errors
# package cannot resolve that itself -- its hierarchy binds error codes while
# still being defined, so reaching here from its module scope re-enters a
# half-built module. This is the first point at which both halves exist.
from .errors.error_codes import complete_error_envelope_model  # noqa: E402 - see comment above

complete_error_envelope_model()
