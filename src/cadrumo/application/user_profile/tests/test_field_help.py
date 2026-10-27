"""Profile field help is the setup wizard's own copy, remapped by profile path.

These gates build the real setup flow for a pinned authority and read the help
back through the real producer and the real overview projection. The expected
lines are named by their locale keys, not recomputed by walking the flow the
way the producer does, so a field that stops being remapped fails here.
"""

from __future__ import annotations

import pytest

from ....core.config import override_settings
from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.deadlines.profiles import MODELO_IVA_BLOCK_REQUIRED_PATHS
from ....domain.user_profile.values import ProfileSetupState, create_user_profile_record
from ...wizard.catalogue import build_setup_flow
from ..field_help import profile_field_help
from ..overview import build_profile_overview, relocalize_profile_field

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "33333333-3333-4333-8333-333333333333"
_IVA_REGIME_KEY = "wizard.setup.profile.iva-regime.choices.general"


def test_a_field_with_only_a_prompt_shows_that_prompt_in_every_locale() -> None:
    with bundled_indexed_authority().operation() as authority:
        flow = build_setup_flow(authority)
        for locale in SUPPORTED_OUTPUT_LANGUAGES:
            assert profile_field_help(flow, locale=locale)["identity.tax_id"] == (
                tr("wizard.setup.profile.tax-id.prompt", locale=locale),
            )
        assert (
            profile_field_help(flow, locale="en")["identity.tax_id"]
            != profile_field_help(flow, locale="es")["identity.tax_id"]
        )


def test_a_field_with_wizard_help_shows_its_prompt_then_that_help_in_every_locale() -> None:
    with bundled_indexed_authority().operation() as authority:
        flow = build_setup_flow(authority)
        for locale in SUPPORTED_OUTPUT_LANGUAGES:
            assert profile_field_help(flow, locale=locale)["identity.legal_name"] == (
                tr("wizard.setup.profile.legal-name.prompt", locale=locale),
                tr("wizard.setup.profile.legal-name.help", locale=locale),
            )
        assert (
            profile_field_help(flow, locale="en")["identity.legal_name"]
            != profile_field_help(flow, locale="es")["identity.legal_name"]
        )


def test_a_choice_field_lists_each_described_choice_after_its_prompt_in_every_locale() -> None:
    with bundled_indexed_authority().operation() as authority:
        flow = build_setup_flow(authority)
        for locale in SUPPORTED_OUTPUT_LANGUAGES:
            lines = profile_field_help(flow, locale=locale)["iva.regime"]
            assert lines[0] == tr("wizard.setup.profile.iva-regime.prompt", locale=locale)
            assert (
                f"{tr(_IVA_REGIME_KEY + '.label', locale=locale)}: {tr(_IVA_REGIME_KEY + '.description', locale=locale)}"
                in lines[1:]
            )
            entity = profile_field_help(flow, locale=locale)["taxpayer_type.entity_type"]
            assert entity[:2] == (
                tr("wizard.setup.taxpayer-type.entity-type.prompt", locale=locale),
                tr("wizard.setup.taxpayer-type.entity-type.help", locale=locale),
            )
            assert len(entity) > 2


def test_a_choice_without_a_description_adds_no_line() -> None:
    with bundled_indexed_authority().operation() as authority:
        flow = build_setup_flow(authority)
        territory = next(
            question
            for section in flow.sections
            for question in section.questions
            if question.profile_key == "tax_residence.jurisdiction_scope"
        )
        assert territory.choices
        assert all(choice.description is None for choice in territory.choices)
        assert profile_field_help(flow, locale="en")["tax_residence.jurisdiction_scope"] == (
            tr("wizard.setup.residence.tax-residence-jurisdiction-scope.prompt", locale="en"),
        )


def test_help_exists_exactly_for_the_schema_fields_a_wizard_question_writes() -> None:
    with bundled_indexed_authority().operation() as authority:
        flow = build_setup_flow(authority)
        schema = authority.profile_schema()
        declared = {f"{section.key}.{field.key}" for section in schema.sections for field in section.fields}
        written = {
            question.profile_key
            for section in flow.sections
            for question in section.questions
            if question.profile_key is not None
        }
        assert written <= declared, sorted(written - declared)
        assert written and declared - written, "the schema must hold both asked and unasked fields"
        for locale in SUPPORTED_OUTPUT_LANGUAGES:
            assert set(profile_field_help(flow, locale=locale)) == written
        assert "contact.fiscal_address" in declared - written


def test_every_question_setup_can_ask_has_wizard_help() -> None:
    """A schema-required field, or one the IVA block obliges, is never asked unexplained."""
    with bundled_indexed_authority().operation() as authority:
        schema = authority.profile_schema()
        helped = set(profile_field_help(build_setup_flow(authority)))
        setup_paths = {
            f"{section.key}.{field.key}"
            for section in schema.sections
            if not section.repeatable
            for field in section.fields
            if field.required
        } | set(MODELO_IVA_BLOCK_REQUIRED_PATHS)
        assert setup_paths, "the schema must declare setup questions, or this proves nothing"
        assert setup_paths <= helped, sorted(setup_paths - helped)


def test_the_overview_serves_wizard_help_and_keeps_the_schema_description_for_other_fields() -> None:
    with bundled_indexed_authority().operation() as authority:
        flow = build_setup_flow(authority)
        schema = authority.profile_schema()
        record = create_user_profile_record(
            context=authority.profile_create_context(),
            profile_id=_PROFILE_ID,
            setup_state=ProfileSetupState.INCOMPLETE,
            facts=(),
        )
        helped = {
            field.path: field
            for section in build_profile_overview(record, schema=schema, flow=flow).sections
            for field in section.fields
        }
        assert helped["identity.tax_id"].help == profile_field_help(flow)["identity.tax_id"]
        assert helped["contact.fiscal_address"].help is None
        assert helped["contact.fiscal_address"].about
        unhelped = build_profile_overview(record, schema=schema)
        assert all(field.help is None for section in unhelped.sections for field in section.fields)


def test_the_overview_help_is_the_producer_output_for_the_active_language() -> None:
    with bundled_indexed_authority().operation() as authority:
        flow = build_setup_flow(authority)
        schema = authority.profile_schema()
        record = create_user_profile_record(
            context=authority.profile_create_context(),
            profile_id=_PROFILE_ID,
            setup_state=ProfileSetupState.INCOMPLETE,
            facts=(),
        )
        for locale in SUPPORTED_OUTPUT_LANGUAGES:
            with override_settings(cadrumo_output_language=locale):
                overview = build_profile_overview(record, schema=schema, flow=flow)
            expected = profile_field_help(flow, locale=locale)
            served = {
                field.path: field.help
                for section in overview.sections
                for field in section.fields
                if field.help is not None
            }
            assert served == dict(expected)


def test_relocalizing_a_field_keeps_the_help_the_backend_served() -> None:
    with bundled_indexed_authority().operation() as authority:
        flow = build_setup_flow(authority)
        record = create_user_profile_record(
            context=authority.profile_create_context(),
            profile_id=_PROFILE_ID,
            setup_state=ProfileSetupState.INCOMPLETE,
            facts=(),
        )
        overview = build_profile_overview(record, schema=authority.profile_schema(), flow=flow)
        field = next(field for section in overview.sections for field in section.fields if field.path == "iva.regime")
        assert field.help is not None
        assert relocalize_profile_field(field).help == field.help
