"""A negative art. 105.Seis base stays an unresolved finding, never a domain error.

See Also:
    :func:`~application.calculations.prorrata_regularizacion.negative_gross_base_finding`
        Guard the settlement resolver consults before the partitioned
        regularisation, exercised here directly.
    :func:`~domain.iva.prorrata.compute_regularizacion_prorrata_particionada`
        Domain computation whose partitions refuse a negative gross base.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.i18n.render import tr as render_tr
from ....domain.iva.errors import ProrrataInputError
from ....domain.iva.prorrata import RegularizacionProrrataParticion
from ..prorrata_regularizacion_periods import negative_gross_base_finding

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def test_negative_partitions_are_named_with_their_total() -> None:
    """Rectifications that drive two sectors below zero report the sum of the negative bases."""
    finding = negative_gross_base_finding(
        {"sector-a": Decimal("-150.00"), "sector-b": Decimal("-25.50"), None: Decimal("300.00")},
    )

    assert finding == render_tr(
        "application.calculations.prorrata_regularizacion.unresolved.gross_negative",
        amount=Decimal("-175.50"),
    )


@pytest.mark.parametrize(
    "gross_by_partition",
    [{None: Decimal("1280.00")}, {None: Decimal("0.00")}, {}],
)
def test_non_negative_bases_raise_no_finding(gross_by_partition: dict[str | None, Decimal]) -> None:
    """A zero or positive base, or no regularisable cuota at all, is regularised normally."""
    assert negative_gross_base_finding(gross_by_partition) is None


def test_the_domain_partition_still_refuses_a_negative_base() -> None:
    """The guard exists because the pure computation does not define a negative base."""
    with pytest.raises((ProrrataInputError, ValueError)):
        RegularizacionProrrataParticion(
            cuotas_soportadas_deducibles=Decimal("-150.00"),
            prorrata_definitiva_pct=Decimal("56"),
        )
