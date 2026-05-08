"""Tests for the ``authenticated_simulator`` cross-reference surface category.

The ``authenticated_simulator`` category models cross-references whose
empirical semantics are cl@ve-movil-required, synthetic-NIFs-accepted,
and form-submit POST (the GROI binding's shape). The schema validator
enforces explicit rules for the category; these tests pin the
canonical content the validator allows.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ._live_parity import _COMPATIBLE_SURFACE_PAIRS
from ._remote_state_guard import AEAT_WRITE_FORBIDDEN_ACTIONS
from ._schema import LiveCrossReferenceDecision

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _kwargs(**overrides: object) -> dict[str, object]:
    """Default kwargs for an authenticated_simulator cross-reference.

    The defaults form the canonical 'GROI Spanish-ROI consult' shape;
    individual tests override one field at a time to exercise
    validator rules.
    """

    base: dict[str, object] = {
        "id": "modelo-349-groi-spanish-counterparty-check",
        "evidence_tier": "executable_parity_evidence",
        "surface": "authenticated_simulator",
        "guard_policy_id": "modelo-349-groi-spanish-roi-check",
        "allowed_hosts": ("www2.agenciatributaria.gob.es",),
        "allowed_methods": ("GET", "POST"),
        "forbidden_actions": AEAT_WRITE_FORBIDDEN_ACTIONS,
        "synthetic_data_allowed": True,
        "requires_authentication": True,
        "requires_aeat_authorization": False,
        "legal_refs": ("orden-hac-174-2020:art-1",),
        "source_refs": ("aeat-modelo-349-procedure",),
    }
    for key, value in overrides.items():
        base[key] = value
    return base


def test_authenticated_simulator_with_canonical_groi_shape_validates() -> None:
    """The canonical GROI cross-reference shape — auth required, synthetic data,
    POST in allowed_methods, executable parity — validates clean."""

    decision = LiveCrossReferenceDecision.model_validate(_kwargs())  # type: ignore[arg-type]

    assert decision.surface == "authenticated_simulator"
    assert decision.evidence_tier == "executable_parity_evidence"
    assert decision.requires_authentication is True
    assert decision.synthetic_data_allowed is True
    assert "POST" in decision.allowed_methods


def test_authenticated_simulator_rejects_non_executable_parity_evidence_tier() -> None:
    """The new category is callable / executable parity. Other tiers raise."""

    with pytest.raises(ValidationError, match="executable parity evidence"):
        LiveCrossReferenceDecision.model_validate(_kwargs(evidence_tier="official_source_guidance"))
    with pytest.raises(ValidationError, match="executable parity evidence"):
        LiveCrossReferenceDecision.model_validate(_kwargs(evidence_tier="layout_authority"))


def test_authenticated_simulator_requires_authentication_to_be_true() -> None:
    """The defining property: this category is auth-gated."""

    with pytest.raises(ValidationError, match="authenticated simulator must require authentication"):
        LiveCrossReferenceDecision.model_validate(_kwargs(requires_authentication=False))


def test_authenticated_simulator_requires_non_empty_allowed_hosts() -> None:
    with pytest.raises(ValidationError, match="must declare allowed_hosts"):
        LiveCrossReferenceDecision.model_validate(_kwargs(allowed_hosts=()))


def test_authenticated_simulator_rejects_methods_outside_query_set() -> None:
    """allowed_methods may include only {GET, HEAD, OPTIONS, POST}."""

    with pytest.raises(ValidationError, match="not in"):
        LiveCrossReferenceDecision.model_validate(_kwargs(allowed_methods=("GET", "PUT")))
    with pytest.raises(ValidationError, match="not in"):
        LiveCrossReferenceDecision.model_validate(_kwargs(allowed_methods=("DELETE",)))
    with pytest.raises(ValidationError, match="not in"):
        LiveCrossReferenceDecision.model_validate(_kwargs(allowed_methods=("PATCH",)))


def test_authenticated_simulator_permits_synthetic_data_optional_authorization() -> None:
    """synthetic_data_allowed and requires_aeat_authorization are both flexible."""

    # Synthetic data permitted (GROI accepts arbitrary NIFs).
    LiveCrossReferenceDecision.model_validate(_kwargs(synthetic_data_allowed=True))
    # Synthetic data also permitted False (a future surface that only
    # accepts the caller's own NIF would set this False).
    LiveCrossReferenceDecision.model_validate(_kwargs(synthetic_data_allowed=False))
    # Authorization required (a future surface gated on certificate
    # tier on top of cl@ve-movil).
    LiveCrossReferenceDecision.model_validate(_kwargs(requires_aeat_authorization=True))


def test_authenticated_simulator_inherits_canonical_aeat_write_forbidden_actions() -> None:
    """Every authenticated_simulator cross-reference must include the canonical write-class set.

    The schema validator does not enforce this directly: the
    ``forbidden_actions`` field is constrained only to be a non-empty
    tuple via ``min_length=1``. The canonical-content check is a
    project-level invariant pinning the GROI binding's expected shape.
    """

    decision = LiveCrossReferenceDecision.model_validate(_kwargs())
    for forbidden in AEAT_WRITE_FORBIDDEN_ACTIONS:
        assert forbidden in decision.forbidden_actions


def test_authenticated_simulator_vat_id_check_pair_is_in_compatibility_table() -> None:
    """The new cross-reference category pairs with the vat_id_check oracle surface_kind."""

    assert ("authenticated_simulator", "vat_id_check") in _COMPATIBLE_SURFACE_PAIRS


def test_existing_surface_categories_still_validate() -> None:
    """Every non-``authenticated_simulator`` surface category continues to validate.

    Key shapes (open_simulator without auth, public_read_surface
    without auth and observation_evidence, authenticated_read_surface
    with auth + authorization, static_official_documentation) all
    produce valid models. Failure here would mean the schema rejected
    a cross-reference whose category is not the new one.
    """

    # open_simulator
    LiveCrossReferenceDecision(
        id="probe-open-sim",
        evidence_tier="executable_parity_evidence",
        surface="open_simulator",
        guard_policy_id="probe",
        allowed_hosts=("sede.agenciatributaria.gob.es",),
        allowed_methods=("GET",),
        forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS,
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
        legal_refs=("orden-hac-174-2020:art-1",),
        source_refs=("aeat-modelo-349-procedure",),
    )
    # public_read_surface
    LiveCrossReferenceDecision(
        id="probe-public-read",
        evidence_tier="official_source_guidance",
        surface="public_read_surface",
        guard_policy_id="probe",
        allowed_hosts=("sede.agenciatributaria.gob.es",),
        allowed_methods=("GET",),
        forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS,
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
        legal_refs=("orden-hac-174-2020:art-1",),
        source_refs=("aeat-modelo-349-procedure",),
    )
    # authenticated_read_surface
    LiveCrossReferenceDecision(
        id="probe-auth-read",
        evidence_tier="official_source_guidance",
        surface="authenticated_read_surface",
        guard_policy_id="probe",
        allowed_hosts=("sede.agenciatributaria.gob.es",),
        allowed_methods=("GET",),
        forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS,
        synthetic_data_allowed=False,
        requires_authentication=True,
        requires_aeat_authorization=True,
        legal_refs=("orden-hac-174-2020:art-1",),
        source_refs=("aeat-modelo-349-procedure",),
    )
    # static_official_documentation
    LiveCrossReferenceDecision(
        id="probe-static-doc",
        evidence_tier="official_source_guidance",
        surface="static_official_documentation",
        guard_policy_id="probe",
        allowed_hosts=("sede.agenciatributaria.gob.es",),
        allowed_methods=(),
        forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS,
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
        legal_refs=("orden-hac-174-2020:art-1",),
        source_refs=("aeat-modelo-349-procedure",),
    )
