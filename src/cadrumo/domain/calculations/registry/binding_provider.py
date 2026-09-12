"""The closed union of value providers a binding declaration may name.

A binding says where a form slot's value comes from. That "where" used to be a
pair: an open ``source`` token beside an untyped ``selector`` mapping, hydrated
into a per-family model by a lookup dict and re-validated by a second one. The
pair could disagree, the serialised form carried no tag, and every consumer
re-derived the member it was holding.

:data:`BindingProvider` replaces the pair with one discriminated union. Each
member is the family's own selector model, now carrying the ``kind`` literal
that used to live in the sibling ``source`` field, so the declaration is
self-describing: it validates to exactly one member, serialises with its own
tag, and reads back to the same member without a second field to consult.

Membership is the authored set. :class:`~cadrumo.core.aggregation.BindingSourceKind`
carries two mesh-only members -- ``borrador`` and ``iva_wallet_decision`` --
which name runtime value routes that no registry row may declare; they are
absent here, which is what makes "not a registry binding source" a type error
rather than a hand-written refusal.

The five invoice-family members share :class:`~.invoice_bindings.InvoiceProviderBase`
rather than collapsing into one member: a union member carries exactly one
``kind``, and the direction a row declares (payable, collectible, the combined
M347 third-party total) is the fact its resolver and its clave classification
turn on.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from .bienes_inversion_regularizacion_bindings import BienesInversionRegularizacionProvider
from .bindings_previous_filing import PreviousFilingProvider
from .design_constant_bindings import DesignConstantProvider
from .detail_record_bindings import (
    AtribucionMemberProvider,
    ForeignAssetProvider,
    RefundOperationProvider,
    RelatedPartyOperationProvider,
)
from .donativo_bindings import DonativoDonorProvider
from .gasto193_bindings import Gasto193ContributorProvider
from .inventory_bindings import InventoryProvider
from .invoice_bindings import (
    CollectibleInvoiceProvider,
    LedgerTransactionProvider,
    M347ThirdPartyOperationProvider,
    PayableInvoiceProvider,
    PurchaseInvoiceEvidenceProvider,
)
from .irnr_ledger_bindings import LedgerIrnrIncomeProvider
from .iva_compensation_annual_partition_bindings import IvaCompensationAnnualPartitionProvider
from .ledger_impatriado_bindings import LedgerImpatriadoIncomeProvider
from .ledger_iva_bindings import LedgerIvaProvider
from .ledger_oss_bindings import LedgerOssProvider
from .ledger_renta_gastos_estimacion_directa_bindings import LedgerRentaGastosEstimacionDirectaProvider
from .ledger_renta_gastos_pago_fraccionado_bindings import LedgerRentaGastosPagoFraccionadoProvider
from .ledger_renta_income_bindings import LedgerRentaIncomeProvider
from .m303_regimen_simplificado_annual_summary_bindings import M303RegimenSimplificadoAnnualSummaryProvider
from .manual_input_selector import ManualInputProvider
from .profile_bindings import ProfileProvider
from .prorrata_regularizacion_bindings import ProrrataRegularizacionProvider
from .relation_prefill_bindings import RelationPrefillProvider
from .retenciones_bindings import RetencionesAggregationProvider
from .withholding296_bindings import Withholding296Provider
from .withholding_bindings import WithholdingProvider

__all__ = ["BindingProvider"]


BindingProvider = Annotated[
    ManualInputProvider
    | DesignConstantProvider
    | ProfileProvider
    | PreviousFilingProvider
    | RelationPrefillProvider
    | IvaCompensationAnnualPartitionProvider
    | M303RegimenSimplificadoAnnualSummaryProvider
    | ProrrataRegularizacionProvider
    | BienesInversionRegularizacionProvider
    | LedgerIvaProvider
    | LedgerOssProvider
    | LedgerRentaIncomeProvider
    | LedgerRentaGastosEstimacionDirectaProvider
    | LedgerRentaGastosPagoFraccionadoProvider
    | LedgerImpatriadoIncomeProvider
    | LedgerIrnrIncomeProvider
    | RetencionesAggregationProvider
    | WithholdingProvider
    | Withholding296Provider
    | LedgerTransactionProvider
    | PurchaseInvoiceEvidenceProvider
    | PayableInvoiceProvider
    | CollectibleInvoiceProvider
    | M347ThirdPartyOperationProvider
    | ForeignAssetProvider
    | RelatedPartyOperationProvider
    | AtribucionMemberProvider
    | RefundOperationProvider
    | DonativoDonorProvider
    | Gasto193ContributorProvider
    | InventoryProvider,
    Field(discriminator="kind"),
]
"""Every provider a registry binding may declare, discriminated on ``kind``."""
