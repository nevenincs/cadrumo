"""The Modelo edit mutation-capability facade for the Edit Contract V1.

Behind :mod:`cadrumo.application.modelo`. This is the one place the edit
contract composes a closed capability row for a target rather than inferring
one: domain eligibility (whether the target resolves at all) is the only join
this module owns; the registered operation identity and the green C3
financial-operand dependency receipt remain each their own canonical owner's
concern, per D5's "the facade composes rather than infers."

Every row is ``UNMEASURED`` in this V1: no financial-operand dependency
receipt is green yet (D1, D5), so this facade never advertises a usable C3
path on its own say-so. Once that receipt exists, the disposition and the
mandatory ``operation_definition_id`` join for an ``AVAILABLE`` row belong
here, not fabricated ahead of it.
"""

from __future__ import annotations

from ...domain.modelos.work_unit import WorkUnitCatalogue
from .edit_models import (
    ModeloMutationCapabilityProjectionV1,
    ModeloMutationCapabilityRequestV1,
    ModeloMutationCapabilityRowV1,
)
from .work_addressing import (
    ModeloWorkAddressNotFoundError,
    ModeloWorkUnitNotFoundError,
    law_selected_revision_for_work_target,
    resolve_modelo_work_address_unit,
    work_address_for_modelo_target,
)
from .workspace_models import ModeloWorkspaceCapabilityDisposition

_RESPONSIBLE_OWNER = "modelo.edit"


def project_modelo_edit_mutation_capability(
    request: ModeloMutationCapabilityRequestV1,
    *,
    bucket_id: str,
    work_catalogue: WorkUnitCatalogue,
) -> ModeloMutationCapabilityProjectionV1:
    """Project the closed CALCULATE mutation-capability row for one edit target.

    Independently re-resolves the target exactly as
    :func:`~._edit_services.admit_modelo_edit` does; an unresolved target
    projects an empty capability set rather than a fabricated row. A
    resolved target always projects ``UNMEASURED`` in this V1 -- see the
    module docstring.
    """
    domain_target = request.target.target
    try:
        work_unit = resolve_modelo_work_address_unit(
            work_address_for_modelo_target(domain_target),
            catalogue=work_catalogue,
            bucket_id=bucket_id,
        )
    except (ModeloWorkAddressNotFoundError, ModeloWorkUnitNotFoundError):
        return ModeloMutationCapabilityProjectionV1(rows=())

    law_selected_revision_id = law_selected_revision_for_work_target(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        stored_revision_id=work_unit.revision_id,
    )
    row = ModeloMutationCapabilityRowV1(
        mutation_id="calculate",
        owning_producer=_RESPONSIBLE_OWNER,
        revision_id=law_selected_revision_id,
        disposition=ModeloWorkspaceCapabilityDisposition.UNMEASURED,
        reconsideration_condition="becomes AVAILABLE once the green C3 financial-operand dependency receipt exists",
    )
    return ModeloMutationCapabilityProjectionV1(rows=(row,))


__all__ = ["project_modelo_edit_mutation_capability"]
