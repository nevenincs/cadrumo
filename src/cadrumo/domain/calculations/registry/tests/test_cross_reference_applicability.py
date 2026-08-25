"""Tests for cross-reference applicability predicates.

Cross-reference decisions may declare profile predicates so surfaces such as
GROI for ROI-enrolled subjects or OSS for OSS-enrolled subjects are selected
only when the filing profile satisfies their official conditions.
"""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schedules import applicable_filing_schedules
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_verification import (
    LiveCrossReferenceDecision,
    ProfilePredicateDefinition,
)
from cadrumo.domain.calculations.registry.validate import RegistryValidator

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from ..live_parity import (
    CrossReferenceApplicability,
    evaluate_cross_reference_applicability,
)
from ..remote_state_guard import AEAT_WRITE_FORBIDDEN_ACTIONS
from ._registry_schema_support import _committed_modelo, _with_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_WWW2_HOST = aeat_host("www2")

_ROI_PREDICATE = ProfilePredicateDefinition(
    field="iva.roi_enrolled",
    op="equals",
    value=True,
    explanation="GROI consult requires ROI enrollment.",
    legal_refs=("orden-hac-174-2020:art-1",),
    source_refs=("aeat-modelo-349-procedure",),
)
_INTRACOM_PREDICATE = ProfilePredicateDefinition(
    field="does_intracomunitario",
    op="equals",
    value=True,
    explanation="GROI consult requires intracom operations.",
    legal_refs=("orden-eha-769-2010:art-1",),
    source_refs=("aeat-modelo-349-procedure",),
)


def _decision(
    *,
    applicability_predicates: tuple[ProfilePredicateDefinition, ...] = (),
    applicability_condition_mode: Literal["all", "any"] = "all",
) -> LiveCrossReferenceDecision:
    return LiveCrossReferenceDecision(
        id="probe-applicability",
        evidence_tier="executable_parity_evidence",
        surface="authenticated_simulator",
        guard_policy_id="probe-policy",
        allowed_hosts=(_WWW2_HOST,),
        allowed_methods=("GET", "POST"),
        forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS,
        synthetic_data_allowed=False,
        requires_authentication=True,
        requires_aeat_authorization=False,
        legal_refs=("orden-hac-174-2020:art-1",),
        source_refs=("aeat-modelo-349-procedure",),
        applicability_predicates=applicability_predicates,
        applicability_condition_mode=applicability_condition_mode,
    )


def test_decision_with_no_predicates_is_unconditionally_applicable() -> None:
    """A decision without predicates is unconditionally applicable."""

    result = evaluate_cross_reference_applicability(_decision(), profile_facts={})

    assert isinstance(result, CrossReferenceApplicability)
    assert result.applicable is True
    assert result.matched_explanations == ()
    assert result.unmet_predicate_fields == ()


def test_decision_with_all_mode_predicates_requires_every_match() -> None:
    """all-mode (the default) requires every predicate to be satisfied."""

    decision = _decision(applicability_predicates=(_ROI_PREDICATE, _INTRACOM_PREDICATE))

    fully_applicable = evaluate_cross_reference_applicability(
        decision,
        profile_facts={"iva": {"roi_enrolled": True}, "does_intracomunitario": True},
    )
    assert fully_applicable.applicable is True
    assert len(fully_applicable.matched_explanations) == 2
    assert fully_applicable.unmet_predicate_fields == ()

    partially_applicable = evaluate_cross_reference_applicability(
        decision,
        profile_facts={"iva": {"roi_enrolled": False}, "does_intracomunitario": True},
    )
    assert partially_applicable.applicable is False
    assert partially_applicable.unmet_predicate_fields == ("iva.roi_enrolled",)


def test_decision_with_any_mode_predicates_requires_at_least_one_match() -> None:
    """any-mode requires at least one predicate to be satisfied."""

    decision = _decision(
        applicability_predicates=(_ROI_PREDICATE, _INTRACOM_PREDICATE),
        applicability_condition_mode="any",
    )

    one_match = evaluate_cross_reference_applicability(
        decision,
        profile_facts={"iva": {"roi_enrolled": False}, "does_intracomunitario": True},
    )
    assert one_match.applicable is True
    assert one_match.matched_explanations == (_INTRACOM_PREDICATE.explanation,)
    assert one_match.unmet_predicate_fields == ("iva.roi_enrolled",)

    none_match = evaluate_cross_reference_applicability(
        decision,
        profile_facts={"iva": {"roi_enrolled": False}, "does_intracomunitario": False},
    )
    assert none_match.applicable is False
    assert none_match.matched_explanations == ()
    assert set(none_match.unmet_predicate_fields) == {"iva.roi_enrolled", "does_intracomunitario"}


def test_schema_rejects_any_mode_with_empty_predicates() -> None:
    """The any-mode + empty-predicates shape is meaningless; validator must reject."""

    with pytest.raises(ValidationError, match="any-mode requires applicability predicates"):
        _decision(applicability_predicates=(), applicability_condition_mode="any")


def test_groi_349_binding_is_not_applicable_when_profile_is_not_intracomunitario() -> None:
    """The committed GROI binding evaluates to applicable=False under a
    profile that doesn't conduct intracom operations.

    Asserts the typed result shape: live tests + the resolver consume
    `unmet_predicate_fields` to emit precise skip diagnostics. Non-
    tautological: the predicate's truth comes from the profile fact;
    the test asserts the evaluator's gate semantics, not the formula
    arithmetic.
    """

    modelo, _ = _committed_modelo("349")
    binding = next(
        decision
        for decision in modelo.revisions["2020-y-siguientes"].live_cross_references
        if decision.id == "modelo-349-groi-spanish-counterparty-check"
    )

    not_applicable = evaluate_cross_reference_applicability(
        binding,
        profile_facts={"does_intracomunitario": False},
    )
    assert not_applicable.applicable is False
    assert not_applicable.unmet_predicate_fields == ("does_intracomunitario",)
    assert not_applicable.matched_explanations == ()

    applicable = evaluate_cross_reference_applicability(
        binding,
        profile_facts={"does_intracomunitario": True},
    )
    assert applicable.applicable is True
    assert applicable.unmet_predicate_fields == ()
    assert len(applicable.matched_explanations) == 1


def _load_binding(modelo_id: str, revision_id: str, cross_reference_id: str) -> LiveCrossReferenceDecision:
    modelo, _ = _committed_modelo(modelo_id)
    return next(
        decision
        for decision in modelo.revisions[revision_id].live_cross_references
        if decision.id == cross_reference_id
    )


def test_oss_369_binding_is_not_applicable_when_profile_is_not_oss_enrolled() -> None:
    """The committed Modelo 369 OSS read binding evaluates to applicable=False
    under a profile that hasn't enrolled in the OSS regime.

    Mirrors the GROI test pattern. Non-tautological: applicability comes
    from the profile state; the test asserts the gate semantics, not
    formula arithmetic.
    """

    binding = _load_binding("369", "esquema-exterior", "modelo-369-exterior-filed-declarations-read")

    not_enrolled = evaluate_cross_reference_applicability(
        binding,
        profile_facts={"iva": {"oss_enrolled": False}},
    )
    assert not_enrolled.applicable is False
    assert not_enrolled.unmet_predicate_fields == ("iva.oss_enrolled",)
    assert not_enrolled.matched_explanations == ()

    enrolled = evaluate_cross_reference_applicability(
        binding,
        profile_facts={"iva": {"oss_enrolled": True}},
    )
    assert enrolled.applicable is True
    assert enrolled.unmet_predicate_fields == ()
    assert len(enrolled.matched_explanations) == 1


def test_oss_369_filing_schedules_select_only_when_oss_enrolled() -> None:
    """Modelo 369's three filing schedules (esquema-union, -exterior,
    -importacion) gate on iva.oss_enrolled. Non-enrolled subjects do
    not see the schedule fire at all — the cross-reference applicability
    gate is then defense-in-depth at the binding layer.
    """

    modelo_369, _ = _committed_modelo("369")

    for revision in modelo_369.revisions.values():
        not_enrolled = applicable_filing_schedules(
            revision,
            profile_facts={"iva": {"oss_enrolled": False}},
        )
        assert not_enrolled == (), f"revision {revision.id}: schedule fires for non-OSS-enrolled subject"

        enrolled = applicable_filing_schedules(
            revision,
            profile_facts={"iva": {"oss_enrolled": True}},
        )
        assert enrolled, f"revision {revision.id}: schedule did not fire for OSS-enrolled subject"
        for schedule in enrolled:
            fields = {predicate.field for predicate in schedule.profile_conditions}
            assert "iva.oss_enrolled" in fields


def test_oss_369_cross_reference_declares_iva_oss_enrolled_predicate() -> None:
    """The committed OSS read binding must carry the OSS enrollment gate.

    Pinning the registered predicate fields catches a regression where
    the predicate is silently dropped on a future TOML edit. Mirrors
    the GROI pinning test.
    """

    binding = _load_binding("369", "esquema-exterior", "modelo-369-exterior-filed-declarations-read")
    assert binding.applicability_predicates, "OSS-369 binding must declare an applicability gate"
    assert binding.applicability_condition_mode == "all"
    fields = {predicate.field for predicate in binding.applicability_predicates}
    assert "iva.oss_enrolled" in fields


def test_ixvi_349_binding_evaluates_under_does_intracomunitario_predicate() -> None:
    """The Modelo 349 IXVI foreign-counterparty binding mirrors the GROI
    binding: applicable iff the taxpayer conducts intracom operations,
    bound to the aeat-nif-iva-checker oracle, surface=
    authenticated_simulator. Resolves the prior orphan reported by
    audit-oracles by giving the NIF-IVA checker a real binding.
    """

    binding = _load_binding("349", "2020-y-siguientes", "modelo-349-ixvi-foreign-counterparty-check")
    assert binding.oracle_id == "aeat-nif-iva-checker"
    assert binding.surface == "authenticated_simulator"
    assert binding.applicability_predicates, "IXVI binding must declare an applicability gate"
    fields = {predicate.field for predicate in binding.applicability_predicates}
    assert "does_intracomunitario" in fields

    not_applicable = evaluate_cross_reference_applicability(
        binding,
        profile_facts={"does_intracomunitario": False},
    )
    assert not_applicable.applicable is False
    assert not_applicable.unmet_predicate_fields == ("does_intracomunitario",)

    applicable = evaluate_cross_reference_applicability(
        binding,
        profile_facts={"does_intracomunitario": True},
    )
    assert applicable.applicable is True


def test_user_profile_contract_rejects_typoed_predicate_field() -> None:
    """Predicate fields must resolve in the user_profile schema.

    A typo'd field (`iva.roi_enrolled_X`) would silently match nothing
    and the binding would always evaluate to applicable=False. The
    user_profile registry contract validator catches this at registry
    load time, surfacing a structural failure naming the cross-
    reference + bad selector. Mirrors the existing schedule /
    deadline-window predicate validation.
    """

    from .....core.errors import BaseSeverity
    from ....user_profile.loader import load_user_profile_schema
    from ....user_profile.registry_contract import validate_user_profile_registry_contract

    modelo_349, _ = _committed_modelo("349")
    revision = modelo_349.revisions["2020-y-siguientes"]
    binding = next(
        decision
        for decision in revision.live_cross_references
        if decision.id == "modelo-349-groi-spanish-counterparty-check"
    )

    typoed_predicate = ProfilePredicateDefinition(
        field="iva.roi_enrolled_X",
        op="equals",
        value=True,
        explanation="Typo'd field for validator coverage.",
        legal_refs=("orden-hac-174-2020:art-1",),
        source_refs=("aeat-modelo-349-procedure",),
    )
    bad_binding = binding.model_copy(update={"applicability_predicates": (typoed_predicate,)})
    bad_revision = revision.model_copy(
        update={
            "live_cross_references": tuple(
                bad_binding if decision.id == bad_binding.id else decision
                for decision in revision.live_cross_references
            ),
        },
    )
    bad_modelo: ModeloDefinition = modelo_349.model_copy(update={"revisions": {"2020-y-siguientes": bad_revision}})
    assert isinstance(bad_revision, ModeloRevision)

    schema = load_user_profile_schema()
    report = validate_user_profile_registry_contract([bad_modelo], schema)
    matching = [
        issue
        for issue in report.issues
        if issue.surface == "cross_reference_applicability" and issue.selector == "iva.roi_enrolled_X"
    ]
    assert matching, "validator did not catch the typo'd predicate field"
    assert matching[0].severity is BaseSeverity.ERROR
    assert matching[0].construct_id == "modelo-349-groi-spanish-counterparty-check"


def test_validator_rejects_cross_reference_applicability_predicate_without_official_guidance_source() -> None:
    modelo, catalogues = _committed_modelo("349")
    revision = modelo.revisions["2020-y-siguientes"]
    binding = next(
        decision
        for decision in revision.live_cross_references
        if decision.id == "modelo-349-groi-spanish-counterparty-check"
    )
    predicate = binding.applicability_predicates[0]
    mutated_predicate = predicate.model_copy(update={"source_refs": ("aeat-dr-349-2020-current",)})
    mutated_binding = binding.model_copy(
        update={"applicability_predicates": (mutated_predicate, *binding.applicability_predicates[1:])},
    )
    mutated_revision = revision.model_copy(
        update={
            "live_cross_references": tuple(
                mutated_binding if decision.id == binding.id else decision
                for decision in revision.live_cross_references
            ),
        },
    )

    with pytest.raises(
        RegistryValidationError,
        match=(
            r"cross-reference modelo-349-groi-spanish-counterparty-check applicability predicate "
            r"'does_intracomunitario' requires official_source_guidance source evidence"
        ),
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(
            _with_revision(modelo, mutated_revision),
        )


def test_groi_349_cross_reference_declares_does_intracomunitario_predicate() -> None:
    """The committed modelo-349-groi-spanish-counterparty-check binding must
    carry an applicability gate so non-intracom subjects skip the consult.

    The test reads the loaded registry rather than the TOML directly so a
    schema-side regression (predicate dropped on serialisation, mode flipped)
    fails alongside any TOML edit.
    """

    modelo, _ = _committed_modelo("349")
    revision = modelo.revisions["2020-y-siguientes"]
    binding = next(
        decision
        for decision in revision.live_cross_references
        if decision.id == "modelo-349-groi-spanish-counterparty-check"
    )
    assert binding.applicability_predicates, "GROI binding must declare an applicability gate"
    assert binding.applicability_condition_mode == "all"
    fields = {predicate.field for predicate in binding.applicability_predicates}
    assert "does_intracomunitario" in fields
