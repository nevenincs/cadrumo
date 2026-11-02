"""Composition group for the suffered-withholding certificate operations."""

from __future__ import annotations

from ..application.operations.contract_manifest import OperationGroupBuild
from .operation_composition_inputs import OperationCompositionInputs, built


def compose_retencion_soportada_certificado_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose the list, record and removal operations of the payer certificates."""
    from ..application.retencion_soportada_certificado.registered_operation import (
        build_retencion_soportada_list_definition,
        build_retencion_soportada_list_registration,
        build_retencion_soportada_mutation_registration,
        build_retencion_soportada_record_definition,
        build_retencion_soportada_remove_definition,
    )
    from .retencion_soportada_certificado_composition import build_retencion_soportada_certificado_ports

    del inputs
    ports = build_retencion_soportada_certificado_ports
    listing = build_retencion_soportada_list_definition(ports)
    record = build_retencion_soportada_record_definition(ports)
    remove = build_retencion_soportada_remove_definition(ports)
    return built(
        (listing, record, remove),
        (
            build_retencion_soportada_list_registration(listing),
            build_retencion_soportada_mutation_registration(record),
            build_retencion_soportada_mutation_registration(remove),
        ),
    )
