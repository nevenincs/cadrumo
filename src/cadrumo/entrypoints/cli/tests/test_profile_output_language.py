"""CLI behavior tests for profile-owned output language.

Profiles are seeded through the credential registration door: the wizard
``create`` arm refuses unconditionally, so a profile can no longer be minted
from the command line. What each test is about -- where the preference is
stored, that ``edit`` patches instead of rewriting, that ``--language``
overrides for one invocation, that ``config repair`` speaks the profile's
language -- is unchanged by that, so the seed moved and the subjects stayed.

Two tests were retired rather than moved, because their subject was a code
path the retirement made unreachable rather than merely unseedable:

- create_error_renders_in_command_line_output_language: it drove the
  missing-required-flags refusal, which no live surface can reach --
  ``create`` refuses above it, and a non-interactive ``edit`` is a patch that
  never checks required flags.
- env_output_language_honored_when_creating_profile_with_accept_defaults:
  the environment seeding it asserted runs only on the full-flow path, which
  ``create`` no longer reaches and a non-interactive ``edit`` bypasses,
  writing only explicitly-supplied flags.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence

import pytest
from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage
from ....tests.user_profile import register_cli_profile

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
    return register_cli_profile(label=name, facts=merged)


def _json_output(result: Result) -> str:
    match = re.search(r"(\{.*\}|\[.*\])", result.output, re.DOTALL)
    return match.group(0) if match else result.output


def _profile_facts(profile_name: str) -> dict[str, str]:
    show_result = _invoke(("--format", "json", "config", "profile", "show", profile_name))
    assert show_result.exit_code == 0, show_result.output
    payload = json.loads(_json_output(show_result))
    return {row["path"]: row["value"] for row in payload["result"]["facts"]}


def test_registration_writes_profile_output_language() -> None:
    """The output-language preference declared at registration is stored and read back.

    Both surfaces are asserted, because they read through different paths:
    the ``profile show`` projection and the encrypted profile record the
    workflow state resolves.

    The wizard-create bucket-event assertions this test also carried
    (``profile.created`` plus a ``keys:``-scoped ``profile.values.updated``)
    were dropped rather than moved: the registration door emits no
    workflow-state bucket events at all, so there was nothing to re-point
    them at and asserting the wizard's events here would assert a path the
    product no longer runs.
    """
    from ....application.user_profile import fact_value
    from ....application.workflow import workflow_state_repository
    from ....tests.profile_capsule import open_test_profile_session

    profile_id = _seed_profile(
        "default",
        **{
            "identity.tax_id": "00000000T",
            "activities.description": "Servicios",
            "preferences.output_language": "en",
        },
    )

    facts = _profile_facts("default")
    assert facts["preferences.output_language"] == "en"
    with open_test_profile_session(profile_id):
        record = workflow_state_repository().load().active_profile_record()
        assert record is not None
        assert fact_value(record, "preferences.output_language") == "en"


def test_config_profile_edit_quiet_validates_profile_output_language() -> None:
    """An unknown output-language token is refused, and the stored value survives.

    The refusal is the subject; the profile is seeded through the
    registration door and then patched, because ``edit`` is the surviving
    surface that takes an ``--output-language`` flag.
    """
    from ....application.user_profile import fact_value
    from ....application.workflow import workflow_state_repository
    from ....tests.profile_capsule import open_test_profile_session

    profile_id = _seed_profile(
        "default",
        **{"identity.tax_id": "00000000T", "activities.description": "Servicios"},
    )

    valid_result = _invoke(("config", "profile", "edit", "default", "--quiet", "--output-language", "ca"))
    assert valid_result.exit_code == 0, valid_result.output
    assert _profile_facts("default")["preferences.output_language"] == "ca"

    invalid_result = _invoke(("config", "profile", "edit", "default", "--quiet", "--output-language", "zz"))
    assert invalid_result.exit_code != 0
    assert "zz" in invalid_result.output
    assert "Traceback" not in invalid_result.output

    # The refused patch left the previously-stored value untouched.
    with open_test_profile_session(profile_id):
        reloaded = workflow_state_repository().load().active_profile_record()
        assert reloaded is not None
        assert fact_value(reloaded, "preferences.output_language") == "ca"


def test_config_profile_edit_quiet_is_a_patch_not_a_full_rewrite() -> None:
    """`profile edit --quiet` writes only the supplied flags.

    The wizard `--quiet` path used to seed descriptor defaults for
    every unsupplied question and persist the full answer set, so
    editing one field silently reverted every other field to its
    default (`output_language` flipped en->es). `edit` must be a true
    patch: a field the operator did not name on the command line is
    left exactly as stored.
    """

    from ....application.user_profile import fact_value
    from ....application.workflow import workflow_state_repository
    from ....tests.profile_capsule import open_test_profile_session

    profile_id = _seed_profile(
        "default",
        **{
            "identity.tax_id": "00000000T",
            "identity.name": "Output",
            "identity.surnames": "Language",
            "activities.description": "Servicios",
            "preferences.output_language": "en",
            "contact.postcode": "08001",
            "iva.regime": "EXENTO",
        },
    )

    # Edit ONE unrelated field; the operator supplies nothing else.
    edit_result = _invoke(
        (
            "config",
            "profile",
            "edit",
            "default",
            "--quiet",
            "--address-postcode",
            "28010",
        ),
    )
    assert edit_result.exit_code == 0, edit_result.output

    with open_test_profile_session(profile_id):
        record = workflow_state_repository().load().active_profile_record()
        assert record is not None
        # The supplied field is patched.
        assert fact_value(record, "contact.postcode") == "28010"
        # Every other field the operator did NOT supply is unchanged —
        # the wizard must not have rewritten them to descriptor defaults.
        assert fact_value(record, "preferences.output_language") == "en"
        assert fact_value(record, "identity.tax_id") == "00000000T"
        assert fact_value(record, "activities.description") == "Servicios"
        assert fact_value(record, "iva.regime") == "EXENTO"


def test_global_language_flag_overrides_profile_for_invocation() -> None:
    # Seed a profile with output-language "ca" through the registration door.
    _seed_profile(
        "default",
        **{
            "identity.tax_id": "00000000T",
            "activities.description": "Servicios",
            "preferences.output_language": "ca",
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
    assert facts["preferences.output_language"] == "ca"


def test_config_repair_labels_render_in_profile_output_language() -> None:
    """``config repair`` renders its labels in the active profile's language.

    ``config repair`` is bootstrap-exempt, so it skipped the
    session-open path that drops the cached output language. Under an
    ``en`` profile the diagnostic labels (Overall, Version, Checks,
    Next) stayed Spanish. The verb now opens the bucket session
    opportunistically when a profile exists and re-resolves the
    language through the active-profile resolver.
    """

    # Seed a profile with output-language "en" through the registration door.
    _seed_profile(
        "default",
        **{
            "identity.tax_id": "00000000T",
            "activities.description": "Servicios",
            "preferences.output_language": "en",
        },
    )

    result = _invoke(("config", "repair"))

    assert result.exit_code == 0, result.output
    # The diagnostic labels render in English.
    assert "Overall\t" in result.output
    assert "Checks" in result.output
    # The Spanish labels must not appear.
    assert "Estado\t" not in result.output
    assert "Comprobaciones" not in result.output
