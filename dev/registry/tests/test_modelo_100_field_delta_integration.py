"""Regression coverage for the live Modelo 100 whole-model migration path."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..edition_delta_migration import migrate_modelo_100_field_deltas
from ..modelo_100_family_delta import convert

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_LIVE = REPO_ROOT / "src/cadrumo/_data/registry/aeat/modelos/100"


@pytest.fixture(scope="module")
def converted(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, object]]:
    area = tmp_path_factory.mktemp("m100-whole-model")
    registry_root = area / "registry/aeat"
    modelo = registry_root / "modelos/100"
    modelo.parent.mkdir(parents=True)
    shutil.copytree(_LIVE, modelo)
    result = dict(
        migrate_modelo_100_field_deltas(
            registry_root=registry_root,
            work_dir=area / "first-run",
            apply=True,
        )
    )
    return registry_root, result


def test_existing_casilla_delta_chain_continues_through_remaining_families(
    converted: tuple[Path, dict[str, object]],
) -> None:
    _root, result = converted

    assert result["already_delta_authored"] is True
    assert result["file_content_changes"] > 0
    assert result["applied"] is True
    assert result["complete"] is True


def test_redundant_override_leaves_are_removed_and_coverage_is_complete(
    converted: tuple[Path, dict[str, object]],
) -> None:
    _root, result = converted
    after = result["after"]

    assert result["pruned_redundant_override_leaves"] == 23
    assert isinstance(after, dict)
    assert after["redundant_overrides"] == 0
    assert after["unresolved_duplication"] == ()
    assert after["blocked_work"] == ()


def test_repeated_execution_is_a_genuine_minimal_no_op(
    converted: tuple[Path, dict[str, object]], tmp_path: Path
) -> None:
    registry_root, first = converted

    second = migrate_modelo_100_field_deltas(
        registry_root=registry_root,
        work_dir=tmp_path / "second-run",
        apply=True,
    )

    assert second["before_fingerprint"] == first["after_fingerprint"] == second["after_fingerprint"]
    assert second["file_content_changes"] == 0
    assert second["pruned_redundant_override_leaves"] == 0
    assert second["complete"] is True
    assert second["applied"] is False


def test_partial_family_enrolment_continues_instead_of_skipping_revision(
    converted: tuple[Path, dict[str, object]], tmp_path: Path
) -> None:
    registry_root, _result = converted
    source = tmp_path / "source"
    candidate = tmp_path / "candidate"
    shutil.copytree(registry_root / "modelos/100", source)
    shutil.copytree(
        _LIVE / "revisions/2021/applicability",
        source / "revisions/2021/applicability",
    )

    report = convert(source, candidate)

    assert any(
        row["revision"] == "2021" and row["family"] == "applicability"
        for row in report["by_revision_family"]
    )
    assert not (candidate / "revisions/2021/applicability").exists()
