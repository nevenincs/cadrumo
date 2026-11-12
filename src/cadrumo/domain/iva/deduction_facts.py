"""Immutable, evidence-grounded IVA deduction-fact classification."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, Field, field_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identity.digest import ContentDigest
from ...core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ...core.models import STRICT_FROZEN_CONFIG
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.iva_deduction_catalogue import (
    require_iva_deduction_evidence_authority,
    require_iva_deduction_fact_kind,
    resolve_iva_deduction_catalogue,
)
from ..calculations.registry.iva_flow_catalogue import require_iva_flow_direction
from .errors import IvaValidationError
from .flow import IvaFlowDirection
from .schema import IvaCategory, IvaRateKind

#: The fact-0085 source families one deduction kind can belong to.
#:
#: Each family names three declarations that have to agree before a
#: classification carries authority: ``kind.<family>`` lists the kinds it covers,
#: ``category.<family>`` the IVA categories that bear such a deduction, and
#: ``flow.<family>`` the flows that settle it. This tuple is the single place the
#: families are enumerated -- :func:`admits_iva_deduction_classification` reads it
#: to answer whether any deduction arises at all, and
#: :func:`_validate_non_rectification_category` reads it to check the declared
#: kind against the row. Two enumerations would be free to disagree about which
#: rows bear a deduction, and the two answers reach the operator as opposite
#: refusals on one row.
_DEDUCTION_SOURCE_FAMILIES: Final = ("domestic", "import", "intra_eu", "reagp")


class IvaDeductionClassificationProvenance(BaseModel):
    """Immutable evidence pointer for one explicitly classified deduction fact."""

    model_config = STRICT_FROZEN_CONFIG

    authority: IvaDeductionEvidenceAuthority
    source_locator: str = Field(min_length=1, max_length=512)
    evidence_digest: ContentDigest

    @field_validator("authority", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _project_authority(cls, value: object) -> IvaDeductionEvidenceAuthority:
        """Accept persisted text only after fact-0085 membership validation."""
        if isinstance(value, IvaDeductionEvidenceAuthority):
            return value
        try:
            return require_iva_deduction_evidence_authority(value)
        except RegistryValidationError as exc:
            raise IvaValidationError(str(exc)) from exc


def _registry_iva_deduction_declarations(effective_date: date) -> Mapping[str, str]:
    """Resolve the IVA deduction applicability catalogue in force on ``effective_date``."""
    return resolve_iva_deduction_catalogue(effective_date=effective_date).declarations


def _required_declaration(declarations: Mapping[str, str], key: str) -> str:
    try:
        return declarations[key]
    except KeyError as exc:
        raise IvaValidationError(f"IVA deduction registry declaration is missing: {key}") from exc


def _declared_values(declarations: Mapping[str, str], key: str) -> frozenset[str]:
    return frozenset(value.strip() for value in _required_declaration(declarations, key).split(",") if value.strip())


def _declared_flow_values(declarations: Mapping[str, str], key: str, *, effective_date: date) -> frozenset[str]:
    """Resolve 0085 flow relations against the canonical 0083 vocabulary."""
    return frozenset(
        require_iva_flow_direction(value, effective_date=effective_date).value
        for value in _declared_values(declarations, key)
    )


def required_deduction_evidence_authority(
    kind: IvaDeductionFactKind,
    *,
    effective_date: date,
) -> IvaDeductionEvidenceAuthority:
    """Return the one evidence authority that can establish ``kind``.

    Exposes the mapping :func:`validate_iva_deduction_fact` already enforces, so
    a caller deciding whether it is ABLE to build a provenance for a kind reads
    the same table the refusal is derived from. Without this a caller must
    either duplicate the mapping or attempt a construction it knows will be
    rejected, and a duplicate would be free to drift.
    """
    try:
        return resolve_iva_deduction_catalogue(effective_date=effective_date).required_authority(kind)
    except RegistryValidationError as exc:
        raise IvaValidationError(str(exc)) from exc


def supplier_invoice_deduction_authority(
    kind: IvaDeductionFactKind,
    *,
    effective_date: date,
) -> IvaDeductionEvidenceAuthority | None:
    """Return the authority ``kind`` requires when the supplier's invoice justifies it, else ``None``.

    LIVA art. 97.Uno names the documents that justify a deduction. The
    supplier's invoice justifies a domestic purchase (1.º), an intra-community
    acquisition of goods (2.º) and an operation whose recipient is the sujeto
    pasivo under art. 84.Uno.2.º, among them a service acquired from a supplier
    established in another Member State (4.º). In the last two the invoice
    justifies the deduction only while the operation is consigned in the
    recipient's own declaración-liquidación: the intra-EU family's category and
    flow pair, which :func:`validate_iva_deduction_fact` enforces, makes the
    same row accrue the self-assessed cuota it deducts, so deduction and
    devengo reach the one return together. An import rests on the customs
    liquidation (3.º), a REAGP compensation on the farmer's receipt (5.º) and a
    rectification on its rectifying document (art. 97.Dos), none of which is
    the original purchase invoice the row links, so those kinds answer ``None``.
    """
    required = required_deduction_evidence_authority(kind, effective_date=effective_date)
    catalogue = resolve_iva_deduction_catalogue(effective_date=effective_date)
    try:
        invoice = catalogue.authority_for_role("invoice")
        self_assessed = catalogue.projection("kind.intra_eu")
    except RegistryValidationError as exc:
        raise IvaValidationError(str(exc)) from exc
    if required == invoice or kind in self_assessed:
        return required
    return None


def _validate_required_authority(
    kind: IvaDeductionFactKind,
    provenance: IvaDeductionClassificationProvenance,
    declarations: Mapping[str, str],
    *,
    effective_date: date,
) -> None:
    try:
        required_authority = require_iva_deduction_evidence_authority(
            _required_declaration(declarations, f"kind.required_authority.{kind.value}"),
            effective_date=effective_date,
        )
    except RegistryValidationError as exc:
        raise IvaValidationError(str(exc)) from exc
    if provenance.authority != required_authority:
        raise IvaValidationError(
            f"deduction kind {kind.value!r} requires {required_authority.value!r} evidence, "
            f"not {provenance.authority.value!r}"
        )


def _validate_investment_asset_identity(
    kind: IvaDeductionFactKind,
    investment_asset_id: str | None,
    declarations: Mapping[str, str],
) -> None:
    if kind.value in _declared_values(declarations, "kind.investment_acquisition"):
        if investment_asset_id is None:
            raise IvaValidationError(f"deduction kind {kind.value!r} requires investment_asset_id")
    elif investment_asset_id is not None:
        raise IvaValidationError(f"non-investment deduction kind {kind.value!r} cannot carry investment_asset_id")


def _validate_rectification(
    *,
    category: IvaCategory,
    rate_kind: IvaRateKind,
    flow_direction: IvaFlowDirection,
    base_amount: Decimal,
    iva_amount: Decimal,
    rectifies_ledger_id: str | None,
    declarations: Mapping[str, str],
    effective_date: date,
) -> None:
    if rectifies_ledger_id is None:
        raise IvaValidationError("rectification requires rectifies_ledger_id")
    if base_amount == Decimal("0") or iva_amount == Decimal("0"):
        raise IvaValidationError("rectification base_amount and iva_amount must both be signed non-zero evidence")
    required_flow = require_iva_flow_direction(
        _required_declaration(declarations, f"rectification_flow.{category.value}"),
        effective_date=effective_date,
    )
    if flow_direction.value != required_flow.value:
        raise IvaValidationError("rectification category and input IVA flow are not a closed legal pair")
    if rate_kind.value == _required_declaration(declarations, "rate.rectification_forbidden"):
        raise IvaValidationError("rectification of a deductible cuota cannot use the exempt rate tier")


def _validate_non_rectification_identity(
    *,
    kind: IvaDeductionFactKind,
    base_amount: Decimal,
    iva_amount: Decimal,
    rectifies_ledger_id: str | None,
) -> None:
    if rectifies_ledger_id is not None:
        raise IvaValidationError(f"deduction kind {kind.value!r} cannot carry rectifies_ledger_id")
    if base_amount < Decimal("0") or iva_amount < Decimal("0"):
        raise IvaValidationError("only rectification may carry signed negative IVA evidence")


def _source_family_for_kind(kind: IvaDeductionFactKind, declarations: Mapping[str, str]) -> str | None:
    """Return the fact-0085 source family ``kind`` belongs to, or ``None``."""
    return next(
        (
            family
            for family in _DEDUCTION_SOURCE_FAMILIES
            if kind.value in _declared_values(declarations, f"kind.{family}")
        ),
        None,
    )


def _source_families_admitting(
    category: IvaCategory,
    flow_direction: IvaFlowDirection,
    declarations: Mapping[str, str],
    *,
    effective_date: date,
) -> tuple[str, ...]:
    """Return every fact-0085 family whose category and flow this row satisfies."""
    return tuple(
        family
        for family in _DEDUCTION_SOURCE_FAMILIES
        if category.value in _declared_values(declarations, f"category.{family}")
        and flow_direction.value in _declared_flow_values(declarations, f"flow.{family}", effective_date=effective_date)
    )


def admits_iva_deduction_classification(
    *,
    category: IvaCategory,
    flow_direction: IvaFlowDirection,
    effective_date: date,
) -> bool:
    """Return whether fact 0085 grants any deduction on this category and flow.

    LIVA art. 92.Uno makes the object of a deduction a cuota that was devengada
    in the territory and borne by direct repercusión; where the operation raises
    no cuota there is no deduction fact to classify at all. Fact 0085 states that
    closed set as the ``category``/``flow`` pairs of its source families, so this
    asks the registry rather than restating the law. An exempt (LIVA art. 20) or
    not-subject (art. 7) domestic purchase belongs to no family, and a recargo de
    equivalencia purchase is non-deductible acquisition cost.

    Callers ask it from both sides of one decision: whether a deduction
    classification is REQUIRED on a row, and whether a present one has any
    authority. Answering the first from the flow direction deadlocked every
    zero-cuota purchase -- a received row settles as ``soportado`` whatever it is,
    so no kind satisfied the requirement and every kind failed admissibility.
    """
    declarations = _registry_iva_deduction_declarations(effective_date)
    return bool(_source_families_admitting(category, flow_direction, declarations, effective_date=effective_date))


def deduction_evidence_authority_for_row(
    *,
    kind: IvaDeductionFactKind | None,
    category: IvaCategory | None,
    effective_date: date,
) -> IvaDeductionEvidenceAuthority | None:
    """Return the registry authority establishing this row's deduction, when unambiguous.

    A declared kind governs its evidence. Without one, only a category whose
    admitted source families agree on one authority answers; an unknown or
    ambiguous category stays unresolved rather than guessing a document.
    """
    catalogue = resolve_iva_deduction_catalogue(effective_date=effective_date)
    if kind is not None:
        return catalogue.required_authority(kind) if kind in catalogue.kinds else None
    if category is None:
        return None
    authorities = {
        catalogue.required_authority(candidate)
        for family in _DEDUCTION_SOURCE_FAMILIES
        if category.value in _declared_values(catalogue.declarations, f"category.{family}")
        for candidate in catalogue.projection(f"kind.{family}")
    }
    return next(iter(authorities)) if len(authorities) == 1 else None


def _validate_non_rectification_category(
    *,
    kind: IvaDeductionFactKind,
    category: IvaCategory,
    rate_kind: IvaRateKind,
    flow_direction: IvaFlowDirection,
    declarations: Mapping[str, str],
    effective_date: date,
) -> None:
    family = _source_family_for_kind(kind, declarations)
    if family is None:
        return
    # Read by family name rather than branched on one: fact 0085 pins a single
    # admissible rate tier for the REAGP compensation family (``rate.reagp``) and
    # declares no such key for the families whose cuota is an ordinary tipo.
    required_rate = declarations.get(f"rate.{family}")
    if required_rate is not None and rate_kind.value != required_rate:
        raise IvaValidationError("registry-selected compensation rate is not admissible")
    if family not in _source_families_admitting(category, flow_direction, declarations, effective_date=effective_date):
        raise IvaValidationError("registry-selected deduction category and flow are not an admissible pair")


def validate_iva_deduction_fact(
    *,
    kind: IvaDeductionFactKind,
    provenance: IvaDeductionClassificationProvenance,
    category: IvaCategory,
    rate_kind: IvaRateKind,
    flow_direction: IvaFlowDirection,
    base_amount: Decimal,
    iva_amount: Decimal,
    investment_asset_id: str | None,
    rectifies_ledger_id: str | None,
    effective_date: date,
) -> None:
    """Refuse every deduction classification combination lacking legal authority."""
    try:
        kind = require_iva_deduction_fact_kind(kind, effective_date=effective_date)
    except RegistryValidationError as exc:
        raise IvaValidationError(str(exc)) from exc
    declarations = _registry_iva_deduction_declarations(effective_date)
    _validate_required_authority(kind, provenance, declarations, effective_date=effective_date)
    if kind.value in _declared_values(declarations, "kind.owner_only"):
        raise IvaValidationError("the owner-only deduction kind is emitted only by the bienes-inversion owner")
    _validate_investment_asset_identity(kind, investment_asset_id, declarations)
    if kind.value in _declared_values(declarations, "kind.rectification"):
        _validate_rectification(
            category=category,
            rate_kind=rate_kind,
            flow_direction=flow_direction,
            base_amount=base_amount,
            iva_amount=iva_amount,
            rectifies_ledger_id=rectifies_ledger_id,
            declarations=declarations,
            effective_date=effective_date,
        )
        return
    _validate_non_rectification_identity(
        kind=kind,
        base_amount=base_amount,
        iva_amount=iva_amount,
        rectifies_ledger_id=rectifies_ledger_id,
    )
    _validate_non_rectification_category(
        kind=kind,
        category=category,
        rate_kind=rate_kind,
        flow_direction=flow_direction,
        declarations=declarations,
        effective_date=effective_date,
    )


__all__ = [
    "IvaDeductionClassificationProvenance",
    "admits_iva_deduction_classification",
    "deduction_evidence_authority_for_row",
    "required_deduction_evidence_authority",
    "supplier_invoice_deduction_authority",
    "validate_iva_deduction_fact",
]
