"""A Modelo 100 refund refused for want of an account cites the Orden of the edition serving its ejercicio.

The Orden each year's citation must come from is read from the serving edition's
own ``orden_aplicabilidad``, apart from the fact under test. A year no edition
authors is served by the nearest edition and cites that edition's Orden.
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
    revision_selected_for,
    supported_authored_exercises,
    supported_exercises_with_projection,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..action_errors import ModeloRefundAccountMissingError
from ..export_settlement import DeclaredSettlement, settlement_dictionary_values
from ..refund_account_authority import refund_account_legal_refs

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_MODELO = "100"
_ANNUAL = "0A"
_CLOCK = datetime(1980, 7, 9, tzinfo=UTC)
#: The refund the Modelo 100 settles, by statute, whichever Orden is cited beside it.
_STATUTE = "ley-35-2006:art-103"


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


def test_every_supported_year_cites_the_orden_of_the_edition_serving_it(operation: PinnedAuthorityOperation) -> None:
    years = supported_exercises_with_projection(_MODELO)
    cited = {year: refund_account_legal_refs(_work_unit(year), operation=operation) for year in years}

    assert len(years) > len(supported_authored_exercises(_MODELO))
    for year, refs in cited.items():
        ordenes = {_document(ref) for ref in refs if ref != _STATUTE}
        assert ordenes == _approving_ordenes(year), year
        assert _STATUTE in refs, year
        assert len(refs) > 1, year


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
            refund_legal_refs=lambda: refs,
        )

    context = refused.value.context or {}
    assert str(context["legal_refs"]).split(", ") == list(refs)
    assert context["account_role"] == "refund"
