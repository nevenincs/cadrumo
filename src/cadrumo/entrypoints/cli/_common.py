"""Shared CLI transport helpers used across all ``cadrumo`` command groups.

Provides output helpers, period normalisation, and repository accessors
used by the ledger, modelo, and config command groups. The repository
accessors return typed domain objects:
:class:`TransactionCatalogue` and
:class:`TransactionCatalogueRepository` for transaction
ledger access, :class:`InvoiceCatalogue` and
:class:`InvoiceCatalogueRepository` for invoice data,
:class:`ModeloDraft` for in-progress modelo drafts, and
:class:`TaxpayerProfile` for deadline and period
calculations.

The output boundary is :func:`emit_envelope`. It routes every JSON result
through :class:`SchemaEnvelope`, requires a graph-declared result schema, and
carries typed :class:`Notice` diagnostics while preserving the text line
iterator unchanged.

Application-layer and domain symbols are imported lazily inside each
helper to avoid pulling the registry parse into fast-path commands such
as ``aeat --version``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Generator, Iterable, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from enum import StrEnum
from functools import cache, partial
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import click
import typer
import typer._click.types as typer_click_types
from pydantic import BaseModel, Field, field_validator

from ...core import NON_REGISTRY_MODELOS, STRICT_FROZEN_CONFIG, Modelo
from ...core.cli_metadata import is_metadata_invocation
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity, ResolvedActionArgument, ResolvedPreconditionAction
from ...core.output_rendering import OutputFormat, render_command_output
from ._command_suggestions import INVOCATION_REMAINDER_META_KEY
from ._operator_surface_reconciliation import current_operator_surface_reconciliation

# The accepted-code set for every ``--modelo`` option and argument. It is derived
# from the closed core identifier taxonomy rather than the registry authority:
# help and parse-time refusals are introspection surfaces and must render even
# while a peer's registry authoring slice is fail-hard invalid. Command bodies
# still reach the registry-backed services for real data access.
#
# Non-registry members are excluded because every consumer of this choice resolves
# a registry revision. Surfaces that legitimately address a retired code — the
# portal catalogue ships an entry for the suppressed Modelo 037 — must NOT use
# this constant; they need the full taxonomy.
#
# It is a module-level constant because ``from __future__ import annotations``
# stringifies the ``Annotated`` metadata carrying ``click_type=...`` and Typer
# re-evaluates that string in the defining module's global namespace, where a
# closure-local binding would be invisible.
#
# CAST-RATIONALE-TYPER-CLICK-PARAMTYPE-DUALITY: typer vendors its own click, so
# click.Choice's click.types.ParamType and typer's typer._click.types.ParamType
# are the same runtime object behind two static names; the cast bridges only that
# static duality, with no Any escape.
MODELO_CODE_CHOICE: typer_click_types.ParamType = cast(
    typer_click_types.ParamType,
    click.Choice([modelo.value for modelo in Modelo if modelo not in NON_REGISTRY_MODELOS]),
)

# The FULL modelo taxonomy, including the codes that have no registry definition.
# Use this only where a command legitimately addresses a retired or non-registry
# modelo: the portal catalogue ships an entry for the suppressed Modelo 037, so a
# portal filter pinned to MODELO_CODE_CHOICE would refuse a code the application
# deliberately supports. It is a separate constant rather than a widening of
# MODELO_CODE_CHOICE because the registry-resolving surfaces must keep refusing
# those codes.
#
# CAST-RATIONALE-TYPER-CLICK-PARAMTYPE-DUALITY: typer vendors its own click, so
# click.Choice's click.types.ParamType and typer's typer._click.types.ParamType
# are the same runtime object behind two static names; the cast bridges only that
# static duality, with no Any escape.
MODELO_CODE_CHOICE_ALL: typer_click_types.ParamType = cast(
    typer_click_types.ParamType,
    click.Choice([modelo.value for modelo in Modelo]),
)


def case_insensitive_choice(enum_class: type[StrEnum]) -> typer_click_types.ParamType:
    """Build a case-insensitive click choice over ``enum_class``'s values.

    Typer renders a bare enum annotation as a case-SENSITIVE choice. Several
    options on this CLI previously hand-parsed their token with ``.upper()`` or
    ``.strip().lower()`` before constructing the enum, so replacing that parser
    with the annotation alone silently narrows the accepted spellings — a
    behaviour change invisible at the declaration site and in every test that
    only uses canonical forms.

    Passing the result as ``click_type`` keeps the parameter's enum annotation
    authoritative: the handler still receives a real member, not the raw token,
    and external input-schema builders still read the closed value set off the
    wrapped choice. Only the accepted spelling widens.
    """
    # CAST-RATIONALE-TYPER-CLICK-PARAMTYPE-DUALITY: typer vendors its own click, so
    # click.Choice's click.types.ParamType and typer's typer._click.types.ParamType
    # are the same runtime object behind two static names; the cast bridges only
    # that static duality, with no Any escape.
    return cast(
        typer_click_types.ParamType,
        click.Choice([member.value for member in enum_class], case_sensitive=False),
    )


# The application- and domain-layer symbols below are imported lazily,
# inside the helpers that use them at runtime. A module-level import
# would pull the application layer — and transitively the registry
# parse — into every consumer of this transport module, including the
# ``aeat --version`` / ``aeat --help`` fast paths that import ``emit_envelope``
# but never reach a registry-backed helper. ``from __future__ import
# annotations`` keeps the type annotations valid as strings without a
# runtime import; the ``TYPE_CHECKING`` block keeps static checkers
# resolving them.
if TYPE_CHECKING:
    from ...adapters.persistence.profile.filing_drafts import ModeloDraftRepository
    from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ...application.auth.catalogue import AuthProviderListing
    from ...application.modelo._work_lifecycle import ModeloWorkLifecycleContinuation
    from ...application.operator_actions import (
        ActionArgumentBinding,
        ActionArgumentBindingSpecification,
        ActionReference,
        PreconditionVerdict,
    )
    from ...application.workflow.state_models import WorkflowState
    from ...core.json_contract import ResolvedActionReference, ResolvedNoticeAction
    from ...domain.deadlines import TaxpayerProfile
    from ...domain.filing import ModeloDraft
    from ...domain.invoices import InvoiceCatalogue
    from ...domain.transactions import TransactionCatalogue
    from ...domain.user_profile.values import UserProfileRecord
    from ._verb_input_schema import VerbInputSchema

__all__ = [
    "active_profile_label",
    "bad",
    "emit_envelope",
    "emit_help_text",
    "emit_progress_line",
    "format_of",
    "no_active_profile_refusal",
    "notice_lines",
    "resolve_lifecycle_continuation_notice",
    "resolve_notice_action",
]


REQUESTED_CLI_LEAF_META_KEY = "cadrumo.requested_cli_leaf"
"""Context key holding the terminal leaf selected before root guards run."""

_OPERATOR_SURFACE_RECONCILIATION_META_KEY = "cadrumo.operator_surface_reconciliation"
"""Invocation-scoped immutable reconciliation shared by nested Click contexts."""

_CLI_POLICY_REFUSAL_PROJECTION_ATTRIBUTE = "_cadrumo_cli_policy_refusal_projection"


class RequestedCliLeaf(BaseModel):
    """Immutable identity of the real terminal command the operator requested."""

    model_config = STRICT_FROZEN_CONFIG

    subject_leaf_key: str = Field(min_length=1)
    canonical_cli_path: tuple[str, ...] = Field(min_length=1)

    @field_validator("canonical_cli_path")
    @classmethod
    def _path_tokens_are_canonical(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not token or token != token.strip() or token.startswith("-") for token in value):
            raise ValueError("requested CLI leaf path requires canonical command tokens")
        return value


_REQUESTED_CLI_LEAF_CONTEXT: ContextVar[RequestedCliLeaf | None] = ContextVar(
    "cadrumo_requested_cli_leaf",
    default=None,
)

#: The same leaf, held for the WHOLE invocation rather than the Click context.
#:
#: :data:`_REQUESTED_CLI_LEAF_CONTEXT` is reset by ``ctx.call_on_close`` when the
#: Click context closes, which is correct for in-command reads and useless to the
#: PROCESS boundary: ``_terminal_errors._emit_crash`` runs after that close, so it
#: asked and got ``None``, and every refusal escaping there published a null
#: ``command`` even where the leaf was known.
#:
#: Lifetime is owned by :func:`run_standalone_with_error_contract`, which every
#: invocation passes through, exactly as it already owns ``_INVOCATION_ARGV``.
#: That reset is what stops a leaf leaking into the NEXT invocation -- the failure
#: mode that matters here is not a crash but a WRONG command name on an unrelated
#: error, which the cached in-process runner would surface first.
_BOUNDARY_REQUESTED_CLI_LEAF: ContextVar[RequestedCliLeaf | None] = ContextVar(
    "cadrumo_boundary_requested_cli_leaf",
    default=None,
)


@contextmanager
def boundary_requested_leaf_scope() -> Generator[None]:
    """Bound the invocation-scoped requested leaf to one CLI dispatch."""
    token = _BOUNDARY_REQUESTED_CLI_LEAF.set(None)
    try:
        yield
    finally:
        _BOUNDARY_REQUESTED_CLI_LEAF.reset(token)


class CliPolicyRefusalProjection(BaseModel):
    """Typed policy handoff awaiting generic boundary transport in S18."""

    model_config = STRICT_FROZEN_CONFIG

    requested_leaf: RequestedCliLeaf | None
    precondition_action: ResolvedPreconditionAction


class _CommandGroup(Protocol):
    def get_command(self, ctx: object, cmd_name: str) -> object | None:
        """Resolve one real child command."""


def attach_cli_policy_refusal_projection[ExceptionT: Exception](
    error: ExceptionT,
    *,
    projection: CliPolicyRefusalProjection,
) -> ExceptionT:
    """Attach the strict S17 handoff without changing generic S18 transport."""
    setattr(error, _CLI_POLICY_REFUSAL_PROJECTION_ATTRIBUTE, projection)
    return error


def cli_policy_refusal_projection(error: BaseException) -> CliPolicyRefusalProjection | None:
    """Read a directly attached or workflow-terminal typed policy handoff."""
    value = getattr(error, _CLI_POLICY_REFUSAL_PROJECTION_ATTRIBUTE, None)
    if value is not None:
        if not isinstance(value, CliPolicyRefusalProjection):
            raise TypeError("CLI policy refusal contains an invalid typed projection")
        return value

    from ...application.cli_exception_preconditions import nested_terminal_precondition_verdict

    terminal_verdict = nested_terminal_precondition_verdict(error)
    if terminal_verdict is None:
        return None
    return project_cli_policy_refusal(
        requested_leaf=current_requested_cli_leaf(),
        verdict=terminal_verdict,
    )


def cli_policy_refusal_context(projection: CliPolicyRefusalProjection) -> dict[str, object] | None:
    """Render configuration identities from typed evidence, never recovery prose."""
    context: dict[str, object] = {}
    for evidence in projection.precondition_action.evidence:
        for key, value in evidence.values.items():
            if key.endswith("_setting"):
                context[key] = value
    return context or None


def preserve_requested_cli_leaf(ctx: typer.Context) -> RequestedCliLeaf | None:
    """Resolve and retain the terminal live leaf before root policy guards."""
    existing = ctx.meta.get(REQUESTED_CLI_LEAF_META_KEY)
    if existing is not None:
        if not isinstance(existing, RequestedCliLeaf):
            raise TypeError("requested CLI leaf context contains an invalid value")
        return existing

    raw_tokens = tuple(str(token) for token in ctx.meta.get(INVOCATION_REMAINDER_META_KEY, ()))
    command: object = ctx.command
    canonical_path: list[str] = []
    for token in raw_tokens:
        if token.startswith("-") or not hasattr(command, "get_command"):
            break
        child = cast(_CommandGroup, command).get_command(ctx, token)
        if child is None:
            return None
        command_name = getattr(child, "name", None)
        canonical_path.append(command_name if isinstance(command_name, str) and command_name else token)
        command = child
        if not hasattr(command, "get_command"):
            from ._command_specs import COMMAND_GRAPH

            spec = COMMAND_GRAPH.resolve_path(("aeat", *canonical_path))
            identity = spec.result_schema.identity
            if identity is None:
                return None
            requested = RequestedCliLeaf(
                subject_leaf_key=identity,
                canonical_cli_path=tuple(canonical_path),
            )
            ctx.meta[REQUESTED_CLI_LEAF_META_KEY] = requested
            token = _REQUESTED_CLI_LEAF_CONTEXT.set(requested)
            ctx.call_on_close(partial(_REQUESTED_CLI_LEAF_CONTEXT.reset, token))
            # Written through to the invocation-scoped holder as well, so the
            # process boundary can still name the command after this Click
            # context has closed. Deliberately NOT reset on close.
            _BOUNDARY_REQUESTED_CLI_LEAF.set(requested)
            return requested
    return None


def requested_cli_leaf(ctx: typer.Context) -> RequestedCliLeaf | None:
    """Return the already-preserved requested terminal identity, if any."""
    value = ctx.meta.get(REQUESTED_CLI_LEAF_META_KEY)
    if value is None:
        return None
    if not isinstance(value, RequestedCliLeaf):
        raise TypeError("requested CLI leaf context contains an invalid value")
    return value


def current_requested_cli_leaf() -> RequestedCliLeaf | None:
    """Return the preserved leaf from the current Click context, if one exists."""
    bound = _REQUESTED_CLI_LEAF_CONTEXT.get()
    if bound is not None:
        return bound
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        # No Click context: either before one opened, or after it closed. The
        # invocation-scoped holder answers the second case, which is where the
        # process boundary asks from.
        return _BOUNDARY_REQUESTED_CLI_LEAF.get()
    return requested_cli_leaf(cast(typer.Context, ctx))


def project_cli_policy_refusal(
    *,
    requested_leaf: RequestedCliLeaf | None,
    verdict: PreconditionVerdict,
) -> CliPolicyRefusalProjection:
    """Project one application verdict without teaching the CLI applicability."""
    return CliPolicyRefusalProjection(
        requested_leaf=requested_leaf,
        precondition_action=resolve_cli_precondition_action(verdict),
    )


def _validate_cli_precondition_action_bindings(
    *,
    action_id: str,
    specifications: tuple[ActionArgumentBindingSpecification, ...],
    argument_bindings: tuple[ActionArgumentBinding, ...],
) -> None:
    """Require verdict bindings to account for the declared action arguments."""
    specifications_by_name = _catalogue_argument_specifications_by_name(specifications)
    observed_arguments = {item.argument_name: item for item in argument_bindings}
    if set(observed_arguments) != set(specifications_by_name):
        raise ValueError(f"CLI policy action arguments do not match catalogue declaration: {action_id}")
    _require_cli_precondition_argument_sources(
        observed_arguments=observed_arguments,
        specifications_by_name=specifications_by_name,
    )


def _catalogue_argument_specifications_by_name(
    specifications: tuple[ActionArgumentBindingSpecification, ...],
) -> dict[str, list[ActionArgumentBindingSpecification]]:
    """Group the catalogue's declared input sources by their argument identity."""
    specifications_by_name: dict[str, list[ActionArgumentBindingSpecification]] = {}
    for specification in specifications:
        specifications_by_name.setdefault(specification.argument_name, []).append(specification)
    return specifications_by_name


def _require_cli_precondition_argument_sources(
    *,
    observed_arguments: dict[str, ActionArgumentBinding],
    specifications_by_name: dict[str, list[ActionArgumentBindingSpecification]],
) -> None:
    """Refuse a resolved verdict binding whose provenance contradicts the catalogue."""
    from ...core import ActionArgumentStatus

    for name, argument in observed_arguments.items():
        if argument.status is ActionArgumentStatus.MISSING:
            continue
        matching_specifications = tuple(
            specification
            for specification in specifications_by_name[name]
            if argument.source is specification.source
            and argument.source_key == specification.source_key
            and argument.source_evidence_id == specification.source_evidence_id
        )
        if len(matching_specifications) != 1:
            raise ValueError(f"CLI policy action argument source contradicts catalogue: {name}")


def _resolve_cli_precondition_action_reference(
    verdict: PreconditionVerdict,
) -> ResolvedActionReference | None:
    """Resolve the optional verdict recovery action against the live surface."""
    action = verdict.action
    if action is None:
        return None
    from ...application.operator_actions import OPERATOR_ACTION_CATALOGUE
    from ...application.operator_surface import resolve_catalogue_action
    from ...core.json_contract import ResolvedActionReference

    resolution = resolve_catalogue_action(
        action=action,
        catalogue=OPERATOR_ACTION_CATALOGUE,
        reconciliation=current_operator_surface_reconciliation(),
    )
    declaration = resolution.declaration
    if resolution.target_leaf.input_schema is None:
        raise ValueError(
            f"CLI policy action target has no live input schema: {declaration.target_command_key}",
        )
    _validate_cli_precondition_action_bindings(
        action_id=action.action_id,
        specifications=declaration.argument_specifications,
        argument_bindings=verdict.argument_bindings,
    )
    return ResolvedActionReference(
        action_id=declaration.action_id,
        target_command_key=declaration.target_command_key,
        cli_path=resolution.target_leaf.live_leaf.canonical_cli_path,
    )


def resolve_cli_precondition_action(verdict: PreconditionVerdict) -> ResolvedPreconditionAction:
    """Schema-resolve one application verdict against the live action catalogue.

    This is the sole CLI adapter from application-owned verdict facts into the
    strict wire DTO.  Both immediate refusal envelopes and persisted workflow
    history use it, so neither path can reconstruct recovery prose or disagree
    about missing bindings.
    """
    from ...core.json_contract import ActionConditionEvidence, ResolvedActionArgument

    projected = ResolvedPreconditionAction(
        failed_condition_id=verdict.failed_condition_id,
        evidence=tuple(
            ActionConditionEvidence(
                condition_id=item.condition_id,
                evidence_id=item.evidence_id,
                provenance=item.provenance,
                values=item.values,
            )
            for item in verdict.evidence
        ),
        action=_resolve_cli_precondition_action_reference(verdict),
        argument_bindings=tuple(
            ResolvedActionArgument(
                argument_name=item.argument_name,
                status=item.status,
                value=item.value,
                source=item.source,
                source_key=item.source_key,
                source_evidence_id=item.source_evidence_id,
            )
            for item in verdict.argument_bindings
        ),
        missing_argument_names=verdict.missing_argument_names,
        conditionality=verdict.conditionality,
        no_recovery_outcome=verdict.no_recovery_outcome,
    )
    return projected


def attach_cli_policy_verdict[ExceptionT: Exception](
    error: ExceptionT,
    *,
    verdict: PreconditionVerdict,
    requested_leaf: RequestedCliLeaf | None = None,
) -> ExceptionT:
    """Project and attach an application verdict at the shared CLI boundary."""
    leaf = requested_leaf if requested_leaf is not None else current_requested_cli_leaf()
    return attach_cli_policy_refusal_projection(
        error,
        projection=project_cli_policy_refusal(
            requested_leaf=leaf,
            verdict=verdict,
        ),
    )


# ---------------------------------------------------------------------
# Transport helpers
# ---------------------------------------------------------------------


def _is_metadata_invocation(ctx: typer.Context) -> bool:
    """Read metadata posture from captured tokens and eager callback flags.

    Click consumes eager ``--help`` / ``--version`` options before group
    :meth:`invoke` runs, so the captured remainder is intentionally not the
    only authority.  The callback parameters are the lossless observation for
    those root and curated-group flags; consulting them keeps metadata output
    off profile, custody, and sandbox discovery even after parsing.
    """
    arguments = tuple(str(token) for token in ctx.meta.get(INVOCATION_REMAINDER_META_KEY, ()))
    if is_metadata_invocation(arguments):
        return True
    return any(ctx.params.get(name) is True for name in ("help_", "version"))


def _format_of(ctx: typer.Context) -> OutputFormat:
    state = cast(dict[str, object], ctx.ensure_object(dict))
    format_value = state.get("format", OutputFormat.TEXT)
    if isinstance(format_value, OutputFormat):
        return format_value
    return OutputFormat(format_value)


format_of = _format_of


def emit_help_text(ctx: typer.Context) -> None:
    """Emit Click/Typer help text through the shared CLI output boundary."""
    typer.echo(ctx.get_help())


def _render_and_echo(*, format_name: str, payload: object, lines: tuple[str, ...]) -> None:
    """Render through the output boundary and emit whatever text it returns.

    The single place operator-facing success text crosses from rendering into
    standard output. Both the closing envelope and the streamed progress
    channel funnel through here, so the redaction pass and the
    reveal-identifiers resolver are applied once, in one place, rather than
    once per emitter. A second copy of these three lines is how the streamed
    channel came to bypass redaction in the first place.
    """
    rendered = render_command_output(format_name=format_name, payload=payload, lines=lines)
    if rendered.text:
        typer.echo(rendered.text)


def emit_progress_line(line: str) -> None:
    """Emit one streamed text-mode progress line through the success-output funnel.

    A long-running command reports per-item progress while the run is still
    working, so those lines reach stdout before the closing envelope exists.
    They are operator-facing success output all the same, and they are rendered
    here by :func:`~cadrumo.core.output_rendering.render_command_output` — the
    very renderer :func:`emit_envelope` uses for its text arm. The streamed
    channel therefore applies the same line-oriented CLI redaction and consults
    the same
    :func:`~cadrumo.core.output_rendering.reveal_cli_identifiers_opt_in`
    resolver, so an operator cannot be shown a raw value on the progress stream
    that the envelope would have masked, nor a masked one they opted to reveal.

    This is deliberately not a second envelope: it carries no schema spine, no
    notices, and no sandbox banner. Callers gate the stream to text mode
    themselves, because in JSON the closing envelope already carries every row.

    **What the funnel masks, stated because the change that introduced this
    primitive overstated it.** The redaction policy substitutes embedded tax
    identities and opaque record identifiers; it does NOT mask filesystem
    paths. A streamed line naming a document by its path still emits that
    path, and only an identity inside it is replaced. The protection this
    primitive restores is identity and opaque-id masking on a channel that had
    none, which is narrower than "the material the funnel exists to mask" and
    is the accurate claim to reason from.
    """
    _render_and_echo(format_name=OutputFormat.TEXT.value, payload=None, lines=(line,))


@cache
def _live_action_input_schema(command_key: str) -> VerbInputSchema:
    """Resolve one action target through the command-spec input authority."""
    from ._verb_input_schema import build_verb_input_schemas

    return build_verb_input_schemas((command_key,))[command_key]


def _resolve_notice_actions(notices: Sequence[Notice] | None) -> tuple[Notice, ...]:
    """Join success-notice actions to their live CLI paths before presentation."""
    from ...application.operator_actions import lookup_action
    from ...core.json_contract import ResolvedNoticeAction

    resolved: list[Notice] = []
    for notice in notices or ():
        notice_action = notice.action
        if not isinstance(notice_action, ResolvedNoticeAction):
            resolved.append(notice)
            continue
        action = notice_action.action
        declaration = lookup_action(action.action_id)
        if declaration.target_command_key != action.target_command_key:
            raise ValueError(
                f"notice action target contradicts catalogue: {action.action_id} -> {action.target_command_key}",
            )
        schema = _live_action_input_schema(action.target_command_key)
        parameter_names = {parameter.name for parameter in schema.parameters}
        argument_names = {binding.argument_name for binding in notice_action.argument_bindings}
        if not argument_names <= parameter_names:
            raise ValueError(
                f"notice action arguments do not exist on live target {action.target_command_key}: "
                f"{tuple(sorted(argument_names - parameter_names))}",
            )
        resolved.append(
            notice.model_copy(
                update={
                    "action": notice_action.model_copy(
                        update={"action": action.model_copy(update={"cli_path": schema.cli_path})},
                    ),
                },
            ),
        )
    return tuple(resolved)


_SAFE_ACTION_TOKEN = re.compile(r"^[A-Za-z0-9._:/=@+-]+$")


def _powershell_action_token(token: str) -> str:
    """Render one argv token as a PowerShell literal without enabling expansion.

    PowerShell expands ``$()``, ``$env:...`` and backticks inside double-quoted
    strings, so JSON string quoting is not a safe copy/paste representation on
    the supported Windows shell. Single-quoted strings are literal there; an
    embedded apostrophe is represented by two apostrophes.
    """
    if _SAFE_ACTION_TOKEN.fullmatch(token):
        return token
    return "'" + token.replace("'", "''") + "'"


def _action_text_lines(notices: Sequence[Notice]) -> tuple[str, ...]:
    """Derive executable text commands from the same resolved action DTOs as JSON."""
    from ...core.json_contract import ResolvedNoticeAction
    from ...core.product_identity import PRODUCT_IDENTITY
    from ._verb_input_schema import cli_argv_for

    lines: list[str] = []
    for notice in notices:
        notice_action = notice.action
        if not isinstance(notice_action, ResolvedNoticeAction):
            continue
        action = notice_action.action
        if action.cli_path is None:
            continue
        schema = _live_action_input_schema(action.target_command_key)
        arguments: dict[str, object] = {
            binding.argument_name: binding.value for binding in notice_action.argument_bindings
        }
        argv = cli_argv_for(schema, arguments)[2:]
        rendered = " ".join(_powershell_action_token(token) for token in argv)
        lines.append(f"next_action\t{PRODUCT_IDENTITY.cli_executable} {rendered}")
    return tuple(lines)


def notice_lines(notices: Sequence[Notice]) -> tuple[str, ...]:
    """Render envelope notices as the matching machine-parsable text lines.

    Text mode receives no ``notices`` channel of its own, so a command that
    passes notices to :func:`emit_envelope` and does not fold the same values
    into its ``lines`` emits a diagnostic in JSON that is simply absent from the
    terminal. Rebuilding the line from the notice itself is what stops the two
    surfaces drifting: the code and the message are the notice's, never a second
    sentence written beside it.

    This is the tab-separated transport form every ``app`` surface uses. The
    config storage surface renders its own wrapped, severity-labelled block
    instead; that is a presentation choice for a human-read report and is not
    substitutable here, where the line is parsed.
    """
    return tuple(f"notice\t{notice.code}\t{notice.message}" for notice in notices)


def emit_envelope(
    ctx: typer.Context,
    *,
    command: str,
    result: object,
    lines: Iterable[str],
    notices: Sequence[Notice] | None = None,
    metadata_only: bool = False,
) -> None:
    """Render a typed result through JSON or text output.

    JSON mode goes through :func:`~cadrumo.application.operator_output.emit_operator_json_success`
    so the payload is wrapped in the shared
    :class:`SchemaEnvelope` spine
    ``{"schema_version": ..., "command": ..., "status": ..., "result": ...,
    "notices": ...}``; ``status`` is derived from the supplied notice
    severities. Text mode keeps the existing line iterator unchanged so
    terminal output is unaffected.

    When the active profile bucket is a sandbox
    (:func:`~cadrumo.application.bucket_maintenance.is_sandbox_label`), a
    persistent info :class:`Notice` naming the sandbox is prepended to
    ``notices`` (JSON mode, via
    :func:`~cadrumo.application.operator_output.emit_operator_json_success`)
    and a matching banner line is prepended ahead of ``lines`` (text mode),
    so an operator can never mistake a sandbox run for a run against the
    real profile. The indicator is resolved by
    :func:`~cadrumo.application.operator_output.sandbox_notice_for_active_bucket`,
    shared with the setup wizard's own success emitters
    (:mod:`cadrumo.application.wizard.commands`), which sit below this CLI
    package and route through the same funnel rather than a second
    implementation.

    Args:
        ctx: Typer context (used to discover the requested output format).
        command: Stable command path string (matches the
            the CommandSpec result-schema identity argument on the result model).
        result: The strict-validated payload model to surface as
            ``envelope.result``. Must be a pydantic model registered
            under ``command`` in
            the command-spec graph; the CLI
            conformance gate enforces this at test time.
        lines: Iterable of pre-formatted text lines (used unchanged
            for text mode).
        notices: Optional typed :class:`Notice`
            diagnostics surfaced on the envelope's ``notices`` channel.
            The text-mode rendering is unchanged; callers fold the same
            notices into ``lines`` themselves so JSON and text cannot
            drift.
        metadata_only: Skip profile notices, action resolution, and sandbox
            discovery for a callback that only renders command metadata.
    """
    metadata_invocation = metadata_only or _is_metadata_invocation(ctx)
    output_format = _format_of(ctx)
    supplied_notices = tuple(notices or ())
    if metadata_invocation:
        resolved_notices = supplied_notices
    else:
        from ._profile_authentication_notice import drain_profile_authentication_notices

        supplied_notices = (*supplied_notices, *drain_profile_authentication_notices())
        resolved_notices = _resolve_notice_actions(supplied_notices)
    if output_format is OutputFormat.JSON:
        if metadata_invocation:
            # The ``--help`` / ``--version`` fast path stays off the
            # sandbox/active-profile resolution entirely — active_profile is
            # forced to ``None`` and no sandbox lookup runs, matching the
            # existing metadata-invocation contract, and it never imports
            # ``application.operator_output`` at all. This is the one
            # documented direct call to the low-level primitive, allowlisted
            # in test_json_schema_conformance.py.
            from ...core.json_contract import emit_json_success

            emit_json_success(command, result, notices=resolved_notices, active_profile=None)
            return
        from ...application.operator_output import emit_operator_json_success

        active_profile = active_profile_label()
        emit_operator_json_success(command, result, notices=resolved_notices, active_profile=active_profile)
        return
    # Route non-JSON paths through render_command_output so unsupported
    # ``--format`` values (e.g. ``xml``) raise the shared refusal contract.
    # ``render_command_output``
    # ignores ``payload`` outside JSON mode and emits the line iterator.
    if metadata_invocation:
        rendered_lines = tuple(lines)
    else:
        rendered_lines = (*lines, *notice_lines(resolved_notices), *_action_text_lines(resolved_notices))
        from ...application.operator_output import sandbox_banner_line, sandbox_notice_for_active_bucket

        sandbox_notice = sandbox_notice_for_active_bucket()
        if sandbox_notice is not None:
            rendered_lines = (sandbox_banner_line(sandbox_notice), *rendered_lines)
    _render_and_echo(format_name=output_format.value, payload=result, lines=rendered_lines)


def resolve_notice_action(
    *,
    action: ActionReference,
    argument_bindings: tuple[ResolvedActionArgument, ...] = (),
) -> ResolvedNoticeAction:
    """Resolve a fully materialised successful notice action against the live CLI.

    This is the sole entrypoint bridge for successful ``Notice.action`` values.
    It derives the current result-schema, Click/S05 input, mounted-family,
    profile-policy, and external projections, then delegates all action validation
    to the application-owned resolver.  Producers therefore supply only their
    stable action identity and provenance-bearing concrete values; they cannot
    hand-assemble a wire action or silently omit a live required input.
    """
    from ...application.operator_actions import OPERATOR_ACTION_CATALOGUE
    from ...application.operator_surface import resolve_notice_action as resolve_application_notice_action

    resolved = resolve_application_notice_action(
        action=action,
        argument_bindings=argument_bindings,
        catalogue=OPERATOR_ACTION_CATALOGUE,
        reconciliation=current_operator_surface_reconciliation(),
    )
    schema = _live_action_input_schema(resolved.action.target_command_key)
    return resolved.model_copy(
        update={"action": resolved.action.model_copy(update={"cli_path": schema.cli_path})},
    )


def resolve_lifecycle_continuation_notice(continuation: ModeloWorkLifecycleContinuation) -> Notice:
    """Project an application-owned lifecycle continuation through the live action resolver."""
    action = None
    if continuation.action is not None:
        action = resolve_notice_action(
            action=continuation.action,
            argument_bindings=tuple(
                ResolvedActionArgument(
                    argument_name=binding.argument_name,
                    status=binding.status,
                    value=binding.value,
                    source=binding.source,
                    source_key=binding.source_key,
                    source_evidence_id=binding.source_evidence_id,
                )
                for binding in continuation.argument_bindings
            ),
        )
    context = {key: str(value) for key, value in continuation.evidence.values.items()}
    context["continuation_outcome"] = (
        "action_available" if continuation.no_recovery_outcome is None else continuation.no_recovery_outcome.value
    )
    return Notice(
        severity=NoticeSeverity.INFO,
        code=continuation.notice_code,
        message=tr(continuation.summary_locale_key, **continuation.evidence.values),
        action=action,
        context=context,
    )


def active_profile_label() -> str | None:
    """Return the active taxpayer profile's display label, or ``None``.

    Resolves the active bucket id through the same core precedence chain
    every command uses (:func:`~cadrumo.core.bucket_pointer.resolve_active_bucket_id`), then
    resolves its live plaintext manifest label
    (:func:`~cadrumo.application.workflow.resolve_profile_bucket`) — the
    same non-secret display name
    :func:`~cadrumo.application.operator_output.sandbox_notice_for_active_bucket`
    reads,
    never opening the encrypted per-bucket database and never touching the
    redacted profile/bucket UUID. Returns ``None`` when no profile is
    active, Cadrumo has rejected a legacy product-state location, or the manifest is
    absent, unreadable, or fails strict validation, so a non-profile-bound
    command and a degraded manifest both leave the envelope spine's
    ``active_profile`` null rather than breaking the emit. This is the identity anchor injected at the CLI
    transport boundary because the ``core`` layer that builds the envelope
    (:func:`~cadrumo.core.json_contract.emit_json_success`) never scans
    profile manifests.
    """
    from ...adapters.persistence.storage import StorageValidationError
    from ...application.workflow.profile_bucket_scan import resolve_profile_bucket
    from ...core import FormerProductStateError
    from ...core.bucket_pointer import resolve_active_bucket_id

    try:
        bucket_id = resolve_active_bucket_id()
        if bucket_id is None:
            return None
        pointer = resolve_profile_bucket(bucket_id)
    except (FormerProductStateError, StorageValidationError):
        return None
    return pointer.label if pointer is not None else None


def _bad(message: str) -> typer.BadParameter:
    return typer.BadParameter(message)


bad = _bad


def _no_active_profile_refusal() -> Exception:
    """Return the canonical no-active-profile refusal exception.

    A missing active profile is a workflow-state refusal, not a
    user-input error: it must read as ``Refused. No active profile…``
    rather than be wrapped in a Click ``Invalid value:`` header. Every
    cold-start command path — ledger, modelo work, overview — raises
    this same translated refusal so first-contact guidance is
    consistent across the CLI surface.

    The suggested next command distinguishes "no profile registered at
    all" (suggest create) from "at least one profile is registered but
    none is active" (suggest login), so an operator who has already
    created a profile and merely logged out is never told to create a
    second one. ``list_profile_buckets`` reads only manifest files and
    never unlocks a bucket, so this check is cheap.
    """
    from ...application.profile_preconditions import inspect_active_profile_precondition
    from ...application.workflow.profile_bucket_scan import list_profile_buckets
    from .errors import CliRefusedBoundaryError

    registered_profile_count = len(list_profile_buckets())
    verdict = inspect_active_profile_precondition(
        active_profile_present=False,
        registered_profile_count=registered_profile_count,
    )
    if verdict is None:
        raise RuntimeError("no-active-profile refusal did not produce a failed verdict")
    # Each branch calls tr() with a literal key so the locale scaffold's
    # static discovery can find both keys; a single tr(variable) call would
    # be invisible to that AST-literal scan and the second key would never
    # get scaffolded across the four catalogues.
    if registered_profile_count:
        error = CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile_registered"))
    else:
        error = CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    return attach_cli_policy_verdict(error, verdict=verdict)


no_active_profile_refusal = _no_active_profile_refusal


def _state() -> WorkflowState:
    from ...application.workflow.persistence import workflow_state_repository
    from ...core.bucket_pointer import resolve_active_bucket_id

    # Without an active profile there is no bucket database to open;
    # workflow_state_repository().load() would raise a raw StorageError
    # ("cadrumo_database_url is empty") that leaks internal plumbing to the
    # operator. Refuse early with the operator-facing no-active-profile
    # message instead.
    if resolve_active_bucket_id() is None:
        raise _no_active_profile_refusal()
    return workflow_state_repository().load()


def _label_for(listing: AuthProviderListing) -> str:
    return _translate(listing.label)


def _translate(translatable: str) -> str:
    """Render a str in the operator's preferred locale (Spanish first)."""
    from ...core.i18n import tr

    return tr(translatable)


def resolve_optional_root(value: Path | None, default: Callable[[], Path]) -> Path:
    """Resolve an optional ``--*-root`` Typer option to its declared default.

    Shared by every optional-root option that falls back to a bundled data
    path or a :class:`~cadrumo.core.config.Settings` field when the operator
    supplies no override. ``default`` is invoked ONLY when ``value`` is
    ``None``, so a settings-backed default never triggers a settings load on
    the common override path.
    """
    return value if value is not None else default()


def resolve_pull_year_range(
    *,
    year: int | None,
    year_from: int | None,
    year_to: int | None,
) -> tuple[int, int]:
    """Resolve mutually exclusive single-year and inclusive range pull options."""
    if year is not None and (year_from is not None or year_to is not None):
        raise typer.BadParameter("use --year for a single-year pull or --from-year/--to-year for a range, not both")
    if year is not None:
        return year, year
    if year_from is None and year_to is None:
        raise typer.BadParameter("either --year or both --from-year and --to-year are required")
    if year_from is None or year_to is None:
        raise typer.BadParameter("--from-year and --to-year must be supplied together")
    if year_from > year_to:
        raise typer.BadParameter("--from-year must be less than or equal to --to-year")
    return year_from, year_to


def _profile_to_taxpayer(state: WorkflowState) -> TaxpayerProfile:
    from ...application.user_profile.projections import projection_for_taxpayer

    record = state.active_profile_record()
    if record is None:
        return projection_for_taxpayer({})
    return projection_for_taxpayer(record)


def _declared_tax_id(record: UserProfileRecord | None) -> str:
    """Return the ``identity.tax_id`` fact declared on a :class:`UserProfileRecord`.

    Returns ``""`` when the record is absent or carries no such fact.

    Deliberately NOT routed through :func:`_profile_to_taxpayer`. That projection
    substitutes a synthetic placeholder NIF for an absent identity, which reads
    downstream as a declared value and cannot be told apart from one. A caller
    that compares the operator's identity against stored AEAT evidence needs the
    absence to survive, so this returns the empty string and lets the owning
    application service raise its own grounded refusal naming the missing fact.
    """
    from ...application.user_profile.projections import fact_value

    return (fact_value(record, "identity.tax_id") or "").strip()


_TAX_ID_SELECTOR = "tax.id"


def _filing_taxpayer_or_refuse(state: WorkflowState) -> TaxpayerProfile:
    """Return the taxpayer projection for a FILING-grade command, or refuse.

    :func:`_profile_to_taxpayer` substitutes a synthetic placeholder NIF when the
    operator has declared none, and that placeholder is checksum-valid, so it is
    indistinguishable downstream from a real declared identity. On a read-only
    surface that substitution is deliberate and load-bearing - the calendar must
    not drop a taxpayer's filed evidence merely because their NIF is undeclared.
    On a filing surface it is the opposite of what is wanted: the value is written
    into the exported bytes as the declarant, so an operator who never entered
    their NIF would receive a file identifying them as somebody else.

    This is the filing boundary the two populations were missing. Read-only
    callers keep using :func:`_profile_to_taxpayer` directly; every command that
    writes or packages a declaration routes through here, so absence refuses
    once rather than at each call site.
    """
    from ...application.profile_preconditions import inspect_filing_taxpayer_identity_precondition
    from ...application.user_profile.preflight import format_profile_selector_requirements
    from ...domain.calculations.registry.profile_grounding import build_profile_grounding_index
    from ...domain.user_profile.loader import load_user_profile_schema
    from .errors import CliRefusedBoundaryError

    record = state.active_profile_record()
    # The registry authority is reached only on this refusal path, so it is
    # imported here rather than at module scope: `_common` is loaded by the
    # CLI bootstrap, and a module-level edge made every command -- including
    # every state-free one -- pay for the whole calculation registry.
    from ...domain.calculations.registry.authority import bundled_authority as _bundled_authority

    verdict = inspect_filing_taxpayer_identity_precondition(
        declared_tax_id=_declared_tax_id(record),
        profile_name=record.profile_id if record is not None else None,
    )
    if verdict is not None:
        raise attach_cli_policy_verdict(
            CliRefusedBoundaryError(
                translated_message="cli.common.errors.filing_requires_declared_tax_id",
                context={
                    "requirements": ", ".join(
                        format_profile_selector_requirements(
                            [_TAX_ID_SELECTOR],
                            schema=load_user_profile_schema(),
                            grounding_index=build_profile_grounding_index(_bundled_authority()),
                        ),
                    ),
                },
            ),
            verdict=verdict,
        )
    return _profile_to_taxpayer(state)


# ---------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------


def active_bucket_id_or_refuse() -> str:
    """Return the active profile bucket id or raise the canonical no-active-profile refusal.

    Stateless single source for the cold-start bucket-id guard shared across
    bucket-bound CLI command families. :func:`_active_bucket_id_or_bad`
    delegates here.
    """
    from ...core.bucket_pointer import require_active_bucket_id
    from ...core.errors import NoActiveProfileError

    try:
        return require_active_bucket_id()
    except NoActiveProfileError as exc:
        raise _no_active_profile_refusal() from exc


def _active_bucket_id_or_bad(state: WorkflowState) -> str:
    """Return the active profile bucket id or raise the CLI 'bad' error."""
    return active_bucket_id_or_refuse()


def _tx_repo(state: WorkflowState) -> TransactionCatalogueRepository:
    from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ...application.workflow.active_profile import active_transaction_catalogue_repository
    from ...domain.transactions import LedgerNoActiveBucketError

    try:
        return active_transaction_catalogue_repository(
            repository_factory=lambda bucket_id: TransactionCatalogueRepository(bucket_id=bucket_id),
        )
    except LedgerNoActiveBucketError as exc:
        raise _no_active_profile_refusal() from exc


def _invoice_repo(*, bucket_id: str | None = None) -> InvoiceCatalogueRepository:
    from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository

    return InvoiceCatalogueRepository(bucket_id=bucket_id)


def _draft_repo(*, bucket_id: str | None = None) -> ModeloDraftRepository:
    from ...adapters.persistence.profile.filing_drafts import ModeloDraftRepository

    return ModeloDraftRepository(bucket_id=bucket_id)


def _load_transactions(state: WorkflowState) -> TransactionCatalogue:
    return _tx_repo(state).load()


def _load_invoices() -> InvoiceCatalogue:
    return _invoice_repo().load()


def _load_drafts() -> tuple[ModeloDraft, ...]:
    repo = _draft_repo()
    return tuple(repo.iter_drafts())


def _draft_by_id(draft_id: str) -> ModeloDraft:
    for draft in _load_drafts():
        if draft.draft_id == draft_id:
            return draft
    raise _bad(tr("cli.common.errors.draft_id_not_found", draft_id=draft_id))


# ---------------------------------------------------------------------
# Output-language override
# ---------------------------------------------------------------------


def activate_subcommand_output_language(ctx: typer.Context, language: OutputLanguage | None) -> None:
    """Apply a subcommand-supplied ``--output-language`` to the render path.

    ``--output-language`` on a subcommand short-circuits the root
    callback's ``--language`` flow; rather than re-parsing, override the
    Settings field directly and drop the cached language so any ``tr()``
    fired during the verb body resolves to the requested locale.
    """
    if language is None:
        return
    from ...core.config import override_settings
    from ...core.i18n import clear_output_language_cache

    ctx.with_resource(override_settings(cadrumo_output_language=language))
    clear_output_language_cache()
