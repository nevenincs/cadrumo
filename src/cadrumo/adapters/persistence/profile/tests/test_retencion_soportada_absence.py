"""Absence attestations through the real encrypted store, guarded write path and source resolver.

All tax identifiers, notes and amounts are synthetic. A class with no payer
record resolves to a proven zero only on an active attestation or on profile
income categories that positively exclude it; every other empty class stays
unresolved with a typed finding.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.aggregation.retencion_soportada_absence_repository import (
    RetencionSoportadaAbsenceRefusedError,
    RetencionSoportadaAbsenceWritePorts,
    attest_retencion_soportada_absence,
    withdraw_retencion_soportada_absence,
)
from .....application.aggregation.retencion_soportada_repository import (
    PinnedRetencionSoportadaWriteAuthority,
    RetencionSoportadaPorts,
    RetencionSoportadaRevisionConflictError,
)
from .....application.aggregation.retencion_soportada_source import RetencionSoportadaSourceResolver
from .....application.aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from .....application.aggregation.source_resolution_operations import merge_source_resolutions
from .....application.modelo.work_profile import ModeloWorkProfile
from .....core.aggregation import BindingSourceKind
from .....core.external_constants import UTF_8_ENCODING
from .....core.period import Period
from .....core.retencion_soportada import RetencionSoportadaClase
from .....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from .....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from .....domain.calculations.registry.schema_references import PeriodSelector
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.modelos.calculation_revision_sources import CalculationNoteSentence
from .....domain.renta.retencion_soportada_absence import RetencionSoportadaAbsence
from .....domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from .....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...storage.runtime_repository import secure_object_repository_for_active_bucket
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..retencion_soportada_certificado import RetencionSoportadaCertificadoRepositoryAdapter
from ..retencion_soportada_records import (
    RetencionSoportadaAbsenceRepositoryAdapter,
    RetencionSoportadaRecordRepositoryAdapter,
)
from .retencion_soportada_seed import seed_payer_certificate

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_TAXPAYER = "00000000T"
_PAYER = "B00000001"
_EJERCICIO = filing_year_envelope().horizon
_PROFILE_ID = "11111111-1111-4111-8111-111111111111"
_AT = datetime(_EJERCICIO + 1, 4, 2, 9, 0, tzinfo=UTC)
_NOTE = "Synthetic note: the employer paid below the withholding threshold."
_LEGAL_REFS = ("ley-35-2006:art-99", "rd-439-2007:art-108")
_SOURCE_REFS = ("aeat-modelo-100-instructions-2025",)
_TRABAJO_BINDING = "renta-retencion-soportada-trabajo"
_ATRIBUCION_BINDING = "renta-retencion-soportada-atribucion-capital-mobiliario"
_CATEGORIES = "taxpayer_type.irpf_income_categories"


def _binding(binding_id: str, income_class: str) -> BindingDefinition:
    return BindingDefinition(
        id=binding_id,
        provider={"kind": "retencion_soportada", "income_class": income_class, "quantity": "pago_a_cuenta"},
        value={"data_type": "money", "channel": "decimal"},
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def _revision(*bindings: BindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id=f"{_EJERCICIO}-retencion-soportada-absence-test",
        localization_key=f"test.schema.revision.{_EJERCICIO}-retencion-soportada-absence-test.label",
        valid_from=date(_EJERCICIO, 1, 1),
        period_selector=PeriodSelector(years=(_EJERCICIO,), periods=("0A",)),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        bindings=bindings,
    )


_TRABAJO_REVISION = _revision(_binding(_TRABAJO_BINDING, "trabajo"))


def _profile(operation: PinnedAuthorityOperation, *facts: UserProfileFact) -> ModeloWorkProfile:
    record = create_user_profile_record(
        context=profile_creation_context_for_test(),
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=facts,
    )
    return ModeloWorkProfile(record=record, profile_decode_context=operation.profile_decode_context())


def _context(revision: ModeloRevision, profile: ModeloWorkProfile | None) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id="operator",
        modelo="100",
        filing_year=_EJERCICIO,
        period=Period.from_year_and_code(_EJERCICIO, "0A"),
        revision=revision,
        profile=profile,
    )


def _ports(operation: PinnedAuthorityOperation) -> RetencionSoportadaAbsenceWritePorts:
    objects = secure_object_repository_for_active_bucket()
    return RetencionSoportadaAbsenceWritePorts(
        attestations=RetencionSoportadaAbsenceRepositoryAdapter(objects=objects),
        records=RetencionSoportadaRecordRepositoryAdapter(objects=objects),
        authority=PinnedRetencionSoportadaWriteAuthority(operation),
    )


def _resolve(
    revision: ModeloRevision = _TRABAJO_REVISION, profile: ModeloWorkProfile | None = None
) -> CalculationSourceResolution:
    objects = secure_object_repository_for_active_bucket()
    resolver = RetencionSoportadaSourceResolver(
        ports=RetencionSoportadaPorts(
            repository=RetencionSoportadaRecordRepositoryAdapter(objects=objects),
            absences=RetencionSoportadaAbsenceRepositoryAdapter(objects=objects),
        ),
    )
    return merge_source_resolutions((resolver.resolve(_context(revision, profile)),))


def _attestation(income_class: RetencionSoportadaClase = RetencionSoportadaClase.TRABAJO) -> RetencionSoportadaAbsence:
    return RetencionSoportadaAbsence(ejercicio=_EJERCICIO, income_class=income_class, note=_NOTE, attested_at=_AT)


def _attest(operation: PinnedAuthorityOperation, *, expected: str = ABSENT_SECURE_OBJECT_REVISION_ID) -> str:
    return attest_retencion_soportada_absence(_attestation(), ports=_ports(operation), expected_revision_id=expected)


def _seed_trabajo(operation: PinnedAuthorityOperation) -> None:
    seed_payer_certificate(
        operation=operation,
        taxpayer_tax_id=_TAXPAYER,
        ejercicio=_EJERCICIO,
        payer_tax_id=_PAYER,
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion=Decimal("1200.00"),
        ingreso_a_cuenta=Decimal("300.00"),
    )


def _unresolved(resolution: CalculationSourceResolution) -> list[tuple[str, str | None, CalculationNoteSentence]]:
    findings: list[tuple[str, str | None, CalculationNoteSentence]] = []
    for item in resolution.diagnostics:
        assert item.fact is not None
        findings.append((item.reason, item.binding_id, item.fact.sentence))
    return findings


def test_an_attestation_is_a_proven_zero_resting_on_operator_input_and_its_note_is_never_plaintext(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        revision_id = _attest(operation)
        ports = _ports(operation)
        stored, read_revision = ports.attestations.load_revisioned(_attestation().identity)
        assert stored == _attestation()
        assert read_revision == revision_id != ABSENT_SECURE_OBJECT_REVISION_ID
        assert ports.records.load_records(_EJERCICIO) == ()
        listing = RetencionSoportadaCertificadoRepositoryAdapter(objects=secure_object_repository_for_active_bucket())
        assert listing.list_revisioned(_EJERCICIO) == ()
        assert ports.attestations.load_attestations(_EJERCICIO + 1) == ()
        resolution = _resolve()
        on_disk = b"".join(path.read_bytes() for path in profile.storage_root.rglob("*") if path.is_file())

    assert _NOTE.encode(UTF_8_ENCODING) not in on_disk
    assert resolution.binding_values == {_TRABAJO_BINDING: Decimal("0.00")}
    assert resolution.diagnostics == ()
    (node,) = resolution.provenance
    assert node.resolved_binding_source is BindingSourceKind.RETENCION_SOPORTADA
    assert node.terminal_origin is TerminalOriginClass.OPERATOR_INPUT
    assert node.source_ref == f"retencion-soportada:absence:{_EJERCICIO}:trabajo"
    assert node.fingerprint is None


def test_withdrawing_returns_the_class_to_unresolved_and_needs_the_current_revision(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    identity = _attestation().identity
    with isolated_runtime_profile(tmp_path=tmp_path):
        revision_id = _attest(operation)
        later = _AT + timedelta(days=1)
        with pytest.raises(RetencionSoportadaRevisionConflictError):
            withdraw_retencion_soportada_absence(
                identity, at=later, ports=_ports(operation), expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID
            )
        assert _resolve().binding_values == {_TRABAJO_BINDING: Decimal("0.00")}

        withdrawn, withdrawn_revision = withdraw_retencion_soportada_absence(
            identity, at=later, ports=_ports(operation), expected_revision_id=revision_id
        )
        assert not withdrawn.active
        assert withdrawn.withdrawn_at == later
        assert withdrawn_revision != revision_id
        resolution = _resolve()
        with pytest.raises(RetencionSoportadaAbsenceRefusedError) as refused:
            withdraw_retencion_soportada_absence(
                identity, at=later, ports=_ports(operation), expected_revision_id=withdrawn_revision
            )
        assert refused.value.reason == "not_attested"

        with pytest.raises(RetencionSoportadaRevisionConflictError):
            _attest(operation)
        _attest(operation, expected=withdrawn_revision)
        reattested = _resolve()

    assert resolution.binding_values == {}
    assert _unresolved(resolution) == [
        ("unresolved_binding", _TRABAJO_BINDING, CalculationNoteSentence.RETENCION_SOPORTADA_EVIDENCE_REQUIRED),
    ]
    assert reattested.binding_values == {_TRABAJO_BINDING: Decimal("0.00")}


def test_a_second_active_attestation_is_refused(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        revision_id = _attest(operation)
        with pytest.raises(RetencionSoportadaAbsenceRefusedError) as refused:
            _attest(operation, expected=revision_id)
    assert refused.value.reason == "already_attested"


def test_an_attestation_for_a_class_with_payer_records_is_refused(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        _seed_trabajo(operation)
        with pytest.raises(RetencionSoportadaAbsenceRefusedError) as refused:
            _attest(operation)
        assert _ports(operation).attestations.load_attestations(_EJERCICIO) == ()
        # The other classes of the ejercicio are untouched by the trabajo records.
        attest_retencion_soportada_absence(
            _attestation(RetencionSoportadaClase.CAPITAL_MOBILIARIO),
            ports=_ports(operation),
            expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    assert refused.value.reason == "records_present"


def test_an_unsupported_ejercicio_is_refused_before_storage(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    unsupported = filing_year_envelope().floor - 1
    with isolated_runtime_profile(tmp_path=tmp_path):
        with pytest.raises(RetencionSoportadaAbsenceRefusedError) as refused:
            attest_retencion_soportada_absence(
                _attestation().model_copy(update={"ejercicio": unsupported}),
                ports=_ports(operation),
                expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
            )
        assert _ports(operation).attestations.load_attestations(unsupported) == ()
    assert refused.value.reason == "ejercicio_unsupported"


def test_records_stored_after_an_attestation_contradict_it_and_neither_is_credited(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        _attest(operation)
        _seed_trabajo(operation)
        resolution = _resolve()
    assert resolution.binding_values == {}
    assert _unresolved(resolution) == [
        ("unresolved_binding", _TRABAJO_BINDING, CalculationNoteSentence.RETENCION_SOPORTADA_ABSENCE_CONTRADICTED),
    ]
    assert all(_PAYER not in item.message and "1200" not in item.message for item in resolution.diagnostics)


def test_a_record_still_resolves_to_its_payer_total_beside_a_profile_that_declares_the_income(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    profile = _profile(operation, UserProfileFact(path=_CATEGORIES, value="trabajo"))
    with isolated_runtime_profile(tmp_path=tmp_path):
        _seed_trabajo(operation)
        resolution = _resolve(profile=profile)
    assert resolution.binding_values == {_TRABAJO_BINDING: Decimal("1500.00")}
    assert resolution.diagnostics == ()
    (node,) = resolution.provenance
    assert node.terminal_origin is TerminalOriginClass.PAYER_CERTIFICATE


def test_categories_that_exclude_the_class_are_a_proven_zero_resting_on_the_profile_fact(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    profile = _profile(operation, UserProfileFact(path=_CATEGORIES, value="actividad_economica,capital_mobiliario"))
    with isolated_runtime_profile(tmp_path=tmp_path):
        resolution = _resolve(profile=profile)
    assert resolution.binding_values == {_TRABAJO_BINDING: Decimal("0.00")}
    assert resolution.diagnostics == ()
    (node,) = resolution.provenance
    assert node.terminal_origin is TerminalOriginClass.PROFILE_FIELD
    assert node.source_ref == f"profile:operator:{_CATEGORIES}:{_EJERCICIO}:trabajo"


@pytest.mark.parametrize(
    "facts",
    [
        (),
        (UserProfileFact(path=_CATEGORIES, value="pension"),),
        (UserProfileFact(path=_CATEGORIES, value="trabajo,actividad_economica"),),
        # A declaration that starts after the ejercicio says nothing about it.
        (UserProfileFact(path=_CATEGORIES, value="actividad_economica", valid_from=date(_EJERCICIO + 1, 1, 1)),),
    ],
    ids=["no-declaration", "pension-is-work-income", "declared", "declared-only-after-the-ejercicio"],
)
def test_a_class_the_profile_declares_or_leaves_unknown_needs_evidence(
    tmp_path: Path, operation: PinnedAuthorityOperation, facts: tuple[UserProfileFact, ...]
) -> None:
    profile = _profile(operation, *facts)
    with isolated_runtime_profile(tmp_path=tmp_path):
        resolution = _resolve(profile=profile)
        without_profile = _resolve()
    for item in (resolution, without_profile):
        assert item.binding_values == {}
        assert _unresolved(item) == [
            ("unresolved_binding", _TRABAJO_BINDING, CalculationNoteSentence.RETENCION_SOPORTADA_EVIDENCE_REQUIRED),
        ]
        assert item.provenance == ()


def test_a_class_without_its_own_category_is_never_read_as_absent_from_the_profile(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    profile = _profile(operation, UserProfileFact(path=_CATEGORIES, value="trabajo"))
    revision = _revision(_binding(_ATRIBUCION_BINDING, "atribucion_capital_mobiliario"))
    with isolated_runtime_profile(tmp_path=tmp_path):
        resolution = _resolve(revision, profile)
        attest_retencion_soportada_absence(
            _attestation(RetencionSoportadaClase.ATRIBUCION_CAPITAL_MOBILIARIO),
            ports=_ports(operation),
            expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
        attested = _resolve(revision, profile)
    assert resolution.binding_values == {}
    assert _unresolved(resolution) == [
        ("unresolved_binding", _ATRIBUCION_BINDING, CalculationNoteSentence.RETENCION_SOPORTADA_EVIDENCE_REQUIRED),
    ]
    assert attested.binding_values == {_ATRIBUCION_BINDING: Decimal("0.00")}
    assert attested.diagnostics == ()
