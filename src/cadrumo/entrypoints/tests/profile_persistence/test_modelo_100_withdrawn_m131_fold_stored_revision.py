"""A stored Modelo 100 revision that still carries the withdrawn Modelo 131 módulos fold.

Until the 2024 edition withdrew it, Modelo 100 folded the four quarterly copies of
Modelo 131 casilla 01 into casilla 1481 through the binding
``renta-modelo-131-rendimiento-neto-modulos``. A revision calculated then kept the
folded figure under that binding id, and an operator ``--relation`` under its
pre-absorption relation id. Such a revision stays in encrypted storage after the
edition drops the binding, and each read path meets it under a named rule:

* reload keeps the stored figures as the historical record, and the relation-override
  migration rekeys the retired relation id onto its binding through the frozen join;
* recalculation builds a new revision from the current edition, which neither
  replays the stored figure nor folds the quarterly estimate again;
* the filing draft that verification, filing and export rebuild from the stored
  revision refuses the withdrawn binding as an input key the edition no longer
  declares, so the figure cannot reach a filed or exported return.

Every value is synthetic.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from decimal import Decimal

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....application.filing.draft_construction import build_draft
from ....application.filing.runtime import build_runtime_schema_provider, filing_profile_from_taxpayer
from ....application.modelo.calculation_action_ports import CalculationActionPorts
from ....application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    list_calculation_revisions,
)
from ....application.modelo.revision_replay_inputs import revision_filing_replay_inputs
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.contribuyente.entity_type import EntityType
from ....domain.deadlines.models import IrpfEstimationRegime, IrpfIncomeCategory, IVARegime, TaxpayerProfile
from ....domain.filing.errors import ModeloBuilderError
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    derive_calculation_revision_id_from_revision,
)
from .file_flow_test_support import calculation_ports_for_test
from .test_modelo_100_m131_pagos_fold_in_live import (
    _BUCKET_ID,
    _calculate_m100_annual,
    _non_relation_zero_bindings,
    _seed_m131_quarters,
    bucket_id,
    secure_objects,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

__all__ = ["bucket_id", "secure_objects"]

_WITHDRAWN_FOLD = "renta-modelo-131-rendimiento-neto-modulos"
_RETIRED_RELATION_ID = "renta-2024-rel-131-rendimiento-neto-modulos"
#: What the withdrawn fold persisted: four quarterly copies of one 5.400 annual estimate.
_FOLDED_ESTIMATE = "21600.00"
_M100_EO_RENDIMIENTO: CasillaId = validated_casilla_id("1481", surface="_M100_EO_RENDIMIENTO")


def _stored_before_withdrawal(
    revision: CalculationRevision,
    *,
    binding_overrides: dict[str, str] | None = None,
    relation_overrides: dict[str, str] | None = None,
) -> CalculationRevision:
    """The same revision as it would have been persisted while the fold existed."""
    candidate = revision.model_copy(
        update={
            "binding_overrides": {**revision.binding_overrides, **(binding_overrides or {})},
            "relation_overrides": {**revision.relation_overrides, **(relation_overrides or {})},
        },
    )
    return candidate.model_copy(
        update={"calculation_revision_id": derive_calculation_revision_id_from_revision(candidate)}
    )


def _persist_pre_withdrawal_revisions(
    objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> tuple[str, CalculationRevision, CalculationRevision]:
    """Calculate on the current edition, then store the two shapes a pre-withdrawal revision had.

    The quarterly Modelo 131 filings the withdrawn fold summed stay on file throughout.
    """
    _seed_m131_quarters(objects)
    current = _calculate_m100_annual(objects, estimation_regime="objetiva", operation=operation).revision
    assert isinstance(current, CalculationRevision)
    folded = _stored_before_withdrawal(current, binding_overrides={_WITHDRAWN_FOLD: _FOLDED_ESTIMATE})
    overridden = _stored_before_withdrawal(current, relation_overrides={_RETIRED_RELATION_ID: _FOLDED_ESTIMATE})
    repository = CalculationRevisionCatalogueRepository(objects=objects)
    stored = repository.load()
    repository.save(
        CalculationRevisionCatalogue(
            revisions={
                **stored.revisions,
                folded.calculation_revision_id: folded,
                overridden.calculation_revision_id: overridden,
            },
        ),
    )
    return current.work_unit_id, folded, overridden


def _calculation_ports(objects: SecureObjectRepository) -> AbstractContextManager[CalculationActionPorts]:
    return calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=WorkUnitCatalogueRepository(objects=objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=objects),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
    )


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        entity_type=EntityType.from_registry("natural_person"),
        irpf_income_categories=frozenset({IrpfIncomeCategory.from_registry("actividad_economica")}),
        irpf_estimation_regime=IrpfEstimationRegime.from_registry("objetiva"),
        iva_regime=IVARegime("SIMPLIFICADO"),
        has_employees=False,
        pays_professionals_with_retencion=False,
        pays_rent_with_retencion=False,
        pays_capital_income_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        monedas_virtuales_extranjero_above_threshold=False,
    )


def test_reload_keeps_the_stored_figures_and_rekeys_the_retired_relation(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    work_unit_id, folded, _overridden = _persist_pre_withdrawal_revisions(secure_objects, operation=operation)

    with _calculation_ports(secure_objects) as ports:
        reloaded = list_calculation_revisions(ports=ports, work_unit_id=work_unit_id)

    by_id = {revision.calculation_revision_id: revision for revision in reloaded}
    assert by_id[folded.calculation_revision_id].binding_overrides[_WITHDRAWN_FOLD] == _FOLDED_ESTIMATE
    rekeyed = [revision for revision in reloaded if _WITHDRAWN_FOLD in revision.relation_overrides]
    assert [revision.relation_overrides[_WITHDRAWN_FOLD] for revision in rekeyed] == [_FOLDED_ESTIMATE]
    assert all(_RETIRED_RELATION_ID not in revision.relation_overrides for revision in reloaded)


def test_recalculation_neither_replays_nor_refolds_the_withdrawn_figure(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    work_unit_id, _folded, _overridden = _persist_pre_withdrawal_revisions(secure_objects, operation=operation)

    with _calculation_ports(secure_objects) as ports:
        recalculated = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit_id,
            binding_values=_non_relation_zero_bindings(),
            ports=ports,
        ).revision

    assert _WITHDRAWN_FOLD not in recalculated.binding_overrides
    assert _WITHDRAWN_FOLD not in recalculated.relation_overrides
    assert recalculated.casilla_values[_M100_EO_RENDIMIENTO] == Decimal("0")


@pytest.mark.parametrize("shape", ["folded", "overridden"])
def test_filing_draft_refuses_the_withdrawn_binding(
    secure_objects: SecureObjectRepository, shape: str, *, operation: PinnedAuthorityOperation
) -> None:
    work_unit_id, folded, _overridden = _persist_pre_withdrawal_revisions(secure_objects, operation=operation)
    with _calculation_ports(secure_objects) as ports:
        # The production read path, which also runs the relation-override migration.
        reloaded = {revision.calculation_revision_id: revision for revision in list_calculation_revisions(ports=ports)}
    revision = (
        reloaded[folded.calculation_revision_id]
        if shape == "folded"
        else next(item for item in reloaded.values() if _WITHDRAWN_FOLD in item.relation_overrides)
    )
    work_unit = WorkUnitCatalogueRepository(objects=secure_objects).load().get(work_unit_id)
    assert work_unit is not None
    profile = _workflow_profile()
    inputs = revision_filing_replay_inputs(
        revision=revision,
        work_unit=work_unit,
        workflow_profile=profile,
        operation=operation,
    )

    with pytest.raises(ModeloBuilderError) as refused:
        build_draft(
            modelo=str(work_unit.modelo),
            period=work_unit.period,
            profile=filing_profile_from_taxpayer(profile),
            inputs=inputs,
            schema_provider=build_runtime_schema_provider(
                filing_year=work_unit.filing_year,
                period=work_unit.period,
                modelos=(work_unit.modelo,),
                operation=operation,
            ),
        )

    assert str(refused.value) == "application.filing.build_draft.errors.input_key_unknown"
    assert refused.value.context is not None
    input_keys = refused.value.context["input_keys"]
    assert isinstance(input_keys, tuple)
    assert _WITHDRAWN_FOLD in input_keys
