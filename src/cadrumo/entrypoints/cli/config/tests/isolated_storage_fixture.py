"""Canonical isolated profile-storage fixtures for CLI config tests."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import Result
from pydantic import TypeAdapter

from .....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from .....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from .....core.config import override_settings
from ...tests.cli_runner import invoke_cached_cli

#: The passphrase every profile these fixtures create is protected by.
CREDENTIAL_INPUT = "a-sufficiently-long-operator-passphrase"
_JSON_OBJECT: TypeAdapter[dict[str, object]] = TypeAdapter(dict[str, object])

#: Every flag a natural person with activity income needs before
#: ``complete-setup`` accepts the record.
COMPLETE_NATURAL_PERSON_FLAGS = (
    "--entity-type",
    "natural_person",
    "--tax-id",
    "12345678Z",
    "--name",
    "Ana",
    "--surnames",
    "Gil Ruiz",
    "--fiscal-residency",
    "resident_irpf",
    "--tax-residence-jurisdiction-scope",
    "common_regime",
    "--tax-residence-ccaa",
    "madrid",
    "--irpf-income-categories",
    "actividad_economica",
    "--activity",
    "Consultoria",
    "--iva-regime",
    "GENERAL",
    "--iva-m303-regime-composition",
    "general",
    "--no-iva-redeme-enrolled",
    "--no-iva-cash-accounting-regime-enrolled",
    "--no-iva-voluntary-sii-enrolled",
    "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
)


@pytest.fixture
def config_check_backend(tmp_path: Path) -> Iterator[None]:
    """Isolated storage/locale backend for the ``config check`` suites."""

    with (
        override_settings(cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        yield


@pytest.fixture(name="_isolated_backend", autouse=True)
def config_check_isolated_backend(config_check_backend: None) -> None:
    """Autouse variant of :func:`config_check_backend` for the ``config check`` suites."""

    return config_check_backend


@pytest.fixture
def live_cli_profile(tmp_path: Path) -> Iterator[None]:
    """Create one incomplete profile through the real ``create`` verb.

    ``create`` leaves the new profile's session live in this process, so every
    later command in the test authenticates exactly as the operator's own
    session would, and reads records under the same pinned authority the CLI
    uses. Registering through a test-only authority instead binds the record to
    a different generation, which the CLI then refuses to read.
    """
    overrides = {
        "cadrumo_local_storage_root": tmp_path / "cadrumo-storage",
        "cadrumo_secret_passphrase": CREDENTIAL_INPUT,
    }
    with override_settings(**overrides):
        created = invoke_cached_cli(
            ("--format", "json", "config", "profile", "create", "Editor", "--quiet", "--secrets-stdin"),
            input=json.dumps({"passphrase": CREDENTIAL_INPUT, "passphrase_confirmation": CREDENTIAL_INPUT}),
        )
        assert created.exit_code == 0, created.output
        try:
            yield
        finally:
            close_active_bucket_session()


def profile_cli(*args: str) -> Result:
    """Run one ``config profile`` verb in JSON mode against the live profile."""
    return invoke_cached_cli(("--format", "json", "config", "profile", *args))


def profile_view_document() -> dict[str, object]:
    """Return the parsed ``config profile view`` envelope, whatever its exit code."""
    return _JSON_OBJECT.validate_python(json.loads(profile_cli("view").stdout))


def profile_facts() -> dict[str, str]:
    """Return the live profile's facts as a path -> value mapping."""
    result = profile_view_document()["result"]
    assert isinstance(result, dict)
    return {str(fact["path"]): str(fact["value"]) for fact in result["facts"]}


def profile_event_count(event_type: str) -> int:
    """Count the live profile's history events of one type."""
    listed = profile_cli("history")
    assert listed.exit_code == 0, listed.output
    events = json.loads(listed.stdout)["result"]["events"]
    return sum(1 for event in events if event["event_type"] == event_type)


__all__ = [
    "COMPLETE_NATURAL_PERSON_FLAGS",
    "CREDENTIAL_INPUT",
    "config_check_backend",
    "config_check_isolated_backend",
    "live_cli_profile",
    "profile_cli",
    "profile_event_count",
    "profile_facts",
    "profile_view_document",
]
