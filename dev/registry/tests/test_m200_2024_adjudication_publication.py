"""Safety tests specific to the M200 S14/S15 publisher's target path."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..analysis import m200_2024_adjudication_publication as subject
from ..analysis.m200_2024_reviewed_promotions import build_m200_2024_reviewed_promotion_snapshot
from ..analysis.m200_2024_template_adjudications import render_canonical_declaration as render_template
from ..analysis.m200_2024_unique_adjudications import render_canonical_declaration as render_unique

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_target_path_refuses_an_intermediate_link_before_any_transaction(tmp_path: Path) -> None:
    root = tmp_path / "registry" / "aeat"
    root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "modelos"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError as exc:  # pragma: no cover - Windows host policy can deny link creation.
        pytest.skip(f"host does not permit link detector fixture: {exc}")

    with pytest.raises(RegistryValidationError, match="casilla path is unsafe"):
        subject._casillas_root(root)


def test_target_receipt_fingerprints_nested_non_toml_members(tmp_path: Path) -> None:
    root = tmp_path / "casillas"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / "c00001.toml").write_text("first\n", encoding="utf-8")
    (nested / "unexpected.bin").write_bytes(b"must-be-bound\n")

    fingerprint = dict(subject._tree_fingerprint(root))

    assert set(fingerprint) == {"c00001.toml", "nested/unexpected.bin"}


def test_unaffected_receipts_refuse_a_structurally_valid_unique_byte_drift(tmp_path: Path) -> None:
    snapshot = build_m200_2024_reviewed_promotion_snapshot()
    root = tmp_path / "casillas"
    root.mkdir()
    for row in snapshot.template_authority.adjudications:
        (root / f"c{row.casilla_id}.toml").write_text(
            render_template(snapshot.template_authority, row.casilla_id), encoding="utf-8"
        )
    for row in snapshot.unique_authority.adjudications:
        path = root / f"c{row.casilla_id.replace(':', '+')}.toml"
        path.write_text(render_unique(snapshot.unique_authority, row.casilla_id), encoding="utf-8")
    target = snapshot.unique_authority.adjudications[0]
    path = root / f"c{target.casilla_id.replace(':', '+')}.toml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("required = false", "required = true", 1), encoding="utf-8"
    )

    with pytest.raises(RegistryValidationError, match="not compiler-identical"):
        subject._verify_unaffected_receipts(snapshot, root)


def test_isolated_loader_rejects_a_visible_transaction_artifact(tmp_path: Path) -> None:
    root = tmp_path / "registry" / "aeat"
    artifact = root / "modelos" / "200" / "revisions" / "2024" / f"{subject._STAGE_PREFIX}token"
    artifact.mkdir(parents=True)

    with pytest.raises(RegistryValidationError, match="transaction artifact is loader-visible"):
        subject._reject_visible_transaction_artifacts(root)
