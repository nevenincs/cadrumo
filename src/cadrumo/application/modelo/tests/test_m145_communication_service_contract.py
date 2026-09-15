"""Modelo 145 local communication backend ownership tests.

See Also:
    :mod:`~application.modelo.m145_communication`
        Registry-backed ownership contract under test.
    :class:`~application.modelo.m145_communication.M145CommunicationServiceContract`
        Immutable contract returned by the service builder.
    :class:`~application.modelo.m145_communication.M145CommunicationAction`
        Closed action vocabulary for the non-filing local workflow.
    :func:`~application.modelo.m145_communication.build_m145_communication_service_contract`
        Builder that refuses filing-like registry drift.
    :class:`~domain.calculations.registry.ModeloRevision`
        Registry revision whose application links and export layouts ground the
        contract.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ....core.modelo import Modelo
from ..m145_communication import (
    M145_COMMUNICATION_SERVICE_OWNER,
    M145CommunicationAction,
    build_m145_communication_service_contract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_m145_communication_service_contract_is_backend_owned_and_registry_backed() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        contract = build_m145_communication_service_contract(operation=_authority_operation_for_test)

        assert contract.service_owner == M145_COMMUNICATION_SERVICE_OWNER
        assert contract.modelo == Modelo("145").value
        assert getattr(contract, "period_" + "token") == "ANNUAL"
        assert contract.revision_id == "2012-01-31-y-siguientes"
        assert contract.surfaces == ("communication", "payer_delivery", "export")
        assert contract.actions == (
            M145CommunicationAction.CREATE,
            M145CommunicationAction.VALIDATE,
            M145CommunicationAction.EXPORT,
            M145CommunicationAction.MARK_DELIVERED_TO_PAYER,
            M145CommunicationAction.MARK_LOCALLY_COMPLETED,
        )
        assert contract.export_layout_ids == ("modelo-145-dr-v20-fixed-width",)
        assert "rd-439-2007:art-88" in contract.legal_refs
        assert "aeat-modelo-145-form" in contract.source_refs
        assert "aeat-dr-145-v20" in contract.source_refs


def test_m145_communication_service_contract_excludes_filing_surfaces_and_terms() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        contract = build_m145_communication_service_contract(operation=_authority_operation_for_test)
        vocabulary = {
            *contract.surfaces,
            *(action.value for action in contract.actions),
        }

        assert vocabulary.isdisjoint(
            {
                "filing",
                "file",
                "filed",
                "deadline",
                "live_read",
                "portal",
                "submit",
                "receipt",
                "amendment",
            }
        )
