"""Profile-create choice help must match the values refused at runtime."""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

import pytest

from ....domain.deadlines import (
    M303RegimeComposition,
    M303TaxTerritory,
    taxpayer_profile_from_mapping,
)
from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _isolated_env(tmp_path: Path) -> dict[str, str | None]:
    return {
        "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "cadrumo-local"),
        "CADRUMO_SECRET_STORE_BACKEND": "file",
        "CADRUMO_SECRET_STORE_DIR": str(tmp_path / "secret-store"),
        "CADRUMO_SECRET_PASSPHRASE": "profile-choice-help-passphrase",
        "CADRUMO_DATABASE_URL": None,
        "COLUMNS": "1200",
    }


def test_profile_create_minimal_example_creates_a_ready_profile(tmp_path: Path) -> None:
    """The command advertised as minimal must run and satisfy profile readiness."""

    env = _isolated_env(tmp_path)
    help_result = invoke_cached_cli(
        ["--language", "en", "config", "profile", "create", "--help"],
        env=env,
    )
    assert help_result.exit_code == 0, help_result.output
    compact_help = " ".join(help_result.output.split())
    match = re.search(r"Minimal freelancer profile: (?P<command>aeat config profile create .+)$", compact_help)
    assert match is not None, help_result.output

    command = match.group("command")
    replacements = {
        "PROFILE": "minimal-profile",
        "<DNI/NIE/NIF>": "00000000T",
        "<NAME>": "Minimal",
        "<SURNAMES>": "Operator",
        "<ACTIVITY>": "consulting",
    }
    for placeholder, value in replacements.items():
        command = command.replace(placeholder, value)
    command = re.sub(r"(?<=-)\s+(?=[a-z])", "", command)
    argv = shlex.split(command)
    assert argv[:2] == ["aeat", "config"]

    created = invoke_cached_cli(["--language", "en", *argv[1:]], env=env)
    assert created.exit_code == 0, created.output
    status = invoke_cached_cli(["--language", "en", "config", "profile", "status"], env=env)
    assert status.exit_code == 0, status.output
    assert "readiness\tblocked" not in status.output
    assert "profile\tminimal-profile" in status.output

    shown = invoke_cached_cli(
        ["--format", "json", "--language", "en", "config", "profile", "show", "minimal-profile"],
        env=env,
    )
    assert shown.exit_code == 0, shown.output
    envelope = json.loads(shown.output)
    facts = {row["path"]: row["value"] for row in envelope["result"]["facts"]}
    assert str(facts.pop("identity.tax_id")).startswith("sha256:")
    profile = taxpayer_profile_from_mapping(facts, tax_id_default="00000000T")
    assert profile.iva is not None
    assert profile.iva.tax_territory is M303TaxTerritory.COMMON_REGIME
    assert profile.iva.regime_composition is M303RegimeComposition.GENERAL
    assert profile.iva.redeme_enrolled is False
    assert profile.iva.cash_accounting_regime_enrolled is False
    assert profile.iva.voluntary_sii_enrolled is False
    assert profile.iva.hydrocarbon_deposit_advance_payment_deduction_entitled is False


def _choice_tokens_from_invalid_value(output: str) -> set[str]:
    undecorated = re.sub(r"[┌┐└┘─│]", " ", output)
    flat = re.sub(r"\s+", " ", undecorated)
    match = re.search(r"is not one of (?P<choices>.*?)\.", flat)
    assert match is not None, output
    return set(re.findall(r"'([^']+)'", match.group("choices")))


def test_profile_create_help_advertises_situacion_familiar_runtime_choices(
    tmp_path: Path,
) -> None:
    """The help surface must not hide accepted family-situation tokens.

    This drives the real CLI twice: one invalid invocation asks the runtime
    validator which values it accepts, then the help output must advertise those
    same tokens. The assertion is against the observed runtime contract, not a
    duplicated enum literal.
    """

    env = _isolated_env(tmp_path)
    invalid = invoke_cached_cli(
        [
            "--language",
            "en",
            "config",
            "profile",
            "create",
            "invalid-family-situation",
            "--quiet",
            "--accept-defaults",
            "--tax-id",
            "12345678Z",
            "--entity-type",
            "natural_person",
            "--name",
            "Invalid",
            "--surnames",
            "Operator",
            "--situacion-familiar",
            "1",
        ],
        env=env,
    )
    assert invalid.exit_code != 0, invalid.output
    runtime_choices = _choice_tokens_from_invalid_value(invalid.output)
    assert runtime_choices

    help_result = invoke_cached_cli(
        ["--language", "en", "config", "profile", "create", "--help"],
        env=env,
    )
    assert help_result.exit_code == 0, help_result.output
    compact_help = re.sub(r"\s+", "", help_result.output)

    assert "FUNCTION" not in help_result.output
    missing = sorted(token for token in runtime_choices if token not in compact_help)
    assert not missing, f"--situacion-familiar runtime choices are not all visible in profile-create help: {missing}"


def test_profile_create_cli_accepts_objetiva_modulos_facts_and_directa_without_them(
    tmp_path: Path,
) -> None:
    """Real profile-create CLI stores módulos facts only when the operator supplies them."""

    env = _isolated_env(tmp_path)
    direct = invoke_cached_cli(
        [
            "--language",
            "en",
            "config",
            "profile",
            "create",
            "direct-profile",
            "--quiet",
            "--accept-defaults",
            "--tax-id",
            "12345678Z",
            "--entity-type",
            "natural_person",
            "--name",
            "Direct",
            "--surnames",
            "Operator",
            "--activity",
            "direct activity",
            "--irpf-income-categories",
            "actividad_economica",
            "--irpf-estimation-regime",
            "directa_normal",
            "--tax-residence-jurisdiction-scope",
            "common_regime",
            "--iva-regime",
            "GENERAL",
            "--iva-m303-regime-composition",
            "general",
            "--no-iva-redeme-enrolled",
            "--no-iva-cash-accounting-regime-enrolled",
            "--no-iva-voluntary-sii-enrolled",
            "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
        ],
        env=env,
    )
    assert direct.exit_code == 0, direct.output

    objetiva = invoke_cached_cli(
        [
            "--language",
            "en",
            "config",
            "profile",
            "create",
            "modulos-profile",
            "--quiet",
            "--accept-defaults",
            "--tax-id",
            "87654321X",
            "--entity-type",
            "natural_person",
            "--name",
            "Modulos",
            "--surnames",
            "Operator",
            "--activity",
            "barber shop",
            "--irpf-income-categories",
            "actividad_economica",
            "--irpf-estimation-regime",
            "objetiva",
            "--objective-estimation-modulos-iae-epigraph",
            "972.1",
            "--objective-estimation-modulos-module-1-units",
            "2.50",
            "--objective-estimation-modulos-module-2-units",
            "85",
            "--objective-estimation-modulos-module-3-units",
            "12000.75",
            "--tax-residence-jurisdiction-scope",
            "common_regime",
            "--iva-regime",
            "GENERAL",
            "--iva-m303-regime-composition",
            "general",
            "--no-iva-redeme-enrolled",
            "--no-iva-cash-accounting-regime-enrolled",
            "--no-iva-voluntary-sii-enrolled",
            "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
        ],
        env=env,
    )
    assert objetiva.exit_code == 0, objetiva.output

    shown = invoke_cached_cli(
        ["--language", "en", "config", "profile", "show", "modulos-profile"],
        env=env,
    )
    assert shown.exit_code == 0, shown.output
    assert "irpf.objective_estimation_modulos_iae_epigraph" in shown.output
    assert "972.1" in shown.output
    assert "irpf.objective_estimation_modulos_module_1_units" in shown.output
    assert "2.50" in shown.output
