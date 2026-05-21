"""CLI behavior tests for profile-owned output language."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from click.testing import Result

from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _json_output(result: Result) -> str:
    match = re.search(r"(\{.*\}|\[.*\])", result.output, re.DOTALL)
    return match.group(0) if match else result.output


def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from aeat.adapters.persistence.storage.sql import dispose_engine

    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'profile-language.db').as_posix()}")
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.delenv("AEAT_OUTPUT_LANGUAGE", raising=False)
    dispose_engine()


def _seed_profile() -> None:
    from aeat.application.user_profile._testing import register_minimal_profile
    from aeat.application.workflow._persistence import workflow_state_repository

    repository = workflow_state_repository()
    repository.update(
        lambda state: register_minimal_profile(
            state,
            profile_id="default",
            overrides={"identity.tax_id": "00000000T", "activities.description": "Servicios"},
        )
    )


def test_config_profile_create_writes_profile_output_language(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from aeat.adapters.persistence.storage import get_master_key_provider
    from aeat.application.workflow._persistence import workflow_state_repository

    _isolate(monkeypatch, tmp_path)

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
        ]
    )
    show_result = _invoke(["--format", "json", "config", "profile", "show", "default"])

    assert init_result.exit_code == 0, init_result.output
    assert show_result.exit_code == 0, show_result.output
    facts = {row["path"]: row["value"] for row in json.loads(_json_output(show_result))["facts"]}
    assert facts["preferences.output_language"] == "en"
    with get_master_key_provider():
        state = workflow_state_repository().load()
        record = state.active_profile_record()
        assert record is not None
        from aeat.application.user_profile._orchestration import fact_value

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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from aeat.adapters.persistence.storage import get_master_key_provider
    from aeat.application.workflow._persistence import workflow_state_repository

    _isolate(monkeypatch, tmp_path)
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
        ]
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
        ]
    )

    assert valid_result.exit_code == 0, valid_result.output
    assert show_result.exit_code == 0, show_result.output
    facts = {row["path"]: row["value"] for row in json.loads(_json_output(show_result))["facts"]}
    assert facts["preferences.output_language"] == "ca"
    with get_master_key_provider():
        state = workflow_state_repository().load()
        record = state.active_profile_record()
        assert record is not None
        from aeat.application.user_profile._orchestration import fact_value

        assert fact_value(record, "preferences.output_language") == "ca"
        assert invalid_result.exit_code != 0
        assert "zz" in invalid_result.output
        assert "Traceback" not in invalid_result.output
        reloaded = workflow_state_repository().load().active_profile_record()
        assert reloaded is not None
        assert fact_value(reloaded, "preferences.output_language") == "ca"


def test_config_profile_edit_quiet_is_a_patch_not_a_full_rewrite(
    monkeypatch: pytest.MonkeyPatch,
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

    from aeat.adapters.persistence.storage import get_master_key_provider
    from aeat.application.user_profile._orchestration import fact_value
    from aeat.application.workflow._persistence import workflow_state_repository

    _isolate(monkeypatch, tmp_path)

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
        ]
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
        ]
    )
    assert edit_result.exit_code == 0, edit_result.output

    with get_master_key_provider():
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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from aeat.adapters.persistence.storage import get_master_key_provider
    from aeat.application.user_profile._orchestration import set_active_field
    from aeat.application.workflow._persistence import workflow_state_repository
    from aeat.domain.user_profile import UserProfileFact

    _isolate(monkeypatch, tmp_path)
    with get_master_key_provider():
        _seed_profile()
        workflow_state_repository().update(
            lambda state: set_active_field(state, UserProfileFact(path="preferences.output_language", value="ca"))
        )

    result = _invoke(["--language", "en", "--format", "json"])

    # The --language flag's effect is scoped to the CLI invocation via
    # override_settings(...) on the Click context. Once the invocation
    # completes, the override unwinds — the test cannot observe the
    # in-process override after _invoke returns. Exit code is the
    # contract we can verify here; the in-block effect is verified
    # directly by test_render_override.py in core/i18n.
    assert result.exit_code == 0, result.output
    # The profile language survives the invocation untouched.
    with get_master_key_provider():
        state = workflow_state_repository().load()
        record = state.active_profile_record()
        assert record is not None
        from aeat.application.user_profile._orchestration import fact_value

        assert fact_value(record, "preferences.output_language") == "ca"


def test_create_error_renders_in_command_line_output_language(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A creation-time error renders in the ``--output-language`` given on create.

    Before fix: a refusal raised during ``profile create`` (e.g. a
    missing ``--activity`` under ``--quiet``) rendered in the default
    language even when ``--output-language en`` was supplied.
    After fix: the create flag drives the error language too — it is
    available at parse time, before the profile exists.
    """

    _isolate(monkeypatch, tmp_path)

    english = _invoke(
        [
            "config",
            "profile",
            "create",
            "needslang",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--output-language",
            "en",
        ]
    )
    spanish = _invoke(
        [
            "config",
            "profile",
            "create",
            "needslang2",
            "--quiet",
            "--tax-id",
            "00000001R",
            "--output-language",
            "es",
        ]
    )

    assert english.exit_code != 0, english.output
    assert spanish.exit_code != 0, spanish.output
    # The English run names the missing flag in English prose; the
    # Spanish run does not carry the English wording.
    assert "Required flags are missing" in english.output
    assert "Required flags are missing" not in spanish.output


def test_config_repair_labels_render_in_profile_output_language(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``config repair`` renders its labels in the active profile's language.

    ``config repair`` is bootstrap-exempt, so it skipped the
    session-open path that drops the cached output language. Under an
    ``en`` profile the diagnostic labels (Overall, Version, Checks,
    Next) stayed Spanish. The verb now opens the bucket session
    opportunistically when a profile exists and re-resolves the
    language through the active-profile resolver.
    """

    from aeat.adapters.persistence.storage import get_master_key_provider
    from aeat.application.user_profile._orchestration import set_active_field
    from aeat.application.workflow._persistence import workflow_state_repository
    from aeat.domain.user_profile import UserProfileFact

    _isolate(monkeypatch, tmp_path)
    with get_master_key_provider():
        _seed_profile()
        workflow_state_repository().update(
            lambda state: set_active_field(
                state, UserProfileFact(path="preferences.output_language", value="en")
            )
        )

    result = _invoke(["config", "repair"])

    assert result.exit_code == 0, result.output
    # The diagnostic labels render in English.
    assert "Overall\t" in result.output
    assert "Checks" in result.output
    # The Spanish labels must not appear.
    assert "Estado\t" not in result.output
    assert "Comprobaciones" not in result.output
