"""Shared helpers for ledger IVA aggregation binding tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import lru_cache
from typing import Final

from .....application.calculations import (
    ObservationEnvelopePayload,
    ResultDispositionProjection,
    normalize_m303_carry_observation_envelope,
    resolve_iva_compensation_annual_partition_binding_values,
)
from .....core import (
    BindingSourceKind,
    CasillaId,
    IvaDeductionEvidenceAuthority,
    IvaDeductionFactKind,
    RegistryAuthorityGrade,
    ResultDisposition,
    derive_result_disposition,
    result_disposition_casilla_ids,
    validated_casilla_id,
)
from .....core.aggregation import BindingAggregation, BindingAggregationOp
from .....core.resources import bundled_path, resources
from .....tests.registry_tree import bundled_registry_tree
from ....iva import (
    IvaCategory,
    IvaDeductionClassificationProvenance,
    IvaExemptionArticle,
    IvaFlowDirection,
    IvaLedgerObservationRole,
    IvaRateKind,
    required_deduction_evidence_authority,
)
from .. import (
    BindingId,
    DataBindingDefinition,
    IvaLedgerObservation,
    ModeloRevision,
    RegistryCalculationResult,
    RegistryModeloObservation,
    calculate_registry_snapshot,
    materialize_relation_binding_values,
    resolve_available_bound_inputs_by_casilla_id,
    resolve_ledger_iva_aggregation_binding_values,
)
from .._binding_selector_utils import selector_as_dict
from .._relations import resolve_relation_values_from_observations
from .._snapshot import build_snapshot

_M303_APP_FILING_CAPTURED_AT = datetime(2027, 1, 20, 9, 0, 0, tzinfo=UTC)


def _deduction_provenance(
    kind: IvaDeductionFactKind,
    *,
    source_locator: str,
) -> IvaDeductionClassificationProvenance:
    """Build fixture provenance from the production kind-to-authority contract."""
    return IvaDeductionClassificationProvenance(
        authority=required_deduction_evidence_authority(kind),
        source_locator=source_locator,
        evidence_digest="a" * 64,
    )


_M303_AUTOREPERCUTIDO_INTERIOR_DEVENGADO_CASILLA: CasillaId = validated_casilla_id(
    "iva.autorepercutido.interior.devengado"
)
_M303_AUTOREPERCUTIDO_INTERIOR_DEDUCIBLE_CASILLA: CasillaId = validated_casilla_id(
    "iva.autorepercutido.interior.deducible"
)
_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_DEVENGADO_CASILLA: CasillaId = validated_casilla_id(
    "iva.autorepercutido.intracomunitaria.devengado"
)
_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_DEDUCIBLE_CASILLA: CasillaId = validated_casilla_id(
    "iva.autorepercutido.intracomunitaria.deducible"
)
_M303_SOPORTADO_IMPORTACIONES_CASILLA: CasillaId = validated_casilla_id("iva.soportado.importaciones")
_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_M303_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = validated_casilla_id("iva.resultado-regimen-general")
_M303_COMPENSACION_GENERADA_PERIODO_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-generada-periodo")
_M390_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.anual.cuota-devengada-total")
_M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.anual.cuota-deducible-total")
_M390_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = validated_casilla_id("iva.anual.resultado-regimen-general")
_M390_RECONCILIACION_DEVENGADA_303_CASILLA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.devengada-303")
_M390_RECONCILIACION_DEDUCIBLE_303_CASILLA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.deducible-303")
_M390_RECONCILIACION_RESULTADO_303_CASILLA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.resultado-303")
_M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA: CasillaId = validated_casilla_id(
    "iva.anual.compensacion-ultimo-periodo-97"
)
_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA: CasillaId = validated_casilla_id(
    "iva.anual.compensacion-generada-ejercicio-no-97"
)
_M303_REPERCUTIDO_GENERAL_BASE_CASILLA: CasillaId = validated_casilla_id("07")
_M303_SOPORTADO_INTERIORES_BASE_CASILLA: CasillaId = validated_casilla_id("28")
_M303_REPERCUTIDO_GENERAL_CUOTA_CASILLA: CasillaId = validated_casilla_id("09")
_M303_SOPORTADO_INTERIORES_CUOTA_CASILLA: CasillaId = validated_casilla_id("29")
_M303_REPERCUTIDO_SUPER_REDUCIDO_BASE_CASILLA: CasillaId = validated_casilla_id("01")
_M303_REPERCUTIDO_REDUCIDO_BASE_CASILLA: CasillaId = validated_casilla_id("04")


@lru_cache(maxsize=1)
def _modelo_303_revision() -> ModeloRevision:
    modelo = resources().modelos.get("303")
    return modelo.revisions["2022"]


def _binding(binding_id: str = "modelo-303-iva-repercutido-general-cuota") -> DataBindingDefinition:
    return next(item for item in _modelo_303_revision().bindings if item.id == binding_id)


def _with_selector(binding: DataBindingDefinition, **updates: object) -> DataBindingDefinition:
    return binding.model_copy(update={"selector": {**selector_as_dict(binding), **updates}})


def _with_aggregation(binding: DataBindingDefinition, op: BindingAggregationOp) -> DataBindingDefinition:
    return binding.model_copy(update={"aggregation": BindingAggregation(op=op)})


def _filing_result_disposition(result: RegistryCalculationResult) -> ResultDisposition:
    """Use the production result-disposition resolver at this test filing boundary."""
    casilla_ids = result_disposition_casilla_ids("303")
    assert casilla_ids is not None
    disposition = derive_result_disposition(
        "303",
        {casilla_id: Decimal(result.values[casilla_id]) for casilla_id in casilla_ids},
    )
    assert disposition is not None
    return disposition


#: The tiers on which a real line always carries a rate, so a fixture that omits
#: one is modelling a row no production path can mint.
_DOMESTIC_RATE_TIERS: Final[frozenset[IvaRateKind]] = frozenset(
    {IvaRateKind.GENERAL, IvaRateKind.REDUCED, IvaRateKind.SUPER_REDUCED},
)


def _observation(
    *,
    ledger_id: str = "ledger-1",
    txn_date: date = date(2025, 6, 15),
    category: IvaCategory = IvaCategory.DOMESTIC_GENERAL,
    exemption_article: IvaExemptionArticle | None = None,
    rate_kind: IvaRateKind = IvaRateKind.GENERAL,
    flow: IvaFlowDirection = IvaFlowDirection.REPERCUTIDO,
    base: Decimal = Decimal("1000"),
    iva: Decimal = Decimal("210"),
    recargo: Decimal = Decimal("0"),
    applied_rate: Decimal | None = None,
    deduction_fact_kind: IvaDeductionFactKind | None = None,
    deduction_authority: IvaDeductionEvidenceAuthority | None = None,
) -> IvaLedgerObservation:
    """Build an observation fixture, requiring the rate on the domestic tiers.

    ``applied_rate`` is MANDATORY whenever ``rate_kind`` is general, reducido or
    super-reducido, because every production path that mints such an observation
    supplies it: the ledger classifier refuses a transaction with no ``iva_rate``
    before classification and derives the tier FROM the rate, and the invoice
    classifier reads the rate off the line's slot. A fixture omitting it models a
    row production cannot produce, which is how a binding narrowed to a specific
    rate came to look like a silent under-declaration when it was not.

    It is NOT defaulted from ``rate_kind``, and that is deliberate rather than
    ergonomic. Deriving a rate from a tier is the one inference production
    explicitly refuses: the tier-to-rate mapping is date-dependent, so it answers
    "what does this tier mean today" when the question is "what was this line
    actually charged". A tier default would be silently wrong for exactly the
    rows this matters for -- a 2024 reducido line charged 7,5 % or 5 %, or a
    super-reducido line charged 2 % -- and the fixture would pass while encoding
    a rate the statute did not offer on that date.

    Left optional for every other tier, where production legitimately leaves it
    unset: an exempt or not-subject line carries no rate to state.
    """
    if rate_kind in _DOMESTIC_RATE_TIERS and applied_rate is None:
        raise AssertionError(
            f"fixture builds a {rate_kind.value} observation with no applied_rate; "
            "every production path supplies one on the domestic tiers, so this models "
            "a row that cannot occur. State the rate the line carried.",
        )
    if deduction_fact_kind is None and deduction_authority is not None:
        raise AssertionError("deduction evidence authority cannot be stated without its fact kind")
    if deduction_fact_kind is not None and deduction_authority not in {
        None,
        required_deduction_evidence_authority(deduction_fact_kind),
    }:
        raise AssertionError("fixture deduction authority disagrees with the production kind-to-authority contract")
    deduction_provenance = (
        _deduction_provenance(
            deduction_fact_kind,
            source_locator=f"test-ledger:{ledger_id}",
        )
        if deduction_fact_kind is not None
        else None
    )
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=txn_date,
        category=category,
        exemption_article=exemption_article,
        rate_kind=rate_kind,
        flow_direction=flow,
        base_amount=base,
        iva_amount=iva,
        recargo_amount=recargo,
        applied_rate=applied_rate,
        deduction_fact_kind=deduction_fact_kind,
        deduction_provenance=deduction_provenance,
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _revision_with_bindings(*bindings: DataBindingDefinition) -> ModeloRevision:
    return _modelo_303_revision().model_copy(update={"bindings": bindings})


def _calculate_303_from_observations(
    *,
    filing_year: int,
    period: str,
    observations: tuple[IvaLedgerObservation, ...],
) -> RegistryCalculationResult:
    # Stays on ``resources().modelos.authority`` (unlike the M390 helper below):
    # M303 snapshots include the compiled annual-Orden authority, and the
    # production access point is the only source of that cross-cutting
    # projection -- bypassing it via ``load_registry_tree`` would silently
    # produce a partial snapshot rather than a scoped one.
    snapshot = resources().modelos.authority.snapshot("303", filing_year=filing_year, period=period)
    binding_values = {
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        "modelo-303-autoconsumo-promotor-base": Decimal("0"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
        **resolve_ledger_iva_aggregation_binding_values(snapshot.revision, observations),
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": observations[-1].transaction_date},
    )


def _empty_register_bienes_inversion_binding_values(
    revision: ModeloRevision,
) -> dict[BindingId, Decimal]:
    """Zero the capital-goods regularización bindings for a no-register scenario.

    These annual ledger/303 reconciliation fixtures carry no bienes de inversión
    register, so the ``bienes_inversion_regularizacion`` source resolves to its
    empty-register zero (LIVA arts. 107-110): nothing acquired, nothing to
    regularise. This mirrors the empty-register branch of the live
    ``BienesInversionRegularizacionSourceResolver``, keeping the fixture faithful
    to the calculate-path mesh without pulling a profile register into a pure
    registry-engine test.
    """
    return {
        binding.id: Decimal("0.00")
        for binding in revision.bindings
        if binding.source == BindingSourceKind.BIENES_INVERSION_REGULARIZACION
    }


def _calculate_390_from_observations_and_303_filings(
    *,
    filing_year: int,
    observations: tuple[IvaLedgerObservation, ...],
    quarterly_results: dict[str, RegistryCalculationResult],
) -> RegistryCalculationResult:
    # Scoped to M390 alone, at calculation grade -- this computes an IVA
    # aggregation result, never a filing claim -- rather than through
    # ``resources().modelos.authority``, whose ``.load()`` validates every
    # modelo in the bundled tree before returning anything.
    modelos, catalogues = bundled_registry_tree()
    modelo_390 = next(modelo for modelo in modelos if modelo.id == "390")
    snapshot = build_snapshot(
        modelo_390,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period="0A",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    ledger_binding_values = resolve_ledger_iva_aggregation_binding_values(snapshot.revision, observations)
    m303_observations = tuple(
        RegistryModeloObservation(
            modelo="303",
            filing_year=filing_year,
            period=period,
            observations=result.observations,
        )
        for period, result in quarterly_results.items()
    )
    normalized_m303_envelopes = tuple(
        normalize_m303_carry_observation_envelope(
            ObservationEnvelopePayload(
                observation=observation,
                captured_at=_M303_APP_FILING_CAPTURED_AT,
                source_kind="app_filing",
                stamped_revision_id=str(
                    resources()
                    .modelos.authority.snapshot(
                        "303",
                        filing_year=filing_year,
                        period=period,
                    )
                    .revision.id
                ),
                result_disposition=ResultDispositionProjection(
                    disposition=_filing_result_disposition(result),
                    provenance_kind="app_filing",
                    provenance_locator=f"test-local-filing:{filing_year}:{period}",
                ),
            ),
        )
        for (period, result), observation in zip(
            quarterly_results.items(),
            m303_observations,
            strict=True,
        )
    )
    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        m303_observations,
        filing_year=filing_year,
        period="0A",
    )
    relation_binding_values = materialize_relation_binding_values(snapshot.revision, relation_values, period="0A")
    annual_partition_values = resolve_iva_compensation_annual_partition_binding_values(
        snapshot.revision,
        normalized_m303_envelopes,
        filing_year=filing_year,
    )
    binding_values = {
        **ledger_binding_values,
        **relation_binding_values,
        **annual_partition_values,
        **_empty_register_bienes_inversion_binding_values(snapshot.revision),
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(filing_year, 12, 31)},
    )
