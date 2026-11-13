"""Household rows and wizard-worded choices, read from a real encrypted profile."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.family_rows import (
    ProfileFamilyGroupState,
    ProfileViewFamilyGroupItem,
    ProfileViewFamilyRowItem,
)
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.application.user_profile.view_operation import (
    PROFILE_VIEW_MAX_RESULT_BYTES,
    ProfileViewFieldItem,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
    ProfileViewRefusalCode,
)
from cadrumo.application.user_profile.view_reader import read_profile_view_page
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.core.identity.digest import ContentDigest
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.contribuyente.descendant import DescendantInfo
from cadrumo.domain.contribuyente.descendant_facts import descendant_facts_from_list
from cadrumo.domain.contribuyente.renta_codes import RentaDeclaracionType, RentaDisabilityGrade
from cadrumo.domain.user_profile.values import UserProfileFact

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]
_PROFILE_CREDENTIAL = "profile-family-rows-test-passphrase"
_DECLARATION_TYPE_PATH = "renta_filing.declaration_type"
_TAXPAYER_DISABILITY_PATH = "renta_taxpayer.disability_grade"


def _register_profile(*, facts: tuple[UserProfileFact, ...] = ()) -> UUID:
    with bundled_indexed_authority().operation() as authority:
        registered = register_profile_with_credentials(
            label="Profile family rows",
            passphrase=_PROFILE_CREDENTIAL,
            facts=facts,
            profile_create_context=authority.profile_create_context(),
            profile_decode_context=authority.profile_decode_context(),
        )
        authenticate_profile_for_invocation(
            name=registered.profile_id,
            passphrase_callback=lambda: _PROFILE_CREDENTIAL,
            profile_decode_context=authority.profile_decode_context(),
        )
    return UUID(registered.profile_id)


def _descendant_facts() -> tuple[UserProfileFact, ...]:
    with bundled_indexed_authority().operation() as authority:
        stored = descendant_facts_from_list(
            (
                DescendantInfo(
                    birth_date=date(2021, 5, 17),
                    discapacidad_grado=33,
                    convive_con_contribuyente=False,
                    rentas_anuales_euros=Decimal("1200.50"),
                    nif="12345678Z",
                ),
                DescendantInfo(birth_date=date(2024, 1, 2)),
            ),
            authority=authority,
        )
    return tuple(UserProfileFact(path=path, value=value) for path, value in stored)


def _read(profile_id: UUID, page_kind: ProfileViewPageKind, language: str) -> list[object]:
    items: list[object] = []
    cursor = 0
    revision: int | None = None
    digest: ContentDigest | None = None
    with bundled_indexed_authority().operation() as authority:
        while True:
            page = read_profile_view_page(
                ProfileViewOperationRequest(
                    profile_id=profile_id,
                    page_kind=page_kind,
                    cursor=cursor,
                    output_language=OutputLanguage(language),
                    expected_revision=revision,
                    expected_content_digest=digest,
                ),
                authority_operation=authority,
            )
            assert page.outcome == "page"
            assert len(page.model_dump_json().encode("utf-8")) <= PROFILE_VIEW_MAX_RESULT_BYTES
            items.extend(page.items)
            if page.next_cursor is None:
                return items
            cursor = page.next_cursor
            revision, digest = page.record_revision, page.content_digest


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
def test_descendants_are_served_as_stored_rows_in_the_wizard_words(tmp_path: Path, language: str) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register_profile(facts=_descendant_facts())
        items = _read(profile_id, ProfileViewPageKind.FAMILY_ROWS, language)
    groups = [item for item in items if isinstance(item, ProfileViewFamilyGroupItem)]
    rows = [item for item in items if isinstance(item, ProfileViewFamilyRowItem)]
    descendants, ascendants = groups
    assert descendants.group_key == "renta_family.descendiente"
    assert descendants.state is ProfileFamilyGroupState.ROWS
    assert descendants.row_count == 2 and descendants.stated_count == "2"
    leaves = {leaf.leaf: leaf for leaf in descendants.leaves}
    assert leaves["birth_date"].label == tr("wizard.setup.descendientes.birth-date.prompt", locale=language)
    assert leaves["birth_date"].required
    assert {choice.value: choice.label for choice in leaves["relacion"].choices}["descendiente"] == tr(
        "wizard.setup.descendientes.relacion.choices.descendiente.label", locale=language
    )
    assert [choice.value for choice in leaves["convivencia"].choices] == ["true", "false"]
    assert [choice.label for choice in leaves["convivencia"].choices] == [
        tr("flows.confirm.yes", locale=language),
        tr("flows.confirm.no", locale=language),
    ]
    assert {choice.value for choice in leaves["discapacidad"].choices} >= {"33", "65"}
    first, second = rows
    assert (first.row_index, second.row_index) == ("0", "1")
    stated = {fact.leaf: fact.value for fact in first.facts}
    assert stated["birth_date"] == "2021-05-17"
    assert stated["discapacidad"] == "33"
    assert stated["convivencia"] == "false"
    assert stated["rentas_anuales"] == "1200.50"
    assert stated["nif"] == "12345678Z"
    assert all(fact.path == f"renta_family.descendiente.0.{fact.leaf}" and not fact.masked for fact in first.facts)
    # Facts the row never stated are absent rather than served as zero or false.
    assert {fact.leaf for fact in second.facts} == {"birth_date", "convivencia"}
    assert descendants.label == tr("profile.schema.field.renta_family.descendiente.label", locale=language)
    assert ascendants.group_key == "renta_family.ascendiente"
    assert ascendants.label == tr("profile.schema.field.renta_family.ascendiente.label", locale=language)
    assert ascendants.state is ProfileFamilyGroupState.UNKNOWN
    assert ascendants.stated_count is None and ascendants.row_count == 0
    assert {leaf.leaf for leaf in ascendants.leaves} == {
        "nif",
        "apellidos_nombre",
        "birth_date",
        "fallecimiento",
        "convivientes",
        # The art. 59 and 61 LIRPF facts the mínimo por ascendientes turns on, and
        # the art. 60 disability facts, are editable leaves of every row.
        "rentas_anuales",
        "declaracion_propia",
        "discapacidad",
        "convivencia_mitad_periodo",
        "discapacidad_asistencia",
        "incapacidad_judicial",
    }


def test_no_stated_descendants_is_unknown_not_an_empty_household(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register_profile()
        items = _read(profile_id, ProfileViewPageKind.FAMILY_ROWS, "en")
    descendants = items[0]
    assert isinstance(descendants, ProfileViewFamilyGroupItem)
    assert descendants.state is ProfileFamilyGroupState.UNKNOWN
    assert descendants.stated_count is None and descendants.row_count == 0
    assert not any(isinstance(item, ProfileViewFamilyRowItem) for item in items)


def test_a_stated_count_of_zero_is_declared_none(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register_profile(facts=(UserProfileFact(path="renta_family.descendientes_count", value="0"),))
        items = _read(profile_id, ProfileViewPageKind.FAMILY_ROWS, "en")
    descendants = items[0]
    assert isinstance(descendants, ProfileViewFamilyGroupItem)
    assert descendants.state is ProfileFamilyGroupState.NONE_DECLARED
    assert descendants.stated_count == "0" and descendants.row_count == 0


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
def test_ascendants_are_served_as_stored_rows_in_the_family_words(tmp_path: Path, language: str) -> None:
    facts = (
        UserProfileFact(path="renta_family.ascendientes_count", value="1"),
        UserProfileFact(path="renta_family.ascendiente.0.nif", value="12345678Z"),
        UserProfileFact(path="renta_family.ascendiente.0.birth_date", value="1950-02-03"),
        UserProfileFact(path="renta_family.ascendiente.0.convivientes", value="2"),
    )
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register_profile(facts=facts)
        items = _read(profile_id, ProfileViewPageKind.FAMILY_ROWS, language)
    descendants, ascendants, row = items
    assert isinstance(descendants, ProfileViewFamilyGroupItem) and isinstance(ascendants, ProfileViewFamilyGroupItem)
    assert isinstance(row, ProfileViewFamilyRowItem)
    assert descendants.state is ProfileFamilyGroupState.UNKNOWN
    assert ascendants.state is ProfileFamilyGroupState.ROWS
    assert ascendants.row_count == 1 and ascendants.stated_count == "1"
    leaves = {leaf.leaf: leaf for leaf in ascendants.leaves}
    assert leaves["birth_date"].label == tr(
        "application.user_profile.family_rows.ascendiente.birth_date.label", locale=language
    )
    assert leaves["fallecimiento"].help == tr(
        "application.user_profile.family_rows.ascendiente.fallecimiento.help", locale=language
    )
    assert row.group_key == "renta_family.ascendiente" and row.row_index == "0"
    assert {fact.leaf: fact.value for fact in row.facts} == {
        "nif": "12345678Z",
        "birth_date": "1950-02-03",
        "convivientes": "2",
    }
    assert all(fact.path == f"renta_family.ascendiente.0.{fact.leaf}" and not fact.masked for fact in row.facts)


def test_a_stated_count_of_zero_ascendants_is_declared_none_and_leaves_descendants_unknown(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register_profile(facts=(UserProfileFact(path="renta_family.ascendientes_count", value="0"),))
        items = _read(profile_id, ProfileViewPageKind.FAMILY_ROWS, "en")
    descendants, ascendants = items
    assert isinstance(descendants, ProfileViewFamilyGroupItem) and isinstance(ascendants, ProfileViewFamilyGroupItem)
    assert descendants.state is ProfileFamilyGroupState.UNKNOWN
    assert ascendants.state is ProfileFamilyGroupState.NONE_DECLARED
    assert ascendants.stated_count == "0" and ascendants.row_count == 0


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
def test_a_stated_count_larger_than_the_stored_rows_is_incomplete_in_every_language(
    tmp_path: Path, language: str
) -> None:
    facts = (
        UserProfileFact(path="renta_family.ascendientes_count", value="3"),
        UserProfileFact(path="renta_family.ascendiente.0.birth_date", value="1950-02-03"),
    )
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register_profile(facts=facts)
        items = _read(profile_id, ProfileViewPageKind.FAMILY_ROWS, language)
    descendants, ascendants, row = items
    assert isinstance(descendants, ProfileViewFamilyGroupItem) and isinstance(ascendants, ProfileViewFamilyGroupItem)
    assert isinstance(row, ProfileViewFamilyRowItem)
    assert descendants.state is ProfileFamilyGroupState.UNKNOWN and descendants.incomplete_words is None
    assert ascendants.state is ProfileFamilyGroupState.INCOMPLETE
    assert (ascendants.stated_count, ascendants.row_count) == ("3", 1)
    assert ascendants.incomplete_words == tr(
        "application.user_profile.family_rows.incomplete", locale=language, stated="3", recorded=1
    )
    assert row.group_key == "renta_family.ascendiente" and row.row_index == "0"


def test_family_rows_page_keeps_the_revision_pin(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path), bundled_indexed_authority().operation() as authority:
        profile_id = _register_profile(facts=_descendant_facts())
        request = ProfileViewOperationRequest(profile_id=profile_id, page_kind=ProfileViewPageKind.FAMILY_ROWS, limit=1)
        first = read_profile_view_page(request, authority_operation=authority)
        assert first.next_cursor == 1 and first.total_items == 4
        stale = read_profile_view_page(
            request.model_copy(
                update={"expected_revision": first.record_revision, "expected_content_digest": "0" * 64}
            ),
            authority_operation=authority,
        )
        assert stale.refusal_code is ProfileViewRefusalCode.STALE_REVISION and not stale.items


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
def test_declaration_type_and_disability_grade_serve_the_registry_codes_with_wizard_words(
    tmp_path: Path, language: str
) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register_profile(facts=(UserProfileFact(path=_DECLARATION_TYPE_PATH, value="1"),))
        items = _read(profile_id, ProfileViewPageKind.OVERVIEW, language)
        with bundled_indexed_authority().operation() as authority:
            type_codes = RentaDeclaracionType.form_codes(authority=authority)
            grade_codes = RentaDisabilityGrade.form_codes(authority=authority)
    fields = {item.field.path: item.field for item in items if isinstance(item, ProfileViewFieldItem)}
    declaration = fields[_DECLARATION_TYPE_PATH]
    assert [(choice.value, choice.label) for choice in declaration.choices] == [
        (
            type_codes[RentaDeclaracionType.INDIVIDUAL],
            tr("wizard.setup.profile.taxation-type.choices.individual.label", locale=language),
        ),
        (
            type_codes[RentaDeclaracionType.JOINT],
            tr("wizard.setup.profile.taxation-type.choices.joint.label", locale=language),
        ),
    ]
    assert declaration.value == "1"
    grades = fields[_TAXPAYER_DISABILITY_PATH]
    assert grades.value is None
    assert {choice.value for choice in grades.choices} == set(grade_codes.values())
    # A field whose schema already closes the answer set keeps its own words.
    sex = fields["renta_taxpayer.sex"]
    assert [choice.value for choice in sex.choices] == ["H", "M"]
    # A multi-select wizard question is not a pick-one answer for its string field.
    assert not fields["taxpayer_type.irpf_income_categories"].choices
