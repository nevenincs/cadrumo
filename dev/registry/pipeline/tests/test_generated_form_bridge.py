"""M190 generated-form bridge refusals and form companion detection."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.tests.authored_editions import open_ended_revision, revision_covering

from ..generated_form_bridge import generated_form_companion_changed, prepare_generated_form_bridge

pytestmark = [pytest.mark.hex_core]

_OPEN_ENDED = open_ended_revision("190")
_REVISION = str(_OPEN_ENDED.id)
_EXERCISE = _OPEN_ENDED.valid_from.year
# Any other authored edition stands for the target the reviewed repair does not name.
_OTHER_REVISION = str(revision_covering("190", _EXERCISE - 1).id)
_SOURCE = "aeat-dr-190-2025"
_SOURCE_SHA = "a7d1092f78620431812354e560a5146a3ae244e0aed69d9d58c353370ba0134d"
_OLD_MANIFEST_SHA = "c686e3d09a298c32d8025ef9c98f26455548be20d6796df8df05c8509a4d222a"


@pytest.mark.parametrize("defect", ["modelo", "revision", "source", "source_sha", "manifest"])
@pytest.mark.unit
def test_m190_bridge_refuses_an_unreviewed_repair_before_source_access(tmp_path: Path, defect: str) -> None:
    """A reviewed source pin grants no authority to repair another target or package."""
    with pytest.raises(RegistryValidationError, match="exact reviewed source and old target"):
        prepare_generated_form_bridge(
            registry_root=tmp_path / "absent-live",
            candidate_root=tmp_path / "absent-candidate",
            modelo="191" if defect == "modelo" else "190",
            revision=_OTHER_REVISION if defect == "revision" else _REVISION,
            source_ref=f"aeat-dr-190-{_EXERCISE - 1}" if defect == "source" else _SOURCE,
            source_sha256="0" * 64 if defect == "source_sha" else _SOURCE_SHA,
            expected_manifest_sha256="0" * 64 if defect == "manifest" else _OLD_MANIFEST_SHA,
        )


@pytest.mark.integration
def test_unchanged_authored_form_needs_no_bridge_while_a_changed_one_is_regenerated(tmp_path: Path) -> None:
    """A provenance-only republication keeps an authored form without regenerating it."""
    live_root = bundled_path("registry", "aeat")
    form = Path("modelos") / "190" / "revisions" / _REVISION / "form_layouts" / "0001-form-layout.toml"
    assert b'seed_source = "authored"' in (live_root / form).read_bytes()
    candidate_root = tmp_path / "candidate"
    shutil.copytree(live_root, candidate_root)

    assert not generated_form_companion_changed(live_root, candidate_root, "190", _REVISION)

    (candidate_root / form).write_bytes((live_root / form).read_bytes() + b"\n# staged comment\n")
    assert not generated_form_companion_changed(live_root, candidate_root, "190", _REVISION)

    staged = (live_root / form).read_bytes().replace(b"human review remain pending", b"human review pending")
    assert staged != (live_root / form).read_bytes()
    (candidate_root / form).write_bytes(staged)
    with pytest.raises(RegistryValidationError, match="differs from its fresh canonical generation"):
        generated_form_companion_changed(live_root, candidate_root, "190", _REVISION)
