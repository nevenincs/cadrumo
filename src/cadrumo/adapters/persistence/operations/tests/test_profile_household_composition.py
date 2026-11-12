"""A surface adds and removes one household person from what the profile view serves.

The view's family_rows page is read from a real encrypted profile in every
supported language and must carry everything a new row needs: the leaves with
their words, types and answer sets, the answers each leaf is asked after, and the
add and remove controls with their words and the registered operation they
submit. The change itself is a request of that operation stating one row to add
or one served row index to remove, executed by the operation's write function
against the read's revision; the people the change leaves alone keep every leaf
they state.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.operations.error_detail import build_operation_error_detail
from cadrumo.application.user_profile.ascendant_rows import (
    ProfileAscendantFact,
    ProfileAscendantRow,
    replace_profile_ascendants,
)
from cadrumo.application.user_profile.capsule_record import ProfileRecordConflictError
from cadrumo.application.user_profile.descendant_rows import (
    ProfileDescendantFact,
    ProfileDescendantRow,
    replace_profile_descendants,
)
from cadrumo.application.user_profile.family_rows import (
    ProfileFamilyLeafCondition,
    ProfileViewFamilyGroupItem,
    ProfileViewFamilyRowItem,
)
from cadrumo.application.user_profile.household_row_limit import declared_household_row_limit
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_ASCENDANTS_OPERATION_DEFINITION_ID,
    PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,
    ProfileAscendantsOperationRequest,
    ProfileDescendantsOperationRequest,
)
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.application.user_profile.view_operation import (
    PROFILE_VIEW_MAX_RESULT_BYTES,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
)
from cadrumo.application.user_profile.view_reader import read_profile_view_page
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.descendant_relacion_catalogue import (
    descendant_relacion_adoption_token,
    descendant_relacion_entitling_tokens,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.user_profile.errors import UserProfileValidationError
from cadrumo.domain.user_profile.schema import ProfileFieldType
from cadrumo.domain.user_profile.values import UserProfileRecord

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_ASCENDANT = "renta_family.ascendiente"
_DESCENDANT = "renta_family.descendiente"
_ACTIONS = "application.user_profile.family_rows.actions"
_COTIZACIONES = "application.user_profile.family_rows.descendiente.cotizaciones_ss_madre"


@dataclass(frozen=True)
class _Read:
    """One complete family_rows read: its revision pin, groups and rows."""

    revision: int
    digest: str
    groups: dict[str, ProfileViewFamilyGroupItem]
    rows: dict[str, tuple[ProfileViewFamilyRowItem, ...]]


class _World:
    """One registered, authenticated profile, read through the view and changed through the household doors."""

    def __init__(self, profile_id: str, operation: PinnedAuthorityOperation) -> None:
        self.profile_id = profile_id
        self.operation = operation

    def record(self) -> UserProfileRecord:
        return ProfileRecordRepository.for_current_session(
            self.profile_id, profile_decode_context=self.operation.profile_decode_context()
        ).load(self.profile_id)

    def read(self, language: str = "en") -> _Read:
        items: list[object] = []
        cursor, revision, digest = 0, None, None
        while True:
            page = read_profile_view_page(
                ProfileViewOperationRequest(
                    profile_id=UUID(self.profile_id),
                    page_kind=ProfileViewPageKind.FAMILY_ROWS,
                    cursor=cursor,
                    output_language=OutputLanguage(language),
                    expected_revision=revision,
                    expected_content_digest=digest,
                ),
                authority_operation=self.operation,
            )
            assert page.outcome == "page"
            assert len(page.model_dump_json().encode("utf-8")) <= PROFILE_VIEW_MAX_RESULT_BYTES
            items.extend(page.items)
            revision, digest = page.record_revision, page.content_digest
            if page.next_cursor is None:
                break
            cursor = page.next_cursor
        groups = {item.group_key: item for item in items if isinstance(item, ProfileViewFamilyGroupItem)}
        rows = {
            key: tuple(item for item in items if isinstance(item, ProfileViewFamilyRowItem) and item.group_key == key)
            for key in groups
        }
        assert revision is not None and digest is not None
        return _Read(revision=revision, digest=digest, groups=groups, rows=rows)

    def _wire(self, read: _Read, change: dict[str, object]) -> str:
        """The request as a surface sends it: JSON naming the read's revision and one change."""
        pin = {
            "profile_id": self.profile_id,
            "expected_revision": read.revision,
            "expected_content_digest": read.digest,
        }
        return json.dumps({**pin, **change})

    def ascendants(self, read: _Read, **change: object) -> int:
        request = ProfileAscendantsOperationRequest.model_validate_json(self._wire(read, change))
        return replace_profile_ascendants(
            profile_id=str(request.profile_id),
            ascendants=request.ascendants,
            add_row=request.add_row,
            remove_row_index=request.remove_row_index,
            expected_revision=request.expected_revision,
            expected_content_digest=request.expected_content_digest,
            operation=self.operation,
        ).total

    def descendants(self, read: _Read, **change: object) -> int:
        request = ProfileDescendantsOperationRequest.model_validate_json(self._wire(read, change))
        return replace_profile_descendants(
            profile_id=str(request.profile_id),
            descendants=request.descendants,
            add_row=request.add_row,
            remove_row_index=request.remove_row_index,
            expected_revision=request.expected_revision,
            expected_content_digest=request.expected_content_digest,
            operation=self.operation,
        ).total


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    secret = f"household-composition-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=secret),
        isolated_profile_storage_root(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="Household composition",
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


def _ascendant(**leaves: str) -> dict[str, object]:
    return {"facts": [{"field_key": key, "value": value} for key, value in leaves.items()]}


def _stated(row: ProfileViewFamilyRowItem) -> dict[str, str]:
    return {fact.leaf: fact.value for fact in row.facts}


def _stored_descendant_leaves(world: _World) -> dict[int, dict[str, str]]:
    """The stored descendant leaves by row, each in the profile's textual form (a yes or no is ``true``/``false``)."""
    rows: dict[int, dict[str, str]] = {}
    for fact in world.record().facts:
        if fact.path.startswith(f"{_DESCENDANT}.") and fact.value is not None:
            index, leaf = fact.path.removeprefix(f"{_DESCENDANT}.").split(".", 1)
            text = str(fact.value).lower() if isinstance(fact.value, bool) else str(fact.value)
            rows.setdefault(int(index), {})[leaf] = text
    return rows


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
def test_the_new_row_form_and_its_controls_are_served_in_every_language(world: _World, language: str) -> None:
    read = world.read(language)
    descendants, ascendants = read.groups[_DESCENDANT], read.groups[_ASCENDANT]

    leaves = {leaf.leaf: leaf for leaf in descendants.leaves}
    cotizaciones = leaves["cotizaciones_ss_madre"]
    assert cotizaciones.label == tr(f"{_COTIZACIONES}.label", locale=language)
    assert cotizaciones.help == tr(f"{_COTIZACIONES}.help", locale=language)
    assert (cotizaciones.field_type, cotizaciones.required, cotizaciones.choices) == (
        ProfileFieldType.DECIMAL,
        False,
        (),
    )
    order = [leaf.leaf for leaf in descendants.leaves]
    assert order.index("cotizaciones_ss_madre") == order.index("gastos_guarderia_mensuales") + 1
    adoption = descendant_relacion_adoption_token(authority=world.operation).value
    assert leaves["inscripcion_registro_civil"].shown_when == (
        ProfileFamilyLeafCondition(leaf="relacion", equals=adoption),
    )
    entitling = sorted(token.value for token in descendant_relacion_entitling_tokens(authority=world.operation))
    assert leaves["acogimiento_resolucion"].shown_when == tuple(
        ProfileFamilyLeafCondition(leaf="relacion", equals=token) for token in entitling
    )
    assert leaves["dependencia_economica"].shown_when == (
        ProfileFamilyLeafCondition(leaf="convivencia", equals="false"),
    )
    assert leaves["birth_date"].shown_when == () and leaves["birth_date"].required
    shown_after = {condition.leaf for leaf in descendants.leaves for condition in leaf.shown_when}
    assert shown_after <= set(order)
    assert all(leaf.shown_when == () for leaf in ascendants.leaves)

    # Nothing is stored yet: either person can be added, nobody can be removed.
    assert descendants.add_row_action is not None and ascendants.add_row_action is not None
    assert descendants.add_row_action.action_words == tr(f"{_ACTIONS}.add_descendiente", locale=language)
    assert descendants.add_row_action.target_operation_ids == (PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,)
    assert ascendants.add_row_action.action_words == tr(f"{_ACTIONS}.add_ascendiente", locale=language)
    assert ascendants.add_row_action.target_operation_ids == (PROFILE_ASCENDANTS_OPERATION_DEFINITION_ID,)
    assert descendants.remove_row_action is None and ascendants.remove_row_action is None


def test_the_control_words_differ_by_language_and_are_never_keys(world: _World) -> None:
    words = {language: world.read(language).groups[_ASCENDANT] for language in SUPPORTED_OUTPUT_LANGUAGES}
    adds = {group.add_row_action.action_words for group in words.values() if group.add_row_action is not None}
    assert len(adds) == len(SUPPORTED_OUTPUT_LANGUAGES)
    assert not any(text.startswith("application.") for text in adds)


def test_a_person_is_added_from_the_served_form_and_removed_by_the_served_index(world: _World) -> None:
    first = world.read()
    assert world.ascendants(first, add_row=_ascendant(nif="12345678z", birth_date="1948-03-04", convivientes="2")) == 1
    second = world.read()
    assert (
        world.ascendants(second, add_row=_ascendant(birth_date="1951-11-30", fallecimiento=f"{_YEAR - 1}-02-01")) == 2
    )

    third = world.read()
    group, rows = third.groups[_ASCENDANT], third.rows[_ASCENDANT]
    assert (group.row_count, group.stated_count) == (2, "2")
    assert [_stated(row) for row in rows] == [
        {"nif": "12345678Z", "birth_date": "1948-03-04", "convivientes": "2"},
        {"birth_date": "1951-11-30", "fallecimiento": f"{_YEAR - 1}-02-01"},
    ]
    assert group.remove_row_action is not None
    assert group.remove_row_action.action_words == tr(f"{_ACTIONS}.remove_ascendiente", locale="en")

    assert world.ascendants(third, remove_row_index=rows[0].row_index) == 1
    fourth = world.read()
    assert [_stated(row) for row in fourth.rows[_ASCENDANT]] == [
        {"birth_date": "1951-11-30", "fallecimiento": f"{_YEAR - 1}-02-01"}
    ]
    assert world.ascendants(fourth, remove_row_index=fourth.rows[_ASCENDANT][0].row_index) == 0
    emptied = world.read().groups[_ASCENDANT]
    assert (emptied.row_count, emptied.stated_count, emptied.remove_row_action) == (0, "0", None)


def test_removing_a_descendant_keeps_every_leaf_the_others_state(world: _World) -> None:
    kept_leaves = {
        "birth_date": f"{_YEAR - 5}-05-17",
        "convivencia": "false",
        "dependencia_economica": "true",
        "rentas_anuales": "1200.50",
        "cotizaciones_ss_madre": "2332.80",
        "segundo_ciclo_infantil_inicio_mes": "9",
        "nif": "12345678Z",
    }
    whole = (
        {"facts": [{"field_key": "birth_date", "value": f"{_YEAR - 7}-02-03"}]},
        {"facts": [{"field_key": key, "value": value} for key, value in kept_leaves.items()]},
    )
    assert world.descendants(world.read(), descendants=whole) == 2
    assert _stored_descendant_leaves(world) == {
        0: {"birth_date": f"{_YEAR - 7}-02-03", "convivencia": "true"},
        1: kept_leaves,
    }

    read = world.read()
    removed = read.rows[_DESCENDANT][0]
    assert world.descendants(read, remove_row_index=removed.row_index) == 1

    assert _stored_descendant_leaves(world) == {0: kept_leaves}
    served = world.read().rows[_DESCENDANT]
    assert _stated(served[0])["cotizaciones_ss_madre"] == "2332.80"


def test_a_change_against_a_stale_read_is_refused_and_writes_nothing(world: _World) -> None:
    stale = world.read()
    world.ascendants(stale, add_row=_ascendant(birth_date="1948-03-04"))
    current = world.record()

    with pytest.raises(ProfileRecordConflictError):
        world.ascendants(stale, add_row=_ascendant(birth_date="1950-01-01"))
    with pytest.raises(ProfileRecordConflictError):
        world.descendants(stale, remove_row_index="0")

    assert world.record().content_digest == current.content_digest


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_removing_a_row_that_is_not_stored_is_refused_in_words_and_writes_nothing(
    world: _World, language: OutputLanguage
) -> None:
    world.ascendants(world.read(), add_row=_ascendant(birth_date="1948-03-04"))
    read = world.read()
    before = world.record()

    with override_settings(cadrumo_output_language=language.value):
        with pytest.raises(UserProfileValidationError) as ascendant:
            world.ascendants(read, remove_row_index="1")
        with pytest.raises(UserProfileValidationError) as descendant:
            world.descendants(read, remove_row_index="0")
        words = [build_operation_error_detail(refused.value) for refused in (ascendant, descendant)]

    assert all(detail is not None and detail.refusal_words for detail in words)
    sentences = {detail.refusal_words for detail in words if detail is not None}
    assert len(sentences) == 2 and not any(text is None or text.startswith("application.") for text in sentences)
    assert world.record().content_digest == before.content_digest


def test_a_full_group_offers_no_add_and_an_added_row_past_the_limit_is_refused(world: _World) -> None:
    limit = declared_household_row_limit(world.operation, object_path=_ASCENDANT)
    assert limit is not None
    full = [_ascendant(birth_date=f"19{40 + index}-01-01") for index in range(limit)]
    world.ascendants(world.read(), ascendants=full)
    read = world.read()
    group = read.groups[_ASCENDANT]
    assert group.row_count == limit and group.add_row_action is None and group.remove_row_action is not None
    before = world.record()

    with pytest.raises(UserProfileValidationError) as refused:
        world.ascendants(read, add_row=_ascendant(birth_date="1950-01-01"))

    assert refused.value.context == {"limit": limit, "count": limit + 1}
    assert world.record().content_digest == before.content_digest


def test_an_added_row_is_validated_like_a_whole_set(world: _World) -> None:
    read = world.read()
    before = world.record()

    with pytest.raises(UserProfileValidationError) as refused:
        world.descendants(read, add_row={"facts": [{"field_key": "birth_date", "value": f"{_YEAR - 6}-02-30"}]})

    assert refused.value.context == {"row": 1}
    assert world.record().content_digest == before.content_digest


@pytest.mark.parametrize(
    "change",
    [
        {},
        {"ascendants": [], "remove_row_index": "0"},
        {"add_row": _ascendant(birth_date="1948-03-04"), "remove_row_index": "0"},
        {"remove_row_index": "01"},
        {"remove_row_index": "-1"},
        {"remove_row_index": "x"},
    ],
)
def test_a_request_states_exactly_one_change_with_a_canonical_index(change: dict[str, object]) -> None:
    base = {"profile_id": str(UUID(int=1)), "expected_revision": 1, "expected_content_digest": "0" * 64}
    with pytest.raises(ValidationError):
        ProfileAscendantsOperationRequest.model_validate_json(json.dumps({**base, **change}))
    descendant_change = {key: value for key, value in change.items() if key != "ascendants"}
    if "ascendants" in change:
        descendant_change["descendants"] = change["ascendants"]
    with pytest.raises(ValidationError):
        ProfileDescendantsOperationRequest.model_validate_json(json.dumps({**base, **descendant_change}))


def test_one_change_of_each_kind_is_a_valid_request() -> None:
    base = {"profile_id": str(UUID(int=1)), "expected_revision": 1, "expected_content_digest": "0" * 64}
    for change in ({"ascendants": []}, {"add_row": _ascendant(birth_date="1948-03-04")}, {"remove_row_index": "12"}):
        ProfileAscendantsOperationRequest.model_validate_json(json.dumps({**base, **change}))
    for change in (
        {"descendants": []},
        {"add_row": _ascendant(birth_date=f"{_YEAR - 6}-01-01")},
        {"remove_row_index": "0"},
    ):
        ProfileDescendantsOperationRequest.model_validate_json(json.dumps({**base, **change}))


def test_an_added_row_keeps_its_values_out_of_the_request_repr() -> None:
    request = ProfileAscendantsOperationRequest(
        profile_id=UUID(int=1),
        expected_revision=1,
        expected_content_digest="0" * 64,
        add_row=ProfileAscendantRow(facts=(ProfileAscendantFact(field_key="nif", value="12345678Z"),)),
    )
    assert "12345678Z" not in repr(request)
    descendant = ProfileDescendantsOperationRequest(
        profile_id=UUID(int=1),
        expected_revision=1,
        expected_content_digest="0" * 64,
        add_row=ProfileDescendantRow(facts=(ProfileDescendantFact(field_key="nif", value="12345678Z"),)),
    )
    assert "12345678Z" not in repr(descendant)
