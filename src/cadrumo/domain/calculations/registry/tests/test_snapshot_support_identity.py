"""Content-identity contract for registry snapshot test authorities."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from ..errors import RegistryValidationError
from ..facts.resolution import MappingFactQuery
from ..schema import ModeloDefinition
from ..schema_base import DateAxis
from ..schema_catalogues import RegistryCatalogues
from .artifact_runtime_support import minimal_catalogues, minimal_modelo, minimal_revision
from .authored_editions import filing_year_envelope
from .snapshot_support import (
    build_validated_snapshot,
    fixture_authority,
    fixture_authority_identity_digest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _subject() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return minimal_modelo(minimal_revision()), minimal_catalogues()


def test_semantically_equal_typed_inputs_have_a_stable_identity() -> None:
    modelo, catalogues = _subject()

    first = fixture_authority_identity_digest(modelo, catalogues)
    second = fixture_authority_identity_digest(modelo.model_copy(deep=True), catalogues.model_copy(deep=True))

    assert first == second
    assert len(first) == 64
    assert first == first.lower()


def test_an_excluded_semantic_field_participates_in_fixture_identity() -> None:
    modelo, catalogues = _subject()
    changed = modelo.model_copy(update={"title_localization_key": "test.schema.modelo.130.changed-title"})

    assert fixture_authority_identity_digest(changed, catalogues) != fixture_authority_identity_digest(
        modelo, catalogues
    )


def test_fixture_identity_is_accepted_by_governed_fact_resolution() -> None:
    modelo, catalogues = _subject()
    authority = fixture_authority(modelo, catalogues)

    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="spanish-tax-identifier-format",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(filing_year_envelope().horizon, 1, 1),
        )
    )

    assert resolved.authority_digest == fixture_authority_identity_digest(modelo, catalogues)


def test_fixture_authority_does_not_upgrade_an_unsupported_filing_grade() -> None:
    revision = minimal_revision().model_copy(update={"authority_grade": RegistryAuthorityGrade.CALCULATION})
    modelo = minimal_modelo(revision)
    catalogues = minimal_catalogues()

    with pytest.raises(RegistryValidationError, match=r"declares 'calculation' authority grade.*requested 'filing'"):
        build_validated_snapshot(modelo, catalogues, filing_year=filing_year_envelope().horizon, period="0A")
