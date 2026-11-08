"""Live source resolver tests for ``prorrata_regularizacion``.

These tests exercise the source-mesh resolver without enrolling it in the mesh:
the resolver consumes current-year registry values supplied by the
materialisation seam and reads the real encrypted prorrata register, filed
Modelo 303 observations and transaction ledger. The AEAT manual's full
regularisation, which needs a real ledger across four quarters, is proven end
to end in ``entrypoints/tests/profile_persistence``; here each refusal and the
Modelo 390 restatement are pinned in isolation.

See Also:
    :class:`~application.calculations.prorrata_regularizacion.ProrrataRegularizacionSourceResolver`
        Live resolver under test for the prorrata regularización source.
    :class:`~adapters.persistence.profile.prorrata_register.ProrrataRegisterRepository`
        Encrypted profile-scoped carry store used by the register-backed branch.
    :class:`~application.aggregation.CalculationSourceContext`
        Source-mesh context passed into resolver execution.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from .....application.aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from .....application.calculations.observations_repository import ResultDispositionProjection
from .....application.calculations.prorrata_regularizacion import ProrrataRegularizacionSourceResolver
from .....application.prorrata_register.sector_lifecycle import settle_sector_definitive
from .....core.aggregation import BindingSourceKind
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import output_language
from .....core.i18n.render import tr as render_tr
from .....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from .....core.modelo import Modelo
from .....core.period import Period
from .....core.prorrata_register import (
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from .....core.result_disposition import ResultDisposition
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.binding_targets import sole_bound_casilla
from .....domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from .....domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_RESULTADO_CASILLA as M303_RESULTADO_CASILLA,
)
from .....domain.calculations.registry.schema import RegistrySnapshot
from .....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_modelo_observation,
    revision_id_for_observation,
)
from .....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from .....domain.iva.prorrata import InputClassification
from .....domain.prorrata_register.register import (
    ProrrataOperatorGrossDeclaration,
    ProrrataRegister,
    ProrrataRegisterEntry,
    SectorDefinition,
)
from .....domain.transactions.enums import BusinessClassification, TransactionDirection
from .....domain.transactions.models import Transaction, TransactionCatalogue
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...storage.tests.secure_sql import isolated_runtime_profile, isolated_two_bucket_runtime
from ..calculation_observations import CalculationObservationRepository
from ..invoices import InvoiceCatalogueRepository
from ..prorrata_register import ProrrataRegisterRepository
from ..transactions import TransactionCatalogueRepository
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "ca06894b-1eb7-4f25-b325-531f43bc0e48"
_FILING_YEAR = 2025
_PRIOR_YEAR = _FILING_YEAR - 1
_CAPTURED_AT = datetime(2026, 1, 20, 10, 0, tzinfo=UTC)
_KEY = "application.calculations.prorrata_regularizacion.unresolved"

_VOLUMEN_CON_DERECHO_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="test casilla id",
)
_VOLUMEN_TOTAL_ID: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")
_PORCENTAJE_ID: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")
_SOPORTADO_INTERIORES_ID: CasillaId = validated_casilla_id("iva.soportado.interiores", surface="test casilla id")
_REGULARIZACION_ID: CasillaId = validated_casilla_id("44", surface="test casilla id")
#: Every deducible cuota box of the 2025 Modelo 303 design, in declaration
#: order, as a filed liquidation records it. A local filing persists every casilla, so a quarter
#: with no input IVA files each of these as zero.
_DEDUCIBLE_CUOTA_IDS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(raw, surface="test casilla id")
    for raw in (
        "35",
        "39",
        "iva.soportado.interiores",
        "iva.autorepercutido.interior.deducible",
        "iva.autorepercutido.intracomunitaria.deducible",
        "iva.soportado.importaciones",
        "iva.soportado.interiores.bienes-inversion",
        "iva.autorepercutido.interior.deducible.bienes-inversion",
        "iva.rectificacion-deducciones.interiores",
        "iva.rectificacion-deducciones.importaciones",
        "iva.rectificacion-deducciones.inversion-sujeto-pasivo",
    )
)

#: Manual práctico de IVA 2025, pp. 137-138: provisional 73%; 25.000 con
#: derecho over 45.000 total give a definitive 56% (art. 104.Dos rounds 55,56
#: up); the box the manual files is -217,60.
_MANUAL_PROVISIONAL_PERCENTAGE = Decimal("73")
_MANUAL_CON_DERECHO = Decimal("25000.00")
_MANUAL_TOTAL = Decimal("45000.00")
_MANUAL_DEFINITIVE_PERCENTAGE = Decimal("56")
_MANUAL_CASILLA_44_REGULARIZACION = Decimal("-217.60")
_M303_BINDING_ID = "modelo-303-prorrata-regularizacion-casilla-44"
_M390_BINDING_ID = "modelo-390-prorrata-regularizacion-anual"


def _current_year_values() -> dict[CasillaId, Decimal]:
    return {
        _VOLUMEN_CON_DERECHO_ID: _MANUAL_CON_DERECHO,
        _VOLUMEN_TOTAL_ID: _MANUAL_TOTAL,
        _PORCENTAJE_ID: _MANUAL_DEFINITIVE_PERCENTAGE,
    }


def _snapshot(modelo: str, period: str) -> RegistrySnapshot:
    return published_authority_operation().snapshot(modelo, filing_year=_FILING_YEAR, period=period)


def _context(
    snapshot: RegistrySnapshot,
    *,
    modelo: str,
    period: str,
    bucket_id: str = _BUCKET_ID,
) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, period),
        revision=snapshot.revision,
    )


def _register_with_carried_prior() -> ProrrataRegister:
    return ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=_FILING_YEAR,
                regime=ProrrataRegisterRegime.from_registry("general"),
                especial_transition=None,
                provisional_percentage=_MANUAL_PROVISIONAL_PERCENTAGE,
                provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
                source_observation_ref=f"{Modelo('303').value}:{_PRIOR_YEAR}:4T",
                source_registry_snapshot_refs=(
                    published_authority_operation().snapshot("303", filing_year=_PRIOR_YEAR, period="4T").snapshot_ref,
                ),
            ),
        ),
    )


def _save_m303_observation(
    repository: CalculationObservationRepository,
    *,
    period: str,
    casilla_values: dict[CasillaId, Decimal],
) -> None:
    observation = registry_grounded_modelo_observation(
        modelo=Modelo("303").value,
        filing_year=_FILING_YEAR,
        period=period,
        casilla_values={**casilla_values, M303_RESULTADO_CASILLA: Decimal("1")},
    )
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind="app_filing",
            captured_at=_CAPTURED_AT,
            result_disposition=ResultDispositionProjection(
                disposition=ResultDisposition.INGRESO,
                provenance_kind="app_filing",
                provenance_locator="test:prorrata-local-filing:declaration-type",
            ),
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )


def _resolve(
    profile_repository: Any,
    *,
    modelo: str,
    period: str,
    authority_operation: PinnedAuthorityOperation,
    register: ProrrataRegister | None = None,
    current_year_values: dict[CasillaId, Decimal] | None = None,
    undeclared: tuple[CasillaId, ...] = (),
    filed: dict[str, dict[CasillaId, Decimal]] | None = None,
    transactions: tuple[Transaction, ...] = (),
    bucket_id: str = _BUCKET_ID,
) -> tuple[CalculationSourceResolution, RegistrySnapshot]:
    register_repository = ProrrataRegisterRepository(bucket_id=bucket_id, objects=profile_repository)
    observation_repository = CalculationObservationRepository(objects=profile_repository)
    transaction_repository = TransactionCatalogueRepository(bucket_id=bucket_id, objects=profile_repository)
    if register is not None:
        register_repository.save(register)
    if transactions:
        transaction_repository.save(TransactionCatalogue.from_transactions(transactions))
    for filed_period, casilla_values in (filed or {}).items():
        _save_m303_observation(observation_repository, period=filed_period, casilla_values=casilla_values)
    snapshot = _snapshot(modelo, period)
    resolution = ProrrataRegularizacionSourceResolver(
        current_year_values=_current_year_values() if current_year_values is None else current_year_values,
        undeclared_current_year_casilla_ids=undeclared,
        prorrata_register_repository=register_repository,
        observation_repository=observation_repository,
        transaction_repository=transaction_repository,
        invoice_reader=InvoiceCatalogueRepository(bucket_id=bucket_id, objects=profile_repository),
        registry_snapshot=snapshot,
        operation=authority_operation,
    ).resolve(_context(snapshot, modelo=modelo, period=period, bucket_id=bucket_id))
    return resolution, snapshot


def _sole_unresolved_message(resolution: CalculationSourceResolution, binding_id: str) -> str:
    assert resolution.binding_values == {}
    assert resolution.unresolved_binding_ids == (binding_id,)
    assert len(resolution.diagnostics) == 1
    diagnostic = resolution.diagnostics[0]
    assert diagnostic.reason == "unresolved_binding"
    assert diagnostic.binding_source is BindingSourceKind.PRORRATA_REGULARIZACION
    assert diagnostic.binding_id == binding_id
    # Rendered from the catalogue, so worded for the filer in the language the catalogue rendered it in.
    assert diagnostic.message_language is OutputLanguage(output_language())
    return diagnostic.message


_QUARTER_MONTH = {"1T": 2, "2T": 5, "3T": 8, "4T": 11}
_ESPECIAL = ProrrataRegisterRegime.from_registry("especial")
_COMMON = InputClassification.from_registry("common")
_EXCLUSIVELY_DEDUCTIBLE = InputClassification.from_registry("exclusively_deductible")
_EXCLUSIVELY_NON_DEDUCTIBLE = InputClassification.from_registry("exclusively_non_deductible")
#: Manual práctico IVA 2025 p. 139: 800 + 160 x 56% = 889,60.
_MANUAL_ESPECIAL_YEAR_DEDUCTION = Decimal("889.60")
_SECTOR_A = "sector-a"
_SECTOR_B = "sector-b"
_SECTOR_PROVISIONAL = {_SECTOR_A: Decimal("80"), _SECTOR_B: Decimal("30")}


def _filed_deduction(interiores: Decimal) -> dict[CasillaId, Decimal]:
    """A filed liquidation's deducible boxes: every box zero except the interior soportado cuota."""
    return {**dict.fromkeys(_DEDUCIBLE_CUOTA_IDS, Decimal("0.00")), _SOPORTADO_INTERIORES_ID: interiores}


def _purchase(
    provider_id: str,
    *,
    period: str,
    cuota: Decimal,
    classification: InputClassification | None = None,
    sector_id: str | None = None,
) -> Transaction:
    """A domestic 10 % purchase with invoice-evidenced deduction authority, booked mid-quarter."""
    booked = date(_FILING_YEAR, _QUARTER_MONTH[period], 10)
    payload: dict[str, object] = {
        "raw": RawTransaction(
            provider_transaction_id=provider_id,
            booked_date=booked,
            value_date=booked,
            amount=cuota * 11,
            currency="EUR",
            counterparty="Proveedor sintetico",
            description=f"factura recibida {provider_id}",
            provenance=RawProvenance(
                source_path=Path(__file__),
                source_sha256="5" * 64,
                source_row_index=1,
                source_format=SourceFormat.MANUAL,
                ingested_at=_CAPTURED_AT,
                provider_name="manual-ledger",
            ),
            raw_fields={"source_kind": "ledger_transaction"},
        ),
        "direction": TransactionDirection.OUTGOING,
        "business_classification": BusinessClassification.BUSINESS,
        "source_jurisdiction": "ES",
        "group_label": None,
        "category_id": "material_oficina",
        "taxable_base": cuota * 10,
        "iva_rate": Decimal("0.10"),
        "iva_amount": cuota,
        "deduction_fact_kind": IvaDeductionFactKind.from_registry("domestic_current"),
        "deduction_provenance": IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
            source_locator=f"invoice:{provider_id}",
            evidence_digest="5" * 64,
        ),
        "classified_at": _CAPTURED_AT,
        "classified_by": "manual",
    }
    if classification is not None:
        payload["input_classification"] = classification
    if sector_id is not None:
        payload["prorrata_sector_id"] = sector_id
    return Transaction.model_validate(payload)


def test_resolver_refuses_construction_without_an_explicit_prorrata_repository() -> None:
    """The dependency is mandatory; callers cannot re-enter a hidden default path."""
    with pytest.raises(TypeError, match="prorrata_register_repository"):
        cast(Any, ProrrataRegularizacionSourceResolver)(current_year_values=_current_year_values())


def test_resolver_refuses_construction_without_an_explicit_transaction_repository(tmp_path: Path) -> None:
    """The earlier liquidations' gross cuotas cannot come from an implicit active ledger."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile,
        pytest.raises(TypeError, match="transaction_repository"),
    ):
        cast(Any, ProrrataRegularizacionSourceResolver)(
            current_year_values=_current_year_values(),
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=profile.repository),
            observation_repository=CalculationObservationRepository(objects=profile.repository),
        )


def test_a_non_settlement_quarter_is_a_structural_zero(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The AEAT instructions fill the box only in the 4T or month 12; 3T carries a proven zero."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_3t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="3T",
            authority_operation=authority_operation,
            register=_register_with_carried_prior(),
        )

    assert resolution.binding_values == {_M303_BINDING_ID: Decimal("0.00")}
    assert resolution.unresolved_binding_ids == ()
    assert resolution.diagnostics == ()
    assert {row.source_ref for row in resolution.provenance} == {"303:2025:3T:prorrata-regularizacion-settlement-only"}


def test_settlement_without_a_provisional_source_is_unresolved(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Declared exempt volumes with no register value and no prior settlement stay unresolved."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    assert message == render_tr(f"{_KEY}.provisional_missing", year=_FILING_YEAR)


def test_settlement_with_a_missing_definitive_percentage_names_it(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A missing current-year value blocks resolution before any zero can be inferred."""
    current_year_values = _current_year_values()
    del current_year_values[_PORCENTAJE_ID]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_carried_prior(),
            current_year_values=current_year_values,
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    assert message == render_tr(f"{_KEY}.current_year_inputs", casillas=str(_PORCENTAJE_ID))


def test_undeclared_volumes_under_an_active_register_are_unresolved_not_zero(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The engine's default for an unsupplied volume is not a fact; prorrata applies, so refuse."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_carried_prior(),
            current_year_values={
                _VOLUMEN_CON_DERECHO_ID: Decimal("0"),
                _VOLUMEN_TOTAL_ID: Decimal("0"),
                _PORCENTAJE_ID: Decimal("100"),
            },
            undeclared=(_VOLUMEN_CON_DERECHO_ID, _VOLUMEN_TOTAL_ID),
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    assert message == render_tr(
        f"{_KEY}.volumes_undeclared",
        year=_FILING_YEAR,
        casillas=f"{_VOLUMEN_CON_DERECHO_ID}, {_VOLUMEN_TOTAL_ID}",
    )


def test_undeclared_volumes_without_prorrata_evidence_resolve_a_proven_zero(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """No register and no declared exempt volume: prorrata does not apply (LIVA art. 102.Uno)."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            current_year_values={
                _VOLUMEN_CON_DERECHO_ID: Decimal("0"),
                _VOLUMEN_TOTAL_ID: Decimal("0"),
                _PORCENTAJE_ID: Decimal("100"),
            },
            undeclared=(_VOLUMEN_CON_DERECHO_ID, _VOLUMEN_TOTAL_ID),
        )

    assert resolution.binding_values == {_M303_BINDING_ID: Decimal("0.00")}
    assert resolution.unresolved_binding_ids == ()


def test_unfiled_earlier_quarters_are_named(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The box regularises 1T-3T; with none filed it names each instead of reading zero."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_carried_prior(),
            filed={"2T": {_SOPORTADO_INTERIORES_ID: Decimal("0.00")}},
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    assert message == render_tr(f"{_KEY}.source_periods_missing", periods="1T, 3T")


def test_an_earlier_quarter_filed_without_its_deducible_boxes_is_refused(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The practised deduction is read box by box; an absent box is not read as zero."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_carried_prior(),
            filed={period: {_SOPORTADO_INTERIORES_ID: Decimal("0.00")} for period in ("1T", "2T", "3T")},
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    absent = ", ".join(str(casilla_id) for casilla_id in _DEDUCIBLE_CUOTA_IDS if casilla_id != _SOPORTADO_INTERIORES_ID)
    assert message == render_tr(f"{_KEY}.source_period_cuotas_missing", period="1T", casillas=absent)


def test_an_earlier_quarter_filed_without_ledger_input_has_no_derivable_gross_base(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A filed deduction the ledger holds no input for has an unknown gross base.

    1T filed 292,00 of deducible interior cuota -- the manual's first quarter at
    73% -- while the ledger holds no input IVA for the quarter, as when the
    quarter was entered by hand. The gross cuotas before prorrata cannot be
    re-derived, so the regularisation names the quarter instead of guessing.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_carried_prior(),
            filed={
                "1T": _filed_deduction(Decimal("292.00")),
                "2T": _filed_deduction(Decimal("0.00")),
                "3T": _filed_deduction(Decimal("0.00")),
            },
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    assert message == render_tr(f"{_KEY}.source_period_gross_unavailable", period="1T")


def test_an_earlier_quarter_that_disagrees_with_the_ledger_is_refused(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A filed deduction the ledger cannot reproduce at the provisional percentage is not guessed at.

    The ledger holds the manual's 400,00 first-quarter cuota, which at the
    provisional 73% deducts 292,00, but 1T filed 300,00.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_carried_prior(),
            transactions=(_purchase("buy-1t", period="1T", cuota=Decimal("400.00")),),
            filed={
                "1T": _filed_deduction(Decimal("300.00")),
                "2T": _filed_deduction(Decimal("0.00")),
                "3T": _filed_deduction(Decimal("0.00")),
            },
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    assert message == render_tr(
        f"{_KEY}.source_period_ledger_divergence",
        period="1T",
        casilla=str(_SOPORTADO_INTERIORES_ID),
        filed=Decimal("300.00"),
        expected=Decimal("292.00"),
    )


def test_general_regularisation_reproduces_the_manual_box_from_the_ledger(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Manual práctico IVA 2025 pp. 137-138: 1T-3T cuotas 400/420/460 at 73% regularise to -217,60."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_carried_prior(),
            transactions=(
                _purchase("buy-1t", period="1T", cuota=Decimal("400.00")),
                _purchase("buy-2t", period="2T", cuota=Decimal("420.00")),
                _purchase("buy-3t", period="3T", cuota=Decimal("460.00")),
            ),
            filed={
                "1T": _filed_deduction(Decimal("292.00")),
                "2T": _filed_deduction(Decimal("306.60")),
                "3T": _filed_deduction(Decimal("335.80")),
            },
        )

    assert resolution.unresolved_binding_ids == ()
    assert resolution.binding_values == {_M303_BINDING_ID: _MANUAL_CASILLA_44_REGULARIZACION}


def test_especial_regularises_only_the_common_use_slice(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Prorrata especial regularises the regla 3.ª common slice and leaves the 100 % and 0 % slices final.

    The Manual práctico IVA 2025 p. 139 especial example (locales con derecho
    25.000, viviendas sin derecho 20.000, so a definitive 56%) soporta 800,00
    on exclusively deductible inputs and 160,00 on common-use inputs, for a
    year deduction of 889,60. Spread over the year with a provisional 73%: 1T
    soporta 500,00 exclusive, 100,00 common and 40,00 exclusively
    non-deductible (deducts 500 + 73 + 0 = 573,00); 2T soporta 300,00
    exclusive (deducts 300,00); 3T nothing; 4T soporta the remaining 60,00
    common at the definitive 56% (33,60). LIVA art. 106.Uno regla 3.ª applies
    art. 105 to the common slice only, so the box is
    round(56% x 100) - 73 = -17,00, and the year sums to the manual's 889,60.
    """
    especial_register = ProrrataRegister(
        entries=(_register_with_carried_prior().entries[0].model_copy(update={"regime": _ESPECIAL}),),
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=especial_register,
            transactions=(
                _purchase("excl-1t", period="1T", cuota=Decimal("500.00"), classification=_EXCLUSIVELY_DEDUCTIBLE),
                _purchase("common-1t", period="1T", cuota=Decimal("100.00"), classification=_COMMON),
                _purchase("none-1t", period="1T", cuota=Decimal("40.00"), classification=_EXCLUSIVELY_NON_DEDUCTIBLE),
                _purchase("excl-2t", period="2T", cuota=Decimal("300.00"), classification=_EXCLUSIVELY_DEDUCTIBLE),
                _purchase("common-4t", period="4T", cuota=Decimal("60.00"), classification=_COMMON),
            ),
            filed={
                "1T": _filed_deduction(Decimal("573.00")),
                "2T": _filed_deduction(Decimal("300.00")),
                "3T": _filed_deduction(Decimal("0.00")),
            },
        )

    regularizacion = Decimal("-17.00")
    assert resolution.unresolved_binding_ids == ()
    assert resolution.binding_values == {_M303_BINDING_ID: regularizacion}
    settlement_own_deduction = Decimal("33.60")
    year_deduction = Decimal("573.00") + Decimal("300.00") + settlement_own_deduction + regularizacion
    assert year_deduction == _MANUAL_ESPECIAL_YEAR_DEDUCTION


def _sectorized_register(*, settled: dict[str, tuple[Decimal, Decimal]]) -> ProrrataRegister:
    """Two differentiated sectors, each general, with the common entry the apportionment requires.

    ``settled`` maps a sector to its year's con-derecho and sin-derecho volumes;
    the sector's definitive percentage is settled from them by the register's
    own lifecycle (LIVA art. 105.Cuatro applied per sector).
    """
    common = _register_with_carried_prior().entries[0].model_copy(update={"provisional_percentage": Decimal("60")})
    snapshot_ref = published_authority_operation().snapshot("303", filing_year=_FILING_YEAR, period="4T").snapshot_ref
    sectors: list[ProrrataRegisterEntry] = []
    for sector_id, provisional in _SECTOR_PROVISIONAL.items():
        entry = common.model_copy(
            update={
                "sector_id": sector_id,
                "provisional_percentage": provisional,
                "source_observation_ref": f"prorrata-register:{_PRIOR_YEAR}:{sector_id}",
            }
        )
        if sector_id in settled:
            con_derecho, sin_derecho = settled[sector_id]
            entry = settle_sector_definitive(
                entry,
                con_derecho_volume=con_derecho,
                sin_derecho_volume=sin_derecho,
                producing_snapshot_ref=snapshot_ref,
            )
        sectors.append(entry)
    return ProrrataRegister(
        entries=(common, *sectors),
        sector_definitions=(
            SectorDefinition(
                sector_id=_SECTOR_A,
                letra=SectorDiferenciadoLetra.from_registry("a"),
                member_activity_codes=("4711",),
            ),
            SectorDefinition(
                sector_id=_SECTOR_B,
                letra=SectorDiferenciadoLetra.from_registry("a"),
                member_activity_codes=("6820",),
            ),
        ),
    )


#: Sector A's volumes settle at 7.000 / 10.000 = 70 %; sector B's at 4.000 / 10.000 = 40 %.
_SECTOR_A_VOLUMES = (Decimal("7000.00"), Decimal("3000.00"))
_SECTOR_B_VOLUMES = (Decimal("4000.00"), Decimal("6000.00"))


_SECTOR_LEDGER: tuple[tuple[str, str, str, Decimal], ...] = (
    ("a-1t", "1T", "sector-a", Decimal("100.00")),
    ("b-1t", "1T", "sector-b", Decimal("200.00")),
    ("a-2t", "2T", "sector-a", Decimal("50.00")),
)
#: Filed at each sector's provisional percentage: 1T 100 x 80% + 200 x 30% = 140,00; 2T 50 x 80% = 40,00.
_SECTOR_FILED = {
    "1T": _filed_deduction(Decimal("140.00")),
    "2T": _filed_deduction(Decimal("40.00")),
    "3T": _filed_deduction(Decimal("0.00")),
}


def _sector_ledger(*extra: Transaction) -> tuple[Transaction, ...]:
    return (
        *(
            _purchase(provider_id, period=period, cuota=cuota, sector_id=sector_id)
            for provider_id, period, sector_id, cuota in _SECTOR_LEDGER
        ),
        *extra,
    )


def test_each_differentiated_sector_regularises_at_its_own_definitive_percentage(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """LIVA art. 101.Uno: each sector runs its own art. 105 regularisation.

    Sector A deducted 150,00 at 80% (120,00) and settles at 70%: 105,00, so
    -15,00. Sector B deducted 200,00 at 30% (60,00) and settles at 40%: 80,00,
    so +20,00. The box is the sum, +5,00; a single whole-entity percentage
    would give neither figure.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_sectorized_register(settled={_SECTOR_A: _SECTOR_A_VOLUMES, _SECTOR_B: _SECTOR_B_VOLUMES}),
            transactions=_sector_ledger(),
            filed=_SECTOR_FILED,
        )

    assert resolution.unresolved_binding_ids == ()
    assert resolution.binding_values == {_M303_BINDING_ID: Decimal("-15.00") + Decimal("20.00")}


def test_an_unsettled_sector_leaves_the_box_unresolved_and_named(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A sector without its settled definitive percentage is named, never given the whole-entity one."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_sectorized_register(settled={_SECTOR_A: _SECTOR_A_VOLUMES}),
            transactions=_sector_ledger(),
            filed=_SECTOR_FILED,
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    assert message == render_tr(f"{_KEY}.sector_definitive_missing", year=_FILING_YEAR, sectors=_SECTOR_B)


def test_cross_sector_common_use_input_keeps_the_box_unresolved(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Common use across sectors needs the art. 101.Uno percentage the declared volumes do not evidence.

    The common-use input is booked in the settlement quarter itself, so the
    earlier quarters still reconcile and only the partition is refused.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_sectorized_register(settled={_SECTOR_A: _SECTOR_A_VOLUMES, _SECTOR_B: _SECTOR_B_VOLUMES}),
            transactions=_sector_ledger(
                _purchase("common-4t", period="4T", cuota=Decimal("30.00"), classification=_COMMON)
            ),
            filed=_SECTOR_FILED,
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    assert message == render_tr(f"{_KEY}.regime_not_derived", year=_FILING_YEAR)


def test_modelo_390_restates_the_filed_settlement_regularisation(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The annual field equals the 4T box the taxpayer filed, so 390 and 303 cannot disagree."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_0a = _resolve(
            profile.repository,
            modelo=Modelo("390").value,
            period="0A",
            authority_operation=authority_operation,
            filed={"4T": {_REGULARIZACION_ID: _MANUAL_CASILLA_44_REGULARIZACION}},
        )

    assert resolution.binding_values == {_M390_BINDING_ID: _MANUAL_CASILLA_44_REGULARIZACION}
    assert resolution.unresolved_binding_ids == ()
    assert resolution.diagnostics == ()
    assert {row.source_ref for row in resolution.provenance} == {"303:2025:4T:44"}


def test_modelo_390_reads_only_the_explicitly_injected_observation_store(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A settlement filed in the active primary profile cannot leak into the secondary's summary."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        primary_observations = CalculationObservationRepository(objects=runtime.primary.repository)
        _save_m303_observation(
            primary_observations, period="4T", casilla_values={_REGULARIZACION_ID: Decimal("-100.00")}
        )
        with runtime.switch_to_secondary():
            resolution, _snapshot_0a = _resolve(
                runtime.secondary.repository,
                modelo=Modelo("390").value,
                period="0A",
                authority_operation=authority_operation,
                filed={"4T": {_REGULARIZACION_ID: _MANUAL_CASILLA_44_REGULARIZACION}},
                bucket_id=runtime.secondary.bucket_id,
            )

    assert resolution.binding_values == {_M390_BINDING_ID: _MANUAL_CASILLA_44_REGULARIZACION}


def test_modelo_390_without_a_filed_settlement_names_every_terminal_period(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Neither a 4T nor a month-12 liquidation is filed: the annual field names both and its box."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, snapshot = _resolve(
            profile.repository,
            modelo=Modelo("390").value,
            period="0A",
            authority_operation=authority_operation,
        )

    message = _sole_unresolved_message(resolution, _M390_BINDING_ID)
    assert message == render_tr(f"{_KEY}.settlement_observation_missing", periods="4T, 12")
    box = sole_bound_casilla(snapshot.revision, _M390_BINDING_ID)
    assert box is not None, "the annual regularisation fills one box of the Modelo 390"
    assert resolution.diagnostics[0].casilla_id == box


def test_modelo_390_with_both_cadences_filed_is_ambiguous(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A 4T and a month-12 settlement cannot both be the year's last liquidation."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_0a = _resolve(
            profile.repository,
            modelo=Modelo("390").value,
            period="0A",
            authority_operation=authority_operation,
            filed={
                "4T": {_REGULARIZACION_ID: _MANUAL_CASILLA_44_REGULARIZACION},
                "12": {_REGULARIZACION_ID: Decimal("-50.00")},
            },
        )

    message = _sole_unresolved_message(resolution, _M390_BINDING_ID)
    assert message == render_tr(f"{_KEY}.settlement_observation_ambiguous", periods="4T, 12")


#: The manual's 1T-3T gross deducible cuotas, which the filed liquidations
#: deducted at the provisional 73% as 292,00 / 306,60 / 335,80.
_MANUAL_GROSS = {"1T": Decimal("400.00"), "2T": Decimal("420.00"), "3T": Decimal("460.00")}
_MANUAL_FILED = {
    "1T": _filed_deduction(Decimal("292.00")),
    "2T": _filed_deduction(Decimal("306.60")),
    "3T": _filed_deduction(Decimal("335.80")),
}


def _register_with_gross(declared: dict[str, Decimal]) -> ProrrataRegister:
    return _register_with_carried_prior().with_gross_declarations(
        tuple(
            ProrrataOperatorGrossDeclaration(
                ejercicio=_FILING_YEAR,
                period=Period.from_year_and_code(_FILING_YEAR, period),
                gross_cuota=gross,
                evidence_reference=f"operator-evidence:303-{period}",
                declared_at=_CAPTURED_AT,
            )
            for period, gross in declared.items()
        )
    )


def _operator_source_refs(resolution: CalculationSourceResolution) -> set[str]:
    return {
        row.source_ref for row in resolution.provenance if row.terminal_origin is TerminalOriginClass.OPERATOR_INPUT
    }


def test_operator_declared_gross_bases_reproduce_the_manual_box_without_ledger_input(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Manual práctico IVA 2025 pp. 137-138 from hand-entered quarters.

    The ledger holds no input IVA for 1T-3T; the operator declared their gross
    cuotas 400/420/460. At the provisional 73% the quarters practised 934,40;
    the definitive 56% allows 0,56 x 1.280 = 716,80, so casilla 44 is
    716,80 - 934,40 = -217,60.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_gross(_MANUAL_GROSS),
            filed=_MANUAL_FILED,
        )

    assert resolution.unresolved_binding_ids == ()
    assert resolution.binding_values == {_M303_BINDING_ID: _MANUAL_CASILLA_44_REGULARIZACION}
    assert _operator_source_refs(resolution) == {
        f"prorrata-register:{_FILING_YEAR}:operator_declared:{period}" for period in ("1T", "2T", "3T")
    }


def test_operator_declarations_fill_only_the_quarters_the_ledger_leaves_empty(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A ledger-backed 2T and declared 1T/3T regularise to the same manual box."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_gross({"1T": _MANUAL_GROSS["1T"], "3T": _MANUAL_GROSS["3T"]}),
            transactions=(_purchase("buy-2t", period="2T", cuota=Decimal("420.00")),),
            filed=_MANUAL_FILED,
        )

    assert resolution.binding_values == {_M303_BINDING_ID: _MANUAL_CASILLA_44_REGULARIZACION}
    assert _operator_source_refs(resolution) == {
        f"prorrata-register:{_FILING_YEAR}:operator_declared:1T",
        f"prorrata-register:{_FILING_YEAR}:operator_declared:3T",
    }


def test_the_ledger_wins_over_an_agreeing_operator_declaration(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_gross(_MANUAL_GROSS),
            transactions=(
                _purchase("buy-1t", period="1T", cuota=Decimal("400.00")),
                _purchase("buy-2t", period="2T", cuota=Decimal("420.00")),
                _purchase("buy-3t", period="3T", cuota=Decimal("460.00")),
            ),
            filed=_MANUAL_FILED,
        )

    assert resolution.binding_values == {_M303_BINDING_ID: _MANUAL_CASILLA_44_REGULARIZACION}
    assert _operator_source_refs(resolution) == set()


def test_an_operator_declaration_the_ledger_contradicts_is_unresolved(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The ledger holds 400,00 for 1T but the operator declared 410,00: neither is used."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_gross({"1T": Decimal("410.00")}),
            transactions=(
                _purchase("buy-1t", period="1T", cuota=Decimal("400.00")),
                _purchase("buy-2t", period="2T", cuota=Decimal("420.00")),
                _purchase("buy-3t", period="3T", cuota=Decimal("460.00")),
            ),
            filed=_MANUAL_FILED,
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    assert message == render_tr(
        f"{_KEY}.source_period_gross_disagreement",
        period="1T",
        ledger=Decimal("400.00"),
        declared=Decimal("410.00"),
    )


def test_an_operator_declaration_the_filed_liquidation_contradicts_is_unresolved(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """1T filed 292,00 but a declared 420,00 at 73% deducts 306,60: the declaration is not trusted."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_gross({**_MANUAL_GROSS, "1T": Decimal("420.00")}),
            filed=_MANUAL_FILED,
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    assert message == render_tr(
        f"{_KEY}.source_period_operator_divergence",
        period="1T",
        filed=Decimal("292.00"),
        expected=Decimal("306.60"),
    )
