"""Parity gate: the descendant CLI payload is a lossless projection of ``DescendantInfo``.

The transport previously re-declared the canonical record with free strings and
arbitrary integers, and omitted ``meses_madre_trabajo_2024`` and
``gastos_guarderia_euros`` entirely. Those two are tax-driving inputs (Art. 81 and
81 bis LIRPF), so a projection that drops them removes a taxpayer's deduction from
every machine-readable surface without any refusal.

The field-set assertion is the load-bearing one: it is derived from
``DescendantInfo.model_fields`` rather than a hand-written list, so a canonical
field added later fails this gate instead of silently vanishing at the boundary.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from ....domain.contribuyente import DescendantInfo
from .._config_descendiente_payloads import ProfileDescendientePayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _payload_from(canonical: DescendantInfo, *, index: int = 0) -> ProfileDescendientePayload:
    """Project a canonical descendant exactly as the ``descendiente list`` verb does."""
    return ProfileDescendientePayload(
        index=index,
        birth_date=canonical.birth_date,
        adoption_date=canonical.adoption_date,
        discapacidad_grado=canonical.discapacidad_grado,
        convive_con_contribuyente=canonical.convive_con_contribuyente,
        custodia_compartida=canonical.custodia_compartida,
        meses_madre_trabajo_2024=canonical.meses_madre_trabajo_2024,
        gastos_guarderia_euros=canonical.gastos_guarderia_euros,
        nif=canonical.nif,
    )


def test_payload_carries_every_canonical_descendant_field() -> None:
    """No canonical ``DescendantInfo`` field is dropped by the CLI projection."""
    canonical = DescendantInfo(
        birth_date=date(2022, 5, 1),
        adoption_date=date(2023, 6, 2),
        discapacidad_grado=33,
        convive_con_contribuyente=True,
        custodia_compartida=True,
        meses_madre_trabajo_2024=6,
        gastos_guarderia_euros=1500,
        nif="12345678Z",
    )

    wire = _payload_from(canonical).model_dump(mode="json")

    assert set(DescendantInfo.model_fields) - set(wire) == set()


def test_tax_bearing_values_survive_the_projection() -> None:
    """The deducción-maternidad and guardería inputs reach the wire unchanged."""
    canonical = DescendantInfo(
        birth_date=date(2022, 5, 1),
        meses_madre_trabajo_2024=6,
        gastos_guarderia_euros=1500,
    )

    wire = _payload_from(canonical).model_dump(mode="json")

    assert wire["meses_madre_trabajo_2024"] == 6
    assert wire["gastos_guarderia_euros"] == 1500


def test_dates_keep_their_iso_wire_form() -> None:
    """Typing the fields as ``date`` must not change the emitted JSON shape."""
    canonical = DescendantInfo(birth_date=date(2018, 1, 1), adoption_date=date(2019, 3, 4))

    wire = _payload_from(canonical).model_dump(mode="json")

    assert wire["birth_date"] == "2018-01-01"
    assert wire["adoption_date"] == "2019-03-04"


@pytest.mark.parametrize(
    ("field_overrides", "reason"),
    [
        ({"index": -1}, "negative list index"),
        ({"birth_date": "not-date"}, "unparseable birth date"),
        ({"discapacidad_grado": 50}, "grado outside the closed 0/33/65 set"),
        ({"nif": "bad"}, "NIF that is not 9 characters"),
        ({"meses_madre_trabajo_2024": 13}, "more mother-work months than exist in a year"),
        ({"meses_madre_trabajo_2024": -1}, "negative mother-work months"),
        ({"gastos_guarderia_euros": -1}, "negative guardería expenses"),
    ],
)
def test_payload_refuses_values_the_canonical_record_refuses(
    field_overrides: dict[str, object],
    reason: str,
) -> None:
    """Every malformed value the canonical record rejects is rejected at the boundary too."""
    fields: dict[str, object] = {
        "index": 0,
        "birth_date": date(2020, 1, 1),
        "convive_con_contribuyente": True,
        "custodia_compartida": False,
    }
    fields.update(field_overrides)

    with pytest.raises(ValidationError):
        ProfileDescendientePayload(**fields)  # type: ignore[arg-type]


def test_payload_refuses_an_adoption_predating_birth() -> None:
    """Adoption before birth is impossible and must not cross the boundary."""
    with pytest.raises(ValidationError):
        ProfileDescendientePayload(
            index=0,
            birth_date=date(2020, 1, 1),
            adoption_date=date(2019, 1, 1),
            convive_con_contribuyente=True,
            custodia_compartida=False,
        )


def test_payload_refuses_a_future_adoption_date() -> None:
    """A not-yet-finalised adoption cannot already be declared."""
    with pytest.raises(ValidationError):
        ProfileDescendientePayload(
            index=0,
            birth_date=date(2020, 1, 1),
            adoption_date=date.today() + timedelta(days=365),
            convive_con_contribuyente=True,
            custodia_compartida=False,
        )
