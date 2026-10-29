"""Canonical revision ownership and ordering of eager registry deadline windows.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from .errors import RegistrySnapshotError, RegistryValidationError

if TYPE_CHECKING:
    from .schema import ModeloDefinition, ModeloRevision
    from .schema_catalogues import RegistryCatalogues
    from .schema_deadlines import DeadlineWindowDefinition

type DeadlineWindow = tuple[str, ModeloRevision, DeadlineWindowDefinition]


def validated_deadline_windows(
    modelos: tuple[ModeloDefinition, ...],
    year: int,
    *,
    catalogues: RegistryCatalogues,
    validate_modelo: Callable[[str], ModeloDefinition],
) -> tuple[DeadlineWindow, ...]:
    """Select each row's governing revision before exposing its retained provenance.

    Takes the :class:`ModeloDefinition` rows in ``modelos`` and ``validate_modelo``, which resolves one by id.
    """
    from .temporal import select_revision

    out: list[DeadlineWindow] = []
    for modelo in modelos:
        candidates = tuple(
            (revision, window)
            for revision in modelo.revisions.values()
            for window in revision.deadline_windows
            if window.filing_year == year
        )
        if not candidates:
            continue
        try:
            validate_modelo(modelo.id)
        except RegistryValidationError:
            raise
        for containing_revision, window in candidates:
            selected_revision = select_revision(
                modelo,
                filing_year=window.period.filing_year,
                period=window.period.registry_token,
                support=catalogues.supported_filing_years,
            )
            if selected_revision.id != containing_revision.id:
                continue
            # Cold validation proves this ownership invariant.  Keep the
            # guard at the projection boundary as a defence against a
            # future traversal refactor accidentally returning provenance
            # from a revision other than the canonical selector's result.
            if containing_revision is not modelo.revisions[selected_revision.id]:
                raise RegistrySnapshotError(
                    f"modelo {modelo.id} deadline provenance names revision "
                    f"{containing_revision.id!r} while the canonical selector resolved "
                    f"{selected_revision.id!r}",
                )
            out.append((modelo.id, selected_revision, window))
    out.sort(
        key=lambda item: (
            item[2].closes_on,
            item[0],
            *_deadline_window_period_sort_key(item[2]),
            *_deadline_window_qualifier_sort_key(item[2]),
        ),
    )
    return tuple(out)


def _deadline_window_period_sort_key(window: DeadlineWindowDefinition) -> tuple[int, str]:
    return window.filing_year, window.period.registry_token


def _deadline_window_qualifier_sort_key(window: DeadlineWindowDefinition) -> tuple[str, tuple[str, ...]]:
    """Order qualified plazo variants without defining another vocabulary."""
    resultado = "" if window.resultado_scope is None else window.resultado_scope.value
    tipo_renta = () if window.tipo_renta_scope is None else tuple(sorted(window.tipo_renta_scope))
    return resultado, tipo_renta
