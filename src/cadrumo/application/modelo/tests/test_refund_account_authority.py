"""A Modelo 100 refund refused for want of an account cites the ejercicio's own Orden, never another year's.

The Orden each year's citation must come from is read from the authored edition's
own ``orden_aplicabilidad``, apart from the fact under test. A year no edition
authors is carried from the nearest edition, and its refusal cites the statute
alone rather than the Orden of the year it is carried from.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.payment_instalment_election import PaymentInstalmentElection
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import (
    projected_exercise,
    revision_selected_for,
    supported_authored_exercises,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..action_errors import ModeloRefundAccountMissingError
from ..export_settlement import DeclaredSettlement, settlement_dictionary_values
from ..refund_account_authority import REFUND_ACCOUNT_STATUTE, refund_account_legal_refs

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_MODELO = "100"
_ANNUAL = "0A"
_CLOCK = datetime(1980, 7, 9, tzinfo=UTC)


def _work_unit(filing_year: int) -> WorkUnit:
    bucket_id = "refund-account-authority"
    period = Period.from_year_and_code(filing_year, _ANNUAL)
    revision_id = "r" + "0" * 63
    modelo = ModeloCode(_MODELO)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id, modelo=modelo, filing_year=filing_year, period=period, revision_id=revision_id
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{_MODELO}-{filing_year}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _document(ref: str) -> str:
    return ref.split(":", 1)[0]


def _approving_ordenes(filing_year: int) -> set[str]:
    return {_document(ref) for ref in revision_selected_for(_MODELO, filing_year, _ANNUAL).orden_aplicabilidad}


def test_every_authored_year_cites_the_orden_approving_its_own_edition(operation: PinnedAuthorityOperation) -> None:
    years = supported_authored_exercises(_MODELO)
    cited = {year: refund_account_legal_refs(_work_unit(year), operation=operation) for year in years}

    assert years
    for year, refs in cited.items():
        ordenes = {_document(ref) for ref in refs if ref not in REFUND_ACCOUNT_STATUTE}
        assert ordenes == _approving_ordenes(year), year
        assert set(REFUND_ACCOUNT_STATUTE) <= set(refs), year
        assert len(refs) > len(REFUND_ACCOUNT_STATUTE), year


def test_a_year_no_edition_authors_cites_the_statute_alone(operation: PinnedAuthorityOperation) -> None:
    year = projected_exercise(_MODELO)

    assert refund_account_legal_refs(_work_unit(year), operation=operation) == REFUND_ACCOUNT_STATUTE


def test_the_refusal_of_a_refund_without_an_account_carries_the_citation(operation: PinnedAuthorityOperation) -> None:
    year = supported_authored_exercises(_MODELO)[-1]
    refs = refund_account_legal_refs(_work_unit(year), operation=operation)

    with pytest.raises(ModeloRefundAccountMissingError) as refused:
        settlement_dictionary_values(
            disposition=ResultDisposition.DEVOLUCION,
            settlement=DeclaredSettlement(amount=Decimal("-100.00"), refusal=None),
            instalment=PaymentInstalmentElection.SINGLE,
            first_instalment_share=None,
            charge_account=None,
            refund_account=None,
            refund_legal_refs=refs,
        )

    context = refused.value.context or {}
    assert str(context["legal_refs"]).split(", ") == list(refs)
    assert context["account_role"] == "refund"
