"""Composition group for the suffered-withholding absence attestation operations."""

from __future__ import annotations

from ..application.operations.contract_manifest import OperationGroupBuild
from .operation_composition_inputs import OperationCompositionInputs, built


def compose_retencion_soportada_absence_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose the attestation, withdrawal and list operations of the absence of suffered withholding."""
    from ..application.retencion_soportada_absence.registered_operation import (
        build_retencion_soportada_absence_attest_definition,
        build_retencion_soportada_absence_list_definition,
        build_retencion_soportada_absence_list_registration,
        build_retencion_soportada_absence_registration,
        build_retencion_soportada_absence_withdraw_definition,
    )
    from .retencion_soportada_absence_composition import build_retencion_soportada_absence_ports

    del inputs
    attest = build_retencion_soportada_absence_attest_definition(build_retencion_soportada_absence_ports)
    withdraw = build_retencion_soportada_absence_withdraw_definition(build_retencion_soportada_absence_ports)
    listing = build_retencion_soportada_absence_list_definition(build_retencion_soportada_absence_ports)
    return built(
        (attest, withdraw, listing),
        (
            build_retencion_soportada_absence_registration(attest),
            build_retencion_soportada_absence_registration(withdraw),
            build_retencion_soportada_absence_list_registration(listing),
        ),
    )
