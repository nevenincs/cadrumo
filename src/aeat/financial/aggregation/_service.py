"""Aggregation service from classified transactions to casilla inputs."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...casillas import ModeloCode as CategoryModeloCode
from ...financial.categories import (
    CasillaMapping,
    CategoryProfile,
    ProportionalityKind,
    SpendingCategory,
    load_category_profiles_from_manual,
)
from ...models import ModeloCode
from ..transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    is_classified,
)
from ._errors import (
    AggregationCasillaMappingError,
    AggregationCategoryCoverageError,
    AggregationMissingClassificationError,
    AggregationPeriodError,
    AggregationUnsupportedModeloError,
    t,
)
from ._models import CasillaAggregation, CasillaProvenance, Period, PeriodKind

_ZERO = Decimal("0")
_ONE = Decimal("1")
_SUPPORTED_MODELOS = {ModeloCode.MODELO_130}
_MODELO_130_INPUT_CASILLAS = frozenset({"01", "02", "05", "06", "08", "10", "13", "15", "16", "18"})


def aggregate_catalogue(
    catalogue: TransactionCatalogue,
    *,
    modelo: str | ModeloCode,
    period: str | Period,
    category_profiles: Mapping[SpendingCategory, CategoryProfile] | None = None,
) -> CasillaAggregation:
    """Aggregate a classified transaction catalogue into casilla totals."""

    modelo_code = _parse_modelo(modelo)
    if modelo_code not in _SUPPORTED_MODELOS:
        raise AggregationUnsupportedModeloError(
            translated_message=t(
                "La agregacion T6 solo esta implementada para Modelo 130.",
                "T6 aggregation is currently implemented only for Modelo 130.",
                "A T6 osszesites jelenleg csak a 130-as nyomtatvanyhoz elerheto.",
            ),
            context={"modelo": modelo_code.value},
        )
    resolved_period = period if isinstance(period, Period) else Period.model_validate(period)
    if resolved_period.kind is not PeriodKind.QUARTERLY:
        raise AggregationPeriodError(
            translated_message=t(
                "Modelo 130 requiere un periodo trimestral.",
                "Modelo 130 requires a quarterly period.",
                "A 130-as nyomtatvany negyedeves idoszakot igenyel.",
            ),
            context={"period": resolved_period.raw},
        )
    resolved_profiles = category_profiles or _category_profiles_for_year(resolved_period.year)

    in_period = tuple(
        transaction
        for transaction in catalogue.values()
        if resolved_period.contains(transaction.raw.value_date or transaction.raw.booked_date)
    )
    missing = tuple(tx.transaction_id for tx in in_period if not is_classified(tx.business_classification))
    if missing:
        raise AggregationMissingClassificationError(
            translated_message=t(
                "Hay transacciones del periodo sin clasificacion de negocio.",
                "Some transactions in this period still need business classification.",
                "Az idoszakban vannak uzleti besorolas nelkuli tranzakciok.",
            ),
            context={"period": resolved_period.raw, "transaction_ids": ", ".join(sorted(missing))},
            suggestion="aeat financial txs classify <transaction-id> --as BUSINESS --category <category>",
        )

    totals: dict[str, Decimal] = {}
    provenance_buckets: dict[tuple[str, str | None], list[tuple[str, Decimal]]] = {}
    for transaction in in_period:
        contribution = _transaction_contribution(
            transaction,
            modelo=modelo_code,
            period=resolved_period,
            category_profiles=resolved_profiles,
        )
        if contribution is None:
            continue
        casilla, category_id, amount = contribution
        if amount == _ZERO:
            continue
        totals[casilla] = totals.get(casilla, _ZERO) + amount
        provenance_buckets.setdefault((casilla, category_id), []).append((transaction.transaction_id, amount))

    provenance = tuple(
        CasillaProvenance(
            casilla=casilla,
            category_id=category_id,
            transaction_ids=tuple(sorted(transaction_id for transaction_id, _ in rows)),
            subtotal=sum((amount for _, amount in rows), _ZERO),
        )
        for (casilla, category_id), rows in sorted(
            provenance_buckets.items(),
            key=lambda item: (item[0][0], item[0][1] or ""),
        )
    )
    return CasillaAggregation(
        modelo=modelo_code.value,
        period=resolved_period,
        casilla_values=totals,
        provenance=provenance,
    )


def _category_profiles_for_year(year: int) -> Mapping[SpendingCategory, CategoryProfile]:
    try:
        return load_category_profiles_from_manual(year)
    except ValueError as exc:
        raise AggregationCasillaMappingError(
            translated_message=t(
                "No hay perfiles fiscales de categorias para el ejercicio solicitado.",
                "No fiscal category profiles are available for the requested tax year.",
                "A kert adoevre nem erheto el adozasi kategoriaprofil.",
            ),
            context={"year": year},
        ) from exc


def _transaction_contribution(
    transaction: Transaction,
    *,
    modelo: ModeloCode,
    period: Period,
    category_profiles: Mapping[SpendingCategory, CategoryProfile],
) -> tuple[str, str | None, Decimal] | None:
    if transaction.business_classification is BusinessClassification.PERSONAL:
        return None
    if transaction.direction is TransactionDirection.INTERNAL_TRANSFER:
        return None

    business_factor = _business_factor(transaction)
    if transaction.direction is TransactionDirection.INCOMING:
        return ("01", transaction.category_id, abs(transaction.raw.amount) * business_factor)

    category = _require_category(transaction)
    profile = category_profiles.get(category)
    if profile is None:
        raise AggregationCategoryCoverageError(
            translated_message=t(
                "La categoria de una transaccion no tiene perfil fiscal.",
                "A transaction category has no fiscal profile.",
                "Egy tranzakcio kategoriajahoz nincs adozasi profil.",
            ),
            context={"transaction_id": transaction.transaction_id, "category_id": category.value},
        )
    factor = business_factor * _profile_factor(transaction, profile)
    casilla = _resolve_casilla(profile, modelo=modelo, period=period, transaction=transaction)
    return (casilla, category.value, abs(transaction.raw.amount) * factor)


def _business_factor(transaction: Transaction) -> Decimal:
    if transaction.business_classification is BusinessClassification.MIXED:
        assert transaction.business_pct is not None
        return transaction.business_pct
    return _ONE


def _profile_factor(transaction: Transaction, profile: CategoryProfile) -> Decimal:
    rule = profile.proportionality
    if rule.kind is ProportionalityKind.NON_DEDUCTIBLE:
        return _ZERO
    if rule.kind is ProportionalityKind.FIXED_PERCENTAGE:
        assert rule.fixed_pct is not None
        return rule.fixed_pct
    if rule.default_ratio is not None:
        return rule.default_ratio
    return _ONE


def _require_category(transaction: Transaction) -> SpendingCategory:
    if transaction.category_id is None:
        raise AggregationCategoryCoverageError(
            translated_message=t(
                "Una transaccion de gasto de negocio no tiene categoria fiscal.",
                "A business expense transaction has no fiscal category.",
                "Egy uzleti kiadas tranzakcionak nincs adozasi kategoriaja.",
            ),
            context={"transaction_id": transaction.transaction_id},
            suggestion="aeat financial txs classify <transaction-id> --category <category>",
        )
    try:
        return SpendingCategory(transaction.category_id)
    except ValueError as exc:
        raise AggregationCategoryCoverageError(
            translated_message=t(
                "La categoria de una transaccion no existe en el catalogo fiscal.",
                "A transaction category is not in the fiscal category catalogue.",
                "Egy tranzakcio kategoriaja nincs az adozasi katalogusban.",
            ),
            context={"transaction_id": transaction.transaction_id, "category_id": transaction.category_id},
        ) from exc


def _resolve_casilla(
    profile: CategoryProfile,
    *,
    modelo: ModeloCode,
    period: Period,
    transaction: Transaction,
) -> str:
    mappings = tuple(
        mapping
        for mapping in profile.casilla_mappings
        if _mapping_modelo(mapping) == modelo and mapping.period_type is period.period_type
    )
    if not mappings:
        raise AggregationCasillaMappingError(
            translated_message=t(
                "La categoria no tiene mapeo de casilla para este modelo y periodo.",
                "The category has no casilla mapping for this modelo and period.",
                "A kategorianak nincs casilla-lekepezese ehhez a nyomtatvanyhoz es idoszakhoz.",
            ),
            context={
                "transaction_id": transaction.transaction_id,
                "category_id": profile.category.value,
                "modelo": modelo.value,
            },
        )
    if len(mappings) != 1:
        raise AggregationCasillaMappingError(
            translated_message=t(
                "La categoria tiene mas de un mapeo de casilla compatible.",
                "The category has more than one compatible casilla mapping.",
                "A kategorianak egynel tobb kompatibilis casilla-lekepezese van.",
            ),
            context={
                "transaction_id": transaction.transaction_id,
                "category_id": profile.category.value,
                "modelo": modelo.value,
                "mapping_count": len(mappings),
            },
        )
    mapping = mappings[0]
    if modelo is ModeloCode.MODELO_130:
        if mapping.casilla_code == "01":
            return "02"
        if mapping.casilla_code not in _MODELO_130_INPUT_CASILLAS:
            raise AggregationCasillaMappingError(
                translated_message=t(
                    "El mapeo de la categoria apunta a una casilla calculada o no compatible.",
                    "The category mapping points to a computed or incompatible casilla.",
                    "A kategoria lekepezese szamitott vagy nem kompatibilis casillara mutat.",
                ),
                context={
                    "transaction_id": transaction.transaction_id,
                    "category_id": profile.category.value,
                    "modelo": modelo.value,
                    "casilla": mapping.casilla_code,
                },
            )
        return mapping.casilla_code
    return mapping.casilla_code


def _mapping_modelo(mapping: CasillaMapping) -> ModeloCode | None:
    if mapping.modelo is CategoryModeloCode.MODELO_130:
        return ModeloCode.MODELO_130
    if mapping.modelo is CategoryModeloCode.MODELO_303:
        return ModeloCode.MODELO_303
    if mapping.modelo is CategoryModeloCode.MODELO_390:
        return ModeloCode.MODELO_390
    return None


def _parse_modelo(modelo: str | ModeloCode) -> ModeloCode:
    if isinstance(modelo, ModeloCode):
        return modelo
    text = modelo.strip().upper()
    for candidate in ModeloCode:
        if text in {candidate.value, candidate.name}:
            return candidate
    raise AggregationUnsupportedModeloError(
        translated_message=t(
            "Modelo desconocido para agregacion financiera.",
            "Unknown modelo for financial aggregation.",
            "Ismeretlen nyomtatvany penzugyi osszesiteshez.",
        ),
        context={"modelo": modelo},
    )


__all__ = ["aggregate_catalogue"]
