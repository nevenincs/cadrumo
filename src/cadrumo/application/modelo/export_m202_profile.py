"""Resolve the Modelo 202 page 01 entity facts an export cites, or refuse with the door to state them.

Page 01 of every Modelo 202 record design carries the principal CNAE, the
"Datos adicionales" marks, the tipo de gravamen and the turnover band. Each is
a fact about the entity the operator states on the profile, or a value the
design derives from a stated fact:

- The C.N.A.E. de la actividad principal (2025 design position 118, Num 4;
  2019 and 2023 designs position 117) is stated as ``taxpayer_type.principal_cnae``.
- Each "X o blanco" mark is a stated yes/no: the design writes an X when the
  régimen or circumstance applies and a blank when it does not, so a blank is an
  answer and an unstated mark is refused rather than written as a no.
- The "superior a 6.000.000 euros" mark (2025 position 127, earlier position 125)
  and the turnover band (2025 position 147, earlier position 132: "0" No consta,
  "1" from 10 to 20 M, "2" from 20 to 60 M, "3" from 60 M) both read the
  ``taxpayer_type.incn_prior_12_months`` the designs name: the twelve months
  before the start of the período impositivo.
- The 2019 and 2023 designs fold the cooperativa and several-rates marks into one
  key at position 126: "1" Cooperativa, "2" Otras entidades, "0" No consta.
- The tipo de gravamen (2025 position 132, 15 positions; earlier position 127,
  5 positions) is stated as the operator consigns it.

Only the facts the selected edition's layout cites are asked for, so a fact a
year's design has no position for never blocks that year's export.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from datetime import date
from decimal import Decimal
from typing import Final

from ...core.filing_producer_key import FilingProducerKey
from ...core.parsing.utils import parse_bool
from ...domain.calculations.registry.applicability_modelo202 import (
    modelo_202_incn_threshold_decimal,
    resolve_modelo_202_art_40_3_incn_threshold,
)
from ...domain.deadlines.models import TaxpayerProfile
from ..filing.producer_snapshot import FilingProducerSnapshotError, Modelo202ProducerProfile
from ..operator_actions.preconditions import profile_required_facts_missing_verdict
from ..user_profile.completeness import pinned_registry_scope

_K = FilingProducerKey

PRINCIPAL_CNAE_PATH: Final = "taxpayer_type.principal_cnae"
INCN_PRIOR_12_MONTHS_PATH: Final = "taxpayer_type.incn_prior_12_months"
TIPO_GRAVAMEN_PATH: Final = "taxpayer_type.tipo_gravamen_is"
COOPERATIVA_PATH: Final = "taxpayer_type.cooperativa_fiscalmente_protegida"
MULTIPLES_TIPOS_PATH: Final = "taxpayer_type.multiples_tipos_impositivos"

#: Every "X o blanco" mark the designs cite, with the profile fact that answers it.
MARK_FACT_BY_PRODUCER_KEY: Final[Mapping[FilingProducerKey, str]] = {
    _K.M202_REGIMEN_LEY_49_2002_SIN_FINES_LUCRATIVOS: "taxpayer_type.regimen_ley_49_2002",
    _K.M202_REGIMEN_LEY_11_2009_SOCIMI: "taxpayer_type.regimen_socimi",
    _K.M202_REGIMEN_ENTIDAD_CAPITAL_RIESGO: "taxpayer_type.regimen_entidad_capital_riesgo",
    _K.M202_REGIMEN_ENTIDADES_NAVIERAS_TONELAJE: "taxpayer_type.regimen_entidades_navieras_tonelaje",
    _K.M202_REGIMEN_ARTICULO_101_LIS_REDUCIDA_DIMENSION: "taxpayer_type.erd_tipo_gravamen_especifico",
    _K.M202_COOPERATIVA_FISCALMENTE_PROTEGIDA: COOPERATIVA_PATH,
    _K.M202_MARCA_INSTRUMENTAL: "taxpayer_type.marca_instrumental",
    _K.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL: "taxpayer_type.incn_periodo_anterior_inferior_1m",
    _K.M202_MULTIPLES_TIPOS_IMPOSITIVOS: MULTIPLES_TIPOS_PATH,
}

_MARK_FIELD_BY_PRODUCER_KEY: Final[Mapping[FilingProducerKey, str]] = {
    _K.M202_REGIMEN_LEY_49_2002_SIN_FINES_LUCRATIVOS: "regimen_ley_49_2002_sin_fines_lucrativos",
    _K.M202_REGIMEN_LEY_11_2009_SOCIMI: "regimen_ley_11_2009_socimi",
    _K.M202_REGIMEN_ENTIDAD_CAPITAL_RIESGO: "regimen_entidad_capital_riesgo",
    _K.M202_REGIMEN_ENTIDADES_NAVIERAS_TONELAJE: "regimen_entidades_navieras_tonelaje",
    _K.M202_REGIMEN_ARTICULO_101_LIS_REDUCIDA_DIMENSION: "regimen_articulo_101_lis_reducida_dimension",
    _K.M202_COOPERATIVA_FISCALMENTE_PROTEGIDA: "cooperativa_fiscalmente_protegida",
    _K.M202_MARCA_INSTRUMENTAL: "marca_instrumental",
    _K.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL: "cifra_negocios_periodo_anterior_bajo_umbral",
    _K.M202_MULTIPLES_TIPOS_IMPOSITIVOS: "multiples_tipos_impositivos",
}

_INCN_PRODUCER_KEYS: Final = frozenset(
    {_K.M202_CIFRA_NEGOCIOS_DOCE_MESES_UMBRAL, _K.M202_IMPORTE_NETO_CIFRA_NEGOCIOS_TRAMO},
)

#: Lower bound of each band the designs enumerate, highest first: "3" (>= 60 M),
#: "2" (>= 20 M and < 60 M), "1" (>= 10 M and < 20 M); below the lowest, "0" No consta.
_TURNOVER_BANDS: Final[tuple[tuple[Decimal, str], ...]] = (
    (Decimal(60_000_000), "3"),
    (Decimal(20_000_000), "2"),
    (Decimal(10_000_000), "1"),
)
_TURNOVER_BAND_NONE: Final = "0"

_CNAE_SHAPE: Final = re.compile(r"^\d{4}$")

#: The 2019 and 2023 designs' combined key: "1" Cooperativa, "2" Otras entidades, "0" No consta.
_COMBINED_COOPERATIVA: Final = "1"
_COMBINED_OTRAS_ENTIDADES: Final = "2"
_COMBINED_NO_CONSTA: Final = "0"

#: The served words of the refusal: the export needs a fact which is not stated.
_PRODUCER_FACT_REQUIRED_MESSAGE: Final = "application.filing.export.errors.producer_fact_required"
_REFUSAL_REASON: Final = "m202_profile_facts_missing"


class _Reader:
    """Read stated facts and remember, in order, every one the export needs but the profile lacks."""

    def __init__(self, profile_values: Mapping[str, str]) -> None:
        self._values = profile_values
        self.missing: list[str] = []

    def _absent(self, path: str) -> None:
        if path not in self.missing:
            self.missing.append(path)

    def mark(self, path: str) -> bool | None:
        stated = parse_bool(self._values.get(path))
        if stated is None:
            self._absent(path)
        return stated

    def text(self, path: str, *, shape: re.Pattern[str] | None = None) -> str | None:
        stated = (self._values.get(path) or "").strip()
        if not stated or (shape is not None and not shape.match(stated)):
            self._absent(path)
            return None
        return stated

    def stated(self, path: str, value: Decimal | None) -> Decimal | None:
        if value is None:
            self._absent(path)
        return value


def modelo_202_producer_profile(
    *,
    workflow_profile: TaxpayerProfile,
    profile_values: Mapping[str, str],
    cited_producer_keys: Collection[FilingProducerKey],
    effective_date: date,
) -> Modelo202ProducerProfile:
    """Return the Modelo 202 producer view, or refuse naming every profile fact the layout needs and lacks.

    Args:
        workflow_profile: The taxpayer the export files for; its turnover answers
            the 6.000.000 mark and the band.
        profile_values: The profile facts in force for the period, keyed by path.
        cited_producer_keys: Every producer key the selected edition's layout cites.
        effective_date: The date the threshold fact is resolved for.

    Raises:
        FilingProducerSnapshotError: A cited fact is unstated, or the principal CNAE
            is not four digits; the refusal opens the first such profile fact.
    """
    cited = frozenset(cited_producer_keys)
    reader = _Reader(profile_values)
    # The CNAE leads page 01, so a refusal opens it before the datos adicionales that follow it.
    principal_cnae = (
        reader.text(PRINCIPAL_CNAE_PATH, shape=_CNAE_SHAPE) if _K.M202_CNAE_ACTIVIDAD_PRINCIPAL in cited else None
    )
    marks = {
        _MARK_FIELD_BY_PRODUCER_KEY[key]: reader.mark(path)
        for key, path in MARK_FACT_BY_PRODUCER_KEY.items()
        if key in cited
    }
    combined = _combined_cooperativa_key(reader) if _K.M202_COOPERATIVA_O_MULTIPLES_TIPOS in cited else None
    tipo = reader.text(TIPO_GRAVAMEN_PATH) if _K.M202_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES in cited else None
    incn = (
        reader.stated(INCN_PRIOR_12_MONTHS_PATH, workflow_profile.incn_prior_12_months)
        if cited & _INCN_PRODUCER_KEYS
        else None
    )
    if reader.missing:
        raise _profile_facts_missing(tuple(reader.missing))
    return Modelo202ProducerProfile.model_validate(
        {
            "taxpayer_profile": workflow_profile,
            "activities": (),
            "principal_cnae": principal_cnae,
            "cooperativa_o_multiples_tipos": combined,
            "tipo_gravamen_impuesto_sociedades": tipo,
            **_turnover_marks(incn, cited, effective_date),
            **marks,
        },
    )


def _combined_cooperativa_key(reader: _Reader) -> str | None:
    """The 2019 and 2023 key: a cooperativa fiscalmente protegida is "1", any other several-rates entity "2"."""
    cooperativa = reader.mark(COOPERATIVA_PATH)
    multiples = reader.mark(MULTIPLES_TIPOS_PATH)
    if cooperativa is None or multiples is None:
        return None
    if cooperativa:
        return _COMBINED_COOPERATIVA
    return _COMBINED_OTRAS_ENTIDADES if multiples else _COMBINED_NO_CONSTA


def _turnover_marks(
    incn: Decimal | None, cited: frozenset[FilingProducerKey], effective_date: date
) -> dict[str, object]:
    """The turnover the layout cites as the 6.000.000 mark and as the band, both read from the stated turnover."""
    if incn is None:
        return {}
    marks: dict[str, object] = {}
    if _K.M202_CIFRA_NEGOCIOS_DOCE_MESES_UMBRAL in cited:
        marks["cifra_negocios_doce_meses_umbral"] = _above_art_40_3_threshold(incn, effective_date)
    if _K.M202_IMPORTE_NETO_CIFRA_NEGOCIOS_TRAMO in cited:
        marks["importe_neto_cifra_negocios_tramo"] = _turnover_band(incn)
    return marks


def _above_art_40_3_threshold(incn: Decimal, effective_date: date) -> bool:
    """Whether the turnover is "superior a 6.000.000 euros", against the governed LIS art. 40.3 threshold."""
    with pinned_registry_scope():
        threshold = resolve_modelo_202_art_40_3_incn_threshold(effective_date=effective_date)
    return incn > modelo_202_incn_threshold_decimal(threshold)


def _turnover_band(incn: Decimal) -> str:
    return next((band for lower, band in _TURNOVER_BANDS if incn >= lower), _TURNOVER_BAND_NONE)


def _profile_facts_missing(paths: tuple[str, ...]) -> FilingProducerSnapshotError:
    listed = ", ".join(paths)
    return FilingProducerSnapshotError(
        f"Modelo 202 export needs profile facts that are not stated: {listed}",
        translated_message=_PRODUCER_FACT_REQUIRED_MESSAGE,
        context={
            "fact": listed,
            "missing_profile_paths": listed,
            "profile_path": paths[0],
            "reason": _REFUSAL_REASON,
        },
        precondition_verdict=profile_required_facts_missing_verdict(modelo="202", field_paths=paths),
    )


__all__ = [
    "COOPERATIVA_PATH",
    "INCN_PRIOR_12_MONTHS_PATH",
    "MARK_FACT_BY_PRODUCER_KEY",
    "MULTIPLES_TIPOS_PATH",
    "PRINCIPAL_CNAE_PATH",
    "TIPO_GRAVAMEN_PATH",
    "modelo_202_producer_profile",
]
