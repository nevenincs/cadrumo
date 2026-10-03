"""Tests for the central per-modelo aggregation service.

The suite pins :func:`~application.aggregation.aggregate_per_modelo` as the
application-owned dispatch boundary for retenciones, counterpart, and foreign
asset provider families. It verifies the immutable command/result contracts,
the canonical :class:`~core.BindingSourceKind` taxonomy, foreign-assets
source-mesh parity, and the retenciones collapse onto
:meth:`~application.aggregation.RetencionesAggregationSourceResolver.aggregate`.

See Also:
    :mod:`~application.aggregation.service`
        Service contracts and dispatch implementation under test.
    :class:`~application.aggregation.PerModeloAggregationCommand`
        Strict command envelope that selects the provider family.
    :class:`~application.aggregation.PerModeloAggregationResult`
        Typed result envelope checked for provider/payload coherence.
    :class:`~application.aggregation.foreign_assets.ForeignAssetsAggregationSourceResolver`
        Foreign-assets resolver compared with Modelo 720 row projections.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from ....core.aggregation import (
    BindingSourceKind,
    CounterpartSourceKind,
    ForeignAssetClass,
    RetencionScheme,
)
from ....core.errors.error_codes import get_registered_error_code
from ....core.foreign_asset_obligation import MODELO_720_FOREIGN_ASSET_CLASS_CODES, M720AssetClassCode
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from ....domain.calculations.registry.temporal import select_revision
from ....domain.calculations.registry.tests.registry_tree import bundled_registry_tree
from ....domain.foreign_assets.register import (
    ForeignAssetDeclarationEntry,
    ForeignAssetRegister,
    ForeignAssetRegisterEntry,
    M720AssetIdentifier,
    M720DeclarantCondition,
    M720IdentifierScheme,
)
from ....domain.foreign_assets.valuation import M720ValuationEvent
from .._preconditions import AggregationPreconditionCondition
from ..counterpart import (
    CounterpartAggregation,
    CounterpartObservation,
)
from ..errors import (
    AggregationConfigError,
    AggregationUnsupportedModeloError,
)
from ..foreign_assets import (
    ForeignAssetIngestObservation,
    ForeignAssetsAggregation,
    ForeignAssetsAggregationSourceResolver,
    aggregate_foreign_assets_720,
    declarable_asset_classes_720,
)
from ..modelo_bindings_retenciones import RetencionesAggregationSourceResolver
from ..retenciones import (
    Modelo180PropertyEvidence,
    Modelo180StructuredAddress,
    RetencionesAggregation,
    RetencionObservation,
    aggregate_retenciones_111,
    aggregate_retenciones_115,
    aggregate_retenciones_123,
    aggregate_retenciones_180,
    aggregate_retenciones_190,
    aggregate_retenciones_193,
)
from ..service import (
    PerModeloAggregationCommand,
    PerModeloAggregationContributor,
    PerModeloAggregationLogFields,
    PerModeloAggregationResult,
    _registered_per_modelo_provider_modelos,
    aggregate_per_modelo,
    provider_for_modelo,
)
from ..source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_P_2025_Q1 = Period.from_year_and_code(2025, "1T")
_P_2025_ANNUAL = Period.from_year_and_code(2025, "0A")


def _retencion_obs(*, source_kind: BindingSourceKind = BindingSourceKind.LEDGER_TRANSACTION) -> RetencionObservation:
    return RetencionObservation(
        source_kind=source_kind,
        source_object_id=f"{source_kind.value}-ret-1",
        perceptor_nif="B00000001",
        perceptor_name="Proveedor Retencion",
        scheme=RetencionScheme("rendimientos_trabajo"),
        taxable_base=Decimal("1000.00"),
        retencion_amount=Decimal("150.00"),
        accrued_on="2025-03-01",
    )


def _counterpart_obs(
    *,
    nif: str = "B00000001",
    name: str = "Cliente Counterpart",
    source_kind: CounterpartSourceKind = BindingSourceKind.LEDGER_TRANSACTION,
    source_id: str | None = None,
    operation_kind: str = "entregas_y_prestaciones",
    country: str = "ES",
    invoice_total: str = "2000.00",
) -> CounterpartObservation:
    return CounterpartObservation(
        source_kind=source_kind,
        source_object_id=source_id or f"{source_kind}-ctr-1",
        counterparty_nif=nif,
        counterparty_name=name,
        counterparty_country=country,
        operation_kind=operation_kind,
        operation_period="0A",
        taxable_base=Decimal(invoice_total),
        invoice_total=Decimal(invoice_total),
        accrued_on="2025-03-01",
        groi_verified=True,
        nif_iva_verified=True,
    )


def _ledger_identity(label: str) -> str:
    """Return a stable canonical transaction identity for a readable test label.

    A ledger-sourced foreign-asset observation must carry a real hex-64
    transaction identity: the resolver copies it into
    ``source_transaction_ids``, which feeds the strict identity field on the
    persisted calculation revision.
    """
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _asset_obs(
    *,
    source_kind: BindingSourceKind = BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
    source_id: str | None = None,
    asset_class: ForeignAssetClass = ForeignAssetClass.ACCOUNT,
    asset_external_id: str | None = None,
    country: str = "AD",
    valuation: str = "50000.01",
    acquisition_date: str = "2023-01-15",
) -> ForeignAssetIngestObservation:
    declared_source_id = source_id or f"{source_kind.value}-asset-1"
    return ForeignAssetIngestObservation(
        source_kind=source_kind,
        source_object_id=(
            _ledger_identity(declared_source_id)
            if source_kind is BindingSourceKind.LEDGER_TRANSACTION
            else declared_source_id
        ),
        asset_ref=_asset_ref(asset_external_id or f"{source_kind.value}-account"),
        asset_class=asset_class,
        asset_external_id=asset_external_id or f"{source_kind.value}-account",
        country=country,
        valuation_amount=Decimal(valuation),
        currency_code="EUR",
        valuation_event=M720ValuationEvent.YEAR_END,
        acquisition_date=acquisition_date,
    )


def _asset_ref(label: str) -> str:
    return "m720a_" + hashlib.sha256(label.encode("utf-8")).hexdigest()[:32]


_SCHEMES = {
    "C": M720IdentifierScheme.ACCOUNT_CODE,
    "V": M720IdentifierScheme.NO_ISIN_ISSUER_COUNTRY,
    "I": M720IdentifierScheme.NO_ISIN_ISSUER_COUNTRY,
}


def _register_for(observations: tuple[ForeignAssetIngestObservation, ...]) -> ForeignAssetRegister:
    """Register and declare, as sole holder, every asset of a declarable 720 class the lots name."""
    assets = []
    for observation in observations:
        code = MODELO_720_FOREIGN_ASSET_CLASS_CODES[observation.asset_class]
        scheme = _SCHEMES.get(code.value, M720IdentifierScheme.NONE)
        if scheme is M720IdentifierScheme.NO_ISIN_ISSUER_COUNTRY and not observation.asset_external_id.startswith("Z"):
            continue  # below its block floor in these fixtures, so never joined
        assets.append(
            ForeignAssetRegisterEntry(
                asset_ref=observation.asset_ref,
                asset_class=code,
                subclave=None if code is M720AssetClassCode.INSTITUCION_INVERSION_COLECTIVA else 1,
                country_code=observation.country,
                identifier=M720AssetIdentifier(
                    scheme=scheme,
                    value="" if scheme is M720IdentifierScheme.NONE else observation.asset_external_id,
                ),
                description="synthetic asset",
            ),
        )
    return ForeignAssetRegister(
        assets=tuple(assets),
        declarations=tuple(
            ForeignAssetDeclarationEntry(
                asset_ref=asset.asset_ref, condition=M720DeclarantCondition.TITULAR, participation_pct=Decimal("100.00")
            )
            for asset in assets
        ),
    )


def _m720_row(index: int, *, label: str, asset_class: str, country: str, valuation: str, acquired: str) -> dict:
    return {
        ("modelo-720-asset-row-asset-ref", index): _asset_ref(label),
        ("modelo-720-asset-row-valuation-event", index): "year_end",
        ("modelo-720-asset-row-valuation-event-date", index): "",
        ("modelo-720-asset-row-class", index): asset_class,
        ("modelo-720-asset-row-country", index): country,
        ("modelo-720-asset-row-currency", index): "EUR",
        ("modelo-720-asset-row-identifier", index): label,
        ("modelo-720-asset-row-valuation", index): Decimal(valuation),
        ("modelo-720-asset-row-acquisition-date", index): acquired,
    }


def test_command_contract_is_strict_and_immutable() -> None:
    command = PerModeloAggregationCommand(
        modelo="111",
        period=_P_2025_Q1,
        retencion_observations=(_retencion_obs(),),
    )

    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        assert (
            provider_for_modelo(command.modelo, operation=_authority_operation_for_test)
            is PerModeloAggregationContributor.RETENCIONES
        )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PerModeloAggregationCommand.model_validate(
            {
                "modelo": "111",
                "period": _P_2025_Q1,
                "retencion_observations": (_retencion_obs(),),
                "unexpected": "field",
            },
        )
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        command.period = Period.from_year_and_code(2025, "2T")


def test_routing_one_modelo_agrees_with_the_registry_wide_inventory() -> None:
    """Every modelo routes to exactly the family the full inventory assigns it.

    Routing classifies the requested modelo from its own revisions rather than
    projecting the whole registry, so the two must be proven to agree over the
    live registry -- including that a modelo outside every family still refuses.
    Building the inventory also runs its one-family-per-modelo check.
    """
    with _indexed_authority_for_test().operation() as operation:
        assigned = {
            modelo: contributor
            for contributor, modelos in _registered_per_modelo_provider_modelos(operation=operation).items()
            for modelo in modelos
        }
        unassigned = [modelo for modelo in operation.modelo_ids() if modelo not in assigned]
        routed = {modelo: provider_for_modelo(modelo, operation=operation) for modelo in assigned}
        assert unassigned, "every registry modelo has a family, so the refusal branch is unproven"
        with pytest.raises(AggregationUnsupportedModeloError):
            provider_for_modelo(unassigned[0], operation=operation)

    assert set(assigned.values()) == set(PerModeloAggregationContributor), (
        "a provider family owns no registry modelo, so its routing is compared over nothing"
    )
    assert routed == assigned


def test_period_boundary_accepts_period_dict_for_roundtrip() -> None:
    command = PerModeloAggregationCommand.model_validate(
        {"modelo": "111", "period": {"filing_year": 2025, "code": "1T"}},
    )
    log_fields = PerModeloAggregationLogFields.model_validate(
        {
            "modelo": "111",
            "period": command.model_dump()["period"],
            "provider": PerModeloAggregationContributor.RETENCIONES,
            "observation_count": 0,
            "source_kind_count": 0,
            "result_row_count": 0,
        },
    )

    assert command.period == _P_2025_Q1
    assert log_fields.period == _P_2025_Q1


def test_period_boundary_rejects_combined_period_string() -> None:
    with pytest.raises(ValidationError) as command_exc:
        PerModeloAggregationCommand.model_validate({"modelo": "111", "period": "2026Q1"})
    with pytest.raises(ValidationError) as log_fields_exc:
        PerModeloAggregationLogFields.model_validate(
            {
                "modelo": "111",
                "period": "2026Q1",
                "provider": PerModeloAggregationContributor.RETENCIONES,
                "observation_count": 0,
                "source_kind_count": 0,
                "result_row_count": 0,
            },
        )

    assert command_exc.value.errors()[0]["loc"] == ("period",)
    assert log_fields_exc.value.errors()[0]["loc"] == ("period",)


def test_service_routes_retenciones_modelos_to_retenciones_aggregation() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        command = PerModeloAggregationCommand(
            modelo="111",
            period=_P_2025_Q1,
            retencion_observations=(_retencion_obs(source_kind=BindingSourceKind.LEDGER_TRANSACTION),),
        )

        result = aggregate_per_modelo(command, operation=_authority_operation_for_test)

        assert result.provider is PerModeloAggregationContributor.RETENCIONES
        assert isinstance(result.aggregation, RetencionesAggregation)
        assert result.aggregation.total_retencion == Decimal("150.00")
        assert result.source_kinds == (BindingSourceKind.LEDGER_TRANSACTION,)
        assert result.log_fields.as_extra().for_logging() == {
            "service_name": "per_modelo_aggregation",
            "modelo": "111",
            "period": "1T",
            "provider": "retenciones",
            "observation_count": 1,
            "source_kind_count": 1,
            "result_row_count": 1,
        }


def test_service_routes_counterpart_modelos_and_preserves_threshold_semantics() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        observations = (
            _counterpart_obs(source_kind=BindingSourceKind.LEDGER_TRANSACTION, invoice_total="1500.00"),
            _counterpart_obs(source_kind=BindingSourceKind.PAYABLE_INVOICE, invoice_total="1505.07"),
        )
        command = PerModeloAggregationCommand(
            modelo="347",
            period=_P_2025_ANNUAL,
            counterpart_observations=observations,
        )

        result = aggregate_per_modelo(command, operation=_authority_operation_for_test)

        assert result.provider is PerModeloAggregationContributor.COUNTERPART
        assert isinstance(result.aggregation, CounterpartAggregation)
        assert result.source_kinds == (
            BindingSourceKind.LEDGER_TRANSACTION,
            BindingSourceKind.PAYABLE_INVOICE,
        )


def test_service_routes_foreign_asset_modelos_and_preserves_threshold_semantics() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        observations = (
            _asset_obs(source_kind=BindingSourceKind.PURCHASE_INVOICE_EVIDENCE, valuation="25000.00"),
            _asset_obs(source_kind=BindingSourceKind.PAYABLE_INVOICE, valuation="25000.01"),
        )
        command = PerModeloAggregationCommand(
            modelo="720",
            period=_P_2025_ANNUAL,
            foreign_asset_observations=observations,
        )

        result = aggregate_per_modelo(command, operation=_authority_operation_for_test)

        assert result.provider is PerModeloAggregationContributor.FOREIGN_ASSETS
        assert isinstance(result.aggregation, ForeignAssetsAggregation)
        assert result.source_kinds == (
            BindingSourceKind.PAYABLE_INVOICE,
            BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
        )
        assert declarable_asset_classes_720(result.aggregation) == frozenset({ForeignAssetClass.ACCOUNT})


def test_foreign_assets_m720_registry_rows_match_prior_aggregate_exactly() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        observations = (
            _asset_obs(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                source_id="tx-account-ad",
                asset_external_id="AD-ACCOUNT-001",
                country="AD",
                valuation="40000.00",
                acquisition_date="2020-01-15",
            ),
            _asset_obs(
                source_kind=BindingSourceKind.PAYABLE_INVOICE,
                source_id="payable-account-ch",
                asset_external_id="CH-ACCOUNT-002",
                country="CH",
                valuation="15000.00",
                acquisition_date="2021-02-20",
            ),
            _asset_obs(
                source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
                source_id="small-security",
                asset_class=ForeignAssetClass.SECURITY,
                asset_external_id="LI-SECURITY-001",
                country="LI",
                valuation="1000.00",
                acquisition_date="2022-03-25",
            ),
        )
        expected_aggregation = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)
        service_result = aggregate_per_modelo(
            PerModeloAggregationCommand(
                modelo="720",
                period=_P_2025_ANNUAL,
                foreign_asset_observations=observations,
            ),
            operation=_authority_operation_for_test,
        )
        _modelos, _catalogues = bundled_registry_tree()
        _modelo_720 = next(candidate for candidate in _modelos if candidate.id == "720")
        snapshot = SimpleNamespace(revision=select_revision(_modelo_720, filing_year=2025, period="0A"))
        context = CalculationSourceContext(
            bucket_id="operator",
            modelo="720",
            filing_year=2025,
            period=_P_2025_ANNUAL,
            revision=snapshot.revision,
        )
        resolution = ForeignAssetsAggregationSourceResolver(
            observations=observations, register_loader=lambda: _register_for(observations)
        ).resolve(context)

        assert service_result.aggregation == expected_aggregation
        assert dict(resolution.row_binding_values) == {
            **_m720_row(
                1, label="AD-ACCOUNT-001", asset_class="C", country="AD", valuation="40000.00", acquired="2020-01-15"
            ),
            **_m720_row(
                2, label="CH-ACCOUNT-002", asset_class="C", country="CH", valuation="15000.00", acquired="2021-02-20"
            ),
        }
        assert resolution.binding_values == {}
        assert resolution.source_transaction_ids == (_ledger_identity("tx-account-ad"),)
        # Ledger-side rows carry no primary provenance until the register join
        # grounds it; the contributing sources stay visible through
        # source_transaction_ids.
        assert resolution.provenance == ()


def test_foreign_assets_m720_mixed_valores_block_selects_both_rows_and_provenance() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        observations = (
            _asset_obs(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                source_id="tx-security-li",
                asset_class=ForeignAssetClass.SECURITY,
                asset_external_id="ZLI",
                country="LI",
                valuation="30000.00",
                acquisition_date="2020-01-15",
            ),
            _asset_obs(
                source_kind=BindingSourceKind.PAYABLE_INVOICE,
                source_id="payable-insurance-ch",
                asset_class=ForeignAssetClass.INSURANCE,
                asset_external_id="CH-INSURANCE-001",
                country="CH",
                valuation="25000.00",
                acquisition_date="2021-02-20",
            ),
        )
        expected_aggregation = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)
        service_result = aggregate_per_modelo(
            PerModeloAggregationCommand(
                modelo="720",
                period=_P_2025_ANNUAL,
                foreign_asset_observations=observations,
            ),
            operation=_authority_operation_for_test,
        )
        _modelos, _catalogues = bundled_registry_tree()
        _modelo_720 = next(candidate for candidate in _modelos if candidate.id == "720")
        snapshot = SimpleNamespace(revision=select_revision(_modelo_720, filing_year=2025, period="0A"))
        context = CalculationSourceContext(
            bucket_id="operator",
            modelo="720",
            filing_year=2025,
            period=_P_2025_ANNUAL,
            revision=snapshot.revision,
        )
        resolution = ForeignAssetsAggregationSourceResolver(
            observations=observations, register_loader=lambda: _register_for(observations)
        ).resolve(context)

        assert service_result.aggregation == expected_aggregation
        assert declarable_asset_classes_720(expected_aggregation) == frozenset(
            {
                ForeignAssetClass.SECURITY,
                ForeignAssetClass.INSURANCE,
            },
        )
        assert dict(resolution.row_binding_values) == {
            **_m720_row(
                1, label="CH-INSURANCE-001", asset_class="S", country="CH", valuation="25000.00", acquired="2021-02-20"
            ),
            **_m720_row(2, label="ZLI", asset_class="V", country="LI", valuation="30000.00", acquired="2020-01-15"),
        }
        assert resolution.binding_values == {}
        assert resolution.source_transaction_ids == (_ledger_identity("tx-security-li"),)
        # Ledger-side rows carry no primary provenance until the register join
        # grounds it; the contributing sources stay visible through
        # source_transaction_ids.
        assert resolution.provenance == ()


def test_command_rejects_observations_from_non_selected_provider_family() -> None:
    """The rejected family rides the machine facts, not an authored sentence.

    The refusal names the offending provider family in its context rather than
    in its message, so a Catalan, Spanish or Hungarian session keeps the same
    detail an English reader gets.
    """
    command = PerModeloAggregationCommand(
        modelo="111",
        period=_P_2025_Q1,
        foreign_asset_observations=(_asset_obs(),),
    )
    with (
        _indexed_authority_for_test().operation() as operation,
        pytest.raises(AggregationConfigError, match=r"aggregation\.service\.errors\.observations_mismatch") as exc_info,
    ):
        aggregate_per_modelo(command, operation=operation)

    assert exc_info.value.context == {"names": "foreign_assets", "modelo": "111"}


def test_unsupported_modelo_uses_registered_aggregation_error() -> None:
    command = PerModeloAggregationCommand(modelo="999", period=_P_2025_ANNUAL)
    with (
        _indexed_authority_for_test().operation() as operation,
        pytest.raises(AggregationUnsupportedModeloError, match="unsupported_modelo") as exc_info,
    ):
        aggregate_per_modelo(command, operation=operation)

    error = exc_info.value
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == AggregationPreconditionCondition.PER_MODELO_MODELO_SUPPORTED.value
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values["modelo"] == "999"
    assert get_registered_error_code(error).code == "REFUSED_FINANCIAL_AGGREGATION_UNSUPPORTED_MODELO"


def test_modelo_whitespace_is_rejected_before_dispatch() -> None:
    command = PerModeloAggregationCommand(
        modelo=" 347 ",
        period=_P_2025_ANNUAL,
        counterpart_observations=(_counterpart_obs(),),
    )
    with (
        _indexed_authority_for_test().operation() as operation,
        pytest.raises(AggregationUnsupportedModeloError, match="unsupported_modelo") as exc_info,
    ):
        aggregate_per_modelo(command, operation=operation)

    assert exc_info.value.context == {"modelo": " 347 "}


def test_result_contract_rejects_incoherent_envelope_payload() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        aggregation_payload = aggregate_per_modelo(
            PerModeloAggregationCommand(
                modelo="347",
                period=_P_2025_ANNUAL,
                counterpart_observations=(_counterpart_obs(),),
            ),
            operation=_authority_operation_for_test,
        ).aggregation

        with pytest.raises(ValidationError, match=r"aggregation\.service\.errors\.envelope_modelo_mismatch"):
            PerModeloAggregationResult(
                modelo="349",
                period=_P_2025_ANNUAL,
                provider=PerModeloAggregationContributor.COUNTERPART,
                aggregation=aggregation_payload,
                source_kinds=(BindingSourceKind.LEDGER_TRANSACTION,),
                log_fields=PerModeloAggregationLogFields(
                    modelo="349",
                    period=_P_2025_ANNUAL,
                    provider=PerModeloAggregationContributor.COUNTERPART,
                    observation_count=1,
                    source_kind_count=1,
                    result_row_count=1,
                ),
            )


def test_result_contract_rejects_provider_payload_mismatch() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        aggregation_payload = aggregate_per_modelo(
            PerModeloAggregationCommand(
                modelo="111",
                period=_P_2025_Q1,
                retencion_observations=(_retencion_obs(),),
            ),
            operation=_authority_operation_for_test,
        ).aggregation

        with pytest.raises(
            ValidationError,
            match=r"aggregation\.service\.errors\.envelope_provider_payload_mismatch",
        ):
            PerModeloAggregationResult(
                modelo="111",
                period=_P_2025_Q1,
                provider=PerModeloAggregationContributor.COUNTERPART,
                aggregation=aggregation_payload,
                source_kinds=(BindingSourceKind.LEDGER_TRANSACTION,),
                log_fields=PerModeloAggregationLogFields(
                    modelo="111",
                    period=_P_2025_Q1,
                    provider=PerModeloAggregationContributor.COUNTERPART,
                    observation_count=1,
                    source_kind_count=1,
                    result_row_count=1,
                ),
            )


# --- Retenciones dispatch collapse is behaviour-preserving --------------------
#
# The per-modelo service dispatch table and the mesh resolver dispatch table share
# the canonical entry point,
# :meth:`~application.aggregation.RetencionesAggregationSourceResolver.aggregate`, shared by the live calculate
# mesh (``resolve``) and the per-modelo aggregation service (``aggregate_per_modelo``,
# the CLI ``aggregate`` / pull surface). These gates prove the collapse routes each
# modelo to the same core it did before (``aeat-calculation-aggregation``)
# with no value shift and the landed distinct-NIF perceptor count unchanged.

# The pre-existing, independently-tested aggregation cores are the oracle: the collapsed
# path must reproduce them exactly. Deriving expected values from these cores (not from a
# hand-computed formula) keeps the gate non-tautological — a mis-wired dispatch that
# routed, say, M180 to the M111 core would break the equality against the M180 core.
_RETENCIONES_CORE_ORACLE = {
    "111": aggregate_retenciones_111,
    "115": aggregate_retenciones_115,
    "123": aggregate_retenciones_123,
    "180": aggregate_retenciones_180,
    "190": aggregate_retenciones_190,
    "193": aggregate_retenciones_193,
}
_RETENCIONES_PERIOD = {
    "111": _P_2025_Q1,
    "115": _P_2025_Q1,
    "123": _P_2025_Q1,
    "180": _P_2025_ANNUAL,
    "190": _P_2025_ANNUAL,
    "193": _P_2025_ANNUAL,
}


def _urban_property(nif: str) -> Modelo180PropertyEvidence:
    """Complete Modelo 180 property detail, which every annual urban row must carry."""
    return Modelo180PropertyEvidence(
        property_key=f"property-{nif}",
        situation="1",
        cadastral_reference=f"{nif}PROPERTY",
        recipient_province_code="28",
        modality="1",
        accrual_year=2025,
        withholding_percentage=Decimal("19.00"),
        address=Modelo180StructuredAddress(
            province_code="28",
            municipality_code="079",
            municipality="Madrid",
            locality="Madrid",
            postal_code="28001",
            street_type="CL",
            street_name="Ejemplo",
            number_type="NUM",
            house_number="1",
        ),
    )


def _mixed_scheme_retencion_observations() -> tuple[RetencionObservation, ...]:
    """One observation per scheme FAMILY (work / urban / capital), distinct perceptors.

    Each retenciones modelo filters by its own scheme catalogue (111/190 = work,
    115/180 = urban, 123/193 = capital), so this single fixture selects a DISTINCT
    non-empty subset per modelo — which makes the equality-to-oracle assertions bite:
    a dispatch that routed a modelo to the wrong core would select the wrong subset.
    """

    def _obs(*, nif: str, name: str, scheme: RetencionScheme, base: str, ret: str) -> RetencionObservation:
        return RetencionObservation(
            source_kind=BindingSourceKind.LEDGER_TRANSACTION,
            source_object_id=f"ledger_transaction-{nif}",
            perceptor_nif=nif,
            perceptor_name=name,
            scheme=scheme,
            taxable_base=Decimal(base),
            retencion_amount=Decimal(ret),
            accrued_on="2025-03-01",
            modelo_180_property=_urban_property(nif) if scheme == RetencionScheme("arrendamiento_urbano") else None,
        )

    return (
        _obs(
            nif="B00000011",
            name="Trabajo SL",
            scheme=RetencionScheme("rendimientos_trabajo"),
            base="1000.00",
            ret="150.00",
        ),
        _obs(
            nif="B00000022",
            name="Alquiler SL",
            scheme=RetencionScheme("arrendamiento_urbano"),
            base="2000.00",
            ret="380.00",
        ),
        _obs(nif="B00000033", name="Capital SL", scheme=RetencionScheme("intereses"), base="3000.00", ret="570.00"),
    )


@pytest.mark.parametrize("modelo", ["111", "115", "123", "180", "190", "193"])
def test_retenciones_collapse_service_and_mesh_reproduce_prior_core_exactly(modelo: str) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        observations = _mixed_scheme_retencion_observations()
        period = _RETENCIONES_PERIOD[modelo]
        expected = _RETENCIONES_CORE_ORACLE[modelo](observations, period=period)

        # The one canonical mesh-resolver aggregation entry point (the calculate path uses
        # this via ``resolve``) and the per-modelo service (which now delegates to it).
        mesh_value = RetencionesAggregationSourceResolver.aggregate(modelo, observations, period=period)
        service_value = aggregate_per_modelo(
            PerModeloAggregationCommand(modelo=modelo, period=period, retencion_observations=observations),
            operation=_authority_operation_for_test,
        ).aggregation

        assert mesh_value == expected
        assert service_value == expected
        assert isinstance(service_value, RetencionesAggregation)


def test_retenciones_collapse_dispatch_is_not_cross_wired() -> None:
    # Anti-tautology guard: the shared dispatch routes each modelo to a DISTINCT core,
    # so the equality-to-oracle assertions above are not trivially satisfiable. The three
    # quarterly modelos select disjoint scheme families from the same fixture, yielding
    # distinct non-empty rollups; if the dispatch collapsed two modelos onto one core the
    # rollup schemes would coincide and this assertion — plus the oracle equality — fail.
    observations = _mixed_scheme_retencion_observations()
    m111 = RetencionesAggregationSourceResolver.aggregate("111", observations, period=_P_2025_Q1)
    m115 = RetencionesAggregationSourceResolver.aggregate("115", observations, period=_P_2025_Q1)
    m123 = RetencionesAggregationSourceResolver.aggregate("123", observations, period=_P_2025_Q1)

    assert m111.rollups and m115.rollups and m123.rollups
    schemes_by_modelo = {
        "111": {row.scheme for row in m111.rollups},
        "115": {row.scheme for row in m115.rollups},
        "123": {row.scheme for row in m123.rollups},
    }
    assert schemes_by_modelo == {
        "111": {RetencionScheme("rendimientos_trabajo")},
        "115": {RetencionScheme("arrendamiento_urbano")},
        "123": {RetencionScheme("intereses")},
    }
    assert len({m111.total_retencion, m115.total_retencion, m123.total_retencion}) == 3


def test_retenciones_collapse_preserves_landed_distinct_nif_perceptor_count() -> None:
    # The distinct-NIF perceptor-count result (on the annual summary
    # modelos 180/193) must be unchanged by the collapse. Two urban observations with
    # distinct NIFs must still count as two perceptors through the one shared path.
    observations = (
        RetencionObservation(
            source_kind=BindingSourceKind.LEDGER_TRANSACTION,
            source_object_id="ledger_transaction-urban-a",
            perceptor_nif="B00000041",
            perceptor_name="Arrendador A",
            scheme=RetencionScheme("arrendamiento_urbano"),
            taxable_base=Decimal("1200.00"),
            retencion_amount=Decimal("228.00"),
            accrued_on="2025-03-01",
            modelo_180_property=_urban_property("B00000041"),
        ),
        RetencionObservation(
            source_kind=BindingSourceKind.LEDGER_TRANSACTION,
            source_object_id="ledger_transaction-urban-b",
            perceptor_nif="B00000042",
            perceptor_name="Arrendador B",
            scheme=RetencionScheme("arrendamiento_urbano"),
            taxable_base=Decimal("800.00"),
            retencion_amount=Decimal("152.00"),
            accrued_on="2025-06-01",
            modelo_180_property=_urban_property("B00000042"),
        ),
    )
    expected = aggregate_retenciones_180(observations, period=_P_2025_ANNUAL)
    mesh_value = RetencionesAggregationSourceResolver.aggregate("180", observations, period=_P_2025_ANNUAL)

    assert expected.total_perceptors == 2
    assert mesh_value == expected
    assert mesh_value.total_perceptors == 2


def test_service_surface_has_no_cli_dependency() -> None:
    import sys
    import textwrap

    from cadrumo.tests.audited_process import run_audited_process

    script = textwrap.dedent("""\
        import importlib
        import sys

        for module_name in (
            "cadrumo.application.aggregation",
            "cadrumo.application.aggregation.service",
        ):
            importlib.import_module(module_name)

        leaked = sorted(
            name
            for name in sys.modules
            if name == "typer" or name.startswith("typer.") or name.startswith("cadrumo.entrypoints.cli")
        )
        assert leaked == [], leaked
    """)
    result = run_audited_process(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        f"aggregation service imported a CLI-only dependency.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
