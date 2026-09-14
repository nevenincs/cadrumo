"""Exercise compaction through the real canonical declaration loader."""

import shutil
from pathlib import Path

import pytest

from dev.registry.compact import canonical, fingerprint, pack_modelo, publish_staged_tree, toml_comments
from dev.registry.compiler.loader import load_modelo_declarations

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def fixture_tree(tmp_path: Path) -> Path:
    directory = tmp_path / "999"
    revision = directory / "revisions" / "2025"
    section = revision / "casillas"
    section.mkdir(parents=True)
    (directory / "manifest.toml").write_text('[modelo]\nid = "999"\n', encoding="utf-8")
    (revision / "revision.toml").write_text('[revisions."2025"]\nvalid_from = 2025-01-01\n', encoding="utf-8")
    for name, identity in [("0001-first", "B"), ("0002-second", "A")]:
        (section / f"{name}.toml").write_text(
            f'[[revisions."2025".casillas]]\nid = "{identity}" # evidence {identity}\nrequired = false\n',
            encoding="utf-8",
        )
    locales = directory / "locales"
    locales.mkdir()
    (locales / "es.toml").write_text('label = "sin cambios"\n', encoding="utf-8")
    return directory


def test_rehearsal_preserves_live_tree(tmp_path: Path) -> None:
    directory = fixture_tree(tmp_path)
    before = fingerprint(directory)
    receipt = pack_modelo(directory, tmp_path / "work")
    assert receipt["equivalent"] is True
    assert receipt["applied"] is False
    assert receipt["before_files"] == 5
    assert receipt["after_files"] == 4
    assert fingerprint(directory) == before
    assert fingerprint(tmp_path / "work" / "original") == before


def test_apply_preserves_values_order_locales_comments_and_is_idempotent(tmp_path: Path) -> None:
    directory = fixture_tree(tmp_path)
    before = canonical(load_modelo_declarations(directory))
    receipt = pack_modelo(directory, tmp_path / "first", apply=True)
    assert receipt["applied"] is True
    assert canonical(load_modelo_declarations(directory)) == before
    packed = directory / "revisions" / "2025" / "casillas" / "0001-declarations.toml"
    assert toml_comments(packed.read_text(encoding="utf-8")) == ["# evidence B", "# evidence A"]
    assert 'id = "B" # evidence B' in packed.read_text(encoding="utf-8")
    assert 'id = "A" # evidence A' in packed.read_text(encoding="utf-8")
    assert (directory / "locales" / "es.toml").read_text(encoding="utf-8") == 'label = "sin cambios"\n'
    again = pack_modelo(directory, tmp_path / "second", apply=True)
    assert again["writes"] == []
    assert again["deletes"] == []


def test_only_retired_source_defaults_are_removed(tmp_path: Path) -> None:
    directory = fixture_tree(tmp_path)
    manifest = directory / "revisions" / "2025" / "revision.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        + '\n[revisions."2025".source_default_dispositions.casillas]\nreason = "derived"\n',
        encoding="utf-8",
    )
    receipt = pack_modelo(directory, tmp_path / "work", apply=True)
    assert receipt["removed_obsolete_fields"] == ["2025.source_default_dispositions"]
    revision = load_modelo_declarations(directory)["revisions"]["2025"]
    assert "source_default_dispositions" not in revision
    assert revision["casillas"][0]["required"] is False


def test_work_inside_source_is_refused_without_changes(tmp_path: Path) -> None:
    directory = fixture_tree(tmp_path)
    before = fingerprint(directory)
    with pytest.raises(ValueError, match="outside"):
        pack_modelo(directory, directory / "work", apply=True)
    assert fingerprint(directory) == before


def test_comments_do_not_extract_hashes_inside_strings() -> None:
    text = '''value = "# string" # trailing
literal = '# literal'
multiline = """# not a comment
still string""" # final
# standalone
'''
    assert toml_comments(text) == ["# trailing", "# final", "# standalone"]


def test_late_concurrent_edit_rolls_back_our_writes_and_preserves_the_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = tmp_path / "live"
    live.mkdir()
    for name in ("a.toml", "b.toml"):
        (live / name).write_text("before", encoding="utf-8")
    before = fingerprint(live)
    original = tmp_path / "original"
    staged = tmp_path / "staged"
    shutil.copytree(live, original)
    shutil.copytree(live, staged)
    for name in ("a.toml", "b.toml"):
        (staged / name).write_text("after", encoding="utf-8")
    replace = Path.replace

    def concurrent_replace(path: Path, target: Path) -> Path:
        result = replace(path, target)
        if target == live / "a.toml":
            (live / "b.toml").write_text("concurrent", encoding="utf-8")
        return result

    monkeypatch.setattr(Path, "replace", concurrent_replace)
    with pytest.raises(ValueError, match="rolled back"):
        publish_staged_tree(live, staged, original, before)
    assert (live / "a.toml").read_text(encoding="utf-8") == "before"
    assert (live / "b.toml").read_text(encoding="utf-8") == "concurrent"


def test_deleted_files_are_restored_if_final_verification_detects_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = tmp_path / "live"
    live.mkdir()
    (live / "a.toml").write_text("before", encoding="utf-8")
    before = fingerprint(live)
    original = tmp_path / "original"
    staged = tmp_path / "staged"
    shutil.copytree(live, original)
    staged.mkdir()
    unlink = Path.unlink

    def concurrent_unlink(path: Path, missing_ok: bool = False) -> None:
        unlink(path, missing_ok=missing_ok)
        if path == live / "a.toml":
            (live / "new.toml").write_text("concurrent", encoding="utf-8")

    monkeypatch.setattr(Path, "unlink", concurrent_unlink)
    with pytest.raises(ValueError, match="rolled back"):
        publish_staged_tree(live, staged, original, before)
    assert (live / "a.toml").read_text(encoding="utf-8") == "before"
    assert (live / "new.toml").read_text(encoding="utf-8") == "concurrent"
