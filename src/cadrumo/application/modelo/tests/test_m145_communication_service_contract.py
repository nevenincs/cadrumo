"""Modelo 145 local communication backend ownership tests.

See Also:
    :mod:`~application.modelo._m145_communication`
        Registry-backed ownership contract under test.
    :class:`~application.modelo.M145CommunicationServiceContract`
        Immutable contract returned by the service builder.
    :class:`~application.modelo.M145CommunicationAction`
        Closed action vocabulary for the non-filing local workflow.
    :func:`~application.modelo.build_m145_communication_service_contract`
        Public facade builder that refuses filing-like registry drift.
    :class:`~domain.calculations.registry.ModeloRevision`
        Registry revision whose application links and export layouts ground the
        contract.
"""

from __future__ import annotations

import pytest

from .._m145_communication import (
    M145_COMMUNICATION_MODELO,
    M145_COMMUNICATION_PERIOD,
    M145_COMMUNICATION_SERVICE_OWNER,
    M145CommunicationAction,
    build_m145_communication_service_contract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_m145_communication_service_contract_is_backend_owned_and_registry_backed() -> None:
    contract = build_m145_communication_service_contract()

    assert contract.service_owner == M145_COMMUNICATION_SERVICE_OWNER
    assert contract.modelo == M145_COMMUNICATION_MODELO
    assert contract.period_token == M145_COMMUNICATION_PERIOD
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
    contract = build_m145_communication_service_contract()
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
