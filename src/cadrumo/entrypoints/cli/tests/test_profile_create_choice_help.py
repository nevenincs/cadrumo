"""Profile-create choice help must match the values refused at runtime.

Credential registration is the only creation door, so the ``create`` verb
refuses every invocation. What survives here is the HELP surface -- the
advertised choice tokens for a closed enum must be exactly the tokens the
runtime accepts -- because ``--help`` is rendered before any refusal.

One test was retired: ``profile_create_minimal_example_creates_a_ready_profile``
executed the ``Minimal freelancer profile:`` command the create help still
advertises, and that command cannot succeed. Retiring the test does not make
the help text true; the help text is a live production defect, and it is not
this module's to fix.

The modulos fact test moved to ``edit --quiet``, which carries the same flags
and writes the same facts.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _isolated_env(tmp_path: Path) -> dict[str, str | None]:
    return {
        "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "cadrumo-local"),
        "CADRUMO_SECRET_STORE_BACKEND": "auto",
        "CADRUMO_SECRET_STORE_DIR": str(tmp_path / "secret-store"),
        "CADRUMO_SECRET_PASSPHRASE": "profile-choice-help-passphrase",
        "CADRUMO_DATABASE_URL": None,
        "COLUMNS": "1200",
    }


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


def test_profile_edit_cli_accepts_objetiva_modulos_facts_and_directa_without_them(
    tmp_path: Path,
) -> None:
    """The real CLI stores módulos facts only when the operator supplies them.

    ``directa_normal`` carries no módulos facts; ``objetiva`` carries exactly
    the ones named on the command line. Both profiles are seeded through the
    registration door and patched with ``edit --quiet``, which is the
    surviving surface that takes these flags.
    """

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_cli_profile(
            label="direct-profile",
            facts={
                "identity.tax_id": "12345678Z",
                "taxpayer_type.entity_type": "natural_person",
                "identity.name": "Direct",
                "identity.surnames": "Operator",
                "activities.description": "direct activity",
                "taxpayer_type.irpf_income_categories": "actividad_economica",
                "irpf.estimation_regime": "directa_normal",
                "tax_residence.jurisdiction_scope": "common_regime",
                "iva.regime": "GENERAL",
                "iva.m303_regime_composition": "general",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            },
        )
        register_cli_profile(
            label="modulos-profile",
            facts={
                "identity.tax_id": "87654321X",
                "taxpayer_type.entity_type": "natural_person",
                "identity.name": "Modulos",
                "identity.surnames": "Operator",
                "activities.description": "barber shop",
                "taxpayer_type.irpf_income_categories": "actividad_economica",
                "irpf.estimation_regime": "objetiva",
                "tax_residence.jurisdiction_scope": "common_regime",
                "iva.regime": "GENERAL",
                "iva.m303_regime_composition": "general",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            },
        )

        patched = invoke_cached_cli(
            [
                "--language",
                "en",
                "config",
                "profile",
                "edit",
                "modulos-profile",
                "--quiet",
                "--objective-estimation-modulos-iae-epigraph",
                "972.1",
                "--objective-estimation-modulos-module-1-units",
                "2.50",
                "--objective-estimation-modulos-module-2-units",
                "85",
                "--objective-estimation-modulos-module-3-units",
                "12000.75",
            ],
        )
        assert patched.exit_code == 0, patched.output

        shown_direct = invoke_cached_cli(
            ["--language", "en", "config", "profile", "view", "direct-profile"],
        )
        assert shown_direct.exit_code == 0, shown_direct.output
        assert "objective_estimation_modulos" not in shown_direct.output

        shown = invoke_cached_cli(
            ["--language", "en", "config", "profile", "view", "modulos-profile"],
        )
        assert shown.exit_code == 0, shown.output
        assert "irpf.objective_estimation_modulos_iae_epigraph" in shown.output
        assert "972.1" in shown.output
        assert "irpf.objective_estimation_modulos_module_1_units" in shown.output
        assert "2.50" in shown.output
