"""A censal certificate file previewed and enrolled by the operation itself, through the real supervisor.

The shipped certificate parser refuses every document until an issued specimen
pins its layout, so the cases that reach an enrollment compose the operation
with a parser for a synthetic layout: the certified axes as JSON after the PDF
magic. The file is still read by the operation, through its own handle, and
what it holds decides the result. The refusals are those of the shipped parser.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from ...adapters.inbound.censo.parser import parse_certificado_censal_bytes
from ...application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...application.operations.models import OperationRequest
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.user_profile.access_contracts import AccessAction, Availability
from ...application.user_profile.censal_certificate_operation import (
    CENSAL_CERTIFICATE_OPERATION_DEFINITION_ID,
    CensalCertificateOperationProjection,
    CensalCertificateOperationRequest,
    censal_certificate_operation,
    read_censal_certificate,
)
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.projections import record_to_effective_facts
from ...core.config import override_settings
from ...core.errors.error_codes import get_registered_error_code
from ...core.external_constants import PROVENANCE_SOURCE_CENSO_ARTEFACT
from ...core.i18n.render import tr
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.censo.certificado import (
    ActividadLocalCertificada,
    CertificadoCensalParseError,
    CertificadoSituacionCensal,
)
from ...domain.user_profile.values import UserProfileRecord
from ..cli.config._censo_payloads import CensoFactPayload, CensoFileIngestResult
from .command_line_rendering import (
    Printed,
    as_the_command_line_renders,
    command_error,
    json_document,
    redacted_as_printed,
)
from .profile_operation_supervisor import SettledOperation, SupervisedProfile, supervised_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_PDF_MAGIC = b"%PDF-"
_FISCAL_ADDRESS = "Calle de la Prueba 1, 28013 Madrid"
_REPRESENTATIVE = "12345678Z"


def _certificate() -> CertificadoSituacionCensal:
    """Build the synthetic certificate under the pinned authority its representative's tax id is checked against."""
    return CertificadoSituacionCensal(
        domicilio_fiscal=_FISCAL_ADDRESS,
        condicion_residencia="Residente en territorio español",
        representantes_nif=(_REPRESENTATIVE,),
        situacion_tributaria=("Alta en el censo de empresarios",),
        actividades=(
            ActividadLocalCertificada(descripcion="Consultoría informática", epigrafe_iae="763"),
            ActividadLocalCertificada(descripcion="Formación no reglada"),
        ),
        obligaciones_periodicas=("Modelo 303 trimestral",),
    )


def _synthetic_layout(data: bytes) -> CertificadoSituacionCensal:
    """Parse the synthetic layout these cases write."""
    if not data.startswith(_PDF_MAGIC):
        raise CertificadoCensalParseError(translated_message="errors.censo.certificado_not_a_pdf")
    return CertificadoSituacionCensal.model_validate_json(data.removeprefix(_PDF_MAGIC))


def _submit(profile: SupervisedProfile, certificate: Path, *, preview: bool) -> SettledOperation:
    return profile.run(
        definition_id=CENSAL_CERTIFICATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile.profile_id)),
        payload=CensalCertificateOperationRequest(
            profile_id=profile.profile_id, certificate_path=certificate, preview=preview
        ),
    )


def _record(profile: SupervisedProfile) -> UserProfileRecord:
    return ProfileRecordRepository.for_current_session(
        profile.profile_id, profile_decode_context=profile.decode_context
    ).load(profile.profile_id)


def _command_prints(certificate: Path, *, applied: bool) -> Printed:
    """Return what ``config profile censo import`` prints for this certificate.

    The command itself cannot be run to a result: its parser refuses every
    document. Its result model is built as the command builds it, from the
    reading the command and the operation share, and passed through the
    envelope's own serialisation and redaction.
    """
    ingest = read_censal_certificate(certificate.read_bytes(), parse=_synthetic_layout).ingest(applied=applied)
    rows = tuple(CensoFactPayload(path=row.path, value=row.value, source=row.source) for row in ingest.facts)
    result = CensoFileIngestResult(applied=ingest.applied, certificate=ingest.certificate, facts=rows)
    return Printed(
        default=as_the_command_line_renders(result),
        revealed=as_the_command_line_renders(result, reveal_identifiers=True),
    )


def _assert_command_prints(result: CensalCertificateOperationProjection, printed: Printed) -> None:
    """The command prints the result's document after its own redaction, in either reveal setting.

    Revealing identifiers reveals profile and bucket identifiers only, so a
    certified tax id stays hidden in what the command prints and whole in the
    result.
    """
    document = json_document(result)
    assert printed.default == redacted_as_printed(document)
    assert printed.revealed == redacted_as_printed(document, reveal_identifiers=True)


def test_a_named_certificate_file_is_previewed_without_a_write_and_then_enrolled(tmp_path: Path) -> None:
    certificate = tmp_path / "certificado.pdf"
    certificate.write_bytes(_PDF_MAGIC + _certificate().model_dump_json().encode("utf-8"))

    with (
        supervised_profile(tmp_path, (censal_certificate_operation(_synthetic_layout),)) as profile,
        override_settings(cadrumo_active_profile=str(profile.profile_id)),
    ):
        before = _record(profile)
        previewed = _submit(profile, certificate, preview=True)
        preview = profile.result(previewed, CensalCertificateOperationProjection)
        after_preview = _record(profile)
        imported = _submit(profile, certificate, preview=False)
        enrolled = profile.result(imported, CensalCertificateOperationProjection)
        after_import = _record(profile)
        printed_preview = _command_prints(certificate, applied=False)
        printed_import = _command_prints(certificate, applied=True)

    assert (previewed.receipt.condition, previewed.receipt.effect) == (
        OperationTerminalCondition.SUCCEEDED,
        OperationEffect.NONE,
    )
    assert preview.applied is False
    assert [(fact.path, fact.value, fact.source) for fact in preview.facts] == [
        ("contact.fiscal_address", _FISCAL_ADDRESS, PROVENANCE_SOURCE_CENSO_ARTEFACT),
        ("activities.description", "Consultoría informática", PROVENANCE_SOURCE_CENSO_ARTEFACT),
        ("activities.iae_epigraph", "763", PROVENANCE_SOURCE_CENSO_ARTEFACT),
        ("activities.1.description", "Formación no reglada", PROVENANCE_SOURCE_CENSO_ARTEFACT),
    ]
    assert after_preview.record_revision == before.record_revision
    assert (imported.receipt.condition, imported.receipt.effect) == (
        OperationTerminalCondition.SUCCEEDED,
        OperationEffect.UPDATED,
    )
    assert enrolled.applied is True
    assert (enrolled.certificate, enrolled.facts) == (preview.certificate, preview.facts)
    assert after_import.record_revision == before.record_revision + 1
    effective = record_to_effective_facts(after_import)
    assert effective["contact.fiscal_address"].value == _FISCAL_ADDRESS
    assert effective["contact.fiscal_address"].source == PROVENANCE_SOURCE_CENSO_ARTEFACT
    # The result carries the certified values themselves; the command redacts when it prints.
    assert preview.certificate.representantes_nif == (_REPRESENTATIVE,)
    _assert_command_prints(preview, printed_preview)
    _assert_command_prints(enrolled, printed_import)


@pytest.mark.parametrize(
    ("content", "message_key"),
    [
        (b"%PDF-1.7 no specimen pins this layout", "errors.censo.certificado_extraction_unpinned"),
        (b"not a certificate", "errors.censo.certificado_not_a_pdf"),
    ],
)
def test_the_shipped_parser_refuses_the_file_for_a_direct_client_as_it_does_for_the_command(
    tmp_path: Path, content: bytes, message_key: str
) -> None:
    certificate = tmp_path / "certificado.pdf"
    certificate.write_bytes(content)

    with (
        supervised_profile(tmp_path, (censal_certificate_operation(parse_certificado_censal_bytes),)) as profile,
        override_settings(cadrumo_active_profile=str(profile.profile_id), cadrumo_output_language="en"),
    ):
        before = _record(profile)
        printed = command_error("config", "profile", "censo", "import", "--file", str(certificate))
        outcomes = [_submit(profile, certificate, preview=preview) for preview in (True, False)]
        details = [profile.error_detail(outcome) for outcome in outcomes]
        after = _record(profile)
        message = tr(message_key)

    for outcome, detail in zip(outcomes, details, strict=True):
        assert outcome.receipt.condition is not OperationTerminalCondition.SUCCEEDED
        assert outcome.receipt.effect is OperationEffect.NONE
        assert detail.error_code == get_registered_error_code(CertificadoCensalParseError).code == printed["code"]
        assert detail.message_key == message_key
    assert printed["message"] == message
    assert after.record_revision == before.record_revision


def test_a_file_that_cannot_be_opened_is_refused_by_reason(tmp_path: Path) -> None:
    with (
        supervised_profile(tmp_path, (censal_certificate_operation(_synthetic_layout),)) as profile,
        override_settings(cadrumo_active_profile=str(profile.profile_id)),
    ):
        absent = _submit(profile, tmp_path / "absent.pdf", preview=True)
        relative = _submit(profile, Path("certificado.pdf"), preview=False)
        reasons = [profile.error_detail(outcome).context_mapping()["reason"] for outcome in (absent, relative)]

    assert reasons == ["not_found", "relative_path"]
    assert all(outcome.receipt.effect is OperationEffect.NONE for outcome in (absent, relative))


def test_every_frontend_resolves_the_same_access_and_a_preview_declares_no_commit() -> None:
    definition, registration = censal_certificate_operation(_synthetic_layout)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    profile_id = uuid4()
    command_line = OperationFrontendProjection.CLI

    for preview in (True, False):
        request = OperationRequest(
            definition_id=CENSAL_CERTIFICATE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            payload=CensalCertificateOperationRequest(
                profile_id=profile_id, certificate_path=Path("/synthetic/certificado.pdf"), preview=preview
            ),
        )
        policies = {
            frontend: resolve_operation_access(
                registry=registry,
                request=request,
                context=OperationAccessContext(
                    profile_id=profile_id,
                    destination_id=profile_id,
                    action=AccessAction.SUBMIT,
                    frontend=frontend,
                    contract=registration.contract,
                    published_authority=Availability.AVAILABLE,
                ),
            ).policy
            for frontend in OperationFrontendProjection
        }
        assert len(policies) == 3
        assert all(policy == policies[command_line] for policy in policies.values())
        assert (AccessAction.COMMIT in policies[command_line].actions) is not preview
