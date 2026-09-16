"""IVA flow direction enum — repercutido / soportado / INVERSION_SUJETO_PASIVO.

Codifies the IVA collectability axis the ledger and modelo registries
need alongside the operation-kind axis (:class:`IvaCategory`) and the
rate axis (:class:`IvaRateKind`). Every IVA-bearing ledger line
classifies along all three axes:

* :class:`IvaCategory` — operation kind (domestic, intracomunitaria,
  recargo, OSS, etc.).
* :class:`IvaRateKind` — rate tier (general / reduced / super-reduced /
  zero / exempt).
* :class:`IvaFlowDirection` — flow direction (output / input /
  self-assessed reverse charge).

Together the triple resolves to a single ledger-bookable Cuota.

The three flow directions are anchored to LIVA articles:

* :attr:`IvaFlowDirection.REPERCUTIDO` — LIVA art. 88 (repercusión
  del impuesto). The sujeto pasivo charges IVA to its customer; the
  customer is the obligado a soportar.
* :attr:`IvaFlowDirection.SOPORTADO` — LIVA art. 92 (cuotas
  tributarias deducibles). The sujeto pasivo bears IVA via direct
  repercusión from suppliers and may deduct that IVA from its own
  output IVA.
* :attr:`IvaFlowDirection.INVERSION_SUJETO_PASIVO` — LIVA art. 84.Uno.2.º
  (inversión del sujeto pasivo). The recipient of certain
  operations (intra-community acquisitions, art. 84.Uno.2.º.f
  construction reverse charge, etc.) is the sujeto pasivo and
  self-assesses both an IVA repercutido entry (output) and a
  matching IVA soportado entry (input) on the same operation.

The :func:`derive_flow_for_classification` helper computes the flow
direction from the substrate's :class:`IvaCategory` plus the invoice
:class:`InvoiceKind` axis so consumers do not have to encode the
mapping by hand.

==============================================================
Settlement-side cornerstones — devengada vs deducible
==============================================================

The IVA settlement model rests on two cornerstone concepts:

* **IVA devengada** (output IVA, "cuota tributaria devengada") — the
  amount the sujeto pasivo OWES to the Treasury as the IVA chargeable
  on its sales. LIVA arts. 75-77 establish when IVA accrues
  (devengo); LIVA art. 88 governs how the sujeto pasivo charges it
  to the customer (repercusión).
* **IVA deducible** (input IVA, "cuotas tributarias deducibles") —
  the amount the sujeto pasivo may DEDUCT from its devengada because
  it bore IVA on inputs. LIVA art. 92 establishes the right to
  deduction; arts. 93-104 establish the conditions, scope, and
  limits.

The cuota neta a ingresar (or a devolver) at the period level is
**devengada - deducible**; this is the canonical Modelo 303 "resultado
régimen general" line.

Every :class:`IvaFlowDirection` member contributes to one or both
cornerstones:

=======================  =========  =========
Flow direction           Devengada  Deducible
=======================  =========  =========
REPERCUTIDO              ✓          ─
SOPORTADO                ─          ✓
INVERSION_SUJETO_PASIVO  ✓          ✓
=======================  =========  =========

INVERSION_SUJETO_PASIVO is the only flow that contributes to BOTH sides on
the SAME operation: the recipient self-assesses an output entry
(devengada) and a matching input entry (deducible) for the cuota
that would have been repercutida by a non-existent or non-EU
supplier. The two entries cancel arithmetically inside Modelo 303
(devengada - deducible = 0 for that line) but both must be booked
to satisfy the LIVA art. 84.Uno.2 inversión-del-sujeto-pasivo
mechanism.

The :class:`IvaSettlementSide` enum + :func:`settlement_sides_for_flow`
helper let the ledger and modelo registries categorize transactions
without re-deriving the mapping. The closed-set helpers
:func:`is_devengada_flow` and :func:`is_deducible_flow` are the
canonical predicates for "does this flow contribute to the cuota
devengada / cuota deducible total?".
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ...core.errors.hierarchy import CoreValidationError
from ..calculations.registry.iva_category_catalogue import IvaCategoryCatalogue, resolve_iva_category_catalogue
from .classification import InvoiceKind
from .schema import IvaCategory

if TYPE_CHECKING:
    from ..calculations.registry.iva_flow_catalogue import IvaFlowDirectionCatalogue


class IvaFlowDirection(str):
    """Opaque IVA flow token projected from fact 0083.

    Flow membership, legal descriptions, and settlement-side semantics belong
    to the dated facts registry.  This wire type deliberately carries no
    closed Python member list; callers must obtain tokens through the typed
    registry projection.
    """

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Construct only tokens admitted by the governing catalogue."""
        if not _registry_validated:
            raise TypeError("IvaFlowDirection tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("IvaFlowDirection token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Construct the typed value from its canonical registry token."""
        return cls(value, _registry_validated=True)

    def __copy__(self) -> Self:
        """Share an immutable token without repeating membership admission."""
        return self

    def __deepcopy__(self, memo: dict[int, object]) -> Self:
        """Preserve the admitted token when copying a containing projection."""
        return self

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("IvaFlowDirection must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Accept already admitted tokens at typed model boundaries."""
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        """Return the canonical registry token for serialization."""
        return str(self)

    @property
    def name(self) -> str:
        """Return the canonical registry token for diagnostics."""
        return str(self)


def flow_direction_for_invoice_kind(invoice_kind: InvoiceKind) -> IvaFlowDirection:
    """Return the IVA flow direction an invoice's issuance side settles as.

    This is the base rule the tax itself states: an invoice the autónomo
    ISSUED charges output IVA onward (:attr:`IvaFlowDirection.REPERCUTIDO`);
    one it RECEIVED bears input IVA (:attr:`IvaFlowDirection.SOPORTADO`).
    :func:`derive_flow_for_classification` and
    :func:`~cadrumo.domain.iva.classify_invoice_line_for_iva` both call this
    for their standard-case resolution and OVERRIDE it for the special
    regimes (reverse charge, intra-community) that route the same members
    differently.
    """
    flow_catalogue = _flow_direction_catalogue()
    return flow_catalogue.issued_token if invoice_kind is InvoiceKind.ISSUED else flow_catalogue.received_token


def _flow_direction_catalogue() -> IvaFlowDirectionCatalogue:
    """Resolve the selected 0083 flow catalogue without an import cycle."""
    from ..calculations.registry.iva_flow_catalogue import resolve_iva_flow_direction_catalogue

    return resolve_iva_flow_direction_catalogue()


def _recipient_only_reverse_charge_categories(
    catalogue: IvaCategoryCatalogue,
) -> frozenset[IvaCategory]:
    """Return the reverse-charge categories that ignore the invoice direction.

    These route to ``INVERSION_SUJETO_PASIVO`` on EITHER invoice direction,
    because only the recipient's side exists.

    Both are ACQUISITIONS. The supplier's counterpart of an intra-community
    acquisition is a different category entirely (an exempt art. 25 supply, or an
    operation not located in Spain), so no invoice direction can put this taxpayer
    on the supplying side of one of these. Direction is therefore genuinely
    irrelevant here, and collapsing it is correct.

    The domestic reverse-charge category is deliberately NOT a member. A domestic
    art. 84.Uno.2 operation has both of its sides in Spain, so the same category
    legitimately describes a supply this taxpayer MADE and a purchase it RECEIVED
    -- and those settle differently. It is handled by direction in
    :func:`derive_flow_for_classification`.
    """
    return frozenset(
        {
            catalogue.require("intra_community_acquisition_reverse_charge"),
            # A B2B service received from an EU supplier sits in the same
            # position as the goods acquisition above: art. 69.Uno.1.o locates
            # it in Spain because the recipient is established here, and art.
            # 84.Uno.2.o makes that recipient the sujeto pasivo. Its supply
            # counterpart is deliberately absent -- there the operation is not
            # located in Spain at all, so no Spanish cuota arises to self-assess.
            catalogue.require("intra_community_service_acquisition_reverse_charge"),
        },
    )


def derive_flow_for_classification(
    *,
    category: IvaCategory,
    invoice_direction: InvoiceKind,
) -> IvaFlowDirection:
    """Return the IVA flow direction for a substrate-classified line.

    The mapping is:

    * Recipient-only reverse-charge categories (the intra-community
      acquisitions in :func:`_recipient_only_reverse_charge_categories`)
      resolve to :attr:`IvaFlowDirection.INVERSION_SUJETO_PASIVO`
      irrespective of the invoice direction, because their supply
      counterpart is not located in Spain and so raises no Spanish cuota
      to self-assess.
    * Domestic reverse charge resolves BY DIRECTION, because both sides
      of the operation are Spanish and the form asks for them
      separately: :attr:`InvoiceKind.RECEIVED` is the recipient
      self-assessing, so
      :attr:`IvaFlowDirection.INVERSION_SUJETO_PASIVO`;
      :attr:`InvoiceKind.ISSUED` is the supplier making a sujeta y no
      exenta supply that repercutes nothing, so
      :attr:`IvaFlowDirection.OPERACION_CON_INVERSION`. Collapsing the
      two once put the supplier's turnover on the recipient's line.
    * Otherwise: :attr:`InvoiceKind.ISSUED` resolves to
      :attr:`IvaFlowDirection.REPERCUTIDO` (the autónomo charged
      output IVA on a sale) and :attr:`InvoiceKind.RECEIVED`
      resolves to :attr:`IvaFlowDirection.SOPORTADO` (the autónomo
      bore input IVA on a purchase).

    Args:
        category: The :class:`IvaCategory` resolved by the substrate
            classifier.
        invoice_direction: Whether the invoice was issued or received
            by the autónomo.

    Returns:
        The :class:`IvaFlowDirection` that matches the classification.
    """
    category_catalogue = resolve_iva_category_catalogue()
    flow_catalogue = _flow_direction_catalogue()
    if category in _recipient_only_reverse_charge_categories(category_catalogue):
        return flow_catalogue.recipient_reverse_charge_token
    if category == category_catalogue.require("domestic_reverse_charge"):
        if invoice_direction is InvoiceKind.ISSUED:
            return flow_catalogue.supplier_reverse_charge_token
        return flow_catalogue.recipient_reverse_charge_token
    return flow_direction_for_invoice_kind(invoice_direction)


class IvaSettlementSide(str):
    """Opaque IVA settlement-side token projected from fact 0083."""

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Construct only tokens admitted by the governing catalogue."""
        if not _registry_validated:
            raise TypeError("IvaSettlementSide tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("IvaSettlementSide token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Construct the typed value from its canonical registry token."""
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("IvaSettlementSide must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Accept already admitted tokens at typed model boundaries."""
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        """Return the canonical registry token for serialization."""
        return str(self)

    @property
    def name(self) -> str:
        """Return the canonical registry token for diagnostics."""
        return str(self)


def settlement_sides_for_flow(
    flow: IvaFlowDirection,
) -> frozenset[IvaSettlementSide]:
    """Return the settlement side(s) ``flow`` contributes to.

    This is the CUOTA axis: which side of the settlement a line's cuota is
    reckoned on. It is not the axis of which half of the return a line's
    amounts appear in, and the two come apart on every zero-cuota operation.
    An exempt sale is an output operation whose base belongs on the devengada
    half of the return while settling no cuota at all, so reading a
    ``{DEVENGADA}`` here as "this line owes output IVA" is wrong for it.

    That distinction is easy to lose, because the Axis-A component table's
    ``cuota_settlement`` column and this function look like two statements of
    one fact and are not. Compare the two directly and roughly half the
    arising pairs appear to disagree; every one of those apparent conflicts is
    a zero-cuota operation where the table says "no cuota arises" and this
    function says "output side", both of which are true. The check worth making
    is per consumer, not per pair.

    Both production consumers screen on a positive cuota before asking, so the
    zero-cuota rows never reach the question. A future consumer that does not
    screen first is the one that would be misled, and it is the reason this
    paragraph exists rather than a coherence gate over two axes that do not
    answer the same question.

    Args:
        flow: The :class:`IvaFlowDirection` to classify.

    Returns:
        Frozenset of :class:`IvaSettlementSide` values: ``{DEVENGADA}`` for
        :attr:`IvaFlowDirection.REPERCUTIDO`, ``{DEDUCIBLE}`` for
        :attr:`IvaFlowDirection.SOPORTADO`, ``{DEVENGADA, DEDUCIBLE}`` for
        :attr:`IvaFlowDirection.INVERSION_SUJETO_PASIVO`, and the empty set for
        :attr:`IvaFlowDirection.OPERACION_CON_INVERSION`, whose supplier
        repercutes no cuota and bears none.
    """
    return _flow_direction_catalogue().settlement_sides_for(flow)


def is_devengada_flow(flow: IvaFlowDirection) -> bool:
    """Return ``True`` iff ``flow`` contributes to cuota devengada.

    Canonical predicate for the ledger / modelo registries when
    aggregating cuota devengada totals — equivalent to
    ``flow in {REPERCUTIDO, INVERSION_SUJETO_PASIVO}`` but anchored to the
    substrate's settlement-side codification so downstream consumers
    don't have to re-enumerate the mapping.
    """
    return _flow_direction_catalogue().is_devengada(flow)


def is_deducible_flow(flow: IvaFlowDirection) -> bool:
    """Return ``True`` iff ``flow`` contributes to cuota deducible.

    Canonical predicate for the ledger / modelo registries when
    aggregating cuota deducible totals — equivalent to
    ``flow in {SOPORTADO, INVERSION_SUJETO_PASIVO}`` but anchored to the
    substrate's settlement-side codification.
    """
    return _flow_direction_catalogue().is_deducible(flow)


def is_inversion_sujeto_pasivo_flow(flow: IvaFlowDirection) -> bool:
    """Return whether ``flow`` is the recipient reverse-charge direction."""
    return flow == _flow_direction_catalogue().recipient_reverse_charge_token


def is_standard_issued_or_received_flow(flow: IvaFlowDirection) -> bool:
    """Return whether ``flow`` is one of the ordinary invoice-side flows."""
    catalogue = _flow_direction_catalogue()
    return flow in {catalogue.issued_token, catalogue.received_token}


def issued_flow_direction() -> IvaFlowDirection:
    """Return the registry-declared flow for an issued invoice."""
    return _flow_direction_catalogue().issued_token


def received_flow_direction() -> IvaFlowDirection:
    """Return the registry-declared flow for a received invoice."""
    return _flow_direction_catalogue().received_token


__all__ = [
    "IvaFlowDirection",
    "IvaSettlementSide",
    "derive_flow_for_classification",
    "flow_direction_for_invoice_kind",
    "is_deducible_flow",
    "is_devengada_flow",
    "is_inversion_sujeto_pasivo_flow",
    "is_standard_issued_or_received_flow",
    "issued_flow_direction",
    "received_flow_direction",
    "settlement_sides_for_flow",
]
