from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ..analysis import m200_2024_restoration_candidates as subject
from ..analysis.m200_semantic_casilla_candidates import M200CasillaDisposition

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _gap() -> SimpleNamespace:
    return SimpleNamespace(
        disposition=M200CasillaDisposition.REVISION_MISSING_DECLARATION,
        export_field_id="m200-2024.dp200012.f0013",
        authored_token="93",  # noqa: S106 - official casilla token
        label="Importe [00093]",
        source_ref="aeat-dr-200-2024",
        source_sha256="a" * 64,
        aeat_type="Num",
        length=17,
    )


def _historic() -> dict[str, object]:
    return {
        "id": "93",
        "number": "93",
        "section": ["liquidacion_i"],
        "semantic_role": "is_correcciones_aumentos",
        "data_type": "money",
        "required": False,
        "input_kind": "manual",
        "legal_refs": ["ley-27-2014:art-41"],
        "source_refs": ["aeat-dr-200-2024"],
        "export_refs": ["m200-2024.dp200012.f0013"],
    }


def _restoration() -> subject.RestorationCandidate:
    return subject.RestorationCandidate(
        id="00093",
        number="00093",
        section=("liquidacion_i",),
        semantic_role="is_correcciones_aumentos",
        data_type="money",
        required=False,
        input_kind="manual",
        legal_refs=("ley-27-2014:art-41",),
        source_refs=("aeat-dr-200-2024",),
        export_refs=("m200-2024.dp200012.f0013",),
        current_source_sha256="a" * 64,
        historic_commit=subject.HISTORIC_COMMIT,
        historic_path="historic/z2024only-dp200012.toml",
    )


def test_build_uses_current_padded_identity_and_historic_semantics(monkeypatch) -> None:
    entry = SimpleNamespace(
        export_field_id="m200-2024.dp200012.f0013",
        source_refs=("aeat-dr-200-2024",),
        legal_refs=("ley-27-2014:art-41",),
    )
    monkeypatch.setattr(subject, "_load_bundled_candidates", lambda: (_gap(),))
    monkeypatch.setattr(subject, "load_semantic_map", lambda _path: SimpleNamespace(entries=(entry,)))
    monkeypatch.setattr(
        subject,
        "_historic_index",
        lambda: {"m200-2024.dp200012.f0013": (("z2024only-dp200012.toml", _historic()),)},
    )

    accepted, refused = subject.build_bundled_restoration_candidates()

    assert not refused
    assert accepted[0].id == "00093"
    assert accepted[0].export_refs == ("m200-2024.dp200012.f0013",)
    assert accepted[0].semantic_role == "is_correcciones_aumentos"


def test_build_refuses_ambiguous_historic_export_identity(monkeypatch) -> None:
    entry = SimpleNamespace(
        export_field_id="m200-2024.dp200012.f0013",
        source_refs=("aeat-dr-200-2024",),
        legal_refs=("ley-27-2014:art-41",),
    )
    match = ("z2024only-dp200012.toml", _historic())
    monkeypatch.setattr(subject, "_load_bundled_candidates", lambda: (_gap(),))
    monkeypatch.setattr(subject, "load_semantic_map", lambda _path: SimpleNamespace(entries=(entry,)))
    monkeypatch.setattr(subject, "_historic_index", lambda: {entry.export_field_id: (match, match)})

    accepted, refused = subject.build_bundled_restoration_candidates()

    assert not accepted
    assert refused[0].reason == "historic export match count is 2"


def test_semantic_or_type_mismatch_refuses() -> None:
    entry = SimpleNamespace(source_refs=("aeat-dr-200-2024",), legal_refs=("different",))

    assert subject._refusal_reason(_gap(), entry, _historic()) == (
        "historic semantic legal payload disagrees with current reviewed map"
    )


def test_apply_patch_has_deterministic_canonical_path_and_registry_only_content(tmp_path: Path) -> None:
    patch = subject.render_apply_patch((_restoration(),), (), workspace_root=tmp_path)

    assert patch == subject.render_apply_patch((_restoration(),), (), workspace_root=tmp_path)
    assert "*** Add File: src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/casillas/c00093.toml" in patch
    assert 'id = "00093"' in patch
    assert 'export_refs = ["m200-2024.dp200012.f0013"]' in patch
    assert subject.HISTORIC_COMMIT in patch
    assert "historic_path" not in patch
    assert "current_source_sha256" not in patch


def test_apply_patch_refuses_existing_canonical_target(tmp_path: Path) -> None:
    target = tmp_path / subject._canonical_relative_path(_restoration())
    target.parent.mkdir(parents=True)
    target.write_text("existing", encoding="utf-8")

    with pytest.raises(ValueError, match="already exist"):
        subject.render_apply_patch((_restoration(),), (), workspace_root=tmp_path)


def test_apply_patch_refuses_any_dry_run_refusal(tmp_path: Path) -> None:
    refusals = (subject.RestorationRefusal("m200-2024.dp200012.f0013", "ambiguous"),)

    with pytest.raises(ValueError, match="1 restoration refusals"):
        subject.render_apply_patch((_restoration(),), refusals, workspace_root=tmp_path)
