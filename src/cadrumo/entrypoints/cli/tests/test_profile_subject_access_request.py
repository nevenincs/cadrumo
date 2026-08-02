"""Real-CLI test for ``config profile subject-access-request`` (GDPR access).

The subject-access-request verb produces the operator's own personal-data
archive by reusing the portable-bundle serializer. This test drives the real
CLI, real encrypted repositories, and asserts the archive parses back as a
:class:`UserProfilePortableExport` and that the envelope names the personal-data
categories held. No mocks.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....domain.user_profile import UserProfilePortableExport
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_source(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _create_profile(name: str) -> Result:
    return _invoke(
        [
            "config",
            "profile",
            "create",
            name,
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--activity",
            "design",
            "--entity-type",
            "natural_person",
            "--name",
            "Subject",
            "--surnames",
            "Access",
        ],
    )


def test_subject_access_request_writes_parsable_archive(tmp_path: Path) -> None:
    """The SAR archive is written and parses back as the portable bundle."""
    assert _create_profile("subject").exit_code == 0
    out = tmp_path / "sar-data.json"

    result = _invoke(["config", "profile", "subject-access-request", "subject", "--to", str(out)])

    assert result.exit_code == 0, result.output
    assert out.is_file()
    bundle = UserProfilePortableExport.model_validate_json(out.read_text(encoding="utf-8"))
    assert bundle.profile.display_name == "subject"


def test_subject_access_request_envelope_lists_data_categories(tmp_path: Path) -> None:
    """The JSON envelope enumerates the personal-data categories held."""
    assert _create_profile("subject").exit_code == 0
    out = tmp_path / "sar-data.json"

    result = _invoke(
        ["--format", "json", "config", "profile", "subject-access-request", "subject", "--to", str(out)],
    )

    assert result.exit_code == 0, result.output
    assert "filing_records" in result.output
    assert "ledger_transactions" in result.output


def test_subject_access_request_defaults_to_active_profile(tmp_path: Path) -> None:
    """Omitting the name targets the active profile."""
    assert _create_profile("subject").exit_code == 0
    out = tmp_path / "active-data.json"

    result = _invoke(["config", "profile", "subject-access-request", "--to", str(out)])

    assert result.exit_code == 0, result.output
    assert out.is_file()


def test_the_response_states_what_the_archive_omits_alongside_what_it_holds(tmp_path: Path) -> None:
    # A right-of-access response that lists only carried categories reads as a
    # completeness claim the structured custody profile cannot support. The
    # subject must be told the omissions too, and machine-readably.
    import json

    _create_profile("subject")
    destination = tmp_path / "subject-access.json"

    result = _invoke(
        ["--format", "json", "config", "profile", "subject-access-request", "subject", "--to", str(destination)],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    payload = envelope["result"]
    assert payload["data_categories"] != []
    # Non-vacuity: the structured archive really does leave namespaces behind.
    assert payload["excluded_data_categories"] != []
    assert set(payload["excluded_data_categories"]).isdisjoint(payload["data_categories"])

    catalogue = next(
        notice
        for notice in envelope["notices"]
        if notice["code"] == "config.profile.subject_access_request.data_catalogue"
    )
    assert catalogue["context"]["excluded_data_categories"] == ",".join(payload["excluded_data_categories"])
    assert catalogue["context"]["data_categories"] == ",".join(payload["data_categories"])


def test_subject_access_request_envelope_carries_purpose_transport_and_reconcile_failures(tmp_path: Path) -> None:
    """SAR reports its custody purpose/transport and an empty reconcile list, typed."""
    import json

    assert _create_profile("subject").exit_code == 0
    out = tmp_path / "sar-custody.json"

    result = _invoke(
        ["--format", "json", "config", "profile", "subject-access-request", "subject", "--to", str(out)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["purpose"] == "subject_access"
    assert payload["transport"] == "cleartext_local"
    assert payload["reconcile_failures"] == []


def test_the_archive_omissions_match_the_bundle_the_command_wrote(tmp_path: Path) -> None:
    # The reported omissions must come from the bundle's own coverage manifest,
    # not from a list the CLI keeps, so the two cannot drift.
    import json

    _create_profile("subject")
    destination = tmp_path / "subject-access.json"

    result = _invoke(
        ["--format", "json", "config", "profile", "subject-access-request", "subject", "--to", str(destination)],
    )

    assert result.exit_code == 0, result.output
    reported = json.loads(result.output)["result"]["excluded_data_categories"]
    bundle = UserProfilePortableExport.model_validate_json(destination.read_text(encoding="utf-8"))
    assert reported == [
        f"secure_object_namespace:{namespace}" for namespace in bundle.coverage_manifest.excluded_namespaces
    ]
