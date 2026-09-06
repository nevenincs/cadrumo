"""Real filesystem proofs for the generated casilla export-refs writer."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..pipeline._casilla_export_refs import write_generated_casilla_export_refs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_generated_casilla_export_refs_replace_a_displaced_field_with_no_stale_reference(tmp_path: Path) -> None:
    """Generator-owned refs are exactly the generated casilla field relation."""
    casillas = tmp_path / "casillas"
    casillas.mkdir()
    path = casillas / "0001-casillas.toml"
    path.write_text(
        """[[revisions.current.casillas]]
id = "addressed"
source_refs = ["source"]

[[revisions.current.casillas]]
id = "displaced"
source_refs = ["source"]
export_refs = ["generated.displaced"]
""",
        encoding="utf-8",
    )

    written = write_generated_casilla_export_refs(
        tmp_path,
        export_refs_by_casilla={"addressed": ("generated.addressed",)},
    )

    assert written == (path,)
    rendered = path.read_text(encoding="utf-8")
    assert 'id = "addressed"\nsource_refs = ["source"]\nexport_refs = ["generated.addressed"]' in rendered
    assert 'id = "displaced"\nsource_refs = ["source"]\nexport_refs' not in rendered


def test_generated_casilla_export_refs_accepts_toml_literal_and_basic_ids_but_not_nested_decoys(
    tmp_path: Path,
) -> None:
    """Declaration IDs are TOML strings, not a generator-specific quote style."""
    casillas = tmp_path / "casillas"
    casillas.mkdir()
    path = casillas / "quotes-and-decoy.toml"
    path.write_text(
        """[[revisions.current.casillas]]
id = 'literal-id'
source_refs = ["source"]

[[revisions.current.casillas]]
id = "basic-id"
source_refs = ["source"]

[[revisions.current.casillas]]
source_refs = ["source"]
[revisions.current.casillas.constraints]
id = "nested-decoy"
""",
        encoding="utf-8",
    )

    written = write_generated_casilla_export_refs(
        tmp_path,
        export_refs_by_casilla={
            "literal-id": ("generated.literal",),
            "basic-id": ("generated.basic",),
        },
    )

    assert written == (path,)
    rendered = path.read_text(encoding="utf-8")
    assert 'id = \'literal-id\'\nsource_refs = ["source"]\nexport_refs = ["generated.literal"]' in rendered
    assert 'id = "basic-id"\nsource_refs = ["source"]\nexport_refs = ["generated.basic"]' in rendered
    assert "nested-decoy\nexport_refs" not in rendered

    with pytest.raises(RegistryValidationError, match="nested-decoy"):
        write_generated_casilla_export_refs(
            tmp_path,
            export_refs_by_casilla={"nested-decoy": ("generated.decoy",)},
        )


def test_generated_casilla_export_refs_follows_the_entire_multiline_source_refs_value(tmp_path: Path) -> None:
    """Derived refs never split a TOML array while preserving declaration bytes."""
    casillas = tmp_path / "casillas"
    casillas.mkdir()
    path = casillas / "multiline-source-refs.toml"
    path.write_text(
        """[[revisions.current.casillas]]
id = '00067'
source_refs = [
    'aeat-dr-200-2024',
    'aeat-modelo-200-manual-2024',
]
""",
        encoding="utf-8",
    )

    write_generated_casilla_export_refs(
        tmp_path,
        export_refs_by_casilla={"00067": ("m200-2024.record.field",)},
    )

    rendered = path.read_text(encoding="utf-8")
    assert "    'aeat-modelo-200-manual-2024',\n]\nexport_refs" in rendered
    assert tomllib.loads(rendered)["revisions"]["current"]["casillas"][0]["export_refs"] == [
        "m200-2024.record.field",
    ]


def test_generated_casilla_export_refs_ignores_array_brackets_inside_toml_comments(tmp_path: Path) -> None:
    """A comment cannot make the textual writer terminate a real array early."""
    casillas = tmp_path / "casillas"
    casillas.mkdir()
    path = casillas / "commented-source-refs.toml"
    path.write_text(
        """[[revisions.current.casillas]]
id = '00067'
source_refs = [
    'aeat-dr-200-2024', # ] a comment is not TOML structure
    'aeat-modelo-200-manual-2024',
]
""",
        encoding="utf-8",
    )

    write_generated_casilla_export_refs(
        tmp_path,
        export_refs_by_casilla={"00067": ("m200-2024.record.field",)},
    )

    rendered = path.read_text(encoding="utf-8")
    assert "'aeat-modelo-200-manual-2024',\n]\nexport_refs" in rendered
    assert tomllib.loads(rendered)["revisions"]["current"]["casillas"][0]["export_refs"] == [
        "m200-2024.record.field",
    ]


def test_generated_casilla_export_refs_refuses_an_unterminated_multiline_source_refs_array(tmp_path: Path) -> None:
    casillas = tmp_path / "casillas"
    casillas.mkdir()
    (casillas / "unterminated-source-refs.toml").write_text(
        """[[revisions.current.casillas]]
id = '00067'
source_refs = [
    'aeat-dr-200-2024',
""",
        encoding="utf-8",
    )

    with pytest.raises(RegistryValidationError, match="unterminated source_refs array"):
        write_generated_casilla_export_refs(
            tmp_path,
            export_refs_by_casilla={"00067": ("m200-2024.record.field",)},
        )


def test_generated_casilla_export_refs_refuses_before_writing_any_file(tmp_path: Path) -> None:
    """A conflict discovered on one file must not leave an earlier file mutated.

    These ``.toml`` files are the live registry tree, not a staging copy a
    caller can roll back, so the completeness/conflict guard has to run before
    the first write rather than after it. ``a.toml`` sorts ahead of ``b.toml``
    under :func:`~cadrumo.core.directory_scan.scan_directory`'s deterministic
    ordering, so it is the one that would have been written first.
    """
    casillas = tmp_path / "casillas"
    casillas.mkdir()
    a_path = casillas / "a.toml"
    a_original = '[[revisions.current.casillas]]\nid = "010"\nsource_refs = ["source"]\n'
    a_path.write_text(a_original, encoding="utf-8")
    b_path = casillas / "b.toml"
    b_original = (
        '[[revisions.current.casillas]]\n'
        'id = "020"\n'
        'source_refs = ["source"]\n'
        'export_refs = ["existing.other"]\n'
    )
    b_path.write_text(b_original, encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="disagreeing answers"):
        write_generated_casilla_export_refs(
            tmp_path,
            export_refs_by_casilla={"010": ("generated.new",), "020": ("generated.conflict",)},
        )

    assert a_path.read_text(encoding="utf-8") == a_original, "the earlier file was written before the refusal"
    assert b_path.read_text(encoding="utf-8") == b_original


def test_generated_casilla_export_refs_missing_casilla_leaves_matched_files_unwritten(tmp_path: Path) -> None:
    """A layout addressing an undeclared casilla must not partially apply.

    Every other casilla the layout addresses is present and would otherwise
    write cleanly; the completeness check still has to run before any of
    those writes, not after.
    """
    casillas = tmp_path / "casillas"
    casillas.mkdir()
    path = casillas / "a.toml"
    original = '[[revisions.current.casillas]]\nid = "010"\nsource_refs = ["source"]\n'
    path.write_text(original, encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="does not declare"):
        write_generated_casilla_export_refs(
            tmp_path,
            export_refs_by_casilla={"010": ("generated.new",), "absent": ("generated.absent",)},
        )

    assert path.read_text(encoding="utf-8") == original, "the matched file was written before the refusal"
