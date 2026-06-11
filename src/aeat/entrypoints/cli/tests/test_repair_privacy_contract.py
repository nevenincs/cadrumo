"""CLI privacy contracts for repair and secure-object inventory output."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage import get_master_key_provider
from ....adapters.persistence.storage.master_key._active_session import activate_session
from ....adapters.persistence.storage.master_key._bucket_session import BucketSession
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core import resolve_active_bucket_id
from ....core.classification import SensitivityClass
from ....core.config import override_settings
from ....core.logging import default_log_file_path
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_UUID_PATTERN = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


@pytest.fixture(autouse=True)
def _isolated_secure_object_database(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(
            aeat_output_language="en",
            aeat_token_dir=tmp_path / "tokens",
            aeat_runs_dir=tmp_path / "runs",
            aeat_financial_txs_dir=tmp_path / "txs",
            aeat_invoices_dir=tmp_path / "invoices",
            aeat_drafts_dir=tmp_path / "drafts",
        ),
    ):
        try:
            yield
        finally:
            dispose_engine()


def _write_row_with_wrong_bucket_key(
    *,
    key: bytes,
    namespace: str,
    object_key: str,
    payload: bytes,
) -> None:
    active_bucket_id = resolve_active_bucket_id()
    assert active_bucket_id is not None
    session = BucketSession.open(
        bucket_id=active_bucket_id,
        kek=key,
        dek=key,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )
    with activate_session(session):
        secure_object_repository_for_active_bucket().save(
            namespace=namespace,
            object_key=object_key,
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=payload,
        )


def test_config_repair_cli_redacts_active_profile_identifier() -> None:
    """The public repair command should be safe to paste into audit notes."""

    _create_operator_profile()

    text = invoke_cached_cli(["config", "repair"])
    payload_result = invoke_cached_cli(["--format", "json", "config", "repair"])

    assert text.exit_code == 0, text.output
    assert payload_result.exit_code == 0, payload_result.output
    assert not _UUID_PATTERN.search(text.output)

    payload = json.loads(payload_result.output)
    assert payload["setup"]["active_profile"] == "<profile-id>"
    summaries = "\n".join(str(row.get("summary", "")) for row in payload["checks"])
    assert not _UUID_PATTERN.search(summaries)


def test_config_repair_profile_cli_redacts_profile_identifiers() -> None:
    """Profile repair diagnostics must be paste-safe in text and JSON modes."""

    _create_operator_profile()
    active_bucket_id = resolve_active_bucket_id()
    assert active_bucket_id is not None

    commands = (
        ["config", "repair", "profile"],
        ["config", "repair", "profile", "--profile", "operator"],
        ["config", "repair", "profile", "--repair-manifest-status", "--yes"],
    )
    for command in commands:
        text = invoke_cached_cli(command)
        payload_result = invoke_cached_cli(["--format", "json", *command])

        assert text.exit_code in {0, 2}, text.output
        assert payload_result.exit_code in {0, 2}, payload_result.output
        assert active_bucket_id not in text.output
        assert active_bucket_id not in payload_result.output
        assert not _UUID_PATTERN.search(text.output)
        assert not _UUID_PATTERN.search(payload_result.output)

    named_text = invoke_cached_cli(["config", "repair", "profile", "--profile", "operator"])
    named_payload_result = invoke_cached_cli(
        ["--format", "json", "config", "repair", "profile", "--profile", "operator"],
    )
    assert named_text.exit_code == 0, named_text.output
    assert named_payload_result.exit_code == 0, named_payload_result.output
    assert "profile_id\t<profile-id>" in named_text.output
    assert "bucket_id\t<bucket-id>" in named_text.output
    named_payload = json.loads(named_payload_result.output)
    assert named_payload["result"]["profile_id"] == "<profile-id>"
    assert named_payload["result"]["bucket_id"] == "<bucket-id>"


def test_config_repair_list_operator_surface_is_retired() -> None:
    """Secure-object inventory must not be mounted on the operator repair CLI."""

    _create_operator_profile()

    result = invoke_cached_cli(["config", "repair", "list", "aeat.domain.transactions.bucket", "--all"])

    assert result.exit_code != 0
    assert "rows_total" not in result.output


def test_config_repair_integrity_objects_cli_is_metadata_only_for_unreadable_rows() -> None:
    """Integrity objects is the operator-facing inventory for degraded rows."""

    _create_operator_profile()
    active_bucket_id = resolve_active_bucket_id()
    assert active_bucket_id is not None
    namespace = "aeat.outbound.aeat.sede.iva_compensation_wallet.observations"
    sensitive_tax_id = "12345678Z"
    sensitive_period = "2026Q1"
    sensitive_payload = b"wallet-balance=999999; taxpayer=12345678Z"
    _write_row_with_wrong_bucket_key(
        key=b"\xa1" * 32,
        namespace=namespace,
        object_key=f"wallet:{sensitive_tax_id}:{sensitive_period}:{active_bucket_id}",
        payload=sensitive_payload,
    )

    text = invoke_cached_cli(["config", "repair", "integrity", "objects", "--namespace", namespace])
    payload_result = invoke_cached_cli(
        ["--format", "json", "config", "repair", "integrity", "objects", "--namespace", namespace],
    )

    assert text.exit_code == 0, text.output
    assert payload_result.exit_code == 0, payload_result.output
    assert "readable\t0" in text.output
    assert "unreadable\t1" in text.output
    assert f"{namespace}\treadable=0\tunreadable=1" in text.output
    assert "key\t" not in text.output
    assert not _UUID_PATTERN.search(text.output)
    assert sensitive_tax_id not in text.output
    assert sensitive_period not in text.output
    assert "wallet-balance" not in text.output

    envelope = json.loads(payload_result.output)
    payload = envelope["result"]
    serialized = json.dumps(payload)
    assert payload["unreadable_total"] == 1
    assert payload["readable_total"] == 0
    assert payload["namespaces"][0]["namespace"] == namespace
    assert payload["namespaces"][0]["unreadable"] == 1
    assert payload["namespaces"][0]["readable"] == 0
    assert payload["check"]["status"] == "fail"
    assert not _UUID_PATTERN.search(serialized)
    assert sensitive_tax_id not in serialized
    assert sensitive_period not in serialized
    assert "wallet-balance" not in serialized


def test_config_repair_quarantine_moves_unreadable_rows_without_disclosing_payload() -> None:
    """Non-dry-run quarantine archives unreadable rows without disclosing them."""

    _create_operator_profile()
    active_bucket_id = resolve_active_bucket_id()
    assert active_bucket_id is not None
    namespace = "aeat.outbound.aeat.sede.iva_compensation_wallet.observations"
    _write_row_with_wrong_bucket_key(
        key=b"\xb2" * 32,
        namespace=namespace,
        object_key=f"wallet:12345678Z:2026Q1:{active_bucket_id}",
        payload=b"wallet-balance=999999; taxpayer=12345678Z",
    )

    result = invoke_cached_cli(["config", "repair", "quarantine", "--yes"])
    payload_result = invoke_cached_cli(
        ["--format", "json", "config", "repair", "integrity", "objects", "--namespace", namespace],
    )

    assert result.exit_code == 0, result.output
    assert "quarantined\t1" in result.output
    assert not _UUID_PATTERN.search(result.output)
    assert "12345678Z" not in result.output
    assert "wallet-balance" not in result.output
    assert payload_result.exit_code == 0, payload_result.output
    envelope = json.loads(payload_result.output)
    payload = envelope["result"]
    assert payload["unreadable_total"] == 0
    assert payload["readable_total"] == 0
    serialized = json.dumps(payload)
    assert "12345678Z" not in serialized
    assert "wallet-balance" not in serialized


def test_config_repair_quarantine_dry_run_is_metadata_only_and_non_mutating() -> None:
    """The quarantine preview must not mutate or disclose degraded evidence."""

    _create_operator_profile()
    active_bucket_id = resolve_active_bucket_id()
    assert active_bucket_id is not None
    namespace = "aeat.outbound.aeat.sede.iva_compensation_wallet.observations"
    sensitive_tax_id = "12345678Z"
    sensitive_period = "2026Q1"
    _write_row_with_wrong_bucket_key(
        key=b"\xc3" * 32,
        namespace=namespace,
        object_key=f"wallet:{sensitive_tax_id}:{sensitive_period}:{active_bucket_id}",
        payload=b"wallet-balance=999999; taxpayer=12345678Z",
    )
    with get_master_key_provider():
        rows_before = tuple(secure_object_repository_for_active_bucket().iter_all_records_raw())

    text = invoke_cached_cli(["config", "repair", "quarantine", "--dry-run"])
    payload_result = invoke_cached_cli(["--format", "json", "config", "repair", "quarantine", "--dry-run"])
    with get_master_key_provider():
        rows_after = tuple(secure_object_repository_for_active_bucket().iter_all_records_raw())

    assert text.exit_code == 0, text.output
    assert payload_result.exit_code == 0, payload_result.output
    assert rows_after == rows_before
    assert "dry_run\ttrue" in text.output
    assert "would_quarantine\t1" in text.output
    retained_match = re.search(r"would_retain\t(?P<count>\d+)", text.output)
    assert retained_match is not None
    assert int(retained_match.group("count")) >= 1
    assert f"{namespace}\t1" in text.output
    assert not _UUID_PATTERN.search(text.output)
    assert sensitive_tax_id not in text.output
    assert sensitive_period not in text.output
    assert "wallet-balance" not in text.output

    envelope = json.loads(payload_result.output)
    payload = envelope["result"]
    serialized = json.dumps(payload)
    assert payload["dry_run"] is True
    assert payload["unreadable_total"] == 1
    assert payload["readable_total"] >= 1
    impacted = next(item for item in payload["namespaces"] if item["namespace"] == namespace)
    assert impacted["unreadable"] == 1
    assert not _UUID_PATTERN.search(serialized)
    assert sensitive_tax_id not in serialized
    assert sensitive_period not in serialized
    assert "wallet-balance" not in serialized


def test_config_repair_logs_redacts_profile_identifiers_and_object_key_hints() -> None:
    """Repair logs must be paste-safe even when a prior log line was not."""

    _create_operator_profile()
    active_bucket_id = resolve_active_bucket_id()
    assert active_bucket_id is not None
    sensitive_tax_id = "12345678Z"
    object_key = f"wallet:{sensitive_tax_id}:2026Q1:{active_bucket_id}"
    generic_object_key = f"invoice:{sensitive_tax_id}:2026Q2:{active_bucket_id}"
    log_path = default_log_file_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        (
            "diagnostic active_profile="
            f"{active_bucket_id} object_key={object_key} tax_id={sensitive_tax_id}\n"
            f"diagnostic lookup-key:{generic_object_key}\n"
        ),
        encoding="utf-8",
    )

    text = invoke_cached_cli(["config", "repair", "logs", "--lines", "2"])
    payload_result = invoke_cached_cli(["--format", "json", "config", "repair", "logs", "--lines", "2"])

    assert text.exit_code == 0, text.output
    assert payload_result.exit_code == 0, payload_result.output
    assert active_bucket_id not in text.output
    assert object_key not in text.output
    assert generic_object_key not in text.output
    assert sensitive_tax_id not in text.output
    assert "<profile-id>" in text.output
    assert "<object-key>" in text.output
    assert "sha256:1c9f9632" in text.output

    payload = json.loads(payload_result.output)
    serialized = json.dumps(payload)
    assert active_bucket_id not in serialized
    assert object_key not in serialized
    assert generic_object_key not in serialized
    assert sensitive_tax_id not in serialized


def test_config_repair_bootstrap_surfaces_do_not_require_active_profile() -> None:
    """Bootstrap-exempt repair verbs return cleanly before profile enrollment."""

    commands = (
        ["config", "repair", "quarantine", "--dry-run"],
        ["config", "repair", "integrity", "objects"],
        ["config", "repair", "logs", "--lines", "0"],
    )
    for command in commands:
        result = invoke_cached_cli(command)
        assert result.exit_code == 0, result.output
        assert "Traceback" not in result.output
        assert not _UUID_PATTERN.search(result.output)


def _create_operator_profile() -> None:
    result = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--accept-defaults",
            "--tax-id",
            "00000000T",
            "--name",
            "Operator",
            "--activity",
            "design",
            "--iva-regime",
            "GENERAL",
        ],
    )
    assert result.exit_code == 0, result.output
