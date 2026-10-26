"""Content-identity contract for registry snapshot test authorities."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from ..errors import RegistryValidationError
from ..facts.resolution import MappingFactQuery
from ..schema import ModeloDefinition, RegistryCatalogues
from ..schema_base import DateAxis
from .artifact_runtime_support import minimal_catalogues, minimal_modelo, minimal_revision
from .snapshot_support import (
    _fixture_authority,
    _fixture_authority_identity_digest,
    build_validated_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _subject() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return minimal_modelo(minimal_revision()), minimal_catalogues()


def test_semantically_equal_typed_inputs_have_a_stable_identity() -> None:
    modelo, catalogues = _subject()

    first = _fixture_authority_identity_digest(modelo, catalogues)
    second = _fixture_authority_identity_digest(modelo.model_copy(deep=True), catalogues.model_copy(deep=True))

    assert first == second
    assert len(first) == 64
    assert first == first.lower()


def test_an_excluded_semantic_field_participates_in_fixture_identity() -> None:
    modelo, catalogues = _subject()
    changed = modelo.model_copy(update={"title_localization_key": "test.schema.modelo.130.changed-title"})

    assert _fixture_authority_identity_digest(changed, catalogues) != _fixture_authority_identity_digest(
        modelo, catalogues
    )


def test_fixture_identity_is_accepted_by_governed_fact_resolution() -> None:
    modelo, catalogues = _subject()
    authority = _fixture_authority(modelo, catalogues)

    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="spanish-tax-identifier-format",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(2024, 1, 1),
        )
    )

    assert resolved.authority_digest == _fixture_authority_identity_digest(modelo, catalogues)


def test_fixture_authority_does_not_upgrade_an_unsupported_filing_grade() -> None:
    revision = minimal_revision().model_copy(update={"authority_grade": RegistryAuthorityGrade.CALCULATION})
    modelo = minimal_modelo(revision)
    catalogues = minimal_catalogues()

    with pytest.raises(RegistryValidationError, match=r"declares 'calculation' authority grade.*requested 'filing'"):
        build_validated_snapshot(modelo, catalogues, filing_year=2024, period="0A")
