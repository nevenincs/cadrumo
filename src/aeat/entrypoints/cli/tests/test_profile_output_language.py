"""CLI behavior tests for profile-owned output language."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _json_output(result: Result) -> str:
    match = re.search(r"(\{.*\}|\[.*\])", result.output, re.DOTALL)
    return match.group(0) if match else result.output


def _isolate(tmp_path: Path) -> None:
    """Test-isolation hook (no-op today).

    Every test pins language via ``override_settings(...)`` or the
    ``--output-language`` CLI flag; both surfaces shadow ambient env
    values. Kept as a marker so future env-isolation concerns can
    re-thread the helper without churning every call site.
    """

    _ = tmp_path  # reserved for future per-test isolation hooks


def test_config_profile_create_writes_profile_output_language(
    tmp_path: Path,
) -> None:
    from ....adapters.persistence.storage import activate_master_key_provider, get_master_key_provider
    from ....application.workflow._persistence import workflow_state_repository
    from ....core import resolve_active_bucket_id
    from ....core.config import override_settings

    _isolate(tmp_path)

    init_result = _invoke(
        [
            "config",
            "profile",
            "create",
            "default",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
            "--output-language",
            "en",
        ],
    )
    show_result = _invoke(["--format", "json", "config", "profile", "show", "default"])

    assert init_result.exit_code == 0, init_result.output
    assert show_result.exit_code == 0, show_result.output
    facts = {row["path"]: row["value"] for row in json.loads(_json_output(show_result))["result"]["facts"]}
    assert facts["preferences.output_language"] == "en"
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with (
        override_settings(aeat_active_profile=bucket_id),
        activate_master_key_provider(get_master_key_provider()),
    ):
        state = workflow_state_repository().load()
        record = state.active_profile_record()
        assert record is not None
        from ....application.user_profile._orchestration import fact_value

        assert fact_value(record, "preferences.output_language") == "en"
        profile_id = record.profile_id
        assert ("profile.created", profile_id, profile_id) in [
            (event.action, event.bucket_id, event.object_id) for event in state.bucket_events
        ]
        assert any(
            event.action == "profile.values.updated"
            and event.bucket_id == profile_id
            and event.object_id is not None
            and event.object_id.startswith("keys:")
            for event in state.bucket_events
        )


def test_config_profile_create_validates_profile_output_language(
    tmp_path: Path,
) -> None:
    from ....adapters.persistence.storage import activate_master_key_provider, get_master_key_provider
    from ....application.workflow._persistence import workflow_state_repository

    _isolate(tmp_path)
    valid_result = _invoke(
        [
            "config",
            "profile",
            "create",
            "default",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
            "--output-language",
            "ca",
        ],
    )
    show_result = _invoke(["--format", "json", "config", "profile", "show", "default"])
    invalid_result = _invoke(
        [
            "config",
            "profile",
            "create",
            "invalid",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
            "--output-language",
            "zz",
        ],
    )

    assert valid_result.exit_code == 0, valid_result.output
    assert show_result.exit_code == 0, show_result.output
    facts = {row["path"]: row["value"] for row in json.loads(_json_output(show_result))["result"]["facts"]}
    assert facts["preferences.output_language"] == "ca"
    with activate_master_key_provider(get_master_key_provider()):
        state = workflow_state_repository().load()
        record = state.active_profile_record()
        assert record is not None
        from ....application.user_profile._orchestration import fact_value

        assert fact_value(record, "preferences.output_language") == "ca"
        assert invalid_result.exit_code != 0
        assert "zz" in invalid_result.output
        assert "Traceback" not in invalid_result.output
        reloaded = workflow_state_repository().load().active_profile_record()
        assert reloaded is not None
        assert fact_value(reloaded, "preferences.output_language") == "ca"


def test_config_profile_edit_quiet_is_a_patch_not_a_full_rewrite(
    tmp_path: Path,
) -> None:
    """`profile edit --quiet` writes only the supplied flags.

    The wizard `--quiet` path used to seed descriptor defaults for
    every unsupplied question and persist the full answer set, so
    editing one field silently reverted every other field to its
    default (`output_language` flipped en->es). `edit` must be a true
    patch: a field the operator did not name on the command line is
    left exactly as stored.
    """

    from ....adapters.persistence.storage import activate_master_key_provider, get_master_key_provider
    from ....application.user_profile._orchestration import fact_value
    from ....application.workflow._persistence import workflow_state_repository

    _isolate(tmp_path)

    create_result = _invoke(
        [
            "config",
            "profile",
            "create",
            "default",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
            "--output-language",
            "en",
            "--address-postcode",
            "08001",
            "--iva-regime",
            "EXENTO",
        ],
    )
    assert create_result.exit_code == 0, create_result.output

    # Edit ONE unrelated field; the operator supplies nothing else.
    edit_result = _invoke(
        [
            "config",
            "profile",
            "edit",
            "default",
            "--quiet",
            "--address-postcode",
            "28010",
        ],
    )
    assert edit_result.exit_code == 0, edit_result.output

    with activate_master_key_provider(get_master_key_provider()):
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


def test_global_language_flag_overrides_profile_for_invocation(
    tmp_path: Path,
) -> None:
    _isolate(tmp_path)

    # Seed a profile with output-language "ca" via the canonical CLI path.
    create_result = _invoke(
        [
            "config",
            "profile",
            "create",
            "default",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
            "--output-language",
            "ca",
        ],
    )
    assert create_result.exit_code == 0, create_result.output

    result = _invoke(["--language", "en", "--format", "json"])

    # The --language flag's effect is scoped to the CLI invocation via
    # override_settings(...) on the Click context. Once the invocation
    # completes, the override unwinds — the test cannot observe the
    # in-process override after _invoke returns. Exit code is the
    # contract we can verify here; the in-block effect is verified
    # directly by test_render_override.py in core/i18n.
    assert result.exit_code == 0, result.output
    # The profile language survives the invocation untouched.
    show_result = _invoke(["--format", "json", "config", "profile", "show", "default"])
    assert show_result.exit_code == 0, show_result.output
    facts = {row["path"]: row["value"] for row in json.loads(_json_output(show_result))["result"]["facts"]}
    assert facts["preferences.output_language"] == "ca"


def test_create_error_renders_in_command_line_output_language(
    tmp_path: Path,
) -> None:
    """A creation-time error renders in the ``--output-language`` given on create.

    Before fix: a refusal raised during ``profile create`` (e.g. a
    missing required flag under ``--quiet``) rendered in the default
    language even when ``--output-language en`` was supplied.
    After fix: the create flag drives the error language too — it is
    available at parse time, before the profile exists.

    ``--tax-id`` is the one unconditionally-required flag, so omitting
    it under ``--quiet`` raises the missing-required-flags refusal that
    must localise to the supplied ``--output-language``.
    """

    _isolate(tmp_path)

    english = _invoke(
        [
            "config",
            "profile",
            "create",
            "needslang",
            "--quiet",
            "--output-language",
            "en",
        ],
    )
    spanish = _invoke(
        [
            "config",
            "profile",
            "create",
            "needslang2",
            "--quiet",
            "--output-language",
            "es",
        ],
    )

    assert english.exit_code != 0, english.output
    assert spanish.exit_code != 0, spanish.output
    # The English run names the missing flag in English prose; the
    # Spanish run does not carry the English wording.
    assert "is missing required details" in english.output
    assert "is missing required details" not in spanish.output


def test_env_output_language_honored_when_creating_profile_with_accept_defaults(
    tmp_path: Path,
) -> None:
    """``AEAT_OUTPUT_LANGUAGE=en`` is written to the profile when no ``--output-language`` flag is given.

    Before the fix: ``profile create --quiet --accept-defaults`` seeded the
    catalogue default (``"es"``) for every question that the operator did
    not supply on the command line, including ``output-language``.  The
    ``AEAT_OUTPUT_LANGUAGE`` env var was completely ignored for the stored
    preference.

    After the fix: the wizard reads ``load_settings().aeat_output_language``
    (which honours the env var) and injects that value into the canonical
    dict before the catalogue-default seeding runs, so the env var wins.
    """

    from ....adapters.persistence.storage import activate_master_key_provider, get_master_key_provider
    from ....application.user_profile._orchestration import fact_value
    from ....application.workflow._persistence import workflow_state_repository

    _isolate(tmp_path)

    result = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            "marta",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "natural_person",
            "--irpf-income-categories",
            "actividad_economica",
            "--tax-id",
            "12345678Z",
        ],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )
    assert result.exit_code == 0, result.output

    show_result = _invoke(["--format", "json", "config", "profile", "show", "marta"])
    assert show_result.exit_code == 0, show_result.output

    import json as _json
    import re as _re

    m = _re.search(r"(\{.*\}|\[.*\])", show_result.output, _re.DOTALL)
    facts = {row["path"]: row["value"] for row in _json.loads(m.group(0))["result"]["facts"]} if m else {}
    assert facts.get("preferences.output_language") == "en", (
        f"Expected output_language 'en' but got {facts.get('preferences.output_language')!r}. "
        "AEAT_OUTPUT_LANGUAGE=en env var was not honoured by profile create."
    )

    # Verify via the repository as well (not just the CLI show surface).
    from ....core import resolve_active_bucket_id
    from ....core.config import override_settings

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with (
        override_settings(aeat_active_profile=bucket_id),
        activate_master_key_provider(get_master_key_provider()),
    ):
        record = workflow_state_repository().load().active_profile_record()
        assert record is not None
        assert fact_value(record, "preferences.output_language") == "en", (
            "Repository fact 'preferences.output_language' must be 'en' when "
            "AEAT_OUTPUT_LANGUAGE=en is set at profile create time."
        )


def test_config_repair_labels_render_in_profile_output_language(
    tmp_path: Path,
) -> None:
    """``config repair`` renders its labels in the active profile's language.

    ``config repair`` is bootstrap-exempt, so it skipped the
    session-open path that drops the cached output language. Under an
    ``en`` profile the diagnostic labels (Overall, Version, Checks,
    Next) stayed Spanish. The verb now opens the bucket session
    opportunistically when a profile exists and re-resolves the
    language through the active-profile resolver.
    """

    _isolate(tmp_path)

    # Seed a profile with output-language "en" via the canonical CLI path.
    create_result = _invoke(
        [
            "config",
            "profile",
            "create",
            "default",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
            "--output-language",
            "en",
        ],
    )
    assert create_result.exit_code == 0, create_result.output

    result = _invoke(["config", "repair"])

    assert result.exit_code == 0, result.output
    # The diagnostic labels render in English.
    assert "Overall\t" in result.output
    assert "Checks" in result.output
    # The Spanish labels must not appear.
    assert "Estado\t" not in result.output
    assert "Comprobaciones" not in result.output
