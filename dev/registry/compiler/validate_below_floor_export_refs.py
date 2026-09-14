"""Downgrade of export binding-reference refusals for a below-floor tree.

A generated export tree whose revision lies below the registry-wide
supported-filing-years floor cannot be regenerated: revision selection admits no
coordinate for it, so the publisher refuses before it renders anything. Its
shipped records therefore keep whatever binding identifier spellings were
current when they were last emitted, and a later re-spelling of those
identifiers leaves the tree quoting names the revision no longer declares.

Refusing those references would demand a regeneration that is unreachable, and
suppressing them silently would hide a real dangling reference in a tree that is
reachable. The pipeline-owned disposition ledger is what tells the two apart: a
``below_floor`` row states the floor it was written against and the newest filing
year the revision declares. This module honours such a row in one place and
nowhere else, and only while the row still describes the live registry - the
recorded floor must still equal the declared floor and the revision must still
sit below it. Lower the floor to admit the revision and the references refuse
again.

The dependency runs compiler -> pipeline, through the ledger's public loader. The
pipeline never reads the compiler's validation, so the ledger stays a declaration
rather than a participant in the compile.

See Also:
    :mod:`dev.registry.pipeline.generated_tree_dispositions`
        Owning module of the ``below_floor`` declaration honoured here.
    :func:`dev.registry.compiler.validate_exports.validate_export_layout_section`
        Producer of the refusals this module partitions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

import rtoml

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import SupportedFilingYearsCatalogue

from ..pipeline.generated_tree_dispositions import (
    GeneratedTreeBelowSupportedFilingYearsDisposition,
    below_floor_dispositions,
    disposition_ledger_from_path,
)

__all__ = [
    "below_floor_export_reference_advisories",
    "declared_supported_filing_years_floor",
    "downgrade_below_floor_export_reference_failures",
]

_LOGGER = logging.getLogger(__name__)

#: The registry-relative path of the sole supported-filing-years declaration.
SUPPORTED_FILING_YEARS_DECLARATION: Final = Path("legal") / "supported-filing-years.toml"

_UNKNOWN_BINDING_MARKER: Final = "references unknown binding"
_EXPORT_FIELD_MARKER: Final = "export field "


def declared_supported_filing_years_floor(*, registry_root: Path | None = None) -> int:
    """Return the live floor the registry's legal tree declares.

    Read from the declaration rather than from a compiled catalogue so the
    honoured row is checked against the same authored fact an author would edit,
    and so this check stays usable on an isolated registry copy.
    """
    root = bundled_path("registry", "aeat") if registry_root is None else registry_root
    declaration = rtoml.load(root / SUPPORTED_FILING_YEARS_DECLARATION)
    catalogue = SupportedFilingYearsCatalogue.model_validate(declaration["supported_filing_years"])
    return catalogue.floor


def _live_below_floor_row(
    *,
    modelo_id: str,
    revision_id: str,
    ledger_path: Path | None,
    registry_root: Path | None,
) -> GeneratedTreeBelowSupportedFilingYearsDisposition | None:
    """Return the below-floor row for one revision while it still describes the registry.

    The ledger loader already refuses a row whose revision the recorded floor no
    longer excludes. What it cannot see is the registry: a row pinned to a floor
    the legal tree no longer declares describes a registry that no longer exists,
    and is not honoured here.
    """
    if ledger_path is None:
        rows: tuple[GeneratedTreeBelowSupportedFilingYearsDisposition, ...] = below_floor_dispositions()
    else:
        rows = tuple(
            row
            for row in disposition_ledger_from_path(ledger_path)
            if isinstance(row, GeneratedTreeBelowSupportedFilingYearsDisposition)
        )
    subject = f"{modelo_id}/{revision_id}"
    matching = next((row for row in rows if row.subject == subject), None)
    if matching is None:
        return None
    floor = declared_supported_filing_years_floor(registry_root=registry_root)
    if matching.supported_filing_years_floor != floor:
        return None
    if matching.revision_last_filing_year >= floor:
        return None
    return matching


def below_floor_export_reference_advisories(
    failures: list[str],
    *,
    modelo_id: str,
    revision_id: str,
    ledger_path: Path | None = None,
    registry_root: Path | None = None,
) -> tuple[list[str], tuple[str, ...]]:
    """Partition export binding-reference refusals honoured by a below-floor row.

    Returns the failures that still stand and one advisory per honoured row. The
    advisory carries the count, so the population stays reported rather than
    disappearing: a disposition moves these lines from the refusal list to a
    named advisory, never out of the report.
    """
    row = _live_below_floor_row(
        modelo_id=modelo_id,
        revision_id=revision_id,
        ledger_path=ledger_path,
        registry_root=registry_root,
    )
    if row is None:
        return failures, ()
    downgraded = [
        failure for failure in failures if _EXPORT_FIELD_MARKER in failure and _UNKNOWN_BINDING_MARKER in failure
    ]
    if not downgraded:
        return failures, ()
    kept = [failure for failure in failures if failure not in downgraded]
    advisory = (
        f"modelo {modelo_id} revision {revision_id}: export tree of {row.subject} is below the "
        f"supported-filing-years floor ({row.supported_filing_years_floor}) per disposition; "
        f"{len(downgraded)} references to superseded binding spellings are not a refusal"
    )
    return kept, (advisory,)


def downgrade_below_floor_export_reference_failures(
    failures: list[str],
    *,
    modelo_id: str,
    revision_id: str,
    ledger_path: Path | None = None,
    registry_root: Path | None = None,
) -> list[str]:
    """Return the standing failures, reporting each honoured row as an advisory."""
    kept, advisories = below_floor_export_reference_advisories(
        failures,
        modelo_id=modelo_id,
        revision_id=revision_id,
        ledger_path=ledger_path,
        registry_root=registry_root,
    )
    for advisory in advisories:
        _LOGGER.warning("%s", advisory)
    return kept
