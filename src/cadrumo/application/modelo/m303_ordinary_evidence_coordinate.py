"""Filing coordinates where ordinary Modelo 303 filing evidence can be authored.

The ordinary evidence envelope carries three operator-declared header facts:
the joint self-assessment election, the non-zero annual volume answer and the
Modelo 390 exemption applicability. A coordinate admits that envelope only when
the law-selected Modelo 303 revision for the quarter prints those facts in its
official record design, so support follows the registry instead of a list of
years.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.filing_producer_key import FilingProducerKey
from ...core.period import Period

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

ORDINARY_M303_EVIDENCE_PRODUCER_KEYS: frozenset[FilingProducerKey] = frozenset(
    {
        FilingProducerKey.M303_JOINT_RETURN_ELECTED,
        FilingProducerKey.M303_ANNUAL_VOLUME_NONZERO,
        FilingProducerKey.M303_EXONERADO_390_APPLICABLE,
    }
)


def ordinary_m303_evidence_coordinate_supported(
    *,
    filing_year: int,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Return whether this quarterly coordinate's selected record design declares every ordinary evidence field.

    A coordinate outside the registry's supported envelope raises the
    authority's own refusal from ``snapshot`` rather than reporting ``False``.
    """
    if period.filing_year != filing_year or not period.is_quarterly:
        return False
    snapshot = operation.snapshot("303", filing_year=filing_year, period=period.registry_token)
    declared = {
        field.producer_key
        for layout in snapshot.revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.producer_key is not None
    }
    return declared >= ORDINARY_M303_EVIDENCE_PRODUCER_KEYS


__all__ = ["ORDINARY_M303_EVIDENCE_PRODUCER_KEYS", "ordinary_m303_evidence_coordinate_supported"]
