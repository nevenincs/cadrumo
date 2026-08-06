"""CLI behavior tests for profile-owned output language."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
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


def _invoke(args: Sequence[str], *, env: Mapping[str, str | None] | None = None) -> Result:
    return invoke_cached_cli(args, env=env)


def _create_profile(name: str, *options: str, env: Mapping[str, str | None] | None = None) -> Result:
    return _invoke(
        (
            "config",
            "profile",
            "create",
            name,
            "--quiet",
            *_filing_identity_defaults(name, options),
            *options,
        ),
        env=env,
    )


def _filing_identity_defaults(name: str, options: tuple[str, ...]) -> tuple[str, ...]:
    option_set = set(options)
    defaults: list[str] = []
    if "--entity-type" not in option_set:
        defaults.extend(["--entity-type", "natural_person"])
    entity_type = _option_value(options, "--entity-type") or "natural_person"
    if entity_type == "legal_entity":
        if "--legal-name" not in option_set:
            defaults.extend(["--legal-name", f"{name} SL"])
        return tuple(defaults)
    if "--name" not in option_set:
        defaults.extend(["--name", name])
    if entity_type == "natural_person" and "--surnames" not in option_set:
        defaults.extend(["--surnames", "Test"])
    return tuple(defaults)


def _option_value(options: tuple[str, ...], flag: str) -> str | None:
    try:
        index = options.index(flag)
    except ValueError:
        return None
    value_index = index + 1
    if value_index >= len(options):
        return None
    value = options[value_index]
    return None if value.startswith("--") else value


def _json_output(result: Result) -> str:
    match = re.search(r"(\{.*\}|\[.*\])", result.output, re.DOTALL)
    return match.group(0) if match else result.output


def _profile_facts(profile_name: str) -> dict[str, str]:
    show_result = _invoke(("--format", "json", "config", "profile", "show", profile_name))
    assert show_result.exit_code == 0, show_result.output
    payload = json.loads(_json_output(show_result))
    return {row["path"]: row["value"] for row in payload["result"]["facts"]}


def test_config_profile_create_writes_profile_output_language() -> None:
    from ....adapters.persistence.storage.master_key import (
        activate_master_key_provider,
        get_master_key_provider,
    )
    from ....application.workflow import workflow_state_repository
    from ....core import resolve_active_bucket_id
    from ....core.config import override_settings

    init_result = _create_profile(
        "default",
        "--tax-id",
        "00000000T",
        "--activity",
        "Servicios",
        "--output-language",
        "en",
    )

    assert init_result.exit_code == 0, init_result.output
    facts = _profile_facts("default")
    assert facts["preferences.output_language"] == "en"
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with (
        override_settings(cadrumo_active_profile=bucket_id),
        activate_master_key_provider(get_master_key_provider()),
    ):
        state = workflow_state_repository().load()
        record = state.active_profile_record()
        assert record is not None
        from ....application.user_profile import fact_value

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


def test_config_profile_create_validates_profile_output_language() -> None:
    from ....adapters.persistence.storage.master_key import (
        activate_master_key_provider,
        get_master_key_provider,
    )
    from ....application.workflow import workflow_state_repository

    valid_result = _create_profile(
        "default",
        "--tax-id",
        "00000000T",
        "--activity",
        "Servicios",
        "--output-language",
        "ca",
    )
    invalid_result = _create_profile(
        "invalid",
        "--tax-id",
        "00000000T",
        "--activity",
        "Servicios",
        "--output-language",
        "zz",
    )

    assert valid_result.exit_code == 0, valid_result.output
    facts = _profile_facts("default")
    assert facts["preferences.output_language"] == "ca"
    with activate_master_key_provider(get_master_key_provider()):
        state = workflow_state_repository().load()
        record = state.active_profile_record()
        assert record is not None
        from ....application.user_profile import fact_value

        assert fact_value(record, "preferences.output_language") == "ca"
        assert invalid_result.exit_code != 0
        assert "zz" in invalid_result.output
        assert "Traceback" not in invalid_result.output
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

    from ....adapters.persistence.storage.master_key import (
        activate_master_key_provider,
        get_master_key_provider,
    )
    from ....application.user_profile import fact_value
    from ....application.workflow import workflow_state_repository

    create_result = _create_profile(
        "default",
        "--entity-type",
        "natural_person",
        "--tax-id",
        "00000000T",
        "--name",
        "Output",
        "--surnames",
        "Language",
        "--activity",
        "Servicios",
        "--output-language",
        "en",
        "--address-postcode",
        "08001",
        "--iva-regime",
        "EXENTO",
    )
    assert create_result.exit_code == 0, create_result.output

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


def test_global_language_flag_overrides_profile_for_invocation() -> None:
    # Seed a profile with output-language "ca" via the canonical CLI path.
    create_result = _create_profile(
        "default",
        "--tax-id",
        "00000000T",
        "--activity",
        "Servicios",
        "--output-language",
        "ca",
    )
    assert create_result.exit_code == 0, create_result.output

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


def test_create_error_renders_in_command_line_output_language() -> None:
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

    english = _create_profile(
        "needslang",
        "--output-language",
        "en",
    )
    spanish = _create_profile(
        "needslang2",
        "--output-language",
        "es",
    )

    assert english.exit_code != 0, english.output
    assert spanish.exit_code != 0, spanish.output
    # The English run names the missing flag in English prose; the
    # Spanish run does not carry the English wording.
    assert "is missing required details" in english.output
    assert "is missing required details" not in spanish.output


def test_env_output_language_honored_when_creating_profile_with_accept_defaults() -> None:
    """``CADRUMO_OUTPUT_LANGUAGE=en`` is written to the profile when no ``--output-language`` flag is given.

    Before the fix: ``profile create --quiet --accept-defaults`` seeded the
    catalogue default (``"es"``) for every question that the operator did
    not supply on the command line, including ``output-language``.  The
    ``CADRUMO_OUTPUT_LANGUAGE`` env var was completely ignored for the stored
    preference.

    After the fix: the wizard reads ``load_settings().cadrumo_output_language``
    (which honours the env var) and injects that value into the canonical
    dict before the catalogue-default seeding runs, so the env var wins.
    """

    from ....adapters.persistence.storage.master_key import (
        activate_master_key_provider,
        get_master_key_provider,
    )
    from ....application.user_profile import fact_value
    from ....application.workflow import workflow_state_repository

    result = _create_profile(
        "autonoma",
        "--accept-defaults",
        "--entity-type",
        "natural_person",
        "--irpf-income-categories",
        "actividad_economica",
        "--tax-id",
        "12345678Z",
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )
    assert result.exit_code == 0, result.output

    facts = _profile_facts("autonoma")
    assert facts.get("preferences.output_language") == "en", (
        f"Expected output_language 'en' but got {facts.get('preferences.output_language')!r}. "
        "CADRUMO_OUTPUT_LANGUAGE=en env var was not honoured by profile create."
    )

    # Verify via the repository as well (not just the CLI show surface).
    from ....core import resolve_active_bucket_id
    from ....core.config import override_settings

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with (
        override_settings(cadrumo_active_profile=bucket_id),
        activate_master_key_provider(get_master_key_provider()),
    ):
        record = workflow_state_repository().load().active_profile_record()
        assert record is not None
        assert fact_value(record, "preferences.output_language") == "en", (
            "Repository fact 'preferences.output_language' must be 'en' when "
            "CADRUMO_OUTPUT_LANGUAGE=en is set at profile create time."
        )


def test_config_repair_labels_render_in_profile_output_language() -> None:
    """``config repair`` renders its labels in the active profile's language.

    ``config repair`` is bootstrap-exempt, so it skipped the
    session-open path that drops the cached output language. Under an
    ``en`` profile the diagnostic labels (Overall, Version, Checks,
    Next) stayed Spanish. The verb now opens the bucket session
    opportunistically when a profile exists and re-resolves the
    language through the active-profile resolver.
    """

    # Seed a profile with output-language "en" via the canonical CLI path.
    create_result = _create_profile(
        "default",
        "--tax-id",
        "00000000T",
        "--activity",
        "Servicios",
        "--output-language",
        "en",
    )
    assert create_result.exit_code == 0, create_result.output

    result = _invoke(("config", "repair"))

    assert result.exit_code == 0, result.output
    # The diagnostic labels render in English.
    assert "Overall\t" in result.output
    assert "Checks" in result.output
    # The Spanish labels must not appear.
    assert "Estado\t" not in result.output
    assert "Comprobaciones" not in result.output


def test_malformed_bucket_dek_error_renders_in_profile_output_language() -> None:
    """A critical master-key failure still renders through the profile language hint."""

    from ....adapters.persistence.storage.bucket import read_bucket_output_language_hint
    from ....adapters.persistence.storage.master_key import bucket_dek_path, current_active_bucket_session
    from ....application.workflow import read_profile_bucket
    from ....core.config import load_settings, override_settings
    from ....core.i18n import clear_output_language_cache, tr

    create_result = _create_profile(
        "catala",
        "--tax-id",
        "00000000T",
        "--activity",
        "Serveis",
        "--output-language",
        "ca",
    )
    assert create_result.exit_code == 0, create_result.output
    pointer = read_profile_bucket("catala")
    assert pointer is not None
    assert (
        read_bucket_output_language_hint(
            storage_root=load_settings().cadrumo_local_storage_root,
            bucket_id=pointer.bucket_id,
        )
        == "ca"
    )

    assert current_active_bucket_session() is None
    target = bucket_dek_path(storage_root=load_settings().cadrumo_local_storage_root, bucket_id=pointer.bucket_id)
    target.write_text("not-json\n", encoding="utf-8")

    with override_settings(cadrumo_output_language=None):
        clear_output_language_cache()
        result = _invoke(("config", "profile", "show"))
        clear_output_language_cache()

    assert result.exit_code != 0, result.output
    assert tr("errors.auth.auth_storage_master_key_unavailable", locale="ca") in result.output
    assert tr("errors.auth.auth_storage_master_key_unavailable", locale="en") not in result.output
    assert "Traceback" not in result.output


def test_config_switch_malformed_target_bucket_dek_uses_target_profile_output_language() -> None:
    """A failed target-bucket switch renders through the target bucket's language hint."""

    from ....adapters.persistence.storage.bucket import read_bucket_output_language_hint
    from ....adapters.persistence.storage.master_key import bucket_dek_path
    from ....application.workflow import read_profile_bucket
    from ....core import resolve_active_bucket_id
    from ....core.config import load_settings, override_settings
    from ....core.i18n import clear_output_language_cache, tr

    alpha = _create_profile(
        "alpha",
        "--tax-id",
        "00000000T",
        "--activity",
        "Services",
        "--output-language",
        "en",
    )
    assert alpha.exit_code == 0, alpha.output
    beta = _create_profile(
        "beta",
        "--tax-id",
        "00000001R",
        "--activity",
        "Serveis",
        "--output-language",
        "ca",
    )
    assert beta.exit_code == 0, beta.output

    alpha_pointer = read_profile_bucket("alpha")
    beta_pointer = read_profile_bucket("beta")
    assert alpha_pointer is not None
    assert beta_pointer is not None

    switched_alpha = _invoke(("config", "login", "alpha"))
    assert switched_alpha.exit_code == 0, switched_alpha.output
    assert resolve_active_bucket_id() == alpha_pointer.bucket_id
    assert (
        read_bucket_output_language_hint(
            storage_root=load_settings().cadrumo_local_storage_root,
            bucket_id=alpha_pointer.bucket_id,
        )
        == "en"
    )
    assert (
        read_bucket_output_language_hint(
            storage_root=load_settings().cadrumo_local_storage_root,
            bucket_id=beta_pointer.bucket_id,
        )
        == "ca"
    )

    target = bucket_dek_path(storage_root=load_settings().cadrumo_local_storage_root, bucket_id=beta_pointer.bucket_id)
    target.write_text("not-json\n", encoding="utf-8")

    with override_settings(cadrumo_output_language=None):
        clear_output_language_cache()
        result = _invoke(("config", "login", "beta"))
        clear_output_language_cache()

    assert result.exit_code != 0, result.output
    assert resolve_active_bucket_id() == alpha_pointer.bucket_id
    assert tr("errors.auth.auth_storage_master_key_unavailable", locale="ca") in result.output
    assert tr("errors.auth.auth_storage_master_key_unavailable", locale="en") not in result.output
    assert "Traceback" not in result.output
