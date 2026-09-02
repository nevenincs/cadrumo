"""Typed ``--json`` payload schemas for the ``config profile descendiente`` family.

Split out of the cohesive sibling :mod:`_config_payloads` so the declared-descendant
transport can carry the full canonical contract without growing that module.

:class:`ProfileDescendientePayload` is a lossless projection of
:class:`~cadrumo.domain.contribuyente.DescendantInfo`: every field the canonical
record validates is re-declared here with the same shape, including the two
tax-driving inputs (``meses_madre_trabajo``, ``gastos_guarderia_euros``) that
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

``gastos_guarderia_mensuales`` rides as typed month rows rather than the canonical
``MM:AMOUNT`` string the ``--descendiente`` flag and the fact index carry. That
string is an INPUT grammar, chosen so a month map fits a flag value that already
splits on commas; a machine-readable transport has structure available and should
not make its consumer re-implement a parser to read a month.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import NonNegativeInt, StringConstraints, field_validator, model_validator

from ...core.descendant_relacion import ART_58_2_ENTITLING_RELACIONES, DescendantRelacion
from ...core.json_contract import OutputSchema
from ...core.text_bounds import is_canonical_month_set
from ...core.time.clock import today_madrid
from ...domain.contribuyente.descendant_record import DescendantRecordFields

DescendantNif = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, min_length=9, max_length=9),
]
"""Optional descendant NIF/NIE, shaped exactly as :class:`DescendantInfo` validates it."""


class ProfileDescendientePayload(DescendantRecordFields, OutputSchema):
    """One declared descendant row in the ``config profile descendiente`` surface.

    Lossless projection of :class:`~cadrumo.domain.contribuyente.DescendantInfo`;
    ``index`` is the 0-based position :func:`~cadrumo.domain.contribuyente.descendant_list_from_facts`
    assigns, the same index ``descendiente remove`` addresses.
    """

    index: NonNegativeInt
    # ``convive_con_contribuyente``, ``custodia_compartida`` and
    # ``gastos_guarderia_mensuales`` come from the shared field vocabulary with
    # their canonical types; the projection always states them explicitly.
    nif: DescendantNif | None = None

    @field_validator("meses_madre_trabajo")
    @classmethod
    def _validate_meses_madre_trabajo(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        """Mirror the canonical month-set rules on the wire.

        Mirrored for the same reason the coherence rules below are: this
        transport is a lossless projection, so a payload a consumer could
        construct but the canonical record would refuse is a shape that exists
        only on the wire.
        """
        if not is_canonical_month_set(value):
            raise ValueError(
                "meses_madre_trabajo must name real months, once each, in ascending order",
            )
        return value

    @model_validator(mode="after")
    def _validate_guarderia_spend(self) -> ProfileDescendientePayload:
        """Mirror the canonical one-spend-authority-per-child rule on the wire.

        Mirrored rather than left to the record for the same reason the entry-date
        coherence rules are: this transport is a lossless projection, so a payload
        a consumer could construct but the canonical record would refuse is a
        shape that exists only on the wire. Here that shape is a child carrying
        both an annual total and a monthly breakdown — two spend figures with no
        rule saying which reached the filing, which is exactly the ambiguity the
        canonical refusal exists to remove.

        The repeated-month half is mirrored too. A sparse map's only way to
        contradict itself is two rows for one month, and summing them would
        invent a figure nobody stated.
        """
        months = [row.month for row in self.gastos_guarderia_mensuales]
        duplicates = sorted({month for month in months if months.count(month) > 1})
        if duplicates:
            raise ValueError(f"gastos_guarderia_mensuales declares month(s) {duplicates} more than once")
        if self.gastos_guarderia_mensuales and self.gastos_guarderia_euros > 0:
            raise ValueError(
                "gastos_guarderia_euros and gastos_guarderia_mensuales cannot both be declared for one descendant",
            )
        return self

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

    @model_validator(mode="after")
    def _validate_alta_posterior_coherence(self) -> ProfileDescendientePayload:
        """Mirror the canonical alta-posterior/worked-months coherence rule on the wire.

        Mirrored for the same reason the entry-date rules above are: a payload a
        consumer could construct but the canonical record would refuse is a
        shape that exists only on the wire.
        """
        if self.alta_posterior_nacimiento_mes is None:
            return self
        if not self.meses_madre_trabajo:
            raise ValueError(
                "alta_posterior_nacimiento_mes is declared but meses_madre_trabajo is empty",
            )
        if self.alta_posterior_nacimiento_mes != self.meses_madre_trabajo[0]:
            raise ValueError(
                "alta_posterior_nacimiento_mes must equal the first declared working month",
            )
        return self


class ConfigProfileDescendienteAddResult(OutputSchema):
    """JSON envelope for ``aeat config profile descendiente add``."""

    profile: str
    added: NonNegativeInt
    total: NonNegativeInt


class ConfigProfileDescendienteListResult(OutputSchema):
    """JSON envelope for ``aeat config profile descendiente list``."""

    profile: str
    total: NonNegativeInt
    descendientes: list[ProfileDescendientePayload] = []


class ConfigProfileDescendienteRemoveResult(OutputSchema):
    """JSON envelope for ``aeat config profile descendiente remove``."""

    profile: str
    removed_index: NonNegativeInt
    total: NonNegativeInt
