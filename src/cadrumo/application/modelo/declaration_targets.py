"""New-declaration choices from the pinned registry's supported legal windows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...core.period import Period
from ...domain.calculations.registry.temporal import select_authored_revision_metadata

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


@dataclass(frozen=True, slots=True)
class DeclarationTarget:
    """An admitted natural filing coordinate; the picker never accepts arbitrary years."""

    modelo: str
    period: Period


def declaration_targets(operation: PinnedAuthorityOperation) -> tuple[DeclarationTarget, ...]:
    """Enumerate authored windows, retaining only their law-selected revision owners."""
    support = operation.supported_filing_years()
    targets: set[tuple[str, Period]] = set()
    for modelo in operation.modelo_ids():
        directory = operation.modelo_directory(modelo)
        for revision in directory.revisions:
            for window in revision.deadline_windows:
                if not support.admits_coordinate(window.period.filing_year):
                    continue
                selected = select_authored_revision_metadata(
                    directory,
                    filing_year=window.period.filing_year,
                    period=window.period.registry_token,
                )
                if selected.id == revision.id:
                    targets.add((modelo, window.period))
    return tuple(
        DeclarationTarget(modelo, period)
        for modelo, period in sorted(
            targets,
            key=lambda item: (item[0], item[1].filing_year, item[1].registry_token),
        )
    )
