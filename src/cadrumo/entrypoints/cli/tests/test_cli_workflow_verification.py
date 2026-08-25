"""End-to-end verification for the accepted CLI roots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
import typer
from typer.core import TyperGroup

from ....application.operator_surface import get_operator_surface_contract
from ....core.config import override_settings
from ....core.redaction import CLI_BUCKET_ID_PLACEHOLDER, CLI_PROFILE_ID_PLACEHOLDER
from ....tests.cli_envelope import unwrap_cli_result as _json
from ....tests.cli_runner import cadrumo_click_command, invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _assert_is_command_group(value: object) -> None:
    """isinstance check that recognises typer's vendored Click hierarchy.

    ``cadrumo_click_command()`` and ``get_command`` return ``typer.core.TyperGroup``
    instances whose MRO is ``TyperGroup -> typer._click.core.Command -> ABC``
    and never descends from the upstream ``click.Group``, so a bare
    ``isinstance(value, click.Group)`` is False. Derive the vendored
    ``Command`` base from the value's MRO and assert against it (mirrors the
    production fix in ``cli/errors.py`` and the test-side fix in
    ``test_backend_boundary.py``).
    """
    vendored_command = next(
        (base for base in type(value).__mro__ if base.__name__ == "Command"),
        None,
    )
    assert vendored_command is not None, f"{type(value).__name__} has no Command in MRO"
    assert isinstance(value, vendored_command)


def _as_group(command: object) -> TyperGroup:
    """Narrow a resolved command to the vendored ``TyperGroup``.

    The Cadrumo tree is the vendored Typer hierarchy
    (``CadrumoTyperGroup -> typer.core.TyperGroup``), which does not descend from
    upstream ``click.Group``; ``TyperGroup`` is the correct narrow target and
    carries the typed ``get_command`` / ``list_commands`` surface.
    """
    assert isinstance(command, TyperGroup)
    return command


@pytest.fixture(autouse=True)
def _certificate_bearing_cli_backend(tmp_path: Path):
    # The round-trip helper writes its synthetic certificate to
    # ``<tmp_path>/certificate.p12``. The certificate auth backend
    # probes the path from ``Settings.cadrumo_certificate_path``, so the
    # override must name the same file the operator configures —
    # otherwise ``configured`` (operational readiness) and the backend
    # health summary would describe two different paths. The other
    # auth-related fields are pinned to ``None`` so the test always
    # starts from a clean slate regardless of ambient operator env.
    with (
        override_settings(
            cadrumo_auth_provider=None,
            cadrumo_certificate_path=tmp_path / "certificate.p12",
            cadrumo_certificate_password_secret=None,
            cadrumo_clave_movil_dni_nie=None,
            cadrumo_clave_movil_dni_fecha=None,
            cadrumo_clave_movil_nie_soporte=None,
        ),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        yield tmp_path


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _mounted_child_names(root_name: str) -> set[str]:
    """Return the subcommand names mounted under a top-level root.

    The command tree registers heavy subcommand modules lazily, so the
    Typer ``registered_groups`` list no longer carries them. The
    materialized Click group's ``list_commands`` is the canonical
    mount-point introspection surface and reports eager and lazy
    subcommands alike.
    """

    root_group = _as_group(cadrumo_click_command())
    group = _as_group(root_group.get_command(typer.Context(root_group), root_name))
    return set(group.list_commands(typer.Context(group)))


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

    root_group = _as_group(cadrumo_click_command())
    config_group = _as_group(root_group.get_command(typer.Context(root_group), "config"))
    profile_group = _as_group(config_group.get_command(typer.Context(config_group), "profile"))
    create_command = profile_group.get_command(typer.Context(profile_group), "create")
    assert create_command is not None
    callback = create_command.callback
    assert callback is not None
    wrapped = getattr(callback, "__wrapped__", callback)

    from ....core.wizard_catalogue import get_setup_flow

    assert getattr(wrapped, "__wizard_flow__", None) is get_setup_flow()


def test_rejected_aliases_do_not_reach_workflow_services() -> None:
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
class _WorkflowRoundTripOutcome:
    """Bundle returned by _drive_workflow_round_trip.

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


def _review_rows(outcome: _WorkflowRoundTripOutcome) -> list[Mapping[str, object]]:
    """Return the typed review-queue rows from the JSON ``review_payload``."""
    rows = outcome.review_payload["rows"]
    assert isinstance(rows, list)
    typed_rows: list[Mapping[str, object]] = []
    for row in rows:
        assert isinstance(row, Mapping)
        # Review-queue rows decode from JSON as string-keyed objects.
        typed_rows.append({str(key): value for key, value in row.items()})
    return typed_rows


def _drive_workflow_round_trip(backend: Path) -> _WorkflowRoundTripOutcome:
    """Drive the canonical operator round-trip through the CLI.

    Five logical stages:

    1. `config profile create` — register operator profile with the required
       filing identity flags and --accept-defaults.
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
    register_cli_profile(
        label="operator",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Workflow",
            "activities.description": "design",
            "iva.regime": "GENERAL",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )
    status = _invoke(["--format", "json", "config", "profile", "status"])
    assert status.exit_code == 0, status.output

    certificate = backend / "certificate.p12"
    certificate.write_bytes(b"not-a-real-certificate")
    configured = _invoke(
        ["--format", "json", "config", "auth", "configure", "--provider", "certificate", "--file", str(certificate)],
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
    imported = _invoke(["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "csv"])
    overview = _invoke(["--format", "json", "app", "overview", "status"])
    review = _invoke(["--format", "json", "app", "review", "queue", "--source-kind", "ledger_transaction"])
    assert imported.exit_code == 0, imported.output
    assert overview.exit_code == 0, overview.output
    assert review.exit_code == 0, review.output

    return _WorkflowRoundTripOutcome(
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
    _certificate_bearing_cli_backend: Path,
    key: str,
    expected: object,
) -> None:
    outcome = _drive_workflow_round_trip(_certificate_bearing_cli_backend)
    assert outcome.status_payload[key] == expected


def test_config_app_round_trip_certificate_configure_records_provider(_certificate_bearing_cli_backend: Path) -> None:
    outcome = _drive_workflow_round_trip(_certificate_bearing_cli_backend)
    assert outcome.configured_payload["provider"] == "certificate"


def test_config_app_round_trip_certificate_auth_status_reports_configured(
    _certificate_bearing_cli_backend: Path,
) -> None:
    outcome = _drive_workflow_round_trip(_certificate_bearing_cli_backend)
    assert outcome.auth_status_payload["configured"] is True


def test_config_app_round_trip_certificate_auth_test_records_provider(_certificate_bearing_cli_backend: Path) -> None:
    outcome = _drive_workflow_round_trip(_certificate_bearing_cli_backend)
    assert outcome.auth_test_payload["provider"] == "certificate"


def test_config_app_round_trip_ledger_import_records_one_row(_certificate_bearing_cli_backend: Path) -> None:
    outcome = _drive_workflow_round_trip(_certificate_bearing_cli_backend)
    assert outcome.imported_payload["imported"] == 1


def test_config_app_round_trip_overview_reports_one_transaction(_certificate_bearing_cli_backend: Path) -> None:
    outcome = _drive_workflow_round_trip(_certificate_bearing_cli_backend)
    assert outcome.overview_payload["transactions"] == 1


def test_config_app_round_trip_review_queue_lists_imported_row(_certificate_bearing_cli_backend: Path) -> None:
    outcome = _drive_workflow_round_trip(_certificate_bearing_cli_backend)
    assert len(_review_rows(outcome)) == 1


_REVIEW_ROW_EXPECTATIONS = (
    ("source_kind", "ledger_transaction"),
    ("period", "2026-04"),
)


@pytest.mark.parametrize(("key", "expected"), _REVIEW_ROW_EXPECTATIONS)
def test_config_app_round_trip_review_row_records_field(
    _certificate_bearing_cli_backend: Path, key: str, expected: str
) -> None:
    outcome = _drive_workflow_round_trip(_certificate_bearing_cli_backend)
    assert _review_rows(outcome)[0][key] == expected


def test_config_app_round_trip_review_row_records_bucket_id(_certificate_bearing_cli_backend: Path) -> None:
    """The review row carries a redacted profile bucket id.

    Profile identity is the decoupled ``profile_id`` UUID, not the
    operator-facing label. Public JSON output must expose the label as
    ``active_profile`` while redacting the machine identifiers.
    """

    outcome = _drive_workflow_round_trip(_certificate_bearing_cli_backend)
    assert outcome.status_payload["active_profile"] == "operator"
    assert _review_rows(outcome)[0]["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    assert outcome.status_payload["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER


def test_config_app_round_trip_review_row_has_affected_object(_certificate_bearing_cli_backend: Path) -> None:
    outcome = _drive_workflow_round_trip(_certificate_bearing_cli_backend)
    assert _review_rows(outcome)[0]["affected_object_id"]


def test_config_app_round_trip_review_row_canonical_next_command_is_review_verb(
    _certificate_bearing_cli_backend: Path,
) -> None:
    outcome = _drive_workflow_round_trip(_certificate_bearing_cli_backend)
    canonical_next_command = _review_rows(outcome)[0]["canonical_next_command"]
    assert isinstance(canonical_next_command, str)
    assert canonical_next_command.startswith("aeat app ledger review ")
    assert " edit " not in canonical_next_command
    assert "--set" not in canonical_next_command


def test_config_app_round_trip_review_row_carries_legal_refs_field(
    _certificate_bearing_cli_backend: Path,
) -> None:
    """Every JSON review row exposes a ``legal_refs`` field.

    The how-to guide promises the JSON output always carries ``legal_refs``;
    a ledger-transaction row grounds its obligation in the operator's own
    records, so the field is present and empty rather than absent.
    """
    outcome = _drive_workflow_round_trip(_certificate_bearing_cli_backend)
    row = _review_rows(outcome)[0]
    assert "legal_refs" in row
    assert row["legal_refs"] == []


def test_config_app_round_trip_review_queue_text_omits_bucket_placeholder(
    _certificate_bearing_cli_backend: Path,
) -> None:
    """The text queue table does not render the redacted bucket placeholder.

    The profile-wide queue always scopes to the active bucket, so a per-row
    Bucket column adds no operator value and only ever printed the paste-safe
    ``<profile-id>`` placeholder (the m17 leak). The column is removed; the
    JSON ``bucket_id`` (redacted) remains for tooling.
    """
    _drive_workflow_round_trip(_certificate_bearing_cli_backend)

    text_queue = _invoke(["app", "review", "queue"])
    assert text_queue.exit_code == 0, text_queue.output
    assert CLI_PROFILE_ID_PLACEHOLDER not in text_queue.output
    assert CLI_BUCKET_ID_PLACEHOLDER not in text_queue.output
    # The row itself still surfaces (the column removal must not drop data).
    assert "ledger_transaction" in text_queue.output
