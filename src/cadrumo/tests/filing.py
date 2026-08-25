"""Registry-backed filing support for real-behavior tests.

The helpers keep tests on the same path as production filing: they resolve a
typed :class:`~core.Period` through
:func:`application.filing.build_runtime_schema_provider`, call
:func:`application.filing.build_draft`, and only use
:func:`application.filing.approve_draft` when the requested
:class:`~domain.submission.ModeloDraftStatus` is
:attr:`~domain.submission.ModeloDraftStatus.APROBADO`. The approval path
receives an empty :class:`TransactionCatalogue` and an empty
:class:`~domain.invoices.InvoiceCatalogue` so tests without ledger or
invoice state get a deterministic approval basis without a bucket self-load.

See Also:
    :mod:`application.filing.runtime`
        Production registry schema-provider projection.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from pydantic import TypeAdapter, ValidationError

from ..application.filing import (
    approve_draft,
    build_draft,
    build_runtime_schema_provider,
    empty_prior_filing_observations_fingerprint,
    empty_profile_activity_fingerprint,
)
from ..core import CasillaId, Period, validated_casilla_id
from cadrumo.domain.calculations.registry.ids import BindingId
from ..domain.filing import ModeloBuilderError, ModeloDraft, ModeloInputs
from ..domain.invoices import InvoiceCatalogue
from ..domain.submission import ModeloDraftStatus
from ..domain.transactions import TransactionCatalogue

_REGISTRY_TEST_BUCKET_ID = "1465aefb-768a-4344-a564-1f0737966d59"  # was 'registry-test'
_BINDING_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(BindingId)


@dataclass(frozen=True, slots=True)
class _RegistryProfile:
    """Minimal filing identity for registry-backed real-behavior tests."""

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
    """Build a :class:`ModeloDraft` through the validated registry runtime path.

    Args:
        modelo: Stable modelo id to resolve from the bundled registry.
        period: Typed :class:`~core.Period`; raw string periods are
            rejected before registry lookup.
        profile_tax_id: Tax identifier written to the generated test profile.
        casilla_values: Casilla input mapping passed to
            :func:`application.filing.build_draft`.
        binding_values: Optional registry binding inputs. Keys that duplicate
            ``casilla_values`` are rejected so fixture data cannot shadow itself.
        status: Desired final :class:`~domain.submission.ModeloDraftStatus`.
            ``APROBADO`` uses :func:`application.filing.approve_draft`;
            every other status clears approval metadata on the built draft.

    Returns:
        The built :class:`ModeloDraft`, approved only when ``status`` is
        :attr:`~domain.submission.ModeloDraftStatus.APROBADO`.

    Raises:
        ModeloBuilderError: When ``period`` is not a
            :class:`~core.Period`, duplicate input ids are supplied, or
            the registry build/approval path rejects the fixture inputs.
    """
    if not isinstance(period, Period):
        raise ModeloBuilderError("registry filing test helper requires a core.Period")
    typed_period = period
    schema_provider = build_runtime_schema_provider(
        modelos=(modelo,),
        filing_year=typed_period.filing_year,
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
        profile=_RegistryProfile(
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
            invoice_catalogue=InvoiceCatalogue(),
            prior_filing_observations_fingerprint=empty_prior_filing_observations_fingerprint(),
            profile_activity_fingerprint=empty_profile_activity_fingerprint(),
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

    Casilla keys are canonicalised with
    :func:`domain.calculations.registry.validated_casilla_id`; binding
    keys are validated as registry ``BindingId`` tokens before the coerced
    values are forwarded to :func:`build_registry_filing_draft`.

    Args:
        modelo: Stable modelo id to resolve from the bundled registry.
        period: Typed :class:`~core.Period` passed through unchanged.
        profile_tax_id: Tax identifier written to the generated test profile.
        casilla_decimals: Casilla-id keyed values as :class:`Decimal` instances
            or decimal strings.
        binding_decimals: Optional binding-id keyed values as
            :class:`Decimal` instances or decimal strings.
        status: Desired final :class:`~domain.submission.ModeloDraftStatus`.

    Returns:
        The :class:`ModeloDraft` returned by :func:`build_registry_filing_draft`.

    Raises:
        ValueError: When a casilla key is not a canonical casilla id.
        ModeloBuilderError: When a binding key is not a canonical binding id.
        decimal.InvalidOperation: When a decimal string cannot be parsed.
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
    "build_registry_filing_draft",
    "build_registry_filing_draft_from_decimals",
]
