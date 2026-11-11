"""Native CLI acceptance for the suffered-withholding certificate commands.

Every identifier and amount is synthetic. The payers' tax IDs must never appear
in command output or in any readable file the runtime leaves in the profile
storage root.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from cadrumo.entrypoints.cli.retencion_soportada_results import (
    RetencionSoportadaListResult,
    RetencionSoportadaRecordResult,
    RetencionSoportadaRemoveResult,
)
from cadrumo.tests.cli_envelope import unwrap_cli_result

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .cli_fixture_worlds import RegisteredCliProfile, cli_world_provider, invoke_joined_cli

_YEAR = filing_year_envelope().horizon


pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_TAXPAYER = "12345678Z"
_PAYER_A = "B00010082"
_PAYER_B = "B00010090"
_PAYER_C = "B00010165"
# Control digit 1 where the hand-derived CIF control of these digits is 0.
_PAYER_BAD_CONTROL = "B00000001"
_EJERCICIO = str(_YEAR)
_FIRST_CERTIFICATE = b"%PDF-1.4 first synthetic payer certificate"
_SECOND_CERTIFICATE = b"%PDF-1.4 second synthetic payer certificate"
_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Certificates",
    "identity.tax_id": _TAXPAYER,
    "activities.description": "synthetic payer certificate profile",
    "censo.activity_start_date": date(filing_year_envelope().floor, 1, 1).isoformat(),
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}
_PAYER_TAX_IDS = (_PAYER_A, _PAYER_B, _PAYER_C, _PAYER_BAD_CONTROL, _TAXPAYER)


@pytest.fixture
def native_certificate_profile(tmp_path: Path) -> Iterator[RegisteredCliProfile]:
    """Register one encrypted profile and supervise its native runtime worker."""
    with cli_world_provider().native_profile(tmp_path) as profile:
        profile.register(label="native-retencion-soportada", facts=_PROFILE_FACTS)
        yield profile


def _invoke(profile: RegisteredCliProfile, *command: str) -> Result:
    if profile.label is None:
        raise AssertionError("native certificate profile must be registered before invocation")
    close_active_bucket_session()
    result = invoke_joined_cli(
        (
            "--language",
            "en",
            "--format",
            "json",
            "--profile",
            profile.label,
            "--profile-secrets-stdin",
            "app",
            "ledger",
            "retencion-soportada",
            *command,
        ),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    for tax_id in _PAYER_TAX_IDS:
        assert tax_id not in result.output
    return result


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _certificate_file(profile: RegisteredCliProfile, data: bytes) -> Path:
    """Write a synthetic certificate beside, not inside, the profile storage root and return its path."""
    directory = profile.storage_root.parent / "certificate-files"
    directory.mkdir(exist_ok=True)
    path = directory / f"{_sha256(data)[:12]}.pdf"
    path.write_bytes(data)
    return path


def _record(
    profile: RegisteredCliProfile,
    payer: str,
    *,
    retencion: str,
    origin: str = "payer_certificate",
    ingreso_a_cuenta: str = "0.00",
    repercutido: str = "0.00",
    income_class: str = "trabajo",
    ejercicio: str = _EJERCICIO,
    certificate: bytes | None = _FIRST_CERTIFICATE,
    evidence_sha256: str | None = None,
    revision: str | None = None,
) -> Result:
    command = [
        "record",
        payer,
        "--ejercicio",
        ejercicio,
        "--income-class",
        income_class,
        "--origin",
        origin,
        "--retencion",
        retencion,
        "--ingreso-a-cuenta",
        ingreso_a_cuenta,
        "--ingreso-a-cuenta-repercutido",
        repercutido,
        "--importe-integro",
        "20000.00",
        "--payer-name",
        "Pagador Sintetico SL",
    ]
    if certificate is not None:
        command += ["--certificate-file", str(_certificate_file(profile, certificate))]
    if evidence_sha256 is not None:
        command += ["--evidence-sha256", evidence_sha256]
    if revision is not None:
        command += ["--expected-revision", revision]
    return _invoke(profile, *command)


def _listed(profile: RegisteredCliProfile) -> RetencionSoportadaListResult:
    result = _invoke(profile, "list", "--ejercicio", _EJERCICIO)
    assert result.exit_code == 0, result.output
    return RetencionSoportadaListResult.model_validate_json(json.dumps(unwrap_cli_result(result)))


def _refusal_context(result: Result) -> dict[str, object]:
    assert result.exit_code != 0, result.output
    document = STR_KEYED_MAPPING_ADAPTER.validate_python(json.loads(result.output))
    error = STR_KEYED_MAPPING_ADAPTER.validate_python(document["error"])
    context = STR_KEYED_MAPPING_ADAPTER.validate_python(error["context"])
    assert context["effect"] == "none"
    assert context["terminal_condition"] == "refused"
    return context


def _readable_files_with_tax_ids(root: Path) -> list[Path]:
    needles = tuple(tax_id.encode() for tax_id in _PAYER_TAX_IDS)
    found: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file():
            try:
                content = path.read_bytes()
            except OSError:
                continue
            if any(needle in content for needle in needles):
                found.append(path)
    return found


def _recorded(
    profile: RegisteredCliProfile,
    payer: str,
    *,
    retencion: str,
    origin: str = "payer_certificate",
    ingreso_a_cuenta: str = "0.00",
    repercutido: str = "0.00",
    income_class: str = "trabajo",
    certificate: bytes | None = _FIRST_CERTIFICATE,
    revision: str | None = None,
) -> RetencionSoportadaRecordResult:
    result = _record(
        profile,
        payer,
        retencion=retencion,
        origin=origin,
        ingreso_a_cuenta=ingreso_a_cuenta,
        repercutido=repercutido,
        income_class=income_class,
        certificate=certificate,
        revision=revision,
    )
    return RetencionSoportadaRecordResult.model_validate_json(json.dumps(unwrap_cli_result(result)))


def _record_two_certificates(
    profile: RegisteredCliProfile,
) -> RetencionSoportadaRecordResult:
    first = _recorded(profile, _PAYER_A, retencion="1000.00", ingreso_a_cuenta="300.00", repercutido="300.00")
    assert first.count == 1
    assert first.row.pago_a_cuenta == "1300.00"
    assert first.row.evidence_sha256 == _sha256(_FIRST_CERTIFICATE)
    assert first.row.origin == "payer_certificate"
    assert len(first.row.payer_ref) == 64

    second = _recorded(profile, _PAYER_B, retencion="450.00", origin="operator_declaration", certificate=None)
    assert second.count == 2
    assert second.row.evidence_sha256 is None
    return first


def _assert_revision_conflicts_refused(profile: RegisteredCliProfile) -> None:
    # A first record cannot overwrite a stored row, and a stale revision is refused.
    unguarded = _refusal_context(_record(profile, _PAYER_A, retencion="1200.00", certificate=_SECOND_CERTIFICATE))
    assert unguarded["reason"] == "stale_revision"
    assert unguarded["refusal_code"] == "REFUSED_RETENCION_SOPORTADA_REVISION_CONFLICT"
    stale = _refusal_context(
        _record(
            profile,
            _PAYER_A,
            retencion="1200.00",
            ingreso_a_cuenta="300.00",
            repercutido="300.00",
            certificate=_SECOND_CERTIFICATE,
            revision="f" * 64,
        )
    )
    assert stale["reason"] == "stale_revision"
    assert sorted(row.retencion for row in _listed(profile).rows) == ["1000.00", "450.00"]


def _replace_first_certificate(profile: RegisteredCliProfile, first: RetencionSoportadaRecordResult) -> None:
    # The correct revision replaces the row and records the certificate it supersedes.
    replaced = _recorded(
        profile,
        _PAYER_A,
        retencion="1200.00",
        ingreso_a_cuenta="300.00",
        repercutido="300.00",
        certificate=_SECOND_CERTIFICATE,
        revision=first.row.revision_id,
    )
    assert replaced.count == 2
    assert replaced.row.payer_ref == first.row.payer_ref
    assert replaced.row.revision_id != first.row.revision_id
    assert replaced.row.evidence_sha256 == _sha256(_SECOND_CERTIFICATE)


def _assert_invalid_records_refused(profile: RegisteredCliProfile) -> None:
    # Refusals: the taxpayer's own NIF, a payer ID whose check character fails, repercutido above the
    # ingreso a cuenta, an unsupported ejercicio, a certificate without its fingerprint and an unreadable amount.
    own = _refusal_context(_record(profile, _TAXPAYER, retencion="10.00"))
    assert own["reason"] == "own_tax_id"
    assert own["refusal_code"] == "REFUSED_RETENCION_SOPORTADA_WRITE"
    unchecked = _refusal_context(_record(profile, _PAYER_BAD_CONTROL, retencion="10.00"))
    assert unchecked["reason"] == "validation"
    excess = _refusal_context(
        _record(profile, _PAYER_C, retencion="10.00", ingreso_a_cuenta="100.00", repercutido="100.01")
    )
    assert excess["reason"] == "repercutido_exceeds_ingreso_a_cuenta"
    unsupported = _refusal_context(_record(profile, _PAYER_C, retencion="10.00", ejercicio="1999"))
    assert unsupported["reason"] == "ejercicio_unsupported"
    unfingerprinted = _refusal_context(_record(profile, _PAYER_C, retencion="10.00", certificate=None))
    assert unfingerprinted["reason"] == "certificate_fingerprint_required"
    # A fingerprint of bytes this profile never kept names no evidence.
    uncustodied = _refusal_context(
        _record(profile, _PAYER_C, retencion="10.00", certificate=None, evidence_sha256=_sha256(b"never kept"))
    )
    assert uncustodied["reason"] == "certificate_not_in_custody"
    # A fingerprint that is not the named file's is refused, and the file is not kept.
    mismatched = _refusal_context(
        _record(profile, _PAYER_C, retencion="10.00", evidence_sha256=_sha256(b"another file"))
    )
    assert mismatched["reason"] == "certificate_fingerprint_mismatch"
    assert mismatched["effect"] == "none"
    unreadable = _refusal_context(_record(profile, _PAYER_C, retencion="10.00", certificate=b""))
    assert unreadable["reason"] == "certificate_file_unreadable"
    malformed = _record(profile, _PAYER_C, retencion="1.234,50")
    assert malformed.exit_code != 0
    assert "1.234,50" in malformed.output


def _assert_refused_records_not_stored(profile: RegisteredCliProfile) -> None:
    # Nothing refused was stored; the class credits are the hand sum 1.200,00 + 300,00 + 450,00.
    listed = _listed(profile)
    assert listed.count == 2
    assert sum(Decimal(row.pago_a_cuenta) for row in listed.rows) == Decimal("1950.00")
    assert {row.payer_name for row in listed.rows} == {"Pagador Sintetico SL"}


def _remove_third_certificate(profile: RegisteredCliProfile) -> None:
    # Removal needs the revision the list showed.
    third = _recorded(profile, _PAYER_C, retencion="75.00", income_class="capital_mobiliario")
    assert third.count == 3
    target = ("--ejercicio", _EJERCICIO, "--income-class", "capital_mobiliario")
    stale_removal = _refusal_context(
        _invoke(profile, "remove", third.row.payer_ref, *target, "--expected-revision", "e" * 64)
    )
    assert stale_removal["reason"] == "stale_revision"
    removed = RetencionSoportadaRemoveResult.model_validate_json(
        json.dumps(
            unwrap_cli_result(
                _invoke(profile, "remove", third.row.payer_ref, *target, "--expected-revision", third.row.revision_id)
            )
        )
    )
    assert removed.count == 2
    assert removed.payer_ref == third.row.payer_ref
    missing = _refusal_context(
        _invoke(profile, "remove", third.row.payer_ref, *target, "--expected-revision", third.row.revision_id)
    )
    assert missing["reason"] == "not_found"
    assert _listed(profile).count == 2


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_native_certificates_record_replace_refuse_list_and_remove(
    native_certificate_profile: RegisteredCliProfile,
) -> None:
    profile = native_certificate_profile

    first = _record_two_certificates(profile)
    _assert_revision_conflicts_refused(profile)
    _replace_first_certificate(profile, first)
    _assert_invalid_records_refused(profile)
    _assert_refused_records_not_stored(profile)
    _remove_third_certificate(profile)

    assert _readable_files_with_tax_ids(profile.storage_root) == []
