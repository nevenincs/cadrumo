"""The file-verification acts, served by the real runtime, give the command line's verdicts.

The transport, the connection service, the installation door and the handlers
are the real ones. Each case builds the files with the application's own
builders and signers, then asks the same question of the command in this
process and of the act on the running runtime, and compares what comes back.
"""

from __future__ import annotations

import json
import sys
import time
import zipfile
from collections.abc import Generator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4

import pikepdf
import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation_client import RuntimeInstallationClient
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.outbound.calculation_summary_pdf.tests.summary_report_support import (
    render_summary,
    synthetic_keypair,
    synthetic_report,
)
from cadrumo.application.modelo.calculation_summary_pdf_ports import (
    SIGNATURE_ATTACHMENT_NAME,
    CalculationSummaryPdfUnreadableError,
)
from cadrumo.application.modelo.review_package import build_review_package
from cadrumo.application.modelo.review_package_counter_sign import counter_sign_review_package
from cadrumo.application.modelo.review_package_signing import ReviewPackageSigningKeypair, sign_review_package
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.runtime.installation_requests import (
    InstallationAct,
    RuntimeInstallationCompleted,
    RuntimeInstallationRefused,
    RuntimeReportVerifyDocumentReply,
    RuntimeReportVerifyDocumentRequest,
    RuntimeReviewPackageVerifyReceiptReply,
    RuntimeReviewPackageVerifyReceiptRequest,
    RuntimeReviewPackageVerifyReply,
    RuntimeReviewPackageVerifyRequest,
    RuntimeReviewPackageVerifySignatureReply,
    RuntimeReviewPackageVerifySignatureRequest,
)
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.output_rendering import jsonable_output_payload
from cadrumo.core.period import Period
from cadrumo.core.redaction.rules import CLI_BUCKET_ID_PLACEHOLDER, redact_structured_for_cli_output
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.bindings import CasillaObservation
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli
from cadrumo.tests.env_scope import derived_storage_settings

from ....runtime.installation_artefacts import register_artefact_acts
from ....runtime.tests.installation_registered_runtime import serving_registered_runtime
from ....runtime.tests.installation_runtime import InstallationLogin

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
]

_CLI = OperationFrontendProjection.CLI
_NOW = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)
_BASE_CASILLA = validated_casilla_id("base", surface="installation artefacts test")
_CUOTA_CASILLA = validated_casilla_id("cuota", surface="installation artefacts test")
_OPERATOR_BUCKET = "33333333-3333-4333-8333-333333333333"
_UNRELATED_KEY = "ab" * 32


def _work_unit(*, bucket_id: str) -> WorkUnit:
    period = Period.from_year_and_code(2026, "2T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id, modelo="303", filing_year=2026, period=period, revision_id="2026-y-siguientes"
        ),
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_id="2026-y-siguientes",
        name="303-2026-2T",
        created_at=_NOW,
        updated_at=_NOW,
        state=WorkUnitState.BORRADOR,
    )


def _revision(work_unit: WorkUnit) -> CalculationRevision:
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
            binding_overrides={},
            casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
            source_transaction_ids=(),
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        observations=(
            CasillaObservation(
                casilla_id=_CUOTA_CASILLA,
                value=Decimal("21.00"),
                legal_refs=("ley-37-1992:art-99",),
                source_refs=("test-installation-artefacts",),
            ),
        ),
        ledger_filing_evidence=None,
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        filed_at=None,
        filed_by=None,
        superseded_at=None,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _build_package(tmp_path: Path, *, bucket_id: str, operation: PinnedAuthorityOperation) -> Path:
    work_unit = _work_unit(bucket_id=bucket_id)
    output = tmp_path / "review-package.zip"
    build_review_package(
        revision=_revision(work_unit),
        work_unit=work_unit,
        draft_bytes=b"FICHERO-BOE-BYTES-FOR-INSTALLATION-ARTEFACTS-TEST",
        output_path=output,
        built_by="operator",
        operation=operation,
    )
    return output


def _tamper(package: Path) -> None:
    """Rewrite the draft member so it no longer matches the manifest."""
    rewritten = package.with_name(package.name + ".rewritten")
    with zipfile.ZipFile(package, "r") as source, zipfile.ZipFile(rewritten, "w") as target:
        for item in source.infolist():
            data = b"TAMPERED" if item.filename == "draft.fichero-boe" else source.read(item.filename)
            target.writestr(item, data)
    rewritten.replace(package)


@contextmanager
def _installed(tmp_path: Path) -> Generator[tuple[WindowsRuntimeEndpoint, Path]]:
    """Serve one storage root that the runtime and a command in this process both resolve."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    with derived_storage_settings(root):
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        with serving_registered_runtime(endpoint, root, InstallationLogin(owner=owner_id()), register_artefact_acts):
            yield endpoint, root


def _client(endpoint: WindowsRuntimeEndpoint) -> RuntimeInstallationClient:
    return RuntimeInstallationClient(
        VerifiedRuntimeConnection(
            endpoint.connect(timeout=3),
            expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
            deadline=time.monotonic() + 3,
        )
    )


@dataclass(frozen=True, slots=True)
class _Printed:
    """The result document one command printed, by default and with identifiers revealed."""

    default: dict[str, object]
    revealed: dict[str, object]


def _printed(arguments: tuple[str, ...]) -> tuple[int, dict[str, object]]:
    result = invoke_cached_cli(["--format", "json", *arguments])
    document: dict[str, object] = {}
    with suppress(ValueError, KeyError, TypeError):
        document = dict(json.loads(result.output)["result"])
    return result.exit_code, document


def _command(*arguments: str) -> tuple[int, _Printed]:
    """Run the command in this process; the result document it printed, empty when it printed none."""
    status, default = _printed(arguments)
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        _revealed_status, revealed = _printed(arguments)
    return status, _Printed(default=default, revealed=revealed)


def _signed_files(
    tmp_path: Path, package: Path
) -> tuple[Path, Path, ReviewPackageSigningKeypair, ReviewPackageSigningKeypair]:
    """Sign ``package`` as the operator and counter-sign it as the accountant; write both files."""
    operator = synthetic_keypair("installation-artefacts-operator")
    accountant = synthetic_keypair("installation-artefacts-accountant")
    signed = sign_review_package(package, keypair=operator)
    receipt = counter_sign_review_package(
        signed, counter_signer_keypair=accountant, note="reviewed, no changes", counter_signed_at=_NOW
    )
    signature_path = tmp_path / "signature.json"
    receipt_path = tmp_path / "receipt.json"
    signature_path.write_text(signed.model_dump_json(), encoding="utf-8")
    receipt_path.write_text(receipt.model_dump_json(), encoding="utf-8")
    return signature_path, receipt_path, operator, accountant


def _verify_package(client: RuntimeInstallationClient, package: Path, frontend=_CLI):
    return client.perform(
        RuntimeReviewPackageVerifyRequest(request_id=uuid4(), frontend=frontend, package=str(package)),
        RuntimeReviewPackageVerifyReply,
    )


def _document(reply: RuntimeInstallationCompleted) -> dict[str, object]:
    """A reply as the terminal interface and MCP show it, JSON-shaped: everything but the transport members."""
    shaped = jsonable_output_payload(
        reply.model_dump(exclude={"request_id", "runtime_boot_id", "connection_id", "kind"})
    )
    return dict(cast("Mapping[str, object]", shaped))


def _assert_prints(reply: RuntimeInstallationCompleted, printed: _Printed) -> None:
    """The command prints the reply's document: redacted as it always is, and whole when identifiers are revealed."""
    document = _document(reply)
    assert printed.revealed == document
    assert printed.default == redact_structured_for_cli_output(document, reveal_identifiers=False)


def test_a_genuine_package_verifies_clean_and_the_act_and_the_command_give_one_document(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    package = _build_package(tmp_path, bucket_id=_OPERATOR_BUCKET, operation=operation)

    with _installed(tmp_path) as (endpoint, _root), _client(endpoint) as client:
        reply = _verify_package(client, package)
        status, printed = _command("app", "modelo", "review-package", "verify", str(package))

    assert isinstance(reply, RuntimeReviewPackageVerifyReply)
    assert reply.is_clean
    assert reply.modelo == "303"
    # The reply carries the real bucket; the command hides it unless identifiers are revealed.
    assert printed.default["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    assert printed.revealed["bucket_id"] == reply.bucket_id
    assert status == 0
    _assert_prints(reply, printed)


def test_a_tampered_package_names_the_member_that_no_longer_matches(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    package = _build_package(tmp_path, bucket_id=_OPERATOR_BUCKET, operation=operation)
    _tamper(package)

    with _installed(tmp_path) as (endpoint, _root), _client(endpoint) as client:
        reply = _verify_package(client, package)
        status, printed = _command("app", "modelo", "review-package", "verify", str(package))

    assert isinstance(reply, RuntimeReviewPackageVerifyReply)
    assert not reply.is_clean
    assert reply.mismatched == ["draft.fichero-boe"]
    assert status == 0
    _assert_prints(reply, printed)


def test_a_missing_package_is_refused_as_an_integrity_failure_by_the_act_and_by_the_command(tmp_path: Path) -> None:
    absent = tmp_path / "absent.zip"

    with _installed(tmp_path) as (endpoint, _root), _client(endpoint) as client:
        refused = _verify_package(client, absent)
        status, _printed_by_command = _command("app", "modelo", "review-package", "verify", str(absent))

    assert isinstance(refused, RuntimeInstallationRefused)
    assert refused.act is InstallationAct.REVIEW_PACKAGE_VERIFY
    assert refused.detail.error_code == "REFUSED_MODELO_REVIEW_PACKAGE_INTEGRITY"
    assert status != 0


def test_a_signature_holds_for_its_signer_and_fails_for_any_other_key_or_a_changed_package(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    package = _build_package(tmp_path, bucket_id=_OPERATOR_BUCKET, operation=operation)
    signature, _receipt, operator, _accountant = _signed_files(tmp_path, package)

    def ask(client: RuntimeInstallationClient, key: str, frontend=_CLI):
        return client.perform(
            RuntimeReviewPackageVerifySignatureRequest(
                request_id=uuid4(), frontend=frontend, package=str(package), signature=str(signature), public_key=key
            ),
            RuntimeReviewPackageVerifySignatureReply,
        )

    def command(key: str) -> _Printed:
        status, printed = _command(
            "app", "modelo", "review-package", "verify-signature", str(package), str(signature), "--public-key", key
        )
        assert status == 0
        return printed

    shouted = operator.public_key_hex.upper()
    with _installed(tmp_path) as (endpoint, _root), _client(endpoint) as client:
        holds = ask(client, operator.public_key_hex)
        normalised = ask(client, f"  {shouted}  ")
        wrong = ask(client, _UNRELATED_KEY)
        command_holds = command(operator.public_key_hex)
        command_wrong = command(_UNRELATED_KEY)
        _tamper(package)
        changed = ask(client, operator.public_key_hex)

    for reply in (holds, normalised, wrong, changed):
        assert isinstance(reply, RuntimeReviewPackageVerifySignatureReply)
    assert holds.is_valid and normalised.is_valid
    assert normalised.signer_public_key_hex == operator.public_key_hex
    assert not wrong.is_valid
    assert not changed.is_valid
    for reply, printed in ((holds, command_holds), (wrong, command_wrong)):
        _assert_prints(reply, printed)


def test_a_signature_file_that_cannot_be_read_is_refused_by_the_act_and_by_the_command(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    package = _build_package(tmp_path, bucket_id=_OPERATOR_BUCKET, operation=operation)
    malformed = tmp_path / "malformed.json"
    malformed.write_text("not valid json at all", encoding="utf-8")
    absent = tmp_path / "absent.json"

    with _installed(tmp_path) as (endpoint, _root), _client(endpoint) as client:
        replies = [
            client.perform(
                RuntimeReviewPackageVerifySignatureRequest(
                    request_id=uuid4(), frontend=_CLI, package=str(package), signature=str(path), public_key="0" * 64
                ),
                RuntimeReviewPackageVerifySignatureReply,
            )
            for path in (malformed, absent)
        ]
        statuses = [
            _command(
                "app", "modelo", "review-package", "verify-signature", str(package), str(path), "--public-key", "0" * 64
            )[0]
            for path in (malformed, absent)
        ]

    for refused in replies:
        assert isinstance(refused, RuntimeInstallationRefused)
        assert refused.detail.error_code == "ERROR_MODELO_REVIEW_PACKAGE_SIGNING"
    assert all(status != 0 for status in statuses)


def test_a_receipt_holds_only_for_both_keys_and_the_package_it_was_made_for(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    package = _build_package(tmp_path, bucket_id=_OPERATOR_BUCKET, operation=operation)
    _signature, receipt, operator, accountant = _signed_files(tmp_path, package)

    def ask(client: RuntimeInstallationClient, operator_key: str, counter_key: str):
        return client.perform(
            RuntimeReviewPackageVerifyReceiptRequest(
                request_id=uuid4(),
                frontend=_CLI,
                package=str(package),
                receipt=str(receipt),
                operator_public_key=operator_key,
                counter_signer_public_key=counter_key,
            ),
            RuntimeReviewPackageVerifyReceiptReply,
        )

    def command(operator_key: str, counter_key: str) -> _Printed:
        status, printed = _command(
            "app",
            "modelo",
            "review-package",
            "verify-receipt",
            str(package),
            str(receipt),
            "--operator-public-key",
            operator_key,
            "--counter-signer-public-key",
            counter_key,
        )
        assert status == 0
        return printed

    with _installed(tmp_path) as (endpoint, _root), _client(endpoint) as client:
        holds = ask(client, operator.public_key_hex, accountant.public_key_hex)
        wrong_counter = ask(client, operator.public_key_hex, _UNRELATED_KEY)
        swapped = ask(client, accountant.public_key_hex, operator.public_key_hex)
        command_holds = command(operator.public_key_hex, accountant.public_key_hex)
        command_wrong = command(operator.public_key_hex, _UNRELATED_KEY)
        _tamper(package)
        changed = ask(client, operator.public_key_hex, accountant.public_key_hex)

    for reply in (holds, wrong_counter, swapped, changed):
        assert isinstance(reply, RuntimeReviewPackageVerifyReceiptReply)
    assert holds.is_valid
    assert not wrong_counter.is_valid and not swapped.is_valid and not changed.is_valid
    for reply, printed in ((holds, command_holds), (wrong_counter, command_wrong)):
        _assert_prints(reply, printed)


def test_a_receipt_file_that_cannot_be_read_is_refused(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> None:
    package = _build_package(tmp_path, bucket_id=_OPERATOR_BUCKET, operation=operation)
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{}", encoding="utf-8")

    with _installed(tmp_path) as (endpoint, _root), _client(endpoint) as client:
        refused = [
            client.perform(
                RuntimeReviewPackageVerifyReceiptRequest(
                    request_id=uuid4(),
                    frontend=_CLI,
                    package=str(package),
                    receipt=str(path),
                    operator_public_key="0" * 64,
                    counter_signer_public_key="1" * 64,
                ),
                RuntimeReviewPackageVerifyReceiptReply,
            )
            for path in (malformed, tmp_path / "absent.json")
        ]

    for reply in refused:
        assert isinstance(reply, RuntimeInstallationRefused)
        assert reply.detail.error_code == "ERROR_MODELO_REVIEW_PACKAGE_COUNTER_SIGNING"


def _verify_report(client: RuntimeInstallationClient, path: Path, trusted_key: str | None = None, frontend=_CLI):
    return client.perform(
        RuntimeReportVerifyDocumentRequest(
            request_id=uuid4(), frontend=frontend, path=str(path), trusted_key=trusted_key
        ),
        RuntimeReportVerifyDocumentReply,
    )


def _command_report(path: Path, *extra: str) -> tuple[int, _Printed]:
    return _command("app", "modelo", "work", "report-verify", str(path), "--document-only", *extra)


def _genuine_summary(tmp_path: Path) -> Path:
    summary = tmp_path / "summary.pdf"
    summary.write_bytes(render_summary(synthetic_report(OutputLanguage.ES), keypair=synthetic_keypair()).payload)
    return summary


def _tampered_summary(summary: Path, target: Path) -> Path:
    with pikepdf.open(summary) as pdf:
        signature = bytearray(pdf.attachments[SIGNATURE_ATTACHMENT_NAME].get_file().read_bytes())
        signature[0] ^= 0x01
        pdf.attachments[SIGNATURE_ATTACHMENT_NAME].obj.EF.F.write(bytes(signature))
        pdf.save(target)
    return target


def test_a_summary_is_checked_by_its_own_bytes_and_the_act_and_the_command_give_one_document(
    tmp_path: Path,
) -> None:
    summary = _genuine_summary(tmp_path)
    tampered = _tampered_summary(summary, tmp_path / "tampered.pdf")
    key = synthetic_keypair().public_key_hex

    with _installed(tmp_path) as (endpoint, _root), _client(endpoint) as client:
        unpinned = _verify_report(client, summary)
        pinned = _verify_report(client, summary, key)
        shouted = _verify_report(client, summary, f" {key.upper()} ")
        other_key = _verify_report(client, summary, _UNRELATED_KEY)
        forged = _verify_report(client, tampered)
        commands = {
            "unpinned": _command_report(summary),
            "pinned": _command_report(summary, "--trusted-key", key),
            "other_key": _command_report(summary, "--trusted-key", _UNRELATED_KEY),
            "forged": _command_report(tampered),
        }

    replies = {"unpinned": unpinned, "pinned": pinned, "other_key": other_key, "forged": forged}
    for reply in (*replies.values(), shouted):
        assert isinstance(reply, RuntimeReportVerifyDocumentReply)
    assert unpinned.outcome == "valid_unpinned"
    assert pinned.outcome == "verified"
    assert shouted.outcome == "verified"
    assert other_key.outcome == "refused"
    assert forged.outcome == "refused"
    assert not any(reply.store_checked for reply in replies.values())
    for name, reply in replies.items():
        status, printed = commands[name]
        # The command exits non-zero on a refusal, and still prints the document.
        assert (status != 0) == (reply.outcome == "refused")
        _assert_prints(reply, printed)


def test_a_summary_the_act_cannot_read_or_a_key_that_is_not_a_key_is_refused(tmp_path: Path) -> None:
    summary = _genuine_summary(tmp_path)

    with _installed(tmp_path) as (endpoint, _root), _client(endpoint) as client:
        absent = _verify_report(client, tmp_path / "absent.pdf")
        malformed_key = _verify_report(client, summary, "not-a-key")
        command_statuses = [
            _command_report(tmp_path / "absent.pdf")[0],
            _command_report(summary, "--trusted-key", "not-a-key")[0],
        ]

    assert isinstance(absent, RuntimeInstallationRefused)
    assert absent.detail.error_code == get_registered_error_code(CalculationSummaryPdfUnreadableError).code
    assert isinstance(malformed_key, RuntimeInstallationRefused)
    assert malformed_key.detail.error_code == "ERROR_MODELO_REVIEW_PACKAGE_SIGNING"
    assert all(status != 0 for status in command_statuses)


def test_every_frontend_gets_the_same_verdict_for_each_file_check(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    package = _build_package(tmp_path, bucket_id=_OPERATOR_BUCKET, operation=operation)
    signature, receipt, operator, accountant = _signed_files(tmp_path, package)
    summary = _genuine_summary(tmp_path)
    answers: dict[OperationFrontendProjection, list[dict[str, object]]] = {}

    with _installed(tmp_path) as (endpoint, _root):
        for frontend in (OperationFrontendProjection.CLI, OperationFrontendProjection.TUI):
            with _client(endpoint) as client:
                replies = (
                    _verify_package(client, package, frontend),
                    client.perform(
                        RuntimeReviewPackageVerifySignatureRequest(
                            request_id=uuid4(),
                            frontend=frontend,
                            package=str(package),
                            signature=str(signature),
                            public_key=operator.public_key_hex,
                        ),
                        RuntimeReviewPackageVerifySignatureReply,
                    ),
                    client.perform(
                        RuntimeReviewPackageVerifyReceiptRequest(
                            request_id=uuid4(),
                            frontend=frontend,
                            package=str(package),
                            receipt=str(receipt),
                            operator_public_key=operator.public_key_hex,
                            counter_signer_public_key=accountant.public_key_hex,
                        ),
                        RuntimeReviewPackageVerifyReceiptReply,
                    ),
                    _verify_report(client, summary, synthetic_keypair().public_key_hex, frontend),
                )
                answers[frontend] = [
                    reply.model_dump(mode="json", exclude={"request_id", "connection_id"}) for reply in replies
                ]

    assert len(answers) == 2
    assert answers[OperationFrontendProjection.CLI] == answers[OperationFrontendProjection.TUI]
    kinds = [reply["kind"] for reply in answers[OperationFrontendProjection.CLI]]
    assert kinds == [
        "review_package_verify_reply",
        "review_package_verify_signature_reply",
        "review_package_verify_receipt_reply",
        "report_verify_document_reply",
    ]
