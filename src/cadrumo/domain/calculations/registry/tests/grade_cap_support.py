"""Re-declare a binding grade cap on a copy of a compiled revision, for the tests of the cap mechanism.

The published registry caps no binding once its promotions land, so a test of
the mechanism itself (the reach, the emitted note, the screen digest) declares
the cap in memory on one real binding. Only the copy carries it; the bundled
tree and the published authority are never written.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, override

from .....core.authority_grade import BindingGradeCapReason, RegistryAuthorityGrade
from .....core.modelo import Modelo
from ..authority import PinnedAuthorityOperation
from ..binding_grade_cap import BindingGradeCap

if TYPE_CHECKING:
    from ..ids import RevisionId
    from ..schema import ModeloRevision, RegistrySnapshot

IMPUTATION_PERIOD_CAP = BindingGradeCap(
    grade=RegistryAuthorityGrade.CALCULATION,
    reason=BindingGradeCapReason.IMPUTATION_PERIOD_UNGROUNDED,
    legal_refs=("rd-439-2007:art-79", "rd-439-2007:art-7", "ley-35-2006:art-14"),
)
"""A calculation-grade cap whose reason and provisions are the ones the withholding credits carried."""


def recapped_revision(
    revision: ModeloRevision, binding_id: str, cap: BindingGradeCap = IMPUTATION_PERIOD_CAP
) -> ModeloRevision:
    """Return ``revision`` with ``cap`` declared on the binding ``binding_id``, which must exist uncapped."""
    matched = [binding for binding in revision.bindings if str(binding.id) == binding_id]
    assert len(matched) == 1, binding_id
    assert matched[0].grade_cap is None, binding_id
    return revision.model_copy(
        update={
            "bindings": tuple(
                binding.model_copy(update={"grade_cap": cap}) if str(binding.id) == binding_id else binding
                for binding in revision.bindings
            )
        }
    )


def recapped_snapshot(
    snapshot: RegistrySnapshot, binding_id: str, cap: BindingGradeCap = IMPUTATION_PERIOD_CAP
) -> RegistrySnapshot:
    """Return ``snapshot`` whose revision declares ``cap`` on the binding ``binding_id``."""
    return snapshot.model_copy(update={"revision": recapped_revision(snapshot.revision, binding_id, cap)})


def recapped_operation(
    operation: PinnedAuthorityOperation,
    modelo_id: str,
    binding_id: str,
    cap: BindingGradeCap = IMPUTATION_PERIOD_CAP,
) -> PinnedAuthorityOperation:
    """Return an operation over ``operation``'s generation whose ``modelo_id`` snapshots declare ``cap`` on ``binding_id``.

    A consumer that selects its snapshot through the operation (the gates, the
    signed report and the review workbook) then screens against the capped copy.
    Components, governed facts and the generation pin are the real ones; only
    the snapshot a caller is handed carries the cap, and the cached published
    snapshot is never touched.
    """
    normalized = Modelo(modelo_id).value

    class _RecappedOperation(PinnedAuthorityOperation):
        @override
        def snapshot(
            self,
            modelo_id: str | Modelo,
            *,
            filing_year: int,
            period: str,
            on: date | None = None,
            revision_id: RevisionId | None = None,
            grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
        ) -> RegistrySnapshot:
            published = super().snapshot(
                modelo_id, filing_year=filing_year, period=period, on=on, revision_id=revision_id, grade=grade
            )
            if Modelo(modelo_id).value != normalized:
                return published
            return recapped_snapshot(published, binding_id, cap)

    return _RecappedOperation(operation.reader, operation.generation)


__all__ = ["IMPUTATION_PERIOD_CAP", "recapped_operation", "recapped_revision", "recapped_snapshot"]
