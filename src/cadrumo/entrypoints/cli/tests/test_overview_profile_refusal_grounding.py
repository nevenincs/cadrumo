"""The overview projections name missing profile facts, not selector tokens.

When ``overview calendar``, ``agenda`` or ``backlog`` refuse because the active
profile has not answered a fact the projection depends on, the refusal must
name the field the way the operator sees it in the profile editor, with the
legal grounding the registry carries, rather than the internal selector token
the deadline engine gates on.

The same warning stream also carries codes that are not profile fields at all
(censo enrolment, unverified justificante, AEAT evidence conflict). Those have
no field to name and must survive verbatim.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest
from click.testing import Result

from ....application.user_profile.preflight import (
    build_profile_preflight_requirement,
    format_profile_preflight_requirement,
    format_profile_selector_requirements,
)
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.profile_grounding import build_profile_grounding_index
from ....domain.user_profile.loader import load_user_profile_schema
from ....tests.cli_runner import invoke_cached_cli
from .._overview import (
    _ENTITY_TYPE_SELECTOR,
    _IRPF_INCOME_CATEGORIES_SELECTOR,
    _undeclared_taxpayer_model_refusal,
)
from ._overview_calendar_support import _isolated_backend

__all__ = ["_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: A gating field held as its declared selector token, which is exactly the
#: string the enriched rendering must NOT emit.
_GATING_SELECTOR = "has_employees"
_GATING_PATH = "withholding.has_employees"

#: A calendar warning code that is not a profile field at all.
_NON_PROFILE_WARNING_CODE = "censo.enrolment_unverified"


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _grounding_index():
    return build_profile_grounding_index(bundled_authority())


def test_the_gating_field_label_differs_from_its_selector_token() -> None:
    """Anchor the fixture: every assertion below is vacuous if they are equal."""
    schema = load_user_profile_schema()
    requirement = build_profile_preflight_requirement(
        _GATING_PATH,
        schema=schema,
        selector=_GATING_SELECTOR,
    )

    assert requirement.label != _GATING_SELECTOR
    assert _GATING_SELECTOR in schema.field(_GATING_PATH).model_selectors


def test_a_profile_selector_token_renders_as_its_operator_label() -> None:
    """The token is replaced by the label the profile editor shows.

    Run against the real committed schema and the real registry authority, so
    the label and any legal grounding come from the same authority the modelo
    readiness gate consults when it refuses for this same field.
    """
    schema = load_user_profile_schema()

    rendered = format_profile_selector_requirements(
        (_GATING_SELECTOR,),
        schema=schema,
        grounding_index=_grounding_index(),
    )

    expected = format_profile_preflight_requirement(
        build_profile_preflight_requirement(
            _GATING_PATH,
            schema=schema,
            selector=_GATING_SELECTOR,
            grounding_index=_grounding_index(),
        ),
    )
    assert rendered == (expected,)
    assert rendered[0] != _GATING_SELECTOR


def test_a_non_profile_warning_code_survives_verbatim() -> None:
    """A code naming no profile field must not be relabelled or dropped."""
    rendered = format_profile_selector_requirements(
        (_NON_PROFILE_WARNING_CODE,),
        schema=load_user_profile_schema(),
        grounding_index=_grounding_index(),
    )

    assert rendered == (_NON_PROFILE_WARNING_CODE,)


def test_a_mixed_stream_enriches_only_the_profile_fields_and_preserves_order() -> None:
    """Both kinds arrive interleaved in one stream and each keeps its position."""
    schema = load_user_profile_schema()

    rendered = format_profile_selector_requirements(
        (_NON_PROFILE_WARNING_CODE, _GATING_SELECTOR, _NON_PROFILE_WARNING_CODE),
        schema=schema,
        grounding_index=_grounding_index(),
    )

    assert len(rendered) == 3
    assert rendered[0] == _NON_PROFILE_WARNING_CODE
    assert rendered[2] == _NON_PROFILE_WARNING_CODE
    assert rendered[1] != _GATING_SELECTOR


def test_calendar_refusal_reads_as_a_refusal_not_as_invalid_input() -> None:
    """A missing profile fact is workflow state, not a bad command line.

    Guards the channel as well as the wording: routed as a Click parameter
    error, the same text would reach the operator under an invalid-value
    header, telling them to correct an argument that is not wrong.
    """
    # Asserted on the envelope, not the prose: both the refusal word and
    # Click's "Invalid value" header are translated, so an English token cannot
    # decide the question in a Spanish-rendered run. The category IS the
    # channel -- a parameter error never carries REFUSED.
    result = _invoke(["--format", "json", "app", "overview", "calendar", "--from", "2026-01-01", "--to", "2026-03-31"])

    assert result.exit_code != 0, result.output
    envelope = json.loads(result.output)
    error = envelope["error"]

    # Neither the category nor the code settles this: a Click parameter error
    # on this same verb is published as REFUSED with the identical
    # `REFUSED_CLI_BOUNDARY` code -- both were checked against the live CLI.
    # What separates the channels is the FAILED CONDITION: workflow state names
    # the condition it could not satisfy, and a bad command line names none.
    assert (error["action"] or {})["failed_condition_id"] == "cli.overview.profile.complete", result.output


def test_calendar_refusal_carries_the_remediation_command() -> None:
    """The operator is told what to run, not only what is missing."""
    result = _invoke(["app", "overview", "calendar", "--from", "2026-01-01", "--to", "2026-03-31"])

    assert result.exit_code != 0, result.output
    assert "aeat config profile edit" in result.output, result.output


def test_calendar_allow_incomplete_still_renders_rather_than_refusing() -> None:
    """The refusal CONDITION is unchanged; only its message was rewritten."""
    result = _invoke(
        [
            "app",
            "overview",
            "calendar",
            "--from",
            "2026-01-01",
            "--to",
            "2026-03-31",
            "--allow-incomplete",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "entries\t" in result.output


def _label_for(selector: str) -> str:
    schema = load_user_profile_schema()
    path = schema.path_for_model_selector(selector)
    assert path is not None, f"{selector} does not resolve to a schema field"
    return build_profile_preflight_requirement(path, schema=schema, selector=selector).label


def _profile(**kwargs):
    from ....domain.deadlines.models import IVARegime, TaxpayerProfile

    return TaxpayerProfile(tax_id="00000000T", iva_regime=IVARegime.GENERAL, **kwargs)


def test_the_taxpayer_model_fields_have_labels_that_differ_from_their_tokens() -> None:
    """Anchor: the two tests below are vacuous if label and token coincide."""
    assert _label_for(_ENTITY_TYPE_SELECTOR) != _ENTITY_TYPE_SELECTOR
    assert _label_for(_IRPF_INCOME_CATEGORIES_SELECTOR) != _IRPF_INCOME_CATEGORIES_SELECTOR


def test_an_undeclared_entity_type_is_named_rather_than_summarised() -> None:
    """The refusal names the entity-type field, not only "model undeclared"."""
    refusal = _undeclared_taxpayer_model_refusal(_profile())

    context = refusal.context
    assert context is not None
    requirements = context.get("requirements")
    assert isinstance(requirements, str)
    assert _label_for(_ENTITY_TYPE_SELECTOR) in requirements
    assert _ENTITY_TYPE_SELECTOR not in requirements


def test_a_natural_person_without_income_categories_is_told_about_the_categories() -> None:
    """A field the operator already filled in must not be named.

    The entity type IS declared here, so naming it would send the operator
    back to a box they already answered.
    """
    from ....domain.contribuyente.entity_type import EntityType

    refusal = _undeclared_taxpayer_model_refusal(_profile(entity_type=EntityType.NATURAL_PERSON))

    context = refusal.context
    assert context is not None
    requirements = context.get("requirements")
    assert isinstance(requirements, str)
    assert _label_for(_IRPF_INCOME_CATEGORIES_SELECTOR) in requirements
    assert _label_for(_ENTITY_TYPE_SELECTOR) not in requirements
