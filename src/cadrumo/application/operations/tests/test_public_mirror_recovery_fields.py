"""The workbench mirror carries a verdict's alternative actions and a review's verification digest."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import BaseModel

from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
)
from ....core.period import Period
from ...modelo.work_review import ModeloWorkProgress, ModeloWorkReview
from ...operator_actions.models import (
    ActionArgumentBinding,
    ActionReference,
    AlternativeRecoveryAction,
    ConditionEvidence,
    PreconditionVerdict,
)
from ...workbench_generation_modelo_contracts import (
    PublicAlternativeRecoveryAction,
    PublicModeloWorkReview,
    PublicPreconditionVerdict,
)
from ..public_mirror import project_public_mirror, restore_public_mirror

# The review is built without the registry, so the year only has to be coherent.
_YEAR = date.today().year

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _verdict(*alternatives: AlternativeRecoveryAction) -> PreconditionVerdict:
    return PreconditionVerdict(
        failed_condition_id="profile.active",
        evidence=(
            ConditionEvidence(
                condition_id="profile.active",
                evidence_id="profile.active.selection",
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                values={"profile_key": "operator"},
            ),
        ),
        action=ActionReference(action_id="profile.create"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name="profile_key",
                status=ActionArgumentStatus.RESOLVED,
                value="operator",
                source=ActionArgumentSource.CONDITION_EVIDENCE,
                source_key="profile_key",
                source_evidence_id="profile.active.selection",
            ),
        ),
        conditionality=ActionConditionality.IMMEDIATE,
        alternative_actions=alternatives,
    )


def _round_trip(value: BaseModel, canonical: type[BaseModel], public: type[BaseModel]) -> tuple[BaseModel, object]:
    projected = project_public_mirror(value, canonical, public)
    assert isinstance(projected, public)
    transported = public.model_validate_json(projected.model_dump_json())
    return projected, restore_public_mirror(transported, canonical, public)


def test_alternative_actions_cross_the_mirror_in_offered_order() -> None:
    verdict = _verdict(
        AlternativeRecoveryAction(
            action=ActionReference(action_id="profile.select"), conditionality=ActionConditionality.IMMEDIATE
        ),
        AlternativeRecoveryAction(
            action=ActionReference(action_id="profile.attest"),
            argument_bindings=(ActionArgumentBinding(argument_name="value", status=ActionArgumentStatus.MISSING),),
            missing_argument_names=("value",),
            conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
        ),
    )
    projected, restored = _round_trip(verdict, PreconditionVerdict, PublicPreconditionVerdict)
    assert isinstance(projected, PublicPreconditionVerdict)
    assert all(isinstance(item, PublicAlternativeRecoveryAction) for item in projected.alternative_actions)
    assert [item.action.action_id for item in projected.alternative_actions] == ["profile.select", "profile.attest"]
    assert projected.alternative_actions[1].missing_argument_names == ("value",)
    assert restored == verdict


def test_a_verdict_without_alternatives_keeps_its_published_shape() -> None:
    verdict = _verdict()
    projected, restored = _round_trip(verdict, PreconditionVerdict, PublicPreconditionVerdict)
    assert isinstance(projected, PublicPreconditionVerdict)
    assert projected.alternative_actions == ()
    assert "alternative_actions" not in projected.model_dump(mode="json")
    assert restored == verdict


@pytest.mark.parametrize("digest", ["a" * 64, None])
def test_verification_sources_digest_crosses_the_mirror(digest: str | None) -> None:
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000453",
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        registry_revision_id=str(_YEAR),
        work_unit_id="d" * 64,
        calculation_revision_id=None,
        lifecycle_state=None,
        verification_outcome=None,
        verification_sources_digest=digest,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=(),
        findings=(),
        blockers=(),
    )
    projected, restored = _round_trip(review, ModeloWorkReview, PublicModeloWorkReview)
    assert isinstance(projected, PublicModeloWorkReview)
    assert projected.verification_sources_digest == digest
    assert restored == review
