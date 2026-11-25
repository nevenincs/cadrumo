"""Serve one declaration's form again, without reading and projecting it afresh, while nothing it is made of changed.

A form read is a function of the profile's stored rows, the pinned authority
generation, the public operation contracts, the language, the Madrid date its
deadlines are counted from, and the edit admission it is read with. The key
below names each: ``store_epoch`` digests every row of the profile store all
the read ports read, so any write to the profile moves it. The edit admission
is admitted afresh on every read, as a read without the memo admits it; the
key holds it without its own identity and lifetime (``baseline_id``,
``issued_at``, ``expires_at``), which differ on every admission, and the
served form carries the fresh admission's baseline. A served form is
therefore the one a fresh read would return, but for the new baseline's
identity and lifetime, which a fresh read also issues anew.

An export writes one bucket event, which moves ``store_epoch``, so the read
that returns to the form after it would build the whole form again. When an
export settles having written, the session therefore reads its last served
form again in the background, through the same reader and under the same
key, and the returning read finds it kept or joins the read under way.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date
from typing import Final
from uuid import UUID

from ...core.external_constants import OutputLanguage
from ...core.operations import OperationEffect, OperationLifecycle
from ..operations.persistence.journal import OperationPersistedSnapshot
from .edit_baseline_projection import ModeloEditApplyBaselineV1
from .edit_models import ModeloEditAdmissionResultV1, ModeloEditAdmittedV1
from .operation_shared import MODELO_EXPORT_OPERATION_DEFINITION_ID
from .workbench_projection import ModeloWorkbenchFormProjectionV1

__all__ = [
    "WorkbenchFormReadKey",
    "admission_identity",
    "changed_key_parts",
    "export_settled_with_effect",
    "with_fresh_admission",
]

_BASELINE_LIFETIME: Final[frozenset[str]] = frozenset({"baseline_id", "issued_at", "expires_at"})
"""What every admission issues anew, even for an unchanged declaration."""


@dataclass(frozen=True, slots=True)
class WorkbenchFormReadKey:
    """Everything one served form is computed from."""

    profile_id: UUID
    work_unit_id: str
    store_epoch: str
    logical_generation: str
    contract_set_digest: str
    language: OutputLanguage
    as_of: date
    admission: str


def changed_key_parts(kept: WorkbenchFormReadKey, key: WorkbenchFormReadKey) -> tuple[str, ...]:
    """The names of the key parts in which ``key`` differs from the ``kept`` one, in declaration order."""
    return tuple(
        part.name for part in fields(WorkbenchFormReadKey) if getattr(kept, part.name) != getattr(key, part.name)
    )


def admission_identity(admission: ModeloEditAdmissionResultV1) -> str:
    """The admission as the form is read with it: all of it but the baseline's own identity and lifetime."""
    if isinstance(admission, ModeloEditAdmittedV1):
        return "admitted:" + admission.baseline.model_dump_json(exclude=set(_BASELINE_LIFETIME))
    return "refused:" + admission.model_dump_json()


def with_fresh_admission(
    served: ModeloWorkbenchFormProjectionV1, admission: ModeloEditAdmissionResultV1
) -> ModeloWorkbenchFormProjectionV1:
    """The served form carrying the baseline this read admitted rather than the one it was first read with."""
    if not isinstance(admission, ModeloEditAdmittedV1):
        return served
    return served.model_copy(update={"admitted_baseline": ModeloEditApplyBaselineV1.from_baseline(admission.baseline)})


def export_settled_with_effect(snapshot: OperationPersistedSnapshot) -> bool:
    """Whether ``snapshot`` records a Modelo export that settled having written, or may have written, its event."""
    return (
        snapshot.lifecycle is OperationLifecycle.TERMINAL
        and snapshot.identity.definition_id == MODELO_EXPORT_OPERATION_DEFINITION_ID
        and snapshot.effect is not OperationEffect.NONE
    )
