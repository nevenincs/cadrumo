"""End-to-end verification for the accepted apex CLI roots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import click
import pytest

from aeat.adapters.persistence.storage.sql import dispose_engine
from aeat.application.operator_surface import get_operator_surface_contract
from aeat.application.wizard._catalogue import SETUP_FLOW
from aeat.tests.cli_runner import aeat_click_command, invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    dispose_engine()
    for name in (
        "AEAT_AUTH_PROVIDER",
        "AEAT_CERTIFICATE_PATH",
        "AEAT_CERTIFICATE_PASSWORD_SECRET",
        "AEAT_CLAVE_MOVIL_DNI_NIE",
        "AEAT_CLAVE_MOVIL_DNI_FECHA",
        "AEAT_CLAVE_MOVIL_NIE_SOPORTE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path / "tokens"))
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "txs"))
    monkeypatch.setenv("AEAT_INVOICES_DIR", str(tmp_path / "invoices"))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))
    try:
        yield tmp_path
    finally:
        dispose_engine()


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _json(result) -> dict:
    return json.loads(result.output)


def _mounted_child_names(root_name: str) -> set[str]:
    """Return the subcommand names mounted under a top-level root.

    The command tree registers heavy subcommand modules lazily, so the
    Typer ``registered_groups`` list no longer carries them. The
    materialized Click group's ``list_commands`` is the canonical
    mount-point introspection surface and reports eager and lazy
    subcommands alike.
    """

    root = aeat_click_command()
    ctx = click.Context(root)
    assert isinstance(root, click.Group)
    group = root.get_command(ctx, root_name)
    assert isinstance(group, click.Group)
    return set(group.list_commands(click.Context(group)))


def test_backend_declared_command_families_are_mounted_in_cli() -> None:
    """The backend contract must not drift into a detached interface."""

    mounted = {
        "config": _mounted_child_names("config"),
        "app": _mounted_child_names("app"),
    }

    for family in get_operator_surface_contract().command_families:
        assert family.child in mounted[family.root.value]

    config_children = mounted["config"]
    app_children = mounted["app"]
    assert {"profile", "auth", "repair"}.issubset(config_children)
    assert "init" not in config_children
    assert {"overview", "ledger", "modelo", "registry", "review"}.issubset(app_children)


def test_config_profile_create_mounts_existing_setup_wizard_flow() -> None:
    """First-run configuration is the wizard flow, not a parallel interface."""

    root = aeat_click_command()
    assert isinstance(root, click.Group)
    config_group = root.get_command(click.Context(root), "config")
    assert isinstance(config_group, click.Group)
    profile_group = config_group.get_command(click.Context(config_group), "profile")
    assert isinstance(profile_group, click.Group)
    create_command = profile_group.get_command(click.Context(profile_group), "create")
    assert create_command is not None
    callback = create_command.callback
    assert callback is not None
    wrapped = getattr(callback, "__wrapped__", callback)
    assert getattr(wrapped, "__wizard_flow__", None) is SETUP_FLOW


def test_rejected_aliases_do_not_reach_apex_workflow_services() -> None:
    for command in (
        ["setup", "--help"],
        ["auth", "--help"],
        ["financial", "--help"],
        ["filing", "--help"],
        ["app", "invoice", "--help"],
        ["app", "declaration", "--help"],
        ["app", "archive", "--help"],
        ["config", "init", "--help"],
        ["config", "set", "--help"],
        ["config", "status", "--help"],
    ):
        result = _invoke(command)
        assert result.exit_code != 0, command


@dataclass(frozen=True, slots=True)
class _ApexWorkflowOutcome:
    """Bundle returned by _drive_apex_workflow_round_trip.

    Captures every payload the focused tests inspect: the
    post-init profile status, the certificate-auth configure /
    status / test results, and the imported / overview / review
    payloads emitted by the canonical operator round-trip.
    """

    status_payload: dict[str, object]
    configured_payload: dict[str, object]
    auth_status_payload: dict[str, object]
    auth_test_payload: dict[str, object]
    imported_payload: dict[str, object]
    overview_payload: dict[str, object]
    review_payload: dict[str, object]


def _drive_apex_workflow_round_trip(backend: Path) -> _ApexWorkflowOutcome:
    """Drive the canonical operator round-trip through the apex CLI.

    Five logical phases:

    1. `config profile create` — register operator profile with --accept-defaults.
    2. `config profile status` — verify the wizard persisted every
       required profile fact.
    3. `config auth configure/status/test --provider certificate` —
       register a synthetic certificate file and exercise the
       three auth-CLI verbs that read it back.
    4. `app ledger import <csv>` — ingest one synthetic bank row.
    5. `app overview status` + `app review queue` — verify the
       imported row surfaces in the operator overview and review
       queue with the expected metadata.

    Every CLI invocation is asserted to exit 0 here; downstream
    tests assert against the JSON payloads only.
    """
    profile = _invoke(
        [
            "--format", "json",
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--activity", "design",
            "--iva-regime", "GENERAL",
        ]
    )  # fmt: skip
    assert profile.exit_code == 0, profile.output
    status = _invoke(["--format", "json", "config", "profile", "status"])
    assert status.exit_code == 0, status.output

    certificate = backend / "certificate.p12"
    certificate.write_bytes(b"not-a-real-certificate")
    configured = _invoke(
        ["--format", "json", "config", "auth", "configure", "--provider", "certificate", "--file", str(certificate)]
    )
    auth_status = _invoke(["--format", "json", "config", "auth", "status", "--provider", "certificate"])
    auth_test = _invoke(["--format", "json", "config", "auth", "test", "--provider", "certificate"])
    assert configured.exit_code == 0, configured.output
    assert auth_status.exit_code == 0, auth_status.output
    assert auth_test.exit_code == 0, auth_test.output

    statement = backend / "bank.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Payment F-001,121.00,EUR,bank-001\n",
        encoding="utf-8",
    )
    imported = _invoke(["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv"])
    overview = _invoke(["--format", "json", "app", "overview", "status"])
    review = _invoke(["--format", "json", "app", "review", "queue", "--source-kind", "ledger_transaction"])
    assert imported.exit_code == 0, imported.output
    assert overview.exit_code == 0, overview.output
    assert review.exit_code == 0, review.output

    return _ApexWorkflowOutcome(
        status_payload=_json(status),
        configured_payload=_json(configured),
        auth_status_payload=_json(auth_status),
        auth_test_payload=_json(auth_test),
        imported_payload=_json(imported),
        overview_payload=_json(overview),
        review_payload=_json(review),
    )


_PROFILE_STATUS_EXPECTATIONS = (
    ("active_profile", "operator"),
    ("tax_id_present", True),
    ("activity_present", True),
    ("iva_regime", "GENERAL"),
)


@pytest.mark.parametrize(("key", "expected"), _PROFILE_STATUS_EXPECTATIONS)
def test_config_app_round_trip_profile_status_records_field(
    _isolated_cli_backend: Path, key: str, expected: object
) -> None:
    outcome = _drive_apex_workflow_round_trip(_isolated_cli_backend)
    assert outcome.status_payload[key] == expected


def test_config_app_round_trip_certificate_configure_records_provider(_isolated_cli_backend: Path) -> None:
    outcome = _drive_apex_workflow_round_trip(_isolated_cli_backend)
    assert outcome.configured_payload["provider"] == "certificate"


def test_config_app_round_trip_certificate_auth_status_reports_configured(
    _isolated_cli_backend: Path,
) -> None:
    outcome = _drive_apex_workflow_round_trip(_isolated_cli_backend)
    assert outcome.auth_status_payload["configured"] is True


def test_config_app_round_trip_certificate_auth_test_records_provider(_isolated_cli_backend: Path) -> None:
    outcome = _drive_apex_workflow_round_trip(_isolated_cli_backend)
    assert outcome.auth_test_payload["provider"] == "certificate"


def test_config_app_round_trip_ledger_import_records_one_row(_isolated_cli_backend: Path) -> None:
    outcome = _drive_apex_workflow_round_trip(_isolated_cli_backend)
    assert outcome.imported_payload["imported"] == 1


def test_config_app_round_trip_overview_reports_one_transaction(_isolated_cli_backend: Path) -> None:
    outcome = _drive_apex_workflow_round_trip(_isolated_cli_backend)
    assert outcome.overview_payload["transactions"] == 1


def test_config_app_round_trip_review_queue_lists_imported_row(_isolated_cli_backend: Path) -> None:
    outcome = _drive_apex_workflow_round_trip(_isolated_cli_backend)
    assert len(outcome.review_payload["rows"]) == 1


_REVIEW_ROW_EXPECTATIONS = (
    ("source_kind", "ledger_transaction"),
    ("period", "2026-04"),
)


@pytest.mark.parametrize(("key", "expected"), _REVIEW_ROW_EXPECTATIONS)
def test_config_app_round_trip_review_row_records_field(
    _isolated_cli_backend: Path, key: str, expected: str
) -> None:
    outcome = _drive_apex_workflow_round_trip(_isolated_cli_backend)
    assert outcome.review_payload["rows"][0][key] == expected


def test_config_app_round_trip_review_row_records_bucket_id(_isolated_cli_backend: Path) -> None:
    """The review row carries the profile bucket id, a generated UUID.

    Profile identity is the decoupled ``profile_id`` UUID, not the
    operator-facing label. The review row's ``bucket_id`` must equal
    the active profile's ``profile_id`` reported by ``profile status``.
    """

    outcome = _drive_apex_workflow_round_trip(_isolated_cli_backend)
    assert outcome.review_payload["rows"][0]["bucket_id"] == outcome.status_payload["profile_id"]


def test_config_app_round_trip_review_row_has_affected_object(_isolated_cli_backend: Path) -> None:
    outcome = _drive_apex_workflow_round_trip(_isolated_cli_backend)
    assert outcome.review_payload["rows"][0]["affected_object_id"]


def test_config_app_round_trip_review_row_canonical_next_command_is_review_verb(
    _isolated_cli_backend: Path,
) -> None:
    outcome = _drive_apex_workflow_round_trip(_isolated_cli_backend)
    canonical_next_command = outcome.review_payload["rows"][0]["canonical_next_command"]
    assert canonical_next_command.startswith("aeat app ledger review --id ")
    assert " edit " not in canonical_next_command
    assert "--set" not in canonical_next_command
