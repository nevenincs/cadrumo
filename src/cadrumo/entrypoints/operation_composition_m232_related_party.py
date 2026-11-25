"""Composition group for the Modelo 232 related-party statement operations."""

from __future__ import annotations

from ..application.operations.contract_manifest import OperationGroupBuild
from .operation_composition_inputs import OperationCompositionInputs, built


def compose_m232_related_party_operations(inputs: OperationCompositionInputs) -> OperationGroupBuild:
    """Compose the statement, withdrawal and listing operations of the Modelo 232 related-party records."""
    from ..application.m232_related_party.contracts import (
        M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID,
        M232_RELATED_PARTY_WRITE_DEFINITION_IDS,
    )
    from ..application.m232_related_party.registered_operation import (
        build_m232_related_party_definition,
        build_m232_related_party_list_registration,
        build_m232_related_party_registration,
    )
    from .m232_related_party_composition import build_m232_related_party_ports

    del inputs
    writes = tuple(
        build_m232_related_party_definition(definition_id, build_m232_related_party_ports)
        for definition_id in sorted(M232_RELATED_PARTY_WRITE_DEFINITION_IDS)
    )
    listing = build_m232_related_party_definition(
        M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID, build_m232_related_party_ports
    )
    return built(
        (*writes, listing),
        (
            *(build_m232_related_party_registration(definition) for definition in writes),
            build_m232_related_party_list_registration(listing),
        ),
    )
