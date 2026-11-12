"""Work-income bindings of the suffered-withholding family through the real store and resolver.

The six income quantities of a trabajo payer record fill income casillas. A record states the
income; an absence attestation only says that no payer withheld, so it zeroes the credit and never
the income; a profile that excludes the class proves a zero; a record stored before the two
certificate figures existed leaves the bindings that draw them unresolved. All identifiers and
amounts are synthetic, and each expected sum is derived by hand from the certificates seeded.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.aggregation.retencion_soportada_absence_repository import (
    RetencionSoportadaAbsenceWritePorts,
    attest_retencion_soportada_absence,
)
from .....application.aggregation.retencion_soportada_repository import (
    PinnedRetencionSoportadaWriteAuthority,
    RetencionSoportadaPorts,
    RetencionSoportadaRecordReader,
)
from .....application.aggregation.retencion_soportada_source import (
    RetencionSoportadaSourceResolver,
    recorded_income_classes,
)
from .....application.aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from .....application.aggregation.source_resolution_operations import merge_source_resolutions
from .....application.modelo.work_profile import ModeloWorkProfile
from .....core.period import Period
from .....core.retencion_soportada import RetencionSoportadaCantidad, RetencionSoportadaClase
from .....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from .....domain.calculations.registry.retencion_soportada_bindings import RETENCION_SOPORTADA_INCOME_ROLES
from .....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from .....domain.calculations.registry.schema_references import PeriodSelector
from .....domain.modelos.calculation_revision_sources import CalculationNoteSentence
from .....domain.renta.retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord
from .....domain.renta.retencion_soportada_absence import RetencionSoportadaAbsence
from .....domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from .....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...storage.runtime_repository import secure_object_repository_for_active_bucket
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..retencion_soportada_records import (
    RetencionSoportadaAbsenceRepositoryAdapter,
    RetencionSoportadaRecordRepositoryAdapter,
)
from .retencion_soportada_seed import seed_payer_certificate

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_TAXPAYER = "00000000T"
_EJERCICIO = 2025
_PROFILE_ID = "11111111-1111-4111-8111-111111111111"
_CATEGORIES = "taxpayer_type.irpf_income_categories"
_LEGAL_REFS = ("ley-35-2006:art-99", "rd-439-2007:art-108")
_SOURCE_REFS = ("aeat-modelo-100-instructions-2025",)
_QUANTITIES = tuple(quantity for _, quantity in RETENCION_SOPORTADA_INCOME_ROLES)


def _binding_id(quantity: RetencionSoportadaCantidad) -> str:
    return f"binding-{quantity.value}".replace("_", "-")


def _binding(quantity: RetencionSoportadaCantidad) -> BindingDefinition:
    return BindingDefinition(
        id=_binding_id(quantity),
        provider={"kind": "retencion_soportada", "income_class": "trabajo", "quantity": quantity.value},
        value={"data_type": "money", "channel": "decimal"},
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


_REVISION = ModeloRevision(
    id="2025-retencion-soportada-income-test",
    localization_key="test.schema.revision.2025-retencion-soportada-income-test.label",
    valid_from=date(2025, 1, 1),
    period_selector=PeriodSelector(years=(_EJERCICIO,), periods=("0A",)),
    legal_refs=_LEGAL_REFS,
    source_refs=_SOURCE_REFS,
    bindings=(*(_binding(quantity) for quantity in _QUANTITIES), _binding(RetencionSoportadaCantidad.PAGO_A_CUENTA)),
)


def _profile(operation: PinnedAuthorityOperation, *facts: UserProfileFact) -> ModeloWorkProfile:
    record = create_user_profile_record(
        context=profile_creation_context_for_test(),
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=facts,
    )
    return ModeloWorkProfile(record=record, profile_decode_context=operation.profile_decode_context())


def _resolve(
    profile: ModeloWorkProfile | None = None, *, repository: RetencionSoportadaRecordReader | None = None
) -> CalculationSourceResolution:
    objects = secure_object_repository_for_active_bucket()
    resolver = RetencionSoportadaSourceResolver(
        ports=RetencionSoportadaPorts(
            repository=repository or RetencionSoportadaRecordRepositoryAdapter(objects=objects),
            absences=RetencionSoportadaAbsenceRepositoryAdapter(objects=objects),
        ),
    )
    context = CalculationSourceContext(
        bucket_id="operator",
        modelo="100",
        filing_year=_EJERCICIO,
        period=Period.from_year_and_code(_EJERCICIO, "0A"),
        revision=_REVISION,
        profile=profile,
    )
    return merge_source_resolutions((resolver.resolve(context),))


def _seed(operation: PinnedAuthorityOperation, payer: str, **figures: Decimal) -> None:
    seed_payer_certificate(
        operation=operation,
        taxpayer_tax_id=_TAXPAYER,
        ejercicio=_EJERCICIO,
        payer_tax_id=payer,
        income_class=RetencionSoportadaClase.TRABAJO,
        **figures,
    )


def _attest_trabajo(operation: PinnedAuthorityOperation) -> None:
    objects = secure_object_repository_for_active_bucket()
    attest_retencion_soportada_absence(
        RetencionSoportadaAbsence(
            ejercicio=_EJERCICIO,
            income_class=RetencionSoportadaClase.TRABAJO,
            note="Synthetic note: no payer withheld.",
            attested_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
        ),
        ports=RetencionSoportadaAbsenceWritePorts(
            attestations=RetencionSoportadaAbsenceRepositoryAdapter(objects=objects),
            records=RetencionSoportadaRecordRepositoryAdapter(objects=objects),
            authority=PinnedRetencionSoportadaWriteAuthority(operation),
        ),
        expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
    )


def _sentences(resolution: CalculationSourceResolution) -> dict[str, CalculationNoteSentence]:
    return {
        item.binding_id: item.fact.sentence
        for item in resolution.diagnostics
        if item.fact is not None and item.binding_id is not None
    }


def test_two_payers_sum_into_each_income_binding_and_the_credit(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        _seed(
            operation,
            "B00000001",
            retencion=Decimal("1200.00"),
            ingreso_a_cuenta=Decimal("300.00"),
            ingreso_a_cuenta_repercutido=Decimal("100.00"),
            importe_integro_dinerario=Decimal("20000.00"),
            valoracion_especie=Decimal("1500.00"),
            reducciones_aplicables=Decimal("3060.00"),
            gastos_deducibles=Decimal("610.00"),
        )
        _seed(
            operation,
            "B00000002",
            retencion=Decimal("80.50"),
            importe_integro_dinerario=Decimal("4000.25"),
            gastos_deducibles=Decimal("50.00"),
        )
        resolution = _resolve()
    assert resolution.diagnostics == ()
    assert resolution.binding_values == {
        _binding_id(RetencionSoportadaCantidad.IMPORTE_INTEGRO_DINERARIO): Decimal("24000.25"),
        _binding_id(RetencionSoportadaCantidad.VALORACION_ESPECIE): Decimal("1500.00"),
        _binding_id(RetencionSoportadaCantidad.INGRESO_A_CUENTA): Decimal("300.00"),
        _binding_id(RetencionSoportadaCantidad.INGRESO_A_CUENTA_REPERCUTIDO): Decimal("100.00"),
        _binding_id(RetencionSoportadaCantidad.REDUCCIONES_APLICABLES): Decimal("3060.00"),
        _binding_id(RetencionSoportadaCantidad.GASTOS_DEDUCIBLES): Decimal("660.00"),
        _binding_id(RetencionSoportadaCantidad.PAGO_A_CUENTA): Decimal("1580.50"),
    }
    assert recorded_income_classes(ref.source_ref for ref in resolution.provenance) == {RetencionSoportadaClase.TRABAJO}


def test_an_attestation_zeroes_the_credit_and_leaves_every_income_binding_unresolved(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        _attest_trabajo(operation)
        resolution = _resolve()
    credit = _binding_id(RetencionSoportadaCantidad.PAGO_A_CUENTA)
    assert resolution.binding_values == {credit: Decimal("0.00")}
    assert set(resolution.unresolved_binding_ids) == {_binding_id(quantity) for quantity in _QUANTITIES}
    assert set(_sentences(resolution).values()) == {CalculationNoteSentence.RETENCION_SOPORTADA_INCOME_RECORD_REQUIRED}
    assert recorded_income_classes(ref.source_ref for ref in resolution.provenance) == frozenset()
    diagnostic = resolution.diagnostics[0]
    assert "withdraw-absence" in (diagnostic.remedy or "")
    assert "operator_declaration" in (diagnostic.remedy or "")


def test_a_class_the_profile_excludes_is_a_proven_zero_for_every_income_binding(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    profile = _profile(operation, UserProfileFact(path=_CATEGORIES, value="actividad_economica,capital_mobiliario"))
    with isolated_runtime_profile(tmp_path=tmp_path):
        resolution = _resolve(profile)
    assert resolution.diagnostics == ()
    assert set(resolution.binding_values.values()) == {Decimal("0.00")}
    assert len(resolution.binding_values) == len(_QUANTITIES) + 1
    assert {node.terminal_origin for node in resolution.provenance} == {TerminalOriginClass.PROFILE_FIELD}


def test_a_declared_class_without_a_record_or_attestation_needs_evidence_for_income_and_credit(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    profile = _profile(operation, UserProfileFact(path=_CATEGORIES, value="trabajo"))
    with isolated_runtime_profile(tmp_path=tmp_path):
        resolution = _resolve(profile)
    assert resolution.binding_values == {}
    assert len(resolution.unresolved_binding_ids) == len(_QUANTITIES) + 1
    assert set(_sentences(resolution).values()) == {CalculationNoteSentence.RETENCION_SOPORTADA_EVIDENCE_REQUIRED}


class _StoredBeforeTheTwoFigures:
    """The records of a store written before the certificate figures existed: both are absent."""

    def __init__(self, record: RetencionSoportadaRecord) -> None:
        self._record = record

    def load_records(self, ejercicio: int) -> tuple[RetencionSoportadaRecord, ...]:
        assert ejercicio == _EJERCICIO
        return (self._record,)


def test_a_record_stored_before_the_two_figures_resolves_the_rest_and_leaves_those_two_unresolved(
    tmp_path: Path,
) -> None:
    legacy = RetencionSoportadaRecord(
        ejercicio=_EJERCICIO,
        payer_tax_id="B00000001",
        payer_ref="0" * 64,
        income_class=RetencionSoportadaClase.TRABAJO,
        importe_integro_dinerario=Decimal("18000.00"),
        valoracion_especie=Decimal("0.00"),
        retencion=Decimal("900.00"),
        ingreso_a_cuenta=Decimal("0.00"),
        ingreso_a_cuenta_repercutido=Decimal("0.00"),
        origin=RetencionSoportadaOrigen.PAYER_CERTIFICATE,
        evidence_fingerprint="a" * 64,
        captured_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
    )
    assert legacy.reducciones_aplicables is None
    with isolated_runtime_profile(tmp_path=tmp_path):
        resolution = _resolve(repository=_StoredBeforeTheTwoFigures(legacy))
    assert resolution.binding_values == {
        _binding_id(RetencionSoportadaCantidad.IMPORTE_INTEGRO_DINERARIO): Decimal("18000.00"),
        _binding_id(RetencionSoportadaCantidad.VALORACION_ESPECIE): Decimal("0.00"),
        _binding_id(RetencionSoportadaCantidad.INGRESO_A_CUENTA): Decimal("0.00"),
        _binding_id(RetencionSoportadaCantidad.INGRESO_A_CUENTA_REPERCUTIDO): Decimal("0.00"),
        _binding_id(RetencionSoportadaCantidad.PAGO_A_CUENTA): Decimal("900.00"),
    }
    assert _sentences(resolution) == {
        _binding_id(RetencionSoportadaCantidad.REDUCCIONES_APLICABLES): (
            CalculationNoteSentence.RETENCION_SOPORTADA_RECORD_FIGURE_MISSING
        ),
        _binding_id(RetencionSoportadaCantidad.GASTOS_DEDUCIBLES): (
            CalculationNoteSentence.RETENCION_SOPORTADA_RECORD_FIGURE_MISSING
        ),
    }
