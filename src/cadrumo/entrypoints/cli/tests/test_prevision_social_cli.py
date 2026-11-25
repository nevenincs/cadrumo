"""Native CLI acceptance for the pension contribution certificate commands.

Every identifier and amount is synthetic, and the ejercicio comes from the
published support envelope. The issuer's and the plans' tax IDs must never
appear in command output or in any readable file the runtime leaves in the
profile storage root.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.cli.prevision_social_results import (
    PrevisionSocialListResult,
    PrevisionSocialRecordResult,
    PrevisionSocialRemoveResult,
)
from cadrumo.tests.cli_envelope import unwrap_cli_result

from .cli_fixture_worlds import RegisteredCliProfile, cli_world_provider, invoke_joined_cli

pytestmark = [pytest.mark.integration, pytest.mark.windows_only, pytest.mark.hex_entrypoint]

_TAXPAYER = "12345678Z"
# Synthetic CIFs with hand-derived control digits (see the executor mesh test).
_ISSUER = "V00010082"
_PLAN_A = "V00010090"
_PLAN_B = "V00010165"
_FIRST_CERTIFICATE = b"%PDF-1.4 first synthetic pension contribution certificate"
_SECOND_CERTIFICATE = b"%PDF-1.4 second synthetic pension contribution certificate"
_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Contributions",
    "identity.tax_id": _TAXPAYER,
    "activities.description": "synthetic pension contribution profile",
    "tax_residence.jurisdiction_scope": "common_regime",
}
_TAX_IDS = (_ISSUER, _PLAN_A, _PLAN_B)


@pytest.fixture
def native_contribution_profile(tmp_path: Path) -> Iterator[RegisteredCliProfile]:
    """Register one encrypted profile and supervise its native runtime worker."""
    with cli_world_provider().native_profile(tmp_path) as profile:
        profile.register(label="native-prevision-social", facts=_PROFILE_FACTS)
        yield profile


def _invoke(profile: RegisteredCliProfile, *command: str) -> Result:
    if profile.label is None:
        raise AssertionError("native contribution profile must be registered before invocation")
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
            "prevision-social",
            *command,
        ),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    for tax_id in _TAX_IDS:
        assert tax_id not in result.output
    return result


def _certificate_file(profile: RegisteredCliProfile, data: bytes) -> Path:
    """Write a synthetic certificate beside, not inside, the profile storage root and return its path."""
    directory = profile.storage_root.parent / "certificate-files"
    directory.mkdir(exist_ok=True)
    path = directory / f"{hashlib.sha256(data).hexdigest()[:12]}.pdf"
    path.write_bytes(data)
    return path


def _record(
    profile: RegisteredCliProfile,
    ejercicio: int,
    *options: str,
    certificate: bytes | None = _FIRST_CERTIFICATE,
) -> Result:
    command = ["record", _ISSUER, "--ejercicio", str(ejercicio), "--issuer-name", "Gestora Sintetica SA", *options]
    if certificate is not None:
        command += ["--certificate-file", str(_certificate_file(profile, certificate))]
    return _invoke(profile, *command)


def _recorded(result: Result) -> PrevisionSocialRecordResult:
    assert result.exit_code == 0, result.output
    return PrevisionSocialRecordResult.model_validate_json(json.dumps(unwrap_cli_result(result)))


def _refusal(result: Result) -> dict[str, object]:
    assert result.exit_code != 0, result.output
    document = STR_KEYED_MAPPING_ADAPTER.validate_python(json.loads(result.output))
    error = STR_KEYED_MAPPING_ADAPTER.validate_python(document["error"])
    context = STR_KEYED_MAPPING_ADAPTER.validate_python(error["context"])
    assert context.get("effect") == "none", result.output
    assert context["terminal_condition"] == "refused"
    return context


def _listed(profile: RegisteredCliProfile, ejercicio: int) -> PrevisionSocialListResult:
    result = _invoke(profile, "list", "--ejercicio", str(ejercicio))
    assert result.exit_code == 0, result.output
    return PrevisionSocialListResult.model_validate_json(json.dumps(unwrap_cli_result(result)))


def _readable_files_with_tax_ids(root: Path) -> list[Path]:
    needles = tuple(tax_id.encode() for tax_id in _TAX_IDS)
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


def _assert_refused_at_record_time(profile: RegisteredCliProfile, ejercicio: int) -> None:
    unplaced = _refusal(_record(profile, ejercicio, "--clave", "D", "--subclave", "01", "--amount", "300.00"))
    assert unplaced["reason"] == "unplaced_clave"
    assert unplaced["refusal_code"] == "REFUSED_PREVISION_SOCIAL_CONTRIBUTION_WRITE"
    unstated = _refusal(
        _record(profile, ejercicio, "--clave", "J", "--subclave", "01", "--amount", "300.00", "--plan-nif", _PLAN_B)
    )
    assert unstated["reason"] == "same_plan_split_unstated"
    undefined = _refusal(_record(profile, ejercicio, "--clave", "B", "--subclave", "01", "--amount", "300.00"))
    assert undefined["reason"] == "clave_pair_undefined"
    unevidenced = _refusal(
        _record(profile, ejercicio, "--clave", "A", "--subclave", "01", "--amount", "300.00", certificate=None)
    )
    assert unevidenced["reason"] == "certificate_fingerprint_required"
    malformed = _record(profile, ejercicio, "--clave", "A", "--subclave", "01", "--amount", "1.234,50")
    assert malformed.exit_code != 0
    assert _listed(profile, ejercicio).count == 0


def _correct_and_remove(profile: RegisteredCliProfile, ejercicio: int) -> None:
    first = _recorded(
        _record(profile, ejercicio, "--clave", "A", "--subclave", "01", "--amount", "1000.00", "--plan-nif", _PLAN_A)
    )
    assert first.count == 1
    assert first.row.casilla_id is not None
    same_plan = _recorded(
        _record(
            profile,
            ejercicio,
            *("--clave", "J", "--subclave", "01", "--amount", "400.00", "--plan-nif", _PLAN_B),
            *("--employer-same-plan", "yes"),
        )
    )
    assert same_plan.row.employer_same_plan is True
    assert same_plan.row.casilla_id != first.row.casilla_id

    correction = ("--clave", "A", "--subclave", "01", "--amount", "1100.00", "--plan-nif", _PLAN_A)
    stale = _refusal(
        _record(profile, ejercicio, *correction, "--expected-revision", "f" * 64, certificate=_SECOND_CERTIFICATE)
    )
    assert stale["reason"] == "stale_revision"
    assert stale["refusal_code"] == "REFUSED_PREVISION_SOCIAL_CONTRIBUTION_REVISION_CONFLICT"
    corrected = _recorded(
        _record(
            profile,
            ejercicio,
            *correction,
            "--expected-revision",
            first.row.revision_id,
            certificate=_SECOND_CERTIFICATE,
        )
    )
    assert corrected.row.amount == "1100.00"
    assert corrected.row.replaces_evidence_sha256 == first.row.evidence_sha256
    assert corrected.count == 2

    target = (
        corrected.row.issuer_ref,
        *("--ejercicio", str(ejercicio), "--clave", "A", "--subclave", "01"),
        *("--plan-ref", str(corrected.row.plan_ref)),
    )
    stale_removal = _refusal(_invoke(profile, "remove", *target, "--expected-revision", first.row.revision_id))
    assert stale_removal["reason"] == "stale_revision"
    removed = PrevisionSocialRemoveResult.model_validate_json(
        json.dumps(
            unwrap_cli_result(_invoke(profile, "remove", *target, "--expected-revision", corrected.row.revision_id))
        )
    )
    assert removed.count == 1
    missing = _refusal(_invoke(profile, "remove", *target, "--expected-revision", corrected.row.revision_id))
    assert missing["reason"] == "not_found"
    assert [row.amount for row in _listed(profile, ejercicio).rows] == ["400.00"]


def test_native_contributions_refuse_record_correct_list_and_remove(
    native_contribution_profile: RegisteredCliProfile, operation: PinnedAuthorityOperation
) -> None:
    profile = native_contribution_profile
    ejercicio = min(operation.supported_filing_years().years)

    _assert_refused_at_record_time(profile, ejercicio)
    _correct_and_remove(profile, ejercicio)

    assert _readable_files_with_tax_ids(profile.storage_root) == []
