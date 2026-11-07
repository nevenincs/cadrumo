"""Generate the desktop's household fixture from the real profile operations.

Each state starts from the ``asalariada-familia`` persona of the canonical catalogue, replayed
through the production profile operations without its household; its household is then
written through the same replacement the desktop's edits use (``replace_profile_descendants``
and ``replace_profile_ascendants``), then read as the ``family_rows`` page stream of
``user-profile.view`` in every language. The masked state reads the same function against a
copy of the schema that declares the stored descendant object secret, because the shipped
schema masks none of the household. The single-parent states state the family situation, and
the answer to whether the parent lives with the child's other parent, through the profile
fact writer, so the question the stream serves beside the groups is read in each of its
states. The refusals are the registered
error details an ascendants or descendants replacement settles with. Every person written is
one of the persona's household rows; a state that needs more people than the persona has
repeats its rows without their identity. No stored user profile is read; run after publishing
a changed profile schema, wizard wording, design or persona.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, cast

from dev.fixture_projections.location import family_directory, scratch_tree
from dev.fixture_projections.producer_output import emit, producer_arguments
from dev.prettier_json import dump_json

if TYPE_CHECKING:
    from cadrumo.application.user_profile.ascendant_rows import ProfileAscendantRow
    from cadrumo.application.user_profile.descendant_rows import ProfileDescendantRow
    from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
    from cadrumo.domain.user_profile.schema import ProfileFieldDefinition, ProfileSchemaDefinition
    from cadrumo.domain.user_profile.values import UserProfileRecord
    from cadrumo.entrypoints.tests.persona_materialisation import MaterialisedPersona

LANGUAGES = ("en", "es", "ca", "hu")
PROFILE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
PERSONA_ID = "asalariada-familia"
"""The catalogue persona whose household every state writes."""
_COUNTS = {
    "descendants": "renta_family.descendientes_count",
    "ascendants": "renta_family.ascendientes_count",
}


@dataclass(frozen=True, slots=True)
class Household:
    """What one state's profile holds: people written, and the counts stated over them where they differ."""

    descendants: int | None
    ascendants: int | None
    stated: dict[str, str] = field(default_factory=dict)
    #: Profile facts stated beside the household, as (path, value).
    facts: tuple[tuple[str, str | None], ...] = ()
    #: The shipped schema masks no household fact, so this state reads against a copy that does.
    secret: bool = False


_COHABITATION_PATH = "renta_family.convive_con_otro_progenitor"
#: The persona is married and states whether she lives with her children's other parent; a single parent who
#: has not said so yet takes both back.
_SINGLE_PARENT: tuple[tuple[str, str | None], ...] = (
    ("renta_family.situacion_familiar", "soltero"),
    (_COHABITATION_PATH, None),
)

STATES: dict[str, Household] = {
    "unknown": Household(None, None),
    "none_declared": Household(0, 0),
    "rows": Household(2, 2),
    "incomplete": Household(1, 1, stated={"descendants": "3", "ascendants": "2"}),
    "at_cap": Household(15, 4),
    "masked": Household(2, 1, secret=True),
    "married": Household(None, None, facts=(("renta_family.situacion_familiar", "casado"),)),
    "single_parent_unstated": Household(None, None, facts=_SINGLE_PARENT),
    "single_parent_lives_with": Household(None, None, facts=(*_SINGLE_PARENT, (_COHABITATION_PATH, "true"))),
    "single_parent_apart": Household(None, None, facts=(*_SINGLE_PARENT, (_COHABITATION_PATH, "false"))),
}


def _rows(persona: MaterialisedPersona, members: str, count: int) -> tuple[tuple[tuple[str, str], ...], ...]:
    """``count`` of the persona's descendant or ascendant rows, as the replacement takes them.

    The persona's own people come first, with their identity; past them its rows repeat without one,
    because an identity is bound to one person only.
    """
    from cadrumo.entrypoints.tests.persona_materialisation import household_leaves

    own = getattr(persona.persona, members)
    if not own:
        raise SystemExit(f"{PERSONA_ID} states no {members}")
    leaves = [household_leaves(persona.persona, member, persona.world.envelope) for member in own]
    return tuple(
        leaves[index]
        if index < len(leaves)
        else tuple(leaf for leaf in leaves[index % len(leaves)] if leaf[0] != "nif")
        for index in range(count)
    )


def _descendants(rows: tuple[tuple[tuple[str, str], ...], ...]) -> tuple[ProfileDescendantRow, ...]:
    from cadrumo.application.user_profile.descendant_rows import ProfileDescendantFact, ProfileDescendantRow

    return tuple(
        ProfileDescendantRow(facts=tuple(ProfileDescendantFact(field_key=key, value=value) for key, value in row))
        for row in rows
    )


def _ascendants(rows: tuple[tuple[tuple[str, str], ...], ...]) -> tuple[ProfileAscendantRow, ...]:
    from cadrumo.application.user_profile.ascendant_rows import ProfileAscendantFact, ProfileAscendantRow

    return tuple(
        ProfileAscendantRow(facts=tuple(ProfileAscendantFact(field_key=key, value=value) for key, value in row))
        for row in rows
    )


def _record(persona: MaterialisedPersona) -> UserProfileRecord:
    from cadrumo.entrypoints.tests.persona_materialisation import load_profile_record

    return load_profile_record(persona.world)


def _write(persona: MaterialisedPersona, shape: Household) -> None:
    """Write the household the way the desktop's edits do, then state any count over it."""
    from cadrumo.application.user_profile.ascendant_rows import replace_profile_ascendants
    from cadrumo.application.user_profile.descendant_rows import replace_profile_descendants
    from cadrumo.application.user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
    from cadrumo.domain.user_profile.values import UserProfileFact

    operation = persona.world.operation
    profile_id = str(persona.world.profile_id)
    if shape.descendants is not None:
        current = _record(persona)
        replace_profile_descendants(
            profile_id=profile_id,
            descendants=_descendants(_rows(persona, "descendants", shape.descendants)),
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
            operation=operation,
        )
    if shape.ascendants is not None:
        current = _record(persona)
        replace_profile_ascendants(
            profile_id=profile_id,
            ascendants=_ascendants(_rows(persona, "ascendants", shape.ascendants)),
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
            operation=operation,
        )
    if shape.facts:
        apply_profile_fact_changes(
            profile_id=profile_id,
            changes=tuple(UserProfileFact(path=path, value=value) for path, value in shape.facts),
            door=ProfileFactWriteDoor.MANAGER_FIELD,
            expected_record=_record(persona),
            profile_decode_context=operation.profile_decode_context(),
        )
    if shape.stated:
        apply_profile_fact_changes(
            profile_id=profile_id,
            changes=tuple(UserProfileFact(path=_COUNTS[group], value=count) for group, count in shape.stated.items()),
            door=ProfileFactWriteDoor.MANAGER_DESCENDANTS,
            expected_record=_record(persona),
            profile_decode_context=operation.profile_decode_context(),
        )


def _secret_schema(operation: PinnedAuthorityOperation) -> ProfileSchemaDefinition:
    """The profile schema with the stored descendant object declared secret."""
    from cadrumo.core.classification.policies import SensitivityClass

    schema = operation.profile_schema()

    def secret(declared: ProfileFieldDefinition) -> ProfileFieldDefinition:
        if declared.key != "descendiente":
            return declared
        return declared.model_copy(update={"sensitivity": SensitivityClass.SECRET})

    sections = tuple(
        section.model_copy(update={"fields": tuple(secret(declared) for declared in section.fields)})
        if section.key == "renta_family"
        else section
        for section in schema.sections
    )
    return schema.model_copy(update={"sections": sections})


def _items(persona: MaterialisedPersona, language: str, *, secret: bool) -> list[dict[str, object]]:
    """The ``family_rows`` stream as the profile view serves it, read to its last page."""
    from cadrumo.application.user_profile.family_rows import family_row_items
    from cadrumo.application.user_profile.projections import record_to_path_values
    from cadrumo.application.user_profile.view_operation import (
        ProfileViewOperationRequest,
        ProfileViewPageKind,
    )
    from cadrumo.application.user_profile.view_reader import read_profile_view_page
    from cadrumo.core.external_constants import OutputLanguage

    operation = persona.world.operation
    items: list[dict[str, object]] = []
    cursor = 0
    revision = None
    digest = None
    while True:
        page = read_profile_view_page(
            ProfileViewOperationRequest(
                profile_id=persona.world.profile_id,
                page_kind=ProfileViewPageKind.FAMILY_ROWS,
                cursor=cursor,
                output_language=OutputLanguage(language),
                expected_revision=revision,
                expected_content_digest=digest,
            ),
            authority_operation=operation,
        )
        items.extend(json.loads(item.model_dump_json()) for item in page.items)
        if page.next_cursor is None:
            break
        cursor, revision, digest = page.next_cursor, page.record_revision, page.content_digest
    if not secret:
        return items
    values = record_to_path_values(_record(persona))
    served = family_row_items(values, schema=_secret_schema(operation), operation=operation)
    return [json.loads(item.model_dump_json()) for item in served]


def _refusal_value() -> str:
    """A NIF the catalogue keeps for refusal tests: its control letter does not match."""
    from cadrumo.tests.personas import identity_catalogue

    return next(refusal.value for refusal in identity_catalogue().refusals if refusal.kind == "nif")


def _first(persona: MaterialisedPersona, members: str, *keys: str) -> dict[str, str]:
    """The persona's first descendant or ascendant row, reduced to ``keys``."""
    (row,) = _rows(persona, members, 1)
    return {key: value for key, value in row if key in keys}


def _first_name(persona: MaterialisedPersona, members: str) -> str:
    """The given name of the persona's first descendant or ascendant."""
    member = getattr(persona.persona, members)[0]
    if member.identity is None:
        raise SystemExit(f"{PERSONA_ID}'s first {members} row names no identity")
    return persona.persona.identities.role(member.identity).field("name")


def _ascendant_sets(persona: MaterialisedPersona) -> dict[str, tuple[ProfileAscendantRow, ...]]:
    from cadrumo.application.user_profile.ascendant_rows import ProfileAscendantFact, ProfileAscendantRow

    def person(leaves: dict[str, str]) -> ProfileAscendantRow:
        return ProfileAscendantRow(
            facts=tuple(ProfileAscendantFact(field_key=key, value=value) for key, value in leaves.items())
        )

    born = _first(persona, "ascendants", "birth_date")
    return {
        "ascendants_over_limit": tuple(person(born) for _ in range(5)),
        "ascendants_second_nif_invalid": (person(born), person({"nif": _refusal_value(), **born})),
        "ascendants_first_birth_date_missing": (person(_first(persona, "ascendants", "nif")),),
        "ascendants_fact_unsupported": (person({**born, "apellidos_nombre": _first_name(persona, "ascendants")}),),
    }


def _descendant_sets(persona: MaterialisedPersona) -> dict[str, tuple[ProfileDescendantRow, ...]]:
    from cadrumo.application.user_profile.descendant_rows import ProfileDescendantFact, ProfileDescendantRow

    def person(leaves: dict[str, str]) -> ProfileDescendantRow:
        return ProfileDescendantRow(
            facts=tuple(ProfileDescendantFact(field_key=key, value=value) for key, value in leaves.items())
        )

    born = _first(persona, "descendants", "birth_date")
    return {
        "descendants_over_limit": tuple(person(born) for _ in range(16)),
        "descendants_second_value_invalid": (person(born), person({**born, "convivencia": "perhaps"})),
        "descendants_first_birth_date_missing": (person({"convivencia": "true"}),),
        "descendants_fact_unsupported": (person({**born, "apellidos_nombre": _first_name(persona, "descendants")}),),
    }


def _refusal(persona: MaterialisedPersona, language: str, name: str) -> dict[str, object]:
    """Settle one refused replacement as the registered executor does, and keep its recorded detail."""
    from cadrumo.application.operations.error_detail import build_operation_error_detail
    from cadrumo.application.user_profile.ascendant_rows import replace_profile_ascendants
    from cadrumo.application.user_profile.descendant_rows import replace_profile_descendants
    from cadrumo.core.config import override_settings
    from cadrumo.core.errors.hierarchy import CadrumoError

    current = _record(persona)
    profile_id = str(persona.world.profile_id)
    operation = persona.world.operation
    try:
        with override_settings(cadrumo_output_language=language):
            if name.startswith("ascendants_"):
                replace_profile_ascendants(
                    profile_id=profile_id,
                    ascendants=_ascendant_sets(persona)[name],
                    expected_revision=current.record_revision,
                    expected_content_digest=current.content_digest,
                    operation=operation,
                )
            else:
                replace_profile_descendants(
                    profile_id=profile_id,
                    descendants=_descendant_sets(persona)[name],
                    expected_revision=current.record_revision,
                    expected_content_digest=current.content_digest,
                    operation=operation,
                )
    except CadrumoError as error:
        with override_settings(cadrumo_output_language=language):
            detail = build_operation_error_detail(error)
        if detail is None:
            raise SystemExit(f"{name} records no error detail") from error
        return cast("dict[str, object]", json.loads(detail.model_dump_json()))
    raise SystemExit(f"{name} was not refused")


@contextmanager
def _persona(root: Path, name: str) -> Generator[MaterialisedPersona]:
    """A copy of the persona replayed without its household, for one state to write into."""
    from cadrumo.entrypoints.tests.persona_materialisation import ReplayScope, materialised_persona

    with materialised_persona(
        PERSONA_ID, root / name, ReplayScope.PROFILE, reuse=True, complete_setup=False
    ) as persona:
        yield persona


def render_fixture(root: Path) -> str:
    """Read every state and every refusal through the application, in every language."""
    from cadrumo.core.config import override_settings
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition

    reads: dict[str, dict[str, object]] = {}
    refusals: dict[str, dict[str, object]] = {}
    with profile_adapter_composition(), bundled_indexed_authority().operation():
        for state, shape in STATES.items():
            with _persona(root, state) as persona:
                _write(persona, shape)
                record = _record(persona)
                items: dict[str, list[dict[str, object]]] = {}
                for language in LANGUAGES:
                    with override_settings(cadrumo_output_language=language):
                        items[language] = _items(persona, language, secret=shape.secret)
            reads[state] = {
                "record_revision": record.record_revision,
                "content_digest": hashlib.sha256(f"household-{state}".encode()).hexdigest(),
                "items": items,
            }
        with _persona(root, "refusals") as persona:
            _write(persona, STATES["rows"])
            for name in (*_ascendant_sets(persona), *_descendant_sets(persona)):
                refusals[name] = {language: _refusal(persona, language, name) for language in LANGUAGES}
    return dump_json({"profile_id": PROFILE_ID, "reads": reads, "refusals": refusals})


def main() -> None:
    """Write, verify or redirect the synthetic browser fixture."""
    arguments = producer_arguments(__doc__)
    target = family_directory("desktop-household") / "household.json"
    with scratch_tree() as tmp:
        rendered = render_fixture(Path(tmp))
    emit({target: rendered}, arguments, remedy="uv run --no-sync python -m dev.desktop_household_fixture")


if __name__ == "__main__":
    main()
