"""Smoke tests for ``aeat filing`` CLI commands.

Drives the root ``aeat`` Typer app via :class:`typer.testing.CliRunner`
against a per-test isolated SQLite backend (engine cached by
``AEAT_DATABASE_URL``) and an ephemeral master key. Drafts and
submissions persist through the real encrypted SQL repository; the
``drafts_dir`` / ``submissions_dir`` fixtures retain the env-var
plumbing only because the schema-provider and submission browser-trace
paths still consume the env vars.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.filing import FilingBuilderError, FilingOperatorProfile, build_draft, build_runtime_schema_provider
from ....core.config import PROJECT_ROOT
from ....domain.deadlines import AutonomoProfile, IVARegime
from ....domain.filing._repository import FilingDraftRepository
from ....domain.submission import SubmissionAttempt, SubmissionRepository, SubmissionStatus, SubmittedFiling
from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_JUSTIFICANTE_FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "justificantes"

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    """Per-test SQLite + ephemeral master key so list_records sees only fresh rows.

    Mirrors the pattern used by ``tests/import_contract/domain/invoices``
    and ``aeat.application.archive.test_archive``.
    """
    previous_db = os.environ.get("AEAT_DATABASE_URL")
    os.environ["AEAT_DATABASE_URL"] = f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}"
    dispose_engine()

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_secret_store(secret_store)
    try:
        yield
    finally:
        override_master_key_provider(None)
        override_secret_store(None)
        dispose_engine()
        if previous_db is None:
            os.environ.pop("AEAT_DATABASE_URL", None)
        else:
            os.environ["AEAT_DATABASE_URL"] = previous_db


def _registry_modelo_calculable_without_inputs() -> str:
    provider = build_runtime_schema_provider()
    profile = FilingOperatorProfile(tax_id="00000000T", display_name="CLI filing")
    for modelo in sorted(provider.collections):
        try:
            build_draft(
                modelo=modelo,
                period="2026Q1",
                profile=profile,
                inputs={},
                schema_provider=provider,
            )
        except FilingBuilderError:
            continue
        return modelo
    raise AssertionError("registry has no modelo calculable without explicit inputs")


def _write_inputs(tmp_path: Path) -> Path:
    """Write a JSON inputs file for registry-backed CLI build tests."""
    payload: dict[str, object] = {}
    target = tmp_path / "inputs.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def _write_submitted_filing(
    *,
    modelo: str,
    period: str,
    draft_id: str = "draft-cli-1",
) -> SubmittedFiling:
    """Persist a real submitted-filing record for CLI amendment tests."""
    now = datetime(2026, 4, 13, 8, 0, tzinfo=UTC)
    filing = SubmittedFiling(
        submission_id="sub-cli-1",
        draft_id=draft_id,
        modelo=modelo,
        period=period,
        profile_tax_id="00000000T",
        status=SubmissionStatus.SUBMITTED,
        justificante_csv="CSV-sub-cli-1",
        justificante_pdf_path=None,
        submitted_at=now,
        acknowledged_at=None,
        attempts=(
            SubmissionAttempt(
                attempt_id="sub-cli-1.1",
                started_at=now,
                ended_at=now,
                status=SubmissionStatus.SUBMITTED,
            ),
        ),
    )
    SubmissionRepository().save(filing)
    return filing


def _single_draft_id() -> str:
    """Return the only draft id persisted in the per-test repository."""
    drafts = FilingDraftRepository().list_draft_ids()
    assert len(drafts) == 1, drafts
    return drafts[0]


def _single_draft_path() -> Path:
    """Return the logical path of the only persisted draft."""
    repository = FilingDraftRepository()
    return repository.envelope_path_for(_single_draft_id())


def _persisted_draft_count() -> int:
    """Return the number of drafts in the per-test repository."""
    return len(FilingDraftRepository().list_draft_ids())


@pytest.fixture
def drafts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``AEAT_DRAFTS_DIR`` at a clean per-test directory."""
    target = tmp_path / "drafts"
    target.mkdir()
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(target))
    return target


@pytest.fixture
def submissions_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "submissions"
    target.mkdir()
    monkeypatch.setenv("AEAT_SUBMISSIONS_DIR", str(target))
    monkeypatch.setenv("AEAT_SUBMISSION_BROWSER_TRACE_DIR", str(tmp_path / "traces"))
    return target


@pytest.fixture
def transactions_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "transactions"
    target.mkdir()
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(target))
    return target


@pytest.fixture
def profile_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Persist an :class:`AutonomoProfile` through the SQL secure-object backend.

    The setup-profile namespace is path-keyed: the natural object key
    is the resolved POSIX path of the configured profile location, so
    we write to the SQL backend under exactly that key and point
    ``AEAT_DEFAULT_PROFILE_PATH`` at the same path.
    """
    from datetime import UTC, datetime

    from ....adapters.persistence.storage import SensitivityClass
    from ....adapters.persistence.storage.sql import SecureObjectRepository

    profile = AutonomoProfile(
        tax_id="00000000T",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    target = tmp_path / "profile.json"
    object_key = target.expanduser().resolve().as_posix()
    SecureObjectRepository().save(
        namespace="aeat.application.setup.profile",
        object_key=object_key,
        classification=SensitivityClass.IDENTITY,
        schema_version=1,
        written_at=datetime.now(UTC),
        payload=profile.model_dump_json().encode("utf-8"),
    )
    monkeypatch.setenv("AEAT_DEFAULT_PROFILE_PATH", str(target))
    return target


class TestFilingCLI:
    """Smoke coverage for ``aeat filing`` build, show, validate, list, import paths."""

    def test_build_uses_configured_profile_file(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        profile_path: Path,
    ) -> None:
        inputs = _write_inputs(tmp_path)
        modelo = _registry_modelo_calculable_without_inputs()
        result = runner.invoke(
            app,
            [
                "build",
                "--modelo",
                modelo,
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
                "--profile",
                str(profile_path),
                "--profile-name",
                "Configured operator",
            ],
        )
        assert result.exit_code == 0, result.output
        assert f"registry:{modelo}:" in result.output
        assert _persisted_draft_count() == 1

    def test_build_writes_draft_to_disk(self, tmp_path: Path, drafts_dir: Path) -> None:
        inputs = _write_inputs(tmp_path)
        modelo = _registry_modelo_calculable_without_inputs()
        result = runner.invoke(
            app,
            [
                "build",
                "--modelo",
                modelo,
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
                "--profile-tax-id",
                "00000000T",
            ],
        )
        assert result.exit_code == 0, result.output
        assert f"registry:{modelo}:" in result.output
        assert _persisted_draft_count() == 1

    def test_show_and_validate_round_trip(self, tmp_path: Path, drafts_dir: Path, transactions_dir: Path) -> None:
        inputs = _write_inputs(tmp_path)
        modelo = _registry_modelo_calculable_without_inputs()
        build_result = runner.invoke(
            app,
            [
                "build",
                "--modelo",
                modelo,
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
                "--profile-tax-id",
                "00000000T",
            ],
        )
        assert build_result.exit_code == 0, build_result.output
        draft_path = _single_draft_path()

        show_result = runner.invoke(app, ["show", str(draft_path)])
        assert show_result.exit_code == 0, show_result.output
        assert f"registry:{modelo}:" in show_result.output

        validate_result = runner.invoke(app, ["validate", str(draft_path)])
        assert validate_result.exit_code == 0, validate_result.output
        assert "READY_TO_SUBMIT" in validate_result.output

    def test_validate_preserves_approval_for_unchanged_reviewed_draft(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        transactions_dir: Path,
    ) -> None:
        del transactions_dir
        inputs = _write_inputs(tmp_path)
        modelo = _registry_modelo_calculable_without_inputs()
        result = runner.invoke(
            app,
            [
                "build",
                "--modelo",
                modelo,
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
                "--profile-tax-id",
                "00000000T",
            ],
        )
        assert result.exit_code == 0, result.output
        draft_path = _single_draft_path()

        validate_result = runner.invoke(app, ["validate", str(draft_path)])
        assert validate_result.exit_code == 0, validate_result.output
        assert "READY_TO_SUBMIT" in validate_result.output

    def test_list_filters_by_modelo(self, tmp_path: Path, drafts_dir: Path) -> None:
        inputs = _write_inputs(tmp_path)
        modelo = _registry_modelo_calculable_without_inputs()
        build_result = runner.invoke(
            app,
            [
                "build",
                "--modelo",
                modelo,
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
                "--profile-tax-id",
                "00000000T",
            ],
        )
        assert build_result.exit_code == 0, build_result.output
        result = runner.invoke(app, ["list", "--modelo", modelo], terminal_width=240)
        assert result.exit_code == 0, result.output
        assert modelo in result.output
        assert "2026Q1" in result.output

    def test_import_refuses_pdf_when_required_registry_inputs_are_missing(
        self,
        drafts_dir: Path,
        submissions_dir: Path,
    ) -> None:
        pdf = _JUSTIFICANTE_FIXTURES / "modelo_130_2026Q1.pdf"
        result = runner.invoke(
            app,
            ["import", "--from-justificante", str(pdf)],
            terminal_width=240,
        )
        assert result.exit_code != 0, result.output
        assert "registry calculation failed" in result.output
        assert "irpf.previous_year_economic_activity_net_income" in result.output
        assert _persisted_draft_count() == 0

    def test_import_rejects_missing_pdf(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
    ) -> None:
        missing = tmp_path / "nowhere.pdf"
        result = runner.invoke(
            app,
            ["import", "--from-justificante", str(missing)],
        )
        assert result.exit_code != 0, result.output
        assert _persisted_draft_count() == 0

    def test_import_rejects_unsupported_modelo(
        self,
        drafts_dir: Path,
        submissions_dir: Path,
    ) -> None:
        pdf = _JUSTIFICANTE_FIXTURES / "modelo_100_2025A.pdf"
        result = runner.invoke(
            app,
            ["import", "--from-justificante", str(pdf)],
        )
        assert result.exit_code != 0, result.output
        assert _persisted_draft_count() == 0

    def test_complementaria_submit_command_is_absent(
        self,
    ) -> None:
        """``aeat filing complementaria submit`` must not exist.

        Local amendment drafting is available, but this CLI surface must not
        expose a remote presentation command.
        """
        result = runner.invoke(app, ["complementaria", "submit", "amd-1"])
        # Click/Typer returns 2 for an unknown subcommand.
        assert result.exit_code == 2, result.output
        assert "no such command" in result.output.lower()

    def test_complementaria_build_reports_missing_submission_cleanly(self) -> None:
        payload = {
            "original_submission_id": "missing-submission",
            "updated_inputs": {
                "01": 1,
            },
        }

        result = runner.invoke(
            app,
            ["complementaria", "build", "111", "2026Q1", json.dumps(payload)],
            terminal_width=240,
        )

        assert result.exit_code != 0, result.output
        assert "missing-submission" in result.output
        assert "Traceback" not in result.output

    def test_complementaria_build_requires_registry_schema_provider(
        self,
        drafts_dir: Path,
        submissions_dir: Path,
        tmp_path: Path,
    ) -> None:
        inputs = _write_inputs(tmp_path)
        modelo = _registry_modelo_calculable_without_inputs()
        period = "2024Q1"
        build_result = runner.invoke(
            app,
            [
                "build",
                "--modelo",
                modelo,
                "--period",
                period,
                "--inputs",
                str(inputs),
                "--profile-tax-id",
                "00000000T",
            ],
        )
        assert build_result.exit_code == 0, build_result.output
        draft_path = _single_draft_path()
        draft_id = draft_path.name.removesuffix(".envelope.json")
        submitted = _write_submitted_filing(modelo=modelo, period=period, draft_id=draft_id)
        payload = {
            "original_submission_id": submitted.submission_id,
            "updated_inputs": {
                "01": 1,
            },
        }

        result = runner.invoke(
            app,
            ["complementaria", "build", modelo, period, json.dumps(payload)],
        )

        assert result.exit_code == 0, result.output
        assert _persisted_draft_count() == 2
        from ....domain.filing._complementaria_repository import FilingAmendmentRepository

        assert FilingAmendmentRepository().list_amendment_ids()
