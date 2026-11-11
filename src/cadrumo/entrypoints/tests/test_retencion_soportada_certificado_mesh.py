"""Certificates recorded through the registered executor feed the real suffered-withholding source mesh.

The executor runs against the real encrypted repository, the real write port, the
real attachment custody and the pinned authority; only the operation host's event
and operand plumbing is a minimal stand-in. All identifiers, files and amounts are
synthetic.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast, override
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.profile.retencion_soportada_certificado import (
    RetencionSoportadaCertificadoRepositoryAdapter,
)
from cadrumo.adapters.persistence.profile.retencion_soportada_evidence_custody import (
    RetencionSoportadaEvidenceCustodyAdapter,
)
from cadrumo.adapters.persistence.profile.tests.retencion_soportada_seed import active_bucket_custody
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from cadrumo.adapters.persistence.storage.secure_object_namespaces import ATTACHMENT_BLOB_NAMESPACE
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.retencion_soportada_repository import (
    PinnedRetencionSoportadaWriteAuthority,
    RetencionSoportadaPorts,
)
from cadrumo.application.aggregation.retencion_soportada_source import RetencionSoportadaSourceResolver
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.aggregation.source_resolution_operations import merge_source_resolutions
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.refusal_evidence import OperationRefusalEvidence
from cadrumo.application.retencion_soportada_certificado.contracts import (
    RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
)
from cadrumo.application.retencion_soportada_certificado.executor import RetencionSoportadaCertificadoExecutor
from cadrumo.application.retencion_soportada_certificado.ports import (
    RetencionSoportadaCertificadoPorts,
    RetencionSoportadaCertificateCustody,
)
from cadrumo.application.retencion_soportada_certificado.requests import RetencionSoportadaRecordRequest
from cadrumo.application.retencion_soportada_certificado.results import RetencionSoportadaOperationExecutionResult
from cadrumo.application.tests.operation_host_fakes import RecordingEvents
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.core.operations import OperationEffect, profile_operation_subject
from cadrumo.core.period import Period
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.renta.retencion_soportada import RetencionSoportadaOrigen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_PROFILE = "3f1c8b2e-5d4a-4e6b-9c7d-0a1b2c3d4e5f"
_TAXPAYER = "00000000T"
# Synthetic CIFs whose control digit is hand-derived: with every digit before it zero but the last, the
# odd-position doubling leaves 2 * d7 (digit-summed), so the control is (10 - 2 * d7) mod 10 -- 0, 8, 6.
_PAYER_A = "B00010090"
_PAYER_B = "B00010165"
_PAYER_WRONG_CONTROL = "B00000001"
_EJERCICIO = newest_authored_edition("100")
_BINDING = "renta-retencion-soportada-trabajo"
_LEGAL_REFS = ("ley-35-2006:art-99", "rd-439-2007:art-108")
_SOURCE_REFS = (f"aeat-modelo-100-instructions-{_EJERCICIO}",)


class _Cancellation:
    def __init__(self) -> None:
        self.inside = False

    @asynccontextmanager
    async def irreversible_section(self):
        self.inside = True
        try:
            yield
        finally:
            self.inside = False


class _Operands:
    def __init__(self, cancellation: _Cancellation) -> None:
        self._cancellation = cancellation
        self.value: BaseModel | None = None

    async def put(self, value: BaseModel, *, written_at: object) -> str:
        del written_at
        assert self._cancellation.inside
        self.value = value
        return "d" * 64


class _Context:
    def __init__(self, authority_operation: PinnedAuthorityOperation) -> None:
        self.identity = OperationIdentity(
            operation_id="c" * 64,
            definition_id=RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(_PROFILE),
        )
        self.authority_operation = authority_operation
        self.events = RecordingEvents()
        self.cancellation = _Cancellation()
        self.operands = _Operands(self.cancellation)


class _RacingCustody(RetencionSoportadaCertificateCustody):
    """The real custody, with one competing write landing while a certificate is being kept.

    It reproduces the only way a refusal can follow the keeping of the bytes: another
    writer moves the payer's row between the executor's check and its write.
    """

    def __init__(self, inner: RetencionSoportadaCertificateCustody, *, race: Callable[[], None]) -> None:
        self._inner = inner
        self._race = race

    @override
    def holds(self, fingerprint: str) -> bool:
        return self._inner.holds(fingerprint)

    @override
    def ingest(self, *, source_path: Path, data: bytes, mime_type: str, captured_at: datetime) -> str:
        kept = self._inner.ingest(source_path=source_path, data=data, mime_type=mime_type, captured_at=captured_at)
        self._race()
        return kept


def _custody() -> RetencionSoportadaEvidenceCustodyAdapter:
    return active_bucket_custody()


def _repository() -> RetencionSoportadaCertificadoRepositoryAdapter:
    return RetencionSoportadaCertificadoRepositoryAdapter(objects=secure_object_repository_for_active_bucket())


def _ports_factory(custody: RetencionSoportadaCertificateCustody | None = None):
    def factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> RetencionSoportadaCertificadoPorts:
        del profile_id
        return RetencionSoportadaCertificadoPorts(
            repository=_repository(),
            authority=PinnedRetencionSoportadaWriteAuthority(operation),
            custody=custody or _custody(),
            taxpayer_tax_id=lambda: _TAXPAYER,
        )

    return factory


def _certificate_file(directory: Path, name: str) -> bytes:
    """Write a synthetic certificate named ``name`` into ``directory`` and return its bytes."""
    data = f"%PDF-1.4 synthetic payer certificate {name}".encode()
    (directory / name).write_bytes(data)
    return data


def _request(
    payer: str,
    *,
    retencion: str,
    ingreso: str = "0.00",
    repercutido: str = "0.00",
    directory: Path | None = None,
    file: str | None = None,
    fingerprint: str | None = None,
    origin: RetencionSoportadaOrigen = RetencionSoportadaOrigen.PAYER_CERTIFICATE,
    expected_revision: str | None = None,
) -> OperationRequest[BaseModel]:
    return OperationRequest(
        definition_id=RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(_PROFILE),
        payload=RetencionSoportadaRecordRequest(
            profile_id=UUID(_PROFILE),
            ejercicio=_EJERCICIO,
            income_class=RetencionSoportadaClase.TRABAJO,
            payer_tax_id=payer,
            importe_integro_dinerario=PublicDecimal(decimal="20000.00"),
            valoracion_especie=PublicDecimal(decimal="0.00"),
            retencion=PublicDecimal(decimal=retencion),
            ingreso_a_cuenta=PublicDecimal(decimal=ingreso),
            ingreso_a_cuenta_repercutido=PublicDecimal(decimal=repercutido),
            origin=origin,
            evidence_fingerprint=fingerprint,
            source_path=file,
            source_directory=None if directory is None else str(directory),
            expected_revision_id=expected_revision,
        ),
    )


def _run_in(
    authority_operation: PinnedAuthorityOperation,
    request: OperationRequest[BaseModel],
    *,
    custody: RetencionSoportadaCertificateCustody | None = None,
) -> tuple[object, _Context]:
    context = _Context(authority_operation)
    executor = RetencionSoportadaCertificadoExecutor(
        _ports_factory(custody), definition_id=RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID
    )
    return asyncio.run(executor.execute(request, cast(OperationExecutorContext, context))), context


def _run(
    authority_operation: PinnedAuthorityOperation,
    request: OperationRequest[BaseModel],
    *,
    custody: RetencionSoportadaCertificateCustody | None = None,
) -> object:
    return _run_in(authority_operation, request, custody=custody)[0]


def _refusal_reason(context: _Context) -> str:
    result = context.operands.value
    assert isinstance(result, RetencionSoportadaOperationExecutionResult)
    assert result.refusal is not None
    return result.refusal.reason


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_recorded_certificates_resolve_to_the_hand_summed_class_credit(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    for name in ("a.pdf", "b.pdf", "own.pdf"):
        _certificate_file(files, name)
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):
        # Payer A: 1.200,00 retención + 300,00 ingreso a cuenta (repercutido, still credited); payer B: 450,00.
        for request in (
            _request(
                _PAYER_A, retencion="1200.00", ingreso="300.00", repercutido="300.00", directory=files, file="a.pdf"
            ),
            _request(_PAYER_B, retencion="450.00", directory=files, file="b.pdf"),
        ):
            assert not isinstance(_run(operation, request), OperationRefusalEvidence)
        own = _run(operation, _request(_TAXPAYER, retencion="10.00", directory=files, file="own.pdf"))
        assert isinstance(own, OperationRefusalEvidence)

        revision = ModeloRevision(
            id=f"{_EJERCICIO}-retencion-soportada-test",
            localization_key=f"test.schema.revision.{_EJERCICIO}-retencion-soportada-test.label",
            valid_from=date(_EJERCICIO, 1, 1),
            period_selector=PeriodSelector(years=(_EJERCICIO,), periods=("0A",)),
            legal_refs=_LEGAL_REFS,
            source_refs=_SOURCE_REFS,
            bindings=(
                BindingDefinition(
                    id=_BINDING,
                    provider={"kind": "retencion_soportada", "income_class": "trabajo", "quantity": "pago_a_cuenta"},
                    value={"data_type": "money", "channel": "decimal"},
                    legal_refs=_LEGAL_REFS,
                    source_refs=_SOURCE_REFS,
                ),
            ),
        )
        repository = _repository()
        resolver = RetencionSoportadaSourceResolver(ports=RetencionSoportadaPorts(repository=repository))
        resolution = merge_source_resolutions(
            (
                resolver.resolve(
                    CalculationSourceContext(
                        bucket_id="operator",
                        modelo="100",
                        filing_year=_EJERCICIO,
                        period=Period.from_year_and_code(_EJERCICIO, "0A"),
                        revision=revision,
                    )
                ),
            )
        )
        stored = repository.list_revisioned(_EJERCICIO)

    assert resolution.binding_values == {_BINDING: Decimal("1950.00")}
    assert len(stored) == 2
    assert all(revision_id != ABSENT_SECURE_OBJECT_REVISION_ID for _record, revision_id in stored)


def test_a_payer_id_failing_its_checksum_is_refused_and_nothing_is_stored(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    _certificate_file(files, "wrong.pdf")
    accepted_bytes = _certificate_file(files, "accepted.pdf")
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):
        refused, context = _run_in(
            operation, _request(_PAYER_WRONG_CONTROL, retencion="100.00", directory=files, file="wrong.pdf")
        )
        stored_after_refusal = _repository().list_revisioned(_EJERCICIO)
        accepted = _run(operation, _request(_PAYER_A, retencion="100.00", directory=files, file="accepted.pdf"))
        stored_after_success = _repository().list_revisioned(_EJERCICIO)
        refused_bytes_kept = _custody().holds(_sha256(b"%PDF-1.4 synthetic payer certificate wrong.pdf"))

    assert isinstance(refused, OperationRefusalEvidence)
    assert _refusal_reason(context) == "validation"
    assert stored_after_refusal == ()
    assert not refused_bytes_kept
    assert not isinstance(accepted, OperationRefusalEvidence)
    assert [record.evidence_fingerprint for record, _revision in stored_after_success] == [_sha256(accepted_bytes)]


def _printed_cif(cif: str) -> str:
    """Return a bare CIF in the hyphenated form a certificate prints: letter, seven digits, control."""
    return f"{cif[0]}-{cif[1:8]}-{cif[8]}"


def test_the_printed_and_bare_forms_of_one_payer_id_name_one_row(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    for name in ("first.pdf", "second.pdf"):
        _certificate_file(files, name)
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):
        first = _run(operation, _request(_PAYER_A, retencion="100.00", directory=files, file="first.pdf"))
        # The printed form of the same identifier meets the stored row, not an empty slot.
        printed, context = _run_in(
            operation, _request(_printed_cif(_PAYER_A), retencion="250.00", directory=files, file="second.pdf")
        )
        stored = _repository().list_revisioned(_EJERCICIO)

    assert not isinstance(first, OperationRefusalEvidence)
    assert isinstance(printed, OperationRefusalEvidence)
    assert _refusal_reason(context) == "stale_revision"
    assert [record.retencion for record, _revision in stored] == [Decimal("100.00")]


def test_importing_a_certificate_file_keeps_its_bytes_in_encrypted_custody_and_records_their_sha256(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    data = _certificate_file(files, "payer-a.pdf")
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE) as profile:
        outcome, context = _run_in(
            operation, _request(_PAYER_A, retencion="1200.00", directory=files, file="payer-a.pdf")
        )
        ((record, _revision),) = _repository().list_revisioned(_EJERCICIO)
        kept = AttachmentStore(objects=secure_object_repository_for_active_bucket()).read_bytes(_sha256(data))
        on_disk = b"".join(path.read_bytes() for path in profile.storage_root.rglob("*") if path.is_file())

    assert not isinstance(outcome, OperationRefusalEvidence)
    assert context.events.effects[-1] is OperationEffect.UPDATED
    assert record.evidence_fingerprint == _sha256(data)
    assert kept == data
    assert data not in on_disk
    assert b"synthetic payer certificate" not in on_disk


def test_a_fingerprint_alone_is_accepted_only_for_bytes_custody_holds(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    data = _certificate_file(files, "payer-a.pdf")
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):
        _run(operation, _request(_PAYER_A, retencion="100.00", directory=files, file="payer-a.pdf"))
        # The bytes are now in custody, so a second payer can cite them by their sha256.
        cited = _run(operation, _request(_PAYER_B, retencion="50.00", fingerprint=_sha256(data)))
        # A well formed sha256 of bytes this profile never kept is refused.
        invented, context = _run_in(
            operation, _request("A00010009", retencion="5.00", fingerprint=_sha256(b"never kept"))
        )
        stored = _repository().list_revisioned(_EJERCICIO)

    assert not isinstance(cited, OperationRefusalEvidence)
    assert isinstance(invented, OperationRefusalEvidence)
    assert _refusal_reason(context) == "certificate_not_in_custody"
    assert context.events.effects[-1] is OperationEffect.NONE
    assert len(stored) == 2


def test_a_fingerprint_whose_kept_bytes_were_replaced_is_refused(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    genuine = _sha256(_certificate_file(files, "genuine.pdf"))
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):
        objects = secure_object_repository_for_active_bucket()
        store = AttachmentStore(objects=objects)
        substitute = store.put_bytes(b"%PDF-1.4 substituted content")
        row = objects.load(
            ATTACHMENT_BLOB_NAMESPACE.namespace,
            substitute,
            expected_class=ATTACHMENT_BLOB_NAMESPACE.sensitivity,
            max_supported_version=ATTACHMENT_BLOB_NAMESPACE.schema_version,
        )
        assert row is not None
        # The address of the genuine certificate now holds the substitute's bytes.
        objects.save(
            namespace=ATTACHMENT_BLOB_NAMESPACE.namespace,
            object_key=genuine,
            classification=ATTACHMENT_BLOB_NAMESPACE.sensitivity,
            schema_version=ATTACHMENT_BLOB_NAMESPACE.schema_version,
            written_at=datetime(_EJERCICIO + 1, 4, 2, 9, 0, tzinfo=UTC),
            payload=row.payload,
        )
        refused, context = _run_in(operation, _request(_PAYER_A, retencion="100.00", fingerprint=genuine))
        stored = _repository().list_revisioned(_EJERCICIO)

    assert isinstance(refused, OperationRefusalEvidence)
    assert _refusal_reason(context) == "certificate_not_in_custody"
    assert stored == ()


def test_a_fingerprint_that_is_not_the_files_sha256_is_refused_before_anything_is_kept(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    data = _certificate_file(files, "payer-a.pdf")
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):
        refused, context = _run_in(
            operation,
            _request(
                _PAYER_A, retencion="100.00", directory=files, file="payer-a.pdf", fingerprint=_sha256(b"other bytes")
            ),
        )
        kept = _custody().holds(_sha256(data))
        agreeing = _run(
            operation,
            _request(_PAYER_A, retencion="100.00", directory=files, file="payer-a.pdf", fingerprint=_sha256(data)),
        )
        stored = _repository().list_revisioned(_EJERCICIO)

    assert isinstance(refused, OperationRefusalEvidence)
    assert _refusal_reason(context) == "certificate_fingerprint_mismatch"
    assert context.events.effects[-1] is OperationEffect.NONE
    assert not kept
    assert not isinstance(agreeing, OperationRefusalEvidence)
    assert len(stored) == 1


@pytest.mark.parametrize("name", ["missing.pdf", "notes.txt", "empty.pdf"])
def test_a_certificate_file_the_worker_cannot_read_or_admit_is_refused(
    tmp_path: Path, operation: PinnedAuthorityOperation, name: str
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    (files / "notes.txt").write_bytes(b"synthetic note")
    (files / "empty.pdf").write_bytes(b"")
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):
        refused, context = _run_in(operation, _request(_PAYER_A, retencion="100.00", directory=files, file=name))
        stored = _repository().list_revisioned(_EJERCICIO)

    assert isinstance(refused, OperationRefusalEvidence)
    assert _refusal_reason(context) == "certificate_file_unreadable"
    assert stored == ()


def test_a_record_the_write_would_refuse_leaves_no_certificate_bytes_in_custody(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    data = _certificate_file(files, "own.pdf")
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):
        refused, context = _run_in(operation, _request(_TAXPAYER, retencion="10.00", directory=files, file="own.pdf"))
        kept = _custody().holds(_sha256(data))

    assert isinstance(refused, OperationRefusalEvidence)
    assert _refusal_reason(context) == "own_tax_id"
    assert context.events.effects[-1] is OperationEffect.NONE
    assert not kept


def test_a_refusal_after_the_bytes_were_kept_reports_the_partial_effect(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    data = _certificate_file(files, "payer-a.pdf")
    rival = _certificate_file(files, "rival.pdf")
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):

        def rival_write() -> None:
            # Another writer records the same payer while this certificate is being kept.
            assert not isinstance(
                _run(operation, _request(_PAYER_A, retencion="999.00", directory=files, file="rival.pdf")),
                OperationRefusalEvidence,
            )

        refused, context = _run_in(
            operation,
            _request(_PAYER_A, retencion="100.00", directory=files, file="payer-a.pdf"),
            custody=_RacingCustody(_custody(), race=rival_write),
        )
        stored = _repository().list_revisioned(_EJERCICIO)
        kept = _custody().holds(_sha256(data))

    assert isinstance(refused, OperationRefusalEvidence)
    assert _refusal_reason(context) == "stale_revision"
    assert context.events.effects[-1] is OperationEffect.PARTIAL
    assert kept
    assert [(record.retencion, record.evidence_fingerprint) for record, _revision in stored] == [
        (Decimal("999.00"), _sha256(rival))
    ]


def test_correcting_the_figures_against_the_same_certificate_file_overwrites_the_row_and_keeps_the_lineage(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    data = _certificate_file(files, "payer-a.pdf")
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):
        first = _run(operation, _request(_PAYER_A, retencion="1200.00", directory=files, file="payer-a.pdf"))
        ((_, revision),) = _repository().list_revisioned(_EJERCICIO)
        # Without the stored revision the same file is a stale write, not a second row.
        unguarded, context = _run_in(
            operation, _request(_PAYER_A, retencion="1250.00", directory=files, file="payer-a.pdf")
        )
        corrected = _run(
            operation,
            _request(_PAYER_A, retencion="1250.00", directory=files, file="payer-a.pdf", expected_revision=revision),
        )
        ((record, new_revision),) = _repository().list_revisioned(_EJERCICIO)

    assert not isinstance(first, OperationRefusalEvidence)
    assert isinstance(unguarded, OperationRefusalEvidence)
    assert _refusal_reason(context) == "stale_revision"
    assert not isinstance(corrected, OperationRefusalEvidence)
    assert new_revision != revision
    assert record.retencion == Decimal("1250.00")
    assert record.evidence_fingerprint == record.replaces_evidence_fingerprint == _sha256(data)


def test_a_different_certificate_file_still_replaces_the_one_it_corrects(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    old = _certificate_file(files, "old.pdf")
    new = _certificate_file(files, "new.pdf")
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE):
        _run(operation, _request(_PAYER_A, retencion="1200.00", directory=files, file="old.pdf"))
        ((_, revision),) = _repository().list_revisioned(_EJERCICIO)
        replaced = _run(
            operation,
            _request(_PAYER_A, retencion="1300.00", directory=files, file="new.pdf", expected_revision=revision),
        )
        ((record, _revision),) = _repository().list_revisioned(_EJERCICIO)
        old_kept = _custody().holds(_sha256(old))

    assert not isinstance(replaced, OperationRefusalEvidence)
    assert record.retencion == Decimal("1300.00")
    assert record.evidence_fingerprint == _sha256(new)
    assert record.replaces_evidence_fingerprint == _sha256(old)
    # The replaced certificate's bytes stay in custody: they are still the evidence of the earlier reading.
    assert old_kept


def _served_key(reason: str) -> str:
    return f"aggregation.retencion_soportada.served.{reason}"


def _refusal_of(context: _Context):
    result = context.operands.value
    assert isinstance(result, RetencionSoportadaOperationExecutionResult)
    assert result.refusal is not None
    return result.refusal


def _assert_served(context: _Context, *, reason: str, key: str, language: OutputLanguage, tmp_path: Path) -> None:
    refusal = _refusal_of(context)
    words = refusal.refusal_words
    assert refusal.reason == reason
    assert refusal.refusal_words_language is language
    assert words == tr(_served_key(key), locale=language.value)
    assert words is not None
    assert not words.startswith("aggregation.")
    assert "--" not in words
    assert str(tmp_path) not in words
    assert "payer-a.pdf" not in words
    assert _sha256(b"never kept") not in words


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_every_refusal_the_operation_reaches_serves_its_own_sentence_in_the_workers_language(
    tmp_path: Path, operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    files = tmp_path / "certificates"
    files.mkdir()
    _certificate_file(files, "payer-a.pdf")
    _certificate_file(files, "second.pdf")
    _certificate_file(files, "own.pdf")
    attempts: list[tuple[str, str, _Context]] = []
    with (
        override_settings(cadrumo_output_language=language.value),
        isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE),
    ):

        def refused(reason: str, key: str, request: OperationRequest[BaseModel]) -> None:
            outcome, context = _run_in(operation, request)
            assert isinstance(outcome, OperationRefusalEvidence)
            attempts.append((reason, key, context))

        refused(
            "certificate_not_in_custody",
            "certificate_not_in_custody",
            _request(_PAYER_A, retencion="5.00", fingerprint=_sha256(b"never kept")),
        )
        refused(
            "certificate_file_unreadable",
            "certificate_file_unreadable",
            _request(_PAYER_A, retencion="5.00", directory=files, file="missing.pdf"),
        )
        refused(
            "certificate_fingerprint_mismatch",
            "certificate_fingerprint_mismatch",
            _request(
                _PAYER_A, retencion="5.00", directory=files, file="payer-a.pdf", fingerprint=_sha256(b"other bytes")
            ),
        )
        refused("own_tax_id", "own_tax_id", _request(_TAXPAYER, retencion="10.00", directory=files, file="own.pdf"))
        refused(
            "validation",
            "validation",
            _request(_PAYER_WRONG_CONTROL, retencion="100.00", directory=files, file="payer-a.pdf"),
        )
        refused(
            "repercutido_exceeds_ingreso_a_cuenta",
            "repercutido_exceeds_ingreso",
            _request(
                _PAYER_A, retencion="5.00", ingreso="1.00", repercutido="2.00", directory=files, file="payer-a.pdf"
            ),
        )
        refused(
            "certificate_fingerprint_required", "certificate_needs_fingerprint", _request(_PAYER_A, retencion="5.00")
        )
        _run(operation, _request(_PAYER_A, retencion="100.00", directory=files, file="payer-a.pdf"))
        refused(
            "stale_revision",
            "stale_revision",
            _request(_PAYER_A, retencion="200.00", directory=files, file="second.pdf"),
        )

    assert len(attempts) == 8
    for reason, key, context in attempts:
        _assert_served(context, reason=reason, key=key, language=language, tmp_path=tmp_path)


def test_a_refusal_for_a_profile_without_a_tax_id_serves_its_sentence(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    def no_taxpayer(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> RetencionSoportadaCertificadoPorts:
        del profile_id
        return RetencionSoportadaCertificadoPorts(
            repository=_repository(),
            authority=PinnedRetencionSoportadaWriteAuthority(operation),
            custody=_custody(),
            taxpayer_tax_id=lambda: None,
        )

    with (
        override_settings(cadrumo_output_language="en"),
        isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_PROFILE),
    ):
        context = _Context(operation)
        executor = RetencionSoportadaCertificadoExecutor(
            no_taxpayer, definition_id=RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID
        )
        asyncio.run(
            executor.execute(
                _request(_PAYER_A, retencion="5.00", fingerprint=_sha256(b"x")),
                cast(OperationExecutorContext, context),
            )
        )

    _assert_served(
        context,
        reason="taxpayer_tax_id_unknown",
        key="taxpayer_tax_id_unknown",
        language=OutputLanguage.EN,
        tmp_path=tmp_path,
    )


def test_the_served_sentences_differ_between_the_supported_languages(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    sentences: dict[OutputLanguage, str | None] = {}
    for language in OutputLanguage:
        with (
            override_settings(cadrumo_output_language=language.value),
            isolated_runtime_profile(tmp_path=tmp_path / f"profile-{language.value}", bucket_id=_PROFILE),
        ):
            _, context = _run_in(operation, _request(_PAYER_A, retencion="5.00", fingerprint=_sha256(b"never kept")))
        sentences[language] = _refusal_of(context).refusal_words

    assert all(sentences.values())
    assert len(set(sentences.values())) == len(OutputLanguage)
