"""Application-owned outcomes for CLI exception boundaries.

Exception boundaries observe a transport failure but must not manufacture a
copy-paste command from an error string.  This module gives those boundaries a
small closed policy vocabulary: each condition records its observed fact and
explicitly states that no executable recovery can be bound from that fact.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from enum import StrEnum

from pydantic import ValidationError

from ..core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from .operator_actions.models import PreconditionVerdict


def _registered_terminal_precondition_verdict(current: BaseException) -> PreconditionVerdict | None:
    """Extract one registered terminal verdict from a single exception."""
    from ..core.errors.error_codes import get_registered_error_code
    from ..core.errors.hierarchy import CadrumoError, CoreValidationError
    from ..core.optional_extras import MissingOptionalExtraError

    if not isinstance(current, CadrumoError):
        return None
    try:
        get_registered_error_code(current)
    except ValueError:
        return None

    verdict = getattr(current, "terminal_precondition_verdict", None)
    if isinstance(verdict, PreconditionVerdict):
        return verdict
    if isinstance(current, MissingOptionalExtraError):
        return cli_exception_no_recovery_verdict(
            CliExceptionPrecondition.OPTIONAL_EXTRA_IMPORTABLE,
            facts={
                "extra": current.extra.extra,
                "import_name": current.extra.import_name,
                "importable": False,
            },
        )
    if (
        isinstance(current, CoreValidationError)
        and current.context is not None
        and current.context.get("section") == "aeat.pre303"
    ):
        return cli_exception_no_recovery_verdict(
            CliExceptionPrecondition.EXTERNAL_CONSTANTS_SECTION_VALID,
            facts={"section": "aeat.pre303", "valid": False},
        )
    return None


def _nested_exception_links(current: BaseException) -> Iterator[BaseException]:
    """Yield structural nested and causal links in traversal order."""
    if isinstance(current, ValidationError):
        for detail in current.errors(include_url=False):
            context = detail.get("ctx")
            nested = context.get("error") if isinstance(context, dict) else None
            if isinstance(nested, BaseException):
                yield nested
    if current.__cause__ is not None:
        yield current.__cause__
    if current.__context__ is not None:
        yield current.__context__


def nested_terminal_precondition_verdict(error: BaseException) -> PreconditionVerdict | None:
    """Return one unambiguous registered typed verdict nested in ``error``.

    Pydantic retains exceptions raised by validators at
    ``errors()[...]["ctx"]["error"]``.  The shared CLI boundary cannot use the
    rendered validation message to recover that identity, so this traversal
    follows only exception-bearing structural links: Pydantic contexts and
    Python causal chains.  Exactly one registered exception carrying a valid
    terminal verdict is admitted; zero or multiple candidates fail closed to
    the generic validation outcome.
    """
    pending: list[BaseException] = [error]
    seen: set[int] = set()
    candidates: dict[int, PreconditionVerdict] = {}
    while pending:
        current = pending.pop()
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)

        verdict = _registered_terminal_precondition_verdict(current)
        if verdict is not None:
            candidates[identity] = verdict
        pending.extend(_nested_exception_links(current))

    if len(candidates) != 1:
        return None
    return next(iter(candidates.values()))


def cli_exception_envelope_view(error: BaseException) -> BaseException:
    """Return the narrow envelope-safe view for the exception producer families."""
    from ..core.errors.error_codes import get_registered_error_code
    from ..core.errors.hierarchy import CadrumoError, CoreValidationError
    from ..core.optional_extras import MissingOptionalExtraError

    if isinstance(error, MissingOptionalExtraError):
        safe_context: Mapping[str, object] = {
            "extra": error.extra.extra,
            "import_name": error.extra.import_name,
            "importable": False,
        }
    elif (
        isinstance(error, CoreValidationError)
        and error.context is not None
        and error.context.get("section") == "aeat.pre303"
    ):
        safe_context = {
            "section": "aeat.pre303",
            "validation_error_type": (
                type(error.__cause__).__name__ if error.__cause__ is not None else "ValidationError"
            ),
        }
    else:
        return error

    code = get_registered_error_code(error)
    view = BaseException.__new__(type(error))
    assert isinstance(view, CadrumoError)
    view.__dict__.update(error.__dict__)
    for attribute in ("extra", "name", "path"):
        view.__dict__.pop(attribute, None)
    view.args = (code.message_key,)
    view.translated_message = code.message_key
    view.context = dict(safe_context)
    return view


class CliExceptionPrecondition(StrEnum):
    """Closed failed-condition identities for the CLI exception slice."""

    VALIDATION_BOUNDARY = "cli.validation.boundary_clean"
    UNEXPECTED_BOUNDARY = "cli.runtime.unexpected_absent"
    STORED_DATA_VALID = "cli.storage.persisted_data_valid"
    COMMAND_GROUP_AVAILABLE = "cli.command_group.available"
    REFUSAL_RETRIED = "cli.refusal.completed"
    CONFIG_BOUNDARY = "cli.config.boundary_clean"
    STDIN_INTERACTIVE = "cli.stdin.interactive"
    LOGIN_COMPLETED = "cli.profile.login.completed"
    ACTIVE_BUCKET_SELECTED = "storage.active_bucket.selected"
    ACTIVE_BUCKET_SESSION_AVAILABLE = "storage.active_bucket.session_available"
    RESUMED_SESSION_KEK_MATERIAL_AVAILABLE = "storage.resumed_session.kek_material_available"
    MASTER_KEY_MATERIAL_AVAILABLE = "storage.master_key.material_available"
    BUCKET_SESSION_UNLOCKED = "storage.bucket_session.unlocked"
    BUCKET_SESSION_FRESH = "storage.bucket_session.fresh"
    OVERVIEW_PROFILE_COMPLETE = "cli.overview.profile.complete"
    PROFILE_EXPORT_REQUEST_COMPLETE = "cli.profile.export_request.complete"
    PROFILE_IMPORT_PATH_SUPPLIED = "cli.profile.import_path.supplied"
    GOOGLE_CONFIGURATION_COMPLETE = "cli.google.configuration.complete"
    GOOGLE_MIRROR_REQUEST_COMPLETE = "cli.google.mirror_request.complete"
    LEDGER_CENSO_RATIO_CONSISTENT = "cli.ledger.censo_ratio.consistent"
    LEDGER_FILTER_VALID = "cli.ledger.filter.valid"
    LEDGER_TRANSACTION_ID_RESOLVES = "cli.ledger.transaction_id.resolves"
    LEDGER_TRANSACTION_VALID = "cli.ledger.transaction.valid"
    LEDGER_INVOICE_VALID = "cli.ledger.invoice.valid"
    OPTIONAL_EXTRA_IMPORTABLE = "provisioning.optional_extra.importable"
    EXTERNAL_CONSTANTS_SECTION_VALID = "cli.external_constants.section_valid"


def cli_exception_no_recovery_verdict(
    condition: CliExceptionPrecondition,
    *,
    facts: Mapping[str, str | int | bool],
    outcome: NoRecoveryOutcome = NoRecoveryOutcome.OPERATOR_DECISION,
) -> PreconditionVerdict:
    """Return one explicit non-actionable outcome for an exception boundary.

    The facts name what was observed, while the closed outcome prevents a CLI
    adapter from smuggling an unbound command template into a recovery field.
    """
    from .operator_actions.preconditions import no_action_precondition_verdict

    return no_action_precondition_verdict(
        condition_id=condition.value,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=outcome,
    )


__all__ = [
    "CliExceptionPrecondition",
    "cli_exception_envelope_view",
    "cli_exception_no_recovery_verdict",
    "nested_terminal_precondition_verdict",
]
