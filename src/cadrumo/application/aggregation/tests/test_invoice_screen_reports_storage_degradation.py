"""An unreadable invoice catalogue must not look like an empty one.

The invoice IVA screen exists to refuse a filing whose invoice IVA would be
absent from the transaction-ledger totals the return is about to use. It loads
the invoice catalogue, and that load can fail for reasons that are not the
operator's doing: an envelope that will not decrypt, a version the reader does
not know, a storage validation error.

The screen caught those and returned an empty result. Downstream, an empty result
is indistinguishable from a bucket that genuinely holds no invoices, and the
guard returns without refusing. So a storage fault silently switched off the one
check standing between a partial read and an under-declared return -- and the
operator was told nothing, because the catch bound no exception and emitted no
diagnostic.

Five sibling catches in the same module do the opposite: they bind the error and
return a resolution carrying a ``storage_degraded`` diagnostic. This one was the
exception, and the asymmetry is the defect.

Degrading is still the right behaviour -- a bucket whose invoice catalogue is
temporarily unreadable should not hard-fail every calculation. Degrading SILENTLY
is not. The guard now reports that it did not run.

The fault is injected at the storage boundary because that is the only place a
degraded read can be produced: the failure being exercised is the catch itself,
so the repository must actually raise. Everything downstream of the boundary is
the real production path.
"""

from __future__ import annotations

import pytest

from ....core import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.invoices.errors import InvoicePersistenceError
from ....domain.invoices.models import InvoiceCatalogue
from .._modelo_bindings import (
    CalculationSourceContext,
    _raise_if_invoice_iva_would_be_silent,
    _screened_invoice_iva_observations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = 2026
_PERIOD_CODE = "2T"


class _UnreadableInvoiceCatalogue:
    """A catalogue that exists and cannot be read.

    Fault injection at the I/O boundary, not a stand-in for the code under test:
    the behaviour being exercised IS the screen's handling of a failed load, so
    the load has to fail. It raises a real production error from the set the
    screen catches.
    """

    bucket_id: str = "29292929-2929-4929-8929-292929292929"

    def exists(self) -> bool:
        # It exists. That is the whole distinction under test: absent and
        # unreadable are different answers, and only one of them is degradation.
        return True

    def load(self) -> InvoiceCatalogue:
        raise InvoicePersistenceError("invoice catalogue envelope could not be decrypted")

    def save(self, catalogue: InvoiceCatalogue) -> None:
        raise InvoicePersistenceError("invoice catalogue envelope could not be decrypted")


def _context() -> CalculationSourceContext:
    revision = bundled_authority().snapshot("303", filing_year=_YEAR, period=_PERIOD_CODE).revision
    return CalculationSourceContext(
        bucket_id=_UnreadableInvoiceCatalogue.bucket_id,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD_CODE),
        revision=revision,
    )


def test_the_screen_records_that_it_could_not_read_the_catalogue() -> None:
    """The screen distinguishes "no invoices" from "could not look".

    Asserted on the screen itself rather than only on the guard, because this is
    where the information exists and is thrown away. Anything downstream can only
    report what the screen chose to carry.
    """
    screened = _screened_invoice_iva_observations(
        context=_context(),
        period=Period.from_year_and_code(_YEAR, _PERIOD_CODE),
        invoice_repository=_UnreadableInvoiceCatalogue(),
    )

    assert screened.observations == ()
    assert screened.storage_degraded is True, (
        "an unreadable catalogue is reported as an empty one, so the silence guard cannot tell them apart"
    )


def test_the_silence_guard_carries_the_degradation_to_its_caller() -> None:
    """The guard says it did not run, instead of returning as if it had.

    The guard's whole purpose is to refuse a filing whose invoice IVA is absent
    from the ledger. When the catalogue cannot be read it cannot make that
    judgement at all, and returning quietly is the outcome that reads as "checked
    and fine".
    """
    report = _raise_if_invoice_iva_would_be_silent(
        context=_context(),
        period=Period.from_year_and_code(_YEAR, _PERIOD_CODE),
        transaction_binding_values={},
        invoice_repository=_UnreadableInvoiceCatalogue(),
        prorrata_apportionment=None,
    )

    assert report.storage_degraded is True, (
        "the guard returned as though it had compared the invoice catalogue against the ledger"
    )


def test_a_readable_empty_catalogue_is_not_reported_as_degraded() -> None:
    """The negative case, so the flag means what it says.

    A bucket that genuinely holds no invoices must not raise a degradation
    signal. Without this, the flag would fire on every empty bucket and the
    operator would learn to ignore it -- which is the failure mode that makes an
    advisory worthless.
    """

    class _EmptyCatalogue:
        bucket_id: str = _UnreadableInvoiceCatalogue.bucket_id

        def exists(self) -> bool:
            return False

        def load(self) -> InvoiceCatalogue:
            return InvoiceCatalogue.model_validate({})

        def save(self, catalogue: InvoiceCatalogue) -> None:
            raise NotImplementedError("the screen under test reads the catalogue and never writes it")

    screened = _screened_invoice_iva_observations(
        context=_context(),
        period=Period.from_year_and_code(_YEAR, _PERIOD_CODE),
        invoice_repository=_EmptyCatalogue(),
    )

    assert screened.observations == ()
    assert screened.storage_degraded is False
