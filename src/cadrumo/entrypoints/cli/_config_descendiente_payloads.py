"""Typed ``--json`` payload schemas for the ``config profile descendiente`` family.

Split out of the cohesive sibling :mod:`_config_payloads` so the declared-descendant
transport can carry the full canonical contract without growing that module.

:class:`ProfileDescendientePayload` is a lossless projection of
:class:`~cadrumo.domain.contribuyente.DescendantInfo`: every field the canonical
record validates is re-declared here with the same shape, including the two
tax-driving inputs (``meses_madre_trabajo_2024``, ``gastos_guarderia_euros``) that
feed the Art. 81 LIRPF deducción maternidad (81.1) and guardería increment (81.2).
Dropping either at the transport boundary would silently remove a taxpayer's
deduction from every machine-readable surface, so they are carried, not summarised.

``birth_date`` and the two entry-event dates are declared as real
:class:`datetime.date` values rather than free strings. The strict
:class:`OutputSchema` base refuses an ISO string for a date field, so emit sites
pass the typed value they already hold; ``model_dump(mode="json")`` renders the
same ISO-8601 wire form as before.

``relacion`` rides as the :class:`~cadrumo.core.DescendantRelacion` member rather
than a bare string, so a consumer reading this transport gets the same closed set
the engine branches on. It is what decides whether the Art. 58.2 increase applies
at all — a temporal acogimiento takes the tranches and not the increase — so
flattening it here would put the one distinction the axis exists to draw outside
the machine-readable contract.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from ...core import ART_58_2_ENTITLING_RELACIONES, DescendantRelacion
from ...core.time import today_madrid
from ._schemas import OutputSchema, register_schema

DescendantNif = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, min_length=9, max_length=9),
]
"""Optional descendant NIF/NIE, shaped exactly as :class:`DescendantInfo` validates it."""


class ProfileDescendientePayload(OutputSchema):
    """One declared descendant row in the ``config profile descendiente`` surface.

    Lossless projection of :class:`~cadrumo.domain.contribuyente.DescendantInfo`;
    ``index`` is the 0-based position :func:`~cadrumo.domain.contribuyente.descendant_list_from_facts`
    assigns, the same index ``descendiente remove`` addresses.
    """

    index: int = Field(ge=0)
    birth_date: date
    relacion: DescendantRelacion = DescendantRelacion.DESCENDIENTE
    inscripcion_registro_civil_date: date | None = None
    acogimiento_resolucion_date: date | None = None
    discapacidad_grado: Literal[0, 33, 65] | None = None
    convive_con_contribuyente: bool
    custodia_compartida: bool
    rentas_anuales_euros: Decimal | None = Field(default=None, ge=0)
    presenta_declaracion_propia: bool = False
    prorrata_minimo: bool | None = None
    meses_madre_trabajo_2024: int = Field(default=0, ge=0, le=12)
    gastos_guarderia_euros: int = Field(default=0, ge=0)
    nif: DescendantNif | None = None

    @model_validator(mode="after")
    def _validate_entry_event_dates(self) -> ProfileDescendientePayload:
        """Mirror the canonical entry-date ordering AND the relación coherence rules.

        The ordering half was always mirrored here. The coherence half is
        mirrored too, and deliberately rather than defensively: this transport
        is a lossless projection, so a payload a consumer could construct but
        the canonical record would refuse is a shape that exists only on the
        wire. That is precisely where the excluded case would re-enter — a
        tutela or temporal-acogimiento row carrying an entitling anchor.
        """
        for field_name, value in (
            ("inscripcion_registro_civil_date", self.inscripcion_registro_civil_date),
            ("acogimiento_resolucion_date", self.acogimiento_resolucion_date),
        ):
            if value is None:
                continue
            if value < self.birth_date:
                raise ValueError(f"{field_name} {value} must be >= birth_date {self.birth_date}")
            today = today_madrid()
            if value > today:
                raise ValueError(f"{field_name} {value} must not be in the future (today={today})")
        if self.inscripcion_registro_civil_date is not None and self.relacion is not DescendantRelacion.ADOPTADO:
            raise ValueError(
                f"inscripcion_registro_civil_date cannot be carried by relacion={self.relacion.value!r}",
            )
        if self.acogimiento_resolucion_date is not None and self.relacion not in ART_58_2_ENTITLING_RELACIONES:
            raise ValueError(
                f"acogimiento_resolucion_date cannot be carried by relacion={self.relacion.value!r}",
            )
        return self


@register_schema("config.profile.descendiente.add")
class ConfigProfileDescendienteAddResult(OutputSchema):
    """JSON envelope for ``aeat config profile descendiente add``."""

    profile: str
    added: int = Field(ge=0)
    total: int = Field(ge=0)


@register_schema("config.profile.descendiente.list")
class ConfigProfileDescendienteListResult(OutputSchema):
    """JSON envelope for ``aeat config profile descendiente list``."""

    profile: str
    total: int = Field(ge=0)
    descendientes: list[ProfileDescendientePayload] = []


@register_schema("config.profile.descendiente.remove")
class ConfigProfileDescendienteRemoveResult(OutputSchema):
    """JSON envelope for ``aeat config profile descendiente remove``."""

    profile: str
    removed_index: int = Field(ge=0)
    total: int = Field(ge=0)
