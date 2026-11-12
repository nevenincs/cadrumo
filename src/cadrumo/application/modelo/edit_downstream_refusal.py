"""An edit refused after its values were admitted settles under the refusal that stopped it.

The edit's own refusal, "state the value again", is right only for a value the
edit refused. When the values were admitted and a later stage refused -- the
recalculation, or the authority it reads -- the operator needs that stage's
code, words and door. This module keeps exactly those, value-free, across the
edit contract and turns them back into the registered error the edit settles
under.
"""

from __future__ import annotations

import re
from typing import Final

from ...core.errors.error_codes import ErrorCode, get_registered_error_code
from ...core.errors.hierarchy import CadrumoError, RecordedRegisteredError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import extract_placeholders, lookup_translation
from ...core.operator_action_enums import (
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
)
from ..cli_exception_preconditions import nested_terminal_precondition_verdict
from ..operations.error_detail import UNWORDED_REGISTERED_ERROR_LOCALE_KEY
from ..operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict
from .edit_models import MODELO_EDIT_MESSAGE_KEY_PATTERN, ModeloEditDownstreamRefusalV1

#: The one evidence a value-free door states: the edit's values were admitted before the stage refused.
_DOOR_EVIDENCE_ID: Final[str] = "modelo.work.edit.downstream_refusal"


def _finished_in_every_language(key: str) -> bool:
    """Whether ``key`` is a catalogue key with a sentence in every served language that no value has to complete."""
    if re.fullmatch(MODELO_EDIT_MESSAGE_KEY_PATTERN, key) is None:
        return False
    for language in OutputLanguage:
        template = lookup_translation(key, locale=language.value)
        if template is None or extract_placeholders(template):
            return False
    return True


def _message_key(error: CadrumoError, registered: ErrorCode) -> str | None:
    """The key the refusal is worded by, chosen as the error envelope chooses it, if no value completes it.

    The error's own key comes first unless its code's registry entry owns the
    public message; then the code's catalogue key.
    """
    own = error.translated_message
    registry_owned = registered.public_message_from_registry or ".canonical_" in registered.message_key
    keys = (registered.message_key,) if registry_owned or own is None else (own, registered.message_key)
    return next((key for key in keys if _finished_in_every_language(key)), None)


def downstream_refusal(error: CadrumoError) -> ModeloEditDownstreamRefusalV1:
    """Keep the registered refusal a stage after value admission raised as its code, words and value-free door.

    An argument the refusal's verdict resolved from its own facts is kept by
    name only, as still to be given, because its value stays behind.
    """
    registered = get_registered_error_code(error)
    verdict = nested_terminal_precondition_verdict(error)
    if verdict is None:
        return ModeloEditDownstreamRefusalV1(error_code=registered.code, message_key=_message_key(error, registered))
    return ModeloEditDownstreamRefusalV1(
        error_code=registered.code,
        message_key=_message_key(error, registered),
        failed_condition_id=verdict.failed_condition_id,
        recovery_action=None if verdict.action is None else ActionReference(action_id=verdict.action.action_id),
        argument_names=tuple(binding.argument_name for binding in verdict.argument_bindings),
        no_recovery_outcome=verdict.no_recovery_outcome,
    )


def _door(refusal: ModeloEditDownstreamRefusalV1) -> PreconditionVerdict | None:
    """The refusal's door as a verdict whose one fact is that the edit's values were admitted."""
    condition = refusal.failed_condition_id
    if condition is None:
        return None
    evidence = (
        ConditionEvidence(
            condition_id=condition,
            evidence_id=_DOOR_EVIDENCE_ID,
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            values={"edit_values_admitted": True},
        ),
    )
    if refusal.recovery_action is None:
        return PreconditionVerdict(
            failed_condition_id=condition,
            evidence=evidence,
            no_recovery_outcome=refusal.no_recovery_outcome,
            conditionality=ActionConditionality.NOT_APPLICABLE,
        )
    names = refusal.argument_names
    return PreconditionVerdict(
        failed_condition_id=condition,
        evidence=evidence,
        action=refusal.recovery_action,
        argument_bindings=tuple(
            ActionArgumentBinding(argument_name=name, status=ActionArgumentStatus.MISSING) for name in names
        ),
        missing_argument_names=names,
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS if names else ActionConditionality.IMMEDIATE,
    )


def downstream_refusal_error(refusal: ModeloEditDownstreamRefusalV1) -> RecordedRegisteredError:
    """The registered error an edit settles under when a stage after value admission refused it.

    Without a key no value completes, the sentence names the refusal's code.
    """
    if refusal.message_key is None:
        return RecordedRegisteredError(
            refusal.error_code,
            translated_message=UNWORDED_REGISTERED_ERROR_LOCALE_KEY,
            context={"error_code": refusal.error_code},
            precondition_verdict=_door(refusal),
        )
    return RecordedRegisteredError(
        refusal.error_code, translated_message=refusal.message_key, precondition_verdict=_door(refusal)
    )


__all__ = ["downstream_refusal", "downstream_refusal_error"]
