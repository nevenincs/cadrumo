"""A verdict leaving its process names every offered action in served words and routes it by operation."""

from __future__ import annotations

import json
import re

import pytest
from pydantic import BaseModel

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ...operations.error_detail import served_words_language
from ...operations.public_mirror import project_public_mirror, restore_public_mirror
from ...workbench_generation_modelo_contracts import PublicPreconditionVerdict
from ..catalogue import OPERATOR_ACTION_CATALOGUE
from ..models import (
    ActionReference,
    AlternativeRecoveryAction,
    ConditionEvidence,
    PreconditionVerdict,
)
from ..projection import PreconditionVerdictSnapshot
from ..served_actions import ACTION_WORDS_LOCALE_KEYS, NO_RECOVERY_WORDS_LOCALE_KEYS, serve_precondition_verdict

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CALCULATE = "operator.modelo.work.calculate"
_OVERRIDE_WALLET = "operator.modelo.iva_wallet.override"
_LIST_PROFILES = "operator.profile.list"
_COMMAND_TEXT = re.compile(r"(?:^|[\s`'\"])aeat\s")
_SERVED_FIELDS = ("action_words", "action_words_language", "target_operation_ids")


def _evidence() -> tuple[ConditionEvidence, ...]:
    return (
        ConditionEvidence(
            condition_id="modelo.work.calculated",
            evidence_id="modelo.work.calculated.state",
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            values={"calculated": False},
        ),
    )


def _actionable(primary: str, *alternatives: str) -> PreconditionVerdict:
    return PreconditionVerdict(
        failed_condition_id="modelo.work.calculated",
        evidence=_evidence(),
        action=ActionReference(action_id=primary),
        conditionality=ActionConditionality.IMMEDIATE,
        alternative_actions=tuple(
            AlternativeRecoveryAction(
                action=ActionReference(action_id=item), conditionality=ActionConditionality.IMMEDIATE
            )
            for item in alternatives
        ),
    )


def _closed(outcome: NoRecoveryOutcome) -> PreconditionVerdict:
    return PreconditionVerdict(
        failed_condition_id="modelo.work.calculated",
        evidence=_evidence(),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=outcome,
    )


def _catalogue_words(key: str, language: OutputLanguage) -> str:
    words = lookup_translation(key, locale=language.value)
    assert words is not None, f"{language.value} has no words for {key}"
    return words


def test_every_catalogue_action_has_one_words_key_worded_in_every_locale() -> None:
    action_ids = {entry.action_id for entry in OPERATOR_ACTION_CATALOGUE.entries}

    assert set(ACTION_WORDS_LOCALE_KEYS) == action_ids
    assert len(set(ACTION_WORDS_LOCALE_KEYS.values())) == len(action_ids)
    for key in ACTION_WORDS_LOCALE_KEYS.values():
        for language in OutputLanguage:
            words = _catalogue_words(key, language)
            assert words.strip() == words
            assert "%{" not in words
            assert _COMMAND_TEXT.search(words) is None


def test_every_no_recovery_outcome_has_a_sentence_in_every_locale() -> None:
    assert set(NO_RECOVERY_WORDS_LOCALE_KEYS) == set(NoRecoveryOutcome)
    for key in NO_RECOVERY_WORDS_LOCALE_KEYS.values():
        for language in OutputLanguage:
            _catalogue_words(key, language)


def test_each_offered_action_crosses_the_snapshot_with_its_words_language_and_operations() -> None:
    language = served_words_language()
    snapshot = PreconditionVerdictSnapshot.from_verdict(_actionable(_CALCULATE, _OVERRIDE_WALLET, _LIST_PROFILES))

    document = json.loads(snapshot.model_dump_json())

    assert document["action_words"] == _catalogue_words(ACTION_WORDS_LOCALE_KEYS[_CALCULATE], language)
    assert document["action_words_language"] == language.value
    assert document["target_operation_ids"] == ["modelo.work.calculate", "modelo.work.metadata"]
    override, listing = document["alternative_actions"]
    assert override["action_words"] == _catalogue_words(ACTION_WORDS_LOCALE_KEYS[_OVERRIDE_WALLET], language)
    assert override["action_words_language"] == language.value
    assert override["target_operation_ids"] == ["modelo.iva-wallet.override"]
    assert listing["action_words"] == _catalogue_words(ACTION_WORDS_LOCALE_KEYS[_LIST_PROFILES], language)
    assert "target_operation_ids" not in listing
    assert "no_recovery_words" not in document
    assert PreconditionVerdictSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot


def test_a_verdict_without_a_way_out_crosses_the_snapshot_with_its_sentence() -> None:
    language = served_words_language()
    for outcome in NoRecoveryOutcome:
        document = json.loads(PreconditionVerdictSnapshot.from_verdict(_closed(outcome)).model_dump_json())

        assert document["no_recovery_words"] == _catalogue_words(NO_RECOVERY_WORDS_LOCALE_KEYS[outcome], language)
        assert document["no_recovery_words_language"] == language.value
        assert not set(_SERVED_FIELDS) & set(document)


def test_words_follow_the_language_they_are_served_in() -> None:
    for language in OutputLanguage:
        served = serve_precondition_verdict(_actionable(_CALCULATE, _OVERRIDE_WALLET), language)

        assert served.action_words == _catalogue_words(ACTION_WORDS_LOCALE_KEYS[_CALCULATE], language)
        assert served.action_words_language is language
        assert served.alternative_actions[0].action_words_language is language


def test_an_action_outside_the_catalogue_is_served_as_absent() -> None:
    document = json.loads(PreconditionVerdictSnapshot.from_verdict(_actionable("profile.select")).model_dump_json())

    assert not set(_SERVED_FIELDS) & set(document)


def test_served_words_survive_the_workbench_mirror() -> None:
    language = served_words_language()
    verdict = _actionable(_CALCULATE, _OVERRIDE_WALLET)

    def serve(item: BaseModel) -> BaseModel:
        assert isinstance(item, PreconditionVerdict)
        return serve_precondition_verdict(item, language)

    projected = project_public_mirror(
        verdict,
        PreconditionVerdict,
        PublicPreconditionVerdict,
        served={PreconditionVerdict: serve},
    )
    assert isinstance(projected, PublicPreconditionVerdict)
    transported = PublicPreconditionVerdict.model_validate_json(projected.model_dump_json())
    restored = restore_public_mirror(transported, PreconditionVerdict, PublicPreconditionVerdict)

    assert projected.target_operation_ids == ("modelo.work.calculate", "modelo.work.metadata")
    assert projected.alternative_actions[0].action_words is not None
    assert restored == serve_precondition_verdict(verdict, language)


def test_served_words_name_their_language_and_belong_to_an_offered_action() -> None:
    with pytest.raises(ValueError, match="name the language"):
        PreconditionVerdict.model_validate(_actionable(_CALCULATE).model_dump() | {"action_words": "x"})
    with pytest.raises(ValueError, match="require a recovery action"):
        PreconditionVerdict.model_validate(
            _closed(NoRecoveryOutcome.TERMINAL).model_dump() | {"target_operation_ids": ("modelo.work.calculate",)}
        )
    with pytest.raises(ValueError, match="require a no-recovery outcome"):
        PreconditionVerdict.model_validate(
            _actionable(_CALCULATE).model_dump()
            | {"no_recovery_words": "x", "no_recovery_words_language": OutputLanguage.EN}
        )
