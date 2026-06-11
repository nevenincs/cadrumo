"""Core aggregation taxonomy shared across application and adapter layers."""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal

from .logging import get_logger

_log = get_logger(__name__)


class AggregationSourceKind(StrEnum):
    """Accepted source-kind taxonomy for per-modelo aggregation providers.

    Consumer search (C4 / ledger-invoice-unification, recorded 2026-06-11) of
    every ``AggregationSourceKind.INVOICE`` site established that the bare
    ``invoice`` member is NOT a dead alias safe to delete in this pass — it is
    the named token of a *contradictory dual-state* validation surface that a
    clean retirement must first reconcile:

    * It is a member of the ``DataBindingDefinition.source`` ``Literal`` in
      ``_schema.py``, so a binding may be *constructed* with ``source="invoice"``
      (several registry tests rely on ``model_validate({"source": "invoice"})``
      / ``model_copy(update={"source": "invoice"})`` to build the fixture).
    * ``_validate_record_sections.py`` routes ``invoice`` to
      ``validate_invoice_binding_definition`` (a *positive* validator), and
      ``test_export.py`` + ``test_registry_schema_part1.py`` depend on that
      route firing the invoice-selector / aggregation guards.
    * ``_bindings.py`` (``validate_binding_selector_shape``) and
      ``_retenciones.py`` simultaneously *reject* ``invoice`` as "retired", and
      ``test_selector_shape.py`` asserts that rejection text.

    Removing the member therefore breaks the schema ``Literal`` construction
    path that ~6 registry test files exercise as a positive fixture; the
    operator-facing CLI unification (the C4 deliverable) is orthogonal and does
    not require it. The retirement is deferred to a dedicated registry-validation
    reconciliation that migrates those fixtures onto a real source kind
    (e.g. ``collectible_invoice``) and collapses the dual-state to a single
    reject path. The bare ``invoice`` member carries no production binding
    today (no registry TOML declares ``source = "invoice"``); it survives only
    as the guard token until that reconciliation lands.
    """

    INVOICE = "invoice"
    LEDGER_TRANSACTION = "ledger_transaction"
    PURCHASE_INVOICE_EVIDENCE = "purchase_invoice_evidence"
    PAYABLE_INVOICE = "payable_invoice"
    COLLECTIBLE_INVOICE = "collectible_invoice"


type CounterpartSourceKind = Literal[
    AggregationSourceKind.LEDGER_TRANSACTION,
    AggregationSourceKind.PURCHASE_INVOICE_EVIDENCE,
    AggregationSourceKind.PAYABLE_INVOICE,
    AggregationSourceKind.COLLECTIBLE_INVOICE,
]
"""Canonical source-kind subset accepted by counterpart aggregation.

The retired bare ``invoice`` alias remains in :class:`AggregationSourceKind`
for persisted-registry validation and explicit rejection, but it is not a
valid counterpart observation or binding source.
"""

COUNTERPART_SOURCE_KINDS: Final[frozenset[CounterpartSourceKind]] = frozenset(
    {
        AggregationSourceKind.LEDGER_TRANSACTION,
        AggregationSourceKind.PURCHASE_INVOICE_EVIDENCE,
        AggregationSourceKind.PAYABLE_INVOICE,
        AggregationSourceKind.COLLECTIBLE_INVOICE,
    },
)


def counterpart_source_kind(value: object) -> CounterpartSourceKind:
    """Return ``value`` narrowed to the counterpart source-kind subset."""
    try:
        source_kind = value if isinstance(value, AggregationSourceKind) else AggregationSourceKind(value)
    except ValueError as exc:
        raise ValueError(f"unsupported source_kind {value!r}") from exc
    if source_kind in COUNTERPART_SOURCE_KINDS:
        return source_kind
    raise ValueError(
        "unsupported source_kind; use one of ledger_transaction, "
        "purchase_invoice_evidence, payable_invoice, collectible_invoice",
    )


class PeriodKind(StrEnum):
    """Authoritative period cadences shared across aggregation and deadline layers.

    Placed in :mod:`aeat.core` (cross-layer home) so the deadline domain and
    application aggregation layer can both import without violating the
    hexagonal direction (domain → core is always legal; domain → application
    is forbidden).
    """

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class RowSetGroupingKind(StrEnum):
    """Canonical row-set source-kind discriminators for detail-record assembly.

    Placed in :mod:`aeat.core` (cross-layer home) because both the application
    assembly layer and the domain registry schema reference these values, and
    domain → application imports are forbidden under the hexagonal contract.
    """

    WITHHOLDING = "withholding"
    RELATED_PARTY = "related_party"
    FOREIGN_ASSET = "foreign_asset"
    ATRIBUCION = "atribucion"
    REFUND = "refund"


class RetencionScheme(StrEnum):
    """Closed catalogue of retenciones schemes across the retenciones family.

    Each scheme maps to one of the casillas (or grouped casillas) on a
    retenciones modelo form. The mapping from scheme to modelo lives in the
    per-modelo entry-point functions; this enum is the union. Declared in
    :mod:`aeat.core` as a closed value set per the architecture contract.
    """

    # Modelo 111 schemes (quarterly retenciones IRPF on labor + activities)
    WORK_INCOME = "rendimientos_trabajo"  # clave A
    ECONOMIC_ACTIVITY = "actividades_economicas"  # clave G
    PROFESSIONAL = "actividades_profesionales"  # clave H (subset of G)
    PRIZE = "premios"  # clave I (lottery, prize)
    # Modelo 115 schemes (urban rental withholding)
    URBAN_RENTAL = "arrendamiento_urbano"  # locales de negocio
    # Modelo 123 schemes (capital mobiliario, dividends, interest)
    CAPITAL_INTEREST = "intereses"  # clave I (interest income)
    CAPITAL_DIVIDEND = "dividendos"  # clave A (dividend income)
    CAPITAL_OTHER = "otros_capital_mobiliario"  # clave C (other capital income)


class OperationKind347(StrEnum):
    """Modelo 347 operation kinds (clave de operación).

    Source: AEAT Modelo 347 instrucciones. Declared in :mod:`aeat.core` as a
    closed value set per the architecture contract.
    """

    DELIVERY = "entregas_y_prestaciones"  # clave A
    ACQUISITION = "adquisiciones_y_recepciones"  # clave B
    INSURANCE = "operaciones_seguros"  # clave C
    RENTAL = "arrendamientos_locales"  # clave D
    SUBSIDY = "subvenciones_y_ayudas"  # clave E


class OperationKind349(StrEnum):
    """Modelo 349 intracomunitarias operation kinds.

    Source: AEAT Modelo 349 instrucciones. The clave maps from the underlying
    directionality (entrega/adquisición) and operation type (bienes/servicios).
    """

    INTRA_DELIVERY = "entrega_intracomunitaria_bienes"  # clave E
    INTRA_ACQUISITION = "adquisicion_intracomunitaria_bienes"  # clave A
    INTRA_SERVICE_OUT = "prestacion_servicios_intracom"  # clave S
    INTRA_SERVICE_IN = "adquisicion_servicios_intracom"  # clave I
    TRIANGULAR = "triangular"  # clave T


class ForeignAssetClass(StrEnum):
    """Modelo 720 asset classes (clave de tipo de bien).

    Source: AEAT Modelo 720 instrucciones. Each class is declared separately;
    the declarability gate (50,000 EUR per class) is applied after the
    aggregator runs. Declared in :mod:`aeat.core` as a closed value set.
    """

    ACCOUNT = "cuenta_entidad_financiera"  # clave C
    SECURITY = "valor_seguro_renta"  # clave V
    REAL_ESTATE = "inmueble_extranjero"  # clave I
    INSURANCE = "seguro_renta_temporal_vitalicia"  # clave S
    VIRTUAL_CURRENCY = "moneda_virtual"  # clave M
