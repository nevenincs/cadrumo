"""Suffered-withholding records through the real encrypted store, write path and source mesh.

All tax identifiers and amounts are synthetic. Expected totals are worked by
hand: a payer's credit is its retención plus its whole ingreso a cuenta, and the
binding of a class adds the credits of every payer of that class.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.aggregation.retencion_soportada_repository import (
    PinnedRetencionSoportadaWriteAuthority,
    RetencionSoportadaPorts,
    RetencionSoportadaRevisionConflictError,
    RetencionSoportadaWriteRefusedError,
    record_retencion_soportada,
    retencion_soportada_record_key,
)
from .....application.aggregation.retencion_soportada_source import RetencionSoportadaSourceResolver
from .....application.aggregation.source_mesh import CalculationSourceContext
from .....application.aggregation.source_resolution_operations import merge_source_resolutions
from .....core.aggregation import BindingSourceKind
from .....core.external_constants import UTF_8_ENCODING
from .....core.period import Period
from .....core.retencion_soportada import RetencionSoportadaClase
from .....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from .....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from .....domain.calculations.registry.schema_references import PeriodSelector
from .....domain.renta.retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord
from ...storage.runtime_repository import secure_object_repository_for_active_bucket
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..retencion_soportada_records import RetencionSoportadaRecordRepositoryAdapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_TAXPAYER = "00000000T"
_PAYER_A = "B00000001"
_PAYER_B = "B00000002"
_PAYER_C = "B00000003"
_EJERCICIO = 2025
_SECOND_PROFILE = "22222222-2222-4222-8222-222222222222"
_LEGAL_REFS = ("ley-35-2006:art-99", "rd-439-2007:art-108")
_SOURCE_REFS = ("aeat-modelo-100-instructions-2025",)
_TRABAJO_BINDING = "renta-retencion-soportada-trabajo"
_CAPITAL_BINDING = "renta-retencion-soportada-capital-mobiliario"


class _FamilyDeclaredAuthority:
    """The write authority of a generation whose Modelo 100 declares the family.

    The bundled registry binds no casilla to the family yet, so the refusals
    that need a declared family are reached through this answer; the refusals
    the real authority gives are tested against it separately below.
    """

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self._pinned = PinnedRetencionSoportadaWriteAuthority(operation)

    def admits_ejercicio(self, ejercicio: int) -> bool:
        return self._pinned.admits_ejercicio(ejercicio)

    def declares_family(self, ejercicio: int) -> bool:
        del ejercicio
        return True


def _repository() -> RetencionSoportadaRecordRepositoryAdapter:
    return RetencionSoportadaRecordRepositoryAdapter(objects=secure_object_repository_for_active_bucket())


def _record(
    repository: RetencionSoportadaRecordRepositoryAdapter,
    *,
    payer: str = _PAYER_A,
    income_class: RetencionSoportadaClase = RetencionSoportadaClase.TRABAJO,
    retencion: str = "1200.00",
    ingreso_a_cuenta: str = "300.00",
    repercutido: str = "300.00",
    fingerprint: str = "1" * 64,
    replaces: str | None = None,
    ejercicio: int = _EJERCICIO,
) -> RetencionSoportadaRecord:
    return RetencionSoportadaRecord(
        ejercicio=ejercicio,
        payer_tax_id=payer,
        payer_legal_name="Pagador Sintetico SL",
        payer_ref=repository.payer_reference(payer),
        income_class=income_class,
        importe_integro_dinerario=Decimal("20000.00"),
        valoracion_especie=Decimal("1000.00"),
        retencion=Decimal(retencion),
        ingreso_a_cuenta=Decimal(ingreso_a_cuenta),
        ingreso_a_cuenta_repercutido=Decimal(repercutido),
        origin=RetencionSoportadaOrigen.PAYER_CERTIFICATE,
        evidence_fingerprint=fingerprint,
        replaces_evidence_fingerprint=replaces,
        captured_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
    )


def _write(
    repository: RetencionSoportadaRecordRepositoryAdapter,
    record: RetencionSoportadaRecord,
    operation: PinnedAuthorityOperation,
    *,
    expected_revision_id: str = ABSENT_SECURE_OBJECT_REVISION_ID,
) -> None:
    record_retencion_soportada(
        record,
        repository=repository,
        authority=_FamilyDeclaredAuthority(operation),
        taxpayer_tax_id=_TAXPAYER,
        expected_revision_id=expected_revision_id,
    )


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
        id="2025-retencion-soportada-test",
        localization_key="test.schema.revision.2025-retencion-soportada-test.label",
        valid_from=date(2025, 1, 1),
        period_selector=PeriodSelector(years=(_EJERCICIO,), periods=("0A",)),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        bindings=bindings,
    )


def _context(revision: ModeloRevision) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id="operator",
        modelo="100",
        filing_year=_EJERCICIO,
        period=Period.from_year_and_code(_EJERCICIO, "0A"),
        revision=revision,
    )


def _resolve(repository: RetencionSoportadaRecordRepositoryAdapter, revision: ModeloRevision):
    resolver = RetencionSoportadaSourceResolver(ports=RetencionSoportadaPorts(repository=repository))
    return merge_source_resolutions((resolver.resolve(_context(revision)),))


def test_a_record_survives_the_encrypted_store_and_its_payer_is_never_plaintext(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = _repository()
        record = _record(repository)
        _write(repository, record, operation)

        assert repository.load_records(_EJERCICIO) == (record,)
        assert repository.load_records(_EJERCICIO + 1) == ()
        stored, revision_id = repository.load_revisioned(record.identity)
        assert stored == record
        assert revision_id != ABSENT_SECURE_OBJECT_REVISION_ID

        key = retencion_soportada_record_key(record.identity)
        unkeyed = {
            hashlib.sha256(_PAYER_A.encode(UTF_8_ENCODING)).hexdigest(),
            hashlib.sha256(_PAYER_A.lower().encode(UTF_8_ENCODING)).hexdigest(),
        }
        assert key == f"{_EJERCICIO}:trabajo:{record.payer_ref}"
        assert _PAYER_A not in key and _PAYER_A.lower() not in key
        assert record.payer_ref not in unkeyed
        assert not any(digest in key for digest in unkeyed)

        on_disk = b"".join(path.read_bytes() for path in profile.storage_root.rglob("*") if path.is_file())
        assert _PAYER_A.encode(UTF_8_ENCODING) not in on_disk
        assert b"Pagador Sintetico" not in on_disk


def test_the_payer_reference_is_stable_within_a_profile_and_differs_across_profiles(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path / "first"):
        first = _repository()
        reference = first.payer_reference(_PAYER_A)
        assert first.payer_reference(f"  {_PAYER_A.lower()} ") == reference
        assert first.payer_reference(_PAYER_B) != reference
    with isolated_runtime_profile(tmp_path=tmp_path / "second", bucket_id=_SECOND_PROFILE):
        assert _repository().payer_reference(_PAYER_A) != reference


def test_a_payer_carrying_the_taxpayers_own_tax_id_is_refused(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        with pytest.raises(RetencionSoportadaWriteRefusedError) as refused:
            _write(repository, _record(repository, payer=f" {_TAXPAYER.lower()}"), operation)
        assert refused.value.reason == "own_tax_id"
        assert repository.load_records(_EJERCICIO) == ()


def test_the_real_authority_refuses_an_unsupported_ejercicio_and_an_undeclared_family(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    authority = PinnedRetencionSoportadaWriteAuthority(operation)
    unsupported = 2000
    assert not authority.admits_ejercicio(unsupported)
    assert authority.admits_ejercicio(_EJERCICIO)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        for ejercicio, reason in ((unsupported, "ejercicio_unsupported"), (_EJERCICIO, "family_not_declared")):
            with pytest.raises(RetencionSoportadaWriteRefusedError) as refused:
                record_retencion_soportada(
                    _record(repository, ejercicio=ejercicio),
                    repository=repository,
                    authority=authority,
                    taxpayer_tax_id=_TAXPAYER,
                    expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
                )
            assert refused.value.reason == reason
        assert repository.load_records(_EJERCICIO) == ()


def test_a_record_whose_reference_is_not_this_profiles_digest_is_refused(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        forged = _record(repository).model_copy(
            update={"payer_ref": hashlib.sha256(_PAYER_A.encode(UTF_8_ENCODING)).hexdigest()},
        )
        with pytest.raises(RetencionSoportadaWriteRefusedError) as refused:
            _write(repository, forged, operation)
        assert refused.value.reason == "identity_mismatch"
        assert repository.load_records(_EJERCICIO) == ()


def test_an_overwrite_needs_the_stored_revision_and_the_replaced_certificate(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        original = _record(repository)
        _write(repository, original, operation)
        _, stored_revision = repository.load_revisioned(original.identity)
        correction = _record(repository, retencion="1250.00", fingerprint="2" * 64, replaces="1" * 64)

        with pytest.raises(RetencionSoportadaRevisionConflictError):
            _write(repository, correction, operation)
        with pytest.raises(RetencionSoportadaWriteRefusedError) as refused:
            _write(
                repository,
                _record(repository, retencion="1250.00", fingerprint="2" * 64, replaces="3" * 64),
                operation,
                expected_revision_id=stored_revision,
            )
        assert refused.value.reason == "identity_mismatch"
        with pytest.raises(RetencionSoportadaWriteRefusedError):
            _write(
                repository, _record(repository, fingerprint="2" * 64), operation, expected_revision_id=stored_revision
            )
        assert repository.load_records(_EJERCICIO) == (original,)

        _write(repository, correction, operation, expected_revision_id=stored_revision)
        assert repository.load_records(_EJERCICIO) == (correction,)
        with pytest.raises(RetencionSoportadaRevisionConflictError):
            _write(repository, correction, operation, expected_revision_id=stored_revision)


def test_a_first_record_cannot_claim_to_replace_a_certificate(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        with pytest.raises(RetencionSoportadaWriteRefusedError) as refused:
            _write(repository, _record(repository, replaces="9" * 64), operation)
        assert refused.value.reason == "identity_mismatch"


def test_no_record_leaves_every_family_binding_unresolved_and_never_zero(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        resolution = _resolve(_repository(), _revision(_binding(_TRABAJO_BINDING, "trabajo")))
    assert resolution.binding_values == {}
    assert [(item.reason, item.binding_id) for item in resolution.diagnostics] == [
        ("unresolved_binding", _TRABAJO_BINDING),
    ]
    assert resolution.provenance == ()


def test_a_revision_without_the_family_reads_nothing(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        _write(repository, _record(repository), operation)
        resolver = RetencionSoportadaSourceResolver(ports=RetencionSoportadaPorts(repository=repository))
        assert resolver.load_calculation_records(period=_context(_revision()).period, revision=_revision()) is None
        resolution = resolver.resolve(_context(_revision()))
    assert resolution.binding_values == {}
    assert resolution.diagnostics == ()


def test_two_payers_of_one_class_sum_and_each_other_class_stays_distinct(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        _write(repository, _record(repository, payer=_PAYER_A), operation)
        _write(
            repository,
            _record(repository, payer=_PAYER_B, retencion="800.00", ingreso_a_cuenta="0.00", repercutido="0.00"),
            operation,
        )
        _write(
            repository,
            _record(repository, payer=_PAYER_C, income_class=RetencionSoportadaClase.GANANCIA_PATRIMONIAL),
            operation,
        )
        resolution = _resolve(
            repository,
            _revision(_binding(_TRABAJO_BINDING, "trabajo"), _binding(_CAPITAL_BINDING, "capital_mobiliario")),
        )

    # Payer A: 1.200,00 + 300,00 (repercutido, still credited); payer B: 800,00.
    assert resolution.binding_values == {_TRABAJO_BINDING: Decimal("2300.00")}
    reasons = sorted((item.reason, item.binding_id) for item in resolution.diagnostics)
    assert reasons == [("unresolved_binding", _CAPITAL_BINDING), ("unrouted_observation", None)]
    assert all(_PAYER_C not in item.message and "1200" not in item.message for item in resolution.diagnostics)
    assert len(resolution.provenance) == 2
    for node in resolution.provenance:
        assert node.resolved_binding_source is BindingSourceKind.RETENCION_SOPORTADA
        assert node.terminal_origin is TerminalOriginClass.PAYER_CERTIFICATE
        assert node.fingerprint == "1" * 64
        assert node.source_ref is not None
        assert _PAYER_A not in node.source_ref and _PAYER_B not in node.source_ref


def test_a_zero_record_is_a_proven_zero(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = _repository()
        _write(
            repository,
            _record(repository, retencion="0.00", ingreso_a_cuenta="0.00", repercutido="0.00"),
            operation,
        )
        resolution = _resolve(repository, _revision(_binding(_TRABAJO_BINDING, "trabajo")))
    assert resolution.binding_values == {_TRABAJO_BINDING: Decimal("0.00")}
    assert resolution.diagnostics == ()
