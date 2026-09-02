"""Unit tests for the LIRPF Art. 85 imputación-regime discriminator.

Pins :attr:`cadrumo.domain.fincas.Finca.imputed_under_art_85` against
every :class:`cadrumo.domain.fincas.UseType` member, anchoring the
regime-mapping invariant declared in the docstrings of
:class:`Finca` and :class:`UseType`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..enums import TitularContribuyente, TitularidadRegime, UseType
from ..models import Finca
from ..titularidad import Titularidad

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _finca(use_type: UseType) -> Finca:
    return Finca(
        identifier=f"calle-prueba-{use_type.value.lower()}",
        address="Calle de prueba 1, 28001 Madrid",
        valor_catastral_total=Decimal("100000.00"),
        valor_catastral_construccion=Decimal("60000.00"),
        valor_catastral_revision_year=2018,
        coste_adquisicion=Decimal("120000.00"),
        coste_adquisicion_construccion=Decimal("72000.00"),
        acquisition_date=date(2018, 1, 1),
        use_type=use_type,
        titularidad=Titularidad(
            regime=TitularidadRegime.PLENO_DOMINIO,
            contribuyente=TitularContribuyente.PRIMER_DECLARANTE,
            porcentaje_propiedad=Decimal("100.00"),
        ),
    )


@pytest.mark.parametrize(
    ("use_type", "expected"),
    [
        (UseType.VIVIENDA_ARRENDADA, False),
        (UseType.LOCAL_COMERCIAL, False),
        (UseType.VIVIENDA_HABITUAL, False),
        (UseType.OTRO_INMUEBLE_NO_AFECTO, True),
        (UseType.VIVIENDA_DESOCUPADA, True),
    ],
)
def test_imputed_under_art_85_discriminates_every_use_type(
    use_type: UseType,
    expected: bool,
) -> None:
    """Every :class:`UseType` member maps to the documented Art. 85 verdict."""

    assert _finca(use_type).imputed_under_art_85 is expected
