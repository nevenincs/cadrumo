"""The registry snapshot construction contract.

Building an immutable snapshot for one filing context is what callers outside
this package legitimately need; its validated construction boundary lives in
:mod:`cadrumo.domain.calculations.registry.snapshot`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ..core.authority_grade import RegistryAuthorityGrade
from ..domain.calculations.registry.authority import ValidatedRegistryAuthority
from ..domain.calculations.registry.ids import RevisionId
from ..domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from ..domain.calculations.registry.snapshot import build_validated_snapshot as _build_validated_snapshot

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
    """Return a snapshot for an already validated modelo and catalogue slice.

    This helper performs model-local validation and snapshot-local reference
    checks. It cannot validate cross-model relation closure because it does not
    receive the full modelo tree; production callers should request snapshots
    through :class:`ValidatedRegistryAuthority`.

    ``grade`` defaults to :attr:`RegistryAuthorityGrade.FILING`, so this function is
    strict by default rather than by request. It is a public function of this
    defining module and returns a full :class:`RegistrySnapshot`, which made the
    previous permissive default a door: importing the obvious-looking name yielded an unattested,
    filing-shaped snapshot with none of the three gates run. A caller needing a
    lower rung now names it.

    Args:
        modelo: The :class:`ModeloDefinition` to validate and snapshot.
        catalogues: Legal and source catalogues for validation.
        source_root: Filesystem root for resolving source artefacts.
        filing_year: The filing year to select a revision for.
        period: The filing period to select a revision for.
        on: Optional reference date for revision selection.
        revision_id: Optional explicit revision identifier to select.
        grade: The rung of authority the caller needs. Defaults to
            :attr:`RegistryAuthorityGrade.FILING`, which runs the revision-review,
            filing-capability and legal-review checks; a lower rung skips the
            checks that belong to claims the caller is not making.

    Returns:
        The validated :class:`RegistrySnapshot` for the requested filing context.
    """
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
    """Return a filing-grade snapshot for an already validated modelo.

    The selected revision and the complete legal-reference slice must both be
    operator-reviewed. The model-local precondition remains separate from the
    cross-model relation closure, which callers must validate through the full
    registry tree, normally by using :class:`ValidatedRegistryAuthority`.

    Args:
        modelo: The validated :class:`ModeloDefinition` whose revision is selected.
        catalogues: Legal and source catalogues used to populate the snapshot.
        filing_year: The filing year to select a revision for.
        period: The filing period to select a revision for.
        on: Optional reference date for revision selection.
        revision_id: Optional explicit revision identifier to select.

    Returns:
        The selected :class:`RegistrySnapshot`.
    """
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
    """Build a graded snapshot when the caller already validated its modelo.

    Test fixtures that deliberately exercise a later validation layer use this
    boundary to avoid re-running model-local validation. Production callers
    should use :func:`build_snapshot` or ``ValidatedRegistryAuthority``.
    """
    return _build_validated_snapshot(
        modelo,
        catalogues,
        filing_year=filing_year,
        period=period,
        on=on,
        revision_id=revision_id,
        grade=grade,
    )
