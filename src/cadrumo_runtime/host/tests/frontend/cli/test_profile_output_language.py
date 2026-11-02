"""CLI behavior tests for profile-owned output language.

Profiles are seeded through the credential registration door: the wizard
``create`` arm refuses unconditionally, so a profile cannot be minted from the
command line. Each test covers where the preference is stored, that ``edit``
patches instead of rewriting, that ``--language`` overrides for one invocation,
and that ``config repair`` speaks the profile's language.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH

from ._profile_cli_support import invoke_protected_profile
from ._profile_cli_support import native_profile_runtime as native_profile_runtime
from .cli_runner import invoke_cached_cli

__all__ = ["isolated_profile_storage"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str], *, env: Mapping[str, str | None] | None = None) -> Result:
    return invoke_cached_cli(args, env=env)


def _seed_profile(name: str, **facts: str) -> str:
    """Seed one profile through the credential registration door."""
    merged = {
        "taxpayer_type.entity_type": "natural_person",
        "identity.name": name,
        "identity.surnames": "Test",
        **facts,
    }
    return register_cli_profile(label=name, facts=merged, log_in=False)


def _json_output(result: Result) -> str:
    match = re.search(r"(\{.*\}|\[.*\])", result.output, re.DOTALL)
    return match.group(0) if match else result.output


def _profile_facts(profile_name: str) -> dict[str, str]:
    show_result = invoke_protected_profile(profile_name, "view", json_output=True)
    assert show_result.exit_code == 0, show_result.output
    payload = json.loads(_json_output(show_result))
    return {row["path"]: row["value"] for row in payload["result"]["facts"]}


@pytest.mark.windows_only
@pytest.mark.usefixtures("native_profile_runtime")
def test_registration_writes_profile_output_language() -> None:
    """The output-language preference declared at registration is stored and read back.

    Both surfaces are asserted, because they read through different paths:
    the ``profile view`` projection and the encrypted profile record the
    workflow state resolves.

    The registration door emits no workflow-state bucket events.
    """
    from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
    from cadrumo.application.user_profile.projections import fact_value
    from cadrumo.application.workflow.persistence import workflow_state_repository

    profile_id = _seed_profile(
        "default",
        **{
            "identity.tax_id": "00000000T",
            "activities.description": "Servicios",
            PROFILE_OUTPUT_LANGUAGE_PATH: "en",
        },
    )

    facts = _profile_facts("default")
    assert facts[PROFILE_OUTPUT_LANGUAGE_PATH] == "en"
    with open_test_profile_session(profile_id):
        record = workflow_state_repository().load().active_profile_record()
        assert record is not None
        assert fact_value(record, PROFILE_OUTPUT_LANGUAGE_PATH) == "en"


@pytest.mark.windows_only
@pytest.mark.usefixtures("native_profile_runtime")
def test_config_profile_edit_quiet_validates_profile_output_language() -> None:
    """An unknown output-language token is refused, and the stored value survives.

    The refusal is the subject; the profile is seeded through the
    registration door and then patched, because ``edit`` is the surface that
    takes an ``--output-language`` flag.
    """
    from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
    from cadrumo.application.user_profile.projections import fact_value
    from cadrumo.application.workflow.persistence import workflow_state_repository

    profile_id = _seed_profile(
        "default",
        **{"identity.tax_id": "00000000T", "activities.description": "Servicios"},
    )

    valid_result = invoke_protected_profile("default", "edit", "--quiet", "--output-language", "ca")
    assert valid_result.exit_code == 0, valid_result.output
    assert _profile_facts("default")[PROFILE_OUTPUT_LANGUAGE_PATH] == "ca"

    invalid_result = invoke_protected_profile("default", "edit", "--quiet", "--output-language", "zz")
    assert invalid_result.exit_code != 0
    assert "zz" in invalid_result.output
    assert "Traceback" not in invalid_result.output

    # The refused patch left the previously-stored value untouched.
    with open_test_profile_session(profile_id):
        reloaded = workflow_state_repository().load().active_profile_record()
        assert reloaded is not None
        assert fact_value(reloaded, PROFILE_OUTPUT_LANGUAGE_PATH) == "ca"


@pytest.mark.windows_only
@pytest.mark.usefixtures("native_profile_runtime")
def test_config_profile_edit_quiet_is_a_patch_not_a_full_rewrite() -> None:
    """`profile edit --quiet` writes only the supplied flags.

    `edit` is a true patch: a field the operator did not name on the
    command line is left exactly as stored.
    """

    from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
    from cadrumo.application.user_profile.projections import fact_value
    from cadrumo.application.workflow.persistence import workflow_state_repository

    profile_id = _seed_profile(
        "default",
        **{
            "identity.tax_id": "00000000T",
            "identity.name": "Output",
            "identity.surnames": "Language",
            "activities.description": "Servicios",
            PROFILE_OUTPUT_LANGUAGE_PATH: "en",
            "contact.postcode": "08001",
            "iva.regime": "EXENTO",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )

    # Edit ONE unrelated field; the operator supplies nothing else.
    edit_result = invoke_protected_profile("default", "edit", "--quiet", "--address-postcode", "28010")
    assert edit_result.exit_code == 0, edit_result.output

    with open_test_profile_session(profile_id):
        record = workflow_state_repository().load().active_profile_record()
        assert record is not None
        # The supplied field is patched.
        assert fact_value(record, "contact.postcode") == "28010"
        # Every other field the operator did NOT supply is unchanged.
        assert fact_value(record, PROFILE_OUTPUT_LANGUAGE_PATH) == "en"
        assert fact_value(record, "identity.tax_id") == "00000000T"
        assert fact_value(record, "activities.description") == "Servicios"
        assert fact_value(record, "iva.regime") == "EXENTO"


@pytest.mark.windows_only
@pytest.mark.usefixtures("native_profile_runtime")
def test_global_language_flag_overrides_profile_for_invocation() -> None:
    # Seed a profile with output-language "ca" through the registration door.
    _seed_profile(
        "default",
        **{
            "identity.tax_id": "00000000T",
            "activities.description": "Servicios",
            PROFILE_OUTPUT_LANGUAGE_PATH: "ca",
        },
    )

    result = _invoke(("--language", "en", "--format", "json"))

    # The --language flag's effect is scoped to the CLI invocation via
    # override_settings(...) on the Click context. Once the invocation
    # completes, the override unwinds — the test cannot observe the
    # in-process override after _invoke returns. Exit code is the
    # contract we can verify here; the in-block effect is verified
    # directly by test_render_override.py in core/i18n.
    assert result.exit_code == 0, result.output
    # The profile language survives the invocation untouched.
    facts = _profile_facts("default")
    assert facts[PROFILE_OUTPUT_LANGUAGE_PATH] == "ca"


def test_config_repair_labels_render_in_profile_output_language() -> None:
    """``config repair`` renders its labels in the active profile's language.

    The test suite pins an explicit output-language setting. This case clears
    that setting for the invocation so the active profile's ``en`` preference
    selects the diagnostic labels (Overall, Version, Checks, Next).
    """

    from cadrumo.core.config import override_settings

    # The CLI conftest pins an explicit English environment setting. Clear that
    # setting in this invocation so the profile preference is the resolver's
    # selected source rather than an explicit operator override.
    _seed_profile(
        "default",
        **{
            "identity.tax_id": "00000000T",
            "activities.description": "Servicios",
            PROFILE_OUTPUT_LANGUAGE_PATH: "en",
        },
    )

    with override_settings(cadrumo_output_language=None):
        result = _invoke(("config", "repair"))

    assert result.exit_code == 0, result.output
    # The diagnostic labels render in English.
    assert "Overall\t" in result.output
    assert "Checks" in result.output
