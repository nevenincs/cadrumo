"""New-declaration choices from the pinned registry's supported legal windows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...core.period import Period
from ...domain.calculations.registry.errors import NoRevisionForPeriodError
from ...domain.calculations.registry.temporal import select_revision_metadata

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


@dataclass(frozen=True, slots=True)
class DeclarationTarget:
    """An admitted natural filing coordinate; the picker never accepts arbitrary years."""

    modelo: str
    period: Period


def declaration_targets(operation: PinnedAuthorityOperation) -> tuple[DeclarationTarget, ...]:
    """Every modelo period the registry envelope admits, as the one envelope resolver selects its revision.

    A modelo's periods are those its editions declare filing windows for. Each is offered in every
    envelope year the resolver answers, a year without its own edition projected from the nearest
    authored one; a year before the modelo's declared inception is refused there and not offered.
    """
    support = operation.supported_filing_years()
    targets: list[DeclarationTarget] = []
    for modelo in sorted(operation.modelo_ids()):
        directory = operation.modelo_directory(modelo)
        codes = sorted(
            {str(window.period.code) for revision in directory.revisions for window in revision.deadline_windows}
        )
        for year in support.years:
            for code in codes:
                period = Period.from_year_and_code(year, code)
                try:
                    select_revision_metadata(directory, filing_year=year, period=period.registry_token, support=support)
                except NoRevisionForPeriodError:
                    continue
                targets.append(DeclarationTarget(modelo, period))
    return tuple(targets)
