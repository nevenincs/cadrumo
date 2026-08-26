"""Regression tests for the user-facing ``cadrumo`` CLI surface."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.bucket import bucket_paths
from ....application.diagnostics import build_cli_version_report
from ....core import StorageCategory, storage_path
from ....core.config import load_settings, override_settings
from ....core.redaction import CLI_BUCKET_ID_PLACEHOLDER, CLI_PROFILE_ID_PLACEHOLDER
from ....core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ....domain.buckets import BucketEventType
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session, set_active_test_profile_facts
from ....tests.secure_sql import isolated_profile_storage_root, read_db_at_rest_bytes
from ....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _json_output(result: Result) -> str:
    import re

    # print(f"DEBUG: result.output={result.output!r}")
    match = re.search(r"(\{.*\}|\[.*\])", result.output, re.DOTALL)
    if not match:
        # print("DEBUG: no JSON match found")
        return result.output
    # print(f"DEBUG: matched={match.group(0)!r}")
    return match.group(0)


@contextmanager
def _isolated_user_cli(tmp_path: Path) -> Iterator[Path]:
    """Isolate CLI-runtime storage and neutralize ambient auth configuration.

    Storage and secrets isolation delegates to
    :func:`isolated_profile_storage_root`, the canonical helper that derives
    every leaf directory (tokens, drafts, runs, financial catalogues) from
    ``STORAGE_TAXONOMY``. A hand-spelled override block here once drifted from
    that taxonomy (a literal ``txs`` leaf where the declared subpath is
    ``financial/transactions``), and nothing caught it, because a fixture that
    only round-trips its own override agrees with any name it is given.
    Delegating removes the possibility of that drift recurring.

    The auth-provider nulling stays local: it isolates this module's tests
    from ambient dev-machine auth configuration, which is not a storage-path
    concern :func:`isolated_profile_storage_root` owns.
    """
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(
            cadrumo_auth_provider=None,
            cadrumo_certificate_path=None,
            cadrumo_certificate_password_secret=None,
            cadrumo_clave_movil_dni_nie=None,
            cadrumo_clave_movil_dni_fecha=None,
            cadrumo_clave_movil_nie_soporte=None,
            cadrumo_allow_unencrypted="",
        ),
    ):
        yield tmp_path


@pytest.fixture
def isolated_user_cli(tmp_path: Path) -> Iterator[Path]:
    with _isolated_user_cli(tmp_path) as path:
        yield path


@pytest.fixture
def encrypted_user_cli(isolated_user_cli: Path) -> Path:
    return isolated_user_cli


def _assert_secure_database_payload(bucket_id: str, *plaintext_canaries: str) -> None:
    storage_root = load_settings().cadrumo_local_storage_root
    db_path = bucket_paths(storage_root, bucket_id).database_file
    assert db_path.exists()
    on_disk = read_db_at_rest_bytes(db_path)
    assert b"secure_objects" in on_disk
    for canary in plaintext_canaries:
        assert canary.encode("utf-8") not in on_disk


def _seed_profile(
    *,
    tax_id: str = "00000000T",
    name: str = "operator",
    activity: str = "design",
    iva_regime: str = "GENERAL",
    extra_values: dict[str, str] | None = None,
) -> str:
    """Register the profile through the shared CLI registration door, and return its id.

    ``_seed_profile`` used to write a record through the application-layer
    ``register_minimal_profile`` door, which opens no custody envelope under
    the passphrase the isolated CLI backend configures -- so a CLI invocation
    made afterwards could not unlock the profile it just seeded.
    :func:`register_cli_profile` is the door built for exactly this: real CLI
    invocations follow every one of these calls.

    ``iva.regime`` defaults to ``GENERAL`` so the seeded profile matches the
    operator's state after a quiet profile-create run.
    """

    values = {
        "identity.tax_id": tax_id,
        "identity.name": name,
        "activities.description": activity,
        "iva.regime": iva_regime,
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.m303_regime_composition": "general",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    }
    if extra_values:
        values.update(extra_values)
    return register_cli_profile(label=name, facts=values)


def test_profile_create_set_deadlines_and_filing_runtime_share_profile_bucket(
    encrypted_user_cli: Path,
) -> None:
    """Profile setup, config reads, deadlines, and filing runtime use one profile bucket."""

    from ....application.filing import load_default_filing_profile
    from ....application.user_profile.projections import fact_value
    from ....application.workflow.persistence import workflow_state_repository
    from ....tests.profile_capsule import load_test_profile_record

    register_cli_profile(
        label="operator",
        facts={
            "identity.tax_id": "00000000T",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Workflow",
            "activities.description": "Servicios",
            "iva.regime": "GENERAL",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            "tax_residence.ccaa": "madrid",
        },
    )

    # Modelo applicability is derived from the taxpayer model; declare
    # an autónomo (natural person with actividad económica) so the
    # overview calendar can compute obligations rather than reporting
    # the taxpayer model incomplete.
    declare_result = _invoke(
        [
            "config",
            "profile",
            "edit",
            "operator",
            "--quiet",
            "--entity-type",
            "natural_person",
            "--irpf-income-categories",
            "actividad_economica",
        ],
    )
    assert declare_result.exit_code == 0, declare_result.output
    from ....application.workflow.profile_bucket_scan import read_profile_bucket
    from ....domain.user_profile.values import UserProfileFact

    # Profile identity is an immutable UUIDv4 minted at creation; the
    # ``operator`` string is only the operator-facing display label.
    # The bucket directory, the lifecycle-repository ``bucket_id``, and
    # the ``load`` profile-id argument all key on that UUID.
    operator_pointer = read_profile_bucket("operator")
    assert operator_pointer is not None, "config profile create did not register the 'operator' bucket"
    operator_profile_id = operator_pointer.bucket_id
    set_active_test_profile_facts((UserProfileFact(path=PROFILE_OUTPUT_LANGUAGE_PATH, value="en"),))

    with open_test_profile_session(operator_profile_id):
        refreshed = load_test_profile_record(operator_profile_id)
    assert fact_value(refreshed, PROFILE_OUTPUT_LANGUAGE_PATH) == "en"

    # `config profile status` reads the profile-bound secure store, needing an
    # active bucket session that the in-process test runner does not re-open per invoke
    # (#52 / master_key _active_session); hold the provider active across it.
    status_result = _invoke(["--format", "json", "config", "profile", "status"])
    assert status_result.exit_code == 0, status_result.output
    status_envelope = json.loads(_json_output(status_result))
    assert status_envelope["command"] == "config.profile.status"
    status_payload = status_envelope["result"]
    assert status_payload["active_profile"] == "operator"
    assert operator_profile_id not in json.dumps(status_payload, sort_keys=True)
    assert status_payload["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
    assert status_payload["iva_regime"] == "GENERAL"

    state = workflow_state_repository().load()
    assert state.active_profile_bucket_id() == operator_profile_id
    with open_test_profile_session(operator_profile_id):
        stored = load_test_profile_record(operator_profile_id)
    assert fact_value(stored, "identity.tax_id") == "00000000T"
    assert fact_value(stored, PROFILE_OUTPUT_LANGUAGE_PATH) == "en"

    # overview calendar reads the profile-bound store for obligation derivation,
    # needing an active bucket session that the in-process test runner does not re-open
    # per invoke (#52 / master_key _active_session); hold the provider active.
    calendar_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "overview",
            "calendar",
            "--from",
            "2026-01-01",
            "--to",
            "2026-03-31",
            "--allow-incomplete",
        ],
    )
    assert calendar_result.exit_code == 0, calendar_result.output
    calendar_envelope = json.loads(_json_output(calendar_result))
    assert calendar_envelope["command"] == "overview.calendar"
    calendar_payload = calendar_envelope["result"]
    assert "iva.regime" in calendar_payload["completeness"]["explicitly_set_keys"]

    filing_profile = load_default_filing_profile()
    assert filing_profile.tax_id == "00000000T"


def test_root_surface_contains_config_and_app_only() -> None:
    result = _invoke(["--help"])

    assert result.exit_code == 0, result.output
    assert "config" in result.output
    assert "app" in result.output
    for removed_command in (
        "setup",
        "auth",
        "financial",
        "filing",
        "bootstrap",
        "doctor",
        "declarations",
        "workspaces",
        "audits",
    ):
        # The substring may legitimately appear inside an option label
        # (e.g. ``--install-completion``) or another command name;
        # only the top-level Commands block
        # is checked here.
        commands_section = result.output.split("Commands", 1)[-1] if "Commands" in result.output else ""
        assert removed_command not in commands_section, removed_command


def test_root_no_args_renders_help_successfully(isolated_user_cli: Path) -> None:
    result = _invoke([])

    assert result.exit_code == 0, result.output
    assert "aeat config profile create NAME" in result.output
    assert ("aeat config " + "init") not in result.output
    assert "aeat app overview status" in result.output
    assert "aeat app ledger import" in result.output


def test_retired_commands_are_not_registered() -> None:
    removed_commands = [
        ["financial", "--help"],
        ["filing", "--help"],
        ["bootstrap", "--help"],
        ["repair", "--help"],
        ["config", "init", "--help"],
        ["config", "doctor", "--help"],
        ["config", "doctor-logs", "--help"],
        ["config", "repair-logs", "--help"],
        ["auth", "--help"],
        ["app", "declarations", "--help"],
        ["app", "workspaces", "--help"],
        ["app", "audits", "--help"],
        ["app", "ledger", "create", "--help"],
        ["app", "ledger", "edit", "--help"],
        ["app", "ledger", "read", "--help"],
        ["app", "invoice", "view", "--help"],
    ]

    for command in removed_commands:
        result = _invoke(command)
        assert result.exit_code != 0, command


def test_config_repair_is_config_scoped_not_root(isolated_user_cli: Path) -> None:
    root_repair = _invoke(["repair", "--help"])
    help_result = _invoke(["config", "repair", "--help"])
    text_result = _invoke(["config", "repair"])
    json_result = _invoke(["--format", "json", "config", "repair"])
    logs_result = _invoke(["config", "repair", "logs", "--lines", "0"])

    assert root_repair.exit_code != 0
    assert help_result.exit_code == 0, help_result.output
    assert text_result.exit_code == 0, text_result.output
    assert "Overall\t" in text_result.output
    assert "registry.load" in text_result.output
    envelope = json.loads(_json_output(json_result))
    assert envelope["command"] == "config.repair"
    payload = envelope["result"]
    assert payload["registry"]["available"] is True
    assert "registry.load" in {check["name"] for check in payload["checks"]}
    assert logs_result.exit_code == 0, logs_result.output
    assert "path\t" in logs_result.output


def test_version_flag_renders_backend_registry_summary() -> None:
    report = build_cli_version_report()
    assert report.registry.available

    for command in (["--version", "--detail"], ["-V", "--detail"]):
        result = _invoke(command)

        assert result.exit_code == 0, result.output
        assert f"cadrumo {report.package_version}" in result.output
        assert f"{report.registry.modelo_count} modelos" in result.output
        assert f"{report.registry.casilla_count} casillas" in result.output
        assert f"{report.registry.formula_count} formulas" in result.output


def test_app_surface_uses_singular_user_domains() -> None:
    result = _invoke(["app", "--help"])

    assert result.exit_code == 0, result.output
    for command in ("overview", "ledger", "live", "modelo", "registry", "review"):
        assert command in result.output
    for removed_command in (
        "aeat app invoice",
        "aeat app declaration",
        "aeat app transactions",
        "aeat app imports",
        "workspaces",
        "audits",
    ):
        assert removed_command not in result.output


def test_registry_verification_gate_is_registered_under_app_surface() -> None:
    result = _invoke(["app", "registry", "verify", "--help"])

    assert result.exit_code == 0, result.output
    assert "--registry-root" in result.output
    assert "--source-root" in result.output


def test_modelo_introspection_surface_uses_registry_query_backend() -> None:
    listed = _invoke(["--format", "json", "app", "modelo", "list", "--year", "2026"])
    described = _invoke(
        ["--format", "json", "app", "modelo", "describe", "303", "--year", "2026", "--period", "1T"],
    )
    casillas = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "casillas",
            "303",
            "--year",
            "2026",
            "--period",
            "1T",
            "--input-kind",
            "computed",
        ],
    )
    bindings = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "130",
            "--year",
            "2026",
            "--period",
            "1T",
        ],
    )
    formulas = _invoke(
        ["--format", "json", "app", "modelo", "formulas", "303", "--year", "2026", "--period", "1T"],
    )

    assert listed.exit_code == 0, listed.output
    assert described.exit_code == 0, described.output
    assert casillas.exit_code == 0, casillas.output
    assert bindings.exit_code == 0, bindings.output
    assert formulas.exit_code == 0, formulas.output
    listed_payload = json.loads(_json_output(listed))["result"]
    described_payload = json.loads(_json_output(described))["result"]
    casilla_payload = json.loads(_json_output(casillas))["result"]
    binding_payload = json.loads(_json_output(bindings))["result"]
    formula_payload = json.loads(_json_output(formulas))["result"]
    assert "303" in {row["code"] for row in listed_payload["modelos"]}
    assert described_payload["code"] == "303"
    assert described_payload["period"] == "1T"
    assert casilla_payload["rows"]
    assert {row["input_kind"] for row in casilla_payload["rows"]} == {"computed"}
    assert any(
        row["binding_id"] == "irpf.previous_year_economic_activity_net_income" for row in binding_payload["bindings"]
    )
    assert "previous_filing" in {row["source"] for row in binding_payload["bindings"]}
    assert any(row["input_casilla_ids"] or row["input_bindings"] for row in formula_payload["rows"])


def test_user_help_surfaces_do_not_leak_translation_keys() -> None:
    commands = [
        ["--help"],
        ["config", "--help"],
        ["config", "profile", "create", "--help"],
        ["config", "profile", "status", "--help"],
        ["config", "auth", "--help"],
        ["config", "auth", "providers", "--help"],
        ["config", "auth", "configure", "--help"],
        ["config", "profile", "--help"],
        ["config", "profile", "edit", "--help"],
        ["config", "profile", "view", "--help"],
        ["config", "repair", "--help"],
        ["config", "repair", "connectivity", "--help"],
        ["app", "--help"],
        ["app", "overview", "--help"],
        ["app", "overview", "status", "--help"],
        ["app", "ledger", "--help"],
        ["app", "modelo", "--help"],
        ["app", "review", "--help"],
        ["app", "review", "queue", "--help"],
        ["app", "review", "view", "--help"],
    ]

    for command in commands:
        result = _invoke(command)
        assert result.exit_code == 0, command
        assert "cli." not in result.output, command


def test_ledger_split_is_top_level_verb_with_yes_and_reason() -> None:
    """``split`` is the canonical N-way row splitter.

    It is a first-class top-level verb, not a flag nested under
    ``update``. It requires --yes confirmation and accepts --reason for
    the bucket-event payload.
    """

    ledger = _invoke(["app", "ledger", "--help"])
    split = _invoke(["app", "ledger", "split", "--help"])

    assert ledger.exit_code == 0, ledger.output
    assert split.exit_code == 0, split.output
    assert "--child-amount" in split.output
    assert "--child-description" in split.output
    assert "--yes" in split.output
    assert "--reason" in split.output


def test_review_and_ledger_share_review_wording_without_retired_invoice_surface() -> None:
    review = _invoke(["app", "review", "--help"])
    ledger = _invoke(["app", "ledger", "--help"])
    invoice = _invoke(["app", "invoice", "--help"])

    assert review.exit_code == 0, review.output
    assert ledger.exit_code == 0, ledger.output
    assert invoice.exit_code != 0
    assert "review" in review.output
    assert "review" in ledger.output


def test_review_filter_help_lists_supported_filter_keys() -> None:
    ledger = _invoke(["app", "ledger", "review", "--help"])
    review = _invoke(["app", "review", "queue", "--help"])

    assert ledger.exit_code == 0, ledger.output
    assert review.exit_code == 0, review.output
    for token in ("status", "period", "issue", "import"):
        assert token in ledger.output
    for token in ("--kind", "--source-kind", "--state", "--modelo"):
        assert token in review.output


def test_config_auth_accepts_supported_provider_and_rejects_others(
    encrypted_user_cli: Path,
) -> None:
    register_cli_profile(
        label="operator",
        facts={
            "identity.tax_id": "00000000T",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Workflow",
            "activities.description": "Servicios",
        },
    )

    configure = _invoke(["config", "auth", "configure", "--provider", "clave_movil"])
    unsupported_spelling = _invoke(["config", "auth", "configure", "--provider", "clave-movil"])
    unsupported = _invoke(["config", "auth", "configure", "--provider", "clave_pin"])
    unsupported_test = _invoke(["config", "auth", "test", "--provider", "dnie_pkcs"])
    unsupported_login = _invoke(["config", "auth", "login", "--provider", "dnie_pkcs"])
    reserved_reset = _invoke(
        ["--format", "json", "config", "auth", "reset", "--provider", "clave_pin", "--yes"],
    )

    assert configure.exit_code == 0, configure.output
    assert "clave_movil" in configure.output
    assert unsupported_spelling.exit_code != 0
    assert "clave-movil" in unsupported_spelling.output
    assert unsupported.exit_code != 0
    assert "clave_pin" in unsupported.output
    assert unsupported_test.exit_code != 0
    assert "dnie_pkcs" in unsupported_test.output
    assert unsupported_login.exit_code != 0
    assert "dnie_pkcs" in unsupported_login.output
    assert reserved_reset.exit_code == 0, reserved_reset.output
    reset_payload = json.loads(_json_output(reserved_reset))["result"]
    assert reset_payload["providers"] == ["clave_pin"]
    assert reset_payload["removed_sessions"] == 0
    assert reset_payload["cleared_provider_configuration"] is False
    assert reset_payload["cleared_locks"] == 0
    assert reset_payload["removed_certificate_sources"] == 0
    assert reset_payload["removed_certificate_secrets"] == 0


def test_ledger_import_accepts_n26_csv_dry_run(isolated_user_cli: Path) -> None:
    _seed_profile(tax_id="00000000T", name="operator", activity="design")

    statement = isolated_user_cli / "n26-q1.csv"
    statement.write_text(
        "\n".join(
            [
                "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID",
                "2026-01-05,Cliente SL,Invoice 2026-001,121.00,EUR,n26-001",
            ],
        ),
        encoding="utf-8",
    )

    imported = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "n26", "--dry-run"],
    )
    overview = _invoke(["--format", "json", "app", "overview", "status"])

    assert imported.exit_code == 0, imported.output
    envelope = json.loads(_json_output(imported))
    assert envelope["command"] == "ledger.import"
    payload = envelope["result"]
    assert payload["rows"] == 1
    assert payload["dry_run"] is True
    # The dry run previews the one row a real import would add, while
    # persisting nothing - the overview still shows zero transactions.
    assert payload["imported"] == 1
    assert overview.exit_code == 0, overview.output
    overview_envelope = json.loads(_json_output(overview))
    assert overview_envelope["command"] == "overview.status"
    assert overview_envelope["result"]["transactions"] == 0


def test_ledger_import_persists_transactions_as_ciphertext_envelope(encrypted_user_cli: Path) -> None:
    tmp_path = encrypted_user_cli
    bucket_id = _seed_profile(tax_id="00000000T", name="operator", activity="design")
    canary = "CLI_ENCRYPTED_LEDGER_CANARY_5A2F"
    transaction_ref = "n26-secure-row-001"
    statement = tmp_path / "n26-secure.csv"
    statement.write_text(
        "\n".join(
            [
                "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID",
                f"2026-01-05,{canary},Invoice 2026-SEC,121.00,EUR,{transaction_ref}",
            ],
        ),
        encoding="utf-8",
    )

    imported = _invoke(["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "n26"])

    assert imported.exit_code == 0, imported.output
    import_envelope = json.loads(_json_output(imported))
    assert import_envelope["command"] == "ledger.import"
    import_payload = import_envelope["result"]
    assert import_payload["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    assert len(import_payload["bucket_event_ids"]) == 1
    assert import_payload["imported_transaction_refs"][0]["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    assert not (storage_path(StorageCategory.FINANCIAL_TRANSACTIONS) / "transactions.envelope.json").exists()
    _assert_secure_database_payload(bucket_id, canary, transaction_ref)

    with open_test_profile_session(bucket_id):
        catalogue = TransactionCatalogueRepository(bucket_id=bucket_id).load()
        [stored] = list(catalogue.transactions.values())
        assert stored.raw.counterparty == canary
        assert stored.raw.provider_transaction_id == transaction_ref
        events = (
            BucketEventHistoryRepository()
            .load()
            .for_bucket(
                bucket_id,
                event_types=(BucketEventType.LEDGER_TRANSACTION_IMPORTED,),
            )
        )
    assert [event.event_type for event in events] == [BucketEventType.LEDGER_TRANSACTION_IMPORTED]
    assert events[0].event_id == import_payload["bucket_event_ids"][0]
    assert events[0].object_id == stored.transaction_id


def test_ledger_import_verify_source_records_original_file_digest(isolated_user_cli: Path) -> None:
    import hashlib

    _seed_profile(tax_id="00000000T", name="operator", activity="design")

    statement = isolated_user_cli / "n26-q1.csv"
    statement.write_text(
        "\n".join(
            [
                "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID",
                "2026-01-05,Cliente SL,Invoice 2026-001,121.00,EUR,n26-001",
            ],
        ),
        encoding="utf-8",
    )
    source = isolated_user_cli / "n26-q1.pdf"
    source_bytes = b"original downloaded bank statement"
    source.write_bytes(source_bytes)

    imported = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "import",
            "--file",
            str(statement),
            "--provider",
            "n26",
            "--dry-run",
            "--verify",
            "--verify-source",
            str(source),
            "--verbose",
        ],
    )

    assert imported.exit_code == 0, imported.output
    envelope = json.loads(_json_output(imported))
    assert envelope["command"] == "ledger.import"
    payload = envelope["result"]
    assert payload["dry_run"] is True
    assert payload["validation"]["valid"] is True
    assert payload["source"]["requested"] is True
    assert payload["source"]["path"] == str(source.resolve())
    assert payload["source"]["sha256"] == hashlib.sha256(source_bytes).hexdigest()


def test_ledger_import_verify_source_rejects_missing_original_file(
    isolated_user_cli: Path,
) -> None:
    """The CLI under test resolves the --source relative path against
    cwd; ``contextlib.chdir`` pins cwd to the isolated_user_cli dir for
    the duration of the call (stdlib, live-tests-friendly).
    """

    import contextlib

    _seed_profile(tax_id="00000000T", name="operator", activity="design")

    statement = isolated_user_cli / "n26-q1.csv"
    statement.write_text(
        "\n".join(
            [
                "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID",
                "2026-01-05,Cliente SL,Invoice 2026-001,121.00,EUR,n26-001",
            ],
        ),
        encoding="utf-8",
    )
    missing_source = Path("missing.pdf")

    with contextlib.chdir(isolated_user_cli):
        imported = _invoke(
            [
                "app",
                "ledger",
                "import",
                "--file",
                str(statement),
                "--provider",
                "n26",
                "--dry-run",
                "--verify",
                "--verify-source",
                str(missing_source),
            ],
        )

    assert imported.exit_code != 0
    assert "missing.pdf" in imported.output


def test_read_only_status_commands_use_isolated_local_state(encrypted_user_cli: Path) -> None:
    _seed_profile(tax_id="00000000T", name="operator", activity="design")

    config_status = _invoke(["--format", "json", "config", "profile", "status"])
    overview = _invoke(["--format", "json", "app", "overview", "status"])

    assert config_status.exit_code == 0, config_status.output
    assert overview.exit_code == 0, overview.output
    config_envelope = json.loads(_json_output(config_status))
    assert config_envelope["command"] == "config.profile.status"
    config_payload = config_envelope["result"]
    # ``active_profile`` carries the operator-facing display label after
    # the UUID-identity cutover; ``profile_id`` carries the immutable
    # bucket identity that ``_seed_profile`` registered as ``default``.
    assert config_payload["active_profile"] == "operator"
    assert config_payload["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
    assert config_payload["tax_id_present"] is True
    assert config_payload["activity_present"] is True
    overview_envelope = json.loads(_json_output(overview))
    assert overview_envelope["command"] == "overview.status"
    assert overview_envelope["result"]["transactions"] == 0
    assert "hashed_lookup.compute" not in config_status.output
    assert "hashed_lookup.compute" not in overview.output


def test_config_profile_view_requires_active_profile_with_typed_error(
    isolated_user_cli: Path,
) -> None:
    """``aeat config profile view`` rejects inspection when no profile is selected.

    The show verb reads the active profile bucket; with no active
    profile, the operation is refused with a typed CLI usage error.
    """

    result = _invoke(["config", "profile", "view"])

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output


def test_config_profile_create_iva_regime_round_trips_to_deadline_engine(
    encrypted_user_cli: Path,
) -> None:
    """Profile creation normalizes lowercase ``iva.regime`` for the deadline engine."""
    from ....application.user_profile.projections import projection_for_taxpayer
    from ....application.workflow.persistence import workflow_state_repository
    from ....domain.deadlines import IVARegime

    bucket_id = register_cli_profile(
        label="operator",
        facts={
            "identity.tax_id": "00000000T",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Workflow",
            "activities.description": "Servicios",
            "iva.regime": "GENERAL",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )

    with open_test_profile_session(bucket_id):
        state = workflow_state_repository().load()
        record = state.active_profile_record()
        assert record is not None
        profile = projection_for_taxpayer(record, tax_id_default="00000000T")
    assert profile.iva_regime is IVARegime.GENERAL


def test_config_profile_create_persists_situacion_familiar(
    encrypted_user_cli: Path,
) -> None:
    """The exposed Art. 82 situacion-familiar flag must persist to a schema-backed fact."""
    from ....application.user_profile.projections import record_to_path_values
    from ....application.workflow.persistence import workflow_state_repository

    bucket_id = register_cli_profile(
        label="operator",
        facts={
            "identity.tax_id": "00000000T",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Workflow",
            "activities.description": "Servicios",
            "renta_family.situacion_familiar": "soltero",
        },
    )

    with open_test_profile_session(bucket_id):
        state = workflow_state_repository().load()
        record = state.active_profile_record()
        assert record is not None
        values = record_to_path_values(record)
    assert values["renta_family.situacion_familiar"] == "soltero"


def test_config_profile_create_does_intracomunitario_round_trips_to_deadline_engine(
    encrypted_user_cli: Path,
) -> None:
    """Boolean profile flags must survive creation and reach the engine."""
    from ....application.user_profile.projections import projection_for_taxpayer
    from ....application.workflow.persistence import workflow_state_repository

    bucket_id = register_cli_profile(
        label="operator",
        facts={
            "identity.tax_id": "00000000T",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Workflow",
            "activities.description": "Servicios",
            "iva.does_intracomunitario": "true",
        },
    )

    show_result = _invoke(["--format", "json", "config", "profile", "view"])
    assert show_result.exit_code == 0, show_result.output
    show_envelope = json.loads(_json_output(show_result))
    assert show_envelope["command"] == "config.profile.show"
    show_payload = show_envelope["result"]
    facts = {row["path"]: row["value"] for row in show_payload["facts"]}
    assert facts["iva.does_intracomunitario"] == "true"

    with open_test_profile_session(bucket_id):
        state = workflow_state_repository().load()
        record = state.active_profile_record()
        assert record is not None
        profile = projection_for_taxpayer(record, tax_id_default="00000000T")
    assert profile.does_intracomunitario is True


def _normalise_help_output(raw: str) -> str:
    import re

    # Strip Unicode box-drawing chars Typer/Click renders around help cells,
    # then collapse all whitespace runs into single spaces so the wrapped
    # help text reads as one continuous string.
    stripped = re.sub(r"[─-╿]", " ", raw)
    return re.sub(r"\s+", " ", stripped)
