"""Shared committed-registry fixtures for conformance tests.

This module is the canonical home for the read-only committed-registry
fixtures shared by the split conformance suites.  Test-specific mutations and
expectations stay in the suites that own them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistrySnapshot,
)
from cadrumo.domain.calculations.registry.schema_formula import KeyedBracketEntry
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot

from ..compiler.authority import compiled_bundled_authority

__all__ = [
    "NUMERIC_CASILLA_01",
    "as_communication_revision",
    "committed_modelo",
    "committed_registry",
    "committed_registry_tree",
    "committed_snapshot",
    "keyed_bracket",
    "revision",
    "with_revision",
]

_REGISTRY_ROOT = bundled_path("registry", "aeat")

#: The two lowest numeric casilla ids, used across this family's split modules
#: to build minimal fixtures. Declared once here rather than per module: an
#: identical private copy in each part is the duplication a split invites, and
#: the validated id is the same object in every one of them.
NUMERIC_CASILLA_01: CasillaId = validated_casilla_id("01", surface="NUMERIC_CASILLA_01")


@cache
def committed_registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Return the compiled bundled registry tree and its catalogues.

    Taken FROM the validated authority rather than compiled a second time. The
    inputs are identical, so a separate compile produced an equal graph of
    different objects, and the validator's per-modelo and catalogue memos key on
    object identity: every consumer of this doorway then re-validated what the
    authority had already validated in the same process.
    """
    authority = compiled_bundled_authority()
    return authority.modelos, authority.catalogues


@cache
def committed_modelo(modelo_id: str) -> tuple[ModeloDefinition, RegistryCatalogues]:
    """Return one bundled modelo and the catalogues that govern it."""
    modelos, catalogues = committed_registry_tree()
    return next(modelo for modelo in modelos if modelo.id == modelo_id), catalogues


@cache
def committed_snapshot(
    modelo_id: str,
    filing_year: int,
    period: str,
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
    *,
    on: date | None = None,
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
        return compiled_bundled_authority().snapshot(modelo_id, filing_year=filing_year, period=period, on=on)
    modelo, catalogues = committed_modelo(modelo_id)
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period=period,
        on=on,
        grade=grade,
    )


def committed_registry() -> tuple[ModeloDefinition, RegistryCatalogues]:
    """Return the default bundled modelo fixture and its catalogues."""
    return committed_modelo("130")


def revision(modelo: ModeloDefinition) -> ModeloRevision:
    """Return the canonical fixture revision for ``modelo``."""
    return modelo.revisions["2019-y-siguientes"]


def with_revision(modelo: ModeloDefinition, revision: ModeloRevision) -> ModeloDefinition:
    """Return ``modelo`` with ``revision`` replacing its same-id revision."""
    return modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: revision}})


def as_communication_revision(revision: ModeloRevision) -> ModeloRevision:
    """Return a revision whose filing links are projected to communication."""
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


def keyed_bracket(key: str, value: str = "0.24") -> KeyedBracketEntry:
    """Build a one-year keyed bracket fixture."""
    return KeyedBracketEntry(
        key=key,
        value=Decimal(value),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
