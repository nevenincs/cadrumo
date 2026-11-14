"""The persona world tool prepares the returns the table plans, in a profile that outlives the run."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.custody.tests.portable_password_custody import portable_password_custody
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_session_setup import reset_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.values import ProfileSetupState
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.tests.persona_materialisation import PERSONA_PROFILE_CREDENTIAL, year_envelope

from .. import desktop_persona_world
from ..desktop_agent_live.disposable_root import create_root, remove_root, temporary_parent
from ..paths import STORAGE_ROOT_ENV

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

PERSONA = "asalariada-familia"


@pytest.fixture
def disposable_root() -> Iterator[Path]:
    """A fresh ``cadrumo-e2e-*`` root in the account's temporary folder, outside every Git project."""
    parent = temporary_parent(os.environ)
    root = create_root(parent)
    try:
        yield root
    finally:
        assert remove_root(root, parent) == []


def _registry_horizon() -> int:
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation).horizon


def _stored_profile(storage_root: Path, profile_id: str) -> tuple[str, ProfileSetupState, dict[str, bool]]:
    """Sign in to the stored profile with the materialiser's passphrase and read its record and work units back.

    The work units map each stored work unit id to whether it holds a calculation.
    """
    identity = UUID(profile_id)
    with (
        bundled_indexed_authority().operation() as operation,
        profile_adapter_composition(),
        isolated_profile_storage_root(tmp_path=storage_root.parent),
        portable_password_custody(),
    ):
        decode = operation.profile_decode_context()
        try:
            authenticate_profile_for_invocation(
                name=profile_id, passphrase_callback=lambda: PERSONA_PROFILE_CREDENTIAL, profile_decode_context=decode
            )
            record = ProfileRecordRepository.for_current_session(identity, profile_decode_context=decode).load(identity)
            catalogue = WorkUnitCatalogueRepository(bucket_id=profile_id).load()
        finally:
            close_active_bucket_session()
            reset_test_profile_session()
    held = {unit_id: unit.current_calculation_revision_id is not None for unit_id, unit in catalogue.work_units.items()}
    return str(record.profile_id), record.setup_state, held


@pytest.mark.parametrize(
    ("persona", "leaves_uncalculated"), [(PERSONA, False), ("traductora-profesional", True)], ids=["held", "open"]
)
def test_world_holds_the_rows_the_table_plans_and_a_profile_that_signs_in(
    disposable_root: Path, capsys: pytest.CaptureFixture[str], persona: str, leaves_uncalculated: bool
) -> None:
    horizon = _registry_horizon()
    ambient = os.environ.get(STORAGE_ROOT_ENV)

    status = desktop_persona_world.main(
        ["--persona", persona, "--horizon", str(horizon), "--storage-root", str(disposable_root / "world")]
    )

    assert status == 0
    assert os.environ.get(STORAGE_ROOT_ENV) == ambient
    report = json.loads(capsys.readouterr().out)

    from ..acceptance.persona_table import sweep

    plans, _emitted = sweep.plan_rows(persona, horizon)
    assert [(row["modelo"], row["year"], row["period"]) for row in report["rows"]] == [
        (plan.modelo, plan.year, plan.period) for plan in plans
    ]
    assert report["persona"] == persona
    assert report["horizon"] == horizon
    assert report["passphrase_source"] == desktop_persona_world.CREDENTIAL_SOURCE
    assert PERSONA_PROFILE_CREDENTIAL not in json.dumps(report)
    assert any(row["prepared"] for row in report["rows"])
    for row in report["rows"]:
        assert "m303_evidence" in row
        if row["prepared"]:
            assert row["work_unit_id"], row
            assert row["pre_calculate_outcome"] is None
            assert row["stages"][0] == "create"
            assert "calculate" not in row["stages"] or row["calculate_inherited_reason"], row
            assert row["driver_calculate"] in {desktop_persona_world.NOT_RUN, "calculated", "refused"}
            assert (row["driver_calculate"] == desktop_persona_world.NOT_RUN) == (
                row["calculate_inherited_reason"] is None and row["driver_calculate"] != "refused"
            ), row
        else:
            assert row["pre_calculate_outcome"], row
            assert row["stages"] == []
            assert row["driver_calculate"] is None
            assert row["calculate_inherited_reason"] is None
    assert PERSONA_PROFILE_CREDENTIAL not in json.dumps(report)

    storage_root = Path(report["storage_root"])
    assert storage_root.is_dir()
    assert storage_root.name == "cadrumo-storage"
    assert storage_root.is_relative_to(disposable_root)
    assert (storage_root / "buckets" / report["profile_id"]).is_dir()
    stored_id, setup_state, held = _stored_profile(storage_root, report["profile_id"])
    assert stored_id == report["profile_id"]
    assert setup_state is ProfileSetupState.COMPLETE
    prepared = [row for row in report["rows"] if row["prepared"]]
    # A row reported not run holds no calculation in the stored profile; one reported calculated holds one.
    assert any(row["driver_calculate"] == desktop_persona_world.NOT_RUN for row in prepared) is leaves_uncalculated
    for row in prepared:
        assert held[row["work_unit_id"]] is (row["driver_calculate"] != desktop_persona_world.NOT_RUN), row


def test_a_root_that_holds_files_is_refused(tmp_path: Path) -> None:
    (tmp_path / "held.txt").write_text("held", encoding="utf-8")

    assert desktop_persona_world.refuse_storage_root(tmp_path) is not None
    with pytest.raises(SystemExit) as refusal:
        desktop_persona_world.main(["--persona", PERSONA, "--horizon", "1", "--storage-root", str(tmp_path)])
    assert refusal.value.code == 2


def test_a_relative_root_is_refused() -> None:
    assert desktop_persona_world.refuse_storage_root(Path("world")) is not None


def test_a_root_inside_a_git_project_is_refused(disposable_root: Path) -> None:
    project = disposable_root / "project"
    (project / ".git").mkdir(parents=True)

    assert desktop_persona_world.refuse_storage_root(project / "world") is not None
    assert desktop_persona_world.refuse_storage_root(disposable_root / "world") is None


def test_an_unknown_persona_is_refused(disposable_root: Path) -> None:
    with pytest.raises(SystemExit) as refusal:
        desktop_persona_world.main(
            ["--persona", "no-such-persona", "--horizon", "1", "--storage-root", str(disposable_root / "world")]
        )
    assert refusal.value.code == 2
