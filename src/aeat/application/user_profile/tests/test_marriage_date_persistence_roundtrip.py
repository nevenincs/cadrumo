"""Encrypted-SQL persistence-boundary roundtrip for the marriage_date profile fact.

``renta_taxpayer.marriage_date`` is declared as ``type = "date"`` in the
user-profile schema and is stored as an ISO-8601 string in the encrypted
store. On reload the schema-driven deserialiser converts it back to a typed
``datetime.date``.

Real adapters only: a real active-profile SQLite runtime and a real
:class:`SecureObjectRepository`.

The anti-tautology test verifies that removing the marriage_date from the
persisted payload causes the fact to be absent on reload rather than
silently reconstructed from some default path.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....domain.user_profile._schema import ProfileSchemaDefinition
from ....tests.secure_sql import isolated_profile_storage_root
from ...workflow._models import WorkflowState
from .._orchestration import (
    profile_create_storage_span,
    read_active_profile,
    register_active_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MARRIAGE_DATE_PATH = "renta_taxpayer.marriage_date"


@pytest.fixture(autouse=True)
def _storage_root(tmp_path: Path) -> Iterator[None]:
    """Real file-backed storage root for the production create-span mint path.

    Each test registers its profile inside
    :func:`profile_create_storage_span`, which mints the per-bucket
    wrapped DEK under the resolved file-backend master key before
    :func:`register_active_profile` writes the manifest — the genuine
    ``BUCKET_DEK_V1`` create path, not a legacy no-DEK shortcut.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


@pytest.fixture(scope="module")
def schema() -> ProfileSchemaDefinition:
    return resources().user_profile_schema.singleton


def _required_facts(schema: ProfileSchemaDefinition) -> list[UserProfileFact]:
    """Every required non-repeatable schema field with a placeholder value."""
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                facts.append(UserProfileFact(path=f"{section.key}.{field.key}", value="placeholder"))
    return facts


def _fact_value(record: UserProfileRecord, path: str) -> object:
    """Return the single fact value at ``path`` on ``record``."""
    matches = [fact.value for fact in record.facts if fact.path == path]
    assert len(matches) == 1, f"expected exactly one fact at {path!r}, found {len(matches)}"
    return matches[0]


def test_marriage_date_fact_survives_encrypted_sql_roundtrip(
    schema: ProfileSchemaDefinition,
) -> None:
    """marriage_date survives the real encrypted-SQL boundary as a typed date.

    Oracle: marriage_date=2024-03-22 stored as ISO-8601 string, reloaded as
    ``datetime.date(2024, 3, 22)`` — not as a bare string — because the
    schema declares ``type = "date"`` on ``renta_taxpayer.marriage_date``.
    """
    marriage_date = date(2024, 3, 22)
    facts = (
        *(
            UserProfileFact(path="iva.regime", value="GENERAL") if f.path == "iva.regime" else f
            for f in _required_facts(schema)
        ),
        UserProfileFact(
            path=_MARRIAGE_DATE_PATH,
            value=marriage_date.isoformat(),
        ),
    )

    with profile_create_storage_span("marriage-date-roundtrip") as routing_profile_id:
        state = register_active_profile(
            WorkflowState(),
            profile_id="marriage-date-roundtrip",
            display_name="Marcos 2024",
            facts=facts,
            schema=schema,
            routing_profile_id=routing_profile_id,
        )

        record = read_active_profile(state, schema=schema)
    assert record is not None
    assert record.profile_id == "marriage-date-roundtrip"

    # The schema type = "date" field deserialises as a typed date, not a string.
    assert _fact_value(record, _MARRIAGE_DATE_PATH) == marriage_date


def test_marriage_date_absent_when_not_stored(
    schema: ProfileSchemaDefinition,
) -> None:
    """Anti-tautology: a record without marriage_date has no such fact on reload.

    If the store silently invented a marriage_date default this test would
    fail, proving the roundtrip does not resurrect absent optional facts.
    """
    facts = tuple(
        UserProfileFact(path="iva.regime", value="GENERAL") if f.path == "iva.regime" else f
        for f in _required_facts(schema)
    )

    with profile_create_storage_span("no-marriage-date") as routing_profile_id:
        state = register_active_profile(
            WorkflowState(),
            profile_id="no-marriage-date",
            display_name="Soltera 2024",
            facts=facts,
            schema=schema,
            routing_profile_id=routing_profile_id,
        )

        record = read_active_profile(state, schema=schema)
    assert record is not None

    # The marriage_date fact must be absent — the store must not fabricate it.
    marriage_fact_paths = {fact.path for fact in record.facts if _MARRIAGE_DATE_PATH in fact.path}
    assert marriage_fact_paths == set()
