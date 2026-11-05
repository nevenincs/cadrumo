"""Real scripted profile-password boundary matrix over the bounded secret channel."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from uuid import UUID

import pytest

from .....adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from .....adapters.persistence.storage.custody.errors import ProfileCustodyPasswordError
from .....adapters.persistence.storage.custody.kdf_supervision import unlock_profile_custody
from .....application.workflow.profile_bucket_scan import list_profile_buckets
from .....core.config import override_settings
from .....core.i18n.render import tr
from .....core.json_contract import ResolvedNoticeAction
from ...common import action_text_lines
from ...tests.cli_runner import invoke_cached_cli
from .. import scripted_registration

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke_create(tmp_path: Path, candidate: str, *, locale: str = "en"):
    with override_settings(
        cadrumo_storage_root=tmp_path / "storage",
        cadrumo_secret_passphrase=None,
    ):
        return invoke_cached_cli(
            (
                "--format",
                "json",
                "config",
                "profile",
                "create",
                "Matrix",
                "--quiet",
                "--output-language",
                locale,
                "--secrets-stdin",
            ),
            input=json.dumps({"passphrase": candidate, "passphrase_confirmation": candidate}),
        )


@pytest.mark.parametrize(
    "candidate",
    (
        pytest.param("a" * 7, id="7-scalars"),
        pytest.param("a" * 257, id="257-scalars"),
        pytest.param("😀" * 255 + "abcde", id="1025-bytes"),
        pytest.param("a" * 15 + "\ud800", id="high-surrogate"),
        pytest.param("a" * 15 + "\udc00", id="low-surrogate"),
    ),
)
def test_scripted_refusal_boundaries_are_localized_secret_safe_and_mutation_free(
    tmp_path: Path,
    candidate: str,
) -> None:
    refused = _invoke_create(tmp_path, candidate)
    combined = refused.stdout + refused.stderr
    assert refused.exit_code != 0
    assert json.loads(refused.stderr)["error"]["category"] == "REFUSED"
    assert candidate not in combined
    assert "profile_password_" not in combined
    assert "ProspectiveProfilePasswordRefusal" not in combined
    assert "profile password must contain 8 to 256 Unicode scalars" not in combined
    assert "Traceback" not in combined
    assert "INTERNAL" not in combined.upper()
    assert not list((tmp_path / "storage").glob("*/capsule.current.json"))


@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
def test_seven_scalar_refusal_is_real_in_every_language(tmp_path: Path, locale: str) -> None:
    candidate = "x" * 7
    refused = _invoke_create(tmp_path, candidate, locale=locale)
    combined = refused.stdout + refused.stderr
    error = json.loads(refused.stderr)["error"]
    context = {
        "minimum_scalars": "8",
        "reason": "too_few_scalars",
        "scalar_count": "7",
        "utf8_byte_count": "7",
    }
    translations = {
        language: tr(
            "application.user_profile.errors.profile_password_too_few_scalars",
            locale=language,
            **context,
        )
        for language in ("en", "es", "ca", "hu")
    }

    assert error == {
        "action": None,
        "category": "REFUSED",
        "code": "REFUSED_PROFILE_REGISTRATION",
        "context": context,
        "message": translations[locale],
        "retryable": False,
        "runbook_id": None,
        "trace_id": None,
    }
    assert all(message not in combined for language, message in translations.items() if language != locale)
    assert candidate not in combined
    assert "application.user_profile.errors" not in combined
    assert "ProspectiveProfilePasswordRefusal" not in combined
    assert "profile password must contain 8 to 256 Unicode scalars" not in combined
    assert "Traceback" not in combined
    assert "INTERNAL" not in combined.upper()
    assert not list((tmp_path / "storage").glob("*/capsule.current.json"))


@pytest.mark.parametrize(
    "candidate",
    (
        pytest.param("a" * 8, id="8-scalars"),
        pytest.param("a" * 256, id="256-scalars"),
        pytest.param("😀" * 256, id="1024-bytes"),
        pytest.param("é" * 15, id="composed"),
        pytest.param("e\u0301" * 15, id="decomposed"),
    ),
)
def test_scripted_accepted_boundaries_unlock_only_with_the_exact_sequence(tmp_path: Path, candidate: str) -> None:
    created = _invoke_create(tmp_path, candidate)
    assert created.exit_code == 0, created.output
    envelope = json.loads(created.stdout)
    login = next(notice for notice in envelope["notices"] if notice["code"] == "PROFILE_LOGIN_REQUIRED")
    assert login["action"]["action"]["action_id"] == "operator.profile.login"
    assert login["action"]["argument_bindings"][0]["value"] == "Matrix"
    buckets = list_profile_buckets(root=tmp_path / "storage")
    assert len(buckets) == 1
    profile_id = UUID(next(iter(buckets)))
    material = load_committed_profile_password_material(profile_id, root=tmp_path / "storage")
    assert unlock_profile_custody(password=candidate, envelope=material.envelope, sentinel=material.sentinel).dek

    counterpart = unicodedata.normalize("NFD" if unicodedata.is_normalized("NFC", candidate) else "NFC", candidate)
    if counterpart != candidate:
        with pytest.raises(ProfileCustodyPasswordError):
            unlock_profile_custody(password=counterpart, envelope=material.envelope, sentinel=material.sentinel)


@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
def test_created_profile_login_notice_has_a_resolved_safe_action(locale: str) -> None:
    label = "operator $env:USERNAME's profile"
    with override_settings(cadrumo_output_language=locale):
        notices = scripted_registration.creation_notices(recovery_enrolled=False, label=label)

    login = next(notice for notice in notices if notice.code == "PROFILE_LOGIN_REQUIRED")
    assert label in login.message
    assert "aeat config" not in login.message.casefold()
    assert isinstance(login.action, ResolvedNoticeAction)
    assert login.action.action.action_id == "operator.profile.login"
    assert login.action.action.target_command_key == "config.login"
    assert login.action.argument_bindings[0].argument_name == "name"
    assert login.action.argument_bindings[0].value == label
    assert action_text_lines(notices) == ("next_action\taeat config login 'operator $env:USERNAME''s profile'",)


@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
def test_created_profile_fallback_stays_a_valid_notice_when_action_resolution_fails(
    locale: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_action(**_kwargs: object) -> None:
        raise RuntimeError("injected action resolution failure")

    monkeypatch.setattr(scripted_registration, "resolve_notice_action", fail_action)
    with override_settings(cadrumo_output_language=locale):
        notices = scripted_registration.creation_notices(recovery_enrolled=False, label="Matrix")
    assert len(notices) == 1
    assert notices[0].code == "PROFILE_CREATED_GUIDANCE_UNAVAILABLE"
    assert notices[0].action is None
    assert "aeat config" not in notices[0].message.casefold()


def test_committed_profile_still_reports_success_if_notice_action_resolution_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_action(**_kwargs: object) -> None:
        raise RuntimeError("injected action resolution failure")

    monkeypatch.setattr(scripted_registration, "resolve_notice_action", fail_action)
    created = _invoke_create(tmp_path, "a strong test passphrase")
    assert created.exit_code == 0, created.output
    envelope = json.loads(created.stdout)
    assert envelope["result"]["profile_name"] == "Matrix"
    assert [notice["code"] for notice in envelope["notices"]] == ["PROFILE_CREATED_GUIDANCE_UNAVAILABLE"]
    assert len(list_profile_buckets(root=tmp_path / "storage")) == 1
