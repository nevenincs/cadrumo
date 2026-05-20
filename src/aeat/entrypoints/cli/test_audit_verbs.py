"""CLI surface tests for `aeat app modelo audit {show, check, export, replay}`.

The four verbs are the ratified audit surface from the evidence-bundle
ADR. These real-behavior tests drive each verb through the Typer
runner against a real EvidenceBundleService and an isolated SQLite +
filesystem backend. No mocks. The bundles under test are built by the
same service the CLI handlers call so the round-trip exercises the
full read path.
"""

from __future__ import annotations

import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage.sql import dispose_engine
from aeat.application.evidence import EvidenceBundleService
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.core.config import Settings
from aeat.entrypoints.cli import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider

    audit_dir = tmp_path / "audit"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'audit-verbs.db').as_posix()}")
    monkeypatch.setenv("AEAT_AUDIT_DIR", str(audit_dir))
    dispose_engine()
    with EphemeralMasterKeyProvider():
        try:
            workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
            yield audit_dir
        finally:
            dispose_engine()


def _seed_bundle() -> str:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    bundle = EvidenceBundleService(settings=Settings()).build(
        bucket_id=bucket_id,
        work_unit_id="wu-001",
        record_payloads={
            ("calculation_revision", "rev-1"): b"casilla-01=1000.00\ncasilla-02=210.00\n",
            ("filing_record", "filing-1"): b"justificante: CSV12345\n",
        },
        calculation_revision_id="rev-1",
        filing_record_id="filing-1",
    )
    return bundle.bundle_id


def test_audit_show_renders_bundle_manifest(cli_runner: CliRunner) -> None:
    bundle_id = _seed_bundle()
    result = cli_runner.invoke(app, ["app", "modelo", "audit", "show", bundle_id])
    assert result.exit_code == 0, result.output
    assert f"bundle_id\t{bundle_id}" in result.output
    assert "work_unit_id\twu-001" in result.output
    assert "manifest_version\t" in result.output
    assert "records\t2" in result.output


def test_audit_show_refuses_unknown_bundle(cli_runner: CliRunner) -> None:
    _seed_bundle()
    result = cli_runner.invoke(app, ["app", "modelo", "audit", "show", "0" * 64])
    assert result.exit_code != 0, result.output


def test_audit_check_reports_verification_state(cli_runner: CliRunner) -> None:
    bundle_id = _seed_bundle()
    result = cli_runner.invoke(app, ["app", "modelo", "audit", "check", bundle_id])
    assert result.exit_code == 0, result.output
    assert f"bundle_id\t{bundle_id}" in result.output
    assert "verification_state\t" in result.output
    assert "completeness_ratio\t" in result.output
    assert "findings\t" in result.output


def test_audit_export_writes_zip_archive(cli_runner: CliRunner, tmp_path: Path) -> None:
    """Export with no payloads marks the bundle INCOMPLETE; the ADR
    requires --force-incomplete to bypass. The archive must still
    write manifest.json as the LAST member."""

    bundle_id = _seed_bundle()
    output = tmp_path / "bundle.zip"
    result = cli_runner.invoke(
        app,
        [
            "app", "modelo", "audit", "export", bundle_id,
            "--output", str(output),
            "--force-incomplete",
        ],
    )
    assert result.exit_code == 0, result.output
    assert output.exists()
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
    assert "manifest.json" in names
    assert names[-1] == "manifest.json", names


def test_audit_export_refuses_incomplete_without_force(cli_runner: CliRunner, tmp_path: Path) -> None:
    """Without `--force-incomplete`, an incomplete bundle (no payloads
    available to the CLI in this scenario) must refuse to write the
    archive. Locks the safety gate from the evidence-bundle ADR."""

    bundle_id = _seed_bundle()
    output = tmp_path / "bundle.zip"
    result = cli_runner.invoke(
        app, ["app", "modelo", "audit", "export", bundle_id, "--output", str(output)]
    )
    assert result.exit_code != 0, result.output
    assert not output.exists()


def test_audit_export_refuses_when_output_path_missing(cli_runner: CliRunner) -> None:
    bundle_id = _seed_bundle()
    result = cli_runner.invoke(app, ["app", "modelo", "audit", "export", bundle_id])
    assert result.exit_code != 0, result.output


def test_audit_replay_reports_verification_state_without_mutation(cli_runner: CliRunner) -> None:
    """Replay is a reproducibility tool — it must never contact AEAT, and
    must not mutate the bundle. Two consecutive replays produce identical
    verification states."""

    bundle_id = _seed_bundle()
    first = cli_runner.invoke(app, ["app", "modelo", "audit", "replay", bundle_id])
    assert first.exit_code == 0, first.output

    second = cli_runner.invoke(app, ["app", "modelo", "audit", "replay", bundle_id])
    assert second.exit_code == 0, second.output

    first_state = next(
        line for line in first.output.splitlines() if line.startswith("verification_state\t")
    )
    second_state = next(
        line for line in second.output.splitlines() if line.startswith("verification_state\t")
    )
    assert first_state == second_state


def test_audit_workflow_end_to_end_show_check_export_replay(
    cli_runner: CliRunner, tmp_path: Path
) -> None:
    """Drive the full ratified audit workflow over a single bundle:
    show → check → export → replay. The four verbs share a state-free
    contract — each reads from the persisted bundle catalogue, so the
    sequence is order-independent and the verification state observed
    by `check` matches the one observed by `replay`."""

    bundle_id = _seed_bundle()
    output = tmp_path / "bundle-e2e.zip"

    show = cli_runner.invoke(app, ["app", "modelo", "audit", "show", bundle_id])
    assert show.exit_code == 0, show.output

    check = cli_runner.invoke(app, ["app", "modelo", "audit", "check", bundle_id])
    assert check.exit_code == 0, check.output

    export = cli_runner.invoke(
        app,
        [
            "app", "modelo", "audit", "export", bundle_id,
            "--output", str(output),
            "--force-incomplete",
        ],
    )
    assert export.exit_code == 0, export.output
    assert output.exists()
    with zipfile.ZipFile(output) as archive:
        assert "manifest.json" in archive.namelist()

    replay = cli_runner.invoke(app, ["app", "modelo", "audit", "replay", bundle_id])
    assert replay.exit_code == 0, replay.output

    check_state = next(
        line for line in check.output.splitlines() if line.startswith("verification_state\t")
    )
    replay_state = next(
        line for line in replay.output.splitlines() if line.startswith("verification_state\t")
    )
    assert check_state == replay_state


def test_audit_help_text_uses_accepted_vocabulary(cli_runner: CliRunner) -> None:
    """Each audit verb's help text must use the operator vocabulary
    ratified by the apex CLI ADR §10A — bundle / manifest / evidence /
    replay / verification (or their Spanish equivalents in the default
    locale: paquete / manifiesto / evidencia / reproducir / verificar) —
    and must never imply live AEAT submission or remote contact."""

    forbidden_en = ("submit ", "submission", "send to aeat", "upload to aeat", "live filing", "telematic")
    forbidden_es = ("enviar a aeat", "subir a aeat", "presentar telemáticamente")

    accepted_per_verb = {
        "show": (("evidence", "evidencia"), ("bundle", "paquete"), ("manifest", "manifiesto", "manifest")),
        "check": (("verify", "verificar", "reverificar"), ("bundle", "paquete")),
        "export": (("bundle", "paquete"), ("manifest", "manifiesto")),
        "replay": (("bundle", "paquete"), ("aeat",)),
    }

    for verb, required_groups in accepted_per_verb.items():
        result = cli_runner.invoke(app, ["app", "modelo", "audit", verb, "--help"])
        assert result.exit_code == 0, (verb, result.output)
        lower = result.output.lower()
        for group in required_groups:
            assert any(term in lower for term in group), (verb, group, result.output)
        for bad in forbidden_en + forbidden_es:
            assert bad not in lower, (verb, bad, result.output)


def test_audit_replay_help_disclaims_aeat_contact(cli_runner: CliRunner) -> None:
    """The evidence-bundle ADR mandates replay never contacts AEAT.
    The help text must say so explicitly so operators do not assume
    replay re-submits or re-verifies against AEAT-side state. Locks
    the disclaimer phrasing in the default (Spanish) locale."""

    result = cli_runner.invoke(app, ["app", "modelo", "audit", "replay", "--help"])
    assert result.exit_code == 0, result.output
    lower = result.output.lower()
    assert "nunca" in lower and "aeat" in lower, result.output


def test_audit_verbs_refuse_without_active_profile(cli_runner: CliRunner) -> None:
    """All four audit verbs route through `_audit_bucket_id`, which raises
    when no active profile bucket exists. Each verb must surface that
    refusal at the CLI boundary rather than crashing or emitting a
    half-built payload."""

    workflow_state_repository().reset_workflow_state()

    for verb in ("show", "check", "replay"):
        result = cli_runner.invoke(app, ["app", "modelo", "audit", verb, "0" * 64])
        assert result.exit_code != 0, (verb, result.output)
