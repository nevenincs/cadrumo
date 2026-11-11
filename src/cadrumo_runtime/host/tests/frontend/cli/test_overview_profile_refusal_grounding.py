"""The overview projections name missing profile facts, not selector tokens.

When ``overview calendar``, ``agenda`` or ``backlog`` refuse because the active
profile declares no taxpayer model, the refusal must name the field the way the
operator sees it in the profile editor, with the legal grounding the registry
carries, rather than the internal selector token the deadline engine gates on.
A fact the profile has merely left unanswered does not refuse: it arrives as a
warning naming the profile edit that answers it.

The same warning stream also carries codes that are not profile fields at all
(censo enrolment, unverified justificante, AEAT evidence conflict). Those have
no field to name and must survive verbatim.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence

import pytest
from click.testing import Result

from cadrumo.application.user_profile.preflight import (
    build_profile_preflight_requirement,
    format_profile_preflight_requirement,
    format_profile_selector_requirements,
)
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.profile_grounding import build_profile_grounding_index
from cadrumo.domain.calculations.registry.tests.published_authority import published_profile_schema
from cadrumo_runtime.host.tests.native_commands.runtime_profile_cli_fixture import NativeCliProfileFixture

from .overview_native_support import invoke_native_overview

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: A gating field held as its declared selector token, which is exactly the
#: string the enriched rendering must NOT emit.
_GATING_SELECTOR = "has_employees"
_GATING_PATH = "withholding.has_employees"

#: A calendar warning code that is not a profile field at all.
_NON_PROFILE_WARNING_CODE = "censo.enrolment_unverified"


def _invoke(fixture: NativeCliProfileFixture, args: Sequence[str]) -> Result:
    return invoke_native_overview(fixture, args)


def _grounding_index():
    with bundled_indexed_authority().operation() as operation:
        return build_profile_grounding_index(operation)


def test_the_gating_field_label_differs_from_its_selector_token() -> None:
    """Anchor the fixture: every assertion below is vacuous if they are equal."""
    schema = published_profile_schema()
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
    schema = published_profile_schema()

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
        schema=published_profile_schema(),
        grounding_index=_grounding_index(),
    )

    assert rendered == (_NON_PROFILE_WARNING_CODE,)


def test_a_mixed_stream_enriches_only_the_profile_fields_and_preserves_order() -> None:
    """Both kinds arrive interleaved in one stream and each keeps its position."""
    schema = published_profile_schema()

    rendered = format_profile_selector_requirements(
        (_NON_PROFILE_WARNING_CODE, _GATING_SELECTOR, _NON_PROFILE_WARNING_CODE),
        schema=schema,
        grounding_index=_grounding_index(),
    )

    assert len(rendered) == 3
    assert rendered[0] == _NON_PROFILE_WARNING_CODE
    assert rendered[2] == _NON_PROFILE_WARNING_CODE
    assert rendered[1] != _GATING_SELECTOR


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_an_unanswered_fact_renders_as_a_warning_naming_its_profile_edit(
    native_overview_profile: NativeCliProfileFixture,
) -> None:
    """An unanswered fact is reported beside the rows, with the edit that answers it.

    Asserted on the envelope, not the prose, so a Spanish-rendered run decides
    it the same way: the calendar succeeds, and each profile-fact warning
    carries the profile edit action rather than a refusal.
    """
    result = _invoke(
        native_overview_profile,
        ["--format", "json", "app", "overview", "calendar", "--from", "2026-01-01", "--to", "2026-03-31"],
    )

    assert result.exit_code == 0, result.output
    calendar = json.loads(result.output)["result"]
    assert calendar["taxpayer_model_declared"] is True, result.output
    assert any(
        warning["fix_action"]["action"]["action"]["action_id"] == "operator.profile.edit"
        for warning in calendar["warnings"]
    ), result.output


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_an_unanswered_fact_renders_as_a_text_warning_beside_the_rows(
    native_overview_profile: NativeCliProfileFixture,
) -> None:
    """The text rendering keeps the rows and states each unanswered fact on its warning line."""
    result = _invoke(
        native_overview_profile, ["app", "overview", "calendar", "--from", "2026-01-01", "--to", "2026-03-31"]
    )

    assert result.exit_code == 0, result.output
    assert "entries\t" in result.output
    assert any(line.startswith("warning\t") for line in result.output.splitlines()), result.output
