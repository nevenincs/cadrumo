"""Regression tests for the user-facing ``aeat`` CLI surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from aeat.application.diagnostics import build_cli_version_report
from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType
from aeat.domain.transactions import TransactionCatalogueRepository
from aeat.tests.cli_runner import invoke_cached_cli

from . import _import_failure_surface, _startup_import_error_text

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


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


def _isolate_user_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from aeat.adapters.persistence.storage.sql import dispose_engine

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


@pytest.fixture
def encrypted_user_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    monkeypatch.delenv("AEAT_SECRET_STORE_BACKEND", raising=False)
    monkeypatch.delenv("AEAT_ALLOW_UNENCRYPTED", raising=False)
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "txs"))
    monkeypatch.setenv("AEAT_INVOICES_DIR", str(tmp_path / "invoices"))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))
    with EphemeralMasterKeyProvider():
        try:
            yield tmp_path
        finally:
            dispose_engine()


def _assert_secure_database_payload(tmp_path: Path, *plaintext_canaries: str) -> None:
    db_path = tmp_path / "aeat.db"
    assert db_path.exists()
    on_disk = db_path.read_bytes()
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
) -> None:
    """Seed an active profile through workflow pointers and profile buckets.

    Registers the profile through canonical user-profile orchestration.
    Workflow state keeps the active profile pointer; profile facts are
    written through the profile lifecycle service.

    ``iva.regime`` defaults to ``GENERAL`` so the seeded profile
    matches the operator's state after a quiet profile-create run.
    """

    from aeat.application.user_profile._testing import register_minimal_profile
    from aeat.application.workflow._persistence import workflow_state_repository

    repo = workflow_state_repository()
    values = {
        "identity.tax_id": tax_id,
        "identity.name": name,
        "activities.description": activity,
        "iva.regime": iva_regime,
    }
    if extra_values:
        values.update(extra_values)
    repo.update(
        lambda state: register_minimal_profile(
            state,
            profile_id="default",
            display_name=name,
            overrides=values,
        )
    )


def test_config_init_profile_set_deadlines_and_filing_runtime_share_profile_bucket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Profile setup, config reads, deadlines, and filing runtime use one profile bucket."""

    from aeat.application.filing import load_default_filing_profile
    from aeat.application.user_profile import UserProfileLifecycleRepository
    from aeat.application.user_profile._orchestration import fact_value
    from aeat.application.workflow import workflow_state_repository

    _isolate_user_cli(monkeypatch, tmp_path)

    init_result = _invoke(
        [
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
            "--iva-regime",
            "GENERAL",
            "--tax-residence-ccaa",
            "madrid",
        ]
    )
    assert init_result.exit_code == 0, init_result.output

    from aeat.adapters.persistence.storage import activate_master_key_provider, get_master_key_provider
    from aeat.application.user_profile._orchestration import set_active_field
    from aeat.application.workflow._profile_bucket_scan import read_profile_bucket
    from aeat.domain.user_profile import UserProfileFact

    # Profile identity is an immutable UUIDv4 minted at creation; the
    # ``operator`` string is only the operator-facing display label.
    # The bucket directory, the lifecycle-repository ``bucket_id``, and
    # the ``load`` profile-id argument all key on that UUID.
    operator_pointer = read_profile_bucket("operator")
    assert operator_pointer is not None, "config profile create did not register the 'operator' bucket"
    operator_profile_id = operator_pointer.bucket_id

    provider = get_master_key_provider()
    with activate_master_key_provider(provider):
        workflow_state_repository().update(
            lambda current: set_active_field(
                current, UserProfileFact(path="preferences.output_language", value="en")
            )
        )

        refreshed = UserProfileLifecycleRepository(bucket_id=operator_profile_id).load(operator_profile_id)
        assert fact_value(refreshed, "preferences.output_language") == "en"

    status_result = _invoke(["--format", "json", "config", "profile", "status"])
    assert status_result.exit_code == 0, status_result.output
    status_payload = json.loads(_json_output(status_result))
    assert status_payload["active_profile"] == "operator"
    assert status_payload["profile_id"] == operator_profile_id
    assert status_payload["iva_regime"] == "GENERAL"

    with activate_master_key_provider(get_master_key_provider()):
        state = workflow_state_repository().load()
        assert state.active_profile_bucket_id() == operator_profile_id
        stored = UserProfileLifecycleRepository(bucket_id=operator_profile_id).load(operator_profile_id)
        assert fact_value(stored, "identity.tax_id") == "00000000T"
        assert fact_value(stored, "preferences.output_language") == "en"

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
        ]
    )
    assert calendar_result.exit_code == 0, calendar_result.output
    calendar_payload = json.loads(_json_output(calendar_result))
    assert "iva.regime" in calendar_payload["completeness"]["explicitly_set_keys"]

    with activate_master_key_provider(get_master_key_provider()):
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


def test_root_no_args_renders_help_successfully(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)
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


def test_config_repair_is_config_scoped_not_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)

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
    payload = json.loads(_json_output(json_result))
    assert payload["registry"]["available"] is True
    assert "registry.load" in {check["name"] for check in payload["checks"]}
    assert logs_result.exit_code == 0, logs_result.output
    assert "path\t" in logs_result.output


def test_startup_import_failure_points_to_config_repair_without_traceback() -> None:
    error = ModuleNotFoundError("No module named 'xlrd'", name="xlrd")

    assert _startup_import_error_text(error) == (
        "Cannot start AEAT command surface: missing dependency 'xlrd'.\nRun: aeat config repair\n"
    )
    result = _RUNNER.invoke(_import_failure_surface("app", error), [])

    assert result.exit_code == 1, result.output
    assert "missing dependency 'xlrd'" in result.output
    assert "aeat config repair" in result.output
    assert "Traceback" not in result.output


def test_version_flag_renders_backend_registry_summary() -> None:
    report = build_cli_version_report()
    assert report.registry.available

    for command in (["--version", "--detail"], ["-V", "--detail"]):
        result = _invoke(command)

        assert result.exit_code == 0, result.output
        assert f"aeat {report.package_version}" in result.output
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
    described = _invoke(["--format", "json", "app", "modelo", "describe", "303", "--period", "2026Q1"])
    casillas = _invoke(
        ["--format", "json", "app", "modelo", "casillas", "303", "--period", "2026Q1", "--input-kind", "computed"]
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
            "Q1",
        ]
    )
    formulas = _invoke(["--format", "json", "app", "modelo", "formulas", "303", "--period", "2026Q1"])

    assert listed.exit_code == 0, listed.output
    assert described.exit_code == 0, described.output
    assert casillas.exit_code == 0, casillas.output
    assert bindings.exit_code == 0, bindings.output
    assert formulas.exit_code == 0, formulas.output
    listed_payload = json.loads(_json_output(listed))
    described_payload = json.loads(_json_output(described))
    casilla_payload = json.loads(_json_output(casillas))
    binding_payload = json.loads(_json_output(bindings))
    formula_payload = json.loads(_json_output(formulas))
    assert "303" in {row["code"] for row in listed_payload["modelos"]}
    assert described_payload["code"] == "303"
    assert described_payload["period"] == "1T"
    assert casilla_payload["rows"]
    assert {row["input_kind"] for row in casilla_payload["rows"]} == {"computed"}
    assert any(
        row["binding_id"] == "irpf.previous_year_economic_activity_net_income" for row in binding_payload["bindings"]
    )
    assert {row["source"] for row in binding_payload["bindings"]} == {"previous_filing"}
    assert any(row["input_casillas"] or row["input_bindings"] for row in formula_payload["rows"])


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
        ["config", "profile", "show", "--help"],
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
    """Per the 2026-05-14 ledger-transaction-lifecycle ADR, `split` is the
    canonical N-way row splitter — a first-class top-level verb, not a
    flag nested under `update`. It requires --yes confirmation and accepts
    --reason for the bucket-event payload."""

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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)
    created = _invoke(
        [
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
        ]
    )
    assert created.exit_code == 0, created.output

    configure = _invoke(["config", "auth", "configure", "--provider", "clave_movil"])
    unsupported_spelling = _invoke(["config", "auth", "configure", "--provider", "clave-movil"])
    unsupported = _invoke(["config", "auth", "configure", "--provider", "clave_permanente"])
    unsupported_test = _invoke(["config", "auth", "test", "--provider", "dnie_pkcs"])
    unsupported_login = _invoke(["config", "auth", "login", "--provider", "dnie_pkcs"])
    unsupported_clear = _invoke(["config", "auth", "clear", "--provider", "clave_pin"])

    assert configure.exit_code == 0, configure.output
    assert "clave_movil" in configure.output
    assert unsupported_spelling.exit_code != 0
    assert "clave-movil" in unsupported_spelling.output
    assert unsupported.exit_code != 0
    assert "clave_permanente" in unsupported.output
    assert unsupported_test.exit_code != 0
    assert "dnie_pkcs" in unsupported_test.output
    assert unsupported_login.exit_code != 0
    assert "dnie_pkcs" in unsupported_login.output
    assert unsupported_clear.exit_code != 0
    assert "clave_pin" in unsupported_clear.output


def test_ledger_import_accepts_n26_csv_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)
    statement = tmp_path / "n26-q1.csv"
    statement.write_text(
        "\n".join(
            [
                "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID",
                "2026-01-05,Cliente SL,Invoice 2026-001,121.00,EUR,n26-001",
            ]
        ),
        encoding="utf-8",
    )

    imported = _invoke(
        ["--format", "json", "app", "ledger", "import", str(statement), "--provider", "n26", "--dry-run"]
    )
    overview = _invoke(["--format", "json", "app", "overview", "status"])

    assert imported.exit_code == 0, imported.output
    payload = json.loads(_json_output(imported))
    assert payload["rows"] == 1
    assert payload["dry_run"] is True
    assert payload["imported"] == 0
    assert overview.exit_code == 0, overview.output
    assert json.loads(_json_output(overview))["transactions"] == 0


def test_ledger_import_persists_transactions_as_ciphertext_envelope(encrypted_user_cli: Path) -> None:
    tmp_path = encrypted_user_cli
    _seed_profile(tax_id="00000000T", name="operator", activity="design")
    canary = "CLI_ENCRYPTED_LEDGER_CANARY_5A2F"
    transaction_ref = "n26-secure-row-001"
    statement = tmp_path / "n26-secure.csv"
    statement.write_text(
        "\n".join(
            [
                "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID",
                f"2026-01-05,{canary},Invoice 2026-SEC,121.00,EUR,{transaction_ref}",
            ]
        ),
        encoding="utf-8",
    )

    imported = _invoke(["--format", "json", "app", "ledger", "import", str(statement), "--provider", "n26"])

    assert imported.exit_code == 0, imported.output
    import_payload = json.loads(_json_output(imported))
    assert import_payload["bucket_id"] == "default"
    assert len(import_payload["bucket_event_ids"]) == 1
    assert import_payload["imported_transaction_refs"][0]["bucket_id"] == "default"
    assert not (tmp_path / "txs" / "transactions.envelope.json").exists()
    _assert_secure_database_payload(tmp_path, canary, transaction_ref)
    catalogue = TransactionCatalogueRepository(bucket_id="default").load()
    [stored] = list(catalogue.transactions.values())
    assert stored.raw.counterparty == canary
    assert stored.raw.transaction_id == transaction_ref
    events = (
        BucketEventHistoryRepository()
        .load()
        .for_bucket(
            "default",
            event_types=(BucketEventType.LEDGER_TRANSACTION_IMPORTED,),
        )
    )
    assert [event.event_type for event in events] == [BucketEventType.LEDGER_TRANSACTION_IMPORTED]
    assert events[0].event_id == import_payload["bucket_event_ids"][0]
    assert events[0].object_id == stored.transaction_id


def test_ledger_import_verify_source_records_original_file_digest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import hashlib

    _isolate_user_cli(monkeypatch, tmp_path)
    statement = tmp_path / "n26-q1.csv"
    statement.write_text(
        "\n".join(
            [
                "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID",
                "2026-01-05,Cliente SL,Invoice 2026-001,121.00,EUR,n26-001",
            ]
        ),
        encoding="utf-8",
    )
    source = tmp_path / "n26-q1.pdf"
    source_bytes = b"original downloaded bank statement"
    source.write_bytes(source_bytes)

    imported = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "import",
            str(statement),
            "--provider",
            "n26",
            "--dry-run",
            "--verify",
            "--source",
            str(source),
            "--verbose",
        ]
    )

    assert imported.exit_code == 0, imported.output
    payload = json.loads(_json_output(imported))
    assert payload["dry_run"] is True
    assert payload["validation"]["valid"] is True
    assert payload["source"]["requested"] is True
    assert payload["source"]["path"] == str(source.resolve())
    assert payload["source"]["sha256"] == hashlib.sha256(source_bytes).hexdigest()


def test_ledger_import_verify_source_rejects_missing_original_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    statement = tmp_path / "n26-q1.csv"
    statement.write_text(
        "\n".join(
            [
                "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID",
                "2026-01-05,Cliente SL,Invoice 2026-001,121.00,EUR,n26-001",
            ]
        ),
        encoding="utf-8",
    )
    missing_source = Path("missing.pdf")

    imported = _invoke(
        [
            "app",
            "ledger",
            "import",
            str(statement),
            "--provider",
            "n26",
            "--dry-run",
            "--verify",
            "--source",
            str(missing_source),
        ]
    )

    assert imported.exit_code != 0
    assert "missing.pdf" in imported.output


def test_read_only_status_commands_use_isolated_local_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)
    from aeat.adapters.persistence.storage import activate_master_key_provider, get_master_key_provider

    with activate_master_key_provider(get_master_key_provider(), fallback_bucket_id="default"):
        _seed_profile(tax_id="00000000T", name="operator", activity="design")

    config_status = _invoke(["--format", "json", "config", "profile", "status"])
    overview = _invoke(["--format", "json", "app", "overview", "status"])

    assert config_status.exit_code == 0, config_status.output
    assert overview.exit_code == 0, overview.output
    config_payload = json.loads(_json_output(config_status))
    # ``active_profile`` carries the operator-facing display label after
    # the UUID-identity cutover; ``profile_id`` carries the immutable
    # bucket identity that ``_seed_profile`` registered as ``default``.
    assert config_payload["active_profile"] == "operator"
    assert config_payload["profile_id"] == "default"
    assert config_payload["tax_id_present"] is True
    assert config_payload["activity_present"] is True
    assert json.loads(_json_output(overview))["transactions"] == 0
    assert "hashed_lookup.compute" not in config_status.output
    assert "hashed_lookup.compute" not in overview.output


def test_config_profile_show_requires_active_profile_with_typed_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``aeat config profile show`` rejects inspection when no profile is selected.

    The show verb reads the active profile bucket; with no active
    profile, the operation is refused with a typed CLI usage error.
    """

    _isolate_user_cli(monkeypatch, tmp_path)

    result = _invoke(["config", "profile", "show"])

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output


def test_config_profile_create_iva_regime_round_trips_to_deadline_engine(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Profile creation must persist ``iva.regime`` for the deadline engine."""
    from aeat.application.user_profile._projections import projection_for_autonomo
    from aeat.application.workflow import workflow_state_repository
    from aeat.domain.deadlines import IVARegime

    _isolate_user_cli(monkeypatch, tmp_path)
    created = _invoke(
        [
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
            "--iva-regime",
            "GENERAL",
        ]
    )
    assert created.exit_code == 0, created.output

    from aeat.adapters.persistence.storage import activate_master_key_provider, get_master_key_provider

    with activate_master_key_provider(get_master_key_provider()):
        state = workflow_state_repository().load()
        record = state.active_profile_record()
        assert record is not None
        profile = projection_for_autonomo(record, tax_id_default="00000000T")
    assert profile.iva_regime is IVARegime.GENERAL


def test_config_profile_create_does_intracomunitario_round_trips_to_deadline_engine(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Boolean profile flags must survive creation and reach the engine."""
    from aeat.application.user_profile._projections import projection_for_autonomo
    from aeat.application.workflow import workflow_state_repository

    _isolate_user_cli(monkeypatch, tmp_path)
    created = _invoke(
        [
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
            "--does-intracomunitario",
        ]
    )
    assert created.exit_code == 0, created.output

    show_result = _invoke(["--format", "json", "config", "profile", "show"])
    assert show_result.exit_code == 0, show_result.output
    show_payload = json.loads(_json_output(show_result))
    facts = {row["path"]: row["value"] for row in show_payload["facts"]}
    assert facts["iva.does_intracomunitario"] == "true"

    from aeat.adapters.persistence.storage import activate_master_key_provider, get_master_key_provider

    with activate_master_key_provider(get_master_key_provider()):
        state = workflow_state_repository().load()
        record = state.active_profile_record()
        assert record is not None
        profile = projection_for_autonomo(record, tax_id_default="00000000T")
    assert profile.does_intracomunitario is True


def _normalise_help_output(raw: str) -> str:
    import re

    # Strip Unicode box-drawing chars Typer/Click renders around help cells,
    # then collapse all whitespace runs into single spaces so the wrapped
    # help text reads as one continuous string.
    stripped = re.sub(r"[─-╿]", " ", raw)
    return re.sub(r"\s+", " ", stripped)
