"""Application-owned outcomes for CLI exception boundaries.

Exception boundaries observe a transport failure but must not manufacture a
copy-paste command from an error string.  This module gives those boundaries a
small closed policy vocabulary: each condition records its observed fact and
explicitly states that no executable recovery can be bound from that fact.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import ValidationError

from ..core import (
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from .operator_actions import (
    ConditionEvidence,
    PreconditionVerdict,
)


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
    from ..core import MissingOptionalExtraError
    from ..core.errors import CadrumoError, CoreValidationError, get_registered_error_code

    pending: list[BaseException] = [error]
    seen: set[int] = set()
    candidates: dict[int, PreconditionVerdict] = {}
    while pending:
        current = pending.pop()
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)

        if isinstance(current, CadrumoError):
            try:
                get_registered_error_code(current)
            except ValueError:
                pass
            else:
                verdict = getattr(current, "terminal_precondition_verdict", None)
                if isinstance(verdict, PreconditionVerdict):
                    candidates[identity] = verdict
                elif isinstance(current, MissingOptionalExtraError):
                    candidates[identity] = cli_exception_no_recovery_verdict(
                        CliExceptionPrecondition.OPTIONAL_EXTRA_IMPORTABLE,
                        facts={
                            "extra": current.extra.extra,
                            "import_name": current.extra.import_name,
                            "importable": False,
                        },
                    )
                elif (
                    isinstance(current, CoreValidationError)
                    and current.context is not None
                    and current.context.get("section") == "aeat.pre303"
                ):
                    candidates[identity] = cli_exception_no_recovery_verdict(
                        CliExceptionPrecondition.EXTERNAL_CONSTANTS_SECTION_VALID,
                        facts={"section": "aeat.pre303", "valid": False},
                    )

        if isinstance(current, ValidationError):
            for detail in current.errors(include_url=False):
                context = detail.get("ctx")
                nested = context.get("error") if isinstance(context, dict) else None
                if isinstance(nested, BaseException):
                    pending.append(nested)

        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)

    if len(candidates) != 1:
        return None
    return next(iter(candidates.values()))


def cli_exception_envelope_view(error: BaseException) -> BaseException:
    """Return the narrow envelope-safe view for S114 producer families."""
    from ..core import MissingOptionalExtraError
    from ..core.errors import CadrumoError, CoreValidationError, get_registered_error_code

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
    condition_id = condition.value
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            ConditionEvidence(
                condition_id=condition_id,
                evidence_id=f"{condition_id}.observation",
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                values=facts,
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=outcome,
    )


__all__ = [
    "CliExceptionPrecondition",
    "cli_exception_envelope_view",
    "cli_exception_no_recovery_verdict",
    "nested_terminal_precondition_verdict",
]
