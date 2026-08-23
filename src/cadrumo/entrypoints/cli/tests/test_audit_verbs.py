"""CLI surface tests for `aeat app modelo audit {show, check, export}`.

The four verbs are the ratified audit surface from the evidence-bundle
contract. These real-behavior tests drive each verb through the Typer
runner against a real EvidenceBundleService and an isolated SQLite +
filesystem backend. No mocks. The bundles under test are built by the
same service the CLI handlers call so the round-trip exercises the
full read path.
"""

from __future__ import annotations

import zipfile
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....application.evidence import EvidenceBundleService
from ....application.workflow import workflow_state_repository
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[Path]:
    # "probe-audit", not the taxonomy's "audit": isolated_profile_storage_root
    # overrides only StorageCategory.SECRETS during bucket provisioning, so
    # nothing else derives or re-reads this location -- it is a pure
    # Isolation destination for cadrumo_live_state_dir, never asserted upon.
    live_state_dir = tmp_path / "probe-live-state"
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(cadrumo_live_state_dir=live_state_dir),
        open_test_profile_session("11111111-1111-4111-8111-111111111111"),
    ):
        register_minimal_profile(profile_id="11111111-1111-4111-8111-111111111111")
        yield live_state_dir


_WORK_UNIT_ID = "a" * 64
_REVISION_ID = "b" * 64
_FILING_ID = "c" * 64


def _seed_bundle() -> str:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    bundle = EvidenceBundleService().build(
        bucket_id=bucket_id,
        work_unit_id=_WORK_UNIT_ID,
        record_payloads={
            ("calculation_revision", _REVISION_ID): b"casilla-01=1000.00\ncasilla-02=210.00\n",
            ("filing_record", _FILING_ID): b"justificante: CSV12345\n",
        },
        calculation_revision_id=_REVISION_ID,
        filing_record_id=_FILING_ID,
    )
    return bundle.bundle_id


def test_audit_show_renders_bundle_manifest() -> None:
    bundle_id = _seed_bundle()
    result = _invoke(["app", "modelo", "audit", "show", bundle_id])
    assert result.exit_code == 0, result.output
    assert f"bundle_id\t{bundle_id}" in result.output
    assert f"work_unit_id\t{_WORK_UNIT_ID}" in result.output
    assert "manifest_version\t" in result.output
    assert "records\t2" in result.output


def test_audit_show_refuses_unknown_bundle() -> None:
    _seed_bundle()
    result = _invoke(["app", "modelo", "audit", "show", "0" * 64])
    assert result.exit_code != 0, result.output


def test_audit_check_reports_verification_state() -> None:
    bundle_id = _seed_bundle()
    result = _invoke(["app", "modelo", "audit", "check", bundle_id])
    assert result.exit_code == 0, result.output
    assert f"bundle_id\t{bundle_id}" in result.output
    assert "verification_state\t" in result.output
    assert "completeness_ratio\t" in result.output
    assert "findings\t" in result.output


def test_audit_export_writes_zip_archive(tmp_path: Path) -> None:
    """Export with no payloads marks the bundle INCOMPLETE; the contract
    requires --force-incomplete to bypass. The archive must still
    write manifest.json as the LAST member."""

    bundle_id = _seed_bundle()
    output = tmp_path / "bundle.zip"
    result = _invoke(
        [
            "app",
            "modelo",
            "audit",
            "export",
            bundle_id,
            "--output",
            str(output),
            "--force-incomplete",
        ],
    )
    assert result.exit_code == 0, result.output
    assert output.exists()
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
    assert "manifest.json" in names
    assert names[-1] == "manifest.json", names


def test_audit_export_refuses_incomplete_without_force(tmp_path: Path) -> None:
    """Without `--force-incomplete`, an incomplete bundle (no payloads
    available to the CLI in this scenario) must refuse to write the
    archive. Locks the evidence-bundle safety gate."""

    bundle_id = _seed_bundle()
    output = tmp_path / "bundle.zip"
    result = _invoke(["app", "modelo", "audit", "export", bundle_id, "--output", str(output)])
    assert result.exit_code != 0, result.output
    assert not output.exists()


def test_audit_export_refuses_when_output_path_missing() -> None:
    bundle_id = _seed_bundle()
    result = _invoke(["app", "modelo", "audit", "export", bundle_id])
    assert result.exit_code != 0, result.output


def test_audit_replay_command_is_removed() -> None:
    """`modelo audit replay` was retired: it was `check` under a second, weaker
    name. Invoking it must fail as an unknown command."""

    bundle_id = _seed_bundle()
    result = _invoke(["app", "modelo", "audit", "replay", bundle_id])
    assert result.exit_code != 0, result.output


def test_audit_replay_result_schema_is_not_registered() -> None:
    """The retired replay leaf's result schema (`modelo.audit.replay`) must no
    longer be a registered output schema."""

    from .._command_schema import command_schema_types

    assert "modelo.audit.replay" not in command_schema_types()


def test_audit_workflow_end_to_end_show_check_export(tmp_path: Path) -> None:
    """Drive the full ratified audit workflow over a single bundle:
    show → check → export. The verbs share a state-free contract — each reads
    from the persisted bundle catalogue, so the sequence is order-independent."""

    bundle_id = _seed_bundle()
    output = tmp_path / "bundle-e2e.zip"

    show = _invoke(["app", "modelo", "audit", "show", bundle_id])
    assert show.exit_code == 0, show.output

    check = _invoke(["app", "modelo", "audit", "check", bundle_id])
    assert check.exit_code == 0, check.output

    export = _invoke(
        [
            "app",
            "modelo",
            "audit",
            "export",
            bundle_id,
            "--output",
            str(output),
            "--force-incomplete",
        ],
    )
    assert export.exit_code == 0, export.output
    assert output.exists()
    with zipfile.ZipFile(output) as archive:
        assert "manifest.json" in archive.namelist()


def test_audit_help_text_uses_accepted_vocabulary() -> None:
    """Each audit verb's help text must use the operator vocabulary
    bundle / manifest / evidence / verification (or their Spanish equivalents
    in the default locale: paquete / manifiesto / evidencia / verificar) — and
    must never imply live AEAT submission or remote contact."""

    forbidden_en = ("submit ", "submission", "send to aeat", "upload to aeat", "live filing", "telematic")
    forbidden_es = ("enviar a aeat", "subir a aeat", "presentar telemáticamente")

    accepted_per_verb = {
        "show": (("evidence", "evidencia"), ("bundle", "paquete"), ("manifest", "manifiesto", "manifest")),
        "check": (("verify", "verificar", "reverificar"), ("bundle", "paquete")),
        "export": (("bundle", "paquete"), ("manifest", "manifiesto")),
    }

    # A forbidden term is only a violation when it *asserts* a live path.
    # A disclaimer ("never performs submission", "nunca contacta con AEAT")
    # contains the same words to deny them — so a bare substring ban is a
    # false positive. Require the term to be un-negated to count as a hit.
    negations = ("never", "not ", "no ", "without ", "nunca", "ni ", "sin ")

    for verb, required_groups in accepted_per_verb.items():
        result = _invoke(["app", "modelo", "audit", verb, "--help"])
        assert result.exit_code == 0, (verb, result.output)
        lower = result.output.lower()
        for group in required_groups:
            assert any(term in lower for term in group), (verb, group, result.output)
        # Collapse help-panel line wrapping so a negation and the term it
        # negates land adjacent regardless of where the renderer broke.
        normalised = " ".join(lower.split())
        for bad in forbidden_en + forbidden_es:
            idx = normalised.find(bad)
            while idx != -1:
                preceding = normalised[max(0, idx - 28) : idx]
                assert any(neg in preceding for neg in negations), (verb, bad, result.output)
                idx = normalised.find(bad, idx + 1)


def test_audit_verbs_refuse_without_active_profile() -> None:
    """The audit verbs route through `_active_bucket_id`, which raises when no
    active profile bucket exists. Each verb must surface that refusal at the CLI
    boundary rather than crashing or emitting a half-built payload."""

    workflow_state_repository().reset_workflow_state()

    for verb in ("show", "check"):
        result = _invoke(["app", "modelo", "audit", verb, "0" * 64])
        assert result.exit_code != 0, (verb, result.output)
