"""The descendants operation replaces the whole family in an encrypted profile and words every refusal.

These tests drive the operation's write function against a real encrypted
profile and read the result back through the stored record and the served
household rows, so the writer, the domain decoder and the profile view are
checked to agree on one stored shape. Refusals are checked for the sentences the
operation serves in every language, for naming the row by its position and for
leaving the record untouched.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.operations.error_detail import build_operation_error_detail
from cadrumo.application.user_profile.capsule_record import ProfileRecordConflictError
from cadrumo.application.user_profile.descendant_rows import (
    DESCENDANT_COUNT_PATH,
    DESCENDANT_OBJECT_PATH,
    DescendantFamilyMutation,
    ProfileDescendantFact,
    ProfileDescendantRow,
    replace_profile_descendants,
)
from cadrumo.application.user_profile.fact_write import apply_manager_profile_field_mutation
from cadrumo.application.user_profile.family_rows import (
    ProfileFamilyGroupState,
    ProfileViewFamilyGroupItem,
    ProfileViewFamilyRowItem,
    family_row_items,
)
from cadrumo.application.user_profile.household_row_limit import declared_household_row_limit
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.descendant_relacion_catalogue import (
    descendant_relacion_adoption_token,
    descendant_relacion_entitling_tokens,
    descendant_relacion_tokens,
)
from cadrumo.domain.contribuyente.household_person_name import household_person_name_limit
from cadrumo.domain.user_profile.errors import UserProfileValidationError
from cadrumo.domain.user_profile.values import UserProfileRecord

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

# The 2025 Modelo 100 XSD declares Hijo with maxOccurs 15.
_DESCENDANT_LIMIT = 15
_ADULT_NIF = "12345678Z"
_WRONG_LETTER_NIF = "12345678A"
_FOREIGN_NIF = "X0001500M"
_ENTITY_NIF = "B00010157"


_BORN = (date.today() - timedelta(days=3650)).isoformat()
_ENTRY = (date.today() - timedelta(days=3590)).isoformat()
_SIBLING_BORN = (date.today() - timedelta(days=2800)).isoformat()


def _row(**leaves: str) -> ProfileDescendantRow:
    return ProfileDescendantRow(
        facts=tuple(ProfileDescendantFact(field_key=key, value=value) for key, value in leaves.items())
    )


def _text(value: object) -> str:
    """A stored fact as the profile's textual form: a yes-or-no answer is ``true`` or ``false``."""
    return str(value).lower() if isinstance(value, bool) else str(value)


class _World:
    """One registered, authenticated profile and the authority the operation runs under."""

    def __init__(self, profile_id: str, operation: PinnedAuthorityOperation) -> None:
        self.profile_id = profile_id
        self.operation = operation

    def record(self) -> UserProfileRecord:
        return ProfileRecordRepository.for_current_session(
            self.profile_id, profile_decode_context=self.operation.profile_decode_context()
        ).load(self.profile_id)

    def facts(self) -> dict[str, str]:
        return {
            fact.path: _text(fact.value)
            for fact in self.record().facts
            if (fact.path.startswith(f"{DESCENDANT_OBJECT_PATH}.") or fact.path == DESCENDANT_COUNT_PATH)
            and fact.value is not None
        }

    def replace(
        self, *rows: ProfileDescendantRow, baseline: UserProfileRecord | None = None
    ) -> DescendantFamilyMutation:
        current = baseline or self.record()
        return replace_profile_descendants(
            profile_id=self.profile_id,
            descendants=rows,
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
            operation=self.operation,
        )

    def served(self) -> tuple[ProfileViewFamilyGroupItem, tuple[ProfileViewFamilyRowItem, ...]]:
        values = {fact.path: _text(fact.value) for fact in self.record().facts if fact.value is not None}
        items = family_row_items(values, schema=self.operation.profile_schema(), operation=self.operation)
        group = next(
            item
            for item in items
            if isinstance(item, ProfileViewFamilyGroupItem) and item.group_key == DESCENDANT_OBJECT_PATH
        )
        rows = tuple(
            item
            for item in items
            if isinstance(item, ProfileViewFamilyRowItem) and item.group_key == DESCENDANT_OBJECT_PATH
        )
        return group, rows


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    secret = f"descendants-operation-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=secret),
        isolated_profile_storage_root(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="Descendants operation",
            passphrase=secret,
            profile_create_context=operation.profile_create_context(),
            profile_decode_context=operation.profile_decode_context(),
        )
        authenticate_profile_for_invocation(
            name=outcome.label,
            passphrase_callback=secret.__str__,
            profile_decode_context=operation.profile_decode_context(),
        )
        register_minimal_profile(profile_id=outcome.profile_id)
        yield _World(outcome.profile_id, operation)


def test_the_row_limit_is_the_one_the_design_declares(world: _World) -> None:
    assert declared_household_row_limit(world.operation, object_path=DESCENDANT_OBJECT_PATH) == _DESCENDANT_LIMIT


def test_a_family_is_stored_as_rows_with_its_count_and_served_back(world: _World) -> None:
    before = world.record()

    mutation = world.replace(
        _row(birth_date="2015-04-03", convivencia="true", custodia_compartida="true", nif=_ADULT_NIF),
        _row(birth_date="2020-08-09", convivencia="false", rentas_anuales="1200.50"),
    )

    assert (mutation.total, mutation.changed) == (2, True)
    assert mutation.record.record_revision == before.record_revision + 1
    assert world.facts() == {
        DESCENDANT_COUNT_PATH: "2",
        f"{DESCENDANT_OBJECT_PATH}.0.birth_date": "2015-04-03",
        f"{DESCENDANT_OBJECT_PATH}.0.convivencia": "true",
        f"{DESCENDANT_OBJECT_PATH}.0.custodia_compartida": "true",
        f"{DESCENDANT_OBJECT_PATH}.0.nif": _ADULT_NIF,
        f"{DESCENDANT_OBJECT_PATH}.1.birth_date": "2020-08-09",
        f"{DESCENDANT_OBJECT_PATH}.1.convivencia": "false",
        f"{DESCENDANT_OBJECT_PATH}.1.rentas_anuales": "1200.50",
    }
    group, rows = world.served()
    assert (group.state, group.row_count, group.stated_count) == (ProfileFamilyGroupState.ROWS, 2, "2")
    assert [row.row_index for row in rows] == ["0", "1"]


def test_a_valid_nif_or_nie_is_stored_in_canonical_form_and_an_absent_one_is_allowed(world: _World) -> None:
    world.replace(
        _row(birth_date="2015-04-03", nif="1234-5678-z"),
        _row(birth_date="2016-04-03", nif=_FOREIGN_NIF),
        _row(birth_date="2017-04-03"),
    )

    facts = world.facts()
    assert facts[f"{DESCENDANT_OBJECT_PATH}.0.nif"] == _ADULT_NIF
    assert facts[f"{DESCENDANT_OBJECT_PATH}.1.nif"] == _FOREIGN_NIF
    assert f"{DESCENDANT_OBJECT_PATH}.2.nif" not in facts


def test_a_nif_with_a_wrong_control_letter_is_refused_by_row_and_never_echoed(world: _World) -> None:
    before = world.record()

    with pytest.raises(UserProfileValidationError) as refused:
        world.replace(
            _row(birth_date="2015-04-03", nif=_ADULT_NIF), _row(birth_date="2016-04-03", nif=_WRONG_LETTER_NIF)
        )

    assert refused.value.context == {"row": 2}
    assert world.record().content_digest == before.content_digest
    for language in OutputLanguage:
        with override_settings(cadrumo_output_language=language.value):
            detail = build_operation_error_detail(refused.value)
        assert detail is not None and detail.refusal_words is not None
        assert not detail.refusal_words.startswith("application.")
        assert "2" in detail.refusal_words
        assert _WRONG_LETTER_NIF not in detail.refusal_words and _WRONG_LETTER_NIF not in repr(detail)


def test_a_smaller_family_clears_the_rows_it_no_longer_holds(world: _World) -> None:
    world.replace(
        _row(birth_date="2015-04-03", rentas_anuales="900"),
        _row(birth_date="2020-08-09"),
    )

    world.replace(_row(birth_date="2020-08-09"))

    assert world.facts() == {
        DESCENDANT_COUNT_PATH: "1",
        f"{DESCENDANT_OBJECT_PATH}.0.birth_date": "2020-08-09",
        f"{DESCENDANT_OBJECT_PATH}.0.convivencia": "true",
    }


def test_a_stated_zero_is_a_declared_empty_family_and_repeats_as_no_change(world: _World) -> None:
    world.replace(_row(birth_date="2015-04-03"))

    cleared = world.replace()

    assert (cleared.total, cleared.changed) == (0, True)
    group, rows = world.served()
    assert (group.state, group.stated_count, rows) == (ProfileFamilyGroupState.NONE_DECLARED, "0", ())
    assert world.replace().changed is False


def test_the_design_limit_is_accepted_and_one_more_is_refused(world: _World) -> None:
    full = tuple(_row(birth_date=f"20{10 + index}-01-01") for index in range(_DESCENDANT_LIMIT))
    assert world.replace(*full).total == _DESCENDANT_LIMIT
    before = world.record()

    with pytest.raises(UserProfileValidationError) as refused:
        world.replace(*full, _row(birth_date="2012-05-05"))

    assert refused.value.context == {"limit": _DESCENDANT_LIMIT, "count": _DESCENDANT_LIMIT + 1}
    assert world.record().content_digest == before.content_digest


@pytest.mark.parametrize(
    ("leaves", "row"),
    [
        ({"convivencia": "true"}, 1),
        ({"birth_date": "2015-02-30"}, 1),
        ({"birth_date": "2015-04-03", "convivencia": "perhaps"}, 1),
        ({"birth_date": "2015-04-03", "rentas_anuales": "12.500"}, 1),
        ({"birth_date": "2015-04-03", "rentas_anuales": "-5"}, 1),
        ({"birth_date": "2015-04-03", "relacion": "cousin"}, 1),
        ({"birth_date": "2015-04-03", "alta_posterior_nacimiento_mes": "13"}, 1),
        ({"birth_date": "2015-04-03", "apellidos_nombre": " 	 "}, 1),
        ({"birth_date": "2015-04-03", "custodia_compartida": "false"}, 1),
        ({"birth_date": "2015-04-03", "nif": _WRONG_LETTER_NIF}, 1),
        ({"birth_date": "2015-04-03", "nif": _ENTITY_NIF}, 1),
        ({"birth_date": "2015-04-03", "nif": "1234"}, 1),
    ],
)
def test_a_row_the_declaration_cannot_hold_is_refused_before_anything_is_written(
    world: _World, leaves: dict[str, str], row: int
) -> None:
    before = world.record()

    with pytest.raises(UserProfileValidationError) as refused:
        world.replace(_row(**leaves))

    assert refused.value.context is not None and refused.value.context["row"] == row
    assert world.record().content_digest == before.content_digest
    assert world.facts() == {}


@pytest.mark.parametrize(
    "leaves",
    [
        {"birth_date": "2015-04-03", "nif": _WRONG_LETTER_NIF},
        {"birth_date": "2015-04-03", "nif": _ENTITY_NIF},
        {"birth_date": "2015-04-03", "rentas_anuales": "12.500"},
        {"birth_date": "2015-02-30"},
    ],
)
def test_a_refused_value_leaves_no_chained_exception_carrying_what_was_typed(
    world: _World, leaves: dict[str, str]
) -> None:
    with pytest.raises(UserProfileValidationError) as refused:
        world.replace(_row(**leaves))

    assert refused.value.__cause__ is None
    assert refused.value.__context__ is None


def test_a_name_is_stored_collapsed_up_to_the_design_length_and_refused_one_past_it(world: _World) -> None:
    limit = household_person_name_limit(authority=world.operation)
    at_limit = "N" * limit
    elder, younger = (date.today() - timedelta(days=days) for days in (3700, 3300))
    world.replace(
        _row(birth_date=elder.isoformat(), apellidos_nombre="  Ortega   Navarro	Pablo "),
        _row(birth_date=younger.isoformat(), apellidos_nombre=at_limit),
    )

    assert world.facts()[f"{DESCENDANT_OBJECT_PATH}.0.apellidos_nombre"] == "Ortega Navarro Pablo"
    assert world.facts()[f"{DESCENDANT_OBJECT_PATH}.1.apellidos_nombre"] == at_limit
    _, rows = world.served()
    assert ("apellidos_nombre", "Ortega Navarro Pablo") in [(fact.leaf, fact.value) for fact in rows[0].facts]
    before = world.record()

    with pytest.raises(UserProfileValidationError) as refused:
        world.replace(_row(birth_date=elder.isoformat(), apellidos_nombre=at_limit + "N"))

    assert refused.value.context == {"row": 1, "limit": limit}
    assert world.record().content_digest == before.content_digest


def test_a_refusal_names_the_row_by_position(world: _World) -> None:
    with pytest.raises(UserProfileValidationError) as refused:
        world.replace(_row(birth_date="2015-04-03"), _row(birth_date="2016-04-03"), _row(convivencia="true"))

    assert refused.value.context is not None and refused.value.context["row"] == 3


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_every_refusal_serves_a_sentence_in_the_workers_language_and_never_echoes_the_value(
    world: _World, language: OutputLanguage
) -> None:
    typed = "zz-typed-value"
    attempts = (
        (_row(birth_date="2015-04-03", convivencia=typed), ("2",)),
        (_row(convivencia="true"), ("2",)),
        (_row(birth_date="2015-04-03", apellidos_nombre=typed * 10), ("2",)),
    )
    sentences: set[str] = set()
    with override_settings(cadrumo_output_language=language.value):
        for offender, expected in attempts:
            with pytest.raises(UserProfileValidationError) as refused:
                world.replace(_row(birth_date="2012-01-01"), offender)
            detail = build_operation_error_detail(refused.value)
            assert detail is not None and detail.refusal_words is not None
            assert detail.refusal_words_language is language
            assert not detail.refusal_words.startswith("application.")
            assert typed not in detail.refusal_words and typed not in repr(detail)
            assert all(token in detail.refusal_words for token in expected)
            sentences.add(detail.refusal_words)
    assert len(sentences) == len(attempts)


def test_the_over_limit_sentence_names_the_limit_and_the_count_in_every_language(world: _World) -> None:
    rows = tuple(_row(birth_date="2012-01-01") for _ in range(_DESCENDANT_LIMIT + 1))
    sentences: dict[OutputLanguage, str] = {}
    for language in OutputLanguage:
        with override_settings(cadrumo_output_language=language.value):
            with pytest.raises(UserProfileValidationError) as refused:
                world.replace(*rows)
            detail = build_operation_error_detail(refused.value)
        assert detail is not None and detail.refusal_words is not None
        assert str(_DESCENDANT_LIMIT) in detail.refusal_words and str(_DESCENDANT_LIMIT + 1) in detail.refusal_words
        sentences[language] = detail.refusal_words
    assert len(set(sentences.values())) == len(sentences)


def test_a_stale_baseline_is_refused_and_writes_nothing(world: _World) -> None:
    stale = world.record()
    world.replace(_row(birth_date="2015-04-03"))
    after = world.record()

    with pytest.raises(ProfileRecordConflictError):
        world.replace(_row(birth_date="2016-04-03"), baseline=stale)

    assert world.record().content_digest == after.content_digest


def _relation_tokens(operation: PinnedAuthorityOperation) -> tuple[str, str]:
    """The adoption token and one relation that is neither adoption nor entitling."""
    entitling = {token.value for token in descendant_relacion_entitling_tokens(authority=operation)}
    plain = next(
        token.value for token in descendant_relacion_tokens(authority=operation) if token.value not in entitling
    )
    return descendant_relacion_adoption_token(authority=operation).value, plain


@pytest.mark.parametrize("leaf", ["inscripcion_registro_civil", "acogimiento_resolucion"])
def test_a_date_stated_for_a_leaf_the_relation_does_not_ask_is_refused_and_writes_nothing(
    world: _World, leaf: str
) -> None:
    _adoption, plain = _relation_tokens(world.operation)
    before = world.record()

    with pytest.raises(UserProfileValidationError) as refused:
        world.replace(_row(birth_date=_BORN, relacion=plain, **{leaf: _ENTRY}))

    # The decoder refuses the incompatible pair as an invalid value; it neither drops nor keeps it.
    assert refused.value.translated_message == "application.user_profile.errors.descendant_value_invalid"
    assert refused.value.context is not None and refused.value.context["row"] == 1
    assert world.record().content_digest == before.content_digest
    assert world.facts() == {}


def test_the_date_an_adoption_asks_for_is_stored_with_it(world: _World) -> None:
    adoption, _plain = _relation_tokens(world.operation)

    world.replace(_row(birth_date=_BORN, relacion=adoption, inscripcion_registro_civil=_ENTRY))

    assert world.facts()[f"{DESCENDANT_OBJECT_PATH}.0.inscripcion_registro_civil"] == _ENTRY


def test_economic_dependence_stated_for_a_descendant_who_lives_with_the_taxpayer_is_stored_as_stated(
    world: _World,
) -> None:
    # Pinned as found: the profile does not refuse or drop a dependence the dependence question did not ask for.
    world.replace(_row(birth_date=_BORN, convivencia="true", dependencia_economica="true"))
    assert world.facts()[f"{DESCENDANT_OBJECT_PATH}.0.dependencia_economica"] == "true"

    # Naming the person without the dependence is what clears it: the row states the whole person.
    world.replace(_row(birth_date=_BORN, convivencia="true"))
    assert f"{DESCENDANT_OBJECT_PATH}.0.dependencia_economica" not in world.facts()


def test_a_stored_dependence_survives_adding_another_person_after_the_answer_it_hangs_on_changed(
    world: _World,
) -> None:
    world.replace(_row(birth_date=_BORN, convivencia="false", dependencia_economica="true"))
    # The cohabitation answer becomes yes by a one-leaf write; the dependence fact is left standing.
    apply_manager_profile_field_mutation(
        profile_id=world.profile_id,
        path=f"{DESCENDANT_OBJECT_PATH}.0.convivencia",
        value="true",
        profile_decode_context=world.operation.profile_decode_context(),
    )
    after_change = world.facts()
    assert after_change[f"{DESCENDANT_OBJECT_PATH}.0.convivencia"] == "true"
    assert after_change[f"{DESCENDANT_OBJECT_PATH}.0.dependencia_economica"] == "true"

    latest = world.record()
    replace_profile_descendants(
        profile_id=world.profile_id,
        add_row=_row(birth_date=_SIBLING_BORN),
        expected_revision=latest.record_revision,
        expected_content_digest=latest.content_digest,
        operation=world.operation,
    )
    assert world.facts()[f"{DESCENDANT_OBJECT_PATH}.0.dependencia_economica"] == "true"
