"""Real scripted profile-password boundary matrix over the bounded secret channel."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from uuid import UUID

import pytest

from .....adapters.persistence.storage.custody import (
    ProfileCustodyPasswordError,
    load_committed_profile_password_material,
    unlock_profile_custody,
)
from .....application.workflow import list_profile_buckets
from .....core.config import override_settings
from .....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke_create(tmp_path: Path, candidate: str, *, locale: str = "en"):
    with override_settings(
        cadrumo_local_storage_root=tmp_path / "storage",
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
        pytest.param("a" * 14, id="14-scalars"),
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
    assert "profile password must contain 15 to 256 Unicode scalars" not in combined
    assert "Traceback" not in combined
    assert "INTERNAL" not in combined.upper()
    assert not list((tmp_path / "storage").glob("*/capsule.current.json"))


@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
def test_original_fourteen_scalar_refusal_is_real_in_every_language(tmp_path: Path, locale: str) -> None:
    candidate = "x" * 14
    refused = _invoke_create(tmp_path, candidate, locale=locale)
    message = json.loads(refused.stderr)["error"]["message"]
    assert message and candidate not in message
    assert "application.user_profile.errors" not in message
    assert "profile password must contain 15 to 256 Unicode scalars" not in message


@pytest.mark.parametrize(
    "candidate",
    (
        pytest.param("a" * 15, id="15-scalars"),
        pytest.param("a" * 256, id="256-scalars"),
        pytest.param("😀" * 256, id="1024-bytes"),
        pytest.param("é" * 15, id="composed"),
        pytest.param("e\u0301" * 15, id="decomposed"),
    ),
)
def test_scripted_accepted_boundaries_unlock_only_with_the_exact_sequence(tmp_path: Path, candidate: str) -> None:
    created = _invoke_create(tmp_path, candidate)
    assert created.exit_code == 0, created.output
    buckets = list_profile_buckets(root=tmp_path / "storage")
    assert len(buckets) == 1
    profile_id = UUID(next(iter(buckets)))
    material = load_committed_profile_password_material(profile_id, root=tmp_path / "storage")
    assert unlock_profile_custody(password=candidate, envelope=material.envelope, sentinel=material.sentinel).dek

    counterpart = unicodedata.normalize("NFD" if unicodedata.is_normalized("NFC", candidate) else "NFC", candidate)
    if counterpart != candidate:
        with pytest.raises(ProfileCustodyPasswordError):
            unlock_profile_custody(password=counterpart, envelope=material.envelope, sentinel=material.sentinel)
