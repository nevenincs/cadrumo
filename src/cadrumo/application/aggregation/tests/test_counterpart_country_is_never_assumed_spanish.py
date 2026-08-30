"""An absent counterparty country must not become Spain at the operator boundary.

``CounterpartObservation`` is what ``aeat app modelo aggregate`` validates each
operator-supplied observation against, so whatever it admits reaches the preview
rollups. Its country field defaulted to ``"ES"``, which made a row that stated
no country indistinguishable from one that stated Spain.

The consequence is not cosmetic. The Modelo 349 readiness rule asks for a GROI
check when the country IS Spain and a NIF-IVA check when it is not, so an
omitted country was read as domestic and the NIF-IVA verification an
intra-community counterparty must pass was never required of it. Modelo 349 is
the recapitulativa de operaciones intracomunitarias, where a Spanish
counterparty is the one thing the row cannot be.

It is also the direction AEAT cross-checks: an informativa naming a counterparty
in the wrong country is reconciled against what that counterparty declared.

The shape is why a search for the fallback found nothing. This was a FIELD
DEFAULT, not an ``or`` expression, so it does not read as a fallback at any call
site -- there is no call site.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import Period
from ....core.aggregation import BindingSourceKind
from .._counterpart import (
    CounterpartObservation,
    OperationKind349,
    aggregate_counterpart_349,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERIOD = Period.from_year_and_code(2026, "2T")


def _observation(**overrides: object) -> CounterpartObservation:
    payload: dict[str, object] = {
        "source_kind": BindingSourceKind.LEDGER_TRANSACTION,
        "source_object_id": "tx-1",
        "counterparty_nif": "DE811234567",
        "counterparty_name": "Muster GmbH",
        "counterparty_country": "DE",
        "operation_kind": OperationKind349.INTRA_DELIVERY.value,
        "operation_period": "2T",
        "taxable_base": Decimal("5000.00"),
        "invoice_total": Decimal("5000.00"),
        "accrued_on": "2026-05-11",
    }
    payload.update(overrides)
    return CounterpartObservation.model_validate(payload)


def test_an_observation_stating_no_country_is_refused() -> None:
    """The defect itself: the field defaulted, so absence was accepted as Spain.

    Refused rather than admitted-as-absent because every consumer branches on
    the country. An optional field would move the same guess into each of them,
    and the shape of the mistake would survive the fix.
    """
    payload = {
        "source_kind": BindingSourceKind.LEDGER_TRANSACTION,
        "source_object_id": "tx-1",
        "counterparty_nif": "DE811234567",
        "operation_kind": OperationKind349.INTRA_DELIVERY.value,
        "operation_period": "2T",
        "taxable_base": Decimal("5000.00"),
        "invoice_total": Decimal("5000.00"),
        "accrued_on": "2026-05-11",
    }

    with pytest.raises(ValidationError) as caught:
        CounterpartObservation.model_validate(payload)

    assert "counterparty_country" in str(caught.value)


def test_the_349_nif_iva_check_is_what_the_default_was_suppressing() -> None:
    """Why the default cost money rather than merely being untidy.

    A non-Spanish counterparty on Modelo 349 must pass the NIF-IVA check. Under
    the old default a row omitting its country was read as Spanish, which
    required the GROI check instead and asked for no NIF-IVA verification at
    all -- on the declaration whose entire subject is intra-community
    operations.

    This asserts the two branches diverge, so the refusal above is protecting a
    real consequence rather than a hypothetical one.
    """
    foreign = aggregate_counterpart_349(
        (_observation(counterparty_country="DE", nif_iva_verified=False),),
        period=_PERIOD,
    )
    (foreign_rollup,) = foreign.rollups

    assert foreign_rollup.requires_nif_iva_check is True
    assert foreign_rollup.declarable_readiness_satisfied is False, (
        "an unverified NIF-IVA on an intra-community counterparty must not read as ready"
    )

    domestic = aggregate_counterpart_349(
        (
            _observation(
                counterparty_nif="12345678Z",
                counterparty_country="ES",
                nif_iva_verified=False,
                groi_verified=True,
            ),
        ),
        period=_PERIOD,
    )
    (domestic_rollup,) = domestic.rollups

    assert domestic_rollup.requires_nif_iva_check is False, (
        "the Spanish branch asks for no NIF-IVA check; that is what an omitted country used to inherit"
    )
    assert domestic_rollup.declarable_readiness_satisfied is True


def test_a_stated_country_still_flows_through_untouched() -> None:
    """The control: this must refuse absence, not make the field harder to use."""
    aggregation = aggregate_counterpart_349(
        (_observation(counterparty_country="FR"),),
        period=_PERIOD,
    )
    (rollup,) = aggregation.rollups

    assert rollup.counterparty_country == "FR"
