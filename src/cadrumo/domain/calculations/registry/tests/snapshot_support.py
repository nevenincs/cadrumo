"""Registry-snapshot fixtures for tests owned by the registry domain package.

Snapshot construction is a domain concern.  Keeping this small test helper
beside the registry tests prevents the shared ``cadrumo.tests`` package from
having to import domain authority code merely to serve registry tests.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .....core.authority_grade import RegistryAuthorityGrade
from ..authority import ValidatedRegistryAuthority
from ..ids import RevisionId
from ..schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from ..snapshot import build_validated_snapshot as _build_validated_snapshot

_SNAPSHOT_CACHE: dict[tuple[object, ...], tuple[ModeloDefinition, RegistryCatalogues, RegistrySnapshot]] = {}


def build_snapshot(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    *,
    source_root: Path,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: RevisionId | None = None,
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> RegistrySnapshot:
    """Return a graded snapshot for an already validated modelo slice."""
    source_root_key = str(source_root.expanduser().resolve())
    key = (id(modelo), id(catalogues), source_root_key, filing_year, period, on, revision_id, grade)
    cached = _SNAPSHOT_CACHE.get(key)
    if cached is not None and cached[0] is modelo and cached[1] is catalogues:
        return cached[2]

    snapshot = ValidatedRegistryAuthority.from_validated_components(
        modelos=(modelo,),
        catalogues=catalogues,
        identity_digest=source_root_key,
    ).snapshot(
        modelo.id,
        filing_year=filing_year,
        period=period,
        on=on,
        revision_id=revision_id,
        grade=grade,
    )
    _SNAPSHOT_CACHE[key] = (modelo, catalogues, snapshot)
    return snapshot


def build_validated_snapshot(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: RevisionId | None = None,
) -> RegistrySnapshot:
    """Return a filing-grade snapshot for a validated modelo slice."""
    return ValidatedRegistryAuthority.from_validated_components(
        modelos=(modelo,),
        catalogues=catalogues,
        identity_digest="validated-modelo-test",
    ).snapshot(
        modelo.id,
        filing_year=filing_year,
        period=period,
        on=on,
        revision_id=revision_id,
        grade=RegistryAuthorityGrade.FILING,
    )


def build_snapshot_for_validated_modelo(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: RevisionId | None = None,
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> RegistrySnapshot:
    """Build a graded snapshot after model-local validation already ran."""
    return _build_validated_snapshot(
        modelo,
        catalogues,
        filing_year=filing_year,
        period=period,
        on=on,
        revision_id=revision_id,
        grade=grade,
    )


__all__ = ["build_snapshot", "build_snapshot_for_validated_modelo", "build_validated_snapshot"]
