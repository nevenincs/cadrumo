"""Shared support for split calculation-registry tests."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.resources import bundled_path
from .. import (
    CasillaContinuidadEvolutionDefinition,
    CasillaDefinition,
    ConvenioRateRow,
    ExportFieldDefinition,
    ExtractionTargetDefinition,
    FormulaExpression,
    KeyedBracketEntry,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistryLoadError,
    RegistryValidationError,
    RegistryValidator,
    SupportRemovalDecisionDefinition,
    build_model_law_coverage_ledger,
    build_snapshot,
    load_modelo_file,
    load_registry_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

__all__ = [
    "CasillaContinuidadEvolutionDefinition",
    "CasillaDefinition",
    "ExtractionTargetDefinition",
    "FormulaExpression",
    "RegistryLoadError",
    "RegistryValidationError",
    "SupportRemovalDecisionDefinition",
    "ValidationError",
    "build_model_law_coverage_ledger",
    "load_modelo_file",
    "re",
]

_REGISTRY_ROOT = bundled_path("registry", "aeat")

_MODELO_130_DIR = _REGISTRY_ROOT / "modelos" / "130"


@cache
def _committed_modelo(modelo_id: str) -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    return next(modelo for modelo in modelos if modelo.id == modelo_id), catalogues


def _committed_registry() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("130")


def _revision(modelo: ModeloDefinition) -> ModeloRevision:
    return modelo.revisions["2019-y-siguientes"]


def _with_revision(modelo: ModeloDefinition, revision: ModeloRevision) -> ModeloDefinition:
    return modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: revision}})


def _with_first_export_field(revision: ModeloRevision, field: ExportFieldDefinition) -> ModeloRevision:
    layout = revision.export_layouts[0]
    record = layout.records[0]
    updated_record = record.model_copy(update={"fields": (field, *record.fields[1:])})
    updated_layout = layout.model_copy(update={"records": (updated_record, *layout.records[1:])})
    return revision.model_copy(update={"export_layouts": (updated_layout, *revision.export_layouts[1:])})


def _as_communication_revision(revision: ModeloRevision) -> ModeloRevision:
    filing_link = next(link for link in revision.application_links if link.surface == "filing")
    communication_link = filing_link.model_copy(
        update={
            "id": f"{filing_link.id}-communication",
            "surface": "communication",
            "consumer": "aeat.application.modelo",
        },
    )
    application_links = tuple(
        communication_link if link.id == filing_link.id else link
        for link in revision.application_links
        if link.id == filing_link.id or link.surface != "filing"
    )
    constructs = tuple(
        construct.model_copy(
            update={
                "application_links": tuple(
                    communication_link.id if link_id == filing_link.id else link_id
                    for link_id in construct.application_links
                ),
                "filing_schedules": (),
            },
        )
        for construct in revision.constructs
    )
    return revision.model_copy(
        update={
            "application_links": application_links,
            "filing_schedules": (),
            "constructs": constructs,
        },
    )


def _copy_committed_modelo(path: Path) -> None:
    revision_dir = _MODELO_130_DIR / "revisions" / "2019-y-siguientes"
    fragments = [revision_dir / "revision.toml"]
    fragments.extend(
        sorted(
            item
            for item in revision_dir.rglob("*.toml")
            if item.name != "revision.toml" and not any(part == "locales" for part in item.parts)
        ),
    )
    text = _MODELO_130_DIR.joinpath("manifest.toml").read_text(encoding="utf-8")
    text += "".join(fragment.read_text(encoding="utf-8") for fragment in fragments)
    path.write_text(text, encoding="utf-8")


@pytest.fixture(scope="module")
def _modelo_130_snapshot():  # type: ignore[no-untyped-def]
    """Validate + build the committed Modelo 130 / 2024 3T snapshot once per module.

    Module scope is safe — both validation and snapshot construction
    are read-only against the bundled registry data. Every focused
    snapshot-attribute test below asserts against the same instance.
    """
    modelo, catalogues = _committed_registry()
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    return build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2024, period="3T")


_SNAPSHOT_HEADER_EXPECTATIONS = (
    ("modelo.id", "130"),
    ("revision.id", "2019-y-siguientes"),
    ("filing_year", 2024),
    ("period", "3T"),
)

_EXPECTED_LIVE_CROSS_REFERENCES = frozenset({"modelo-130-static-official", "modelo-130-filed-declarations-read"})

_EXPECTED_DEADLINE_WINDOWS = (
    "modelo-130-2026-1t",
    "modelo-130-2026-2t",
    "modelo-130-2026-3t",
    "modelo-130-2026-4t",
)

_REQUIRED_APPLICATION_LINKS = frozenset(
    {
        "modelo-130-calculation",
        "modelo-130-deadline",
        "modelo-130-export",
        "modelo-130-extractor",
        "modelo-130-filed-declarations-observation",
        "modelo-130-filing",
        "modelo-130-portal-cross-reference",
        "modelo-130-verification",
    },
)


def _keyed_bracket(key: str, value: str = "0.24") -> KeyedBracketEntry:
    return KeyedBracketEntry(
        key=key,
        value=Decimal(value),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )


def _convenio_row(
    country_code: str,
    tipo_renta: str,
    rate: str,
    *,
    legal_ref_anchor: str = "convenio-art-7",
    notes: str | None = None,
) -> ConvenioRateRow:
    return ConvenioRateRow(
        country_code=country_code,
        tipo_renta=tipo_renta,
        rate=rate,
        legal_ref_anchor=legal_ref_anchor,
        notes=notes,
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
