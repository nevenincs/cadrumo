"""Generate the desktop's household fixture from the real profile operations.

Each state is a synthetic profile whose household is written through the same replacement
the desktop's edits use (``replace_profile_descendants`` and ``replace_profile_ascendants``),
then read as the ``family_rows`` page stream of ``user-profile.view`` in every language. The
masked state reads the same function against a copy of the schema that declares the stored
descendant object secret, because the shipped schema masks none of the household. The
refusals are the registered error details an ascendants replacement settles with. No stored
user profile is read; run after publishing a changed profile schema, wizard wording or design.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, cast
from uuid import UUID

from dev.temporary_output import prepare_temp_root

if TYPE_CHECKING:
    from cadrumo.application.user_profile.ascendant_rows import ProfileAscendantRow
    from cadrumo.application.user_profile.descendant_rows import ProfileDescendantRow
    from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
    from cadrumo.domain.user_profile.schema import ProfileFieldDefinition, ProfileSchemaDefinition
    from cadrumo.domain.user_profile.values import UserProfileRecord

LANGUAGES = ("en", "es", "ca", "hu")
PROFILE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_BUCKET_ID = "13000000-0000-4000-8000-000000000741"
_COUNTS = {
    "descendants": "renta_family.descendientes_count",
    "ascendants": "renta_family.ascendientes_count",
}
#: One synthetic ascendant per entry: its stored leaves.
_ASCENDANTS: tuple[dict[str, str], ...] = (
    {"nif": "12345678Z", "birth_date": "1948-03-04", "convivientes": "2"},
    {"nif": "X1234567L", "birth_date": "1951-11-30", "fallecimiento": "2025-02-01"},
    {"birth_date": "1940-01-01"},
    {"nif": "87654321X", "birth_date": "1945-06-15"},
)


@dataclass(frozen=True, slots=True)
class Household:
    """What one state's profile holds: people written, and the counts stated over them where they differ."""

    descendants: int | None
    ascendants: int | None
    stated: dict[str, str] = field(default_factory=dict)
    #: The shipped schema masks no household fact, so this state reads against a copy that does.
    secret: bool = False


STATES: dict[str, Household] = {
    "unknown": Household(None, None),
    "none_declared": Household(0, 0),
    "rows": Household(2, 2),
    "incomplete": Household(1, 1, stated={"descendants": "3", "ascendants": "2"}),
    "at_cap": Household(15, 4),
    "masked": Household(2, 1, secret=True),
}


def _descendants(operation: PinnedAuthorityOperation, count: int) -> tuple[ProfileDescendantRow, ...]:
    from cadrumo.application.user_profile.descendant_rows import encode_descendant_rows
    from cadrumo.domain.contribuyente.descendant import DescendantInfo

    people = tuple(
        DescendantInfo(
            birth_date=date(2012 + index % 12, 1 + index % 12, 1 + index % 27),
            convive_con_contribuyente=index % 2 == 0,
            nif="12345678Z" if index == 0 else None,
        )
        for index in range(count)
    )
    return encode_descendant_rows(people, authority=operation)


def _ascendants(count: int) -> tuple[ProfileAscendantRow, ...]:
    from cadrumo.application.user_profile.ascendant_rows import ProfileAscendantFact, ProfileAscendantRow

    return tuple(
        ProfileAscendantRow(
            facts=tuple(ProfileAscendantFact(field_key=key, value=value) for key, value in person.items())
        )
        for person in _ASCENDANTS[:count]
    )


def _record(operation: PinnedAuthorityOperation) -> UserProfileRecord:
    from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository

    return ProfileRecordRepository.for_current_session(
        _BUCKET_ID, profile_decode_context=operation.profile_decode_context()
    ).load(_BUCKET_ID)


def _seed_base() -> None:
    from datetime import UTC, datetime

    from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
        profile_authority_contexts,
        seed_test_profile_record,
    )
    from cadrumo.application.modelo.tests.profile_fixture_values import MODELO_READY_PROFILE_FACTS
    from cadrumo.domain.user_profile.values import ProfileSetupState, create_user_profile_record

    create_context, _ = profile_authority_contexts()
    moment = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
    seed_test_profile_record(
        create_user_profile_record(
            context=create_context,
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=MODELO_READY_PROFILE_FACTS,
            created_at=moment,
            updated_at=moment,
        )
    )


def _write(operation: PinnedAuthorityOperation, shape: Household) -> None:
    """Write the household the way the desktop's edits do, then state any count over it."""
    from cadrumo.application.user_profile.ascendant_rows import replace_profile_ascendants
    from cadrumo.application.user_profile.descendant_rows import replace_profile_descendants
    from cadrumo.application.user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
    from cadrumo.domain.user_profile.values import UserProfileFact

    _seed_base()
    if shape.descendants is not None:
        current = _record(operation)
        replace_profile_descendants(
            profile_id=_BUCKET_ID,
            descendants=_descendants(operation, shape.descendants),
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
            operation=operation,
        )
    if shape.ascendants is not None:
        current = _record(operation)
        replace_profile_ascendants(
            profile_id=_BUCKET_ID,
            ascendants=_ascendants(shape.ascendants),
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
            operation=operation,
        )
    if shape.stated:
        apply_profile_fact_changes(
            profile_id=_BUCKET_ID,
            changes=tuple(UserProfileFact(path=_COUNTS[group], value=count) for group, count in shape.stated.items()),
            door=ProfileFactWriteDoor.MANAGER_DESCENDANTS,
            expected_record=_record(operation),
            profile_decode_context=operation.profile_decode_context(),
        )


def _secret_schema(operation: PinnedAuthorityOperation) -> ProfileSchemaDefinition:
    """The profile schema with the stored descendant object declared secret."""
    from cadrumo.domain.user_profile.schema import SensitivityClass

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


def _items(operation: PinnedAuthorityOperation, language: str, *, secret: bool) -> list[dict[str, object]]:
    """The ``family_rows`` stream as the profile view serves it, read to its last page."""
    from cadrumo.application.user_profile.family_rows import family_row_items
    from cadrumo.application.user_profile.projections import record_to_path_values
    from cadrumo.application.user_profile.view_operation import (
        ProfileViewOperationRequest,
        ProfileViewPageKind,
    )
    from cadrumo.application.user_profile.view_reader import read_profile_view_page
    from cadrumo.core.external_constants import OutputLanguage

    items: list[dict[str, object]] = []
    cursor = 0
    revision = None
    digest = None
    while True:
        page = read_profile_view_page(
            ProfileViewOperationRequest(
                profile_id=UUID(_BUCKET_ID),
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
    values = record_to_path_values(_record(operation))
    served = family_row_items(values, schema=_secret_schema(operation), operation=operation)
    return [json.loads(item.model_dump_json()) for item in served]


def _refusal(operation: PinnedAuthorityOperation, language: str, name: str) -> dict[str, object]:
    """Settle one refused ascendants replacement as the registered executor does, and keep its recorded detail."""
    from cadrumo.application.operations.error_detail import build_operation_error_detail
    from cadrumo.application.user_profile.ascendant_rows import (
        ProfileAscendantFact,
        ProfileAscendantRow,
        replace_profile_ascendants,
    )
    from cadrumo.core.config import override_settings
    from cadrumo.core.errors.hierarchy import CadrumoError

    def person(**leaves: str) -> ProfileAscendantRow:
        return ProfileAscendantRow(
            facts=tuple(ProfileAscendantFact(field_key=key, value=value) for key, value in leaves.items())
        )

    sets = {
        "over_limit": tuple(person(birth_date="1940-01-01") for _ in range(5)),
        "second_nif_invalid": (person(birth_date="1940-01-01"), person(nif="12345678A", birth_date="1950-01-01")),
        "first_birth_date_missing": (person(nif="12345678Z"),),
    }
    current = _record(operation)
    try:
        with override_settings(cadrumo_output_language=language):
            replace_profile_ascendants(
                profile_id=_BUCKET_ID,
                ascendants=sets[name],
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


def render_fixture(root: Path) -> str:
    """Read every state and every refusal through the application, in every language."""
    from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
    from cadrumo.core.config import override_settings
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition

    reads: dict[str, dict[str, object]] = {}
    refusals: dict[str, dict[str, object]] = {}
    with (
        profile_adapter_composition(),
        isolated_runtime_profile(tmp_path=root, bucket_id=_BUCKET_ID),
        bundled_indexed_authority().operation() as operation,
    ):
        for state, shape in STATES.items():
            _write(operation, shape)
            record = _record(operation)
            items: dict[str, list[dict[str, object]]] = {}
            for language in LANGUAGES:
                with override_settings(cadrumo_output_language=language):
                    items[language] = _items(operation, language, secret=shape.secret)
            reads[state] = {
                "record_revision": record.record_revision,
                "content_digest": hashlib.sha256(f"household-{state}".encode()).hexdigest(),
                "items": items,
            }
        _write(operation, STATES["rows"])
        for name in ("over_limit", "second_nif_invalid", "first_birth_date_missing"):
            refusals[name] = {language: _refusal(operation, language, name) for language in LANGUAGES}
    return (
        json.dumps({"profile_id": PROFILE_ID, "reads": reads, "refusals": refusals}, ensure_ascii=False, indent=2)
        + "\n"
    )


def main() -> None:
    """Write or verify the checked-in, synthetic browser fixture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = Path(__file__).resolve().parents[1] / "native/desktop/frontend/src/dev/fixtures/household.json"
    with tempfile.TemporaryDirectory(dir=prepare_temp_root()) as tmp:
        rendered = render_fixture(Path(tmp))
    if args.check:
        if json.loads(target.read_text(encoding="utf-8")) != json.loads(rendered):
            raise SystemExit("Household demo is stale; run uv run --no-sync python -m dev.desktop_household_fixture")
    else:
        target.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
