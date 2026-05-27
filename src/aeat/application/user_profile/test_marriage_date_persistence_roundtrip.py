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

from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.config import override_settings
from ...core.resources import resources
from ...domain.user_profile import UserProfileFact, UserProfileRecord
from ...domain.user_profile._schema import ProfileSchemaDefinition
from ...tests.secure_sql import isolated_runtime_profile
from ..workflow._models import WorkflowState
from ._orchestration import read_active_profile, register_active_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]

_MARRIAGE_DATE_PATH = "renta_taxpayer.marriage_date"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """A real SecureObjectRepository over a real active-profile runtime."""
    with (
        isolated_runtime_profile(
            tmp_path=tmp_path,
            bucket_id="marriage-date-roundtrip-test",
        ) as profile,
        override_settings(aeat_active_profile=None),
    ):
        yield profile.repository


@pytest.fixture(scope="module")
def schema():
    return resources().user_profile_schema.singleton


def _required_facts(schema: ProfileSchemaDefinition) -> list[UserProfileFact]:
    """Every required non-repeatable schema field with a placeholder value."""
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                facts.append(
                    UserProfileFact(path=f"{section.key}.{field.key}", value="placeholder")
                )
    return facts


def _fact_value(record: UserProfileRecord, path: str) -> object:
    """Return the single fact value at ``path`` on ``record``."""
    matches = [fact.value for fact in record.facts if fact.path == path]
    assert len(matches) == 1, f"expected exactly one fact at {path!r}, found {len(matches)}"
    return matches[0]


def test_marriage_date_fact_survives_encrypted_sql_roundtrip(
    secure_objects: SecureObjectRepository,
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

    state = register_active_profile(
        WorkflowState(),
        profile_id="marriage-date-roundtrip",
        display_name="Marcos 2024",
        facts=facts,
        secure_objects=secure_objects,
        schema=schema,
    )

    record = read_active_profile(state, secure_objects=secure_objects, schema=schema)
    assert record is not None
    assert record.profile_id == "marriage-date-roundtrip"

    # The schema type = "date" field deserialises as a typed date, not a string.
    assert _fact_value(record, _MARRIAGE_DATE_PATH) == marriage_date


def test_marriage_date_absent_when_not_stored(
    secure_objects: SecureObjectRepository,
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

    state = register_active_profile(
        WorkflowState(),
        profile_id="no-marriage-date",
        display_name="Soltera 2024",
        facts=facts,
        secure_objects=secure_objects,
        schema=schema,
    )

    record = read_active_profile(state, secure_objects=secure_objects, schema=schema)
    assert record is not None

    # The marriage_date fact must be absent — the store must not fabricate it.
    marriage_fact_paths = {fact.path for fact in record.facts if _MARRIAGE_DATE_PATH in fact.path}
    assert marriage_fact_paths == set()
