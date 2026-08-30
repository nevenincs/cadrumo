"""Parity gate: the descendant CLI payload is a lossless projection of ``DescendantInfo``.

The transport previously re-declared the canonical record with free strings and
arbitrary integers, and omitted ``meses_madre_trabajo`` and
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

from ....core import DescendantRelacion
from ....domain.contribuyente.descendant import DescendantInfo
from .._config_descendiente_payloads import ProfileDescendientePayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _payload_from(canonical: DescendantInfo, *, index: int = 0) -> ProfileDescendientePayload:
    """Project a canonical descendant exactly as the ``descendiente list`` verb does."""
    return ProfileDescendientePayload(
        index=index,
        birth_date=canonical.birth_date,
        relacion=canonical.relacion,
        inscripcion_registro_civil_date=canonical.inscripcion_registro_civil_date,
        acogimiento_resolucion_date=canonical.acogimiento_resolucion_date,
        discapacidad_grado=canonical.discapacidad_grado,
        convive_con_contribuyente=canonical.convive_con_contribuyente,
        dependencia_economica=canonical.dependencia_economica,
        custodia_compartida=canonical.custodia_compartida,
        meses_madre_trabajo=canonical.meses_madre_trabajo,
        gastos_guarderia_euros=canonical.gastos_guarderia_euros,
        nif=canonical.nif,
    )


def test_payload_carries_every_canonical_descendant_field() -> None:
    """No canonical ``DescendantInfo`` field is dropped by the CLI projection."""
    canonical = DescendantInfo(
        birth_date=date(2022, 5, 1),
        relacion=DescendantRelacion.ADOPTADO,
        inscripcion_registro_civil_date=date(2023, 6, 2),
        acogimiento_resolucion_date=date(2022, 9, 3),
        discapacidad_grado=33,
        convive_con_contribuyente=True,
        custodia_compartida=True,
        meses_madre_trabajo=(1, 2, 3, 4, 5, 6),
        gastos_guarderia_euros=1500,
        nif="12345678Z",
    )

    wire = _payload_from(canonical).model_dump(mode="json")

    assert set(DescendantInfo.model_fields) - set(wire) == set()


def test_tax_bearing_values_survive_the_projection() -> None:
    """The deducción-maternidad and guardería inputs reach the wire unchanged."""
    canonical = DescendantInfo(
        birth_date=date(2022, 5, 1),
        meses_madre_trabajo=(1, 2, 3, 4, 5, 6),
        gastos_guarderia_euros=1500,
    )

    wire = _payload_from(canonical).model_dump(mode="json")

    assert wire["meses_madre_trabajo"] == [1, 2, 3, 4, 5, 6]
    assert wire["gastos_guarderia_euros"] == 1500


def test_dates_keep_their_iso_wire_form() -> None:
    """Typing the fields as ``date`` must not change the emitted JSON shape."""
    canonical = DescendantInfo(
        birth_date=date(2018, 1, 1),
        relacion=DescendantRelacion.ADOPTADO,
        inscripcion_registro_civil_date=date(2019, 3, 4),
        acogimiento_resolucion_date=date(2018, 7, 5),
    )

    wire = _payload_from(canonical).model_dump(mode="json")

    assert wire["birth_date"] == "2018-01-01"
    assert wire["inscripcion_registro_civil_date"] == "2019-03-04"
    assert wire["acogimiento_resolucion_date"] == "2018-07-05"


def test_relacion_reaches_the_wire_as_its_token() -> None:
    """The axis deciding Art. 58.2 entitlement must be readable off the payload.

    A temporal acogimiento takes the Art. 58.1 tranches and NOT the Art. 58.2
    increase. A machine-readable surface that dropped or flattened the relación
    would put that distinction outside the contract, and the consumer would have
    only the dates -- which for this carer are absent by design, so the record
    would read as an ordinary descendant.
    """
    canonical = DescendantInfo(
        birth_date=date(2015, 1, 1),
        relacion=DescendantRelacion.ACOGIMIENTO_TEMPORAL,
    )

    wire = _payload_from(canonical).model_dump(mode="json")

    assert wire["relacion"] == "acogimiento_temporal"


@pytest.mark.parametrize(
    ("field_overrides", "reason"),
    [
        ({"index": -1}, "negative list index"),
        ({"birth_date": "not-date"}, "unparseable birth date"),
        ({"discapacidad_grado": 50}, "grado outside the closed 0/33/65 set"),
        ({"nif": "bad"}, "NIF that is not 9 characters"),
        ({"meses_madre_trabajo": (13,)}, "a month outside the calendar"),
        ({"meses_madre_trabajo": (0,)}, "a zero month"),
        ({"meses_madre_trabajo": (3, 3)}, "a repeated month"),
        ({"meses_madre_trabajo": (6, 3)}, "an unsorted month set"),
        ({"gastos_guarderia_euros": -1}, "negative guardería expenses"),
        ({"alta_posterior_nacimiento_mes": 0}, "alta-posterior month outside 1-12"),
        ({"alta_posterior_nacimiento_mes": 13}, "alta-posterior month outside 1-12"),
        (
            {"alta_posterior_nacimiento_mes": 5, "meses_madre_trabajo": ()},
            "alta-posterior month declared with zero worked months",
        ),
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
        ProfileDescendientePayload.model_validate(fields)


def test_payload_refuses_an_entry_event_predating_birth() -> None:
    """An entry event before birth is impossible and must not cross the boundary."""
    with pytest.raises(ValidationError):
        ProfileDescendientePayload(
            index=0,
            birth_date=date(2020, 1, 1),
            relacion=DescendantRelacion.ADOPTADO,
            inscripcion_registro_civil_date=date(2019, 1, 1),
            convive_con_contribuyente=True,
            custodia_compartida=False,
        )


def test_payload_refuses_a_future_entry_event() -> None:
    """A not-yet-inscribed adoption cannot already be declared."""
    with pytest.raises(ValidationError):
        ProfileDescendientePayload(
            index=0,
            birth_date=date(2020, 1, 1),
            relacion=DescendantRelacion.ADOPTADO,
            inscripcion_registro_civil_date=date.today() + timedelta(days=365),
            convive_con_contribuyente=True,
            custodia_compartida=False,
        )


@pytest.mark.parametrize(
    ("relacion", "date_field"),
    [
        (DescendantRelacion.TUTELA, "inscripcion_registro_civil_date"),
        (DescendantRelacion.TUTELA, "acogimiento_resolucion_date"),
        (DescendantRelacion.ACOGIMIENTO_TEMPORAL, "inscripcion_registro_civil_date"),
        (DescendantRelacion.ACOGIMIENTO_TEMPORAL, "acogimiento_resolucion_date"),
        (DescendantRelacion.DESCENDIENTE, "inscripcion_registro_civil_date"),
        (DescendantRelacion.ACOGIMIENTO_PREADOPTIVO_O_PERMANENTE, "inscripcion_registro_civil_date"),
    ],
)
def test_payload_refuses_an_entry_date_the_relacion_cannot_carry(
    relacion: DescendantRelacion,
    date_field: str,
) -> None:
    """The transport enforces the coherence rule, not only the canonical record.

    A payload the canonical record would refuse is a shape that exists only on
    the wire, and this one is the shape that matters: an Art. 58.2 anchor riding
    a relación the statute excludes. Tolerating it here would let the excluded
    case re-enter through the transport, which is precisely where nobody would
    look for it.
    """
    fields: dict[str, object] = {
        "index": 0,
        "birth_date": date(2015, 1, 1),
        "relacion": relacion,
        "convive_con_contribuyente": True,
        "custodia_compartida": False,
        date_field: date(2018, 1, 1),
    }

    with pytest.raises(ValidationError):
        ProfileDescendientePayload.model_validate(fields)
