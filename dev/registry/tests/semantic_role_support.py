"""Shared builders for the semantic role tests."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaAlias, CasillaConstraints, CasillaDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..maintenance_support import load_modelo_path
from .authored_edition_support import authored_revisions
from .profile_schema_support import committed_supported_filing_years
from .synthetic_locale_fixtures import (
    write_test_label,
)

SUPPORT = committed_supported_filing_years()


# The first authored Modelo 100 edition that carries the descendant/ascendant family
# fields its XML dictionary publishes.
FAMILY_FIELD_FIRST_EDITION = next(
    revision.valid_from.year
    for revision in authored_revisions("100")
    if any(c.id == "ANOASDLG" for c in revision.casillas)
)


_TEST_CASILLA_ID: CasillaId = validated_casilla_id("test_casilla", surface="_TEST_CASILLA_ID")


def semantic_role_casilla(
    *,
    cid: CasillaId = _TEST_CASILLA_ID,
    label: str = "Test casilla",
    data_type: str = "money",
    semantic_role: str | None = None,
    semantic_role_cardinality: str = "shared",
    semantic_role_cardinality_reason: str | None = None,
    aliases: Iterable[CasillaAlias] = (),
    constraints: CasillaConstraints | None = None,
) -> CasillaDefinition:
    return CasillaDefinition.model_validate(
        {
            "id": cid,
            "number": "01",
            "localization_keys": (write_test_label(label),),
            "section": ("test",),
            "data_type": data_type,
            "semantic_role": semantic_role,
            "semantic_role_cardinality": semantic_role_cardinality,
            "semantic_role_cardinality_reason": semantic_role_cardinality_reason,
            "aliases": tuple(aliases),
            "constraints": constraints,
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
        },
    )


def registry_modelo(modelo_id: str, revision_id: str, casillas: Iterable[CasillaDefinition]) -> ModeloDefinition:
    revision = ModeloRevision.model_validate(
        {
            "id": revision_id,
            "localization_key": f"test.schema.revision.{revision_id}.label",
            "valid_from": date(filing_year_envelope().horizon, 1, 1),
            "period_selector": PeriodSelector(years=(filing_year_envelope().horizon,), periods=("0A",)),
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "casillas": tuple(casillas),
        },
    )
    return ModeloDefinition.model_validate(
        {
            "id": modelo_id,
            "title_localization_key": f"test.schema.modelo.{modelo_id}.title",
            "official_name_localization_key": f"test.schema.modelo.{modelo_id}.official_name",
            "tax_domain": "iva",
            "cadence": "annual",
            "jurisdiction": "ES-AEAT",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "revisions": {revision_id: revision},
        },
    )


def bundled_modelo(modelo_id: str) -> Any:
    path = bundled_path("registry", "aeat", "modelos", modelo_id)
    if path.exists():
        return load_modelo_path(path)
    return load_modelo_path(path.with_suffix(".toml"))
