"""Resolve the Modelo 202 page 01 entity facts an export cites, or refuse with the door to state them.

Page 01 of every Modelo 202 record design carries the principal CNAE, the
"Datos adicionales" marks, the tipo de gravamen and the turnover band. Each is
a fact about the entity the operator states on the profile, or a value the
design derives from a stated fact:

- The C.N.A.E. de la actividad principal (2025 design position 118, Num 4;
  2019 and 2023 designs position 117) is stated as ``taxpayer_type.principal_cnae``
  together with the classification it is a code of. Nota 12 of the 2025 design
  dates the classification by ejercicio, so the registry serves the one the
  instalment's ejercicio requires and a code stated in any other is refused,
  never converted. Only the four-digit shape is checked: no official code list
  is in the corpus.
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
  5 positions), the "INCN del período impositivo inmediato anterior inferior a 1
  millón" mark (2025 position 130) and the several-rates mark (2025 position 131)
  are law, not choices: they are derived from the governed LIS art. 29 rates the
  stated régimen marks select (see ``export_m202_tipo_gravamen``).
- The immediately preceding período's turnover is read through the canonical
  reader (``incn_periodo_anterior``): the held Modelo 200 of that período, else
  the figure the filer stated for it, else, when that período lasted twelve
  months, the twelve-month turnover the profile states, which is then that
  período's own. A shorter preceding período with neither a held return nor a
  statement is refused rather than exported on another turnover, and a held
  return that disagrees with the stated twelve-month turnover is refused with
  both figures, neither overriding the other. An entity in its first período
  has no preceding one, so the mark stays blank.

Only the facts the selected edition's layout cites are asked for, so a fact a
year's design has no position for never blocks that year's export.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from ...core.filing_producer_key import FilingProducerKey
from ...core.parsing.utils import parse_bool
from ...domain.calculations.registry.applicability_modelo202 import (
    modelo_202_incn_threshold_decimal,
    resolve_modelo_202_art_40_3_incn_threshold,
)
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.cnae_classification import (
    cnae_classification_names,
    required_cnae_classification,
)
from ...domain.deadlines.models import TaxpayerProfile
from ..filing.errors import FilingPreconditionCondition, filing_no_recovery_verdict
from ..filing.producer_snapshot import FilingProducerSnapshotError, Modelo202ProducerProfile
from ..operator_actions.preconditions import profile_required_facts_missing_verdict
from ..user_profile.completeness import pinned_registry_scope
from .export_m202_liquidacion import liquidacion_slots
from .export_m202_tipo_gravamen import (
    RegimenMarks,
    consigned_rates,
    governed_rates,
    several_rates_beyond_own_keys,
    tipo_gravamen_rates,
)
from .export_periodo_impositivo import PeriodoImpositivo
from .incn_periodo_anterior import IncnPeriodoAnterior, IncnPeriodoAnteriorGap, IncnPeriodoAnteriorReader

_K = FilingProducerKey

PRINCIPAL_CNAE_PATH: Final = "taxpayer_type.principal_cnae"
PRINCIPAL_CNAE_CLASSIFICATION_PATH: Final = "taxpayer_type.principal_cnae_classification"
INCN_PRIOR_12_MONTHS_PATH: Final = "taxpayer_type.incn_prior_12_months"
NEW_ENTITY_PATH: Final = "taxpayer_type.new_entity_first_two_profit_periods"
LEY_49_2002_PATH: Final = "taxpayer_type.regimen_ley_49_2002"
SOCIMI_PATH: Final = "taxpayer_type.regimen_socimi"
NAVIERAS_PATH: Final = "taxpayer_type.regimen_entidades_navieras_tonelaje"
ERD_PATH: Final = "taxpayer_type.erd_tipo_gravamen_especifico"
COOPERATIVA_PATH: Final = "taxpayer_type.cooperativa_fiscalmente_protegida"

#: Every stated "X o blanco" mark the designs cite, with the profile fact that answers it.
MARK_FACT_BY_PRODUCER_KEY: Final[Mapping[FilingProducerKey, str]] = {
    _K.M202_REGIMEN_LEY_49_2002_SIN_FINES_LUCRATIVOS: LEY_49_2002_PATH,
    _K.M202_REGIMEN_LEY_11_2009_SOCIMI: SOCIMI_PATH,
    _K.M202_REGIMEN_ENTIDAD_CAPITAL_RIESGO: "taxpayer_type.regimen_entidad_capital_riesgo",
    _K.M202_REGIMEN_ENTIDADES_NAVIERAS_TONELAJE: NAVIERAS_PATH,
    _K.M202_REGIMEN_ARTICULO_101_LIS_REDUCIDA_DIMENSION: ERD_PATH,
    _K.M202_COOPERATIVA_FISCALMENTE_PROTEGIDA: COOPERATIVA_PATH,
    _K.M202_MARCA_INSTRUMENTAL: "taxpayer_type.marca_instrumental",
}

_MARK_FIELD_BY_PRODUCER_KEY: Final[Mapping[FilingProducerKey, str]] = {
    _K.M202_REGIMEN_LEY_49_2002_SIN_FINES_LUCRATIVOS: "regimen_ley_49_2002_sin_fines_lucrativos",
    _K.M202_REGIMEN_LEY_11_2009_SOCIMI: "regimen_ley_11_2009_socimi",
    _K.M202_REGIMEN_ENTIDAD_CAPITAL_RIESGO: "regimen_entidad_capital_riesgo",
    _K.M202_REGIMEN_ENTIDADES_NAVIERAS_TONELAJE: "regimen_entidades_navieras_tonelaje",
    _K.M202_REGIMEN_ARTICULO_101_LIS_REDUCIDA_DIMENSION: "regimen_articulo_101_lis_reducida_dimension",
    _K.M202_COOPERATIVA_FISCALMENTE_PROTEGIDA: "cooperativa_fiscalmente_protegida",
    _K.M202_MARCA_INSTRUMENTAL: "marca_instrumental",
}

#: The slots derived from the governed rates the stated régimen selects.
_RATE_PRODUCER_KEYS: Final = frozenset(
    {
        _K.M202_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES,
        _K.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL,
        _K.M202_MULTIPLES_TIPOS_IMPOSITIVOS,
        _K.M202_COOPERATIVA_O_MULTIPLES_TIPOS,
    },
)

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
#: The served words of the refusal: neither a held return nor a statement gives a shorter preceding período's turnover.
_PRIOR_PERIODO_TURNOVER_MESSAGE: Final = "application.filing.export.errors.m202_prior_periodo_turnover_unreadable"
_PRIOR_PERIODO_TURNOVER_REASON: Final = "m202_prior_periodo_turnover_unreadable"
#: The served words of the refusal: the held return and the stated twelve-month turnover disagree.
_PRIOR_PERIODO_TURNOVER_DISAGREES_MESSAGE: Final = (
    "application.filing.export.errors.m202_prior_periodo_turnover_disagrees"
)
_PRIOR_PERIODO_TURNOVER_DISAGREES_REASON: Final = "m202_prior_periodo_turnover_disagrees"


class _Reader:
    """Read stated facts and remember, in order, every one the export needs but the profile lacks."""

    def __init__(self, profile_values: Mapping[str, str]) -> None:
        self._values = profile_values
        self.missing: list[str] = []
        #: What a missing fact must be stated as, where the path alone does not say it.
        self.qualifiers: dict[str, str] = {}

    def _absent(self, path: str) -> None:
        if path not in self.missing:
            self.missing.append(path)

    def need(self, paths: Collection[str]) -> None:
        """Name facts another resolver found unstated, after those already named."""
        for path in paths:
            self._absent(path)

    def classified_code(self, *, code_path: str, classification_path: str, required: str, name: str) -> str | None:
        """A code stated in the required classification; one stated in another is refused as unstated.

        The classification is named first: the code is only ever a code of the
        classification it is stated in, so that is what the operator states first.
        """
        stated_classification = (self._values.get(classification_path) or "").strip()
        if stated_classification != required:
            self._absent(classification_path)
        code = self.text(code_path, shape=_CNAE_SHAPE)
        if classification_path in self.missing or code_path in self.missing:
            self.qualifiers[classification_path] = name
            self.qualifiers[code_path] = name
            return None
        return code

    def mark(self, path: str) -> bool | None:
        stated = parse_bool(self._values.get(path))
        if stated is None:
            self._absent(path)
        return stated

    def opt_in(self, path: str) -> bool:
        """A yes/no whose unstated value the profile defines as no."""
        return parse_bool(self._values.get(path)) is True

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


@dataclass(frozen=True, slots=True)
class _RateInputs:
    """The stated facts the governed rates are selected by.

    ``prior_incn`` is the immediately preceding período's turnover, ``None``
    when the entity is in its first período and has none.
    """

    marks: RegimenMarks
    prior_incn: Decimal | None


def modelo_202_producer_profile(
    *,
    workflow_profile: TaxpayerProfile,
    profile_values: Mapping[str, str],
    cited_producer_keys: Collection[FilingProducerKey],
    effective_date: date,
    periodo: PeriodoImpositivo,
    filing_year: int,
    art_40_3_elected: bool | None,
    operation: PinnedAuthorityOperation,
    incn_periodo_anterior: IncnPeriodoAnteriorReader,
) -> Modelo202ProducerProfile:
    """Return the Modelo 202 producer view, or refuse naming every profile fact the layout needs and lacks.

    Args:
        workflow_profile: The taxpayer the export files for; its turnover answers
            the 6.000.000 mark and the band.
        profile_values: The profile facts in force for the period, keyed by path.
        cited_producer_keys: Every producer key the selected edition's layout cites.
        effective_date: The date the threshold fact is resolved for.
        periodo: The período impositivo the instalment is on account of; its
            start dates the governed rates and its predecessor the turnover
            that selects the microempresa scale.
        filing_year: The instalment's filing year, whose art. 40.3 threshold
            decides the modality.
        art_40_3_elected: The declaración censal art. 40.3 election in force at
            the start of the período, ``None`` when never stated.
        operation: The pinned authority the governed rates are read from.
        incn_periodo_anterior: The canonical reader of the preceding período's
            turnover for the instalment's ejercicio.

    Raises:
        FilingProducerSnapshotError: A cited fact is unstated, or the principal CNAE
            is not four digits; the refusal opens the first such profile fact.
            A régimen or ejercicio whose rates are not published refuses terminally.
            A preceding período shorter than twelve months whose turnover no
            held return or statement gives refuses, as does a held return that
            disagrees with the stated twelve-month turnover.
    """
    cited = frozenset(cited_producer_keys)
    reader = _Reader(profile_values)
    # The CNAE leads page 01, so a refusal opens it before the datos adicionales that follow it.
    principal_cnae = (
        _principal_cnae(reader, effective_date=effective_date, operation=operation)
        if _K.M202_CNAE_ACTIVIDAD_PRINCIPAL in cited
        else None
    )
    marks = {
        _MARK_FIELD_BY_PRODUCER_KEY[key]: reader.mark(path)
        for key, path in MARK_FACT_BY_PRODUCER_KEY.items()
        if key in cited
    }
    rate_inputs = (
        _read_rate_inputs(
            reader, workflow_profile=workflow_profile, periodo=periodo, incn_periodo_anterior=incn_periodo_anterior
        )
        if cited & _RATE_PRODUCER_KEYS
        else None
    )
    incn = (
        reader.stated(INCN_PRIOR_12_MONTHS_PATH, workflow_profile.incn_prior_12_months)
        if cited & _INCN_PRODUCER_KEYS
        else None
    )
    liquidacion = liquidacion_slots(
        profile_values=profile_values,
        cited=cited,
        filing_year=filing_year,
        art_40_3_elected=art_40_3_elected,
        effective_date=effective_date,
        operation=operation,
    )
    reader.need(liquidacion.missing)
    if reader.missing:
        raise _profile_facts_missing(tuple(reader.missing), reader.qualifiers)
    derived = (
        _derived_rate_fields(rate_inputs, cited, periodo=periodo, operation=operation)
        if rate_inputs is not None
        else {}
    )
    return Modelo202ProducerProfile.model_validate(
        {
            "taxpayer_profile": workflow_profile,
            "activities": (),
            "principal_cnae": principal_cnae,
            **_turnover_marks(incn, cited, effective_date),
            **marks,
            **derived,
            **liquidacion.fields,
        },
    )


def _principal_cnae(reader: _Reader, *, effective_date: date, operation: PinnedAuthorityOperation) -> str | None:
    """The principal C.N.A.E. in the classification the registry requires for the instalment's ejercicio."""
    required = required_cnae_classification(effective_date=effective_date, authority=operation)
    return reader.classified_code(
        code_path=PRINCIPAL_CNAE_PATH,
        classification_path=PRINCIPAL_CNAE_CLASSIFICATION_PATH,
        required=required,
        name=cnae_classification_names(authority=operation)[required],
    )


def _read_rate_inputs(
    reader: _Reader,
    *,
    workflow_profile: TaxpayerProfile,
    periodo: PeriodoImpositivo,
    incn_periodo_anterior: IncnPeriodoAnteriorReader,
) -> _RateInputs | None:
    """Read the régimen marks and the preceding período's turnover, or ``None`` when one is unstated.

    Raises:
        FilingProducerSnapshotError: The preceding período's turnover is neither
            held nor stated and that período lasted less than twelve months, or
            the held return disagrees with the stated twelve-month turnover.
    """
    ley_49_2002 = reader.mark(LEY_49_2002_PATH)
    socimi = reader.mark(SOCIMI_PATH)
    navieras = reader.mark(NAVIERAS_PATH)
    erd = reader.mark(ERD_PATH)
    cooperativa = reader.mark(COOPERATIVA_PATH)
    prior_incn, prior_unstated = _prior_periodo_turnover(
        reader, workflow_profile=workflow_profile, periodo=periodo, incn_periodo_anterior=incn_periodo_anterior
    )
    if ley_49_2002 is None or socimi is None or navieras is None or erd is None or cooperativa is None:
        return None
    if prior_unstated:
        return None
    return _RateInputs(
        marks=RegimenMarks(
            ley_49_2002=ley_49_2002,
            socimi=socimi,
            navieras_tonelaje=navieras,
            # Opt-in by the profile's own definition: unstated leaves the otherwise-applicable rate.
            new_entity_first_two_profit_periods=reader.opt_in(NEW_ENTITY_PATH),
            erd_tipo_especifico=erd,
            cooperativa_protegida=cooperativa,
        ),
        prior_incn=prior_incn,
    )


def _prior_periodo_turnover(
    reader: _Reader,
    *,
    workflow_profile: TaxpayerProfile,
    periodo: PeriodoImpositivo,
    incn_periodo_anterior: IncnPeriodoAnteriorReader,
) -> tuple[Decimal | None, bool]:
    """The preceding período's turnover, and whether an owed one is unstated.

    A first período has none and owes none, and neither does an edition that
    selects no rate by it. A twelve-month preceding período with nothing held
    or stated asks for the profile's twelve-month turnover, its own.

    Raises:
        FilingProducerSnapshotError: As :func:`_read_rate_inputs`.
    """
    if periodo.prior_start is None:
        return None, False
    twelve_months = periodo.prior_lasted_twelve_months
    located = incn_periodo_anterior(workflow_profile.incn_prior_12_months if twelve_months else None)
    if located.resolved:
        return located.value, False
    if located.gap is IncnPeriodoAnteriorGap.NOT_READ_BY_EDITION:
        return None, False
    if located.gap is IncnPeriodoAnteriorGap.TWELVE_MONTH_STATEMENT_DISAGREES:
        raise _prior_periodo_turnover_disagrees(located)
    if twelve_months and located.gap is IncnPeriodoAnteriorGap.NO_RETURN_HELD:
        reader.stated(INCN_PRIOR_12_MONTHS_PATH, None)
        return None, True
    raise _prior_periodo_turnover_unreadable(periodo.prior_start)


def _derived_rate_fields(
    inputs: _RateInputs,
    cited: frozenset[FilingProducerKey],
    *,
    periodo: PeriodoImpositivo,
    operation: PinnedAuthorityOperation,
) -> dict[str, object]:
    """The rate slots, derived from the governed rates of the período the stated régimen selects."""
    rates = governed_rates(periodo_start=periodo.start, operation=operation)
    # LIS art. 29.1 reads the "período impositivo inmediato anterior"; a first período has none to qualify it.
    threshold = rates.microempresa_threshold()
    microempresa = inputs.prior_incn is not None and threshold is not None and inputs.prior_incn < threshold
    applied = tipo_gravamen_rates(marks=inputs.marks, microempresa=microempresa, rates=rates)
    several = several_rates_beyond_own_keys(rates=applied, marks=inputs.marks, microempresa=microempresa)
    fields: dict[str, object] = {}
    if _K.M202_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES in cited:
        fields["tipo_gravamen_impuesto_sociedades"] = consigned_rates(applied)
    if _K.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL in cited:
        fields["cifra_negocios_periodo_anterior_bajo_umbral"] = microempresa
    if _K.M202_MULTIPLES_TIPOS_IMPOSITIVOS in cited:
        fields["multiples_tipos_impositivos"] = several
    if _K.M202_COOPERATIVA_O_MULTIPLES_TIPOS in cited:
        fields["cooperativa_o_multiples_tipos"] = _combined_cooperativa_key(
            cooperativa=inputs.marks.cooperativa_protegida, several_rates=several
        )
    return fields


def _combined_cooperativa_key(*, cooperativa: bool, several_rates: bool) -> str:
    """The 2019 and 2023 key: a cooperativa fiscalmente protegida is "1", any other several-rates entity "2"."""
    if cooperativa:
        return _COMBINED_COOPERATIVA
    return _COMBINED_OTRAS_ENTIDADES if several_rates else _COMBINED_NO_CONSTA


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


def _prior_periodo_turnover_unreadable(prior_start: date) -> FilingProducerSnapshotError:
    """Refuse an instalment whose preceding período's turnover neither a held return nor a statement gives.

    LIS art. 29.1 reads the turnover of the "período impositivo inmediato
    anterior"; when that período lasted less than twelve months it is not the
    twelve-month turnover the profile states but the one that período's
    Modelo 200 declares. It is given by holding that return or by stating its
    figure on the ejercicio's Modelo 200; no profile fact replaces it, so the
    refusal opens no profile door.
    """
    return FilingProducerSnapshotError(
        f"the Modelo 202 rates read the turnover of the shorter período starting {prior_start.isoformat()}",
        translated_message=_PRIOR_PERIODO_TURNOVER_MESSAGE,
        context={"reason": _PRIOR_PERIODO_TURNOVER_REASON},
        precondition_verdict=filing_no_recovery_verdict(
            FilingPreconditionCondition.OPERATION_ADMISSIBLE,
            facts={"reason": _PRIOR_PERIODO_TURNOVER_REASON},
        ),
    )


def _prior_periodo_turnover_disagrees(located: IncnPeriodoAnterior) -> FilingProducerSnapshotError:
    """Refuse an instalment whose held preceding return and stated twelve-month turnover disagree.

    For a twelve-month preceding período both are that período's own turnover,
    so they must agree; neither is taken over the other, and the filer corrects
    the one that is wrong.
    """
    held = located.held_value
    stated = located.twelve_month_statement
    return FilingProducerSnapshotError(
        f"the held Modelo 200 turnover {held} and the stated twelve-month turnover {stated} disagree",
        translated_message=_PRIOR_PERIODO_TURNOVER_DISAGREES_MESSAGE,
        context={
            "reason": _PRIOR_PERIODO_TURNOVER_DISAGREES_REASON,
            "held_value": str(held),
            "stated_value": str(stated),
            "profile_path": INCN_PRIOR_12_MONTHS_PATH,
        },
        precondition_verdict=filing_no_recovery_verdict(
            FilingPreconditionCondition.OPERATION_ADMISSIBLE,
            facts={"reason": _PRIOR_PERIODO_TURNOVER_DISAGREES_REASON},
        ),
    )


def _profile_facts_missing(paths: tuple[str, ...], qualifiers: Mapping[str, str]) -> FilingProducerSnapshotError:
    listed = ", ".join(paths)
    named = ", ".join(f"{path} ({qualifiers[path]})" if path in qualifiers else path for path in paths)
    return FilingProducerSnapshotError(
        f"Modelo 202 export needs profile facts that are not stated: {named}",
        translated_message=_PRODUCER_FACT_REQUIRED_MESSAGE,
        context={
            "fact": named,
            "missing_profile_paths": listed,
            "profile_path": paths[0],
            "reason": _REFUSAL_REASON,
            **({"required_cnae_classification": next(iter(qualifiers.values()))} if qualifiers else {}),
        },
        precondition_verdict=profile_required_facts_missing_verdict(modelo="202", field_paths=paths),
    )


__all__ = [
    "COOPERATIVA_PATH",
    "INCN_PRIOR_12_MONTHS_PATH",
    "MARK_FACT_BY_PRODUCER_KEY",
    "NEW_ENTITY_PATH",
    "PRINCIPAL_CNAE_CLASSIFICATION_PATH",
    "PRINCIPAL_CNAE_PATH",
    "modelo_202_producer_profile",
]
