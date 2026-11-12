"""Composition group for the pension contribution certificate operations."""

from __future__ import annotations

from ..application.operations.contract_manifest import OperationGroupBuild
from .operation_composition_inputs import OperationCompositionInputs, built


def compose_prevision_social_contribution_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose the list, record and removal operations of the pension contribution certificates."""
    from ..application.prevision_social_contribution.registered_operation import (
        build_prevision_social_list_definition,
        build_prevision_social_list_registration,
        build_prevision_social_mutation_registration,
        build_prevision_social_record_definition,
        build_prevision_social_remove_definition,
    )
    from .prevision_social_contribution_composition import build_prevision_social_contribution_ports

    del inputs
    ports = build_prevision_social_contribution_ports
    listing = build_prevision_social_list_definition(ports)
    record = build_prevision_social_record_definition(ports)
    remove = build_prevision_social_remove_definition(ports)
    return built(
        (listing, record, remove),
        (
            build_prevision_social_list_registration(listing),
            build_prevision_social_mutation_registration(record),
            build_prevision_social_mutation_registration(remove),
        ),
    )
