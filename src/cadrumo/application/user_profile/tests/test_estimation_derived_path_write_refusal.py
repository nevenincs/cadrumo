"""The estimation-regime projections are engine-derived, so the write door refuses them.

``irpf.estimation_directa``, ``irpf.estimation_directa_normal`` and
``irpf.activity_income_cash_criterion_elected`` are computed at calculate time
from the declared estimation regime and imputation criterion. A value stored at
one of them would otherwise reach Modelo 100 casillas 0168, 0169 and 0224 in
place of the taxpayer's real declaration.

The refusal is asserted by issue CODE through the validator every write door
converges on, and through the application write policy those doors call. A bare
"was refused" would also be satisfied by the weaker ``unknown_field`` refusal,
which names no surface to edit instead.
"""

from __future__ import annotations

import pytest

from ....core.errors.severity import BaseSeverity
from ....domain.calculations.registry.tests.published_authority import published_profile_schema
from ....domain.user_profile.errors import ProfileSchemaValidationError
from ....domain.user_profile.values import UserProfileFact
from ..validation import DERIVED_FIELD_ISSUE_CODE, ProfileValidationService, reject_invalid_profile_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_PROFILE_ID = "3f2a1b4c-5d6e-4f70-8a9b-0c1d2e3f4a5c"

_DERIVED_PATHS = (
    "irpf.estimation_directa",
    "irpf.estimation_directa_normal",
    "irpf.estimation_directa_modalidad_clave",
    "irpf.activity_income_cash_criterion_elected",
)


def _refusals(*facts: UserProfileFact) -> list[tuple[str, str]]:
    """Every blocking issue raised at one of the paths under test, with its code."""
    report = ProfileValidationService(schema=published_profile_schema()).validate_facts(_PROFILE_ID, facts)
    subject_paths = {fact.path for fact in facts}
    return [
        (issue.path, issue.code)
        for issue in report.issues
        if issue.severity is BaseSeverity.ERROR and issue.path is not None and issue.path in subject_paths
    ]


@pytest.mark.parametrize("path", _DERIVED_PATHS)
@pytest.mark.parametrize("value", [True, False])
def test_a_value_written_at_an_estimation_projection_is_refused_as_derived(path: str, value: bool) -> None:
    assert _refusals(UserProfileFact(path=path, value=value)) == [(path, DERIVED_FIELD_ISSUE_CODE)]


@pytest.mark.parametrize("path", _DERIVED_PATHS)
def test_the_application_write_policy_refuses_the_projection_and_names_the_source_surface(path: str) -> None:
    """Registration, the wizard fact patch and the cotejo all refuse through this policy."""
    with pytest.raises(ProfileSchemaValidationError) as refusal:
        reject_invalid_profile_facts(
            _PROFILE_ID,
            (UserProfileFact(path=path, value=True),),
            require_complete=False,
            schema=published_profile_schema(),
        )

    message = str(refusal.value)
    assert path in message
    assert "is computed by the engine" in message
    # The refusal names the operator surface that edits the regime or criterion the value derives from.
    assert "--irpf-" in message


@pytest.mark.parametrize("path", _DERIVED_PATHS)
def test_clearing_a_stale_projection_is_admitted(path: str) -> None:
    """A fact stored before the path was declared derived must stay removable."""
    assert _refusals(UserProfileFact(path=path, value=None)) == []


def test_the_regime_and_criterion_the_projections_derive_from_stay_writable() -> None:
    """Anti-vacuity: the refusal covers the projections, not the operator's declarations."""
    assert (
        _refusals(
            UserProfileFact(path="irpf.estimation_regime", value="directa_simplificada"),
            UserProfileFact(path="irpf.activity_income_imputation_criterion", value="cobros_y_pagos"),
        )
        == []
    )


def test_the_schema_holds_no_field_declaration_at_the_projections() -> None:
    """The paths are declared only as derived selectors, so storage has no field to hold them."""
    schema = published_profile_schema()
    declared = {f"{section.key}.{field.key}" for section in schema.sections for field in section.fields}
    assert not declared.intersection(_DERIVED_PATHS)
    patterns = {selector.pattern for selector in schema.derived_selectors}
    assert set(_DERIVED_PATHS) <= patterns
