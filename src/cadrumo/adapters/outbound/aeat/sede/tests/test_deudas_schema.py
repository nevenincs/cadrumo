"""Validation contract for the AEAT deudas boundary record.

The assertions pin what the boundary refuses, not what it computes: a signed
importe, a blank identifier, an unmodelled objeto tributario, an untyped
direction, and any attempt to repurpose the read marker. AEAT's reported
figures themselves are displayed as reported and asserted nowhere.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ......core import DeudaDireccion, ObjetoTributario, Period
from ..deudas import Deuda

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _deuda(**overrides: object) -> Deuda:
    """Build a valid deuda row, overriding one field at a time."""
    fields: dict[str, object] = {
        "clave_liquidacion": "A2860024500012345",
        "objeto_tributario": ObjetoTributario.SANCION,
        "importe_pendiente": Decimal("150.00"),
        "direccion": DeudaDireccion.DEUDOR,
        "periodo": Period.from_year_and_code(2025, "1T"),
        "situacion": "Pendiente de pago",
    }
    fields.update(overrides)
    return Deuda.model_validate(fields)


def test_a_fully_populated_row_validates_and_carries_the_read_marker() -> None:
    deuda = _deuda()
    assert deuda.clave_liquidacion == "A2860024500012345"
    assert deuda.objeto_tributario is ObjetoTributario.SANCION
    assert deuda.importe_pendiente == Decimal("150.00")
    assert deuda.direccion is DeudaDireccion.DEUDOR
    assert deuda.periodo == Period.from_year_and_code(2025, "1T")
    assert deuda.situacion == "Pendiente de pago"
    assert deuda.mode == "read"


def test_a_negative_importe_is_refused_so_direction_stays_the_only_flow_authority() -> None:
    """The amount is a magnitude; a sign would be a second, conflicting authority."""
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        _deuda(importe_pendiente=Decimal("-150.00"))


def test_a_refundable_amount_is_expressed_by_direction_not_by_a_sign() -> None:
    """AEAT owing the taxpayer is a direction change, not a negative number."""
    deuda = _deuda(direccion=DeudaDireccion.ACREEDOR)
    assert deuda.direccion is DeudaDireccion.ACREEDOR
    assert deuda.importe_pendiente > Decimal("0")


def test_a_zero_importe_is_accepted() -> None:
    """A settled row AEAT still lists is a real state, not a validation error."""
    assert _deuda(importe_pendiente=Decimal("0")).importe_pendiente == Decimal("0")


def test_a_row_with_no_attributable_period_is_accepted() -> None:
    """AEAT attributes some liabilities to no single filing period."""
    assert _deuda(periodo=None).periodo is None


@pytest.mark.parametrize("field", ["clave_liquidacion", "situacion"])
@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_a_blank_identifier_or_situacion_is_refused(field: str, blank: str) -> None:
    """Whitespace-only is refused too; an empty listing cell parses to it.

    A ``min_length`` bound alone would admit it, recording a row whose
    identity and procedural state are unknown as though AEAT reported them.
    """
    with pytest.raises(ValidationError):
        _deuda(**{field: blank})


def test_an_unmodelled_objeto_tributario_is_refused_at_the_boundary() -> None:
    """A label outside the axis never enters as a bare string."""
    with pytest.raises(ValidationError):
        _deuda(objeto_tributario="providencia_de_apremio")


def test_an_untyped_direction_is_refused_at_the_boundary() -> None:
    with pytest.raises(ValidationError):
        _deuda(direccion="owed")


def test_the_read_marker_cannot_be_repurposed_to_a_write() -> None:
    """``mode`` is structurally incapable of naming a mutation."""
    with pytest.raises(ValidationError):
        _deuda(mode="write")


def test_the_record_is_frozen_and_refuses_unknown_fields() -> None:
    """Strict-frozen: a typo'd field is a refusal, not a silently ignored extra."""
    deuda = _deuda()
    with pytest.raises(ValidationError):
        field_name = "importe_pendiente"
        setattr(deuda, field_name, Decimal("1"))
    with pytest.raises(ValidationError):
        _deuda(importe_pendiete=Decimal("1"))


def test_situacion_carries_the_label_aeat_printed_rather_than_a_normalised_token() -> None:
    """The label is displayed as reported; casing and accents survive.

    Normalising here would assert a vocabulary this application does not
    control, and would make two distinct AEAT labels indistinguishable.
    """
    assert _deuda(situacion="En perído ejecutivo").situacion == "En perído ejecutivo"
    assert _deuda(situacion="APLAZAMIENTO CONCEDIDO").situacion == "APLAZAMIENTO CONCEDIDO"
