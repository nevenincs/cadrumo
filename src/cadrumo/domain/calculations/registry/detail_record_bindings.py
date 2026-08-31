"""Detail-record row-set registry binding helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_validator

from ....core.modelo_232_codigos import MetodoValoracion, TipoOperacionVinculada
from ....core.foreign_asset_obligation import M720AssetClassCode
from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.country_code import CountryCodeAlpha2
from ....core.external_constants import DEFAULT_CURRENCY
from ....core.identity import TaxIdIdentityToken
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import (
    BindingExportDataType,
    invariant_diagnostics,
    optional_uppercase_alpha_code,
    selector_against_model,
    uppercase_alpha_code,
)
from .binding_selector_utils import selector_as_dict as _selector_as_dict
from .errors import RegistryValidationError
from .ids import BindingId
from .schema import DataBindingDefinition, ModeloRevision

__all__ = [
    "AtributionMemberObservation",
    "Modelo720RowObservation",
    "RefundOperationObservation",
    "RelatedPartyOperationObservation",
    "foreign_asset_binding_row_field",
    "resolve_atribucion_binding_row_values",
    "resolve_foreign_asset_binding_row_values",
    "resolve_refund_binding_row_values",
    "resolve_related_party_binding_row_values",
    "validate_atribucion_binding",
    "validate_foreign_asset_binding",
    "validate_refund_binding",
    "validate_related_party_binding",
]


def _validate_detail_record_row_field(
    binding: DataBindingDefinition,
    selector_fact: object,
    selector_row_field: object,
    family_label: str,
) -> None:
    """Shared op/fact invariant for the four detail-record families.

    Every detail-record family declares exactly the ``row_field`` fact, defaults
    to (and requires) the ``rows`` aggregation op, and must name a ``row_field``
    selector key. The four families enforced this with byte-identical bodies; the
    one shared check raises a family-labelled :class:`RegistryValidationError`.
    """
    if selector_fact != "row_field":
        raise RegistryValidationError(
            f"binding {binding.id!r} declares unsupported {family_label} fact {selector_fact!r}",
        )
    if binding_aggregation_op(binding) != BindingAggregationOp.ROWS:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
    if selector_row_field is None:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key")


# Related-party operation source bindings (modelo 232).
#
# Legal authority: LIS art. 18 (operaciones vinculadas), RD 634/2015
# art. 13 (informe-país-por-país y declaración modelo 232), Orden
# HFP/816/2017 Anexo (diseno de registro modelo 232).
# ---------------------------------------------------------------------------


_RelatedPartyRowField = Literal[
    "counterparty_tax_id",
    "counterparty_legal_name",
    "country_code",
    "operation_kind_code",
    "transfer_pricing_method_code",
    "amount",
]


def _hydrate_operation_kind_code(value: object) -> object:
    """Hydrate a resolved binding value into its typed ``TipoOperacionVinculada`` member.

    Binding values arrive from the registry as free-form text, so this is the
    boundary that turns a token into a member. It is the same code set the
    operator-supplied CLI row carries, which is why both read it from ``core``
    rather than either side re-spelling the table.
    """
    if not isinstance(value, str):
        return value
    try:
        return TipoOperacionVinculada(value.upper())
    except ValueError:
        accepted = ", ".join(repr(str(member)) for member in TipoOperacionVinculada)
        raise ValueError(f"operation_kind_code must be one of {accepted}; got {value!r}") from None


def _hydrate_transfer_pricing_method_code(value: object) -> object:
    """Hydrate a resolved binding value into its typed ``MetodoValoracion`` member."""
    if not isinstance(value, str):
        return value
    try:
        return MetodoValoracion(value.upper())
    except ValueError:
        accepted = ", ".join(repr(str(member)) for member in MetodoValoracion)
        raise ValueError(f"transfer_pricing_method_code must be one of {accepted}; got {value!r}") from None


class RelatedPartyOperationObservation(BaseModel):
    """One related-party operation for modelo 232."""

    model_config = STRICT_FROZEN_CONFIG

    source_id: str = Field(min_length=1, max_length=128)
    counterparty_tax_id: TaxIdIdentityToken
    counterparty_legal_name: str = Field(default="", max_length=200)
    # Required, and deliberately not defaulted to Spain. Modelo 232 declares
    # operations with países o territorios calificados como paraísos fiscales
    # alongside operaciones vinculadas, so the country is the axis the
    # declaration exists to surface -- a default marks a tax-haven counterparty
    # as domestic on exactly that axis. The operator-supplied row carrying the
    # same operation is required for the same reason; this is the registry-side
    # representation of it, and the two must agree.
    country_code: CountryCodeAlpha2
    transaction_date: date
    operation_kind_code: Annotated[TipoOperacionVinculada, BeforeValidator(_hydrate_operation_kind_code)]
    transfer_pricing_method_code: Annotated[
        MetodoValoracion,
        BeforeValidator(_hydrate_transfer_pricing_method_code),
    ] = MetodoValoracion.NO_DECLARADO
    amount: Decimal

    _country_code_uppercase = field_validator("country_code")(uppercase_alpha_code("country_code"))

    @field_validator("amount")
    @classmethod
    def _decimal_amount(cls, value: Decimal) -> Decimal:
        return value


class _RelatedPartySelector(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    # Only ``row_field`` is a legal fact for related-party-operation
    # bindings; every handler raises on anything else. Promoting to a
    # Literal at the type level mirrors the runtime check at the
    # snapshot-build gate. Audit selector-drift F2.
    fact: Literal["row_field"]
    row_field: _RelatedPartyRowField | None = None
    grouping: str | None = Field(default=None, min_length=1, max_length=64)
    record: str | None = Field(default=None, min_length=1, max_length=64)
    data_type: BindingExportDataType | None = None
    """Scalar type of the value this row field contributes to the export.

    The same fact ``BindingRowExportSelector.data_type`` carries; declared here
    so the selector model admits the key, since a source-family selector is
    validated whole against its own strict model. Optional while the families
    adopt it.
    """


def _validated_related_party_selector(binding: DataBindingDefinition) -> _RelatedPartySelector:
    try:
        selector = _RelatedPartySelector.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed related-party selector") from exc
    _validate_detail_record_row_field(binding, selector.fact, selector.row_field, "related-party")
    return selector


def validate_related_party_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a related-party-operation binding at registry-build time.

    Accumulating ``list[str]`` validator: validates the selector shape against
    :class:`_RelatedPartySelector` and lifts the resolve-time op/fact invariant
    (``row_field`` fact paired with the ``rows`` op and a named ``row_field``)
    to build time, preserving the underlying pydantic field error.
    """
    failures = selector_against_model(binding, _RelatedPartySelector)
    if failures:
        return failures
    return invariant_diagnostics(binding, "related-party", lambda b: _validated_related_party_selector(b))


def resolve_related_party_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[RelatedPartyOperationObservation],
) -> dict[tuple[BindingId, int], Decimal | str]:
    """Resolve row-producer related-party bindings into per-row indexed values.

    Args:
        revision: The :class:`ModeloRevision` whose related-party bindings to resolve.
        observations: Typed :class:`RelatedPartyOperationObservation` rows the
            row-producer bindings group into per-row indexed values.
    """
    available = tuple(observations)
    members: list[tuple[DataBindingDefinition, _RelatedPartySelector]] = []
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.RELATED_PARTY_OPERATION:
            continue
        selector = _validated_related_party_selector(binding)
        members.append((binding, selector))
    if not members:
        return {}
    rows = _build_related_party_rows(available)
    resolved: dict[tuple[BindingId, int], Decimal | str] = {}
    for binding, selector in members:
        assert selector.row_field is not None
        for row_index, row in enumerate(rows, start=1):
            value = row.get(selector.row_field)
            if value is None:
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} not produced for related-party rows",
                )
            resolved[(binding.id, row_index)] = value
    return resolved


def _build_related_party_rows(
    observations: tuple[RelatedPartyOperationObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    """Group related-party observations by (party, country, kind, method) summing amounts."""
    accum: dict[tuple[str, str, str, str], dict[str, Decimal | str]] = {}
    for obs in observations:
        key = (obs.country_code, obs.counterparty_tax_id, obs.operation_kind_code, obs.transfer_pricing_method_code)
        bucket = accum.setdefault(
            key,
            {
                "country_code": obs.country_code,
                "counterparty_tax_id": obs.counterparty_tax_id,
                "counterparty_legal_name": obs.counterparty_legal_name,
                "operation_kind_code": obs.operation_kind_code,
                "transfer_pricing_method_code": obs.transfer_pricing_method_code,
                "amount": Decimal("0"),
            },
        )
        prev = bucket["amount"]
        assert isinstance(prev, Decimal)
        bucket["amount"] = prev + obs.amount
    return tuple(accum[key] for key in sorted(accum.keys()))


# ---------------------------------------------------------------------------
# Foreign asset source bindings (modelo 720).
#
# Legal authority: RD 1065/2007 arts. 42 bis / 42 ter, Orden HAP/72/2013
# Anexo (modelo 720 diseno de registro). Threshold: 50,000 EUR per regulatory
# obligation block (already encoded as a parameter on modelo 720).
# ---------------------------------------------------------------------------


_ForeignAssetRowField = Literal[
    "asset_class_code",
    "country_code",
    "currency_code",
    "asset_identifier",
    "valuation_amount",
    "acquisition_date",
]


class Modelo720RowObservation(BaseModel):
    """One foreign asset for modelo 720."""

    model_config = STRICT_FROZEN_CONFIG

    source_id: str = Field(min_length=1, max_length=128)
    asset_class_code: M720AssetClassCode
    country_code: CountryCodeAlpha2
    currency_code: str = Field(default=DEFAULT_CURRENCY, min_length=3, max_length=3)
    asset_identifier: str = Field(default="", max_length=128)
    acquisition_date: date
    valuation_amount: Decimal

    _iso_code_uppercase = field_validator("country_code", "currency_code")(uppercase_alpha_code("ISO code"))

    @field_validator("valuation_amount")
    @classmethod
    def _decimal_amount(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise RegistryValidationError("foreign asset valuation must be non-negative")
        return value


class _ForeignAssetSelector(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    fact: Literal["row_field"]
    row_field: _ForeignAssetRowField | None = None
    asset_classes: tuple[str, ...] = ()
    grouping: str | None = Field(default=None, min_length=1, max_length=64)
    record: str | None = Field(default=None, min_length=1, max_length=64)
    data_type: BindingExportDataType | None = None
    """Scalar type of the value this row field contributes to the export.

    The same fact ``BindingRowExportSelector.data_type`` carries; declared here
    so the selector model admits the key, since a source-family selector is
    validated whole against its own strict model. Optional while the families
    adopt it.
    """


def _validated_foreign_asset_selector(binding: DataBindingDefinition) -> _ForeignAssetSelector:
    try:
        selector = _ForeignAssetSelector.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed foreign-asset selector") from exc
    _validate_detail_record_row_field(binding, selector.fact, selector.row_field, "foreign-asset")
    return selector


def foreign_asset_binding_row_field(binding: DataBindingDefinition) -> str | None:
    """Return the ``row_field`` a ``foreign_asset`` binding declares, or ``None``.

    Reads through the typed :func:`_validated_foreign_asset_selector` rather
    than a raw ``selector_as_dict(binding).get("row_field")``. Every
    ``foreign_asset`` binding is row-field-shaped by construction (its
    selector's ``fact`` accepts only the ``"row_field"`` literal, and build
    validation refuses a ``row_field``-less selector under that fact), so
    ``row_field`` is never legitimately absent from a valid foreign-asset
    binding -- a raw ``.get()`` returning ``None`` there could ONLY mean a
    RENAMED field, which would silently, permanently make every foreign-asset
    row-field binding unmatchable by any caller searching for a specific
    field, with no error at all.

    Returns ``None`` for a binding that is not ``foreign_asset`` at all -- a
    real, different fact from a drifted selector on one that is.
    """
    if binding.source is not BindingSourceKind.FOREIGN_ASSET:
        return None
    return _validated_foreign_asset_selector(binding).row_field


def validate_foreign_asset_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a foreign-asset binding at registry-build time.

    Accumulating ``list[str]`` validator: validates the selector against
    :class:`_ForeignAssetSelector` and lifts the resolve-time op/fact invariant
    to build time, preserving the underlying pydantic field error.
    """
    failures = selector_against_model(binding, _ForeignAssetSelector)
    if failures:
        return failures
    return invariant_diagnostics(binding, "foreign-asset", lambda b: _validated_foreign_asset_selector(b))


def resolve_foreign_asset_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[Modelo720RowObservation],
) -> dict[tuple[BindingId, int], Decimal | str]:
    """Resolve row-producer foreign-asset bindings into per-row indexed values.

    Args:
        revision: The :class:`ModeloRevision` whose foreign-asset bindings are resolved.
        observations: Modelo 720 row observations to group into rows.
    """
    available = tuple(observations)
    members: list[tuple[DataBindingDefinition, _ForeignAssetSelector]] = []
    cohort_classes: set[tuple[str, ...]] = set()
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.FOREIGN_ASSET:
            continue
        selector = _validated_foreign_asset_selector(binding)
        members.append((binding, selector))
        cohort_classes.add(tuple(sorted(selector.asset_classes)))
    if not members:
        return {}
    # All bindings in a cohort share the same asset_classes filter.
    sample_classes = next(iter(cohort_classes)) if cohort_classes else ()
    class_filter = set(sample_classes)
    filtered = tuple(obs for obs in available if not class_filter or obs.asset_class_code in class_filter)
    rows = _build_foreign_asset_rows(filtered)
    resolved: dict[tuple[BindingId, int], Decimal | str] = {}
    for binding, selector in members:
        assert selector.row_field is not None
        for row_index, row in enumerate(rows, start=1):
            value = row.get(selector.row_field)
            if value is None:
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} not produced for foreign-asset rows",
                )
            resolved[(binding.id, row_index)] = value
    return resolved


def _build_foreign_asset_rows(
    observations: tuple[Modelo720RowObservation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    rows: list[Mapping[str, Decimal | str]] = []
    for obs in sorted(
        observations,
        key=lambda o: (o.country_code, o.asset_class_code, o.asset_identifier, o.acquisition_date.isoformat()),
    ):
        rows.append(
            {
                "asset_class_code": obs.asset_class_code,
                "country_code": obs.country_code,
                "currency_code": obs.currency_code,
                "asset_identifier": obs.asset_identifier,
                "valuation_amount": obs.valuation_amount,
                "acquisition_date": obs.acquisition_date.isoformat(),
            },
        )
    return tuple(rows)


# ---------------------------------------------------------------------------
# Atribución member source bindings (modelo 184).
#
# Legal authority: Ley 35/2006 LIRPF arts. 87-90 (régimen de atribución de
# rentas), Orden HFP/227/2017 Anexo (modelo 184 diseno de registro).
# ---------------------------------------------------------------------------


_AtributionRowField = Literal[
    "member_tax_id",
    "member_legal_name",
    "country_code",
    "share_percentage",
    "base_imponible_assigned",
    "clave",
    "subclave",
    "codigo_provincia",
    "miembro_a_31_diciembre",
    "dias_miembro",
    "domicilio_fiscal",
    "naturaleza_inmueble",
    "situacion_inmueble",
    "referencia_catastral",
    "clave_declarado",
    "porcentaje_titularidad_inmueble",
    "dias_arrendamiento",
    "reduccion",
    "rendimiento_neto_previo_eo",
    "rendimiento_neto_minorado_agricola_eo",
]


class AtributionMemberObservation(BaseModel):
    """One (member, clave, subclave) atribución row for modelo 184.

    Every field below ``base_imponible_assigned`` is the (member, clave,
    subclave) row-shape ADR's clave/subclave-conditional fact set, and is
    ``None`` whenever the declaring clave does not license it -- e.g.
    ``naturaleza_inmueble`` is only ever populated for a clave-C row. A
    ``None`` here is a legitimate "this field does not apply to this row",
    never a missing value.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_id: str = Field(min_length=1, max_length=128)
    member_tax_id: TaxIdIdentityToken
    member_legal_name: str = Field(default="", max_length=200)
    country_code: CountryCodeAlpha2 | None = None
    """The party's country, or ``None`` when the source stated none.

    Nullable rather than defaulted to ``ES``, because these forms carry the
    NON-RESIDENT population by construction -- a perceptor on a withholding
    form is routinely foreign, and an attribution member can be -- so a
    default silently declares a foreign party Spanish on a filing surface.

    Absence propagates as an ABSENT KEY in the built row rather than as a
    value, so a binding that needs the country refuses with the shipped
    not-produced error naming itself. That is the visible failure the silent
    default replaced."""
    transaction_date: date
    share_percentage: Decimal
    base_imponible_assigned: Decimal

    clave: str = Field(min_length=1, max_length=1)
    subclave: str | None = Field(default=None, min_length=2, max_length=2)
    codigo_provincia: str | None = Field(default=None, min_length=2, max_length=2)
    miembro_a_31_diciembre: str | None = Field(default=None, min_length=1, max_length=1)
    """``"X"`` when the member remained one at 31 December, else ``None``.

    A string flag rather than a bool: the diseño's own field (position 82)
    is text, marked ``"X"`` or left blank -- never a boolean literal -- and
    this is the shape the fixed-width renderer's ``data_type = "text"``
    field expects.
    """
    dias_miembro: int | None = None
    domicilio_fiscal: str | None = Field(default=None, max_length=40)
    naturaleza_inmueble: str | None = Field(default=None, min_length=1, max_length=1)
    situacion_inmueble: str | None = Field(default=None, min_length=1, max_length=1)
    referencia_catastral: str | None = Field(default=None, max_length=20)
    clave_declarado: str | None = Field(default=None, min_length=1, max_length=1)
    porcentaje_titularidad_inmueble: Decimal | None = None
    dias_arrendamiento: int | None = None
    reduccion: Decimal | None = None
    rendimiento_neto_previo_eo: Decimal | None = None
    rendimiento_neto_minorado_agricola_eo: Decimal | None = None

    _country_code_uppercase = field_validator("country_code")(optional_uppercase_alpha_code("country_code"))

    @field_validator("share_percentage")
    @classmethod
    def _share_within_bounds(cls, value: Decimal) -> Decimal:
        if value < Decimal("0") or value > Decimal("100"):
            raise RegistryValidationError("share_percentage must be within [0, 100]")
        return value

    @field_validator("base_imponible_assigned")
    @classmethod
    def _decimal_amount(cls, value: Decimal) -> Decimal:
        return value


class _AtributionSelector(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    fact: Literal["row_field"]
    row_field: _AtributionRowField | None = None
    grouping: str | None = Field(default=None, min_length=1, max_length=64)
    record: str | None = Field(default=None, min_length=1, max_length=64)
    data_type: BindingExportDataType | None = None
    """Scalar type of the value this row field contributes to the export.

    The same fact ``BindingRowExportSelector.data_type`` carries; declared here
    so the selector model admits the key, since a source-family selector is
    validated whole against its own strict model. Optional while the families
    adopt it.
    """


def _validated_atribucion_selector(binding: DataBindingDefinition) -> _AtributionSelector:
    try:
        selector = _AtributionSelector.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed atribucion selector") from exc
    _validate_detail_record_row_field(binding, selector.fact, selector.row_field, "atribucion")
    return selector


def validate_atribucion_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate an atribución-member binding at registry-build time.

    Accumulating ``list[str]`` validator: validates the selector against
    :class:`_AtributionSelector` and lifts the resolve-time op/fact invariant to
    build time, preserving the underlying pydantic field error.
    """
    failures = selector_against_model(binding, _AtributionSelector)
    if failures:
        return failures
    return invariant_diagnostics(binding, "atribucion", lambda b: _validated_atribucion_selector(b))


def resolve_atribucion_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[AtributionMemberObservation],
) -> dict[tuple[BindingId, int], Decimal | str | int | bool]:
    """Resolve row-producer atribucion bindings into per-row indexed values.

    Args:
        revision: The :class:`ModeloRevision` whose atribucion bindings are resolved.
        observations: Attribution member observations to group into rows.
    """
    available = tuple(observations)
    members: list[tuple[DataBindingDefinition, _AtributionSelector]] = []
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.ATRIBUCION_MEMBER:
            continue
        selector = _validated_atribucion_selector(binding)
        members.append((binding, selector))
    if not members:
        return {}
    rows = tuple(
        {
            "member_tax_id": obs.member_tax_id,
            "member_legal_name": obs.member_legal_name,
            "country_code": obs.country_code,
            "share_percentage": obs.share_percentage,
            "base_imponible_assigned": obs.base_imponible_assigned,
            "clave": obs.clave,
            "subclave": obs.subclave,
            "codigo_provincia": obs.codigo_provincia,
            "miembro_a_31_diciembre": obs.miembro_a_31_diciembre,
            "dias_miembro": obs.dias_miembro,
            "domicilio_fiscal": obs.domicilio_fiscal,
            "naturaleza_inmueble": obs.naturaleza_inmueble,
            "situacion_inmueble": obs.situacion_inmueble,
            "referencia_catastral": obs.referencia_catastral,
            "clave_declarado": obs.clave_declarado,
            "porcentaje_titularidad_inmueble": obs.porcentaje_titularidad_inmueble,
            "dias_arrendamiento": obs.dias_arrendamiento,
            "reduccion": obs.reduccion,
            "rendimiento_neto_previo_eo": obs.rendimiento_neto_previo_eo,
            "rendimiento_neto_minorado_agricola_eo": obs.rendimiento_neto_minorado_agricola_eo,
        }
        for obs in sorted(available, key=lambda o: (o.country_code, o.member_tax_id))
    )
    resolved: dict[tuple[BindingId, int], Decimal | str | int | bool] = {}
    for binding, selector in members:
        assert selector.row_field is not None
        for row_index, row in enumerate(rows, start=1):
            if selector.row_field not in row:
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} not produced for atribucion rows",
                )
            value = row[selector.row_field]
            # A clave/subclave-conditional field is legitimately absent for a
            # row whose declared clave does not license it (e.g.
            # naturaleza_inmueble on a clave-D row) -- not a "not produced"
            # authoring defect, so it is skipped rather than refused.
            if value is None:
                continue
            resolved[(binding.id, row_index)] = value
    return resolved


# ---------------------------------------------------------------------------
# Refund operation source bindings (modelo 360).
#
# Legal authority: Ley 37/1992 art. 117 bis (devolucion 8a Directiva),
# Orden EHA/789/2010 Anexo (modelo 360 diseno de registro).
# ---------------------------------------------------------------------------


_RefundRowField = Literal[
    "member_state_code",
    "operation_kind_code",
    "operation_date",
    "supplier_tax_id",
    "refund_amount",
]


class RefundOperationObservation(BaseModel):
    """One foreign-MS refund operation for modelo 360."""

    model_config = STRICT_FROZEN_CONFIG

    source_id: str = Field(min_length=1, max_length=128)
    member_state_code: CountryCodeAlpha2
    operation_kind_code: str = Field(min_length=1, max_length=4)
    operation_date: date
    supplier_tax_id: TaxIdIdentityToken
    refund_amount: Decimal

    _iso_code_uppercase = field_validator("member_state_code")(uppercase_alpha_code("member_state_code"))

    @field_validator("refund_amount")
    @classmethod
    def _decimal_amount(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise RegistryValidationError("refund_amount must be non-negative")
        return value


class _RefundSelector(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    fact: Literal["row_field"]
    row_field: _RefundRowField | None = None
    grouping: str | None = Field(default=None, min_length=1, max_length=64)
    record: str | None = Field(default=None, min_length=1, max_length=64)
    data_type: BindingExportDataType | None = None
    """Scalar type of the value this row field contributes to the export.

    The same fact ``BindingRowExportSelector.data_type`` carries; declared here
    so the selector model admits the key, since a source-family selector is
    validated whole against its own strict model. Optional while the families
    adopt it.
    """


AtributionSelector = _AtributionSelector
ForeignAssetSelector = _ForeignAssetSelector
RefundSelector = _RefundSelector
RelatedPartySelector = _RelatedPartySelector
build_foreign_asset_rows = _build_foreign_asset_rows
build_related_party_rows = _build_related_party_rows


def _validated_refund_selector(binding: DataBindingDefinition) -> _RefundSelector:
    try:
        selector = _RefundSelector.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed refund selector") from exc
    _validate_detail_record_row_field(binding, selector.fact, selector.row_field, "refund")
    return selector


def validate_refund_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a refund-operation binding at registry-build time.

    Accumulating ``list[str]`` validator: validates the selector against
    :class:`_RefundSelector` and lifts the resolve-time op/fact invariant to
    build time, preserving the underlying pydantic field error.
    """
    failures = selector_against_model(binding, _RefundSelector)
    if failures:
        return failures
    return invariant_diagnostics(binding, "refund", lambda b: _validated_refund_selector(b))


def resolve_refund_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[RefundOperationObservation],
) -> dict[tuple[BindingId, int], Decimal | str]:
    """Resolve row-producer refund-operation bindings into per-row indexed values.

    Args:
        revision: The :class:`ModeloRevision` whose refund bindings are resolved.
        observations: Refund operation observations to group into rows.
    """
    available = tuple(observations)
    members: list[tuple[DataBindingDefinition, _RefundSelector]] = []
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.REFUND_OPERATION:
            continue
        selector = _validated_refund_selector(binding)
        members.append((binding, selector))
    if not members:
        return {}
    rows = tuple(
        {
            "member_state_code": obs.member_state_code,
            "operation_kind_code": obs.operation_kind_code,
            "operation_date": obs.operation_date.isoformat(),
            "supplier_tax_id": obs.supplier_tax_id,
            "refund_amount": obs.refund_amount,
        }
        for obs in sorted(
            available,
            key=lambda o: (o.member_state_code, o.operation_date.isoformat(), o.supplier_tax_id),
        )
    )
    resolved: dict[tuple[BindingId, int], Decimal | str] = {}
    for binding, selector in members:
        assert selector.row_field is not None
        for row_index, row in enumerate(rows, start=1):
            value = row.get(selector.row_field)
            if value is None:
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} not produced for refund rows",
                )
            resolved[(binding.id, row_index)] = value
    return resolved
