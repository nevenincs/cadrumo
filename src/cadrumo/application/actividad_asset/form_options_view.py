"""Project register form options into the shared frontend view."""

from collections.abc import Callable

from ...core.tipos_actividad import TipoActividad
from ...domain.calculations.registry.actividad_asset_form_options import ActivityAssetFormOptions
from ...domain.renta.actividad_asset.disposal import ADMITTED_DISPOSAL_REASONS, ActivityAssetDisposalReason
from ...domain.renta.actividad_asset.election import DirectEstimationRegime
from ...domain.renta.actividad_asset.election_facts import method_is_statable
from ...domain.renta.actividad_asset.lifecycle import (
    BASIS_STAGE_FACTS,
    OPENING_STATUS_FACTS,
    REGISTERABLE_ACQUISITION_SHAPES,
    AssetBasisStage,
    AssetKind,
)
from ..operations.public_scalar import project_scalar
from .activity_asset_read_models import (
    ActivityAssetBasisStageOption,
    ActivityAssetDisposalReasonOption,
    ActivityAssetEdition,
    ActivityAssetFormOptionsView,
    ActivityAssetOpeningStatusOption,
    ActivityAssetTableGroup,
    activity_asset_label_key,
)
from .fact_wording import token_family
from .register_reads import method_facts_view


def form_options_view(
    options: ActivityAssetFormOptions,
    *,
    tax_year: int,
    asset_kind: AssetKind,
    regime: DirectEstimationRegime,
    edition: ActivityAssetEdition,
    m130_periods: Callable[[int], tuple[str, ...]],
) -> ActivityAssetFormOptionsView:
    """Build the view from the pinned options and profile modality."""
    offered = tuple(method for method in options.methods if method_is_statable(method))
    return ActivityAssetFormOptionsView(
        tax_year=tax_year,
        asset_kind=asset_kind,
        regime=regime,
        edition=edition,
        acquisition_shapes=REGISTERABLE_ACQUISITION_SHAPES,
        declared_activities=tuple(TipoActividad),
        methods=offered,
        method_facts=tuple(method_facts_view(method) for method in offered),
        table_groups=tuple(
            ActivityAssetTableGroup(
                class_key=group.class_key,
                class_label=group.class_label,
                maximum_coefficient=project_scalar(group.maximum_coefficient),
                minimum_coefficient=project_scalar(group.minimum_coefficient),
                maximum_period_years=project_scalar(group.maximum_period_years),
                can_hold_vehicle=group.can_hold_vehicle,
            )
            for group in options.table_groups
        ),
        disposal_reasons=tuple(
            ActivityAssetDisposalReasonOption(
                reason=reason,
                label_key=activity_asset_label_key(token_family(ActivityAssetDisposalReason), reason),
            )
            for reason in ADMITTED_DISPOSAL_REASONS
        ),
        basis_stages=tuple(
            ActivityAssetBasisStageOption(stage=stage, facts=facts, is_property=stage is AssetBasisStage.WHOLE_PROPERTY)
            for stage, facts in BASIS_STAGE_FACTS.items()
        ),
        opening_statuses=tuple(
            ActivityAssetOpeningStatusOption(status=status, facts=facts)
            for status, facts in OPENING_STATUS_FACTS.items()
        ),
        m130_periods=m130_periods(tax_year),
    )
