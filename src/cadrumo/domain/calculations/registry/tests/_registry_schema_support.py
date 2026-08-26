"""Shared support for split calculation-registry tests."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistrySnapshot,
)
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition
from cadrumo.domain.calculations.registry.schema_extraction import ExtractionTargetDefinition
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression, KeyedBracketEntry
from cadrumo.domain.calculations.registry.schema_surfaces import (
    CasillaContinuidadEvolutionDefinition,
    CasillaDefinition,
)

from .....core import CasillaId, RegistryAuthorityGrade, validated_casilla_id
from .....core.directory_scan import scan_directory
from .....core.resources import bundled_path
from .._loader_internals import load_modelo_file
from .._validate import RegistryValidator
from ..authority import bundled_authority
from ..coverage import build_model_law_coverage_ledger
from ..errors import RegistryLoadError, RegistryValidationError
from ..loader import load_registry_tree
from ..snapshot import build_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

__all__ = [
    "CasillaContinuidadEvolutionDefinition",
    "CasillaDefinition",
    "ExtractionTargetDefinition",
    "FormulaExpression",
    "RegistryLoadError",
    "RegistryValidationError",
    "ValidationError",
    "build_model_law_coverage_ledger",
    "load_modelo_file",
    "re",
]

_REGISTRY_ROOT = bundled_path("registry", "aeat")

_MODELO_130_DIR = _REGISTRY_ROOT / "modelos" / "130"

#: The two lowest numeric casilla ids, used across this family's split modules
#: to build minimal fixtures. Declared once here rather than per module: an
#: identical private copy in each part is the duplication a split invites, and
#: the validated id is the same object in every one of them.
_NUMERIC_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_NUMERIC_CASILLA_01")


@cache
def _committed_registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    return tuple(modelos), catalogues


@cache
def _committed_modelo(modelo_id: str) -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = _committed_registry_tree()
    return next(modelo for modelo in modelos if modelo.id == modelo_id), catalogues


@cache
def _committed_snapshot(
    modelo_id: str,
    filing_year: int,
    period: str,
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> RegistrySnapshot:
    """Build the committed snapshot for one modelo, at the requested authority grade.

    ``grade`` defaults to :attr:`RegistryAuthorityGrade.FILING`, preserving the
    original strict contract for callers that need it. A caller asking a
    narrower question (formula-runtime calculation, applicability/scheduling)
    should pass a lower grade explicitly.
    """
    if modelo_id == "303":
        # M303 snapshots include the compiled annual-Orden authority.  The
        # production access point is the only source of that cross-cutting
        # projection, so bypassing it here would produce a partial fixture.
        # M303 stays FILING-grade regardless. It does declare export layouts
        # -- one per revision, all six -- so the rung costs it nothing; the
        # reason it cannot take a lower one is that this branch goes through
        # the authority accessor for the annual-Orden projection.
        return bundled_authority().snapshot(modelo_id, filing_year=filing_year, period=period)
    modelo, catalogues = _committed_modelo(modelo_id)
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period=period,
        grade=grade,
    )


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
            "consumer": "cadrumo.application.modelo",
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
        item
        for item in scan_directory(revision_dir, pattern="*.toml", recursive=True, prune_directories=("locales",))
        if item.name != "revision.toml"
    )
    text = _MODELO_130_DIR.joinpath("manifest.toml").read_text(encoding="utf-8")
    text += "".join(fragment.read_text(encoding="utf-8") for fragment in fragments)
    path.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture(scope="module")
def _modelo_130_snapshot():  # type: ignore[no-untyped-def]  # reason: a pytest module fixture whose return type is the private snapshot the helpers below consume; annotating it would export that internal type from a test-support module
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
    "modelo-130-2024-1t",
    "modelo-130-2024-2t",
    "modelo-130-2024-3t",
    "modelo-130-2024-4t",
    "modelo-130-2025-1t",
    "modelo-130-2025-2t",
    "modelo-130-2025-3t",
    "modelo-130-2025-4t",
    "modelo-130-2026-1t",
    "modelo-130-2026-2t",
    "modelo-130-2026-3t",
    "modelo-130-2026-4t",
)

#: The application links Modelo 130's snapshot must carry, as a floor rather than
#: an inventory -- the revision declares more than these, and adding one must not
#: red the gate.
#:
#: ``modelo-130-verification`` was named here and is NOT declared, because it
#: cannot be: ``verification`` is not a member of ``ApplicationLink.surface``'s
#: closed vocabulary, and no revision anywhere in the registry declares such a
#: surface. Modelo 130's verification concern is carried by the two links that do
#: exist for it -- ``review`` (``cadrumo.application.filing.review``) and
#: ``approval`` (``cadrumo.application.workflow.approval``) -- so the floor names
#: those instead of an id nothing could satisfy.
_REQUIRED_APPLICATION_LINKS = frozenset(
    {
        "modelo-130-approval",
        "modelo-130-calculation",
        "modelo-130-deadline",
        "modelo-130-export",
        "modelo-130-extractor",
        "modelo-130-filed-declarations-observation",
        "modelo-130-filing",
        "modelo-130-portal-cross-reference",
        "modelo-130-review",
    },
)


def _keyed_bracket(key: str, value: str = "0.24") -> KeyedBracketEntry:
    return KeyedBracketEntry(
        key=key,
        value=Decimal(value),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
