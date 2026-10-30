"""Test support for applying Modelo source diagnostics across application packages."""

from ....domain.calculations.registry.schema import ModeloRevision
from ...aggregation.source_mesh import CalculationSourceResolution
from .._calculation_source_staging import add_expected_missing_binding_diagnostics


def apply_expected_missing_binding_diagnostics(
    revision: ModeloRevision, resolution: CalculationSourceResolution
) -> CalculationSourceResolution:
    return add_expected_missing_binding_diagnostics(revision, resolution)
