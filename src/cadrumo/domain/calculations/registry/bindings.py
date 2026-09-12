"""Data binding helpers for registry-backed factual inputs.

This module owns the
:class:`~domain.calculations.registry.CasillaObservation` envelope emitted
by the formula runtime and the
:class:`~domain.calculations.registry.BindingDefinition` helper
surface that turns factual binding values into bound casilla inputs.

See Also:
    :mod:`domain.calculations.registry._formula_runtime`
        Runtime that emits typed observations and consumes resolved bound
        casilla inputs.
    :mod:`domain.calculations.registry._formula_initial_values`
        Initial-value assembler that calls the bound-casilla helpers here.
    :mod:`domain.calculations.registry._schema`
        Registry schema definitions for casillas, bindings, and revisions.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from pydantic import (
    BaseModel,
    Field,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.filing_year import FilingYear
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import Period, RegistryPeriodCode
from ....core.type_adapters import OBJECT_TUPLE_ADAPTER
from ....core.type_guards import is_object_mapping
from .bienes_inversion_regularizacion_bindings import BienesInversionRegularizacionProvider
from .binding_provider_registration import registration_for, validator_for
from .binding_selector_utils import selector_as_dict
from .binding_targets import bound_casilla_binding_ids as _bound_casilla_binding_ids
from .bindings_previous_filing import PreviousFilingProvider
from .errors import RegistryValidationError
from .ids import BindingId, FormulaId, LegalRefId, ModeloId, SourceRefId
from .invoice_bindings import (
    InvoiceProviderBase as InvoiceProviderBase,
)
from .iva_compensation_annual_partition_bindings import (
    IvaCompensationAnnualPartitionProvider,
)
from .m303_regimen_simplificado_annual_summary_bindings import (
    M303RegimenSimplificadoAnnualSummaryProvider,
)
from .period_selector_match import selector_period_matches_request
from .prorrata_regularizacion_bindings import ProrrataRegularizacionProvider
from .relation_prefill_bindings import RelationPrefillProvider
from .schema_input_kind import InputKind
from .schema_surfaces import CasillaDefinition

if TYPE_CHECKING:
    from .schema import BindingDefinition, ModeloRevision

__all__ = [
    "CasillaObservation",
    "IvaCompensationAnnualPartitionRequirement",
    "RegistryModeloObservation",
    "binding_source_casilla_ids",
    "binding_source_modelo",
    "iva_compensation_annual_partition_requirement",
    "resolve_available_bound_inputs_by_casilla_id",
    "resolve_bound_casilla_binding_value",
]


def _tuple_from_json_array(value: object) -> object:
    if isinstance(value, list):
        return OBJECT_TUPLE_ADAPTER.validate_python(value)
    return value


def _decimal_from_json_string(value: object) -> object:
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise RegistryValidationError("casilla observation decimal JSON value must be numeric") from exc
    return value


def _decimal_tuple_from_json_array(value: object) -> object:
    if isinstance(value, list):
        return tuple(_decimal_from_json_string(item) for item in OBJECT_TUPLE_ADAPTER.validate_python(value))
    return value


class CasillaObservationValueKind(StrEnum):
    """Whether an observed casilla value is a number or free text."""

    DECIMAL = "decimal"
    TEXT = "text"


CasillaObservationValueKindValue = Literal[
    CasillaObservationValueKind.DECIMAL,
    CasillaObservationValueKind.TEXT,
]
"""The same vocabulary for a strict model field."""


class CasillaObservation(BaseModel):
    """One typed casilla observation emitted by the formula runtime.

    Carries a :class:`~core.CasillaId`, final
    scalar value (numeric :class:`decimal.Decimal` or validated text), required
    legal/source provenance, and
    optional formula lineage. When ``formula_id`` is set, the runtime computed
    this casilla and ``operand_refs`` / ``operand_values`` trace its inputs
    while ``operand_casilla_refs`` carries the casilla-id-only projection; when
    ``formula_id`` is ``None`` the casilla was supplied as input (manual /
    bound) and the trace fields are empty.

    Used as the primary storage for
    :class:`~domain.calculations.registry.RegistryCalculationResult`;
    derived ``values`` and ``entries`` views project from it.
    """

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    value_kind: CasillaObservationValueKindValue = Field(
        default=CasillaObservationValueKind.DECIMAL,
        exclude_if=lambda value: value == CasillaObservationValueKind.DECIMAL,
    )
    value: Decimal | str
    formula_id: FormulaId | None = None
    # ``op`` is the formula's top-level operator label (``add``, ``multiply``,
    # ``lookup_bracket_by_ccaa`` …). Carried alongside ``formula_id`` so the
    # full :class:`RegistryCalculationEntry` shape projects back from a typed
    # observation tuple without losing the dispatch label. ``None`` for
    # input / bound casillas where no formula ran.
    op: str | None = None
    operand_refs: tuple[str, ...] = ()
    operand_casilla_refs: tuple[CasillaId, ...] = ()
    operand_values: tuple[Decimal, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    # Set ``True`` when the casilla's declared binding produced no
    # source anchor for the target period (e.g. Modelo 130 casilla 15
    # at 1T — the prior-quarter carry-forward selector with
    # ``max_year_delta = 0`` suppresses the cross-ejercicio anchor).
    # The value is ``Decimal("0")`` materialised through an explicit
    # constructor rather than through a generic missing-input default.
    # Downstream audit and review surfaces should distinguish
    # absent-by-design zeros from value-bearing observations.
    absent_by_design: bool = False

    @field_validator("value", mode="before")
    @classmethod
    def _value_from_json_string(cls, value: object, info: ValidationInfo) -> object:
        if info.data.get("value_kind", "decimal") == "decimal":
            return _decimal_from_json_string(value)
        return value

    @field_validator("value")
    @classmethod
    def _scalar_value(cls, value: Decimal | str) -> Decimal | str:
        return value

    @model_validator(mode="after")
    def _value_matches_kind(self) -> CasillaObservation:
        if self.value_kind == "decimal" and not isinstance(self.value, Decimal):
            raise RegistryValidationError("decimal casilla observation must carry a Decimal value")
        if self.value_kind == "text" and not isinstance(self.value, str):
            raise RegistryValidationError("text casilla observation must carry a string value")
        return self

    @field_validator("operand_refs", "operand_casilla_refs", "legal_refs", "source_refs", mode="before")
    @classmethod
    def _tuple_fields_from_json_arrays(cls, value: object) -> object:
        return _tuple_from_json_array(value)

    @field_validator("operand_values", mode="before")
    @classmethod
    def _decimal_tuple_field_from_json_array(cls, value: object) -> object:
        return _decimal_tuple_from_json_array(value)

    @model_validator(mode="after")
    def _operand_casilla_refs_are_traced(self) -> CasillaObservation:
        missing = tuple(ref for ref in self.operand_casilla_refs if ref not in self.operand_refs)
        if missing:
            raise RegistryValidationError(
                f"casilla observation for {self.casilla_id!r} declares operand_casilla_refs "
                f"that are absent from operand_refs: {missing!r}",
            )
        return self


class RegistryModeloObservation(BaseModel):
    """Observed casilla values from a filed declaration.

    Storage is ``observations``: a typed tuple of
    :class:`~domain.calculations.registry.CasillaObservation` carrying full
    formula provenance. The :attr:`casilla_values` property provides a read-only
    mapping view for downstream consumers.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloId
    filing_period: Period | None = None
    filing_year: FilingYear
    #: A registry coordinate, not necessarily a period a taxpayer files in:
    #: a non-filing modelo such as the censal 036 is addressed by its event
    #: (alta, modificacion, baja) rather than by a calendar period. The
    #: span-capable ``filing_period`` above stays ``None`` for those.
    period: RegistryPeriodCode
    observations: tuple[CasillaObservation, ...] = Field(default_factory=tuple)

    @model_validator(mode="before")
    @classmethod
    def _hydrate_filing_period(cls, data: object) -> object:
        if not is_object_mapping(data) or "filing_period" in data:
            return data
        payload: dict[str, object] = {}
        for key, value in data.items():
            if not isinstance(key, str):
                return data
            payload[key] = value
        filing_year = payload.get("filing_year")
        period = payload.get("period")
        if not isinstance(filing_year, int) or not isinstance(period, str):
            return data
        try:
            filing_period = Period.from_year_and_code(filing_year, period)
        except ValueError as exc:
            # An administrative coordinate has no calendar span, so a
            # non-filing modelo simply carries no filing_period. Anything
            # else that cannot form a Period -- a combined display form such
            # as "2025 1T" -- is drift and is still refused here.
            try:
                TypeAdapter(RegistryPeriodCode).validate_python(period)
            except ValidationError:
                raise RegistryValidationError(
                    "observation period must be a bare registry period token",
                ) from exc
            return data
        return {**payload, "filing_period": filing_period}

    @field_validator("observations", mode="before")
    @classmethod
    def _observations_from_json_array(cls, value: object) -> object:
        return _tuple_from_json_array(value)

    @model_validator(mode="after")
    def _validate_filing_period_consistency(self) -> RegistryModeloObservation:
        if self.filing_period is None:
            return self
        if self.filing_period.filing_year != self.filing_year:
            raise RegistryValidationError("observation filing_period year must match filing_year")
        if not selector_period_matches_request(self.period, self.filing_period.registry_token):
            raise RegistryValidationError("observation filing_period code must match period")
        return self

    @property
    def casilla_values(self) -> Mapping[CasillaId, Decimal]:
        """Read-only mapping view: casilla_id -> Decimal derived from typed observations.

        Deliberately a plain ``@property`` and NOT a pydantic
        ``computed_field``: the typed envelope (``observations``) is
        canonical storage. Exposing this derived view in JSON would
        round-trip self-incompatibly under ``extra='forbid'`` because
        the loader would refuse the duplicate field on the way back in.
        """
        return {obs.casilla_id: obs.value for obs in self.observations if isinstance(obs.value, Decimal)}


def resolve_bound_casilla_binding_value(
    casilla: CasillaDefinition,
    facts: Mapping[BindingId, Decimal],
) -> tuple[Decimal | None, tuple[BindingId, ...]]:
    """Resolve equivalent binding facts for one casilla, rejecting disagreements.

    A bound :class:`~domain.calculations.registry.CasillaDefinition` can
    declare reviewed alternate bindings when multiple registry source paths
    represent the same factual amount. Supplying two equivalent source values is
    legal only if they agree exactly; otherwise accepting either one would
    silently over- or under-declare the downstream calculation.
    """
    binding_ids = _bound_casilla_binding_ids(casilla)
    present = tuple((binding_id, facts[binding_id]) for binding_id in binding_ids if binding_id in facts)
    if not present:
        return None, ()
    first_value = present[0][1]
    disagreeing = tuple((binding_id, value) for binding_id, value in present if value != first_value)
    if disagreeing:
        values_by_binding = ", ".join(f"{binding_id!r}={value!r}" for binding_id, value in present)
        raise RegistryValidationError(
            f"bound casilla {casilla.id!r} received conflicting equivalent binding values: {values_by_binding}",
            context={
                "casilla_id": casilla.id,
                "binding_ids": ",".join(binding_id for binding_id, _value in present),
            },
        )
    return first_value, tuple(binding_id for binding_id, _value in present)


def resolve_available_bound_inputs_by_casilla_id(
    revision: ModeloRevision,
    binding_values: Mapping[BindingId, Decimal],
) -> dict[CasillaId, Decimal]:
    """Project available binding values into input values keyed by bound ``casilla.id``.

    The :class:`ModeloRevision` supplies the
    bound casilla-to-binding mapping; only values already present in
    ``binding_values`` are projected. Missing optional bindings are skipped
    rather than treated as registry errors, which lets calculate paths combine
    partial source mesh output with caller overrides before the engine runs.

    Args:
        revision: The :class:`ModeloRevision`
            whose bound casillas are inspected.
        binding_values: Decimal values keyed by
            :class:`~domain.calculations.registry.BindingId`.

    Returns:
        A ``dict`` keyed by
        :class:`~cadrumo.core.CasillaId` for every bound
        casilla whose binding value is currently available.

    See Also:
        :func:`resolve_bound_casilla_binding_value`:
            Per-casilla primitive this projection folds over, including its
            refusal of disagreeing equivalent alternate bindings.
    """
    resolved: dict[CasillaId, Decimal] = {}
    for casilla in revision.casillas:
        if casilla.input_kind != InputKind.BOUND or casilla.binding is None:
            continue
        value, _binding_ids = resolve_bound_casilla_binding_value(casilla, binding_values)
        if value is not None:
            resolved[casilla.id] = value
    return resolved


# Binding-family implementations are split by source family. This module owns
# cross-family selector-shape dispatch and the typed source accessors only; each
# provider member is imported from its own defining module.


class IvaCompensationAnnualPartitionRequirement(BaseModel):
    """One typed annual Modelo 303 compensation-partition projection.

    The annual partition is a distinct FIFO resolution family, rather than a
    relation fold. Its bindings nevertheless share one source fact: four
    Modelo 303 state observations and the target revision's declared treatment
    of that source. This projection is the only interpretation of the binding
    selectors consumers may use; it retains each target slot and the complete
    source/provenance contract without exposing raw selector mappings.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: ModeloId
    source_periods: tuple[str, ...] = Field(min_length=1)
    source_casilla_ids: tuple[CasillaId, ...] = Field(min_length=1)
    binding_ids: tuple[BindingId, ...] = Field(min_length=1)
    last_period_amount_binding_id: BindingId | None = None
    generated_not_in_last_amount_binding_id: BindingId | None = None
    dependency_treatment: str = ""
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


def _iva_compensation_annual_partition_selector(
    binding: BindingDefinition,
) -> IvaCompensationAnnualPartitionProvider:
    try:
        return IvaCompensationAnnualPartitionProvider.model_validate(selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed iva_compensation_annual_partition selector: {exc}",
        ) from exc


def iva_compensation_annual_partition_requirement(
    revision: ModeloRevision,
) -> IvaCompensationAnnualPartitionRequirement | None:
    """Project the revision's annual compensation-partition bindings once.

    Returns ``None`` when the revision declares no partition bindings. When it
    does, every binding must name the same typed source selector and each of
    the two partition outputs may be targeted at most once. The source's
    dependency treatment comes directly from the revision classification and
    stays empty only when that classification is absent; consumers must not
    reconstruct or default it.
    """
    bindings = _iva_compensation_annual_partition_bindings(revision)
    if not bindings:
        return None

    first_selector = _iva_compensation_annual_partition_selector(bindings[0])
    (
        last_period_amount_binding_id,
        generated_not_in_last_amount_binding_id,
        legal_refs,
        source_refs,
    ) = _collect_iva_compensation_partition_bindings(bindings, first_selector)
    return IvaCompensationAnnualPartitionRequirement(
        source_modelo=first_selector.source_modelo,
        source_periods=first_selector.source_periods,
        source_casilla_ids=first_selector.source_casilla_ids,
        binding_ids=tuple(sorted(binding.id for binding in bindings)),
        last_period_amount_binding_id=last_period_amount_binding_id,
        generated_not_in_last_amount_binding_id=generated_not_in_last_amount_binding_id,
        dependency_treatment=_iva_compensation_dependency_treatment(revision, first_selector.source_modelo),
        legal_refs=tuple(sorted(legal_refs)),
        source_refs=tuple(sorted(source_refs)),
    )


def _iva_compensation_annual_partition_bindings(
    revision: ModeloRevision,
) -> tuple[BindingDefinition, ...]:
    """Collect the annual compensation-partition bindings in revision order."""
    return tuple(
        binding
        for binding in revision.bindings
        if binding.source == BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION
    )


def _collect_iva_compensation_partition_bindings(
    bindings: tuple[BindingDefinition, ...],
    first_selector: IvaCompensationAnnualPartitionProvider,
) -> tuple[
    BindingId | None,
    BindingId | None,
    set[LegalRefId],
    set[SourceRefId],
]:
    """Validate shared selectors and collect target ids plus provenance refs."""
    last_period_amount_binding_id: BindingId | None = None
    generated_not_in_last_amount_binding_id: BindingId | None = None
    legal_refs: set[LegalRefId] = set()
    source_refs: set[SourceRefId] = set()
    for binding in bindings:
        selector = _iva_compensation_annual_partition_selector(binding)
        _require_shared_iva_compensation_selector(selector, first_selector)
        if selector.partition_output == "last_period_amount":
            last_period_amount_binding_id = _unique_partition_binding_id(
                last_period_amount_binding_id,
                binding.id,
                "last_period_amount",
            )
        else:
            generated_not_in_last_amount_binding_id = _unique_partition_binding_id(
                generated_not_in_last_amount_binding_id,
                binding.id,
                "generated_not_in_last_amount",
            )
        legal_refs.update(binding.legal_refs)
        source_refs.update(binding.source_refs)
    return last_period_amount_binding_id, generated_not_in_last_amount_binding_id, legal_refs, source_refs


def _require_shared_iva_compensation_selector(
    selector: IvaCompensationAnnualPartitionProvider,
    first_selector: IvaCompensationAnnualPartitionProvider,
) -> None:
    """Require every annual partition binding to use one source selector."""
    if (
        selector.source_modelo != first_selector.source_modelo
        or selector.source_casilla_ids != first_selector.source_casilla_ids
        or selector.source_periods != first_selector.source_periods
    ):
        raise RegistryValidationError(
            "iva_compensation_annual_partition bindings must share one source selector",
        )


def _unique_partition_binding_id(
    existing: BindingId | None,
    binding_id: BindingId,
    output: Literal["last_period_amount", "generated_not_in_last_amount"],
) -> BindingId:
    """Return one partition target id, refusing duplicate target declarations."""
    if existing is not None:
        raise RegistryValidationError(
            f"iva_compensation_annual_partition declares multiple {output} bindings",
        )
    return binding_id


def _iva_compensation_dependency_treatment(revision: ModeloRevision, source_modelo: ModeloId) -> str:
    """Read the revision-owned dependency treatment for the partition source."""
    classification = next(
        (candidate for candidate in revision.dependency_classifications if candidate.source_modelo == source_modelo),
        None,
    )
    return "" if classification is None else str(classification.treatment)


def _declared_source_casilla_ids(
    provider: PreviousFilingProvider | RelationPrefillProvider,
) -> tuple[CasillaId, ...]:
    """Return the source casillas of a member carrying both the singular and plural field."""
    if provider.source_casilla_ids:
        return provider.source_casilla_ids
    if provider.source_casilla_id is not None:
        return (provider.source_casilla_id,)
    return ()


def _refuse_undeclared_source_narrowing(binding: BindingDefinition, coordinate: str) -> None:
    """Refuse a family whose registration names a source coordinate the narrow does not handle.

    Reaching here means the registration table and these accessors disagree: the
    provider member declares the coordinate, so returning the empty answer would
    under-declare a real source rather than report the absence of one.

    Raises:
        RegistryValidationError: Always, when called for such a family.
    """
    raise RegistryValidationError(
        f"binding {binding.id!r} provider {binding.source.value!r} declares a {coordinate} "
        f"that the typed source accessor does not narrow",
        context={"binding_id": str(binding.id), "kind": binding.source.value},
    )


def binding_source_casilla_ids(binding: BindingDefinition) -> tuple[CasillaId, ...]:
    """Return the typed source casilla ids the binding's provider member declares.

    The answer is read off the constructed provider member, not re-parsed from a
    dumped mapping: the union already narrowed the row to one class, so this is
    a structural match over the members that carry a source coordinate.

    An empty tuple means the family declares no source casilla, which the
    registration states independently. A family whose registration says it names
    one and which no branch below handles is refused rather than silently
    answered with the empty tuple.

    Raises:
        RegistryValidationError: The provider's registration declares a source
            casilla coordinate that no branch here narrows.
    """
    provider = binding.provider
    match provider:
        case PreviousFilingProvider() | RelationPrefillProvider():
            return _declared_source_casilla_ids(provider)
        case (
            IvaCompensationAnnualPartitionProvider()
            | M303RegimenSimplificadoAnnualSummaryProvider()
            | ProrrataRegularizacionProvider()
        ):
            return provider.source_casilla_ids
        case _:
            if registration_for(binding.source).names_source_casilla:
                _refuse_undeclared_source_narrowing(binding, "source casilla")
            return ()


def binding_source_modelo(binding: BindingDefinition) -> ModeloId | None:
    """Return the typed source modelo the binding's provider member declares.

    ``None`` means the family declares no source modelo. A family whose
    registration says it declares one and which no branch below handles is
    refused rather than silently answered with ``None``.

    Raises:
        RegistryValidationError: The provider's registration declares a source
            modelo coordinate that no branch here narrows.
    """
    provider = binding.provider
    match provider:
        case (
            PreviousFilingProvider()
            | RelationPrefillProvider()
            | IvaCompensationAnnualPartitionProvider()
            | M303RegimenSimplificadoAnnualSummaryProvider()
            | ProrrataRegularizacionProvider()
            | BienesInversionRegularizacionProvider()
        ):
            return provider.source_modelo
        case _:
            if registration_for(binding.source).names_source_modelo:
                _refuse_undeclared_source_narrowing(binding, "source modelo")
            return None


def validate_binding_selector_shape(binding: BindingDefinition) -> list[str]:
    """Validate a binding against its provider kind's single enrolled validator.

    Dispatch is one join through the canonical enrollment authority: the
    provider member's own discriminator selects its
    :class:`~.binding_provider_registration.BindingProviderRegistration`, whose
    ``validator`` is the family's build-time gate. A kind with no registration
    cannot reach here -- the registration table refuses to import unless it
    covers exactly the provider union, and the union refuses an unknown member
    at construction -- so this function holds no opinion about membership.

    A registration may enrol no validator at all. That is the stated answer for
    a family whose provider member is its own complete gate: the union built
    that member from the authored row, so there is nothing left to check and no
    diagnostic to earn.

    Each family validator validates the provider shape (projected through the
    same normalised mapping the resolve-time helpers see, so the gate is never
    stricter than runtime) and lifts that family's op/fact cross-invariants to
    build time. Failures accumulate as diagnostic strings rather than raising,
    preserving the underlying pydantic field error, so the snapshot-build gate
    collects every failure across a revision in one pass.
    """
    validator = validator_for(binding.source)
    if validator is None:
        return []
    return validator(binding)
