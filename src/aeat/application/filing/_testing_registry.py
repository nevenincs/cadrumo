"""Registry-backed draft builders for filing tests.

:func:`build_registry_filing_draft` constructs a :class:`ModeloDraft`
through the production registry runtime. It calls
:func:`aeat.application.filing.approve_draft` with an empty
:class:`TransactionCatalogue` so the approval basis is deterministic
in tests that have no ledger state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from pydantic import TypeAdapter, ValidationError

from ...core import Period
from ...domain.calculations.registry import BindingId, CasillaId, validated_casilla_id
from ...domain.filing._protocols import ModeloInputs
from ...domain.filing._schema import ModeloDraft
from ...domain.submission import ModeloDraftStatus
from ...domain.transactions import TransactionCatalogue
from . import ModeloBuilderError, approve_draft, build_draft, build_runtime_schema_provider

_REGISTRY_TEST_BUCKET_ID = "registry-test"
_BINDING_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(BindingId)


@dataclass(frozen=True, slots=True)
class RegistryTestProfile:
    """Minimal filing profile used by registry-backed filing tests."""

    tax_id: str
    display_name: str


def build_registry_filing_draft(
    *,
    modelo: str,
    period: object,
    profile_tax_id: str = "Y0000001S",
    casilla_values: ModeloInputs,
    binding_values: ModeloInputs | None = None,
    status: ModeloDraftStatus = ModeloDraftStatus.APROBADO,
) -> ModeloDraft:
    """Build and return a :class:`ModeloDraft` through the validated registry runtime path."""
    if not isinstance(period, Period):
        raise ModeloBuilderError("registry filing test helper requires a core.Period")
    typed_period = period
    schema_provider = build_runtime_schema_provider(
        modelos=(modelo,),
        filing_year=typed_period.year,
        period=typed_period,
    )
    duplicate_input_ids = sorted(set(casilla_values).intersection(binding_values or {}))
    if duplicate_input_ids:
        raise ModeloBuilderError(
            f"registry filing test helper received duplicate casilla/binding input ids: {duplicate_input_ids!r}",
        )
    draft = build_draft(
        modelo=modelo,
        period=typed_period,
        profile=RegistryTestProfile(
            tax_id=profile_tax_id,
            display_name="Registry filing test",
        ),
        inputs={**(binding_values or {}), **casilla_values},
        schema_provider=schema_provider,
    )
    if status is ModeloDraftStatus.APROBADO:
        return approve_draft(
            draft,
            bucket_id=_REGISTRY_TEST_BUCKET_ID,
            approved_by="registry",
            schema_provider=schema_provider,
            transaction_catalogue=TransactionCatalogue(),
        )
    return draft.model_copy(
        update={
            "status": status,
            "approved_at": None,
            "approved_by": None,
            "review_checksum": None,
            "approval_basis": None,
        },
    )


def build_registry_filing_draft_from_decimals[CasillaKey, BindingKey](
    *,
    modelo: str,
    period: Period,
    profile_tax_id: str = "Y0000001S",
    casilla_decimals: Mapping[CasillaKey, str | Decimal],
    binding_decimals: Mapping[BindingKey, str | Decimal] | None = None,
    status: ModeloDraftStatus = ModeloDraftStatus.APROBADO,
) -> ModeloDraft:
    """Coerce decimal strings before building through the registry runtime.

    Returns a :class:`ModeloDraft`.
    """
    coerced: dict[CasillaId, Decimal] = {}
    for casilla_id, raw in casilla_decimals.items():
        canonical_casilla_id = validated_casilla_id(casilla_id, surface="registry filing test helper casilla id")
        coerced[canonical_casilla_id] = raw if isinstance(raw, Decimal) else Decimal(raw)
    coerced_bindings: dict[BindingId, Decimal] = {}
    for raw_binding_id, raw in (binding_decimals or {}).items():
        try:
            binding_id = _BINDING_ID_ADAPTER.validate_python(raw_binding_id)
        except ValidationError as exc:
            raise ModeloBuilderError(
                f"registry filing test helper binding id must be canonical: {raw_binding_id!r}",
            ) from exc
        coerced_bindings[binding_id] = raw if isinstance(raw, Decimal) else Decimal(raw)
    return build_registry_filing_draft(
        modelo=modelo,
        period=period,
        profile_tax_id=profile_tax_id,
        casilla_values=coerced,
        binding_values=coerced_bindings,
        status=status,
    )


__all__ = [
    "RegistryTestProfile",
    "build_registry_filing_draft",
    "build_registry_filing_draft_from_decimals",
]
