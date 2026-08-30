"""Route a received invoice's retención into the one per-perceptor store.

Retención arithmetic is identical on both kinds of invoice and means opposite
things. On an ISSUED invoice the payer withholds from what they owe the
taxpayer and remits it on the taxpayer's account: the taxpayer is the
*retenido* and the amount is a CREDIT against the pago fraccionado (RIRPF
art. 110.3.a). On a RECEIVED invoice from a resident professional the taxpayer
is the obligated *retenedor* and the amount is a LIABILITY settled to AEAT
through Modelo 111 and its annual summary.

Those two destinations already exist and neither is here. The credit reaches
the M130/M100 retenciones casilla through the renta income ledger. The
liability's canonical home is the per-perceptor retención store behind the
``retenciones_aggregation`` binding family, whose committed M111 bindings
already read it. This module is the projection into that store and nothing
else: it builds the same :class:`~._retenciones.RetencionObservation` the
operator-declared path builds, so a received invoice becomes one more
observation in the one store rather than a second retención path with its own
totals to reconcile.

**The scheme is not inferred.** Which retención scheme a payment falls under --
trabajo, actividades económicas, actividades profesionales, premios -- is a
legal fact about the perceptor's activity, not a property of the invoice. An
invoice record carries no field that settles it, and the closed IRPF-category
enum that might is deliberately deferred to its own decision. So the caller
declares it, and this module refuses to guess: choosing a scheme here would
file a figure under a clave the taxpayer never asserted.

The production caller is the ``modelo aggregate`` CLI: an operator (or the LLM
operator on their behalf) declares ``(invoice, scheme)`` pairs via
``--received-invoice-retencion``, and :func:`merge_manual_and_routed_retencion_observations`
unions the resulting observations with any hand-typed
``--retencion-observation`` rows into the ONE set the CLI passes to
``persist_retencion_observations`` -- never two separate persist calls for one
window, since that write is set-replace.

See Also:
    :mod:`~._retenciones`
        The observation type, the aggregators, and the source-kind taxonomy.
    :mod:`~._retencion_observations_repository`
        The encrypted per-perceptor store this projection feeds through
        ``persist_retencion_observations``, the one shared write path every
        producer calls.
    :class:`~cadrumo.domain.iva.IvaRetencionRole`
        The declared per-(category, kind) role this module routes on, rather
        than re-deriving the direction from the invoice kind.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Self

from pydantic import BaseModel, model_validator

from ...core.aggregation import BindingSourceKind
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.identity import InvoiceId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...domain.iva.components import IvaRetencionRole, category_components
from ._retenciones import RetencionObservation, RetencionScheme
from .errors import AggregationValidationError, t

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from ...domain.invoices.models import Invoice

_SPANISH_COUNTRY_CODE: Final[str] = "ES"


class InvoiceRetencionProjectionDefect(StrEnum):
    """Why one invoice's retención did not become a store observation.

    Every member EXCLUDES the invoice from the retenciones store and is
    reported rather than dropped. None of them is a refusal to record the
    invoice itself -- the record stays in the catalogue and stays editable.
    """

    NOT_A_RETENEDOR_LIABILITY = "not_a_retenedor_liability"
    """The Axis-A role for this invoice is not a liability the taxpayer owes.

    Most often the invoice is issued, so its retención is the taxpayer's
    CREDIT: routing it here would declare them retenedor for money withheld
    FROM them, inverting the direction of a tax liability. It is not a missing
    figure; it belongs to the income side and is already carried there. The
    same member covers a (category, kind) pair whose role is ``NONE`` or
    ``UNKNOWN`` -- neither is a liability this store may assert.
    """

    IVA_TREATMENT_UNDECLARED = "iva_treatment_undeclared"
    """No IVA category is declared, so the retención role cannot be read.

    The role is per ``(category, kind)`` pair, so without a category there is
    no row to consult and the direction of the amount is unknown. Guessing it
    from the kind alone is exactly the re-derivation this module refuses.
    """

    NO_RETENCION_DECLARED = "no_retencion_declared"
    """The invoice declares no withheld amount, or declares it as zero.

    Nothing to route. Most received invoices are in this state legitimately.
    """

    NON_RESIDENT_SUPPLIER = "non_resident_supplier"
    """The supplier is not Spanish-resident, so Modelo 111 is the wrong home.

    The retenedor obligation on payments to non-residents runs through the IRNR
    surface, not the IRPF per-perceptor family this store feeds. Excluding is
    the conservative direction: it surfaces the invoice for the operator rather
    than filing a figure under a modelo that does not govern it.
    """

    FX_UNRESOLVED = "fx_unresolved"
    """A non-euro invoice carries no resolved conversion rate.

    The euro base and retención are unknown, and the store holds euro figures.
    """

    MISSING_COUNTERPARTY_TAX_ID = "missing_counterparty_tax_id"
    """A factura simplificada declared a retención but names no perceptor.

    Modelo 111 requires the perceptor's NIF; an invoice may legitimately carry
    no ``counterparty_tax_id`` (RD 1619/2012 art. 6.1.d), but a supplier
    withholding tax is one of the cases that article makes the tax id
    mandatory for regardless, so this exclusion should be rare in practice.
    """


INVOICE_RETENCION_DEFECT_GUIDANCE: Final[Mapping[InvoiceRetencionProjectionDefect, str]] = MappingProxyType(
    {
        InvoiceRetencionProjectionDefect.NOT_A_RETENEDOR_LIABILITY: (
            "an issued invoice's retención is a credit against the pago fraccionado, "
            "already carried by the renta income ledger; it does not belong to the retenedor store"
        ),
        InvoiceRetencionProjectionDefect.IVA_TREATMENT_UNDECLARED: (
            "declare the invoice's IVA treatment (iva_category) so the retención role can be read"
        ),
        InvoiceRetencionProjectionDefect.NO_RETENCION_DECLARED: (
            "record the withheld amount on the invoice if the supplier's factura shows a retención"
        ),
        InvoiceRetencionProjectionDefect.NON_RESIDENT_SUPPLIER: (
            "a withholding on a non-resident supplier is settled through the IRNR surface, not Modelo 111"
        ),
        InvoiceRetencionProjectionDefect.FX_UNRESOLVED: (
            "resolve the invoice's conversion rate; the retenciones store holds euro figures"
        ),
        InvoiceRetencionProjectionDefect.MISSING_COUNTERPARTY_TAX_ID: (
            "record the supplier's counterparty_tax_id; Modelo 111 cannot file a retención "
            "without identifying the perceptor"
        ),
    },
)
"""Operator remediation per defect, so the surfacing layer renders guidance it did not invent."""


class InvoiceRetencionProjection(BaseModel):
    """The verdict for one invoice: a store observation, or why there is none.

    ``observation`` and ``defects`` are mutually exclusive and jointly
    exhaustive, enforced below, so a reader never has to interpret a null.

    Attributes:
        invoice_id: The record this verdict is about.
        observation: The routed observation, present iff the invoice routes.
        defects: Why it did not route, non-empty iff it did not.
    """

    model_config = _STRICT_FROZEN

    invoice_id: InvoiceId
    observation: RetencionObservation | None
    defects: tuple[InvoiceRetencionProjectionDefect, ...]

    @model_validator(mode="after")
    def _validate_outcome_is_unambiguous(self) -> Self:
        """Refuse a verdict that is neither clearly routed nor clearly excluded."""
        if (self.observation is None) != bool(self.defects):
            raise AggregationValidationError(
                t("aggregation.invoice_retencion.errors.projection_outcome_ambiguous"),
                context={
                    "invoice_id": self.invoice_id,
                    "has_observation": self.observation is not None,
                    "defect_count": len(self.defects),
                },
            )
        if len(set(self.defects)) != len(self.defects):
            raise AggregationValidationError(
                t("aggregation.invoice_retencion.errors.projection_defects_repeat"),
                context={
                    "invoice_id": self.invoice_id,
                    "defect_count": len(self.defects),
                    "distinct_defect_count": len(set(self.defects)),
                },
            )
        return self

    @property
    def is_routed(self) -> bool:
        """Whether this invoice produced a store observation."""
        return self.observation is not None


class InvoiceRetencionRouting(BaseModel):
    """Both outcome classes for a set of invoices, in one object.

    The excluded half travels with the routed half so a caller cannot persist
    what routed without holding what did not -- an excluded retención is a
    liability the taxpayer may still owe, and losing it silently is the failure
    this whole surface exists to prevent.

    Attributes:
        observations: The observations to persist into the per-perceptor store.
        excluded: Verdicts that did not route and must be surfaced.
    """

    model_config = _STRICT_FROZEN

    observations: tuple[RetencionObservation, ...]
    excluded: tuple[InvoiceRetencionProjection, ...]


class InvoiceRetencionRouteRequest(BaseModel):
    """One operator-declared ``(invoice, scheme)`` pair to route at aggregation time.

    The wire shape the ``modelo aggregate`` CLI parses ``--received-invoice-retencion``
    JSON into. The scheme is supplied here rather than read off the invoice for the
    same reason :func:`project_received_invoice_retencion` never infers it: it is a
    legal fact about the perceptor's activity the invoice record does not carry.
    """

    model_config = _STRICT_FROZEN

    invoice_id: InvoiceId
    scheme: RetencionScheme


def project_received_invoice_retencion(
    invoice: Invoice,
    *,
    scheme: RetencionScheme,
) -> InvoiceRetencionProjection:
    """Project one received invoice's declared retención into a store observation.

    Never raises for an unroutable invoice: it comes back carrying defects, which
    is the outcome the caller surfaces.

    Args:
        invoice: An already-valid invoice record.
        scheme: The declared retención scheme. A legal fact about the
            perceptor's activity that the invoice does not carry, so it is
            supplied rather than inferred.

    Returns:
        The verdict, carrying either the routed observation or the defects that
        excluded it.
    """
    defects = tuple(_defects_for(invoice))
    if defects:
        return InvoiceRetencionProjection(invoice_id=invoice.invoice_id, observation=None, defects=defects)
    base = invoice.base_total_eur
    retencion = invoice.retention_amount_eur
    # Both are non-None here: an unresolved conversion and an absent retención
    # are defects, so neither reaches this branch.
    if base is None or retencion is None:  # pragma: no cover - guarded by the defect sweep
        raise AggregationValidationError(
            t("aggregation.invoice_retencion.errors.euro_figures_unavailable_after_defect_sweep"),
            context={"invoice_id": invoice.invoice_id},
        )
    if invoice.counterparty_tax_id is None:  # pragma: no cover - guarded by the defect sweep
        raise AggregationValidationError(
            t("aggregation.invoice_retencion.errors.perceptor_tax_id_unavailable_after_defect_sweep"),
            context={"invoice_id": invoice.invoice_id},
        )
    return InvoiceRetencionProjection(
        invoice_id=invoice.invoice_id,
        observation=RetencionObservation(
            source_kind=BindingSourceKind.PAYABLE_INVOICE,
            source_object_id=invoice.invoice_id,
            perceptor_nif=invoice.counterparty_tax_id,
            perceptor_name=invoice.counterparty_name,
            scheme=scheme,
            taxable_base=base,
            retencion_amount=retencion,
            accrued_on=invoice.issued_at.isoformat(),
        ),
        defects=(),
    )


def route_invoice_retenciones(
    entries: Iterable[tuple[Invoice, RetencionScheme]],
) -> InvoiceRetencionRouting:
    """Route many invoices, keeping the excluded ones alongside the routed ones.

    Args:
        entries: Pairs of an invoice and its declared retención scheme.

    Returns:
        The observations to persist and the verdicts that did not route.
    """
    observations: list[RetencionObservation] = []
    excluded: list[InvoiceRetencionProjection] = []
    for invoice, scheme in entries:
        projection = project_received_invoice_retencion(invoice, scheme=scheme)
        if projection.observation is not None:
            observations.append(projection.observation)
        else:
            excluded.append(projection)
    return InvoiceRetencionRouting(observations=tuple(observations), excluded=tuple(excluded))


def merge_manual_and_routed_retencion_observations(
    manual_observations: Sequence[RetencionObservation],
    routed_observations: Sequence[RetencionObservation],
) -> tuple[RetencionObservation, ...]:
    """Union hand-typed and invoice-routed observations for one persist call.

    ``persist_retencion_observations`` is a SET-REPLACE write: whatever this
    returns becomes the *entire* per-perceptor window for one
    ``(modelo, filing_year, period)``, so a caller must union every source
    before persisting rather than call it once per source. Rather than pick a
    winner when the operator has *also* hand-typed an observation this module
    would independently route from the same invoice, the union refuses --  a
    bound value has one writer, and a silent pick would either double-count
    the invoice's retención in the per-perceptor rollup or silently drop
    whichever side lost.

    Args:
        manual_observations: Observations the operator declared directly (a
            ledger-sourced retención, or a hand-typed invoice observation).
        routed_observations: Observations :func:`route_invoice_retenciones`
            produced for this same persist call.

    Returns:
        The union of both sequences, manual observations first.

    Raises:
        AggregationValidationError: A manual observation shares its
            ``(source_kind, source_object_id)`` identity with a routed one --
            the same invoice was both hand-typed and auto-routed in one call.
    """
    routed_identities = {(obs.source_kind, obs.source_object_id) for obs in routed_observations}
    colliding = sorted(
        {
            obs.source_object_id
            for obs in manual_observations
            if (obs.source_kind, obs.source_object_id) in routed_identities
        },
    )
    if colliding:
        raise AggregationValidationError(
            t("aggregation.retenciones.errors.invoice_retencion_collision"),
            context={"source_object_ids": ", ".join(colliding)},
        )
    return (*manual_observations, *routed_observations)


def _defects_for(invoice: Invoice) -> Iterable[InvoiceRetencionProjectionDefect]:
    """Yield every reason the invoice does not route.

    Accumulating rather than short-circuiting, so an operator fixing a record
    sees everything wrong with it in one pass.

    The direction test reads the Axis-A ``retencion_role`` rather than
    re-deriving it from the invoice kind. The role is declared per
    ``(category, kind)`` pair and validated against that kind at authoring
    time, so consulting it keeps one definition of whose money a retención is;
    a local ``kind is RECEIVED`` test would be a second, unvalidated copy of
    the same fact, free to drift from the table the rest of the engine reads.
    """
    if invoice.iva_category is None:
        yield InvoiceRetencionProjectionDefect.IVA_TREATMENT_UNDECLARED
    elif category_components(invoice.iva_category, invoice.kind).retencion_role is not (
        IvaRetencionRole.TAXPAYER_LIABILITY
    ):
        yield InvoiceRetencionProjectionDefect.NOT_A_RETENEDOR_LIABILITY
    if invoice.retention_amount is None or invoice.retention_amount == Decimal("0"):
        yield InvoiceRetencionProjectionDefect.NO_RETENCION_DECLARED
    if invoice.counterparty_country != _SPANISH_COUNTRY_CODE:
        yield InvoiceRetencionProjectionDefect.NON_RESIDENT_SUPPLIER
    if invoice.currency != DEFAULT_CURRENCY and invoice.fx_rate is None:
        yield InvoiceRetencionProjectionDefect.FX_UNRESOLVED
    if invoice.counterparty_tax_id is None:
        yield InvoiceRetencionProjectionDefect.MISSING_COUNTERPARTY_TAX_ID


__all__ = [
    "INVOICE_RETENCION_DEFECT_GUIDANCE",
    "InvoiceRetencionProjection",
    "InvoiceRetencionProjectionDefect",
    "InvoiceRetencionRouteRequest",
    "InvoiceRetencionRouting",
    "merge_manual_and_routed_retencion_observations",
    "project_received_invoice_retencion",
    "route_invoice_retenciones",
]
