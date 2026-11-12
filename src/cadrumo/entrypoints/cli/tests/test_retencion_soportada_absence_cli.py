"""Native CLI acceptance for attesting and withdrawing the absence of a payer on an income class.

Every identifier and note is synthetic. An attestation is the operator's own
statement: it is refused beside payer records of its class, guarded by the
revision it was stored at, and never listed as a payer certificate.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from cadrumo.entrypoints.cli.retencion_soportada_absence_results import (
    RetencionSoportadaAttestAbsenceResult,
    RetencionSoportadaListAbsencesResult,
    RetencionSoportadaWithdrawAbsenceResult,
)
from cadrumo.entrypoints.cli.retencion_soportada_results import RetencionSoportadaListResult
from cadrumo.tests.cli_envelope import unwrap_cli_result

from .cli_fixture_worlds import RegisteredCliProfile, cli_world_provider, invoke_joined_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_TAXPAYER = "12345678Z"
_PAYER = "B00010090"
_EJERCICIO = "2025"
_NOTE = "Synthetic note: the bank paid no interest subject to withholding."
_ABSENCE_CODE = "REFUSED_RETENCION_SOPORTADA_ABSENCE"
_REVISION_CODE = "REFUSED_RETENCION_SOPORTADA_REVISION_CONFLICT"
_MOVABLE_CAPITAL_LABEL_BY_LANGUAGE = {
    "en": "Income from movable capital",
    "es": "Rendimientos del capital mobiliario",
    "ca": "Rendiments del capital mobiliari",
    "hu": "Ingóvagyon-jövedelem (tőkejövedelem)",
}
_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Absences",
    "identity.tax_id": _TAXPAYER,
    "activities.description": "synthetic absence attestation profile",
    "censo.activity_start_date": "2020-01-01",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


@pytest.fixture
def native_absence_profile(tmp_path: Path) -> Iterator[RegisteredCliProfile]:
    """Register one encrypted profile and supervise its native runtime worker."""
    with cli_world_provider().native_profile(tmp_path) as profile:
        profile.register(label="native-retencion-soportada-absence", facts=_PROFILE_FACTS)
        yield profile


def _invoke(profile: RegisteredCliProfile, *command: str, language: str = "en") -> Result:
    if profile.label is None:
        raise AssertionError("native absence profile must be registered before invocation")
    close_active_bucket_session()
    result = invoke_joined_cli(
        (
            "--language",
            language,
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
    assert _PAYER not in result.output
    return result


def _target(income_class: str) -> tuple[str, ...]:
    return ("--ejercicio", _EJERCICIO, "--income-class", income_class)


def _attest(
    profile: RegisteredCliProfile, income_class: str, *, note: str = _NOTE, revision: str | None = None
) -> Result:
    command = ["attest-absence", *_target(income_class), "--note", note]
    if revision is not None:
        command += ["--expected-revision", revision]
    return _invoke(profile, *command)


def _withdraw(profile: RegisteredCliProfile, income_class: str, revision: str) -> Result:
    return _invoke(profile, "withdraw-absence", *_target(income_class), "--expected-revision", revision)


def _attested(result: Result) -> RetencionSoportadaAttestAbsenceResult:
    return RetencionSoportadaAttestAbsenceResult.model_validate_json(json.dumps(unwrap_cli_result(result)))


def _listed(
    profile: RegisteredCliProfile, ejercicio: str = _EJERCICIO, *, language: str = "en"
) -> RetencionSoportadaListAbsencesResult:
    return RetencionSoportadaListAbsencesResult.model_validate_json(
        json.dumps(unwrap_cli_result(_invoke(profile, "list-absences", "--ejercicio", ejercicio, language=language)))
    )


def _refusal_context(result: Result) -> dict[str, object]:
    assert result.exit_code != 0, result.output
    document = STR_KEYED_MAPPING_ADAPTER.validate_python(json.loads(result.output))
    error = STR_KEYED_MAPPING_ADAPTER.validate_python(document["error"])
    context = STR_KEYED_MAPPING_ADAPTER.validate_python(error["context"])
    assert context["effect"] == "none"
    assert context["terminal_condition"] == "refused"
    assert _NOTE not in result.output
    return context


def _record_trabajo_payer(profile: RegisteredCliProfile) -> None:
    recorded = _invoke(
        profile,
        "record",
        _PAYER,
        *_target("trabajo"),
        "--origin",
        "operator_declaration",
        "--retencion",
        "1200.00",
        "--ingreso-a-cuenta",
        "300.00",
        "--ingreso-a-cuenta-repercutido",
        "0.00",
        "--importe-integro",
        "20000.00",
        "--reducciones-aplicables",
        "0.00",
        "--gastos-deducibles",
        "0.00",
        "--payer-name",
        "Pagador Sintetico SL",
    )
    assert recorded.exit_code == 0, recorded.output


def _stored_bytes(profile: RegisteredCliProfile) -> bytes:
    # A runtime lock file is held open by the worker and carries no stored content.
    return b"".join(
        path.read_bytes() for path in profile.storage_root.rglob("*") if path.is_file() and path.suffix != ".lock"
    )


@pytest.mark.windows_only
def test_native_absence_is_attested_and_a_repeat_is_refused(native_absence_profile: RegisteredCliProfile) -> None:
    profile = native_absence_profile

    # Nothing is stored yet: an empty year lists as an empty result, not an error.
    empty = _listed(profile)
    assert (empty.ejercicio, empty.count, empty.attestations) == (int(_EJERCICIO), 0, [])

    first = _attested(_attest(profile, "capital_mobiliario"))
    assert first.attestation.ejercicio == int(_EJERCICIO)
    assert first.attestation.income_class == "capital_mobiliario"
    assert first.attestation.state == "active"
    assert first.attestation.note == _NOTE
    assert first.attestation.withdrawn_at is None

    # A second attestation without the stored revision is stale; with it, the class is already attested.
    unguarded = _refusal_context(_attest(profile, "capital_mobiliario"))
    assert (unguarded["reason"], unguarded["refusal_code"]) == ("stale_revision", _REVISION_CODE)
    repeated = _refusal_context(_attest(profile, "capital_mobiliario", revision=first.attestation.revision_id))
    assert (repeated["reason"], repeated["refusal_code"]) == ("already_attested", _ABSENCE_CODE)
    assert repeated["income_class"] == "capital_mobiliario"


@pytest.mark.windows_only
def test_native_absence_is_refused_beside_payer_records_and_never_listed_as_a_certificate(
    native_absence_profile: RegisteredCliProfile,
) -> None:
    profile = native_absence_profile

    # A class that already holds a payer record cannot be attested absent.
    _record_trabajo_payer(profile)
    beside_records = _refusal_context(_attest(profile, "trabajo"))
    assert (beside_records["reason"], beside_records["refusal_code"]) == ("records_present", _ABSENCE_CODE)
    unsupported = _refusal_context(
        _invoke(
            profile, "attest-absence", "--ejercicio", "1999", "--income-class", "ganancia_patrimonial", "--note", _NOTE
        )
    )
    assert unsupported["reason"] == "ejercicio_unsupported"
    blank = _attest(profile, "ganancia_patrimonial", note="   ")
    assert blank.exit_code != 0

    # The certificate listing shows the payer record only; an attestation is never a certificate.
    listed = RetencionSoportadaListResult.model_validate_json(
        json.dumps(unwrap_cli_result(_invoke(profile, "list", "--ejercicio", _EJERCICIO)))
    )
    assert listed.count == 1
    assert [row.income_class for row in listed.rows] == ["trabajo"]
    assert _PAYER.encode() not in _stored_bytes(profile)


@pytest.mark.windows_only
def test_native_absence_is_withdrawn_under_its_revision_and_stays_listed(
    native_absence_profile: RegisteredCliProfile,
) -> None:
    profile = native_absence_profile
    first = _attested(_attest(profile, "capital_mobiliario"))

    # Withdrawal needs the stored revision, and a withdrawn attestation cannot be withdrawn again.
    stale = _refusal_context(_withdraw(profile, "capital_mobiliario", "f" * 64))
    assert (stale["reason"], stale["refusal_code"]) == ("stale_revision", _REVISION_CODE)
    withdrawn = RetencionSoportadaWithdrawAbsenceResult.model_validate_json(
        json.dumps(unwrap_cli_result(_withdraw(profile, "capital_mobiliario", first.attestation.revision_id)))
    )
    assert withdrawn.attestation.state == "withdrawn"
    assert withdrawn.attestation.attested_at == first.attestation.attested_at
    assert withdrawn.attestation.withdrawn_at is not None
    assert withdrawn.attestation.revision_id != first.attestation.revision_id
    again = _refusal_context(_withdraw(profile, "capital_mobiliario", withdrawn.attestation.revision_id))
    assert (again["reason"], again["refusal_code"]) == ("not_attested", _ABSENCE_CODE)

    # A withdrawn attestation stays listed, with the revision a replacing attestation needs.
    (withdrawn_row,) = _listed(profile).attestations
    assert (withdrawn_row.income_class, withdrawn_row.state) == ("capital_mobiliario", "withdrawn")
    assert withdrawn_row.revision_id == withdrawn.attestation.revision_id
    assert withdrawn_row.income_class_label == _MOVABLE_CAPITAL_LABEL_BY_LANGUAGE["en"]


@pytest.mark.windows_only
def test_native_absence_listing_labels_the_class_in_the_requested_language(
    native_absence_profile: RegisteredCliProfile,
) -> None:
    profile = native_absence_profile
    _attested(_attest(profile, "capital_mobiliario"))

    # The label follows the language of the invocation, not the language the profile's worker renders in:
    # each of the four languages must name the class in its own words, so at most one can be the profile's.
    labels = {
        language: _listed(profile, language=language).attestations[0].income_class_label
        for language in _MOVABLE_CAPITAL_LABEL_BY_LANGUAGE
    }
    assert labels == _MOVABLE_CAPITAL_LABEL_BY_LANGUAGE


@pytest.mark.windows_only
def test_native_withdrawn_absence_is_reattested_and_listed_per_ejercicio(
    native_absence_profile: RegisteredCliProfile,
) -> None:
    profile = native_absence_profile
    first = _attested(_attest(profile, "capital_mobiliario"))
    withdrawn = RetencionSoportadaWithdrawAbsenceResult.model_validate_json(
        json.dumps(unwrap_cli_result(_withdraw(profile, "capital_mobiliario", first.attestation.revision_id)))
    )

    # The decision is reversible: a new attestation replaces the withdrawn one under its revision.
    reattested = _attested(_attest(profile, "capital_mobiliario", revision=withdrawn.attestation.revision_id))
    assert reattested.attestation.state == "active"
    assert reattested.attestation.revision_id != withdrawn.attestation.revision_id

    # The listing is per ejercicio and carries each stored revision and note.
    (active_row,) = _listed(profile).attestations
    assert active_row.state == "active"
    assert active_row.revision_id == reattested.attestation.revision_id
    assert active_row.note == _NOTE
    assert _listed(profile, "2024").attestations == []
    assert _NOTE.encode() not in _stored_bytes(profile)
