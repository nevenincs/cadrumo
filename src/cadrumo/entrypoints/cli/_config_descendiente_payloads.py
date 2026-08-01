"""Typed ``--json`` payload schemas for the ``config profile descendiente`` family.

Split out of the cohesive sibling :mod:`_config_payloads` so the declared-descendant
transport can carry the full canonical contract without growing that module.

:class:`ProfileDescendientePayload` is a lossless projection of
:class:`~cadrumo.domain.contribuyente.DescendantInfo`: every field the canonical
record validates is re-declared here with the same shape, including the two
tax-driving inputs (``meses_madre_trabajo_2024``, ``gastos_guarderia_euros``) that
feed the Art. 81 / 81 bis LIRPF deducción maternidad and guardería deductions.
Dropping either at the transport boundary would silently remove a taxpayer's
deduction from every machine-readable surface, so they are carried, not summarised.

``birth_date`` and ``adoption_date`` are declared as real :class:`datetime.date`
values rather than free strings. The strict :class:`OutputSchema` base refuses an
ISO string for a date field, so emit sites pass the typed value they already hold;
``model_dump(mode="json")`` renders the same ISO-8601 wire form as before.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

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
    adoption_date: date | None = None
    discapacidad_grado: Literal[0, 33, 65] | None = None
    convive_con_contribuyente: bool
    custodia_compartida: bool
    meses_madre_trabajo_2024: int = Field(default=0, ge=0, le=12)
    gastos_guarderia_euros: int = Field(default=0, ge=0)
    nif: DescendantNif | None = None

    @model_validator(mode="after")
    def _validate_adoption_date(self) -> ProfileDescendientePayload:
        """Mirror the canonical adoption-date ordering and non-future rules."""
        if self.adoption_date is None:
            return self
        if self.adoption_date < self.birth_date:
            raise ValueError(f"adoption_date {self.adoption_date} must be >= birth_date {self.birth_date}")
        today = today_madrid()
        if self.adoption_date > today:
            raise ValueError(f"adoption_date {self.adoption_date} must not be in the future (today={today})")
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
