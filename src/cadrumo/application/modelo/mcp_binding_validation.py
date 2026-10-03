"""Pinned binding validation for the MCP modelo query surface."""

from __future__ import annotations

from datetime import date

from pydantic import ValidationError

from ...core.aggregation import BindingTypedEnumKind
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_selector_utils import boolean_binding_encoded_values
from ...domain.calculations.registry.binding_targets import revision_bindings_by_id
from ...domain.calculations.registry.binding_value_contract import BindingValueChannel
from ...domain.calculations.registry.ccaa_catalogue import resolve_ccaa_catalogue
from ...domain.calculations.registry.censo_modelos import CensoModeloEventKind
from ...domain.calculations.registry.entity_type import resolve_entity_vocabulary
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry.rental_reduction import resolve_rental_reduction_art232_tier_catalogue
from ...domain.calculations.registry.schema import BindingDefinition, RegistrySnapshot
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .mcp_binding_channel_validation import validate_binding_channel_value
from .mcp_query_contracts import (
    MAX_TYPED_BINDING_VALUE_LENGTH,
    ModeloBindingsResolveTypedProjection,
    ModeloBindingValueContractUnsupportedError,
    ModeloBindingValueInvalidError,
    ModeloTypedBindingValue,
)
from .query_read_operation import (
    ModeloBindingOverride,
    ModeloBindingsResolveProjection,
    ModeloBindingsResolveRequest,
    read_modelo_bindings_resolve,
)


def _bound_targets(snapshot: RegistrySnapshot, binding_id: str) -> tuple[CasillaDefinition, ...]:
    return tuple(
        row for row in snapshot.revision.casillas if row.binding == binding_id or binding_id in row.alternate_bindings
    )


def _validate_typed_enum(
    binding: BindingDefinition,
    raw: str,
    *,
    operation: PinnedAuthorityOperation,
    effective_date: date | None,
) -> None:
    kind = binding.value.typed_enum
    if kind is None:
        if binding.value.channel is BindingValueChannel.ENUM:
            raise ModeloBindingValueContractUnsupportedError()
        return
    try:
        _validate_enum_kind(binding, kind, raw, operation=operation, effective_date=effective_date)
    except RegistrySnapshotError:
        raise ModeloBindingValueContractUnsupportedError() from None
    except (RegistryValidationError, ValueError):
        raise ModeloBindingValueInvalidError() from None


def _validate_enum_kind(
    binding: BindingDefinition,
    kind: BindingTypedEnumKind,
    raw: str,
    *,
    operation: PinnedAuthorityOperation,
    effective_date: date | None,
) -> None:
    if kind is BindingTypedEnumKind.CENSO_EVENT_KIND:
        _require_enum_channel(binding)
        CensoModeloEventKind(raw)
    elif kind is BindingTypedEnumKind.CCAA:
        _validate_ccaa_enum(binding, raw, operation=operation, effective_date=effective_date)
    elif kind is BindingTypedEnumKind.LEGAL_ENTITY_FORM:
        _validate_legal_entity_form_enum(binding, raw, operation=operation, effective_date=effective_date)
    elif kind is BindingTypedEnumKind.RENTAL_REDUCTION_ART_23_2_TIER:
        _validate_rental_reduction_enum(binding, raw, operation=operation, effective_date=effective_date)
    elif kind is BindingTypedEnumKind.ESTIMACION_DIRECTA_MODALIDAD:
        _validate_estimation_modality_enum(binding, raw)
    else:
        raise ModeloBindingValueContractUnsupportedError()


def _require_enum_channel(binding: BindingDefinition) -> None:
    if binding.value.channel is not BindingValueChannel.ENUM:
        raise ModeloBindingValueContractUnsupportedError()


def _require_enum_date(binding: BindingDefinition, effective_date: date | None) -> date:
    _require_enum_channel(binding)
    if effective_date is None:
        raise ModeloBindingValueContractUnsupportedError()
    return effective_date


def _validate_ccaa_enum(
    binding: BindingDefinition,
    raw: str,
    *,
    operation: PinnedAuthorityOperation,
    effective_date: date | None,
) -> None:
    selected_date = _require_enum_date(binding, effective_date)
    try:
        catalogue = resolve_ccaa_catalogue(effective_date=selected_date, authority=operation)
    except (RegistrySnapshotError, RegistryValidationError):
        raise ModeloBindingValueContractUnsupportedError() from None
    if str(catalogue.require(raw)) != raw:
        raise ModeloBindingValueInvalidError()


def _validate_legal_entity_form_enum(
    binding: BindingDefinition,
    raw: str,
    *,
    operation: PinnedAuthorityOperation,
    effective_date: date | None,
) -> None:
    selected_date = _require_enum_date(binding, effective_date)
    try:
        vocabulary = resolve_entity_vocabulary(effective_date=selected_date, authority=operation)
    except (RegistrySnapshotError, RegistryValidationError):
        raise ModeloBindingValueContractUnsupportedError() from None
    if str(vocabulary.require_legal_entity_form(raw)) != raw:
        raise ModeloBindingValueInvalidError()


def _validate_rental_reduction_enum(
    binding: BindingDefinition,
    raw: str,
    *,
    operation: PinnedAuthorityOperation,
    effective_date: date | None,
) -> None:
    selected_date = _require_enum_date(binding, effective_date)
    try:
        catalogue = resolve_rental_reduction_art232_tier_catalogue(effective_date=selected_date, authority=operation)
    except (RegistrySnapshotError, RegistryValidationError):
        raise ModeloBindingValueContractUnsupportedError() from None
    if str(catalogue.require(raw)) != raw:
        raise ModeloBindingValueInvalidError()


def _validate_estimation_modality_enum(binding: BindingDefinition, raw: str) -> None:
    if binding.value.channel not in {BindingValueChannel.BOOLEAN, BindingValueChannel.DECIMAL}:
        raise ModeloBindingValueContractUnsupportedError()
    encoded = boolean_binding_encoded_values(binding)
    if not encoded:
        raise ModeloBindingValueContractUnsupportedError()
    if raw not in {row.encoded_value for row in encoded}:
        raise ModeloBindingValueInvalidError()


def validate_typed_binding_value(
    binding: BindingDefinition,
    raw: str,
    snapshot: RegistrySnapshot,
    *,
    operation: PinnedAuthorityOperation,
    effective_date: date | None,
) -> ModeloTypedBindingValue:
    """Validate one raw value against its pinned declaration and official constraints."""
    contract = binding.value
    if contract.channel is BindingValueChannel.ROW_SET:
        raise ModeloBindingValueContractUnsupportedError()
    if not raw or len(raw) > MAX_TYPED_BINDING_VALUE_LENGTH:
        raise ModeloBindingValueInvalidError()
    targets = _bound_targets(snapshot, binding.id)
    _validate_typed_enum(binding, raw, operation=operation, effective_date=effective_date)
    try:
        validate_binding_channel_value(binding, raw, targets)
    except ModeloBindingValueContractUnsupportedError:
        raise
    except (RegistryValidationError, ValidationError, ValueError, OverflowError):
        raise ModeloBindingValueInvalidError() from None
    return ModeloTypedBindingValue(
        binding_id=binding.id, data_type=contract.data_type, channel=contract.channel, value=raw
    )


def resolve_typed_bindings(
    payload: ModeloBindingsResolveRequest, operation: PinnedAuthorityOperation
) -> ModeloBindingsResolveTypedProjection:
    """Build the typed preview from the retained authority operation."""
    period = payload.period.to_period()
    snapshot = operation.snapshot(
        payload.modelo, filing_year=period.filing_year, period=period.registry_token, on=payload.as_of
    )
    declarations = revision_bindings_by_id(snapshot.revision)
    _require_declared_binding_overrides(payload.overrides, declarations)
    human = _read_human_binding_preview(payload, operation=operation, snapshot=snapshot)
    validated = _validate_binding_overrides(payload, declarations, snapshot, operation=operation, period=period)
    canonical = {row.binding_id: row.value for row in validated}
    rows = tuple(row.model_copy(update={"override": canonical.get(row.binding_id)}) for row in human.bindings)
    return ModeloBindingsResolveTypedProjection(
        authority_generation=human.authority_generation,
        profile_id=payload.profile_id,
        modelo=human.modelo,
        revision=human.revision,
        filing_year=human.filing_year,
        period=human.period,
        override_count=human.override_count,
        binding_count=human.binding_count,
        bindings=rows,
        validated_overrides=validated,
    )


def _require_declared_binding_overrides(
    overrides: tuple[ModeloBindingOverride, ...],
    declarations: dict[str, BindingDefinition],
) -> None:
    for override in overrides:
        if override.binding_id not in declarations:
            raise ModeloBindingValueInvalidError()


def _read_human_binding_preview(
    payload: ModeloBindingsResolveRequest,
    *,
    operation: PinnedAuthorityOperation,
    snapshot: RegistrySnapshot,
) -> ModeloBindingsResolveProjection:
    try:
        human = read_modelo_bindings_resolve(payload, operation=operation)
    except RegistryValidationError:
        raise ModeloBindingValueInvalidError() from None
    if snapshot.revision.id != human.revision:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return human


def _validate_binding_overrides(
    payload: ModeloBindingsResolveRequest,
    declarations: dict[str, BindingDefinition],
    snapshot: RegistrySnapshot,
    *,
    operation: PinnedAuthorityOperation,
    period: Period,
) -> tuple[ModeloTypedBindingValue, ...]:
    validated_rows: list[ModeloTypedBindingValue] = []
    effective_date = payload.as_of or (period.end_date if period.has_date_span() else None)
    for override in payload.overrides:
        declaration = declarations.get(override.binding_id)
        if declaration is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        try:
            validated_rows.append(
                validate_typed_binding_value(
                    declaration,
                    override.value,
                    snapshot,
                    operation=operation,
                    effective_date=effective_date,
                )
            )
        except (ModeloBindingValueContractUnsupportedError, ModeloBindingValueInvalidError) as error:
            raise type(error)(binding_id=declaration.id, channel=declaration.value.channel) from None
    return tuple(validated_rows)
